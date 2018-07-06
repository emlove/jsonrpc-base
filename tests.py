import contextlib
import inspect
import json
import os
import random
import sys
import unittest

import pep8

import jsonrpc_base
from jsonrpc_base import Server, ProtocolError, TransportError

try:
    # python 3.3
    from unittest.mock import Mock
except ImportError:
    from mock import Mock

class DummyFile(object):
    def write(self, x): pass

@contextlib.contextmanager
def block_stderr():
    real_stderr = sys.stderr
    sys.stderr = DummyFile()
    yield
    sys.stderr = real_stderr

class TestTransportError(ValueError):
    """Test exception representing a transport library error."""

class TestServer(Server):

    def __init__(self, url):
        super(TestServer, self).__init__()
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

class TestCase(unittest.TestCase):
    def assertSameJSON(self, json1, json2):
        """Tells whether two json strings, once decoded, are the same dictionary"""
        return self.assertDictEqual(json.loads(json1), json.loads(json2))

    def assertRaisesRegex(self, *args, **kwargs):
        if hasattr(super(TestCase, self), 'assertRaisesRegex'):
            # python 3.3
            return super(TestCase, self).assertRaisesRegex(*args, **kwargs)
        else:
            # python 2.7
            return self.assertRaisesRegexp(*args, **kwargs)


class TestJSONRPCClient(TestCase):

    def setUp(self):
        random.randint = Mock(return_value=1)
        self.server = TestServer('http://mock/xmlrpc')

    def test_super_not_implemented(self):
        """Test the base class NotImplementedException."""
        with self.assertRaises(NotImplementedError):
            super(TestServer, self.server).send_message(jsonrpc_base.Request('my_method'))

    def test_pep8_conformance(self):
        """Test that we conform to PEP8."""

        source_files = []
        project_dir = os.path.dirname(os.path.abspath(__file__))
        package_dir = os.path.join(project_dir, 'jsonrpc_base')
        for root, directories, filenames in os.walk(package_dir):
            source_files.extend([os.path.join(root, f) for f in filenames if f.endswith('.py')])

        pep8style = pep8.StyleGuide(quiet=False, max_line_length=120)
        result = pep8style.check_files(source_files)
        self.assertEqual(result.total_errors, 0, "Found code style errors (and warnings).")

    def test_dumps(self):
        # test no args
        self.assertSameJSON(
            '''{"jsonrpc": "2.0", "method": "my_method_name", "id": 1}''',
            jsonrpc_base.Request('my_method_name', params=None, msg_id=1).serialize()
        )
        # test keyword args
        self.assertSameJSON(
            '''{"params": {"foo": "bar"}, "jsonrpc": "2.0", "method": "my_method_name", "id": 1}''',
            jsonrpc_base.Request('my_method_name', params={'foo': 'bar'}, msg_id=1).serialize()
        )
        # test positional args
        self.assertSameJSON(
            '''{"params": ["foo", "bar"], "jsonrpc": "2.0", "method": "my_method_name", "id": 1}''',
            jsonrpc_base.Request('my_method_name', params=('foo', 'bar'), msg_id=1).serialize()
        )
        # test notification
        self.assertSameJSON(
            '''{"params": ["foo", "bar"], "jsonrpc": "2.0", "method": "my_method_name"}''',
            jsonrpc_base.Request('my_method_name', params=('foo', 'bar'), msg_id=None).serialize()
        )

    def test_parse_result(self):
        request = jsonrpc_base.Request('my_message', msg_id=1)
        with self.assertRaisesRegex(ProtocolError, 'Response is not a dictionary'):
            request.parse_response([])
        with self.assertRaisesRegex(ProtocolError, 'Response without a result field'):
            request.parse_response({})
        with self.assertRaises(ProtocolError) as protoerror:
            body = {"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found"}, "id": "1"}
            request.parse_response(body)
        self.assertEqual(protoerror.exception.args[0], -32601)
        self.assertEqual(protoerror.exception.args[1], 'Method not found')

    def test_send_message(self):
        # catch non-json responses
        with self.assertRaises(TransportError) as transport_error:
            def handler(message):
                raise TestTransportError("Transport Error")

            self.server._handler = handler
            self.server.send_message(jsonrpc_base.Request('my_method', msg_id=1))

        self.assertEqual(transport_error.exception.args[0], "Error calling method 'my_method': Transport Error")
        self.assertIsInstance(transport_error.exception.args[1], TestTransportError)

        # a notification
        def handler(message):
            return 'we dont care about this'
        self.server._handler = handler
        self.server.send_message(jsonrpc_base.Request('my_notification', msg_id=None))

    def test_exception_passthrough(self):
        with self.assertRaises(TransportError) as transport_error:
            def handler(message):
                raise TestTransportError("Transport Error")
            self.server._handler = handler
            self.server.foo()
        self.assertEqual(transport_error.exception.args[0], "Error calling method 'foo': Transport Error")
        self.assertIsInstance(transport_error.exception.args[1], TestTransportError)

    def test_transport_error_constructor(self):
        with self.assertRaisesRegex(TransportError, 'Test Message'):
            raise TransportError('Test Message')

    def test_forbid_private_methods(self):
        """Test that we can't call private class methods (those starting with '_')"""
        with self.assertRaises(AttributeError):
            self.server._foo()

        # nested private method call
        with self.assertRaises(AttributeError):
            self.server.foo.bar._baz()

    def test_method_call(self):
        """mixing *args and **kwargs is forbidden by the spec"""
        with self.assertRaisesRegex(ProtocolError, 'JSON-RPC spec forbids mixing arguments and keyword arguments'):
            self.server.testmethod(1, 2, a=1, b=2)

    def test_method_nesting(self):
        """Test that we correctly nest namespaces"""
        def handler(message):
            return {
                "jsonrpc": "2.0",
                "result": True if message.params[0] == message.method else False,
                "id": 1,
            }
        self.server._handler = handler

        self.assertEqual(self.server.nest.testmethod("nest.testmethod"), True)
        self.assertEqual(self.server.nest.testmethod.some.other.method("nest.testmethod.some.other.method"), True)

    def test_calls(self):
        # rpc call with positional parameters:
        def handler1(message):
            self.assertEqual(message.params, [42, 23])
            return {
                "jsonrpc": "2.0",
                "result": 19,
                "id": 1,
            }

        self.server._handler = handler1
        self.assertEqual(self.server.subtract(42, 23), 19)

        # rpc call with named parameters
        def handler2(message):
            self.assertEqual(message.params, {'y': 23, 'x': 42})
            return {
                "jsonrpc": "2.0",
                "result": 19,
                "id": 1,
            }

        self.server._handler = handler2
        self.assertEqual(self.server.subtract(x=42, y=23), 19)

        # rpc call with a mapping type
        def handler3(message):
            self.assertEqual(message.params, {'foo': 'bar'})
            return {
                "jsonrpc": "2.0",
                "result": None,
                "id": 1,
            }

        self.server._handler = handler3
        self.server.foobar({'foo': 'bar'})

    def test_notification(self):
        # Verify that we ignore the server response
        def handler(message):
            return {
                "jsonrpc": "2.0",
                "result": 19,
                "id": 3,
            }
        self.server._handler = handler
        self.assertIsNone(self.server.subtract(42, 23, _notification=True))

    def test_receive_server_requests(self):
        def event_handler(*args, **kwargs):
            return args, kwargs
        self.server.on_server_event = event_handler
        self.server.namespace.on_server_event = event_handler

        response = self.server.receive_request(jsonrpc_base.Request(
            'on_server_event', msg_id=1))
        args, kwargs = response.result
        self.assertEqual(len(args), 0)
        self.assertEqual(len(kwargs), 0)

        response = self.server.receive_request(jsonrpc_base.Request(
            'namespace.on_server_event', msg_id=1))
        args, kwargs = response.result
        self.assertEqual(len(args), 0)
        self.assertEqual(len(kwargs), 0)

        response = self.server.receive_request(jsonrpc_base.Request(
            'on_server_event', params=['foo', 'bar'], msg_id=1))
        args, kwargs = response.result
        self.assertEqual(args, ('foo', 'bar'))
        self.assertEqual(len(kwargs), 0)

        response = self.server.receive_request(jsonrpc_base.Request(
            'on_server_event', params={'foo': 'bar'}, msg_id=1))
        args, kwargs = response.result
        self.assertEqual(len(args), 0)
        self.assertEqual(kwargs, {'foo': 'bar'})

        with self.assertRaises(ProtocolError):
            response = self.server.receive_request(jsonrpc_base.Request(
                'on_server_event', params="string_params", msg_id=1))

        response = self.server.receive_request(jsonrpc_base.Request(
            'missing_event', params={'foo': 'bar'}, msg_id=1))
        self.assertEqual(response.error['code'], -32601)
        self.assertEqual(response.error['message'], 'Method not found')

        response = self.server.receive_request(jsonrpc_base.Request(
            'on_server_event'))
        self.assertEqual(response, None)

        def bad_handler():
            raise Exception("Bad Server Handler")
        self.server.on_bad_handler = bad_handler

        # receive_request will normally print traceback when an exception is caught.
        # This isn't necessary for the test
        with block_stderr():
            response = self.server.receive_request(jsonrpc_base.Request(
                'on_bad_handler', msg_id=1))
        self.assertEqual(response.error['code'], -32000)
        self.assertEqual(response.error['message'], 'Server Error: Bad Server Handler')

    def test_receive_server_requests_with_id_zero(self):
        def event_handler(*args, **kwargs):
            return args, kwargs
        self.server.on_server_event = event_handler
        self.server.namespace.on_server_event = event_handler

        response = self.server.receive_request(jsonrpc_base.Request(
            'on_server_event', msg_id=0))
        args, kwargs = response.result
        self.assertEqual(len(args), 0)
        self.assertEqual(len(kwargs), 0)

        response = self.server.receive_request(jsonrpc_base.Request(
            'namespace.on_server_event', msg_id=0))
        args, kwargs = response.result
        self.assertEqual(len(args), 0)
        self.assertEqual(len(kwargs), 0)

        response = self.server.receive_request(jsonrpc_base.Request(
            'on_server_event', params=['foo', 'bar'], msg_id=0))
        args, kwargs = response.result
        self.assertEqual(args, ('foo', 'bar'))
        self.assertEqual(len(kwargs), 0)

        response = self.server.receive_request(jsonrpc_base.Request(
            'on_server_event', params={'foo': 'bar'}, msg_id=0))
        args, kwargs = response.result
        self.assertEqual(len(args), 0)
        self.assertEqual(kwargs, {'foo': 'bar'})

        with self.assertRaises(ProtocolError):
            response = self.server.receive_request(jsonrpc_base.Request(
                'on_server_event', params="string_params", msg_id=0))

        response = self.server.receive_request(jsonrpc_base.Request(
            'missing_event', params={'foo': 'bar'}, msg_id=0))
        self.assertEqual(response.error['code'], -32601)
        self.assertEqual(response.error['message'], 'Method not found')

        response = self.server.receive_request(jsonrpc_base.Request(
            'on_server_event'))
        self.assertEqual(response, None)

        def bad_handler():
            raise Exception("Bad Server Handler")
        self.server.on_bad_handler = bad_handler

        # receive_request will normally print traceback when an exception is caught.
        # This isn't necessary for the test
        with block_stderr():
            response = self.server.receive_request(jsonrpc_base.Request(
                'on_bad_handler', msg_id=0))
        self.assertEqual(response.error['code'], -32000)
        self.assertEqual(response.error['message'], 'Server Error: Bad Server Handler')

    def test_server_responses(self):
        def handler(message):
            handler.response = message
        self.server._handler = handler

        def subtract(foo, bar):
            return foo - bar
        self.server.subtract = subtract

        response = self.server.receive_request(jsonrpc_base.Request(
            'subtract', params={'foo': 5, 'bar': 3}, msg_id=1))
        self.server.send_message(response)
        self.assertSameJSON(
            '''{"jsonrpc": "2.0", "result": 2, "id": 1}''',
            handler.response
        )

        response = self.server.receive_request(jsonrpc_base.Request(
            'subtract', params=[11, 7], msg_id=1))
        self.server.send_message(response)
        self.assertSameJSON(
            '''{"jsonrpc": "2.0", "result": 4, "id": 1}''',
            handler.response
        )

        response = self.server.receive_request(jsonrpc_base.Request(
            'missing_method', msg_id=1))
        self.server.send_message(response)
        self.assertSameJSON(
            '''{"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found"}, "id": 1}''',
            handler.response
        )

        def bad_handler():
            raise TestTransportError("Transport Error")
        self.server._handler = bad_handler

        def good_method():
            return True
        self.server.good_method = good_method
        response = self.server.receive_request(jsonrpc_base.Request(
            'good_method', msg_id=1))
        with self.assertRaisesRegex(TransportError, "Error responding to server method 'good_method': Transport Error"):
            self.server.send_message(response)


    def test_base_message(self):
        message = jsonrpc_base.Message()
        self.assertEqual(message.response_id, None)

        with self.assertRaises(NotImplementedError):
            message.serialize()

        with self.assertRaises(NotImplementedError):
            message.parse_response(None)

        with self.assertRaises(NotImplementedError):
            text = message.transport_error_text

        with self.assertRaises(NotImplementedError):
            str(message)

    def test_request(self):
        with self.assertRaisesRegex(ProtocolError, 'Request from server does not contain method'):
            jsonrpc_base.Request.parse({})

        with self.assertRaisesRegex(ProtocolError, 'Parameters must either be a positional list or named dict.'):
            jsonrpc_base.Request.parse({'method': 'test_method', 'params': 'string_params'})

        request = jsonrpc_base.Request('test_method', msg_id=1)
        self.assertEqual(request.response_id, 1)


if __name__ == '__main__':
    unittest.main()
