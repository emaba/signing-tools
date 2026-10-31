#!/usr/bin/env python3
"""Create missing private Zsh/Bash settings without reading existing contents."""

import argparse
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-root", type=Path, default=Path.home() / ".config/signing-tools")
    args = parser.parse_args()
    settings = args.config_root / "settings.sh"
    args.config_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        descriptor = os.open(settings, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        print("Existing settings kept unchanged.")
    else:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(Path(__file__).with_name("settings.example.sh").read_bytes())
        print("Created private settings template. Configure its reference before signing.")
    print('Add this line once to ~/.zshrc (or ~/.bashrc for interactive Bash):')
    print('. "$HOME/.config/signing-tools/commands.sh"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
