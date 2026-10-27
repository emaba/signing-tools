function signp7m --description "Sign a PDF using an InfoCert smart card (CAdES)"

    # Parse command-line arguments
    argparse -n signp7m h/help 'o/output=' -- $argv
    or return 2

    if set -q _flag_help
        echo "Usage: signp7m [OPTIONS] INPUT.pdf"
        echo ""
        echo "Options:"
        echo "  -o, --output FILE   Specify the output P7M file"
        echo "  -h, --help          Display this help message"
        echo ""
        echo "Examples:"
        echo "  signp7m document.pdf"
        echo "  signp7m -o signed.p7m document.pdf"
        echo ""
        echo "If the output file already exists, confirmation is required."
        return 0
    end

    if test (count $argv) -ne 1
        echo "Error: exactly one input PDF is required."
        echo "Usage: signp7m [-o OUTPUT.p7m] INPUT.pdf"
        return 2
    end

    # Smart card configuration
    set -l pkcs11_module "/Applications/SafeDive/STCryptoTokenKit.app/Contents/PlugIns/STToken.appex/Contents/Frameworks/libstPKCS11.dylib"
    set -l pkcs11_key 'pkcs11:token=CNS;id=%44%53%34;type=private'
    set -l pkcs11_key_id 445334
    set -l pkcs11_slot 0x2

    # Keep user-specific settings outside the repository.
    if set -q SIGNP7M_MODULE
        set pkcs11_module "$SIGNP7M_MODULE"
    end
    if set -q SIGNP7M_KEY_URI
        set pkcs11_key "$SIGNP7M_KEY_URI"
    end
    if set -q SIGNP7M_KEY_ID
        set pkcs11_key_id "$SIGNP7M_KEY_ID"
    end
    if set -q SIGNP7M_SLOT
        set pkcs11_slot "$SIGNP7M_SLOT"
    end
    set -l onepassword_pin_ref "$SIGNP7M_PIN_REF"

    if not string match -q 'op://*/*/*' -- "$onepassword_pin_ref"
        echo "Error: set SIGNP7M_PIN_REF to a 1Password secret reference (op://vault/item/field)."
        return 2
    end

    if string match -qi '*pin-value=*' -- "$pkcs11_key"; or string match -qi '*pin-source=*' -- "$pkcs11_key"
        echo "Error: the key URI must not contain PIN parameters."
        return 2
    end

    # Resolve input file
    set -l input_file (realpath -- "$argv[1]" 2>/dev/null)

    if test -z "$input_file"; or not test -f "$input_file"
        echo "Error: input file not found."
        return 1
    end

    # Resolve output file
    set -l output_file "$input_file.p7m"

    if set -q _flag_output
        set output_file "$_flag_output"

        if test -z "$output_file"
            echo "Error: output filename cannot be empty."
            return 2
        end
    end

    if not string match -q '/*' -- "$output_file"
        set output_file "$PWD/$output_file"
    end

    set output_file (path normalize -- "$output_file")

    if test "$input_file" = "$output_file"
        echo "Error: input and output files must be different."
        return 1
    end

    set -l output_dir (dirname -- "$output_file")

    if not test -d "$output_dir"
        echo "Error: output directory does not exist."
        return 1
    end

    # Resolve directory aliases before comparing input and output paths.
    set output_dir (realpath -- "$output_dir")
    or return 1
    set output_file "$output_dir/"(basename -- "$output_file")

    if test "$input_file" = "$output_file"; or test "$input_file" -ef "$output_file"
        echo "Error: input and output files must be different."
        return 1
    end

    # Handle existing output files
    if test -e "$output_file"; or test -L "$output_file"

        if not test -f "$output_file"; or test -L "$output_file"
            echo "Error: output path is not a regular file."
            return 1
        end

        echo "The output file already exists:"
        echo "$output_file"
        echo ""

        read -l -P "Overwrite existing file? [y/N] " answer

        switch (string lower -- (string trim -- "$answer"))
            case y yes
                echo "Overwrite confirmed."
            case '*'
                echo "Operation cancelled."
                return 0
        end
    end

    # Check required dependencies
    for dependency in openssl pkcs11-tool op cmp mktemp brew
        if not command -q $dependency
            echo "Error: missing dependency: $dependency"
            return 1
        end
    end

    if not test -f "$pkcs11_module"
        echo "Error: SafeDive PKCS#11 module not found."
        return 1
    end

    set -l provider_path (brew --prefix libp11 2>/dev/null)/lib/ossl-modules

    if not test -f "$provider_path/pkcs11prov.dylib"
        echo "Error: libp11 OpenSSL provider not found."
        return 1
    end

    # Create a private temporary working directory
    set -l work_dir (mktemp -d "$output_dir/.signp7m.XXXXXXXX")
    or begin
        echo "Error: unable to create temporary directory."
        return 1
    end

    chmod 700 "$work_dir"
    or begin
        command rm -rf -- "$work_dir"
        echo "Error: unable to secure temporary directory."
        return 1
    end

    set -lx PKCS11_MODULE_PATH "$pkcs11_module"
    set -l result 0

    # Extract the public signing certificate from the smart card
    echo "Reading InfoCert DS4 signing certificate..."

    pkcs11-tool \
        --module "$pkcs11_module" \
        --slot "$pkcs11_slot" \
        --read-object \
        --type cert \
        --id "$pkcs11_key_id" \
        --output-file "$work_dir/DS4.der"

    if test $status -ne 0
        echo "Error: failed to read signing certificate."
        set result 1
    end

    # Convert the public certificate to PEM
    if test $result -eq 0
        openssl x509 \
            -inform DER \
            -in "$work_dir/DS4.der" \
            -out "$work_dir/DS4.pem"

        if test $status -ne 0
            echo "Error: certificate conversion failed."
            set result 1
        end
    end

    # Sign the document using the private key on the smart card
    if test $result -eq 0
        echo "Creating CAdES signature..."
        echo "Authenticating through 1Password..."

        # 1Password resolves the secret reference only for the child process
        set -lx PKCS11_PIN "$onepassword_pin_ref"

        op run -- openssl cms -sign \
            -provider-path "$provider_path" \
            -provider default \
            -provider pkcs11prov \
            -binary \
            -cades \
            -nodetach \
            -md sha256 \
            -in "$input_file" \
            -signer "$work_dir/DS4.pem" \
            -inkey "$pkcs11_key" \
            -outform DER \
            -out "$work_dir/signed.p7m"

        set -l signing_status $status

        # Remove the PIN reference from the function environment
        set -e PKCS11_PIN

        if test $signing_status -ne 0
            echo "Error: digital signing failed."
            set result 1
        end
    end

    # Verify the cryptographic signature
    if test $result -eq 0
        echo "Verifying cryptographic signature..."

        openssl cms -verify \
            -inform DER \
            -in "$work_dir/signed.p7m" \
            -noverify \
            -out "$work_dir/extracted.pdf"

        if test $status -ne 0
            echo "Error: cryptographic signature verification failed."
            set result 1
        end
    end

    # Compare the signed content against the original
    if test $result -eq 0
        echo "Verifying document integrity..."

        if not cmp -s "$input_file" "$work_dir/extracted.pdf"
            echo "Error: signed content differs from the original."
            set result 1
        end
    end

    # Verify the presence of the CAdES signing certificate attribute
    if test $result -eq 0
        echo "Checking CAdES attributes..."

        set -l cms_attributes (openssl cms -cmsout -print \
            -inform DER \
            -in "$work_dir/signed.p7m")
        set -l attributes_status $status

        if test $attributes_status -ne 0; or not string match -q '*id-smime-aa-signingCertificateV2*' -- $cms_attributes
            echo "Error: required CAdES attribute not found."
            set result 1
        end
    end

    if test $result -eq 0
        chmod 600 "$work_dir/signed.p7m"
        or set result 1
    end

    # Publish the signed file only after successful verification
    if test $result -eq 0
        echo "Saving signed document..."

        command mv -f -- "$work_dir/signed.p7m" "$output_file"

        if test $status -ne 0
            echo "Error: failed to save signed document."
            set result 1
        end
    end

    # Remove temporary files
    command rm -rf -- "$work_dir"

    if test $result -ne 0
        echo "Signing operation failed."
        return 1
    end

    echo ""
    echo "Signature completed successfully."
    echo "Cryptographic verification: PASSED"
    echo "Document integrity: PASSED"
    echo "CAdES attribute: PRESENT"
    echo ""
    echo "Output: $output_file"

    return 0
end
