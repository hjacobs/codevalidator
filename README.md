codevalidator
=============

Simple source code validator with file reformatting option (remove trailing WS, pretty print XML, ..).

For Python code formatting it can either use [autopep8][autopep8] or the builtin copy of PythonTidy.

Requirements
------------

* Python 2.7+
* [lxml][lxml] (for XML formatting)
* [pep8][pep8] (for Python checking)
* [autopep8][autopep8] (for Python formatting)
* [pyflakes][pyflakes] (for static Python code checking)
* [Jalopy][Jalopy] (for Java code formatting)
* coffeelint (for CoffeeScript validation)
* PHP_CodeSniffer (for PHP style checking)
* Puppet (for Puppet manifest validation)
* sqlparse
* jshint (for JavaScript checking)

On Ubuntu you can install most packages easily:

    sudo apt-get install python-lxml pep8 pyflakes nodejs npm
    sudo npm install -g jshint

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

Using the filter mode to "fix" stdin and write to stdout:

    echo 'print 1' | ./codevalidator.py --fix --filter foobar.py && echo success

If you are annoyed by the .XX.pre-cvfix backup files you can disable them either on the command line (`--no-backup`) or in the config file.

Known Issues
------------

* PythonTidy cannot parse [dict comprehensions][dict comprehensions]. As a workaround you can use list comprehensions and wrap it with `dict`.

[lxml]:                 http://lxml.de/
[pep8]:                 https://pypi.python.org/pypi/pep8
[autopep8]:             https://pypi.python.org/pypi/autopep8
[pyflakes]:             https://pypi.python.org/pypi/pyflakes
[Jalopy]:               http://www.triemax.com/products/jalopy/
[dict comprehensions]:  http://www.python.org/dev/peps/pep-0274/
