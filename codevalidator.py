#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Simple source code validator with file reformatting option (remove trailing WS, pretty print XML, ..)

written by Henning Jacobs <henning@jacobs1.de>
"""

import argparse
import csv
import fnmatch
import json
import os
import re
import subprocess
import sys
from cStringIO import StringIO
from collections import defaultdict
from lxml import etree
from pythontidy import PythonTidy

NOT_SPACE = re.compile('[^ ]')
TRAILING_WHITESPACE_CHARS = set(' \t')
INDENTATION = '    '

DEFAULT_RULES = [
    'utf8',
    'nobom',
    'notabs',
    'nocr',
    'notrailingws',
]

DEFAULT_CONFIG = {'exclude_dirs': ['.svn', '.git'], 'rules': {
    '*.conf': DEFAULT_RULES,
    '*.css': DEFAULT_RULES,
    '*.groovy': DEFAULT_RULES,
    '*.htm': DEFAULT_RULES,
    '*.html': DEFAULT_RULES,
    '*.java': DEFAULT_RULES,
    '*.js': DEFAULT_RULES,
    '*.jsp': DEFAULT_RULES,
    '*.less': DEFAULT_RULES,
    '*.php': DEFAULT_RULES + ['phpcs'],
    '*.properties': DEFAULT_RULES,
    '*.py': DEFAULT_RULES + ['pythontidy'],
    '*.sh': DEFAULT_RULES,
    '*.sql': DEFAULT_RULES,
    '*.sql_diff': DEFAULT_RULES,
    '*.txt': DEFAULT_RULES,
    '*.vm': DEFAULT_RULES,
    '*.xml': DEFAULT_RULES + ['xmlfmt'],
}, 'options': {'phpcs': {'standard': 'PSR', 'encoding': 'UTF-8'}}}

CONFIG = DEFAULT_CONFIG


def indent_xml(elem, level=0):
    """xmlindent from http://infix.se/2007/02/06/gentlemen-indent-your-xml"""

    i = '\n' + level * INDENTATION
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + INDENTATION
        for e in elem:
            indent_xml(e, level + 1)
            if not e.tail or not e.tail.strip():
                e.tail = i + INDENTATION
        if not e.tail or not e.tail.strip():
            e.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


def message(msg):
    """simple decorator to attach a error message to a validation function"""

    def wrap(f):
        f.message = msg
        return f

    return wrap


@message('contains tabs')
def _validate_notabs(fd):
    return '\t' not in fd.read()


def _fix_notabs(src, dst):
    dst.write(src.read().replace('\t', '   '))


@message('contains carriage return (CR)')
def _validate_nocr(fd):
    return '\r' not in fd.read()


def _fix_nocr(src, dst):
    dst.write(src.read().replace('\r', ''))


@message('is not UTF-8 encoded')
def _validate_utf8(fd):
    try:
        fd.read().decode('utf-8')
    except UnicodeDecodeError:
        return False
    return True


@message('has UTF-8 byte order mark (BOM)')
def _validate_nobom(fd):
    return not fd.read(3).startswith('\xef\xbb\xbf')


@message('contains invalid indentation (not 4 spaces)')
def _validate_indent4(fd):
    for line in fd:
        g = NOT_SPACE.search(line)
        if g and g.start(0) % 4 != 0:
            if g.group(0) == '*' and g.start(0) - 1 % 4 == 0:
                # hack to exclude block comments aligned on "*"
                pass
            else:
                return False
    return True


@message('contains lines with trailing whitespace')
def _validate_notrailingws(fd):
    for line in fd:
        if line.rstrip('\n\r')[-1:] in TRAILING_WHITESPACE_CHARS:
            return False
    return True


def _fix_notrailingws(src, dst):
    for line in src:
        dst.write(line.rstrip())
        dst.write('\n')


@message('is not well-formatted (pretty-printed) XML')
def _validate_xmlfmt(fd):
    source = StringIO(fd.read())
    formatted = StringIO()
    _fix_xmlfmt(source, formatted)
    return source.getvalue() == formatted.getvalue()


def _fix_xmlfmt(src, dst):
    parser = etree.XMLParser(resolve_entities=False)
    tree = etree.parse(src, parser)
    indent_xml(tree.getroot())
    tree.write(dst, encoding='utf-8', xml_declaration=True)
    dst.write('\n')


@message('is not PythonTidy formatted')
def _validate_pythontidy(fd):
    source = StringIO(fd.read())
    if len(source.getvalue()) < 4:
        # small or empty files are ignored
        return True
    formatted = StringIO()
    PythonTidy.tidy_up(source, formatted)
    return source.getvalue() == formatted.getvalue()


def _fix_pythontidy(src, dst):
    PythonTidy.tidy_up(src, dst)


@message('is not phpcs (%(standard)s standard) formatted')
def _validate_phpcs(fd, options):
    """validate a PHP file to conform to PHP_CodeSniffer standards

    Needs a locally installed phpcs ("pear install PHP_CodeSniffer").
    Look at https://github.com/klaussilveira/phpcs-psr to get the PSR standard (sniffs)."""

    po = subprocess.Popen('phpcs -n --report=csv --standard=%s --encoding=%s -' % (options['standard'],
                          options['encoding']), shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE)
    output, stderr = po.communicate(input=fd.read())
    reader = csv.DictReader(output.split('\n'), delimiter=',', doublequote=False, escapechar='\\')
    valid = True
    for row in reader:
        valid = False
        _detail(row['Message'], line=row['Line'], column=row['Column'])
    return valid

VALIDATION_ERRORS = []
VALIDATION_DETAILS = []


def _error(fname, rule, func, message=None):
    if not message:
        message = func.message
    print '{0}: {1}'.format(fname, message % CONFIG.get('options', {}).get(rule, {}))
    if CONFIG['verbose']:
        for message, line, column in VALIDATION_DETAILS:
            if line and column:
                print '  line {0}, col {1}: {2}'.format(line, column, message)
            else:
                print '  {0}'.format(message)
    VALIDATION_DETAILS[:] = []
    VALIDATION_ERRORS.append((fname, rule))


def _detail(message, line=None, column=None):
    VALIDATION_DETAILS.append((message, line, column))


def validate_file_with_rules(fname, rules):
    with open(fname, 'rb') as fd:
        for rule in rules:
            fd.seek(0)
            func = globals().get('_validate_' + rule)
            if not func:
                print rule, 'does not exist'
                continue
            options = CONFIG.get('options', {}).get(rule)
            try:
                if options:
                    res = func(fd, options)
                else:
                    res = func(fd)
            except Exception, e:
                _error(fname, rule, func, 'ERROR validating {0}: {1}'.format(rule, e))
            else:
                if not res:
                    _error(fname, rule, func)


def validate_file(fname):
    for pattern, rules in CONFIG['rules'].items():
        if fnmatch.fnmatch(fname, pattern):
            validate_file_with_rules(fname, rules)


def validate_directory(path):
    for root, dirnames, filenames in os.walk(path):
        for exclude in CONFIG['exclude_dirs']:
            if exclude in dirnames:
                dirnames.remove(exclude)
        for fname in filenames:
            validate_file(os.path.join(root, fname))


def fix_files():
    rules_by_file = defaultdict(list)
    for fname, rule in VALIDATION_ERRORS:
        rules_by_file[fname].append(rule)
    for fname, rules in rules_by_file.items():
        was_fixed = False
        with open(fname, 'rb') as fd:
            dst = fd
            for rule in rules:
                func = globals().get('_fix_' + rule)
                if func:
                    src = dst
                    dst = StringIO()
                    src.seek(0)
                    try:
                        func(src, dst)
                        was_fixed = True
                    except Exception, e:
                        print '{0}: ERROR fixing {1}: {2}'.format(fname, rule, e)
        if was_fixed:
            with open(fname, 'wb') as fd:
                fd.write(dst.getvalue())


def main():
    parser = argparse.ArgumentParser(description='Validate source code files and optionally reformat them.')
    parser.add_argument('-r', '--recursive', action='store_true', help='process given directories recursively')
    parser.add_argument('-c', '--config', help='use custom configuration file (default: ~/.codevalidatorrc)')
    parser.add_argument('-f', '--fix', action='store_true', help='try to fix validation errors (by reformatting files)')
    parser.add_argument('-v', '--verbose', action='store_true', help='print more detailed error information')
    parser.add_argument('files', metavar='FILES', nargs='+', help='list of source files to validate')
    args = parser.parse_args()

    config_file = os.path.expanduser('~/.codevalidatorrc')
    if os.path.isfile(config_file) and not args.config:
        args.config = config_file
    if args.config:
        CONFIG.update(json.load(open(args.config, 'rb')))
    CONFIG['verbose'] = args.verbose

    for f in args.files:
        if args.recursive:
            validate_directory(f)
        else:
            validate_file(f)
    if VALIDATION_ERRORS:
        if args.fix:
            fix_files()
        sys.exit(1)


if __name__ == '__main__':
    main()
