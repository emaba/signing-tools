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

On October 28, 2026, the owner reported a successful invisible signature using
the installed smart-card setup and 1Password. The command passed cryptographic
integrity, prior-signature/permitted-change checks, and PAdES structural checks.
A read-only check of the resulting PDF confirmed one signature, preservation
of the original bytes, and mode `600`. No PIN or certificate details were
displayed or added to the repository. The reader model is not identified in
that command's output.

The owner subsequently completed a visible-signature run and added an invisible
second signature to that signed PDF. Read-only checks confirmed one signature
and one visible widget in the first result, then two signatures and one visible
widget in the second. Both results preserved the preceding PDF bytes and had
mode `600`. All local cryptographic and permitted-change checks passed.

Real invisible, visible, and sequential signing have therefore passed these
acceptance runs. Visual placement/legibility has not been confirmed by the
owner, and existing-field signing still needs a real hardware test. Trust,
revocation, and trusted timestamps remain unvalidated. These results do not
establish compatibility with every reader, PDF, or middleware version. This
program never changes macOS reader preferences.

On October 28, 2026, all 56 automated tests passed using Python 3.12.16.
This includes the existing CAdES tests, synthetic cryptographic PDF tests,
and a PKCS#11 adapter test using substitutes. Visible appearances were also
rendered and reviewed at page rotations 0, 90, 180, and 270 degrees. The
signature text stays upright in the displayed rectangle.

On October 30, a split-column appearance was added and all 64 automated tests
passed. The unsigned preview was rendered and reviewed with the default macOS
fonts. Tests cover embedded fonts, certificate-derived names, agreement between
displayed time and signature metadata, all quarter-turn rotations, and
preservation of a preceding signature. The new appearance still needs an
owner-run smart-card acceptance test.
After visual refinement, all 64 tests passed again with Kaushan Script as the
default cursive face and a 12 percent smaller details column. Separate
synthetic sequential-signature checks passed with the bundled font at page
rotations 0, 90, 180, and 270 degrees.

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

### Cursive name and signature details

The optional `split` appearance places a cursive certificate-holder name on
the left, a black vertical separator, and signature details on the right.
It has a transparent background and no outer border. The existing `simple`
appearance remains the default.
The cursive face is Kaushan Script, with a brush-like stroke. The details
column is 12 percent smaller than the initial split-column version, while
keeping its top-left alignment and the same overall signature rectangle.

```fish
signpdf document.pdf --page last --rect-mm 85,245,110,27 \
    --appearance split --location Genova -o document.split.pdf
```

This example occupies 110 by 27 mm and ends 195 mm from the displayed page's
left edge. Choose a blank area. A wide rectangle is preferable to the original
55-by-20 mm test box for this format. The layout scales uniformly to fit;
long names or locations reduce the text size, so inspect the signed result.

The name is derived from the signing certificate: given name and surname when
both exist, otherwise the common name. The cursive version uses title case
when the certificate name is entirely uppercase. The details use uppercase.
There is no arbitrary signer-name override. This is typeset text, not a stored
image of a handwritten signature.

Italian labels are the default for this style: `Firmato digitalmente`, `da`,
`Luogo`, and `Data`. Use `--appearance-language en` for English labels. The
date and time use the same local signing time as the PDF signature metadata,
in day/month/year and 24-hour format. This is not a trusted timestamp.

`--location` is an optional user declaration, not a detected or verified
location. It is also stored in the PDF signature's location metadata; omit it
to omit the location line. It works as metadata with simple or invisible
signatures too. Control characters and empty locations are rejected.

The default fonts are the bundled `assets/fonts/KaushanScript-Regular.ttf`
and macOS's `Arial.ttf`, loaded from `/System/Library/Fonts/Supplemental`.
Kaushan Script is distributed unmodified under the SIL Open Font License 1.1;
see [font provenance and license](../assets/fonts/README.md). Only the used
glyphs are embedded in the resulting PDF. No system font files are distributed.
Override them with `--script-font /path/to/script.ttf` and
`--text-font /path/to/regular.ttf`. Standalone TTF/OTF fonts with Unicode maps
and editable subset-embedding permission are supported; TTC collections are
not supported. Missing fonts and unsupported glyphs produce controlled errors
rather than silent substitutions. Install the updated requirements to obtain
the `pyHanko[opentype]` dependencies.

Font shaping and PDF metrics use a 1000-unit em to compensate for pyHanko
0.38.0's native-unit CID width handling. The original font program and its
layout tables are preserved; only the embedded subset and PDF metrics are
written to the output. This avoids incorrect spacing with 2048-unit macOS
fonts. Automated tests include a synthetic 2048-unit font.
To restore the earlier cursive face, pass
`--script-font '/System/Library/Fonts/Supplemental/Apple Chancery.ttf'`.

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
