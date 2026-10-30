# Permanent macOS installation

The existing `signp7m` Fish function is already a permanent installation.
This installer leaves that function and its private configuration untouched.
It installs `signpdf` independently of the checkout or Codex chat directory.

## Layout

```text
~/Library/Application Support/signp7m/
    current -> releases/<content-id>
    install.json
    releases/<content-id>/
        app/                 # Reviewed source, assets, licenses and guides
        venv/                # Private Python packages
    backups/                 # Only if an older signpdf function existed

~/.config/fish/functions/signpdf.fish
    -> ~/Library/Application Support/signp7m/current/app/signpdf.fish
```

There is one application directory and one Fish autoload link. No `sudo`,
global Python packages, PATH edits, shell startup configuration, login items,
background service, macOS reader preference or PIN file is added. The local
preview server runs only while choosing a signature position. Python 3.12 and
`uv` must already be installed; the installer does not install global tools.

The current Mac's Homebrew Python 3.12 is reused. The private environment's
packages are copied rather than symlinked to a dependency cache. The working
checkout, its development environment and download cache can be removed
without breaking the installed command. Keep Homebrew Python 3.12, SafeDive,
1Password CLI and the existing signing dependencies installed.

No reference is migrated or duplicated: the existing `signp7m` function remains
the legacy fallback for the 1Password reference. Explicit reference variables
still take precedence. The installer never opens that function or resolves a
credential. Normal signing retains the existing worker-only PIN delivery.

## Install

From a reviewed checkout, in Fish:

```fish
python3.12 install_signpdf.py --plan
python3.12 install_signpdf.py
```

The plan prints only the target paths. Installation prepares a complete
release and verifies startup/dependency imports before switching the current
link. Existing releases remain available. An existing unrelated `signpdf`
Fish file is backed up inside the application directory before replacement.
Dependency downloads use a temporary cache inside the application directory,
removed when installation ends. `--cache-dir PATH --offline` can reuse a
previously populated cache without contacting a package index.

Open a new terminal window after installation or update, then:

```fish
signpdf --help
signpdf document.pdf --location Genova
signp7m document.pdf
```

The installed Fish command discovers its release and Python environment.
It does not need `SIGNPDF_HOME` or `SIGNPDF_PYTHON`. Those variables remain
supported for development and override discovery; remove old session-specific
values or open a fresh terminal if they still point to a Codex checkout.

Do not move the application directory or individual virtual environments:
Python environments can contain absolute paths. To choose another location,
install there with `--prefix PATH`; the autoload link finds that release.

## Update and rollback

Review/pull the desired repository revision, then run the installer from that
checkout again. Close active signing/placement sessions before updating.
An update builds a new release with its own environment before activation.
Failures before activation leave the previous release usable. The previous
release ID and current ID are recorded in `install.json` without credentials.
Installing the same source version again is a no-op after source-integrity
checks. Retained releases consume disk space; they are deliberately kept for
rollback rather than removed automatically.

To roll back, inspect the recorded previous release ID and change the `current`
symlink to that existing `releases/<content-id>` directory, then open a new
terminal. Do not copy or move a virtual environment between release paths.

## Uninstall

From any directory:

```fish
python3.12 "$HOME/Library/Application Support/signp7m/current/app/install_signpdf.py" --uninstall
```

The uninstaller removes only its managed Fish link, restores the backed-up
older `signpdf` function if one existed, and moves the whole application
directory to the user's Trash. It refuses to overwrite a Fish link that was
changed after installation. `signp7m` and its configuration remain in place.
Open a new terminal to discard any already loaded `signpdf` definition.
The application folder can be recovered from Trash until Trash is emptied.

## Verification

The installer checks command startup and dependency imports without accessing
the card or 1Password. A fresh Fish shell should discover `signpdf` through the
single link. A successful installation is not a real signing acceptance test;
sign a disposable PDF locally to validate the reader and authorization flow.

On October 30, 2026, the installer was exercised in temporary directories,
including paths with spaces. Transaction tests cover dependency/activation
failure, preservation of the existing CAdES function, same-version reinstall,
restoring an earlier PDF function on uninstall, and refusal to overwrite an
owner-modified link. A separate real dependency installation passed startup
through Fish autoload without `SIGNPDF_HOME` or `SIGNPDF_PYTHON`. No card or
1Password operation was invoked by these installation checks.
