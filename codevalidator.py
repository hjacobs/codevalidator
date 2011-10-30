#!/usr/bin/python

import argparse
import fnmatch
import os
import re
import sys

NOT_SPACE = re.compile('[^ ]')
TRAILING_WHITESPACE_CHARS = set(' \t')

DEFAULT_CONFIG = {
    'exclude_dirs': ['.svn'],
    'rules': {
        '*.java': ['utf8', 'nobom', 'notabs', 'nocr', 'notrailingws'],
        '*.jsp': ['utf8', 'nobom', 'notabs', 'nocr'],
        '*.properties': ['utf8', 'nobom', 'notabs', 'nocr', 'notrailingws'],
        '*.py': ['utf8', 'nobom', 'notabs', 'nocr', 'indent4', 'notrailingws'],
        '*.sh': ['utf8', 'nobom', 'notabs', 'nocr', 'notrailingws'],
        '*.sql': ['utf8', 'nobom', 'notabs', 'nocr', 'notrailingws'],
        '*.xml': ['utf8', 'nobom', 'notabs', 'nocr', 'indent4', 'notrailingws'],
        '*.html': ['utf8', 'nobom', 'notabs', 'nocr', 'notrailingws'],
        '*.js': ['utf8', 'nobom', 'notabs', 'nocr', 'indent4', 'notrailingws'],
        '*.less': ['utf8', 'nobom', 'notabs', 'nocr', 'notrailingws'],
        '*.css': ['utf8', 'nobom', 'notabs', 'nocr'],
    }
}

config = DEFAULT_CONFIG

def message(msg):
    """simple decorator to attach a error message to a validation function"""
    def wrap(f):
        f.message = msg
        return f
    return wrap

@message('contains tabs')
def _validate_notabs(fd):
    return '\t' not in fd.read()

@message('contains carriage return (CR)')
def _validate_nocr(fd):
    return '\r' not in fd.read()

@message('is not UTF-8 encoded')
def _validate_utf8(fd):
    try:
        fd.read().decode('utf-8')
    except UnicodeDecodeError:
        return False;
    return True

@message('has UTF-8 byte order mark (BOM)')
def _validate_nobom(fd):
    return not fd.read(3).startswith('\xef\xbb\xbf')

@message('contains invalid indentation (not 4 spaces)')
def _validate_indent4(fd):
    for line in fd:
        g = NOT_SPACE.search(line)
        if g and g.start(0) % 4 != 0:
            if g.group(0) == '*' and g.start(0)-1 % 4 == 0:
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

validation_errors = []
def _error(fname, rule, func):
    print '{0}: {1}'.format(fname, func.message)
    validation_errors.append((fname, rule))

def validate_file_with_rules(fname, rules):
    with open(fname, 'rb') as fd:
        for rule in rules:
            fd.seek(0)
            func = globals().get('_validate_' + rule)
            if not func:
                print rule, 'does not exist'
                continue
            res = func(fd)
            if not res:
                _error(fname, rule, func)

def validate_file(fname):
    for pattern, rules in config['rules'].items():
        if fnmatch.fnmatch(fname, pattern):
            validate_file_with_rules(fname, rules)

def validate_directory(path):
    for root, dirnames, filenames in os.walk(path):
        for exclude in config['exclude_dirs']:
            if exclude in dirnames:
                dirnames.remove(exclude)
        for fname in filenames:
            validate_file(os.path.join(root, fname))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Validate source code files.')
    parser.add_argument('-r', '--recursive', action='store_true',
        help='process given directories recursively')
    parser.add_argument('files', metavar='FILES', nargs='+',
        help='list of source files to validate')
    args = parser.parse_args()
    for f in args.files:
        if args.recursive:
            validate_directory(f)
        else:
            validate_file(f)
    if validation_errors:
        sys.exit(1)

