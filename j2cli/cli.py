#! /usr/bin/env python

"""j2cli main file"""

import argparse
import imp
import inspect
import os
import sys

import jinja2
import yaml


# Loader
try:
    # PyYAML 5.1 supports FullLoader
    Loader = yaml.FullLoader
except AttributeError:
    # Have to use SafeLoader for older versions
    Loader = yaml.SafeLoader


class FilePathLoader(jinja2.BaseLoader):
    """Custom Jinja2 template loader which just loads a single template file"""

    def __init__(self, cwd, encoding='utf-8'):
        self.cwd = cwd
        self.encoding = encoding

    def get_source(self, environment, template):
        # Path
        filename = os.path.join(self.cwd, template)

        # Read
        try:
            with open(template, 'rt', encoding=self.encoding) as f:
                contents = f.read()
        except IOError:
            raise jinja2.TemplateNotFound(template)

        # Finish
        uptodate = lambda: False
        return contents, filename, uptodate


class Jinja2TemplateRenderer(object):
    """Template renderer"""

    ENABLED_EXTENSIONS=(
        'jinja2.ext.i18n',
        'jinja2.ext.do',
        'jinja2.ext.loopcontrols',
    )

    def __init__(self, cwd, allow_undefined, encoding='utf-8', j2_env_params={}):
        # Encoding
        self.encoding = encoding

        # Custom env params
        j2_env_params.setdefault('keep_trailing_newline', True)
        j2_env_params.setdefault('undefined', jinja2.Undefined if allow_undefined else jinja2.StrictUndefined)
        j2_env_params.setdefault('extensions', self.ENABLED_EXTENSIONS)
        j2_env_params.setdefault('loader', FilePathLoader(cwd))

        # Environment
        self._env = jinja2.Environment(**j2_env_params)

    def register_filters(self, filters):
        self._env.filters.update(filters)

    def register_tests(self, tests):
        self._env.tests.update(tests)

    def import_filters(self, filename):
        self.register_filters(self._import_functions(filename))

    def import_tests(self, filename):
        self.register_tests(self._import_functions(filename))

    def _import_functions(self, filename):
        m = imp.load_source('imported-funcs', filename)
        return dict((name, func) for name, func in inspect.getmembers(m) if inspect.isfunction(func))

    def render(self, template_path, context):
        """ Render a template
        :param template_path: Path to the template file
        :type template_path: basestring
        :param context: Template data
        :type context: dict
        :return: Rendered template
        :rtype: basestring
        """
        return self._env \
            .get_template(template_path) \
            .render(context) \
            .encode(self.encoding)


def render_command(cwd, stdin, argv):
    """ Pure render command
    :param cwd: Current working directory (to search for the files)
    :type cwd: basestring
    :param environ: Environment variables
    :type environ: dict
    :param stdin: Stdin stream
    :type stdin: file
    :param argv: Command-line arguments
    :type argv: list
    :return: Rendered template
    :rtype: basestring
    """
    parser = argparse.ArgumentParser(
        prog='j2',
        description='Command-line interface to Jinja2 for templating in shell scripts.',
        epilog=''
    )
    parser.add_argument('--filters', nargs='+', default=[], metavar='python-file', dest='filters',
                        help='Load custom Jinja2 filters from a Python file: all top-level functions are imported.')
    parser.add_argument('--tests', nargs='+', default=[], metavar='python-file', dest='tests',
                        help='Load custom Jinja2 tests from a Python file.')
    parser.add_argument('--customize', default=None, metavar='python-file.py', dest='customize',
                        help='A Python file that implements hooks to fine-tune the j2cli behavior')
    parser.add_argument('--undefined', action='store_true', dest='undefined', help='Allow undefined variables to be used in templates (no error will be raised)')
    parser.add_argument('-o', metavar='outfile', dest='output_file', help="Output to a file instead of stdout")
    parser.add_argument('template', help='Template file to process')
    parser.add_argument('data', nargs='?', default=None, help='Input data file path')
    args = parser.parse_args(argv)

    # Read YAML file and read condtext data
    with open(args.data) as f:
        context = yaml.load(f, Loader=Loader)

    # Renderer
    renderer = Jinja2TemplateRenderer(
        cwd, args.undefined,
        encoding='cp1252',
        #j2_env_params={'newline_sequence': '\r\n'}
        )

    # Filters, Tests
    for fname in args.filters:
        renderer.import_filters(fname)
    for fname in args.tests:
        renderer.import_tests(fname)

    # Render
    result = renderer.render(args.template, context)

    # -o
    if args.output_file:
        with open(args.output_file, 'wt', encoding='utf-8') as f:
            f.write(result.decode('utf-8'))
        return b''

    # Finish
    return result


if __name__ == '__main__':
    try:
        output = render_command(
            os.getcwd(),
            sys.stdin,
            sys.argv[1:]
        )
    except SystemExit:
        exit(1)
    outstream = getattr(sys.stdout, 'buffer', sys.stdout)
    outstream.write(output)
