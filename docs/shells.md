# Use Zsh or Bash without Fish

Fish is optional. The fresh-Mac package uses Zsh, macOS's default shell.
`signpdf.py` is shared by all shell integrations. `signp7m.py` provides the
CAdES command for Zsh/Bash using the same OpenSSL, SafeDive and 1Password
pipeline as the original Fish function; it never starts a web server.

From the extracted package in Zsh:

```sh
python3.12 source/install_signpdf.py --shell zsh --plan
python3.12 source/install_signpdf.py --shell zsh
python3.12 install-shell-extras.py
```

The installer creates a private release/environment and one managed link:
`~/.config/signing-tools/commands.sh`. The helper creates only missing
`~/.config/signing-tools/settings.sh`, mode 600, and never reads or replaces
existing settings. Put the copied 1Password PIN **reference** in that file.
Neither installer modifies shell startup files or your shell's PATH.

Add this single line once to `${ZDOTDIR:-$HOME}/.zshrc`, using Vim:

```sh
. "$HOME/.config/signing-tools/commands.sh"
```

Load it in the current terminal with the same command. `signpdf`, `signp7m`
and `signing_tools_check` are then shell functions. Open a new Terminal after
updates. The settings are loaded inside each command's subshell, so the
OpenSSL selection and reference do not alter the parent shell environment.
No PIN is resolved by loading the shell functions or running the checker.
Commands containing paths with spaces must retain their quotation marks.

Bash uses `--shell bash` with the same integration; source the line from the
startup file used by your Bash session (`~/.bash_profile` for macOS login
shells, or `~/.bashrc` for non-login interactive shells). Do not change the
login shell. Other POSIX shells can source the same command file.

For an explicit custom installation prefix, export `SIGNING_TOOLS_ROOT` to
that root before loading commands. `SIGNING_TOOLS_CONFIG` can override the
settings-file path. These are paths, never credential values.

## Existing Fish users

The default installer mode remains `--shell fish`; it installs the PDF Fish
link and preserves the existing P7M function and its configuration. The
original `install-fish-extras.fish` helper and `settings.example.fish` remain
available for a fresh Fish setup. Do not mix both setup procedures or replace
an existing working PIN-reference configuration with a placeholder.

An existing managed root cannot switch integrations silently: it refuses a
different entry-link directory. Review a separate-prefix installation or a
backup/removal first if migration is needed. No migration is required just
to keep using an existing Fish setup.

## Update and remove

Repeat `python3.12 source/install_signpdf.py --shell zsh` from a newer bundle
(use `--shell bash` for Bash). Previous releases are retained for rollback.
The shared settings and startup line are unchanged.

To remove the managed application and entry link:

```sh
python3.12 "$HOME/Library/Application Support/signp7m/current/app/install_signpdf.py" --uninstall
```

The old release directory goes to Trash. Remove the startup source line with
Vim and remove the private settings only if no longer needed. The uninstaller
preserves these manually maintained files and all unrelated Fish functions.

## Validation limits

The Python CAdES port is tested with substituted commands and a generated
software certificate/key through real OpenSSL CMS verification. These tests
use no smart card or 1Password. The original Fish CAdES and Python PAdES
flows have owner-reported hardware successes; the new Zsh/Bash CAdES entry
still requires the recipient's first sample signing test on their own card.
No chain trust, revocation or trusted timestamp is established by local checks.
