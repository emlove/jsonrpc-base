from __future__ import print_function

try:
    from setuptools import setup
except ImportError:
    import sys
    print("Please install the `setuptools` package in order to install this library", file=sys.stderr)
    raise

setup(
    name='jsonrpc-base',
    version='2.1.1',
    author='Emily Love Mills',
    author_email='emily@emlove.me',
    packages=('jsonrpc_base',),
    license='BSD',
    keywords='json-rpc base',
    url='http://github.com/emlove/jsonrpc-base',
    description='''A JSON-RPC client library base interface''',
    long_description=open('README.rst').read(),
    install_requires=[],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
    ],

)
