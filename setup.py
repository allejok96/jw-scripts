#!/usr/bin/env python3

from setuptools import setup

setup(
    name='jw-scripts',
    version='1.0',
    description='Download media from jw.org',
    url='https://github.com/allejok96/jw-scripts',
    license='GPL',
    packages=['jwlib'],
    install_requires=['urllib3'],
    scripts=['jwb-index', 'jwb-stream', 'jwb-offline', 'jwb-offline-import']
)
