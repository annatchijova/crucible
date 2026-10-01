"""Bounded, byte-preserving transport evidence; not a replay bundle or verdict.

Headers and exception messages are deliberately excluded. Request/response bodies
are private evidence: a provider can echo secrets into them. No redaction is
performed because it would destroy exact-byte evidence.
"""

import base64
import http.client
import urllib.error

from .ir import digest_bytes, digest_payload

CAPTURE_VERSION = 'crucible-executor-capture/v1'
MAX_REQUEST_BYTES = 1_000_000
MAX_RESPONSE_BYTES = 4_000_000


def _read_response(response):
    """Read at most the limit plus one sentinel byte, preserving partial input."""
    parts = []
    remaining = MAX_RESPONSE_BYTES + 1
    complete = False
    error = None
    while remaining:
        try:
            chunk = response.read(min(65536, remaining))
        except http.client.IncompleteRead as exc:
            parts.append(exc.partial[:remaining])
            error = 'incomplete-read'
            break
        except (OSError, http.client.HTTPException):
            error = 'response-read-error'
            break
        if not chunk:
            complete = True
            break
        parts.append(chunk)
        remaining -= len(chunk)
    raw = b''.join(parts)
    exceeded = len(raw) > MAX_RESPONSE_BYTES
    raw = raw[:MAX_RESPONSE_BYTES]
    return {
        'http_status': response.getcode(),
        'body_base64': base64.b64encode(raw).decode('ascii'),
        'body_digest': digest_bytes(raw),
        'complete': complete and not exceeded,
    }, exceeded, error


def capture_exchange(request, *, system_prompt, user_prompt, available, open_request):
    """Capture one prepared Nebius request; never retry or synthesize metadata.

    `attempted` means the opener was invoked, not proof of server receipt.
    RECEIVED means transport EOF, not valid JSON or complete model generation.
    """
    body = request.data
    if type(body) is not bytes or len(body) > MAX_REQUEST_BYTES:
        raise ValueError('capture request exceeds byte limit or is not bytes')
    capture = {
        'schema_version': CAPTURE_VERSION,
        'provider': 'nebius-token-factory',
        'guidance': {'system_prompt': system_prompt, 'user_prompt': user_prompt},
        'request': {'body': body.decode('utf-8'), 'body_digest': digest_bytes(body)},
        'attempted': False,
        'status': 'BLOCKED',
        'response': None,
        'error': 'missing-credential' if not available else None,
    }
    if available:
        capture['attempted'] = True
        response = None
        status = 'RECEIVED'
        try:
            try:
                response = open_request(request, timeout=60)
            except urllib.error.HTTPError as exc:
                response = exc
                status = 'HTTP_ERROR'
            captured, exceeded, error = _read_response(response)
            capture['response'] = captured
            capture['error'] = error
            capture['status'] = ('RESPONSE_LIMIT' if exceeded else
                                 'TRANSPORT_ERROR' if error else status)
        except (OSError, http.client.HTTPException):
            capture['status'] = 'TRANSPORT_ERROR'
            capture['error'] = 'transport-error'
        finally:
            if response is not None:
                response.close()
    capture['capture_digest'] = digest_payload(capture)
    return capture
