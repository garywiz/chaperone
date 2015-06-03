import os
import sys
import subprocess
from setuptools import setup, find_packages

ourdir = os.path.dirname(__file__)

def read(fname):
    return open(os.path.join(ourdir, fname)).read()

def get_version():
    return subprocess.check_output([sys.executable, os.path.join("chaperone/cproc/version.py")]).decode().strip()

setup(
    name = "chaperone",
    version = get_version(),
    description = 'Simple system init daemon for Docker-like environments',
    long_description = read('README'),
    packages = find_packages(),
    #test_suite = "pyt_tests.tests.test_all",
    entry_points={
        'console_scripts': [
            'chaperone = chaperone.exec.chaperone:main_entry',
            'telchap = chaperone.exec.telchap:main_entry',
        ],
    },
    license = "BSD 3",
    author = "Gary Wisniewski",
    author_email = "garyw@blueseastech.com",
    url = "http://github.com/garywiz/chaperone",
    keywords = "docker init systemd syslog",

    install_requires = ['docopt>=0.6.2', 'setproctitle>=1.1.8', 'PyYAML>=3.1.1',
                        'voluptuous>=0.8.7'],

    classifiers = [
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Natural Language :: English",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Topic :: System :: Logging",
        "Topic :: System :: Boot :: Init",
        ]
    )
