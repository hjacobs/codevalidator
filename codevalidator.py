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
import tempfile
from cStringIO import StringIO
from collections import defaultdict
from pythontidy import PythonTidy
import pep8
import autopep8
from xml.etree.ElementTree import ElementTree

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
    '*.coffee': DEFAULT_RULES + ['coffeelint'],
    '*.conf': DEFAULT_RULES,
    '*.css': DEFAULT_RULES,
    '*.groovy': DEFAULT_RULES,
    '*.htm': DEFAULT_RULES,
    '*.html': DEFAULT_RULES,
    '*.java': DEFAULT_RULES,
    '*.js': DEFAULT_RULES,
    '*.json': DEFAULT_RULES + ['json'],
    '*.jsp': DEFAULT_RULES,
    '*.less': DEFAULT_RULES,
    '*.php': DEFAULT_RULES + ['phpcs'],
    '*.phtml': DEFAULT_RULES,
    '*.pp': DEFAULT_RULES + ['puppet'],
    '*.properties': DEFAULT_RULES + ['ascii'],
    '*.py': DEFAULT_RULES + ['pep8'],
    '*.sh': DEFAULT_RULES,
    '*.sql': DEFAULT_RULES,
    '*.sql_diff': DEFAULT_RULES,
    '*.styl': DEFAULT_RULES,
    '*.txt': DEFAULT_RULES,
    '*.vm': DEFAULT_RULES,
    '*.wsdl': DEFAULT_RULES,
    '*.xml': DEFAULT_RULES + ['xml', 'xmlfmt'],
    '*pom.xml': ['pomdesc'],
}, 'options': {'phpcs': {'standard': 'PSR', 'encoding': 'UTF-8'},
               'pep8': {"max_line_length": 120,
                        "ignore": "N806",
                        "passes": 5,
                        "select": "e501"}}}

CONFIG = DEFAULT_CONFIG

# base directory where we can find our config folder
# NOTE: to support symlinking codevalidator.py into /usr/local/bin/
# we use realpath to resolve the symlink back to our base directory
BASE_DIR = os.path.dirname(os.path.realpath(__file__))


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


@message('has invalid file path (file name or extension is not allowed)')
def _validate_invalidpath(fd):
    return False


@message('contains tabs')
def _validate_notabs(fd):
    return '\t' not in fd.read()


def _fix_notabs(src, dst):
    dst.write(src.read().replace('\t', ' ' * 4))


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


@message('is not ASCII encoded')
def _validate_ascii(fd):
    try:
        fd.read().decode('ascii')
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


@message('is not valid XML')
def _validate_xml(fd):
    tree = ElementTree()
    try:
        tree.parse(fd)
    except Exception, e:
        _detail('%s: %s' % (e.__class__.__name__, e))
        return False
    return True


def _fix_xmlfmt(src, dst):
    from lxml import etree
    parser = etree.XMLParser(resolve_entities=False)
    tree = etree.parse(src, parser)
    indent_xml(tree.getroot())
    tree.write(dst, encoding='utf-8', xml_declaration=True)
    dst.write('\n')


@message('is not valid JSON')
def _validate_json(fd):
    try:
        json.load(fd)
    except Exception, e:
        _detail('%s: %s' % (e.__class__.__name__, e))
        return False
    return True


@message('is not PythonTidy formatted')
def _validate_pythontidy(fd):
    source = StringIO(fd.read())
    if len(source.getvalue()) < 4:
        # small or empty files are ignored
        return True
    formatted = StringIO()
    PythonTidy.tidy_up(source, formatted)
    return source.getvalue() == formatted.getvalue()


@message('is not pep8 formatted')
def _validate_pep8(fd, options):
    pep8style = pep8.StyleGuide(max_line_length=options["max_line_length"])
    check = pep8style.input_file(fd.name)
    return check == 0


def _fix_pythontidy(src, dst):
    PythonTidy.tidy_up(src, dst)


def _fix_pep8(src, dst, options):
    if type(src) is file:
        source = src.read()
    else:
        source = src.getvalue()

    class OptionsClass():
        select = options["select"]
        ignore = options["ignore"]
        pep8_passes = options["passes"]
        max_line_length = options["max_line_length"]
        verbose = False
        aggressive = True

    fixed = autopep8.fix_string(source, options=OptionsClass)
    dst.write(fixed)


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


@message('fails coffeelint validation')
def _validate_coffeelint(fd, options=None):
    """validate a CoffeeScript file

    Needs a locally installed coffeelint ("npm install -g coffeelint").
    """

    cfgfile = os.path.join(BASE_DIR, 'config/coffeelint.json')
    po = subprocess.Popen('coffeelint --csv -s -f %s' % cfgfile, shell=True, stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, stderr = po.communicate(input=fd.read())
    valid = True
    if stderr:
        valid = False
        _detail(stderr)
    for row in output.split('\n'):
        if row:
            valid = False
            cols = row.split(',')
            if len(cols) > 3:
                _detail(cols[3], line=cols[1])
    return valid


@message('fails puppet parser validation')
def _validate_puppet(fd):
    _env = {}
    _env.update(os.environ)
    _env['HOME'] = '/tmp'
    _env['PATH'] = '/bin:/sbin:/usr/bin:/usr/sbin'
    with tempfile.NamedTemporaryFile() as f:
        f.write(fd.read())
        f.flush()
        cmd = 'puppet parser validate --color=false --confdir=/tmp --vardir=/tmp %s' % (f.name, )
        po = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=_env)
        output, stderr = po.communicate()
        retcode = po.poll()
        valid = True
        if output or retcode != 0:
            valid = False
            _detail('puppet parser exited with %d: %s' % (retcode, re.sub('[^A-Za-z0-9 .:-]', '', output)))
        return valid


@message('has incomplete Maven POM description')
def _validate_pomdesc(fd):
    """check Maven POM for title, description and organization"""

    NS = '{http://maven.apache.org/POM/4.0.0}'
    PROJECT_NAME_REGEX = re.compile(r'^[a-z][a-z0-9-]*$')
    tree = ElementTree()
    try:
        elem = tree.parse(fd)
    except Exception, e:
        _detail('%s: %s' % (e.__class__.__name__, e))
        return False
    # group = elem.findtext(NS + 'groupId')
    name = elem.findtext(NS + 'artifactId')
    # ver = elem.findtext(NS + 'version')
    title = elem.findtext(NS + 'name')
    if title == '${project.artifactId}':
        title = name
    description = elem.findtext(NS + 'description')
    organization = elem.findtext(NS + 'organization/' + NS + 'name')

    if not name or not PROJECT_NAME_REGEX.match(name):
        _detail('has invalid name (does not match %s)' % PROJECT_NAME_REGEX.pattern)
    if not title:
        _detail('is missing title (<name>...</name>)')
    elif title.lower() == name.lower():
        _detail('has same title as name/artifactId')
    if not description:
        _detail('is missing description (<description>..</description>)')
    elif len(description.split()) < 3:
        _detail('has a too short description')
    if not organization:
        _detail('is missing organization (<organization><name>..</name></organization>)')
    return not VALIDATION_DETAILS

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
            elif line:
                print '  line {0}: {1}'.format(line, message)
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
    for exclude in CONFIG['exclude_dirs']:
        if '/%s/' % exclude in fname:
            return
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


def fix_file(fname, rules):
    was_fixed = False
    with open(fname, 'rb') as fd:
        dst = fd
        for rule in rules:
            func = globals().get('_fix_' + rule)
            if func:
                options = CONFIG.get('options', {}).get(rule)
                src = dst
                dst = StringIO()
                src.seek(0)
                try:
                    if options:
                        func(src, dst, options)
                    else:
                        func(src, dst)
                    was_fixed = True
                except Exception, e:
                    print '{0}: ERROR fixing {1}: {2}'.format(fname, rule, e)
    if was_fixed:
        with open(fname, 'wb') as fd:
            fd.write(dst.getvalue())


def fix_files():
    rules_by_file = defaultdict(list)
    for fname, rule in VALIDATION_ERRORS:
        rules_by_file[fname].append(rule)
    for fname, rules in rules_by_file.items():
        fix_file(fname, rules)


def main():
    parser = argparse.ArgumentParser(description='Validate source code files and optionally reformat them.')
    parser.add_argument('-r', '--recursive', action='store_true', help='process given directories recursively')
    parser.add_argument('-c', '--config', help='use custom configuration file (default: ~/.codevalidatorrc)')
    parser.add_argument('-f', '--fix', action='store_true', help='try to fix validation errors (by reformatting files)')
    parser.add_argument('-a', '--apply', metavar='RULE', action='append', help='apply the given rule(s)')
    parser.add_argument('-v', '--verbose', action='store_true', help='print more detailed error information')
    parser.add_argument('files', metavar='FILES', nargs='+', help='list of source files to validate')
    args = parser.parse_args()

    config_file = os.path.expanduser('~/.codevalidatorrc..')
    if os.path.isfile(config_file) and not args.config:
        args.config = config_file
    if args.config:
        CONFIG.update(json.load(open(args.config, 'rb')))
    CONFIG['verbose'] = args.verbose

    for f in args.files:
        if args.recursive:
            validate_directory(f)
        elif args.apply:
            fix_file(f, args.apply)
        else:
            validate_file(f)
    if VALIDATION_ERRORS:
        if args.fix:
            fix_files()
        sys.exit(1)


if __name__ == '__main__':
    main()
