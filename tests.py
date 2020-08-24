import contextlib
import inspect
import json
import os
import random
import sys

import pep8
import pytest
from unittest.mock import Mock

import jsonrpc_base
from jsonrpc_base import Server, ProtocolError, TransportError

pytestmark = pytest.mark.asyncio


class DummyFile(object):
    def write(self, x): pass

@contextlib.contextmanager
def block_stderr():
    real_stderr = sys.stderr
    sys.stderr = DummyFile()
    yield
    sys.stderr = real_stderr

class MockTransportError(ValueError):
    """Test exception representing a transport library error."""

class MockServer(Server):

    def __init__(self, url):
        super(MockServer, self).__init__()
        self._url = url
        self._handler = None

    def send_message(self, message):
        """Issue the request to the server and return the method result (if not a notification)"""
        try:
            if isinstance(message, jsonrpc_base.Request):
                data = jsonrpc_base.Request.parse(json.loads(message.serialize()))
            else:
                data = message.serialize()
            response = json.loads(json.dumps(self._handler(data)))
        except Exception as requests_exception:
            raise TransportError('Transport Error', message, requests_exception)

        return message.parse_response(response)


def assertSameJSON(json1, json2):
    """Tells whether two json strings, once decoded, are the same dictionary"""
    assert json.loads(json1) == json.loads(json2)

@pytest.fixture(autouse=True)
def mock_rand():
    """Mock the build in rand method for determinism in tests."""
    random.randint = Mock(return_value=1)

@pytest.fixture
def server():
    """Get the mock server object"""
    return MockServer('http://mock/xmlrpc')


def test_pep8_conformance(server):
    """Test that we conform to PEP8."""

    source_files = []
    project_dir = os.path.dirname(os.path.abspath(__file__))
    package_dir = os.path.join(project_dir, 'jsonrpc_base')
    for root, directories, filenames in os.walk(package_dir):
        source_files.extend([os.path.join(root, f) for f in filenames if f.endswith('.py')])

    pep8style = pep8.StyleGuide(quiet=False, max_line_length=120)
    result = pep8style.check_files(source_files)
    assert result.total_errors == 0

def test_dumps(server):
    # test no args
    assertSameJSON(
        '''{"jsonrpc": "2.0", "method": "my_method_name", "id": 1}''',
        jsonrpc_base.Request('my_method_name', params=None, msg_id=1).serialize()
    )
    # test zero message ID
    assertSameJSON(
        '''{"jsonrpc": "2.0", "method": "my_method_name", "id": 0}''',
        jsonrpc_base.Request('my_method_name', params=None, msg_id=0).serialize()
    )
    # test empty args dict
    assertSameJSON(
        '''{"params": {}, "jsonrpc": "2.0", "method": "my_method_name", "id": 1}''',
        jsonrpc_base.Request('my_method_name', params={}, msg_id=1).serialize()
    )
    # test keyword args
    assertSameJSON(
        '''{"params": {"foo": "bar"}, "jsonrpc": "2.0", "method": "my_method_name", "id": 1}''',
        jsonrpc_base.Request('my_method_name', params={'foo': 'bar'}, msg_id=1).serialize()
    )
    # test positional args
    assertSameJSON(
        '''{"params": ["foo", "bar"], "jsonrpc": "2.0", "method": "my_method_name", "id": 1}''',
        jsonrpc_base.Request('my_method_name', params=('foo', 'bar'), msg_id=1).serialize()
    )
    # test notification
    assertSameJSON(
        '''{"params": ["foo", "bar"], "jsonrpc": "2.0", "method": "my_method_name"}''',
        jsonrpc_base.Request('my_method_name', params=('foo', 'bar'), msg_id=None).serialize()
    )

def test_parse_result(server):
    request = jsonrpc_base.Request('my_message', msg_id=1)
    with pytest.raises(ProtocolError, match='Response is not a dictionary'):
        request.parse_response([])
    with pytest.raises(ProtocolError, match='Response without a result field'):
        request.parse_response({})
    with pytest.raises(ProtocolError) as protoerror:
        body = {"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found"}, "id": "1"}
        request.parse_response(body)
    assert protoerror.value.args[0] == -32601
    assert protoerror.value.args[1] == 'Method not found'

def test_send_message(server):
    empty_server = Server()
    with pytest.raises(NotImplementedError):
        empty_server.send_message(jsonrpc_base.Request('my_method', msg_id=1))

    # catch non-json responses
    with pytest.raises(TransportError) as transport_error:
        def handler(message):
            raise MockTransportError("Transport Error")

        server._handler = handler
        server.send_message(jsonrpc_base.Request('my_method', msg_id=1))

    assert transport_error.value.args[0] == "Error calling method 'my_method': Transport Error"
    assert isinstance(transport_error.value.args[1], MockTransportError)

    # a notification
    def handler(message):
        return 'we dont care about this'
    server._handler = handler
    server.send_message(jsonrpc_base.Request('my_notification', msg_id=None))

def test_exception_passthrough(server):
    with pytest.raises(TransportError) as transport_error:
        def handler(message):
            raise MockTransportError("Transport Error")
        server._handler = handler
        server.foo()
    assert transport_error.value.args[0] == "Error calling method 'foo': Transport Error"
    assert isinstance(transport_error.value.args[1], MockTransportError)

def test_transport_error_constructor(server):
    with pytest.raises(TransportError, match='Test Message'):
        raise TransportError('Test Message')

def test_forbid_private_methods(server):
    """Test that we can't call private class methods (those starting with '_')"""
    with pytest.raises(AttributeError):
        server._foo()

    # nested private method call
    with pytest.raises(AttributeError):
        server.foo.bar._baz()

def test_method_call(server):
    """mixing *args and **kwargs is forbidden by the spec"""
    with pytest.raises(ProtocolError, match='JSON-RPC spec forbids mixing arguments and keyword arguments'):
        server.testmethod(1, 2, a=1, b=2)

def test_method_nesting(server):
    """Test that we correctly nest namespaces"""
    def handler(message):
        return {
            "jsonrpc": "2.0",
            "result": True if message.params[0] == message.method else False,
            "id": 1,
        }
    server._handler = handler

    assert server.nest.testmethod("nest.testmethod")
    assert server.nest.testmethod.some.other.method("nest.testmethod.some.other.method")

def test_calls(server):
    # rpc call with positional parameters:
    def handler1(message):
        assert message.params == [42, 23]
        return {
            "jsonrpc": "2.0",
            "result": 19,
            "id": 1,
        }

    server._handler = handler1
    assert server.subtract(42, 23) == 19

    # rpc call with named parameters
    def handler2(message):
        assert message.params == {'y': 23, 'x': 42}
        return {
            "jsonrpc": "2.0",
            "result": 19,
            "id": 1,
        }

    server._handler = handler2
    assert server.subtract(x=42, y=23) == 19

    # rpc call with a mapping type
    def handler3(message):
        assert message.params == {'foo': 'bar'}
        return {
            "jsonrpc": "2.0",
            "result": None,
            "id": 1,
        }

    server._handler = handler3
    server.foobar({'foo': 'bar'})

def test_notification(server):
    # Verify that we ignore the server response
    def handler(message):
        return {
            "jsonrpc": "2.0",
            "result": 19,
            "id": 3,
        }
    server._handler = handler
    assert server.subtract(42, 23, _notification=True) is None

def test_receive_server_requests(server):
    def event_handler(*args, **kwargs):
        return args, kwargs
    server.on_server_event = event_handler
    server.namespace.on_server_event = event_handler

    response = server.receive_request(jsonrpc_base.Request(
        'on_server_event', msg_id=1))
    args, kwargs = response.result
    assert len(args) == 0
    assert len(kwargs) == 0

    # Test with a zero message ID
    response = server.receive_request(jsonrpc_base.Request(
        'on_server_event', msg_id=0))
    args, kwargs = response.result
    assert len(args) == 0
    assert len(kwargs) == 0

    response = server.receive_request(jsonrpc_base.Request(
        'namespace.on_server_event', msg_id=1))
    args, kwargs = response.result
    assert len(args) == 0
    assert len(kwargs) == 0

    response = server.receive_request(jsonrpc_base.Request(
        'on_server_event', params=['foo', 'bar'], msg_id=1))
    args, kwargs = response.result
    assert args == ('foo', 'bar')
    assert len(kwargs) == 0

    response = server.receive_request(jsonrpc_base.Request(
        'on_server_event', params={'foo': 'bar'}, msg_id=1))
    args, kwargs = response.result
    assert len(args) == 0
    assert kwargs == {'foo': 'bar'}

    with pytest.raises(ProtocolError):
        response = server.receive_request(jsonrpc_base.Request(
            'on_server_event', params="string_params", msg_id=1))

    response = server.receive_request(jsonrpc_base.Request(
        'missing_event', params={'foo': 'bar'}, msg_id=1))
    assert response.error['code'] == -32601
    assert response.error['message'] == 'Method not found'

    response = server.receive_request(jsonrpc_base.Request(
        'on_server_event'))
    assert response == None

    def bad_handler():
        raise Exception("Bad Server Handler")
    server.on_bad_handler = bad_handler

    # receive_request will normally print traceback when an exception is caught.
    # This isn't necessary for the test
    with block_stderr():
        response = server.receive_request(jsonrpc_base.Request(
            'on_bad_handler', msg_id=1))
    assert response.error['code'] == -32000
    assert response.error['message'] == 'Server Error: Bad Server Handler'

    async def async_event_handler(*args, **kwargs):
        return args, kwargs
    server.on_async_server_event = async_event_handler

    response = server.receive_request(jsonrpc_base.Request(
        'on_async_server_event', msg_id=1))
    assert response.error['code'] == -32000
    assert response.error['message'] == ('Server Error: Async handlers are not '
        'supported in synchronous sever implementations')

async def test_async_receive_server_requests(server):
    def event_handler(*args, **kwargs):
        return args, kwargs
    server.on_server_event = event_handler
    server.namespace.on_server_event = event_handler

    response = await server.async_receive_request(jsonrpc_base.Request(
        'on_server_event', msg_id=1))
    args, kwargs = response.result
    assert len(args) == 0
    assert len(kwargs) == 0

    async def async_event_handler(*args, **kwargs):
        return args, kwargs
    server.on_async_server_event = async_event_handler

    response = await server.async_receive_request(jsonrpc_base.Request(
        'on_async_server_event', msg_id=1))
    args, kwargs = response.result
    assert len(args) == 0
    assert len(kwargs) == 0

    response = await server.async_receive_request(jsonrpc_base.Request(
        'missing_event', params={'foo': 'bar'}, msg_id=1))
    assert response.error['code'] == -32601
    assert response.error['message'] == 'Method not found'

    response = await server.async_receive_request(jsonrpc_base.Request(
        'on_server_event'))
    assert response == None

async def test_server_responses(server):
    def handler(message):
        handler.response = message
    server._handler = handler

    def subtract(foo, bar):
        return foo - bar
    server.subtract = subtract

    response = server.receive_request(jsonrpc_base.Request(
        'subtract', params={'foo': 5, 'bar': 3}, msg_id=1))
    server.send_message(response)
    assertSameJSON(
        '''{"jsonrpc": "2.0", "result": 2, "id": 1}''',
        handler.response
    )

    response = server.receive_request(jsonrpc_base.Request(
        'subtract', params=[11, 7], msg_id=1))
    server.send_message(response)
    assertSameJSON(
        '''{"jsonrpc": "2.0", "result": 4, "id": 1}''',
        handler.response
    )

    response = server.receive_request(jsonrpc_base.Request(
        'missing_method', msg_id=1))
    server.send_message(response)
    assertSameJSON(
        '''{"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found"}, "id": 1}''',
        handler.response
    )

    def bad_handler(self):
        raise MockTransportError("Transport Error")
    server._handler = bad_handler

    def good_method():
        return True
    server.good_method = good_method
    response = server.receive_request(jsonrpc_base.Request(
        'good_method', msg_id=1))
    with pytest.raises(TransportError, match="Error responding to server method 'good_method': Transport Error"):
        server.send_message(response)

    async def async_bad_method():
        raise ValueError("Mock server error")
    server.async_bad_method = async_bad_method
    response = await server.async_receive_request(jsonrpc_base.Request(
        'async_bad_method', msg_id=1))
    with pytest.raises(TransportError, match="Error responding to server method 'async_bad_method': Transport Error"):
        server.send_message(response)


def test_base_message(server):
    message = jsonrpc_base.Message()
    assert message.response_id == None

    with pytest.raises(NotImplementedError):
        message.serialize()

    with pytest.raises(NotImplementedError):
        message.parse_response(None)

    with pytest.raises(NotImplementedError):
        text = message.transport_error_text

    with pytest.raises(NotImplementedError):
        str(message)

def test_request(server):
    with pytest.raises(ProtocolError, match='Request from server does not contain method'):
        jsonrpc_base.Request.parse({})

    with pytest.raises(ProtocolError, match='Parameters must either be a positional list or named dict.'):
        jsonrpc_base.Request.parse({'method': 'test_method', 'params': 'string_params'})

    request = jsonrpc_base.Request('test_method', msg_id=1)
    assert request.response_id == 1

def test_jsonrpc_1_0_call(server):
    # JSON-RPC 1.0 spec needs "error" to be present (with `null` value) when no error occured
    def handler(message):
        assert message.params == [42, 23]
        return {
            "result": 19,
            "id": 1,
            "error": None,
        }

    server._handler = handler
    assert server.subtract(42, 23) == 19
