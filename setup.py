import os
import re
from os.path import abspath, dirname, join
from shutil import rmtree

from robot.libdoc import libdoc
from setuptools import setup, find_packages

from RemoteMonitorLibrary import __author__, __author_email__, __url__, __package_name__
from RemoteMonitorLibrary.utils.string_utils import to_title

current_dir = dirname(abspath(__file__))


def read_file(file_name):
    """Read the given file.
    :param file_name: Name of the file to be read
    :return:      Output of the given file
    """
    with open(os.path.join(os.path.dirname(__file__), file_name)) as sr:
        return sr.read()


with open(join(current_dir, "RemoteMonitorLibrary", "version.py"), encoding="utf-8") as f:
    VERSION = re.search(r"""VERSION = ('|")(.*)('|")""", f.read()).group(2)

print(f"Version: {VERSION}")
update_set = dict(VERSION=VERSION,
                  package_name=__package_name__,
                  package_title=to_title(__package_name__))

long_description = ''
with open(join(current_dir, "readme_template.md"), "r", encoding="utf-8") as reader:
    with open(join(current_dir, "README.md"), "w+", encoding='utf-8') as writer:
        lines = reader.read()
        for k, v in update_set.items():
            lines = lines.replace(f"<{k}>", v)

        long_description += f"{lines}\n"
        writer.write(lines)
        print(lines)

py_file = os.path.join(current_dir, __package_name__, 'library', f'{__package_name__}.py')
html_file = os.path.join(current_dir, __package_name__, 'library', f'{__package_name__}.html')

libdoc(py_file, html_file, __package_name__, VERSION)

rmtree('dist', True)

setup(
    name='robotframework-remote-monitor-library',
    version=VERSION,
    packages=find_packages(exclude=['venv']),
    package_data={'': ['*.html', 'RemoteMonitorLibrary/library/*.html']},
    url=__url__,
    license='MIT',
    author=__author__,
    author_email=__author_email__,
    description='RobotFramework extended keyword library; Allow background system monitoring; aTop, Time, SSHLibrary',
    long_description=long_description,
    long_description_content_type='text/markdown',
    install_requires=read_file('requirements.txt'),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Framework :: Robot Framework",
        "Framework :: Robot Framework :: Library",
        "Operating System :: OS Independent",
        "Development Status :: 3 - Alpha"
    ]
)
