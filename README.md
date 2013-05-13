codevalidator
=============

Simple source code validator with file reformatting option (remove trailing WS, pretty print XML, ..)

Requirements
------------

* python 2.7+
* lxml
* pep8
* autopep8

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

