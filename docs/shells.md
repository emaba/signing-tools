# Shell-independent commands

`signpdf`, `signp7m`, and `signing-tools` are Python package entry points.
Homebrew installs their executable links in its normal prefix. They work in
Fish, Zsh, Bash, other shells, and subprocess calls without sourcing a file.

Existing shell-function installations are migrated with `signing-tools migrate`.
Open a new Terminal afterwards so cached functions stop shadowing executables.
No shell startup edit or application-specific PATH entry is added.

See [installation and rollback](installation.md) and [unified configuration](configuration.md).
The old Fish and shell helper files remain only as historical source-checkout
compatibility material; they are not installed by the new formula.
