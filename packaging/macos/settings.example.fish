# Shared signing-tool settings. Store only a reference, never a PIN.
# This selection affects Fish sessions; it does not replace macOS OpenSSL.
if command -q brew
    set -l signing_openssl (brew --prefix openssl@4 2>/dev/null)
    if test -x "$signing_openssl/bin/openssl"
        fish_add_path --path --prepend "$signing_openssl/bin"
    end
end

# Replace the placeholder with Copy Secret Reference from the exact PIN field.
set -gx SIGNP7M_PIN_REF 'op://VAULT_ID/ITEM_ID/FIELD_ID'

# Optional: set to the actual hexadecimal slot ID from --list-slots.
# Do not use the listing index. Keep commented if the default 0x2 is correct.
# set -gx SIGNP7M_SLOT '0x2'

# The following defaults apply to the tested InfoCert DS4/SafeDive profile.
# Change only after confirming another supported card profile.
# set -gx SIGNP7M_KEY_ID '445334'
# set -gx SIGNP7M_KEY_URI 'pkcs11:token=CNS;id=%44%53%34;type=private'
# set -gx SIGNPDF_TOKEN_LABEL 'CNS'
# set -gx SIGNPDF_CERT_ID '445334'
