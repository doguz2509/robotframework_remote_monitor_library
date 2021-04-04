from setuptools import setup, find_packages

from SystemTraceLibrary import __author__, __author_email__, __version__, __url__

setup(
    name='robotframework-systemtracelibrary',
    version=__version__,
    packages=find_packages(exclude=['venv']),
    # package_dir={'': 'SystemTraceLibrary'},
    url=__url__,
    license='MIT',
    author=__author__,
    author_email=__author_email__,
    description='RobotFramework extended keyword library; Allow background system tracing; aTop+',
    long_description=open(r'./README.md').read(),
    install_requires=[
        'robotframework~=3.2.2',
        'robotframework-sshlibrary',
        'matplotlib',
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
