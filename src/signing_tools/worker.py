"""Private entry point for op run; no shell or configuration discovery."""

import logging
import sys

from .signpdf import main as sign


def main():
    logging.disable(logging.CRITICAL)
    return sign(["--_sign-worker", *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
