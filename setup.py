import os
import sys
import subprocess
from setuptools import setup, find_packages

if sys.version_info < (3,):
    print("You must run setup.py with Python 3 only.  Python 2 distributions are not supported.")
    exit(1)

ourdir = os.path.dirname(__file__)

def read(fname):
    return open(os.path.join(ourdir, fname)).read()

def get_version():
    return subprocess.check_output([sys.executable, os.path.join("chaperone/cproc/version.py")]).decode().strip()

def which(program):
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file
    return None

requires_list = ['docopt>=0.6.2', 'PyYAML>=3.1.1', 'voluptuous>=0.8.7', 'aiocron>=0.3']

if which('gcc'):
    requires_list += ["setproctitle>=1.1.8"]

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
            'envcp = chaperone.exec.envcp:main_entry',
            'sdnotify = chaperone.exec.sdnotify:main_entry',
        ],
    },
    license = "BSD 3",
    author = "Gary Wisniewski",
    author_email = "garyw@blueseastech.com",
    url = "http://github.com/garywiz/chaperone",
    keywords = "docker init systemd syslog",

    install_requires = requires_list,

    classifiers = [
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Natural Language :: English",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Topic :: System :: Logging",
        "Topic :: System :: Boot :: Init",
        ]
    )
