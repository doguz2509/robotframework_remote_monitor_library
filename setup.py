from setuptools import setup, find_packages

from SystemTraceLibrary import __author__, __author_email__, __version__, __url__

setup(
    name='robotframework-system-trace-library',
    version=__version__,
    packages=find_packages(exclude=['venv']),
    url=__url__,
    license='MIT',
    author=__author__,
    author_email=__author_email__,
    description='RobotFramework extended keyword library; Allow background system tracing; aTop+',
    long_description=open(r'./README.md', encoding='utf-8').read(),
    long_description_content_type='text/markdown',
    install_requires=[
        'robotframework~=3.2.2',
        'robotframework-sshlibrary',
        'matplotlib~=3.4.0',
        'pandas',
    ],
    classifiers=[
         "Programming Language :: Python :: 3",
         "Framework :: Robot Framework",
         "Framework :: Robot Framework :: Library",
         "Operating System :: OS Independent",
         "Development Status :: 3 - Alpha"
    ]
)
