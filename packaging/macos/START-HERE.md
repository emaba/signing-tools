# Signing tools for macOS

## A practical installation guide

Guide reviewed 5 November 2026. See `PACKAGE-INFO.json` for the bundle build date and exact source revision.

This package installs two commands: `signp7m` produces a signed `.p7m` file;
`signpdf` produces a signed PDF and normally opens a graphical placement window.
You can follow this guide yourself or give this folder and `FOR-CLAUDE.md` to
Claude. This guide uses Zsh, the macOS default shell: **Fish is not required**.
The Markdown and PDF versions contain the same installation steps.

### Before you start

- Use a recent macOS version supported by Homebrew, an internet connection,
  a working smart-card reader, your own signing card and a 1Password account.
- This tool was tested with an InfoCert JSafe/DS4 signing card, SafeDive and
  native Apple Silicon software. Another card, middleware or Intel Mac needs
  its own compatibility check; the defaults are not universal.
- You must know the correct **digital-signature PIN for your own card**.
  Only you enter it in the 1Password desktop app. Do not send it to Claude.
- The ZIP contains all tool source, fonts, helpers and an unsigned sample.
  It is not an offline installer: Homebrew and Python download dependencies.
  SafeDive and 1Password are obtained separately from their official sources.

### 1. Install the dependencies

Open Terminal. Check Homebrew:

```sh
brew --version
```

If the command is not found, install Homebrew from https://brew.sh/ and follow
the installer's printed **Next steps** for your shell. Enter any Mac administrator
password privately. Do not paste it into a chat. Then run:

```sh
brew install python@3.12 uv openssl@4 libp11 opensc
brew install --cask 1password-cli
```

Install the desktop app only if 1Password is not already installed:

```sh
brew install --cask 1password
```

Keep a working existing 1Password installation. Do not run a general
`brew upgrade`, uninstall working packages, or change the login shell.
The OpenSSL 4 selection matches the libp11/OpenSC formulae checked on this
guide's date. A provider-loading check later catches a future mismatch.

### 2. Open the package folder in your normal Terminal

Unzip the package in Downloads, then:

```sh
cd "$HOME/Downloads/signing-tools-macos"
```

Adjust the path if Finder used another folder name. Keep using Zsh; do not
install Fish or change your login shell. Bash is also supported; see the
included source/docs/shells.md for its startup-file differences.

<!-- pagebreak -->

## Prepare the card and 1Password

### 3. Install the correct SafeDive middleware

Go to the official InfoCert driver page:
https://www.infocert.it/firma-digitale2/driver-installazione

Choose the macOS SafeDive/PKCS#11 download for your card model. Do not assume
the newest driver fits every card. Follow the vendor installer and any restart
instructions. SafeDive is not included in this ZIP or installed by Homebrew.

The default library expected by the tools is:

```text
/Applications/SafeDive/STCryptoTokenKit.app/Contents/PlugIns/
STToken.appex/Contents/Frameworks/libstPKCS11.dylib
```

The two displayed lines form one continuous path. Connect only the reader
you intend to use, insert the card, and check that the issuer's application
recognises it. Do not change macOS smart-card preferences or reader firmware.
In particular, the historical `useIFDCCID` workaround is not an installation step.

### 4. Store the correct PIN in 1Password

**Do this part yourself, in the 1Password desktop app.**

1. Open and unlock 1Password, and select the correct account.
2. Open **Settings > Developer** and enable **Integrate with 1Password CLI**.
   Touch ID may be enabled if available.
3. Create an item, for example **Smart card - signing PIN**. Add a concealed
   password field named **Signing PIN**.
4. Put your card's actual digital-signature PIN in that concealed field and
   save the item. Use the issuer's instructions to identify the signing PIN;
   it is not your 1Password account password, Mac password, PUK or an OTP.
   A CNS/authentication PIN may be different. Do not guess.
5. Use the menu beside that exact field and choose **Copy Secret Reference**.
   Copy the reference, not the field's secret value.

A reference looks like this example:

```text
op://VAULT_ID/ITEM_ID/FIELD_ID
```

An optional section and names with spaces are supported. Keep quotation marks
when inserting it in the private settings file. Prefer the reference copied by the
app; do not invent IDs. References are identifiers rather than PINs, but their
vault/item names can still be private metadata.

**Never use `op read`, reveal the field in a chat, or ask Claude to verify the
PIN by printing it.** You will authorize 1Password access when you actually
sign the sample. The tool cannot determine the correct PIN on your behalf.

<!-- pagebreak -->

## Install the commands

### 5. Install both commands without Fish

From the extracted package folder, in your normal Zsh Terminal:

```sh
python3.12 source/install_signpdf.py --shell zsh --plan
python3.12 source/install_signpdf.py --shell zsh
python3.12 install-shell-extras.py
```

The plan shows the target paths. Installation downloads Python packages into
a private environment and installs one managed command-file link. The helper
creates only missing settings; it never reads or replaces an existing file.
Keep any working setup. Existing Fish installations should instead follow
source/docs/installation.md; do not mix the two installation procedures.

### What gets installed

```text
~/Library/Application Support/signp7m/
    current -> releases/<version>
    releases/<version>/app/      Tool source and assets
    releases/<version>/venv/     Private Python packages
    install.json                Installation metadata

~/.config/signing-tools/commands.sh    Managed shell-entry link
~/.config/signing-tools/settings.sh    Private reference/settings (mode 600)
```

No global Python packages, login items or permanent background services are
added. The selected Homebrew OpenSSL is used only inside the signing/check
commands. Your normal shell PATH is unchanged. The extracted Downloads folder
is not needed at runtime. Do not move installed releases or their environments.

### 6. Configure the reference and enable the commands

Open the private settings file in Vim:

```sh
vim "$HOME/.config/signing-tools/settings.sh"
```

Press `i`. Replace only `op://VAULT_ID/ITEM_ID/FIELD_ID` with the reference
copied in step 4, keeping its surrounding quotes. Never put the numeric PIN
here. Keep the OpenSSL-selection block. Press Escape, then type `:wq` and Enter.

Open your Zsh startup file (respects a custom ZDOTDIR):

```sh
vim "${ZDOTDIR:-$HOME}/.zshrc"
```

Add the following line **once**, at the end, then save. The installer does not
edit this file. Preserve any existing contents; an assistant should back it up
before editing. New Terminal windows will load the commands automatically.

```sh
. "$HOME/.config/signing-tools/commands.sh"
```

Run that same source line in the current Terminal, or open a new window.

<!-- pagebreak -->

## Check the card profile before signing

### 7. Select the slot containing your card

The default profile is token label `CNS`, certificate/private-key ID `445334`
(the DS4 object ID), and a P7M certificate-reading slot of `0x2`.
The slot can differ on another reader or Mac. Run this local, no-login check:

```sh
signing_app='/Applications/SafeDive/STCryptoTokenKit.app'
module="$signing_app/Contents/PlugIns/STToken.appex/Contents/Frameworks/libstPKCS11.dylib"
pkcs11-tool --module "$module" --list-slots
```

Find the slot that contains your card, not an empty virtual reader. Use the
slot's **hexadecimal ID in parentheses**, not its listing index. In the private
configuration file, uncomment and adjust the `SIGNP7M_SLOT` line if needed.
For example, use `0x1` only if that is the ID shown for your card.

Do not paste the full slot listing into a chat: it can contain serial numbers.
This command does not ask for the PIN. If your token label or signing objects
do not match CNS/DS4, stop and confirm the correct profile with the issuer.
Do not guess key IDs, list private-key material, or try different PINs.

### 8. Load the settings and run checks without a PIN

On a fresh setup:

```sh
. "$HOME/.config/signing-tools/commands.sh"
signing_tools_check
signpdf --help
signp7m --help
```

If you already had a working configuration and no new file was created,
keep its normal startup procedure. The supplied checker expects the shared
reference variable used by this fresh-install guide.

`signing_tools_check` reports only PASS/FAIL status for tools, reference format,
the middleware file and OpenSSL provider loading. It does not read the PIN,
contact 1Password, log in to the card or print the reference. PASS means these
local prerequisites work; it does not prove the PIN or signing certificate.

Stop if any required check fails. OpenSSL must be Homebrew OpenSSL and the
libp11 provider must load into it. Keep the process, middleware and libraries
on the same architecture; do not mix Rosetta/Intel and native ARM software.
Keep Homebrew Python 3.12 installed even if another Python version is present.

The commands reload settings inside their own subshell on every invocation.
You do not need to export the reference in your terminal. An existing working
Fish setup can remain unchanged on another Mac; this guide does not require it.

<!-- pagebreak -->

## First signature and daily use

### 9. Sign only the supplied sample first

Keep your card inserted. From the extracted folder:

```sh
signpdf sample.pdf --location Genova -o sample.pades.pdf
```

Replace `Genova` with your own declared place, or omit `--location`. In the
local browser preview choose a page, click to place a box or drag to draw it,
then move/resize it. The side panel accepts millimetres. Select **Use this
position**, return to Terminal, and approve 1Password access yourself.
The real name comes from your certificate; the preview uses placeholder text.

The command should report cryptographic integrity and permitted-change checks
as PASSED. Open the resulting PDF and check that the name, text and position
are legible. The next test exercises CAdES and its slot selection:

```sh
signp7m -o sample.cades.p7m sample.pdf
```

Require cryptographic verification, document integrity and the CAdES attribute
checks to pass. An incorrect-PIN or blocked-card error means **stop**. Do not
retry automatically. An assistant may help with setup, but should not approve
1Password prompts or sign real documents on your behalf.

### Common commands

```sh
# Graphical placement, default appearance
signpdf document.pdf --location Genova

# Explicit page, left/top/width/height in millimetres
signpdf document.pdf --page 2 --rect-mm 85,245,110,27 \
    --appearance split -o document.visible.pdf

# No visible box
signpdf document.pdf --invisible -o document.invisible.pdf

# Optional: reject recoverable PDF syntax/xref issues
signpdf document.pdf --strict-pdf

# Add another signature while preserving an earlier one
signpdf document.visible.pdf --invisible -o document.twice.pdf

# Produce a P7M file
signp7m document.pdf
```

`--page` starts at 1 and accepts `last`. Rectangle offsets are measured from
the displayed page's top-left corner. Existing output files need overwrite
confirmation. Cancel in the browser or press Ctrl+C to stop placement; closing
the tab alone leaves the terminal waiting until the placement timeout.

These tools check cryptographic integrity and selected structural properties.
PDF reading tolerates recoverable syntax issues by default; signature and
permitted-change checks still run. Use `--strict-pdf` for strict PDF parsing.
They do not establish certificate trust, revocation or a trusted timestamp.
Use the recipient's required verifier for acceptance. A success message is
not a general certificate-trust or legal-qualification assessment.

<!-- pagebreak -->

## Problems, updates and removal

### If something does not work

- **Command not found:** load the source line from step 6 or open a new Zsh
  Terminal. Check the startup line and that the installer completed.
- **Reference/configuration error:** copy the reference from the correct
  concealed 1Password field and reload the configuration. Never print the PIN.
- **1Password cannot connect:** open/unlock the desktop app, confirm CLI
  integration is enabled, and authorize from your own Terminal session.
- **Middleware/token error:** confirm the issuer's driver, native architecture,
  inserted card, slot ID and CNS/DS4 profile. Do not apply historical driver
  workarounds automatically.
- **OpenSSL provider error:** check the selected OpenSSL and the libp11 build.
  Do not point OpenSSL 3 at an OpenSSL 4 provider or disable verification.
- **Wrong/blocked PIN:** stop. Use the issuer's documented recovery/support
  process; do not guess the PUK or repeat signing attempts.

### Update

Obtain a reviewed newer package and rerun its installer with `--shell zsh`.
It updates both commands together and retains the previous release. Open a
new Terminal. Do not replace working private settings with the example template.

### Remove a fresh installation

To remove the managed application:

```sh
python3.12 "$HOME/Library/Application Support/signp7m/current/app/install_signpdf.py" --uninstall
```

This removes the managed command link and moves the application folder to
Trash. Remove the source line from your Zsh startup file with Vim. Remove
the private settings only when no longer needed. SafeDive, Homebrew, 1Password
and unrelated Fish functions are preserved. Open a new Terminal afterwards.

### Official references and what was tested

- Homebrew installation: https://brew.sh/
- OpenSSL formula: https://formulae.brew.sh/formula/openssl@4
- libp11 formula: https://formulae.brew.sh/formula/libp11
- 1Password CLI: https://www.1password.dev/cli/get-started
- Desktop integration: https://www.1password.dev/cli/app-integration
- Copying secret references: https://www.1password.dev/cli/secret-reference-syntax
- InfoCert drivers: https://www.infocert.it/firma-digitale2/driver-installazione

Tests cover both shell integrations, CAdES failure handling, generated-key
OpenSSL signing, PDF integrity and package reproducibility. The Zsh/Bash
CAdES command still needs your first hardware sample test; software tests
do not prove compatibility with your reader or 1Password account.
This package does not contain personal signed PDFs, public certificates from
the author, PINs or the author's 1Password references. A fresh-Mac hardware
test is still required on the recipient's own reader and card.
