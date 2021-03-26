from setuptools import setup

setup(
    name='jw-scripts',
    version='1.0',
    description='Download media from jw.org',
    url='https://github.com/allejok96/jw-scripts',
    license='GPL',
    packages=['jwlib'],
    install_requires=['urllib3'],
    #scripts=['jwb-index', 'jwb-offline']
    entry_points={'console_scripts': [
        'jwb-index=jwlib.main:main',
        'jwb-offline=jwlib.player:main'
    ]}
)
