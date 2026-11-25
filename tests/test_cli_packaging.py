"""Checked Homebrew resources and standard Python package entry points."""

import json
from pathlib import Path
import tomllib
import unittest

from scripts.generate_homebrew_formula import generate

ROOT = Path(__file__).resolve().parents[1]


class FormulaTests(unittest.TestCase):
    def setUp(self):
        self.resources = json.loads((ROOT / 'homebrew/resources.json').read_text())

    def test_all_pinned_runtime_packages_and_backend_have_checked_resources(self):
        expected = {line.lower().replace('_', '-') for line in
                    (ROOT / 'requirements-runtime.lock').read_text().splitlines()
                    if line and not line.startswith('#')}
        expected.add('setuptools==84.2.1')
        actual = set()
        for resource in self.resources['resources']:
            actual.add(resource['name'].lower().replace('_', '-') + '==' + resource['version'])
            wheel = resource['wheels']['arm64']
            self.assertTrue(wheel['url'].startswith('https://files.pythonhosted.org/'))
            self.assertRegex(wheel['sha256'], r'^[0-9a-f]{64}$')
        self.assertEqual(expected, actual)

    def test_formula_has_private_runtime_and_only_real_executable_links(self):
        text = generate('a' * 40, 'v0.1.0', self.resources)
        self.assertIn('revision: "' + 'a' * 40 + '"', text)
        self.assertIn('depends_on arch: :arm64', text)
        self.assertIn('bin.install_symlink libexec/"bin/signpdf"', text)
        self.assertIn('"--no-index", "--no-deps"', text)
        self.assertIn('"--offline", "--no-build-isolation"', text)
        self.assertNotIn('post_install', text)
        self.assertNotIn('config.toml', text)
        self.assertNotIn('fish', text)

    def test_immutable_source_revision_and_version_are_required(self):
        for revision, tag in [('main', 'v0.1.0'), ('a' * 40, 'latest'), (None, 'v0.1.0')]:
            with self.assertRaises(ValueError):
                generate(revision, tag, self.resources)

    def test_package_exposes_three_console_scripts_and_assets(self):
        package = tomllib.loads((ROOT / 'pyproject.toml').read_text())
        self.assertEqual(set(package['project']['scripts']), {'signpdf', 'signp7m', 'signing-tools'})
        for target in package['project']['scripts'].values():
            self.assertTrue(target.startswith('signing_tools.cli:'))
        from importlib.resources import files
        for asset in ('fonts/KaushanScript-Regular.ttf', 'fonts/OFL-KaushanScript.txt',
                      'placement/index.html', 'placement/app.js', 'placement/style.css'):
            self.assertTrue(files('signing_tools').joinpath('assets', asset).is_file(), asset)
