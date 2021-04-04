from setuptools import setup, find_packages

from system_trace import __author__, __author_email__, __version__, __url__

setup(
    name='SystemTraceLibrary',
    version=__version__,
    packages=find_packages(exclude=['venv']),
    url=__url__,
    license='MIT',
    author=__author__,
    author_email=__author_email__,
    description='RobotFramework extended keyword library; Allow background system tracing; aTop+',
    long_description=open('README.rst').read(),
    install_requires=[
        'robotframework~=3.2.2',
        'robotframework-sshlibrary',
        'matplotlib',
        'pandas',
    ],
    classifiers=[
         "Programming Language :: Python :: 3",
         "Operating System :: FILES Independent",
         "Development Status :: 3 - Alpha"
    ]
)
