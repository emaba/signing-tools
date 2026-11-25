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
`signing-tools configure` asks for the reference privately and can set supported
card options. Enter at an existing reference prompt keeps that identifier.
The placeholder above must be replaced; a literal PIN is rejected.
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
