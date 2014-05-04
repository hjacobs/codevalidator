#!/usr/bin/env python
# -*- coding: utf-8 -*-

from distutils.core import setup

setup(
    name='codevalidator',
    version='0.8',
    description='Simple source code validator with file reformatting option (remove trailing WS, pretty print XML, ..)'
        ,
    long_description=open('README.md', 'r').read(),
    author='Henning Jacobs',
    author_email='henning@jacobs1.de',
    url='https://github.com/hjacobs/codevalidator',
    py_modules=['codevalidator'],
    packages=['pythontidy'],
)
