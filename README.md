codevalidator
=============

Simple source code validator with file reformatting option (remove trailing WS, pretty print XML, ..)

Requirements
------------

* python 2.7+
* lxml (for XML formatting)
* pep8 (for Python checking)
* autopep8 (for Python formatting)
* pyflakes (for static Python code checking)
* Jalopy (for Java code formatting)
* coffeelint (for CoffeeScript validation)
* PHP_CodeSniffer (for PHP style checking)
* Puppet (for Puppet manifest validation)
* sqlparse

Getting Started
---------------

Validating test files with builtin default configuration:

    ./codevalidator.py test/*

Fixing test files (removing trailing whitespace, XML format):

    ./codevalidator.py -f test/*

Using custom configuration file:

    ./codevalidator.py -c test/config.json test/*

Validate and fix a whole directory tree:

    ./codevalidator.py -c myconfig.json -rf /path/to/mydirectory

Validate a single PHP file and print detailed error messages (needs PHP_CodeSniffer with PSR standards installed!):

    ./codevalidator.py -v test/test.php

Running in very verbose (debug) mode to see what is validated:

    ./codevalidator.py -vvrc test/config.json test


If you are annoyed by the .XX.pre-cvfix backup files you can disable them either on the command line (--no-backup) or in the config file.
