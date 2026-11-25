# Install signing-tools on a Mac

This guide covers a fresh installation with an **InfoCert JSafe/DS4 signing card**
and SafeDive. For another card, confirm its middleware and
[card settings](configuration.md) with its issuer before signing.

You need an **Apple Silicon Mac (M1 or later)**, a compatible USB smart-card
reader, an activated signing card with a valid signing certificate, its known
digital-signature PIN, and a working 1Password account. For a new supported
Homebrew installation, use **macOS 15 or later**: see
[Homebrew's current requirements](https://docs.brew.sh/Installation).
The formula's own macOS 13 minimum does not guarantee current Homebrew or vendor
support on older systems. Intel Macs are not supported by this formula.

Use **Terminal**, in Applications > Utilities. Commands below work in macOS's
usual Zsh shell; Fish, ZIP files and manual Python setup are unnecessary.
Run commands one at a time and stop if one fails. Internet access is needed to
download the software and for 1Password as required by your account.

## 1. Prepare Homebrew

If `brew --version` already works, keep that installation and skip this section.
Otherwise check for Apple's Command Line Tools:

```sh
xcode-select -p
```

If they are missing, run the following and finish the installation in the macOS
dialog before continuing. Full Xcode is unnecessary.

```sh
xcode-select --install
```

Install Homebrew using the command published on [brew.sh](https://brew.sh/):

```sh
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Follow its printed **Next steps** for your shell so `brew` is available in new
Terminal windows. This is Homebrew's initial shell setup; signing-tools adds no
shell startup entries. Open a new Terminal and check:

```sh
brew --version
```

Homebrew's first installation may ask for the Mac administrator password.
Routine `brew install` commands below run without `sudo`.

## 2. Prepare 1Password

Install the 1Password CLI:

```sh
brew install --cask 1password-cli
```

Keep your working 1Password desktop app. If it is missing, install it too:

```sh
brew install --cask 1password
```

Open 1Password, sign in yourself, then enable **Settings > Developer > Integrate
with 1Password CLI**. Touch ID is optional. Check the CLI installation:

```sh
op --version
```

This displays only a version; authentication is tested during the first signature.
See the [official setup guide](https://developer.1password.com/docs/cli/get-started/).

## 3. Install SafeDive and connect the card

SafeDive is the card middleware; Homebrew does **not** install it.

1. Open the official [InfoCert drivers page](https://www.infocert.it/firma-digitale/driver-installazione).
2. Under **Driver e componenti aggiuntivi**, choose **Download safedive lib p11
   modello jsafe per macos** for your issuer-confirmed JSafe card. Other card
   models can require Bit4id instead; do not choose a kit just because it is for Mac.
3. Open the downloaded `.pkg` in Finder. Follow the macOS Installer steps,
   accept the licence if you agree, and install in the default location.
   Enter the **Mac administrator password locally** if requested. This installer
   does not need your signing PIN. Finish any requested restart before testing;
   the currently linked package requires a restart for its CryptoTokenKit component.
4. Connect the compatible reader and insert the card as shown by the reader's
   instructions. Close other signing applications before the tests below.

On 25 November 2026, InfoCert's JSafe link points to
[`SafeDive2025_v6_0_6_Universal.pkg`](https://infocertsignupdate.infocert.it/driver/SafeDive2025_v6_0_6_Universal.pkg).
Prefer the drivers page for future versions. SafeDive is separate from the
InfoCert Sign desktop signing application; the latter is not required by this CLI.
The checked package is signed by **STMicroelectronics SA** and declares both
Apple Silicon and Intel installer architectures; signing-tools itself currently
supports Apple Silicon only.

Check that the expected PKCS#11 library was installed:

```sh
ls -l '/Applications/SafeDive/STCryptoTokenKit.app/Contents/PlugIns/STToken.appex/Contents/Frameworks/libstPKCS11.dylib'
```

This checks a software file, without reading the card or any PIN. If it is
missing, stop and check the installer/model. If the issuer documents a different
library location, use `configure --module` as described below. Do not apply old
`useIFDCCID` workarounds, modify firmware, or disable macOS security checks.

Card activation or recovery, if still needed, follows the issuer's separate
procedure and must be completed by the card owner before these signing tests.

## 4. Install the signing commands

```sh
brew tap emaba/signing-tools https://github.com/emaba/signing-tools.git
brew install emaba/signing-tools/signing-tools
```

Homebrew installs Python, OpenSSL, OpenSC, libp11 and the isolated runtime.
The public repository needs no GitHub account. Check the installed commands:

```sh
signing-tools --version
signpdf --help
signp7m --help
```

## 5. Save the correct PIN in 1Password and configure its reference

In the 1Password desktop app, create an item for your card and save the card's
**digital-signature PIN** in a field of type **Password** (concealed), then save.
Use the PIN supplied for signing, not the PUK, Mac password, one-time code or
necessarily the CNS authentication PIN. Preserve any leading zeroes.
Never guess it or send it to anyone.

Open the menu next to that saved field and choose **Copy Secret Reference**,
not the command that copies its value. CLI integration from step 2 must be enabled
for this option to appear. Then run:

```sh
signing-tools configure
signing-tools doctor
```

Paste only the `op://...` reference into the hidden configuration prompt, **never
the numeric PIN**. The reference identifies the field; signing resolves its value
privately through 1Password. Do not share the reference or configuration file.
[Official secret-reference instructions](https://developer.1password.com/docs/cli/secret-references/).

Continue through the wizard: choose the installed SafeDive library, your reader/card
and its **signing certificate**, checking the displayed name, expiry and purpose.
Confirm the private key ID (normally the selected certificate ID; use another
only if the issuer specifies it). The wizard sets the slot, token label and
certificate ID, derives the matching P7M key URI, and shows a summary. Answer
`y` only after reviewing it. The existing configuration is unchanged if you cancel.
No PIN attempt, private key access or signature happens during this procedure.

If public certificates cannot be listed without login, use
`signing-tools configure --manual` with issuer-confirmed identifiers; do not enter
a PIN to enable discovery. See [guided setup details](configuration.md#guided-setup).

Doctor checks prerequisites without resolving the PIN or logging in to the card.
All checks should report `PASS` before continuing. It does **not** establish
whether the selected card, signing key, PIN, or slot is correct.

The wizard replaces hardcoded profile assumptions with the selected card's public
identifiers. It cannot inspect a private key without login: the key ID still
needs the issuer's confirmation if different from the certificate ID. Follow
[Card detection or P7M certificate errors](#card-detection-or-p7m-certificate-errors)
if needed. Do not guess identifiers or PINs.

## 6. Make a first test yourself

Create a folder in Finder for your tests. In Terminal, type `cd `, drag that
folder from Finder into the Terminal window, then press Return. Use filenames
that do not already exist:

```sh
signing-tools sample signing-test.pdf
signpdf signing-test.pdf -o signing-test.pades.pdf
signp7m signing-test.pdf -o signing-test.cades.p7m
```

For the PDF, choose the page and rectangle in the local browser preview. Approve
the placement, then approve 1Password access yourself when requested. The preview
uses a temporary server on `127.0.0.1`, accessible only from this Mac, and closes
before PIN access. Repeat the owner approval for the P7M test if requested.

Require each command to finish successfully with its verification checks passing.
Open `signing-test.pades.pdf` and inspect the visible signature. The displayed
name comes from the signing certificate; it is not configured as a typed name.
For a location line, add `--location 'Your city'` to the `signpdf` command.
On any PIN or locked-card error, stop; do not retry or guess. A generic signing
failure also needs investigation before another attempt.

Local success checks cryptographic integrity, not certificate trust, revocation
or trusted timestamps. For the first test, also check both files in an independent
signature validator supported by your issuer; do not upload private documents
to a website. These tools do not currently add a trusted timestamp.

## 7. Daily use, updates and removal

For daily use: `signpdf document.pdf` or `signp7m document.pdf`.
For an invisible PDF signature: `signpdf document.pdf --invisible`.
The normal PDF output is `document.signed.pdf`; P7M output is `document.pdf.p7m`.

Quote paths containing spaces, or drag the input file from Finder after typing
`signpdf ` or `signp7m `. The input file is preserved.

Update through Homebrew:

```sh
brew update
brew upgrade signing-tools
```

Private settings remain in `~/.config/signing-tools/config.toml`. See
[the full installation guide](installation.md) for migration/removal and
[the assistant brief](assistant-installation.md) if an assistant is installing
on your behalf. Only you should handle the real PIN and signing authorisation.

`brew uninstall signing-tools` removes the CLI package and preserves your private
settings. It does not uninstall SafeDive or 1Password. No Homebrew developer mode
is needed for installation or normal use.

## Troubleshooting

- **`brew: command not found`:** complete Homebrew's printed Next steps, then open
  a new Terminal. Do not install a second copy.
- **Missing middleware:** repeat the library check in step 3. Keep a working
  installation; use the issuer's installer/support for a missing or incompatible
  library. A different documented location can be saved with
  `signing-tools configure --module '/absolute/path/to/library.dylib'`.
- **1Password menu or authentication missing:** open/unlock the desktop app,
  confirm CLI integration is enabled and use the same macOS user. Follow the
  official setup guide if an organisation policy disables integration.
- **Missing/invalid PIN reference:** run `signing-tools configure` again and
  copy the saved field's reference, never its PIN. Do not print the configuration.
- **PDF syntax warning:** read the Terminal warning and preview banner, then
  inspect the document. Compatible parsing allows recoverable structural issues;
  it cannot make every damaged or encrypted PDF signable.

### Card detection or P7M certificate errors

With the card inserted and other signing apps closed, you can list slots without
logging in or supplying a PIN:

```sh
pkcs11-tool --module '/Applications/SafeDive/STCryptoTokenKit.app/Contents/PlugIns/STToken.appex/Contents/Frameworks/libstPKCS11.dylib' --list-slots
```

Inspect this output **locally**: it can contain token labels and serial numbers;
do not paste the full output into a chat. An empty reader is not a usable token.
For the correct card, use the **slot ID in parentheses**, not its list index.
For example, if the matching entry is `Slot 0 (0x2)`, the ID is `0x2`.
When only the P7M certificate slot needs changing, save the actual ID with:

```sh
signing-tools configure --slot 0x2
```

Replace `0x2` with the observed ID. At the hidden reference prompt, Return keeps
your existing reference. Re-run `signing-tools doctor`. If the token label or
signing key differs from the JSafe/DS4 profile, consult
[configuration](configuration.md) and the issuer before proceeding: changing
the slot alone does not configure a different card profile. No PIN attempts are
needed for this slot listing.
