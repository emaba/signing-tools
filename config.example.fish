# Copy this file to ~/.config/fish/conf.d/signp7m.fish and edit it with Vim.
# Store only a reference here. Never put the actual PIN in a configuration file.
set -gx SIGNP7M_PIN_REF 'op://VAULT_ID/ITEM_ID/FIELD_ID'

# Optional overrides. These defaults reproduce the original InfoCert DS4 setup.
# set -gx SIGNP7M_MODULE '/Applications/SafeDive/STCryptoTokenKit.app/Contents/PlugIns/STToken.appex/Contents/Frameworks/libstPKCS11.dylib'
# set -gx SIGNP7M_KEY_URI 'pkcs11:token=CNS;id=%44%53%34;type=private'
# set -gx SIGNP7M_KEY_ID '445334'
# set -gx SIGNP7M_SLOT '0x2'
