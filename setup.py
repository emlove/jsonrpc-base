from __future__ import print_function

try:
    from setuptools import setup
except ImportError:
    import sys
    print("Please install the `setuptools` package in order to install this library", file=sys.stderr)
    raise

setup(
    name='jsonrpc-base',
    version='0.1',
    author='Adam Mills',
    author_email='adam@armills.info',
    packages=('jsonrpc_base',),
    license='BSD',
    keywords='json-rpc base',
    url='http://github.com/armills/jsonrpc-base',
    description='''A JSON-RPC client library base interface''',
    long_description=open('README.rst').read(),
    install_requires=[],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],

)
