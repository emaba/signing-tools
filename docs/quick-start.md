# Install signing-tools on a Mac

You need an **Apple Silicon Mac (M1 or later), macOS 13+**, a compatible reader,
your signing smart card, and a 1Password account/app. Intel Macs are not supported
by the current formula. Fish, ZIP files and manual Python setup are unnecessary.

## 1. Prepare Homebrew and 1Password

If Homebrew is missing, install it from [brew.sh](https://brew.sh/) and follow its
printed Next steps for your usual shell. Then install the 1Password CLI:

```sh
brew install --cask 1password-cli
```

Keep your working 1Password desktop app. If it is missing, install it too:

```sh
brew install --cask 1password
```

Open 1Password, sign in yourself, then enable **Settings > Developer > Integrate
with 1Password CLI**. See the [official setup guide](https://developer.1password.com/docs/cli/get-started/).

## 2. Prepare the smart card

Install the issuer's official PKCS#11 middleware. The tested InfoCert JSafe/DS4
profile uses SafeDive. Connect the reader and confirm that the issuer's app can
see the card. Other cards may need different [card settings](configuration.md).
Do not apply old reader-driver workarounds or firmware changes.

## 3. Install the signing commands

```sh
brew tap emaba/signing-tools https://github.com/emaba/signing-tools.git
brew install emaba/signing-tools/signing-tools
```

Homebrew installs Python, OpenSSL, OpenSC, libp11 and the isolated runtime.
The public repository needs no GitHub account. Stop if a command reports an error.

## 4. Configure the correct PIN reference

In 1Password, save the card's **digital-signature PIN** in a concealed field.
Use the PIN supplied for signing, not the PUK, Mac password, one-time code or
necessarily the CNS authentication PIN. Never guess it or send it to anyone.

On that field choose **Copy Secret Reference**, then run:

```sh
signing-tools configure
signing-tools doctor
```

Paste only the `op://...` reference into the hidden configuration prompt, **never
the numeric PIN**. The reference identifies the field; signing resolves its value
privately through 1Password. Do not share the reference or configuration file.
[Official secret-reference instructions](https://developer.1password.com/docs/cli/secret-references/).

Doctor checks prerequisites without resolving the PIN or logging in to the card.

## 5. Make a first test yourself

From a convenient folder, using filenames that do not already exist:

```sh
signing-tools sample signing-test.pdf
signpdf signing-test.pdf -o signing-test.pades.pdf
signp7m signing-test.pdf -o signing-test.cades.p7m
```

For the PDF, choose the page and rectangle in the local browser preview. Approve
1Password access yourself. Require the verification checks to pass and inspect
the visible signature. On a PIN error, stop; do not retry or guess.

For daily use: `signpdf document.pdf` or `signp7m document.pdf`.
For an invisible PDF signature: `signpdf document.pdf --invisible`.
The normal PDF output is `document.signed.pdf`; P7M output is `document.pdf.p7m`.

## Updates

```sh
brew update
brew upgrade signing-tools
```

Private settings remain in `~/.config/signing-tools/config.toml`. See
[the full installation guide](installation.md) for migration/removal and
[the assistant brief](assistant-installation.md) if an assistant is installing
on your behalf. Only you should handle the real PIN and signing authorisation.
