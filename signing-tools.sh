# Source this file from Zsh or Bash; Fish is not required.
_signing_tools_run() (
    # Settings and provider PATH changes remain inside this subshell.
    _signing_root=${SIGNING_TOOLS_ROOT:-"$HOME/Library/Application Support/signp7m"}
    _signing_config=${SIGNING_TOOLS_CONFIG:-"$HOME/.config/signing-tools/settings.sh"}
    if [ -r "$_signing_config" ]; then
        . "$_signing_config" || exit 1
    fi
    case "$1" in
        signpdf|signp7m) _signing_script="$1.py" ;;
        check) _signing_script="packaging/macos/check-setup.py" ;;
        *) return 2 ;;
    esac
    shift
    if [ ! -x "$_signing_root/current/venv/bin/python" ]; then
        printf '%s\n' 'Error: install the signing tools before using these commands.' >&2
        exit 1
    fi
    # Resolve current once so an update cannot mix an old interpreter with new code.
    _signing_release=$(CDPATH= cd -- "$_signing_root/current" && pwd -P) || exit 1
    command "$_signing_release/venv/bin/python" "$_signing_release/app/$_signing_script" "$@"
)
signpdf() { _signing_tools_run signpdf "$@"; }
signp7m() { _signing_tools_run signp7m "$@"; }
signing_tools_check() { _signing_tools_run check "$@"; }
