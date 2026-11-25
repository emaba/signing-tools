#!/usr/bin/env python3
"""Retired source installer: the CLI application is now managed by Homebrew."""
import sys

def main(argv=None):
    arguments = sys.argv[1:] if argv is None else argv
    print("The standalone Fish installer has been retired. Homebrew now manages the CLI package.")
    print("See docs/installation.md for the formula and local distribution instructions.")
    print("After installation: signing-tools migrate --plan; signing-tools migrate")
    print("The existing Application Support installation is preserved for rollback.")
    return 0 if "--plan" in arguments or "--help" in arguments or "-h" in arguments else 2

if __name__ == "__main__":
    raise SystemExit(main())
