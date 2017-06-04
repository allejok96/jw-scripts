from setuptools import setup

setup(
    name='jw-scripts',
    version='1.0a1',
    description='Download media from jw.org',
    url='https://github.com/allejok96/jw-scripts',
    license='GPL',
    packages=['jwlib'],
    install_requires=['urllib3'],
    scripts=['jwb-index', 'jwb-stream', 'nwt-index']
)
