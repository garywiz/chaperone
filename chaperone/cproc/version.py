# This file is designed to be used as a package module, but also as a main program runnable
# by P2 or P3 which will print the version.  Used in setup.py

VERSION = (0,1,4)
DISPLAY_VERSION = ".".join([str(v) for v in VERSION])

if __name__ == '__main__':
    print(DISPLAY_VERSION)
