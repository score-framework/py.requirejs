# Copyright © 2017 STRG.AT GmbH, Vienna, Austria
#
# This file is part of the The SCORE Framework.
#
# The SCORE Framework and all its parts are free software: you can redistribute
# them and/or modify them under the terms of the GNU Lesser General Public
# License version 3 as published by the Free Software Foundation which is in the
# file named COPYING.LESSER.txt.
#
# The SCORE Framework and all its parts are distributed without any WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. For more details see the GNU Lesser General Public
# License.
#
# If you have not received a copy of the GNU Lesser General Public License see
# http://www.gnu.org/licenses/.
#
# The License-Agreement realised between you as Licensee and STRG.AT GmbH as
# Licenser including the issue of its valid conclusion and its pre- and
# post-contractual effects is governed by the laws of Austria. Any disputes
# concerning this License-Agreement including the issue of its valid conclusion
# and its pre- and post-contractual effects are exclusively decided by the
# competent court, in whose district STRG.AT GmbH has its registered seat, at
# the discretion of STRG.AT GmbH also the competent court, in whose district the
# Licensee has his registered seat, an establishment or assets.

from score.init import ConfiguredModule, ConfigurationError, parse_list
import json
import os
import tempfile
import subprocess
from score.tpl import TemplateNotFound
from score.tpl.loader import Loader
from score.webassets import WebassetsProxy
import hashlib
import re


defaults = {
    'cachedir': None,
    'config_file': None,
    'passthrough_extensions': [],
    'path.nodejs': 'nodejs',
}


def init(confdict, tpl, webassets):
    """
    Initializes this module acoording to the :ref:`SCORE module initialization
    guidelines <module_initialization>` with the following configuration keys:
    """
    conf = defaults.copy()
    conf.update(confdict)
    if conf['cachedir']:
        cachedir = conf['cachedir']
        if not os.path.isdir(cachedir):
            import score.requirejs
            raise ConfigurationError(
                score.requirejs,
                'Configured `cachedir` does not exist')
    else:
        cachedir = os.path.join(tempfile.gettempdir(), 'score', 'jslib')
        os.makedirs(cachedir, exist_ok=True)
    return ConfiguredRequirejsModule(
        tpl, webassets, conf['config_file'], conf['path.nodejs'],
        parse_list(conf['passthrough_extensions']))


class ConfiguredRequirejsModule(ConfiguredModule):

    def __init__(self, tpl, webassets, config_file, nodejs_path,
                 passthrough_extensions):
        import score.requirejs
        super().__init__(score.requirejs)
        self.tpl = tpl
        self.webassets = webassets
        self.config_file = config_file
        self.nodejs_path = nodejs_path
        self.passthrough_extensions = passthrough_extensions
        self.loader = RequireJsLoader(self)
        self.tpl.loaders['js'].append(self.loader)

    def score_webassets_proxy(self):
        return RequirejsAssets(self)

    def create_bundle(self, paths=None):
        rendered_requirejs = self.tpl.render('!require.js')
        with tempfile.TemporaryDirectory() as tmpdir:
            srcdir = os.path.join(tmpdir, 'src')
            os.makedirs(srcdir)
            open(os.path.join(srcdir, 'require.js'), 'w').write(
                rendered_requirejs)
            include_paths = self._copy_files(srcdir, paths)
            script_tpl = r'''
                var conf = require("fs").readFileSync(%s, {
                    encoding: "UTF-8"
                });
                eval("conf = " + conf + ";");
                var overrides = %s;
                for (var key in overrides) {
                    conf[key] = overrides[key];
                }
                require("requirejs").optimize(conf, function (result) {
                    console.warn(result);
                }, function(err) {
                    console.warn(err);
                    process.exit(1);
                });
            '''
            script = script_tpl % (json.dumps(self.config_file), json.dumps({
                "out": "stdout",
                "include": include_paths,
                "baseUrl": srcdir,
                "optimize": "none",
            }))
            process = subprocess.Popen([self.nodejs_path],
                                       stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE)
            stdout, stderr = process.communicate(script.encode('UTF-8'))
            stdout, stderr = str(stdout, 'UTF-8'), str(stderr, 'UTF-8')
            if process.returncode:
                self.log.error(stderr)
                try:
                    raise subprocess.CalledProcessError(
                        process.returncode, 'node.js',
                        output=stdout, stderr=stderr)
                except TypeError:
                    # the stderr kwarg is only available in python 3.5
                    pass
                raise subprocess.CalledProcessError(
                    process.returncode, 'node.js', output=stderr)
            if stderr:
                self.log.info("node.js output:\n" + stderr)
        return (rendered_requirejs + stdout +
                self.tpl.render('!require-config.js'))

    def _iter_paths(self):
        yield from self.tpl.iter_paths('application/javascript')
        if self.passthrough_extensions:
            extensions_regex = re.compile(
                r'\.(%s)$' %
                '|'.join(map(re.escape, self.passthrough_extensions)))
            yield from (path for path in self.tpl.iter_paths()
                        if extensions_regex.search(path))

    def _copy_files(self, folder, paths=None):
        if not paths:
            paths = list(self._iter_paths())
        include_paths = list()
        for path in paths:
            if path in ('!require.js', '!require-config.js'):
                continue
            header = ''
            file = os.path.join(folder, path)
            if self.tpl.mimetype(path) == 'application/javascript':
                header = \
                    '//--{sep}--//\n' \
                    '//  {path}  //\n' \
                    '//--{sep}--//\n' \
                    .format(path=path, sep=('-' * len(path)))
                content = self.tpl.render(path)
                base, ext = os.path.splitext(path)
                include_paths.append(base)
                file = os.path.join(folder, base + '.js')
            else:
                is_file, result = self.tpl.load(path)
                if is_file:
                    content = open(result).read()
                else:
                    content = result
            os.makedirs(os.path.dirname(file), exist_ok=True)
            open(file, 'w').write(header + content + '\n\n\n')
        return include_paths


class RequireJsLoader(Loader):

    def __init__(self, conf):
        self.conf = conf

    def iter_paths(self):
        yield from ['!require.js', '!require-config.js']

    def load(self, path):
        if path == '!require.js':
            file = os.path.join(os.path.dirname(__file__), 'require.js')
            return True, file
        elif path == '!require-config.js':
            conf = open(self.conf.config_file).read()
            return False, 'require.config(%s);\n' % conf.strip()
        raise TemplateNotFound(path)

    def is_valid(self, path):
        return path in self.iter_paths()


class RequirejsAssets(WebassetsProxy):

    def __init__(self, conf):
        self.conf = conf

    def iter_default_paths(self):
        yield from ['!require.js', '!require-config.js']
        if self.conf.webassets.tpl_autobundle:
            yield from self.conf._iter_paths()

    def validate_path(self, path):
        return path in ['!require.js', '!require-config.js'] or \
            path in self.conf._iter_paths()

    def hash(self, path):
        return None

    def render(self, path):
        try:
            if self.conf.tpl.mimetype(path) == 'application/javascript':
                return self.conf.tpl.render(path)
            is_file, result = self.conf.tpl.load(path)
            if is_file:
                result = open(result).read()
            return result
        except TemplateNotFound:
            from score.webassets import AssetNotFound
            raise AssetNotFound('requirejs', path)

    def mimetype(self, path):
        return self.conf.tpl.mimetype(path)

    def render_url(self, url):
        return '<script src="%s"></script>' % (url,)

    def create_bundle(self, paths):
        return self.conf.create_bundle(paths)

    def bundle_hash(self, paths):
        hashes = []
        for path in sorted(paths):
            hashes.append(self.conf.tpl.hash(path))
        return hashlib.sha256('\0'.join(hashes).encode('UTF-8')).hexdigest()

    def bundle_mimetype(self, paths):
        return 'application/javascript'
