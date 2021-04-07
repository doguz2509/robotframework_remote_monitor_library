import os
import re
from os.path import abspath, dirname, join
from shutil import rmtree

from robot.libdoc import libdoc
from setuptools import setup, find_packages

from SystemTraceLibrary import __author__, __author_email__, __url__

current_dir = dirname(abspath(__file__))

with open(join(current_dir, "SystemTraceLibrary", "version.py"), encoding="utf-8") as f:
    VERSION = re.search(r"""VERSION = ('|")(.*)('|")""", f.read()).group(2)

update_set = dict(VERSION=VERSION)

long_description = ''
with open("readme_template.md", "r", encoding="utf-8") as reader:
    with open("README.md", "w+", encoding='utf-8') as writer:
        lines = reader.read()
        for k, v in update_set.items():
            lines = lines.replace(f"<{k}>", v)

        long_description += f"{lines}\n"
        writer.write(lines)
        print(lines)

libdoc(os.path.join(current_dir, 'SystemTraceLibrary', 'library', 'SystemTraceLibrary.py'),
       os.path.join(current_dir, 'SystemTraceLibrary', 'library', 'SystemTraceLibrary.html'),
       'SystemStraceLibrary', VERSION)

rmtree('dist', True)

setup(
    name='robotframework-system-trace-library',
    version=VERSION,
    packages=find_packages(exclude=['venv']),
    package_data={'': ['*.html', 'SystemTraceLibrary/library/*.html']},
    url=__url__,
    license='MIT',
    author=__author__,
    author_email=__author_email__,
    description='RobotFramework extended keyword library; Allow background system tracing; aTop+',
    long_description=long_description,
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
