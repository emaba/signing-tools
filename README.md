# Signing tools for macOS

A shell-independent Python CLI for local smart-card signing:

- `signpdf`: PAdES signatures inside PDF files, with graphical placement by default.
- `signp7m`: attached binary DER CAdES signatures.
- `signing-tools`: configuration, prerequisite checks, migration and rollback.

The private key stays on the card. 1Password supplies the PIN only to the
signing child process. Configuration stores an `op://` reference, never a PIN.

## Installation and migration

Homebrew owns the application, its private Python environment and executable
links. No Fish installation, shell functions, shell startup edits, global pip
packages or application-specific background service are needed.

The initial tap supports **Apple Silicon, macOS 13 or later, Python 3.12**.
The pinned cryptography release has no upstream Intel macOS wheel; Intel
support needs a separately verified dependency/build path.

Use the supplied local distribution and its local-tap preparation helper.
It installs through Homebrew without requiring GitHub access; see
[installation and migration](docs/installation.md). The formula is maintained
on `codex/signpdf-pades`; the repository's default `main` branch still contains
the historical Fish version, so it is not yet a directly installable remote tap.

Existing installation:

```sh
signing-tools migrate --plan
signing-tools migrate
```

Migration extracts only literal reference/settings identifiers, never runs
Fish or contacts 1Password, preserves existing unified settings, and backs up
retired shell files. The old Application Support installation stays available
for rollback. Open a new Terminal afterwards.

Fresh installation:

```sh
signing-tools configure
signing-tools doctor
```

Enter the PIN **reference** privately at the prompt. Install the correct issuer
middleware and enable 1Password CLI integration before the first signing test.
SafeDive and 1Password are external prerequisites, not redistributed here.

## Use

```sh
signpdf document.pdf
signpdf document.pdf --page 2 --rect-mm 85,245,110,27 --appearance split
signpdf document.pdf --invisible
signpdf document.pdf --strict-pdf
signp7m document.pdf -o document.p7m
signing-tools --version
signing-tools doctor
```

Compatible PDF syntax parsing is the default. Recoverable structural issues
produce a Terminal warning and an amber preview banner with a safe explanation.
The original PDF bytes are preserved incrementally, and cryptographic integrity,
prior signatures, permitted changes and PAdES attributes are still checked.
The temporary preview listens only on `127.0.0.1` and closes before PIN access.

Trust chains, revocation, trusted timestamps and legal/profile qualification
are not validated by the local success messages. The graphical signature name
is typeset from the certificate, not a handwritten authentication mechanism.

## Configuration and updates

One private file: `~/.config/signing-tools/config.toml` (mode 600).
`signing-tools config-path` shows only its location. Reference-only environment
settings can explicitly override configuration without altering the parent shell.
See [configuration](docs/configuration.md) and [security notes](SECURITY.md).

```sh
brew upgrade signing-tools
brew uninstall signing-tools
```

Homebrew upgrades/removal preserve private configuration and migration backups.
To restore the previous shell setup, run `signing-tools rollback --plan` and
`signing-tools rollback` before uninstalling the new package.

## Development and distribution

The standard `pyproject.toml` package includes all preview assets and the
redistributable cursive font. [Build and Homebrew instructions](docs/distribution.md)
explain versioned releases, pinned/checksummed dependencies and local tap testing.
[The PAdES guide](docs/signpdf.md) documents placement and signature checks.
The [legacy Fish reference](docs/legacy-fish.md) is historical documentation;
new installations use the installed CLI executables.
