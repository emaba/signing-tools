# signpdf: PAdES PDF signing

`signpdf` signs a PDF using a PKCS#11 smart card through SafeDive. The output
is another PDF. The private key remains on the card; 1Password resolves a PIN
reference only for the signing worker.

## Scope and verification status

This first version supports existing empty signature fields, invisible
signatures, visible rectangles in millimetres, and sequential signatures.
Mouse placement, automatic blank-space detection, timestamps, and long-term
validation profiles are not implemented.

The implementation uses pyHanko 0.38.0 and pypdf 6.10.0. Tests cover file
handling and page geometry. Integration tests create real PDF signatures with
synthetic in-memory keys: invisible, visible on a cropped/rotated page,
existing field, sequential signatures, certification locks, and tampering
rejection. The PKCS#11 adapter is tested with substitutes for the token and
middleware.

Hardware signing with SafeDive and the owner's JSafe card remains unvalidated.
The successful `signp7m` runs do not prove compatibility with this new
PKCS#11 client. This program never changes macOS reader preferences. Use the
known-working Gemplus reader for the initial hardware acceptance test.

On October 28, 2026, all 56 automated tests passed using Python 3.12.16.
This includes the existing CAdES tests, synthetic cryptographic PDF tests,
and a PKCS#11 adapter test using substitutes. Visible appearances were also
rendered and reviewed at page rotations 0, 90, 180, and 270 degrees. The
signature text stays upright in the displayed rectangle.

## Installation

Use a dedicated Python 3.12 environment with the same architecture as SafeDive.
From the repository, in Fish:

```fish
python3.12 -m venv .venv-signpdf
.venv-signpdf/bin/python -m pip install -r requirements-signpdf.txt
set -gx SIGNPDF_HOME (pwd -P)
set -gx SIGNPDF_PYTHON "$SIGNPDF_HOME/.venv-signpdf/bin/python"
source "$SIGNPDF_HOME/signpdf.fish"
signpdf --help
```

For persistent installation, preserve any existing function, then copy
`signpdf.fish` to `~/.config/fish/functions/signpdf.fish`. In a private Fish
configuration outside the checkout, set `SIGNPDF_HOME` to the absolute checkout
directory and `SIGNPDF_PYTHON` to its dedicated Python executable. Use Vim to
edit that configuration. Update the paths if the checkout moves.

The separate `pyhanko-cli` package and the OpenSSL/libp11 provider are not
required by this function. The CAdES `signp7m` function is unchanged.

## Authentication and card settings

| Variable | Default / fallback | Purpose |
| --- | --- | --- |
| `SIGNPDF_PIN_REF` | `SIGNP7M_PIN_REF`, then the legacy installed function | 1Password `op://VAULT_ID/ITEM_ID/FIELD_ID` reference |
| `SIGNPDF_MODULE` | `SIGNP7M_MODULE`, then the standard SafeDive module | PKCS#11 library |
| `SIGNPDF_TOKEN_LABEL` | `CNS` | Exactly one token must match |
| `SIGNPDF_KEY_ID` | `SIGNP7M_KEY_ID`, then `445334` | Private key object ID in hexadecimal |
| `SIGNPDF_CERT_ID` | Effective `SIGNPDF_KEY_ID` | Matching public certificate object ID |
| `SIGNPDF_RAW_MECHANISM` | `0` | Set `1` only if separate hashing/signing is required |
| `SIGNPDF_HOME` | Required by Fish wrapper | Absolute checkout directory |
| `SIGNPDF_PYTHON` | Required by Fish wrapper | Dedicated Python executable |

If neither reference variable is configured, `signpdf` reads only scalar
assignments from `~/.config/fish/functions/signp7m.fish` to find the historical
`PKCS11_PIN` reference, including an unambiguous local variable alias. It does
not execute, source, or modify that function. Ambiguous assignments, cycles,
and computed values are rejected. The reference is not printed or copied into
the repository. Explicit environment configuration takes precedence.

Vault, item, and section names can contain spaces; optional section paths are
supported. Use the reference exactly as copied from 1Password. It identifies
the PIN field; it is not the PIN value.

`SIGNP7M_SLOT` and `SIGNP7M_KEY_URI` are not reused: selection conventions
differ between clients. Configure explicit token and object IDs for another
card. Token selection by label avoids hard-coding a slot number and rejects
ambiguous labels. The default module is:

```text
/Applications/SafeDive/STCryptoTokenKit.app/Contents/PlugIns/STToken.appex/Contents/Frameworks/libstPKCS11.dylib
```

`op run` resolves the reference into a worker environment variable. The worker
consumes the PIN and removes that variable before opening the token session.
Other `op://` environment values are omitted from this `op run` invocation to
avoid resolving unrelated secrets or duplicating the PIN in configuration
variables passed to the worker.
Neither the PIN nor its reference is written to the temporary request file.
The parent sees only the reference. Python strings and vendor libraries do
not guarantee PIN erasure from process memory. There is no automatic PIN
retry or mechanism fallback. See [SECURITY.md](../SECURITY.md).

## Placement and field names

Choose exactly one mode:

```fish
signpdf document.pdf --list-fields
signpdf document.pdf --field SupplierSignature
signpdf document.pdf --invisible
signpdf document.pdf --page last --rect-mm 140,245,55,20
```

`--list-fields` is read-only, does not authenticate, and emits one JSON object
per signature field with its name and empty/signed status. It does not
validate signatures. `--field` signs only an existing empty signature field;
missing and occupied fields are rejected.

`--rect-mm LEFT,TOP,WIDTH,HEIGHT` measures from the displayed page's top-left
corner after cropping and rotation. `140,245,55,20` means a 55-by-20 mm box
starting 140 mm from the left and 245 mm from the top. The rectangle must fit
within the effective page. Quarter-turn rotation, CropBox offsets, MediaBox
clipping, and `/UserUnit` scaling are handled.

`--page` is one-based, accepts `last`, and defaults to `last` for rectangles.
It is rejected for the other modes. The program checks bounds but does not
detect overlap with text/images; choose a blank area and inspect the result.
Very small rectangles may render the signature text illegibly.

New fields use the first available `SignatureN`. `--name` chooses a new field
name for visible or invisible signatures: start with a letter, use at most
64 ASCII letters/digits/underscores/hyphens. Existing names are used as stored.

## Output and multiple signatures

The default output is `document.signed.pdf`; `-o` and `--output` override it.
An existing regular output requires explicit replacement confirmation.
The input cannot be the output, including through hard links or directory
aliases. Symlinks and non-regular output paths are rejected.

```fish
signpdf document.pdf --invisible --name SupplierSignature -o supplier-signed.pdf
signpdf supplier-signed.pdf --page last --rect-mm 140,220,55,20 \
    --name ClientSignature -o signed-by-both.pdf
```

Each call adds one signature from the selected card in a distinct field and
an incremental revision. Another person's signature requires their card and
configuration. One signature covers a document revision; it need not appear
on every page. Existing document or field locks may prohibit further signing.

## Verification before publishing

Before authentication, the program checks all existing signatures. It signs
a private snapshot, then checks that:

1. The original bytes remain the prefix of the incremental output.
2. The output contains exactly the expected signed fields.
3. All signatures pass cryptographic integrity, revision coverage, and
   pyHanko's permitted-change analysis.
4. The new signature covers the final file and uses `/ETSI.CAdES.detached`
   with a `signingCertificateV2` attribute.
5. The output path has not changed since replacement confirmation.

Temporary directories are mode `700`; final PDFs are mode `600`. Newly
created outputs are published without overwriting a path created concurrently.
Normal failures, cancellation, and keyboard interruption clean up the temporary
directory. Crashes, forced termination, and filesystem failure can leave files.
These checks are not a defense against every race with a malicious process
running as the same user or root; use private directories.

Validation is offline. Certificate trust, revocation, trusted timestamping,
and qualified-signature status are not assessed. The displayed local time is
not a trusted timestamp. The intended output is a basic PAdES signature; the
structural checks are not independent profile-conformance certification.
Check acceptance with the recipient's verifier.

Encrypted PDFs, document timestamps, and signature fields with multiple
widgets are unsupported in this first version.
Third-party logging and exception payloads are suppressed; errors show
controlled messages and exception class names. Do not enable raw APDU or
PKCS#11 traces or provide credentials when reporting a problem.

## Tests and hardware acceptance

```fish
fish --no-config --no-execute signpdf.fish
.venv-signpdf/bin/python -m unittest discover -s tests -v
```

Skipped cryptographic tests are not evidence of successful signing. Review
the final summary. Synthetic test keys are generated in memory; no user
credentials or card are used by the automated suite.

Before signing real documents, use a disposable, non-sensitive PDF:

```fish
signpdf 'test document.pdf' --invisible -o 'test invisible.pdf'
signpdf 'test document.pdf' --page last --rect-mm 10,10,55,20 -o 'test visible.pdf'
signpdf 'test visible.pdf' --invisible -o 'test two signatures.pdf'
signpdf 'test two signatures.pdf' --list-fields
```

Require every integrity check to pass. Inspect visible placement and legibility;
independently verify both signatures in a PDF signature verifier. Confirm that
overwrite refusal preserves the output. Record dependency versions and results
without credentials or document content. Do not run live signing in CI.

## References

- [pyHanko signing guide](https://docs.pyhanko.eu/en/latest/cli-guide/signing.html)
- [Signature fields](https://docs.pyhanko.eu/en/latest/lib-guide/sig-fields.html)
- [PKCS#11 implementation at v0.38.0](https://github.com/MatthiasValvekens/pyHanko/blob/v0.38.0/pkgs/pyhanko/src/pyhanko/sign/pkcs11.py)
- [macOS reader driver incident and rollback](macos-smartcard-driver.md)
