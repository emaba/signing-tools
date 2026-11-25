"""The retired bootstrap gives migration guidance without touching an installation."""
from contextlib import redirect_stdout
from io import StringIO
import unittest
import install_signpdf

class RetiredInstallerTests(unittest.TestCase):
    def test_retired_installer_reports_homebrew_route(self):
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(install_signpdf.main([]), 2)
            self.assertEqual(install_signpdf.main(["--plan"]), 0)
        self.assertIn("Homebrew", output.getvalue())
        self.assertIn("signing-tools migrate", output.getvalue())
