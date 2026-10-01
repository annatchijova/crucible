"""Transport evidence is not model success or replay acceptance."""
import base64
import io
import http.client
import json
import urllib.error

import pytest

from crucible.behavioral import NebiusExecutor
from crucible.ir import digest_bytes, digest_payload


def transport(monkeypatch, body, status=200):
    requests = []

    class Response(io.BytesIO):
        def getcode(self):
            return status

    def open_request(request, timeout):
        requests.append(request)
        assert timeout == 60
        return Response(body)

    monkeypatch.setattr('crucible.behavioral.urllib.request.urlopen', open_request)
    return requests


def test_characterizes_existing_empty_guidance_and_missing_usage(monkeypatch):
    """Pin legacy fallback and zero-filled usage, NOT evidence correctness."""
    requests = transport(monkeypatch, b'{"choices":[{"message":{"content":"ok"}}]}')
    result = NebiusExecutor(api_key='dummy').execute('', 'task')
    assert json.loads(requests[0].data)['messages'][0]['content'] == 'You are a helpful assistant.'
    assert result['usage'] == dict(prompt_tokens=0, completion_tokens=0, total_tokens=0)


def test_capture_exact_bytes_and_actual_request_without_authorization(monkeypatch):
    raw = b'{ "choices": [], "id": "test" }\n'
    requests = transport(monkeypatch, raw)
    capture = NebiusExecutor(api_key='dummy-secret').capture_exchange('', 'tarea ñ')
    assert capture['status'] == 'RECEIVED'
    assert capture['request']['body'].encode() == requests[0].data
    assert capture['request']['body_digest'] == digest_bytes(requests[0].data)
    assert capture['guidance']['system_prompt'] == ''
    assert json.loads(capture['request']['body'])['messages'][0]['content'] == 'You are a helpful assistant.'
    assert base64.b64decode(capture['response']['body_base64']) == raw
    assert capture['response']['body_digest'] == digest_bytes(raw)
    assert capture['response']['complete'] is True
    assert 'dummy-secret' not in json.dumps(capture)
    assert 'usage' not in capture['response']
    assert capture['capture_digest'] == digest_payload({k: v for k, v in capture.items() if k != 'capture_digest'})


@pytest.mark.parametrize('raw', [b'not JSON', b'\xff\x00', b'{"choices":[{"finish_reason":"length"}]}'])
def test_capture_preserves_invalid_and_truncated_provider_content(monkeypatch, raw):
    transport(monkeypatch, raw)
    capture = NebiusExecutor(api_key='dummy').capture_exchange('guide', 'task')
    assert base64.b64decode(capture['response']['body_base64']) == raw
    assert capture['status'] == 'RECEIVED'  # transport receipt, never a model verdict


def test_blocked_capture_does_not_call_network(monkeypatch):
    monkeypatch.delenv('NEBIUS_API_KEY', raising=False)
    monkeypatch.setattr('crucible.behavioral.urllib.request.urlopen', lambda *a, **k: pytest.fail('network'))
    capture = NebiusExecutor().capture_exchange('', 'task')
    assert capture['status'] == 'BLOCKED'
    assert capture['attempted'] is False
    assert capture['response'] is None


def test_response_cap_is_explicit_and_retains_only_bounded_prefix(monkeypatch):
    monkeypatch.setattr('crucible.runtime_capture.MAX_RESPONSE_BYTES', 8)
    transport(monkeypatch, b'0123456789abcdef')
    capture = NebiusExecutor(api_key='dummy').capture_exchange('guide', 'task')
    assert capture['status'] == 'RESPONSE_LIMIT'
    assert capture['response']['complete'] is False
    assert base64.b64decode(capture['response']['body_base64']) == b'01234567'


def test_http_error_body_is_preserved_and_closed(monkeypatch):
    stream = io.BytesIO(b'{"error":"quota"}')
    error = urllib.error.HTTPError('https://example.invalid', 429, 'rate limit', {}, stream)
    def fail(*a, **k):
        raise error
    monkeypatch.setattr('crucible.behavioral.urllib.request.urlopen', fail)
    capture = NebiusExecutor(api_key='dummy').capture_exchange('guide', 'task')
    assert capture['status'] == 'HTTP_ERROR'
    assert capture['response']['http_status'] == 429
    assert base64.b64decode(capture['response']['body_base64']) == b'{"error":"quota"}'
    assert stream.closed


def test_transport_exception_does_not_publish_exception_secrets(monkeypatch):
    def fail(*a, **k):
        raise urllib.error.URLError('dummy-secret in exception')
    monkeypatch.setattr('crucible.behavioral.urllib.request.urlopen', fail)
    capture = NebiusExecutor(api_key='dummy-secret').capture_exchange('guide', 'task')
    assert capture['status'] == 'TRANSPORT_ERROR'
    assert capture['response'] is None
    assert 'dummy-secret' not in json.dumps(capture)


def test_oversized_request_fails_before_network(monkeypatch):
    monkeypatch.setattr('crucible.runtime_capture.MAX_REQUEST_BYTES', 8)
    monkeypatch.setattr('crucible.behavioral.urllib.request.urlopen', lambda *a, **k: pytest.fail('network'))
    with pytest.raises(ValueError, match='request.*limit'):
        NebiusExecutor(api_key='dummy').capture_exchange('guide', 'task')


@pytest.mark.parametrize('error', [TimeoutError('secret'), http.client.IncompleteRead(b'partial')])
def test_interrupted_response_preserves_prefix_without_claiming_completion(monkeypatch, error):
    class Response(io.BytesIO):
        calls = 0

        def read(self, size):
            self.calls += 1
            if self.calls == 1:
                return b'prefix'
            raise error

        def getcode(self):
            return 200

    response = Response()
    monkeypatch.setattr('crucible.behavioral.urllib.request.urlopen', lambda *a, **k: response)
    capture = NebiusExecutor(api_key='dummy').capture_exchange('', 'task')
    expected = b'prefixpartial' if isinstance(error, http.client.IncompleteRead) else b'prefix'
    assert base64.b64decode(capture['response']['body_base64']) == expected
    assert capture['status'] == 'TRANSPORT_ERROR'
    assert capture['response']['complete'] is False
    assert response.closed
    assert 'secret' not in json.dumps(capture)


def test_capture_and_legacy_send_identical_body_with_custom_config(monkeypatch):
    requests = transport(monkeypatch, b'{"choices":[{"message":{"content":"ok"}}]}')
    executor = NebiusExecutor(api_key='dummy', model='fixture-model', temperature=1, max_tokens=123)
    executor.execute('', 'task')
    capture = executor.capture_exchange('', 'task')
    assert len(requests) == 2
    assert requests[0].data == requests[1].data == capture['request']['body'].encode()


def test_capture_is_not_silently_accepted_as_replay_bundle(monkeypatch):
    from crucible.replay import validate_bundle
    transport(monkeypatch, b'{}')
    capture = NebiusExecutor(api_key='dummy').capture_exchange('', 'task')
    with pytest.raises(ValueError, match='schema version'):
        validate_bundle(capture)
