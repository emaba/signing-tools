function signpdf --description "Sign a PDF using a smart card (PAdES)"
    # Resolve the autoload symlink to its immutable installed release.
    set -l app_dir
    if set -q SIGNPDF_HOME
        set app_dir "$SIGNPDF_HOME"
    else
        set app_dir (path dirname (path resolve -- (status filename)))
    end
    set -l python "$app_dir/.venv-signpdf/bin/python"
    if test -x "$app_dir/../venv/bin/python"
        set python (path dirname "$app_dir")/venv/bin/python
    end
    if set -q SIGNPDF_PYTHON
        set python "$SIGNPDF_PYTHON"
    end
    if not test -f "$app_dir/signpdf.py"
        echo "Error: install signpdf or set SIGNPDF_HOME to the repository directory."
        return 1
    end
    if not test -x "$python"
        echo "Error: install the signpdf environment or set SIGNPDF_PYTHON."
        return 1
    end
    command "$python" "$app_dir/signpdf.py" $argv
end
