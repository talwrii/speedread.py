import os
from setuptools import setup

# Utility function to read the README file.
# Used for the long_description.  It's nice, because now 1) we have a top level
# README file and 2) it's easier to type in the README file than to put a raw
# string in below ...
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name = "speedread.py",
    version = "0.1",
    author = "Tal Wrii",
    author_email = "talwrii@gmail.com",
    description = "Linux spritz-like reader for the command line",
    install_requires=['blessings', 'readchar'],
    license = "BSD",
    keywords = "reading",
    packages=['speedread'],
    long_description=read('README.md'),
    entry_points={
        'console_scripts': [
            'pyspeedread = speedread.main:main',
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Topic :: Utilities",
        "License :: OSI Approved :: BSD License",
    ],
)
