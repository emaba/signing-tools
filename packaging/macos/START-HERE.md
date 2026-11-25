# Signing tools for macOS - CLI installation

This release supplies `signpdf`, `signp7m`, and `signing-tools` as real executables.
Fish is not required. Homebrew manages the application and its dependencies;
configuration and migration backups stay private in your home directory.

## 1. Prepare the Mac

Use Apple Silicon with macOS 13 or later and a native Homebrew installation.
Install Homebrew from https://brew.sh/ if needed and follow its printed Next
steps for your normal shell. Do not change your login shell.

Install the 1Password desktop app if missing and its CLI:

```sh
brew install --cask 1password-cli
```

Keep a working existing installation; do not run a general brew upgrade or
cleanup. Install the correct issuer's PKCS#11 middleware (SafeDive for the
tested InfoCert JSafe/DS4 card) from the official issuer website. Connect the
reader and verify that the issuer's application recognises the card.
Do not apply historical useIFDCCID workarounds or reader firmware changes.

## 2. Install through the supplied local Homebrew tap

Unzip this folder, open Terminal and change to it. Adjust the path if necessary:

```sh
cd "$HOME/Downloads/signing-tools-macos-0.1.0"
shasum -a 256 -c SHA256SUMS.txt
python3.12 prepare-local-tap.py
brew tap emaba/signing-tools-local "$PWD/homebrew-tap"
brew install emaba/signing-tools-local/signing-tools
```

Python 3.12 is needed to run the preparation helper. If not already present:
`brew install python@3.12`. Homebrew installs the remaining declared dependencies.
The helper generates only a local Git tap and a formula with the supplied
source archive's checksum; it never accesses a PIN or modifies the shell.
The installed app runs independently of this folder. Keep the ZIP/folder for
reinstallation or use an accessible remote tap for future releases.

## 3. Choose migration or fresh setup

For an existing shell-function installation:

```sh
signing-tools migrate --plan
signing-tools migrate
```

The plan reports reference availability, never its value. Migration preserves
working settings, backs up retired legacy shell files and retains the old
application for rollback. Open a new Terminal afterwards.

For a new card setup, open 1Password and enable Settings > Developer > Integrate
with 1Password CLI. Privately enter the correct digital-signature PIN in a
concealed field for your card. This is not a Mac/account password, PUK, OTP,
or necessarily the CNS authentication PIN. Do not guess or send it to an assistant.
Use **Copy Secret Reference** on that exact field, then run:

```sh
signing-tools configure
```

The hidden prompt asks only for the `op://...` reference, never for the actual
PIN. Store no numeric PIN in configuration. References can contain private
vault/item metadata; do not paste the configuration into chats.

## 4. Check prerequisites and card profile

```sh
signing-tools --version
signing-tools doctor
```

Doctor reports status without resolving the PIN or logging in to the card.
The tested card defaults are token CNS, key/certificate ID 445334 and slot 0x2.
Slot IDs can vary by reader. Use a local `pkcs11-tool --module MODULE --list-slots`
check if necessary, without login/PIN flags; keep serials and the full listing
private. Use the hexadecimal slot ID, not its listing index. Confirm different
card objects with the issuer rather than guessing.

The private settings file is `~/.config/signing-tools/config.toml` (mode 600).
Use `signing-tools configure --slot 0xN` to change a supported option while
keeping an existing reference at the prompt. Use Vim for direct local editing.

## 5. First signing test - owner only

```sh
signing-tools sample sample.pdf
signpdf sample.pdf -o sample.pades.pdf
signp7m sample.pdf -o sample.cades.p7m
```

The PDF preview lets you choose a page and rectangle. Approve 1Password access
yourself when signing. Inspect the result and require the normal integrity checks
to pass. Stop on a wrong/blocked-PIN error; do not retry automatically.
The generated sample has three blank pages and no personal information.

Common commands:

```sh
signpdf document.pdf
signpdf document.pdf --page 2 --rect-mm 85,245,110,27 --appearance split
signpdf document.pdf --invisible
signpdf document.pdf --strict-pdf
signp7m document.pdf -o document.p7m
```

Compatible PDF parsing is the default. Strict structural issues are reported
in Terminal and an amber preview banner with a safe explanation. Signature
integrity/prior-signature checks still run. This is not full PDF/PDF-A, trust,
revocation, trusted-timestamp or legal-qualification validation.
The preview is loopback-only and closes before PIN access.

## Updates, removal and rollback

Use `brew upgrade signing-tools` when the tap provides a reviewed newer release.
Private configuration and backups are preserved. To restore an old migrated
shell setup before removing the new application:

```sh
signing-tools rollback --plan
signing-tools rollback
brew uninstall signing-tools
```

Open a new Terminal. Brew removal alone does not restore legacy functions.
SafeDive, 1Password and user configuration are not removed by this formula.
