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

`signpdf` uses a separate PKCS#11 signing worker. Only that worker receives
the resolved PIN from `op run`; it removes the PIN environment variable before
opening the token session. The temporary JSON request contains public signing
selectors and paths, not a PIN or secret reference. Python does not guarantee
erasure of secret strings from memory. No PIN is accepted as a command-line
argument or stored in a file by this implementation.

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

## Reporting a problem

Report security issues privately to the repository owner. Do not attach real
documents, certificates containing personal details, PINs, references naming
private vaults, or full environment/diagnostic dumps. Use a minimal sanitized
reproduction and the relevant dependency versions.
