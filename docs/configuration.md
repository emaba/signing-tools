# Unified reference-only configuration

Default: `~/.config/signing-tools/config.toml`. `XDG_CONFIG_HOME` and the explicit
`SIGNING_TOOLS_CONFIG` file override are supported. The file is private (mode 600)
and is never included in releases or Homebrew resources.

```toml
schema = 1

[signing]
pin_reference = "op://VAULT_ID/ITEM_ID/FIELD_ID" # Replace with the exact field reference.
module = "/Applications/SafeDive/STCryptoTokenKit.app/Contents/PlugIns/STToken.appex/Contents/Frameworks/libstPKCS11.dylib"
token_label = "CNS"
key_id = "445334"
certificate_id = "445334"
slot = "0x2"
key_uri = "pkcs11:token=CNS;id=%44%53%34;type=private"
raw_mechanism = false
```

These profile values are examples, not universal defaults for every card.
The placeholder above is not accepted as a real reference; a literal PIN is rejected.

## Guided setup

```sh
signing-tools configure
```

Without field options, this starts the wizard:

1. Enter the `op://...` field reference privately. Return keeps an existing reference.
2. Select an installed issuer-supported PKCS#11 library, or enter its absolute path.
3. Select the reader/card. Only slots with a token are listed; slot IDs are taken
   directly from the middleware, not inferred from display indices.
4. Select the currently valid signing certificate, checking its label, owner,
   expiry and usage. Choose the signing certificate, not CNS authentication.
5. Confirm the private key ID. The default is the certificate object's ID;
   change it only when your issuer specifies a different key ID.
6. Review the module, slot, token label, certificate ID, key ID, derived key URI,
   mechanism and hidden-reference status. Save only after explicit confirmation.

Discovery runs in a separate process with a 20-second timeout. It opens read-only
sessions without a user PIN, security-officer PIN or protected-authentication
request, and reads public certificate objects only. It never calls 1Password,
logs in, enumerates private keys, exports a key or creates a test signature.
Names/labels are shown locally for selection and should not be pasted into chats.
Certificates and token serial numbers are not saved in the configuration.

The key URI is derived from the selected token label and private key ID, with
PKCS#11 percent encoding. Both signing commands use the same module/key selection;
both use `certificate_id` for their certificate even if it differs from `key_id`.
The wizard cannot verify the PIN, private key accessibility/match, certificate
trust or revocation. A real owner-approved test remains necessary.

If multiple connected cards have the same token label, disconnect the extra cards
before configuring. The current PDF signer requires an unambiguous token label.
Cancel, EOF, invalid input, missing certificates and discovery errors leave the
existing configuration unchanged. Only the final save writes a mode-600 file.

For middleware that hides public certificates until login, or for an offline setup:

```sh
signing-tools configure --manual
```

This guides the module, slot ID, token label, certificate ID, private key ID and
raw-mechanism setting using issuer-confirmed values, then derives the URI and
asks for confirmation. It performs no card discovery or login. Normal discovery
preserves the existing raw-mechanism setting (false for a fresh setup).

## Explicit field updates

Field options retain the previous direct-update workflow and skip discovery and
the final wizard confirmation, while still prompting privately for the reference:

```sh
signing-tools configure --slot 0x7
signing-tools configure --token-label CNS --key-id 445334 --certificate-id 445334
signing-tools configure --module '/absolute/path/to/middleware.dylib'
```

Changing the token label or private key ID regenerates the P7M key URI to avoid
stale selections. If the existing URI has custom qualifiers, a direct identity
update is refused: use the wizard and review the complete replacement profile.
Other field updates preserve an existing URI. `--wizard` explicitly requests
discovery when supplying a module path; choose card/certificate identifiers
interactively rather than combining it with identity field options. The
mechanism options are `--raw-mechanism` and `--no-raw-mechanism`; do not guess them.
No 1Password lookup is performed by configuration or migration.

Optional `[tools]` keys are `openssl`, `pkcs11_tool`, `onepassword`, and
`provider_path`, containing local paths. Normally Homebrew's immutable
installation defaults select the matching OpenSSL/provider automatically;
no shell PATH modification is needed.

Explicit legacy `SIGNP7M_*` and `SIGNPDF_*` environment settings remain supported
as per-process overrides. `SIGNING_TOOLS_OPENSSL`, `SIGNING_TOOLS_PKCS11_TOOL`,
`SIGNING_TOOLS_ONEPASSWORD`, and `SIGNING_TOOLS_PROVIDER_PATH` override tool paths.
Avoid a second permanent shell configuration: TOML is the canonical user setup.
The signing commands no longer inspect Fish files implicitly. Only the explicit
migration command performs static legacy discovery.

`doctor` reports status, never configuration contents, certificate details or
PIN material. `doctor --runtime-only` checks the installed package and native
imports without loading personal configuration or invoking external tools.
