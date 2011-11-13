codevalidator
=============

Simple source code validator with file reformatting option (remove trailing WS, pretty print XML, ..)

Requirements
------------

* python 2.7+
* lxml

Getting Started
---------------

Validating test files with builtin default configuration:

    ./codevalidator.py test/*

Fixing test files (removing trailing whitespace, XML format):

	./codevalidator.py -f test/*

Using custom configuration file:

    ./configuration.py -c test/config.json test/*

