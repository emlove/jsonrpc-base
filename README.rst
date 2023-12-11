jsonrpc-base: a compact JSON-RPC client library interface supporting multiple backends
=======================================================================================================

.. image:: https://github.com/emlove/jsonrpc-base/actions/workflows/main.yml/badge.svg
    :target: https://github.com/emlove/jsonrpc-base/actions/workflows/main.yml
.. image:: https://coveralls.io/repos/emlove/jsonrpc-base/badge.svg
    :target: https://coveralls.io/r/emlove/jsonrpc-base

This is a compact and simple JSON-RPC client implementation interface python code. This code is forked from https://github.com/gciotta/jsonrpc-requests

Main Features
-------------

* Python 3.6, 3.7, 3.8 & 3.9 compatible
* Supports nested namespaces (eg. `app.users.getUsers()`)
* 100% test coverage

Usage
-----

See `jsonrpc-async <https://github.com/emlove/jsonrpc-async>`_ and `jsonrpc-websocket <https://github.com/emlove/jsonrpc-websocket>`_ for example implementations.

Tests
-----
Install the Python tox package and run ``tox``, it'll test this package with various versions of Python.

Changelog
---------
2.2.0 (2023-12-11)
~~~~~~~~~~~~~~~~~~
- Omit params attribute when empty `(#9) <https://github.com/emlove/jsonrpc-base/pull/9>`_ `@Makman2 <https://github.com/Makman2>`_

2.1.1 (2022-05-03)
~~~~~~~~~~~~~~~~~~
- Unpin test dependencies

2.1.0 (2021-05-03)
~~~~~~~~~~~~~~~~~~
- Use uuid4 for request IDs

2.0.0 (2021-03-16)
~~~~~~~~~~~~~~~~~~
- BREAKING CHANGE: `Allow single mapping as a positional parameter. <https://github.com/emlove/jsonrpc-base/pull/6>`_
  Previously, when calling with a single dict as a parameter (example: ``server.foo({'bar': 0})``), the mapping was used as the JSON-RPC keyword parameters. This made it impossible to send a mapping as the first and only positional parameter. If you depended on the old behavior, you can recreate it by spreading the mapping as your method's kwargs. (example: ``server.foo(**{'bar': 0})``)

1.1.0 (2020-08-24)
~~~~~~~~~~~~~~~~~~
- Support for async server request handlers

1.0.3 (2019-11-12)
~~~~~~~~~~~~~~~~~~
- Forwards compatibility for Python 3.9. `(#4) <https://github.com/emlove/jsonrpc-base/pull/4>`_ `@a1fred <https://github.com/a1fred>`_

1.0.2 (2018-08-23)
~~~~~~~~~~~~~~~~~~
- Improved support for JSON-RPC v1 servers. `(#2) <https://github.com/emlove/jsonrpc-base/pull/2>`_ `@tdivis <https://github.com/tdivis>`_

1.0.1 (2018-07-06)
~~~~~~~~~~~~~~~~~~
- Falsey values are no longer treated as None for message IDs, or request parameters.

Credits
-------
`@gciotta <https://github.com/gciotta>`_ for creating the base project `jsonrpc-requests <https://github.com/gciotta/jsonrpc-requests>`_.

`@mbroadst <https://github.com/mbroadst>`_ for providing full support for nested method calls, JSON-RPC RFC
compliance and other improvements.

`@vaab <https://github.com/vaab>`_ for providing api and tests improvements, better RFC compliance.
