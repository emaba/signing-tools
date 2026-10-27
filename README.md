# signp7m

A Fish function for signing a PDF as an attached, binary DER CAdES `.p7m`
document on macOS with an InfoCert DS4 smart card and SafeDive middleware.
The private key stays on the card. 1Password CLI automatically retrieves the
PIN through `op run`, after any authorization required by 1Password.

```fish
signp7m document.pdf
signp7m -o signed.p7m document.pdf
signp7m --output 'Signed document.p7m' 'Original document.pdf'
signp7m --help
```

The default output is `<resolved-input-path>.p7m`. Relative `--output` paths
are resolved against the current directory. An existing regular output file
requires an explicit `y` or `yes`; Enter, EOF, and other answers cancel.
Directories and symbolic links cannot be output targets. The function refuses
to overwrite the input itself, including hard links and directory aliases.
The filename does not enforce a `.pdf` input or `.p7m` output extension.

## Provenance and verification status

The starting implementation is the locally installed `signp7m.fish` associated
with the **Firma P7M da terminale** conversation. The owner reported a successful
real signing operation on October 27, 2026, including automatic PIN retrieval,
overwrite confirmation, CMS verification, byte comparison, and a CAdES
attribute check. That historical result applies to the original installed
function and card setup.

This repository externalizes the 1Password reference, offers optional card
settings, rejects PIN parameters in key URIs, protects equivalent input paths,
sets the final output to mode `600`, and checks CMS inspection errors.
The automated tests exercise command flow and failure handling with substitutes.
They do not prove cryptography, middleware compatibility, or a fresh hardware
signing operation. The installed function is not replaced by preparing this repo.

## Requirements

| Component | Purpose |
| --- | --- |
| macOS and a working smart-card reader | Target environment |
| Fish 3.6 or newer | `argparse`, `path normalize`, and function support; automated checks were run with Fish 4.9.3 |
| Homebrew | Resolves the libp11 provider directory |
| Homebrew OpenSSL with provider and `cms -cades` support | CMS signing and verification |
| libp11 with `pkcs11prov.dylib` | OpenSSL PKCS#11 provider |
| OpenSC `pkcs11-tool` | Reads the public signing certificate using SafeDive |
| SafeDive for the specific smart card | Vendor PKCS#11 module |
| InfoCert DS4 signing certificate and corresponding private key | Tested card profile |
| 1Password desktop and CLI v2 | PIN reference resolution and user authorization |
| `realpath`, `cmp`, `mktemp`, `chmod`, `dirname`, `basename`, `mv`, `rm` | Filesystem utilities available on the target Mac |
| Python 3 | Optional automated tests only |

Use OpenSSL and libp11 built against compatible OpenSSL libraries and the same
CPU architecture. Do not mix an Intel middleware library with an Apple Silicon
process. The repository does not promise compatibility with every token,
certificate, macOS version, or future dependency upgrade.

## Install dependencies

Install [Homebrew](https://brew.sh/) using its official instructions if needed.
In Fish:

```fish
brew install fish openssl libp11 opensc
brew install --cask 1password-cli
fish_add_path (brew --prefix openssl)/bin
```

`openssl` must resolve to a Homebrew build compatible with the installed libp11
provider, rather than the macOS system implementation. At repository preparation,
this Mac used OpenSSL 4.1.0 and its libp11 provider linked to `libcrypto.4.dylib`.
OpenSSL 3.x also supplies the required provider/CAdES interfaces, but use a
matching libp11 build if selecting it explicitly. Check before changing an
already working setup:

```fish
command -s openssl
openssl version
brew --prefix libp11
ls (brew --prefix libp11)/lib/ossl-modules/pkcs11prov.dylib
otool -L (brew --prefix libp11)/lib/ossl-modules/pkcs11prov.dylib
openssl list -providers \
    -provider-path (brew --prefix libp11)/lib/ossl-modules \
    -provider default -provider pkcs11prov
```

Install SafeDive from the smart-card issuer's official support/download channel.
Use [InfoCert support](https://help.infocert.it/) to locate the package suitable
for your card and macOS version. The function expects this module by default:

```text
/Applications/SafeDive/STCryptoTokenKit.app/Contents/PlugIns/STToken.appex/Contents/Frameworks/libstPKCS11.dylib
```

If the vendor changes that location, configure `SIGNP7M_MODULE` accordingly.
In the 1Password desktop app, enable CLI integration as described in the
[official app integration guide](https://developer.1password.com/docs/cli/app-integration/).
Store the correct card PIN in a concealed field in 1Password, and copy the
field's **secret reference**. Do not copy or print the actual PIN.

## Install the function and configure it

From a directory in which you want to keep the checkout:

```fish
git clone git@github.com:emaba/signp7m.git
cd signp7m
mkdir -p ~/.config/fish/functions ~/.config/fish/conf.d
```

If `~/.config/fish/functions/signp7m.fish` already exists, first save a private
backup outside this repository. Then install:

```fish
cp signp7m.fish ~/.config/fish/functions/signp7m.fish
```

For a new configuration file:

```fish
cp -n config.example.fish ~/.config/fish/conf.d/signp7m.fish
chmod 600 ~/.config/fish/conf.d/signp7m.fish
vim ~/.config/fish/conf.d/signp7m.fish
```

Replace `op://VAULT_ID/ITEM_ID/FIELD_ID` with the exact secret reference copied
from 1Password. The file is outside the checkout. A reference is an identifier,
not the PIN, but may still reveal vault or item names; IDs reduce that metadata.
If a configuration file already exists, edit it with Vim without overwriting
unrelated settings. Keep the example's placeholder out of your active setup.

Load the configuration and function into the current Fish session:

```fish
source ~/.config/fish/conf.d/signp7m.fish
source ~/.config/fish/functions/signp7m.fish
signp7m --help
```

New Fish sessions load both automatically. No plaintext PIN variable, `op read`,
PIN command-line argument, or repository-local credential file is needed.

### Optional card configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `SIGNP7M_PIN_REF` | Required; no default | `op://vault/item/field` reference |
| `SIGNP7M_MODULE` | SafeDive path above | PKCS#11 middleware library |
| `SIGNP7M_KEY_URI` | `pkcs11:token=CNS;id=%44%53%34;type=private` | Private key selector, without PIN parameters |
| `SIGNP7M_KEY_ID` | `445334` | Hex ID of the matching public signing certificate |
| `SIGNP7M_SLOT` | `0x2` | Slot used to read the certificate |

Defaults reproduce the original DS4 setup. Slot IDs can differ between readers
or sessions. Inspect public slots before setting an override:

```fish
pkcs11-tool \
    --module '/Applications/SafeDive/STCryptoTokenKit.app/Contents/PlugIns/STToken.appex/Contents/Frameworks/libstPKCS11.dylib' \
    --list-slots
```

Use the corresponding public certificate ID and key URI together. `DS4.der`
and `DS4.pem` are temporary filenames, even when selectors are overridden.
No attempt is made to export or inspect the private key.

## Test

### Automated tests without a card or secrets

From the repository root:

```fish
fish --no-config --no-execute signp7m.fish
python3 -m unittest discover -s tests -v
```

The tests use a clean Fish session and a restricted environment, replacing
`brew`, `pkcs11-tool`, `op`, and `openssl` with local test substitutes. They
cover arguments, paths with spaces, both output flags, default output, overwrite
acceptance/refusal, input aliases, secret-reference handling, staged failures,
preservation of existing output, temporary cleanup, and output permissions.
They never call the real 1Password CLI or middleware.

### Manual hardware acceptance test

Use a disposable PDF containing no sensitive content, insert the card, and run:

```fish
signp7m 'test document.pdf'
signp7m -o 'test signed.p7m' 'test document.pdf'
signp7m --output 'test signed.p7m' 'test document.pdf'
```

Approve 1Password's authorization prompt when appropriate. On the last command,
first decline replacement and confirm the old output is unchanged; then repeat
and explicitly accept replacement. Successful signing should report:

```text
Signature completed successfully.
Cryptographic verification: PASSED
Document integrity: PASSED
CAdES attribute: PRESENT
```

Check the resulting file with the issuer's verifier when certificate trust,
revocation, or acceptance by a recipient matters. Do not use CI to sign real
documents or supply a real card PIN to the test suite.

## What the function verifies

1. Reads the public signing certificate from the configured card slot.
2. Signs with SHA-256, `-binary -cades -nodetach`, and the on-card private key.
3. Runs CMS cryptographic verification with `-noverify`.
4. Compares the extracted content byte for byte with the original file.
5. Checks the CMS printout for `id-smime-aa-signingCertificateV2`.
6. Sets mode `600` and moves the completed signature into place only on success.

`-noverify` skips certificate-chain verification. These checks do not establish
certificate trust, revocation status, a trusted timestamp, a full CAdES policy
assessment, or legal/qualified-signature validity. The attribute-presence check
is a structural check, not an independent certificate-binding validation.

Exit codes: `0` means successful completion or a user cancellation; `1` means
an operational failure; `2` means invalid arguments or required configuration.
Cancellation prints `Operation cancelled.` and produces no new output.

## Troubleshooting

- **Generic EMV / Alcor AU9540 reader stalls during signing:** see the
  [macOS reader driver workaround](docs/macos-smartcard-driver.md) for the
  October 27, 2026 incident, the system-wide `useIFDCCID` preference, two
  successful signing runs, compatibility limits, accessory-authorization
  implications on supported Macs, and rollback checks.
  Apply this only when troubleshooting the affected setup; it is not a
  general installation requirement.
- **Missing dependency/provider:** check Homebrew paths, the executable selected
  by `command -s openssl`, and `pkcs11prov.dylib`'s linked OpenSSL version.
- **Module cannot load:** check the installed SafeDive path and CPU architecture.
- **Certificate not found:** inspect public slots and confirm the configured
  certificate ID, slot, token label, and private-key URI correspond.
- **1Password authentication fails:** check desktop integration and authorize
  the request; inspect the reference in Vim without displaying the PIN.
- **Incorrect PIN or locked card:** stop retrying and follow the issuer's
  recovery procedure; repeated wrong PINs can lock a card.
- **No output on failure:** the function deliberately publishes only a result
  that passes all its local checks. An existing output is retained on normal
  signing/verification failures.

See [SECURITY.md](SECURITY.md) for handling and cleanup limitations.

## Upstream references

- [libp11 provider configuration](https://github.com/OpenSC/libp11#pkcs11-provider-configuration)
- [OpenSSL CMS and CAdES options](https://docs.openssl.org/3.6/man1/openssl-cms/)
- [1Password `op run`](https://developer.1password.com/docs/cli/reference/commands/run/)
- [Homebrew libp11](https://formulae.brew.sh/formula/libp11)
- [Homebrew OpenSC](https://formulae.brew.sh/formula/opensc)
- [Homebrew 1Password CLI](https://formulae.brew.sh/cask/1password-cli)
- [InfoCert support](https://help.infocert.it/)
