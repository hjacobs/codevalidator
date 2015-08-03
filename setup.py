#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys

from setuptools.command.test import test as TestCommand
from setuptools import setup


class PyTest(TestCommand):

    user_options = [('cov=', None, 'Run coverage'), ('cov-xml=', None, 'Generate junit xml report'), ('cov-html=',
                    None, 'Generate junit html report'), ('junitxml=', None, 'Generate xml of test results')]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.cov = None
        self.cov_xml = False
        self.cov_html = True
        self.junitxml = False

    def finalize_options(self):
        TestCommand.finalize_options(self)
        if self.cov is not None:
            self.cov = ['--cov', self.cov, '--cov-report', 'term-missing']
            if self.cov_xml:
                self.cov.extend(['--cov-report', 'xml'])
            if self.cov_html:
                self.cov.extend(['--cov-report', 'html'])
        if self.junitxml is not None:
            self.junitxml = ['--junitxml', self.junitxml]

    def run_tests(self):
        try:
            import pytest
        except:
            raise RuntimeError('py.test is not installed, run: pip install pytest')
        params = {'args': self.test_args}
        if self.cov:
            params['args'] += self.cov
            params['plugins'] = ['cov']
        if self.junitxml:
            params['args'] += self.junitxml
        params['args'] += ['--doctest-modules', 'codevalidator.py', '-s', '-vv']
        errno = pytest.main(**params)
        sys.exit(errno)

if __name__ == '__main__':
    # Assemble additional setup commands
    cmdclass = {}
    cmdclass['test'] = PyTest

    command_options = {'test': {'test_suite': ('setup.py', 'tests'), 'cov': ('setup.py', 'codevalidator')}}

    with open('README.rst') as readme:
        setup(
            name='codevalidator',
            version='0.8.2',
            description='Simple source code validator with file reformatting option (remove trailing WS, pretty print XML, ..)',
            long_description=readme.read(),
            author='Henning Jacobs',
            author_email='henning@jacobs1.de',
            url='https://github.com/hjacobs/codevalidator',
            py_modules=['codevalidator'],
            packages=['pythontidy'],
            entry_points={'console_scripts': ['codevalidator = codevalidator:main']},
            extras_require={'YAML': ['PyYAML'], 'XML': ['lxml'], 'Python': ['pep8', 'autopep8', 'pyflakes']},
            tests_require=['pytest-cov', 'pytest>=2.7.2'],
            cmdclass=cmdclass,
            command_options=command_options,
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
