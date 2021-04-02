from setuptools import setup

setup(
    name='jw-scripts',
    version='1.10',
    description='Download media from jw.org',
    url='https://github.com/allejok96/jw-scripts',
    license='GPL',
    packages=['jwlib'],
    entry_points={'console_scripts': [
        'jwb-index=jwlib.main:main',
        'jwb-offline=jwlib.player:main'
    ]}
)
