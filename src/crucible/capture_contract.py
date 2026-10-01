"""Offline validation/projection of captured Nebius exchanges for replay v2."""

import base64
import binascii
from copy import deepcopy
import json

from .ir import canonical_bytes, digest_bytes, digest_payload
from .replay import _fields, _text
from .runtime_capture import CAPTURE_VERSION, MAX_REQUEST_BYTES, MAX_RESPONSE_BYTES

ADAPTER_VERSION = 'nebius-chat-guidance/v1'
DEFAULT_SYSTEM_PROMPT = 'You are a helpful assistant.'


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result

    def constant(value):
        raise ValueError('nonfinite JSON constant')

    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    except (RecursionError, TypeError, UnicodeError) as exc:
        raise ValueError('invalid captured JSON') from exc


def validate_capture(capture):
    """Validate bytes, schema and status consistency without contacting a provider."""
    try:
        return _validate_capture(capture)
    except (TypeError, KeyError, RecursionError, UnicodeError, binascii.Error) as exc:
        raise ValueError('invalid capture structure') from exc


def _validate_capture(capture):
    _fields(capture, 'schema_version provider guidance request attempted status response error capture_digest', 'capture')
    if capture['schema_version'] != CAPTURE_VERSION:
        raise ValueError('unsupported capture version')
    if len(canonical_bytes(capture)) > 8_000_000:
        raise ValueError('capture byte limit exceeded')
    if capture['provider'] != 'nebius-token-factory':
        raise ValueError('unsupported capture provider')
    _fields(capture['guidance'], 'system_prompt user_prompt', 'guidance')
    for key in capture['guidance']:
        _text(capture['guidance'][key], key, empty=True)
    _fields(capture['request'], 'body body_digest', 'capture request')
    _text(capture['request']['body'], 'request body')
    body = capture['request']['body'].encode('utf-8')
    if len(body) > MAX_REQUEST_BYTES or digest_bytes(body) != capture['request']['body_digest']:
        raise ValueError('capture request byte limit or digest mismatch')
    wire = strict_json(capture['request']['body'])
    _fields(wire, 'model messages temperature max_tokens stream', 'wire request')
    _text(wire['model'], 'model')
    for key in ('temperature', 'max_tokens'):
        if type(wire[key]) is not int or wire[key] < 0:
            raise ValueError('unsupported sampling configuration')
    if wire['stream'] is not False:
        raise ValueError('streaming capture is unsupported')
    expected_messages = [
        {'role': 'system', 'content': capture['guidance']['system_prompt'] or DEFAULT_SYSTEM_PROMPT},
        {'role': 'user', 'content': capture['guidance']['user_prompt']},
    ]
    if wire['messages'] != expected_messages:
        raise ValueError('captured prompt transformation mismatch')
    if type(capture['attempted']) is not bool:
        raise ValueError('invalid attempted flag')
    status, error, response = capture['status'], capture['error'], capture['response']
    if status not in ('BLOCKED', 'RECEIVED', 'HTTP_ERROR', 'TRANSPORT_ERROR', 'RESPONSE_LIMIT'):
        raise ValueError('invalid capture status')
    if status == 'BLOCKED':
        if capture['attempted'] or response is not None or error != 'missing-credential':
            raise ValueError('inconsistent blocked capture')
    elif not capture['attempted']:
        raise ValueError('capture was not attempted')
    if response is None:
        if status != 'BLOCKED' and not (status == 'TRANSPORT_ERROR' and error == 'transport-error'):
            raise ValueError('missing capture response')
    else:
        _fields(response, 'http_status body_base64 body_digest complete', 'captured response')
        if type(response['http_status']) is not int or not 100 <= response['http_status'] <= 599:
            raise ValueError('invalid HTTP status')
        if type(response['complete']) is not bool:
            raise ValueError('invalid complete flag')
        _text(response['body_base64'], 'body_base64', empty=True)
        raw = base64.b64decode(response['body_base64'], validate=True)
        if len(raw) > MAX_RESPONSE_BYTES or base64.b64encode(raw).decode('ascii') != response['body_base64']:
            raise ValueError('invalid response encoding or limit')
        if digest_bytes(raw) != response['body_digest']:
            raise ValueError('capture response digest mismatch')
        if status in ('RECEIVED', 'HTTP_ERROR'):
            expected_http = (200 <= response['http_status'] < 300 if status == 'RECEIVED'
                             else 300 <= response['http_status'] <= 599)
            if not response['complete'] or error is not None or not expected_http:
                raise ValueError('inconsistent received capture')
        elif status == 'RESPONSE_LIMIT':
            if response['complete'] or len(raw) != MAX_RESPONSE_BYTES or error not in (None, 'incomplete-read'):
                raise ValueError('inconsistent limited capture')
        elif status == 'TRANSPORT_ERROR':
            if response['complete'] or error not in ('incomplete-read', 'response-read-error'):
                raise ValueError('inconsistent failed capture')
    if capture['capture_digest'] != digest_payload({k: v for k, v in capture.items() if k != 'capture_digest'}):
        raise ValueError('capture digest mismatch')
    return deepcopy(capture)


def capture_projection(capture):
    """Derive replay request/response from raw evidence, never default missing usage."""
    capture = validate_capture(capture)
    wire = strict_json(capture['request']['body'])
    request = {key: wire[key] for key in ('model', 'temperature', 'max_tokens')}
    request.update(provider=capture['provider'], system_prompt=wire['messages'][0]['content'],
                   user_prompt=wire['messages'][1]['content'])
    response = dict(status='ERROR', output='', output_digest=digest_bytes(b''),
                    response_id=None, finish_reason=None, truncated=None, usage=None,
                    error='capture-not-complete')
    if capture['status'] == 'BLOCKED':
        response.update(status='BLOCKED', error='missing-credential')
    elif capture['status'] == 'RECEIVED':
        try:
            raw = base64.b64decode(capture['response']['body_base64'], validate=True)
            payload = strict_json(raw.decode('utf-8'))
            if type(payload) is not dict or type(payload.get('choices')) is not list or len(payload['choices']) != 1:
                raise ValueError('invalid provider choices')
            choice = payload['choices'][0]
            if type(choice) is not dict or type(choice.get('message')) is not dict:
                raise ValueError('invalid provider message')
            output = choice['message'].get('content')
            _text(output, 'provider output', empty=True)
            output_digest = digest_bytes(output.encode('utf-8'))
            finish, response_id, usage = choice.get('finish_reason'), payload.get('id'), payload.get('usage')
            for value in (finish, response_id):
                if value is not None:
                    _text(value, 'provider metadata')
            if usage is not None:
                # Unknown provider usage extensions remain in raw evidence.
                if type(usage) is not dict:
                    raise ValueError('invalid usage')
                keys = ('prompt_tokens', 'completion_tokens', 'total_tokens')
                if any(key not in usage for key in keys):
                    usage = None
                else:
                    usage = {key: usage[key] for key in keys}
                    if any(type(v) is not int or v < 0 for v in usage.values()):
                        raise ValueError('invalid usage counts')
                    if usage['total_tokens'] != usage['prompt_tokens'] + usage['completion_tokens']:
                        raise ValueError('inconsistent usage counts')
            response.update(status='COMPLETED', output=output, output_digest=output_digest,
                            response_id=response_id, finish_reason=finish,
                            truncated=None if finish is None else finish == 'length', usage=usage, error=None)
        except (ValueError, UnicodeError, RecursionError):
            response['error'] = 'invalid-provider-response'
    return request, response
