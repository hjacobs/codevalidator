#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup

with open('README.rst') as readme:
    setup(
        name='codevalidator',
        version='0.8.2',
        description='Simple source code validator with file reformatting option (remove trailing WS, pretty print XML, ..)'
            ,
        long_description=readme.read(),
        author='Henning Jacobs',
        author_email='henning@jacobs1.de',
        url='https://github.com/hjacobs/codevalidator',
        py_modules=['codevalidator'],
        packages=['pythontidy'],
        entry_points={'console_scripts': ['codevalidator = codevalidator:main']},
        extras_require={'YAML': ['PyYAML'], 'XML': ['lxml'], 'Python': ['pep8', 'autopep8', 'pyflakes']},
        keywords='formatter, beautify, indentation',
        classifiers=[
            'Development Status :: 3 - Alpha',
            'Environment :: Console',
            'Intended Audience :: Developers',
            'Topic :: Software Development :: Pre-processors',
            'Topic :: Text Processing :: Markup :: XML',
            'Programming Language :: Python :: 2.7',
        ],
    )

