# Install and migrate the Homebrew-managed CLI

## Layout and ownership

The formula installs a private Python environment in its `libexec` and three
executables in its `bin`. Homebrew exposes those commands through its normal
prefix links (usually `/opt/homebrew/bin` on Apple Silicon). The application
never creates a parallel updater or changes a shell startup file or PATH.

Private user data is separate: `~/.config/signing-tools/config.toml`, migration
records and backups. Package upgrades/removal preserve these files.

## Dependencies

Use a native Apple Silicon Homebrew installation. The initial formula targets
macOS 13+, Python 3.12, and the exact previously tested Python runtime versions.
It installs Python, OpenSSL, libp11 and OpenSC as formula dependencies. Install
1Password desktop/CLI and the issuer's middleware separately if missing:

```sh
brew install --cask 1password-cli
```

Keep an existing working 1Password installation. Install the matching SafeDive
middleware from the issuer. Do not change reader firmware or useIFDCCID settings.
Enable **Settings > Developer > Integrate with 1Password CLI** in 1Password.
Use your card's digital-signature PIN, not a CNS authentication PIN, PUK, Mac
password or account password. Only the owner enters that PIN in a concealed
1Password field and copies that field's secret reference. Never use `op read`
or reveal the PIN in a chat or diagnostic output.

## Private remote tap (future promotion)

The formula is maintained on `codex/signpdf-pades`. The default `main` branch
still contains the historical Fish tool, so use the local distribution below
for current installations. After the reviewed formula is promoted to a tap's
default branch, its remote installation can use:

```sh
brew tap emaba/signp7m https://github.com/emaba/signp7m.git
brew install emaba/signp7m/signing-tools
```

The repository remains private and requires Git read access. Use an existing
credential/SSH agent; never export credentials into a formula. Source tags pin
an exact revision and all wheel resources have SHA-256 checksums. This is a
third-party tap, not a Homebrew Core submission.

## Local package without GitHub access

A distribution folder supplies a versioned source archive, a wheel, the resource
manifest and `prepare-local-tap.py`. From that folder:

```sh
python3.12 prepare-local-tap.py
brew tap emaba/signing-tools-local "$PWD/homebrew-tap"
brew install emaba/signing-tools-local/signing-tools
```

The helper creates only a local Git tap and a formula pointing to the supplied
archive with its SHA-256. It performs no package installation, shell change,
credential lookup or signing. Keep the distribution for rebuilding/reinstalling;
the installed commands do not depend on its location at runtime.

## Migrate this existing installation

First install the CLI package. Then:

```sh
signing-tools migrate --plan
signing-tools migrate
```

The plan reports paths and whether a reference exists, never the reference
value. Migration checks known legacy command paths, statically extracts only
literal settings, creates private TOML configuration if absent, and moves the
old Fish functions/settings to private backups. Existing TOML is preserved.
A legacy Zsh/Bash source link becomes a comment-only bridge so an old source
line will not fail or redefine commands. Remove that obsolete line later if desired.
The old `~/Library/Application Support/signp7m` releases are kept for rollback.

Open a **new Terminal** to discard functions already loaded in the old shell.
Confirm that `command -v signpdf`, `command -v signp7m`, and
`command -v signing-tools` resolve to Homebrew executables. Run:

```sh
signing-tools --version
signing-tools doctor
```

The checks do not resolve a PIN or log in to the card. A first actual sample
signature remains an owner-run hardware/1Password acceptance check.

## Fresh configuration

```sh
signing-tools configure
signing-tools doctor
signing-tools sample sample.pdf
signpdf sample.pdf -o sample.pades.pdf
signp7m sample.pdf -o sample.cades.p7m
```

The configuration prompt asks for an `op://...` reference and hides its entry;
it never asks for the actual PIN. Inspect the generated PDF appearance and
normal verification results. Stop on any PIN or locked-card error; never retry
automatically or guess an identifier. Card defaults CNS/445334 and slot 0x2
are profile/reader dependent. `configure --module PATH --slot 0xN` and the TOML
file allow issuer-supported changes without shell configuration.

## Updates, removal and rollback

Use `brew upgrade signing-tools`. Keep configuration/backups outside the Cellar.
To return to the old shell setup before removing the new package:

```sh
signing-tools rollback --plan
signing-tools rollback
brew uninstall signing-tools
```

Rollback refuses changed destination files or backups, restores the exact old
functions and keeps the unified configuration as user data. Open a new Terminal.
Brew removal alone does not restore legacy functions or delete user settings.
Do not remove old Application Support releases until rollback is no longer needed.
