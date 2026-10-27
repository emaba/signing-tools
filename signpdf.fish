function signpdf --description "Sign a PDF using a smart card (PAdES)"
    if not set -q SIGNPDF_HOME; or not test -f "$SIGNPDF_HOME/signpdf.py"
        echo "Error: set SIGNPDF_HOME to the signp7m repository directory."
        return 1
    end
    if not set -q SIGNPDF_PYTHON; or not test -x "$SIGNPDF_PYTHON"
        echo "Error: set SIGNPDF_PYTHON to the Python executable in the signpdf environment."
        return 1
    end
    command "$SIGNPDF_PYTHON" "$SIGNPDF_HOME/signpdf.py" $argv
end
