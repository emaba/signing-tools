"""Formula resources and a portable local tap remain independent of user setup."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
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

    def test_source_revision_and_archive_checksum_are_required(self):
        for revision, tag, extras in [('main', 'v0.1.0', {}), ('a' * 40, 'latest', {}),
                                      (None, 'v0.1.0', {'archive': 'https://example.invalid/source.tar.gz'})]:
            with self.assertRaises(ValueError):
                generate(revision, tag, self.resources, **extras)

    def test_package_exposes_three_console_scripts_and_assets(self):
        package = tomllib.loads((ROOT / 'pyproject.toml').read_text())
        self.assertEqual(set(package['project']['scripts']), {'signpdf', 'signp7m', 'signing-tools'})
        for target in package['project']['scripts'].values():
            self.assertTrue(target.startswith('signing_tools.cli:'))
        self.assertIn('assets/placement/*', package['tool']['setuptools']['package-data']['signing_tools'])


class LocalTapTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='signing local tap ')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for original, name in [('scripts/prepare_local_tap.py', 'prepare-local-tap.py'),
                               ('scripts/generate_homebrew_formula.py', 'formula_builder.py'),
                               ('homebrew/resources.json', 'resources.json')]:
            shutil.copyfile(ROOT / original, self.root / name)
        self.archive = self.root / 'signing_tools-0.1.0.tar.gz'
        self.archive.write_bytes(b'SYNTHETIC SOURCE ARCHIVE FOR TAP GENERATION ONLY')
        self.digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        (self.root / 'SHA256SUMS.txt').write_text(self.digest + '  ' + self.archive.name + '\n')

    def run_helper(self):
        return subprocess.run([sys.executable, str(self.root / 'prepare-local-tap.py')],
                              cwd=self.root, capture_output=True, text=True)

    def test_helper_creates_pinned_git_tap_and_is_idempotent(self):
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        formula = self.root / 'homebrew-tap/Formula/signing-tools.rb'
        text = formula.read_text()
        self.assertIn(self.archive.resolve().as_uri(), text)
        self.assertIn(self.digest, text)
        self.assertTrue((formula.parents[1] / '.git').is_dir())
        self.assertEqual(self.run_helper().returncode, 0)
        self.assertEqual(formula.read_text(), text)

    def test_helper_rejects_archive_changes_before_creating_a_tap(self):
        self.archive.write_bytes(b'SYNTHETIC CHANGED ARCHIVE')
        self.assertNotEqual(self.run_helper().returncode, 0)
        self.assertFalse((self.root / 'homebrew-tap').exists())

    def test_helper_preserves_an_existing_changed_formula(self):
        self.assertEqual(self.run_helper().returncode, 0)
        formula = self.root / 'homebrew-tap/Formula/signing-tools.rb'
        formula.write_text('SYNTHETIC OWNER EDIT\n')
        self.assertNotEqual(self.run_helper().returncode, 0)
        self.assertEqual(formula.read_text(), 'SYNTHETIC OWNER EDIT\n')
