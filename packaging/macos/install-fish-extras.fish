#!/usr/bin/env fish
# Install only missing files. Never read credentials or overwrite a setup.
argparse 'config-root=' -- $argv
or exit 2
if test (count $argv) -ne 0
    echo 'Usage: fish install-fish-extras.fish [--config-root PATH]'
    exit 2
end
set -l bundle (path dirname (path resolve -- (status filename)))
set -l config_root $__fish_config_dir
if set -q _flag_config_root
    set config_root "$_flag_config_root"
end
set -l function_file "$config_root/functions/signp7m.fish"
set -l config_file "$config_root/conf.d/signing-tools.fish"
set -l installed_new_function 0
umask 077
mkdir -p "$config_root/functions" "$config_root/conf.d"
or exit 1
if test -e "$function_file"; or test -L "$function_file"
    echo 'Existing signp7m function kept unchanged.'
else
    cp -n "$bundle/source/signp7m.fish" "$function_file"
    or exit 1
    chmod 600 "$function_file"
    or exit 1
    set installed_new_function 1
    echo 'Installed the signp7m Fish function.'
end
if test -e "$config_file"; or test -L "$config_file"
    echo 'Existing shared settings kept unchanged.'
else if test $installed_new_function -eq 1; and not set -q SIGNP7M_PIN_REF
    cp -n "$bundle/settings.example.fish" "$config_file"
    or exit 1
    chmod 600 "$config_file"
    or exit 1
    echo 'Created private settings template. Replace its reference placeholder before signing.'
else
    echo 'No settings file created: preserve the existing PIN-reference configuration.'
end
echo 'Read START-HERE.md before the first signing test.'
