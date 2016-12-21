import unittest
import random
import json
import inspect
import os

import pep8

from jsonrpc_base import Server, ProtocolError, TransportError

try:
    # python 3.3
    from unittest.mock import Mock
except ImportError:
    from mock import Mock

class TestTransportError(ValueError):
    """Test exception representing a transport library error."""

class TestServer(Server):

    def __init__(self, url):
        self.url = url
        self.handler = None

    def send_request(self, method_name, is_notification, params):
        """Issue the request to the server and return the method result (if not a notification)"""
        try:
            response = json.loads(json.dumps(self.handler(
                json.loads(json.dumps(method_name)),
                is_notification,
                json.loads(json.dumps(params)))))
        except Exception as requests_exception:
            raise TransportError('Error calling method %r' % method_name, requests_exception)

        if not is_notification:
            return self.parse_result(response)

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
            super(TestServer, self.server).__init__(self.server.url)

        with self.assertRaises(NotImplementedError):
            super(TestServer, self.server).send_request('my_method', params=(), is_notification=False)

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
            self.server.serialize('my_method_name', params=None, is_notification=False)
        )
        # test keyword args
        self.assertSameJSON(
            '''{"params": {"foo": "bar"}, "jsonrpc": "2.0", "method": "my_method_name", "id": 1}''',
            self.server.serialize('my_method_name', params={'foo': 'bar'}, is_notification=False)
        )
        # test positional args
        self.assertSameJSON(
            '''{"params": ["foo", "bar"], "jsonrpc": "2.0", "method": "my_method_name", "id": 1}''',
            self.server.serialize('my_method_name', params=('foo', 'bar'), is_notification=False)
        )
        # test notification
        self.assertSameJSON(
            '''{"params": ["foo", "bar"], "jsonrpc": "2.0", "method": "my_method_name"}''',
            self.server.serialize('my_method_name', params=('foo', 'bar'), is_notification=True)
        )

    def test_parse_result(self):
        with self.assertRaisesRegex(ProtocolError, 'Response is not a dictionary'):
            self.server.parse_result([])
        with self.assertRaisesRegex(ProtocolError, 'Response without a result field'):
            self.server.parse_result({})
        with self.assertRaises(ProtocolError) as protoerror:
            body = {"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found"}, "id": "1"}
            self.server.parse_result(body)
        self.assertEqual(protoerror.exception.args[0], -32601)
        self.assertEqual(protoerror.exception.args[1], 'Method not found')

    def test_send_request(self):
        # catch non-json responses
        with self.assertRaises(TransportError) as transport_error:
            def handler(method_name, is_notification, params):
                raise TestTransportError("Transport Error")

            self.server.handler = handler
            self.server.send_request('my_method', is_notification=False, params=None)

        self.assertEqual(transport_error.exception.args[0], "Error calling method 'my_method'")
        self.assertIsInstance(transport_error.exception.args[1], TestTransportError)

        # a notification
        def handler(method_name, is_notification, params):
            return 'we dont care about this'
        self.server.handler = handler
        self.server.send_request('my_notification', is_notification=True, params=None)

    def test_exception_passthrough(self):
        with self.assertRaises(TransportError) as transport_error:
            def handler(method_name, is_notification, params):
                raise TestTransportError("Transport Error")
            self.server.handler = handler
            self.server.foo()
        self.assertEqual(transport_error.exception.args[0], "Error calling method 'foo'")
        self.assertIsInstance(transport_error.exception.args[1], TestTransportError)

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
        def handler(method_name, is_notification, params):
            return {
                "jsonrpc": "2.0",
                "result": True if params[0] == method_name else False,
                "id": 1,
            }
        self.server.handler = handler

        self.assertEqual(self.server.nest.testmethod("nest.testmethod"), True)
        self.assertEqual(self.server.nest.testmethod.some.other.method("nest.testmethod.some.other.method"), True)

    def test_calls(self):
        # rpc call with positional parameters:
        def handler1(method_name, is_notification, params):
            self.assertEqual(params, [42, 23])
            return {
                "jsonrpc": "2.0",
                "result": 19,
                "id": 1,
            }

        self.server.handler = handler1
        self.assertEqual(self.server.subtract(42, 23), 19)

        # rpc call with named parameters
        def handler2(method_name, is_notification, params):
            self.assertEqual(params, {'y': 23, 'x': 42})
            return {
                "jsonrpc": "2.0",
                "result": 19,
                "id": 1,
            }

        self.server.handler = handler2
        self.assertEqual(self.server.subtract(x=42, y=23), 19)

        # rpc call with a mapping type
        def handler3(method_name, is_notification, params):
            self.assertEqual(params, {'foo': 'bar'})
            return {
                "jsonrpc": "2.0",
                "result": None,
                "id": 1,
            }

        self.server.handler = handler3
        self.server.foobar({'foo': 'bar'})

    def test_notification(self):
        # Verify that we ignore the server response
        def handler(method_name, is_notification, params):
            return {
                "jsonrpc": "2.0",
                "result": 19,
                "id": 3,
            }
        self.server.handler = handler
        self.assertIsNone(self.server.subtract(42, 23, _notification=True))


if __name__ == '__main__':
    unittest.main()
