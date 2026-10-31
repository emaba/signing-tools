# Reference only: never put the actual PIN in this file.
# Loaded inside each signing command's subshell; your shell PATH is unchanged.
if command -v brew >/dev/null 2>&1; then
    _signing_openssl=$(brew --prefix openssl@4 2>/dev/null)
    if [ -x "$_signing_openssl/bin/openssl" ]; then
        PATH="$_signing_openssl/bin:$PATH"
        export PATH
    fi
    unset _signing_openssl
fi

export SIGNP7M_PIN_REF='op://VAULT_ID/ITEM_ID/FIELD_ID'

# Optional: use the actual hexadecimal slot ID, not its listing index.
# export SIGNP7M_SLOT='0x2'
# export SIGNP7M_KEY_ID='445334'
# export SIGNP7M_KEY_URI='pkcs11:token=CNS;id=%44%53%34;type=private'
# export SIGNPDF_TOKEN_LABEL='CNS'
# export SIGNPDF_CERT_ID='445334'
