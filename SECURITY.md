# Security notes

## Secrets and signing authority

- Never commit a PIN, password, token, private key, credential export, or real
  document. A private GitHub repository is not a secret store. `.gitignore`
  prevents common accidents but does not scan content or remove Git history.
- Keep `SIGNP7M_PIN_REF` in your Fish configuration outside the checkout. Only
  the non-secret `op://` identifier is read by the function. The repository
  contains a placeholder, not the owner's actual reference.
- `PKCS11_PIN` is set locally to that reference. `op run` resolves it into the
  environment of the signing subprocess; the parent Fish function does not
  capture the plaintext PIN. The local reference variable is erased after
  signing. The PKCS#11 provider and its process necessarily receive the PIN.
- Environment delivery is not protection against a compromised account,
  debugger, malicious executable/library, process inspection, or a memory dump.
  Use trusted dependencies and a trusted `PATH`. Avoid tracing, environment
  dumps, verbose PIN diagnostics, and PKCS#11 spy modules.
- The signing private key remains on the smart card. The function requests a
  signature and exports only the public certificate. Signing may still require
  user authorization in 1Password. An unlocked authorized session can confer
  signing authority; lock the workstation and remove the card when appropriate.
- Do not add `pin-value` or `pin-source` to a key URI. Both are rejected. Never
  replace the 1Password reference with a literal PIN or call `op read` to debug.

## Files and verification

The Zsh/Bash integration in `signing-tools.sh` loads private settings only in
each command's subshell. Its settings contain a 1Password reference, never the
PIN. `signp7m.py` is a shell-independent CAdES port: it uses a private snapshot,
removes unrelated reference-valued environment entries from subprocesses and
provides `PKCS11_PIN` only to the `op run` signing child. Subprocess diagnostics
are suppressed to prevent token information from reaching the terminal.
The OpenSSL provider necessarily receives the resolved PIN while signing.
Its generated-key tests are not smart-card or 1Password acceptance tests.
The original Fish implementation remains available and unchanged.

- A mode-`700` temporary directory is created beside the output. It temporarily
  holds the public certificate, signed document, and extracted document. The
  final signed file is set to mode `600`. Its embedded certificate may reveal
  the signer's identity.
- Normal success and handled failure remove temporary files. Abrupt process
  termination, a power loss, or filesystem errors may leave `.signp7m.*`
  directories behind. Inspect and remove those locally after confirming no
  signing operation is using them. Deletion is not guaranteed secure erasure
  on SSDs, snapshots, backups, or synced storage.
- The source PDF remains subject to its existing permissions. Select a private
  output directory and keep inputs unchanged during signing. Avoid shared or
  untrusted writable directories: pathname checks and publication do not lock
  the directory against concurrent changes. An output created after the initial
  check can be replaced without a new prompt. Do not run concurrent operations
  targeting the same output.
- The output is published through a same-filesystem move after the local checks
  pass. Existing output survives ordinary signing and verification failures;
  this is not a transactional guarantee against hardware or filesystem failure.
- `openssl cms -verify -noverify` verifies CMS cryptography but skips the trust
  chain. Byte comparison checks document integrity. An attribute-presence check
  does not prove full CAdES compliance. No revocation, timestamp, or legal
  qualification assessment is performed.

## Companion PAdES command

PDF syntax parsing defaults to compatible mode (`strict=False`) for layout,
incremental writing and signature verification. This tolerates recoverable
xref issues without rewriting the input snapshot. `--strict-pdf` selects strict
parsing consistently across the parent and signing worker. Neither mode skips
cryptographic integrity, full coverage, prior-signature/permitted-change or
certification checks. The default stream decoding limits are unchanged.
Unreadable inputs and failed validation still prevent output publication.
Strict parser failures detected during compatible-mode preflight are shown
in Terminal and the preview as safe, mapped diagnostics. Raw parser exception
messages are never sent to the browser or printed: they can contain document
data. These probes are not a PDF standards-conformance validator.

`signpdf` uses a separate PKCS#11 signing worker. Only that worker receives
the resolved PIN from `op run`; it removes the PIN environment variable before
opening the token session. The temporary JSON request contains public signing
selectors and paths, not a PIN or secret reference. Python does not guarantee
erasure of secret strings from memory. No PIN is accepted as a command-line
argument or stored in a file by this implementation.

When no reference environment variable is configured, the program can reuse
one unambiguous literal reference from the installed legacy Fish function,
following scalar aliases without executing Fish. It never resolves the PIN
during configuration discovery. Other reference-valued environment variables
are omitted from the `op run` child to avoid unrelated secret resolution.

The private workspace also contains a snapshot of the input PDF. Its mode is
`700`, its snapshot/request files are mode `600`, and the final output is mode
`600`. Temporary `.signpdf.*` directories have the same crash/secure-erasure
limitations as the CAdES workspace. Existing outputs are preserved on normal
signing or verification failure. New output creation refuses a concurrently
created target; replacement checks do not eliminate all same-user races.

The PAdES checks assess cryptographic integrity, permitted incremental changes,
and selected structural properties. They do not establish signer trust,
revocation, trusted time, full profile conformance, or legal qualification.
See [the PAdES guide](docs/signpdf.md) for supported and unsupported cases.

Visible split-column names come from the signing certificate. The displayed
date/time matches the local PDF signing time; it is not a trusted timestamp.
The optional signing location is user-declared. The cursive name is typeset
text and is not an independently authenticated handwritten signature.

### Local graphical placement

The placement preview binds only to `127.0.0.1` on a random port and uses an
unguessable per-session URL. It renders the private signing snapshot and
keeps at most two PNG previews in memory. It serves only packaged UI assets,
the selected script font, page dimensions and rendered page images, never an
arbitrary filesystem path or the raw PDF. PDFium renders annotations and forms
so existing visible signatures and form values can be reviewed.

This is an IPv4 loopback listener, not a wildcard (`0.0.0.0` or `::`)
listener: it does not accept direct connections through Wi-Fi, Ethernet or
other external network interfaces. It requires no Internet connection for
placement. Loopback is accessible to processes belonging to other local users
as well; it is not a user-authentication boundary. Anyone who obtains the
session URL and can connect locally could read previews or submit/cancel a
placement. The HTTP API does not expose a signing or PIN endpoint. Do not
share the session URL or forward its port with a proxy or tunnel.

Host/origin checks, a request header, a per-session capability, a restrictive
content-security policy, no CORS and no-store response headers limit exposure
to other browser pages. There are no external resources or uploads. Neither
PINs nor secret references are sent to the browser, and authentication is not
requested until placement is confirmed. Cancellation does not sign. The
server closes after confirmation/cancellation, on handled errors/interruption,
or after a 30-minute placement timeout. The listener is closed before
1Password authentication and the signing worker start. Closing the tab alone
does not notify the terminal; cancel there if needed.

The browser receives document images and may retain its own memory/history.
An unguessable URL and local binding do not protect against malicious software
or extensions running as the same user. The preview is a placement aid, not a
certificate/trust validation result or an exact preview of a certificate name
that has not yet been read. Final cryptographic verification still runs before
output publication. Use explicit `--rect-mm` or `--invisible` to skip the UI.

To inspect the actual listener on macOS, leave the preview open and run this
in a second Fish terminal. Replace the example port with the port shown in
the preview's browser address; do not copy or share the full session URL.

```fish
set -l preview_port 54321 # Replace with the port shown in the browser.
lsof -nP -a -iTCP:$preview_port -sTCP:LISTEN
```

The listener should show `127.0.0.1:PORT (LISTEN)`. A wildcard or LAN address
would violate the intended boundary. After confirmation or cancellation,
there should be no listener for that process and port. This check does not
read credentials, card contents or document data. Regression tests verify the
bound socket's address/family, rejected browser requests and listener closure.

## Reporting a problem

Report security issues privately to the repository owner. Do not attach real
documents, certificates containing personal details, PINs, references naming
private vaults, or full environment/diagnostic dumps. Use a minimal sanitized
reproduction and the relevant dependency versions.
