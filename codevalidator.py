#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Simple source code validator with file reformatting option (remove trailing WS, pretty print XML, ..)

written by Henning Jacobs <henning@jacobs1.de>
"""

from cStringIO import StringIO
from collections import defaultdict

from pythontidy import PythonTidy
from tempfile import NamedTemporaryFile
from xml.etree.ElementTree import ElementTree
import argparse
import ast
import csv
import fnmatch
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import shutil

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

DEFAULT_CONFIG = {
    'exclude_dirs': ['.svn', '.git'],
    'rules': {
        '*.coffee': DEFAULT_RULES + ['coffeelint'],
        '*.conf': DEFAULT_RULES,
        '*.css': DEFAULT_RULES,
        '*.groovy': DEFAULT_RULES,
        '*.htm': DEFAULT_RULES,
        '*.html': DEFAULT_RULES,
        '*.java': DEFAULT_RULES + ['jalopy'],
        '*.js': DEFAULT_RULES,
        '*.json': DEFAULT_RULES + ['json'],
        '*.jsp': DEFAULT_RULES,
        '*.less': DEFAULT_RULES,
        '*.md': DEFAULT_RULES,
        '*.php': DEFAULT_RULES + ['phpcs'],
        '*.phtml': DEFAULT_RULES,
        '*.pp': DEFAULT_RULES + ['puppet'],
        '*.properties': DEFAULT_RULES + ['ascii'],
        '*.py': DEFAULT_RULES + ['pep8', 'pyflakes'],
        '*.sh': DEFAULT_RULES,
        '*.sql': DEFAULT_RULES,
        '*.sql_diff': DEFAULT_RULES,
        '*.styl': DEFAULT_RULES,
        '*.txt': DEFAULT_RULES,
        '*.vm': DEFAULT_RULES,
        '*.wsdl': DEFAULT_RULES,
        '*.xml': DEFAULT_RULES + ['xml', 'xmlfmt'],
        '*pom.xml': ['pomdesc'],
    },
    'options': {'phpcs': {'standard': 'PSR', 'encoding': 'UTF-8'}, 'pep8': {
        'max_line_length': 120,
        'ignore': 'N806',
        'passes': 5,
        'select': 'e501',
    }, 'jalopy': {'classpath': '/opt/jalopy/lib/jalopy-1.9.4.jar:/opt/jalopy/lib/jh.jar'}},
    'dir_rules': {'db_diffs': ['sql_diff_dir', 'sql_diff_sql'], 'database': ['database_dir']},
    'create_backup': True,
    'backup_filename': '.{original}.pre-cvfix',
    'verbose': 0,
}

CONFIG = DEFAULT_CONFIG

# base directory where we can find our config folder
# NOTE: to support symlinking codevalidator.py into /usr/local/bin/
# we use realpath to resolve the symlink back to our base directory
BASE_DIR = os.path.dirname(os.path.realpath(__file__))


class BaseException(Exception):

    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return '%s: %s' % (self.__class__.__name__, self.msg)


class ConfigurationError(BaseException):

    '''missing or incorrect codevalidator configuration'''

    pass


class ExecutionError(BaseException):

    '''error while executing some command'''

    pass


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
    import pep8
    pep8style = pep8.StyleGuide(max_line_length=options['max_line_length'])
    check = pep8style.input_file(fd.name)
    return check == 0


def __jalopy(original, options):
    jalopy_config = options.get('config')
    java_bin = options.get('java_bin', '/usr/bin/java')
    classpath = options.get('classpath')

    if not classpath:
        raise ConfigurationError('Jalopy classpath not set')

    _env = {}
    _env.update(os.environ)
    _env['LANG'] = 'en_US.utf8'
    _env['LC_ALL'] = 'en_US.utf8'
    with NamedTemporaryFile(suffix='.java', delete=False) as f:
        f.write(original)
        f.flush()
        jalopy = [java_bin, '-classpath', classpath, 'Jalopy']
        config = (['--convention', jalopy_config] if jalopy_config else [])
        cmd = jalopy + config + [f.name]
        j = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=_env)
        stdout, stderr = j.communicate()
        if stderr or 'ERROR' in stdout:
            raise ExecutionError('Failed to execute Jalopy: %s%s' % (stderr, stdout))
        f.seek(0)
        result = f.read()
    return result


@message('is not Jalopy formatted')
def _validate_jalopy(fd, options={}):
    original = fd.read()
    result = __jalopy(original, options)
    return original == result


def _fix_jalopy(src, dst, options={}):
    original = src.read()
    result = __jalopy(original, options)
    dst.write(result)


def _fix_pythontidy(src, dst):
    PythonTidy.tidy_up(src, dst)


def _fix_pep8(src, dst, options):
    import autopep8
    if type(src) is file:
        source = src.read()
    else:
        source = src.getvalue()

    class OptionsClass:

        select = options['select']
        ignore = options['ignore']
        pep8_passes = options['passes']
        max_line_length = options['max_line_length']
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


@message('doesn\'t pass Pyflakes validation')
def _validate_pyflakes(fd, options={}):
    from pyflakes import checker
    tree = ast.parse(fd.read(), fd.name)
    w = checker.Checker(tree, fd.name)
    w.messages.sort(key=lambda x: x.lineno)
    for message in w.messages:
        error = message.message % message.message_args
        _detail(error, line=message.lineno)
    return len(w.messages) == 0


@message('contains syntax errors')
def _validate_database_dir(fname, options={}):
    if 'database/lounge' in fname or not fnmatch.fnmatch(fname, '*.sql'):
        return True
    pgsqlparser_bin = options.get('pgsql-parser-bin', '/opt/codevalidator/PgSqlParser')

    try:
        return_code = subprocess.call([
            pgsqlparser_bin,
            '-q',
            '-c',
            '-i',
            fname,
        ])
        return return_code == 0
    except:
        return False


def _validate_sql_diff_dir(fname, options=None):
    if not (fnmatch.fnmatch(fname, '*.sql_diff') or fnmatch.fnmatch(fname, '*.py')):
        return 'dbdiffs and migration scripts should use .sql_diff or .py extension'

    dirs = get_dirs(fname)
    basedir = dirs[-2]
    filename = dirs[-1]

    if not re.match('^[A-Z]+-[0-9]+', basedir):
        return 'Patch should be located in directory with the name of the jira ticket'

    if not filename.startswith(basedir):
        return 'Filename should start with the parent directory name'

    return True


def _validate_sql_diff_sql(fname, options=None):
    dirs = get_dirs(fname)
    filename = dirs[-1]

    if fname.endswith('.py'):
        return True

    sql = open(fname).read()
    if not re.search('[Ss][Ee][Tt] +[Rr][Oo][Ll][Ee] +[Tt][Oo] +zalando(_admin)?\s*', sql):
        return 'set role to zalando; must be present in db diff'

    if re.search('^ *\\\\cd +', sql, re.MULTILINE):
        return "\cd : is not allowed in db diffs anymore"

    for m in re.finditer('^ *\\\\i +([^\s]+)', sql, re.MULTILINE):
        if not m.group(1).startswith('database/'):
            return 'include path (\i ) should starts with `database/` directory'

    if fnmatch.fnmatch(filename, '*rollback*'):
        if not fnmatch.fnmatch(fname, '*.rollback.sql_diff'):
            return 'rollback script should have .rollback.sql_diff extension'
        patch_name = filename.replace('.rollback.sql_diff', '')
        re_patch_name = re.escape(patch_name)
        pattern = \
            '[Ss][Ee][Ll][Ee][Cc][Tt] +_v\.unregister_patch *\( *\\\'{patch_name}\\\''.format(patch_name=re_patch_name)
        if not re.search(pattern, sql):
            return 'unregister patch not found or patch name does not match with filename'
    else:
        patch_name = filename.replace('.sql_diff', '')
        re_patch_name = re.escape(patch_name)
        pattern = \
            '[Ss][Ee][Ll][Ee][Cc][Tt] +_v\.register_patch *\( *\\\'{patch_name}\\\''.format(patch_name=re_patch_name)
        if not re.search(pattern, sql):
            return 'register patch not found or patch name does not match with filename'

    return True


VALIDATION_ERRORS = []
VALIDATION_DETAILS = []


def _error(fname, rule, func, message=None):
    '''output the collected error messages and also print details if verbosity > 0'''

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


def validate_file_dir_rules(fname):
    fullpath = os.path.abspath(fname)
    dirs = get_dirs(fullpath)
    dirrules = sum([CONFIG['dir_rules'][rule] for rule in CONFIG['dir_rules'] if rule in dirs], [])
    for rule in dirrules:
        logging.debug('Validating %s with %s..', fname, rule)
        func = globals().get('_validate_' + rule)
        if not func:
            print rule, 'does not exist'
            continue
        options = CONFIG.get('options', {}).get(rule)
        try:
            if options:
                res = func(fname, options)
            else:
                res = func(fname)
        except Exception, e:
            _error(fname, rule, func, 'ERROR validating {0}: {1}'.format(rule, e))
        else:
            if not res:
                _error(fname, rule, func)
            elif type(res) == str:
                _error(fname, rule, func, res)


def validate_file_with_rules(fname, rules):
    with open(fname, 'rb') as fd:
        for rule in rules:
            logging.debug('Validating %s with %s..', fname, rule)
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
                elif type(res) == str:
                    _error(fname, rule, func, res)


def validate_file(fname):
    for exclude in CONFIG['exclude_dirs']:
        if '/%s/' % exclude in fname:
            return
    validate_file_dir_rules(fname)
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
    was_fixed = True
    if CONFIG.get('create_backup', True):
        dirname, basename = os.path.split(fname)
        shutil.copy2(fname, os.path.join(dirname, CONFIG['backup_filename'].format(original=basename)))  # creates a backup
    with open(fname, 'rb') as fd:
        dst = fd
        for rule in rules:
            func = globals().get('_fix_' + rule)
            if func:
                print '{0}: Trying to fix {1}..'.format(fname, rule)
                options = CONFIG.get('options', {}).get(rule)
                src = dst
                dst = StringIO()
                src.seek(0)
                try:
                    if options:
                        func(src, dst, options)
                    else:
                        func(src, dst)
                    was_fixed &= True
                except Exception, e:
                    was_fixed = False
                    print '{0}: ERROR fixing {1}: {2}'.format(fname, rule, e)

    fixed = (dst.getvalue() if hasattr(dst, 'getvalue') else '')
    # if the lenght of the fixed code is 0 we don't write the fixed version because either:
    # a) is not worth it
    # b) some fix functions destroyed the code
    if was_fixed and len(fixed) > 0:
        with open(fname, 'wb') as fd:
            fd.write(fixed)
    else:
        print '{0}: ERROR fixing file. File remained unchanged'.format(fname)


def fix_files():
    rules_by_file = defaultdict(list)
    for fname, rule in VALIDATION_ERRORS:
        rules_by_file[fname].append(rule)
    for fname, rules in rules_by_file.items():
        fix_file(fname, rules)


def get_dirs(path):
    head, tail = os.path.split(path)
    if tail:
        return get_dirs(head) + [tail]
    else:
        return []


def main():
    parser = argparse.ArgumentParser(description='Validate source code files and optionally reformat them.')
    parser.add_argument('-r', '--recursive', action='store_true', help='process given directories recursively')
    parser.add_argument('-c', '--config', help='use custom configuration file (default: ~/.codevalidatorrc)')
    parser.add_argument('-f', '--fix', action='store_true', help='try to fix validation errors (by reformatting files)')
    parser.add_argument('-a', '--apply', metavar='RULE', action='append', help='apply the given rule(s)')
    parser.add_argument('-v', '--verbose', action='count', help='print more detailed error information (-vv for debug)')
    parser.add_argument('--no-backup', action='store_true', help='for --fix: do not create a backup file')
    parser.add_argument('files', metavar='FILES', nargs='+', help='list of source files to validate')
    args = parser.parse_args()

    config_file = os.path.expanduser('~/.codevalidatorrc')
    if os.path.isfile(config_file) and not args.config:
        args.config = config_file
    if args.config:
        CONFIG.update(json.load(open(args.config, 'rb')))
    if args.verbose:
        CONFIG['verbose'] = args.verbose
        if args.verbose > 1:
            logging.basicConfig(level=logging.DEBUG, format='%(levelname)s %(message)s')
    if args.no_backup:
        CONFIG['create_backup'] = False

    for f in args.files:
        if args.recursive and os.path.isdir(f):
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
