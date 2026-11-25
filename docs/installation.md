# Install and migrate the Homebrew-managed CLI

## Layout and ownership

The formula installs a private Python environment in its `libexec` and three
executables in its `bin`. Homebrew exposes those commands through its normal
prefix links (usually `/opt/homebrew/bin` on Apple Silicon). The application
never creates a parallel updater or changes a shell startup file or PATH.

Private user data is separate: `~/.config/signing-tools/config.toml`, migration
records and backups. Package upgrades/removal preserve these files.

## Dependencies

For a fresh setup, follow [the complete quick start](quick-start.md), including
Command Line Tools, Homebrew, SafeDive, 1Password, card settings and first tests.

Use a native Apple Silicon Homebrew installation. Current Homebrew's supported
installation requires macOS 15+; the formula itself declares macOS 13+ and Python
3.12 with exact previously tested Python runtime versions. Its lower OS bound
does not guarantee support by current Homebrew or third-party middleware.
It installs Python, OpenSSL, libp11 and OpenSC as formula dependencies. Install
1Password desktop/CLI and the issuer's middleware separately if missing:

```sh
brew install --cask 1password-cli
```

Keep an existing working 1Password installation. For InfoCert JSafe, follow
[the SafeDive download and installation steps](quick-start.md#3-install-safedive-and-connect-the-card)
and verify the expected library. Other cards require their issuer's matching
middleware and profile. Do not change reader firmware or useIFDCCID settings.
Enable **Settings > Developer > Integrate with 1Password CLI** in 1Password.
Use your card's digital-signature PIN, not a CNS authentication PIN, PUK, Mac
password or account password. Only the owner enters that PIN in a concealed
1Password field and copies that field's secret reference. Never use `op read`
or reveal the PIN in a chat or diagnostic output.

## Install from the remote Homebrew tap

The public repository requires no GitHub credentials. Never put a token,
password or private key into a formula or signing configuration.

```sh
brew tap emaba/signing-tools https://github.com/emaba/signing-tools.git
brew install emaba/signing-tools/signing-tools
```

The formula on `main` pins a version tag and exact Git revision. All upstream
wheel resources have SHA-256 checksums and runtime installation/builds use
network resolution disabled. This is a third-party tap, not Homebrew Core.
No ZIP or application-specific installer is needed.

## Move an existing installation to the renamed tap

The repository and tap are now named `signing-tools`. Existing installations
from the former `emaba/signp7m` tap can move to the new tap through Homebrew:

```sh
brew tap emaba/signing-tools https://github.com/emaba/signing-tools.git
brew reinstall emaba/signing-tools/signing-tools
brew untap emaba/signp7m
```

Run the commands in order and stop if any fails. The reinstall preserves private
configuration and migration backups outside the Cellar. Remove the old tap only
after the new installation succeeds. Installations from the historical local
validation tap can remove `emaba/signing-tools-local` afterwards instead.

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

The default [configuration wizard](configuration.md#guided-setup) asks for an
`op://...` reference privately, then selects the module, card and public signing
certificate without login. It confirms the private key ID, derives the P7M URI
and asks before saving the complete profile. It never asks for the actual PIN.
Use `configure --manual` with issuer-confirmed identifiers when discovery is not
available without authentication. Inspect the generated PDF appearance and
normal verification results. Stop on any PIN or locked-card error; never retry
automatically or guess an identifier. Direct options such as
`configure --module PATH --slot 0xN` still update selected fields without
discovery; changing token/key identifiers regenerates the matching URI.

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

## Clean up after migration

After accepting the Homebrew CLI, the previous Application Support installation,
old bundles/checkouts and temporary test environments are no longer required.
Move them to Trash if you want a recoverable cleanup. Preserve your signed PDFs
and `~/.config/signing-tools/config.toml`.

If you retire the old application, also retire its matching `backups` directory
and `migration.json` record from `~/.config/signing-tools`; otherwise a rollback
record can outlive its target application. Restoring the old shell setup later
requires restoring all those retired files first. Fresh Homebrew operation needs
only the current configuration, not a migration record.

Use `brew cleanup signing-tools` for package caches; do not delete Cellar files
or shared dependencies manually. `brew developer` shows the current mode and
`brew developer off` disables development mode when it is enabled.
