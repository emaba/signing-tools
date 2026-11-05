# Recreate the macOS installation package

The shareable package is generated from a **committed local Git snapshot**.
It does not require GitHub access at build/install time. Untracked files and
working-tree edits are never included. Commit reviewed changes before building.

## Maintained inputs

- `packaging/macos/START-HERE.md`: practical English installation guide,
  including Homebrew dependencies, SafeDive, 1Password and sample signing.
- `packaging/macos/FOR-CLAUDE.md`: bounded installation handoff for an assistant;
  PIN entry and 1Password approval remain with the owner.
- `packaging/macos/install-shell-extras.py` and `settings.example.sh`: fresh
  Zsh/Bash configuration without Fish. The primary guide uses this integration.
- `packaging/macos/install-fish-extras.fish`: creates missing P7M/config files
  while preserving existing functions and reference settings.
- `packaging/macos/settings.example.fish`: reference-only template and matched
  Homebrew OpenSSL selection. Never put a real reference or PIN in this file.
- `packaging/macos/check-setup.py`: status-only checks without resolving a PIN,
  contacting 1Password or requesting a card login.
- `scripts/render_setup_guide.py`: PDF guide and unsigned sample renderer.
- `scripts/build_macos_bundle.py`: Git snapshot, metadata, manifests and ZIP.

Generated PDFs, ZIPs, checksums and build environments are not committed.
The distribution builder does not change a signing installation or macOS
preferences and does not read the user's Fish configuration or credentials.

## Build on macOS

Use an existing Python 3.12 and uv. From the repository in Fish:

```fish
uv venv --python python3.12 .venv-packaging
uv pip install --python .venv-packaging/bin/python -r requirements-packaging.txt
.venv-packaging/bin/python scripts/build_macos_bundle.py \
    --ref HEAD --date 2026-11-05
```

The example date is the compatible-parsing package date. For an older handoff,
select its recorded source commit and build date together. For a newer release,
provide the intended ISO build date, or omit `--date` to use the selected
commit's date. `--ref` also accepts a reviewed tag or commit SHA.

The output defaults to `dist/` and can be changed with `--output-dir PATH`:

```text
dist/signing-tools-macos-2026-11-05.zip
dist/signing-tools-macos-2026-11-05.zip.sha256
```

The ZIP has one top-level `signing-tools-macos` folder. It contains the complete
committed source, guide in PDF and Markdown, Claude brief, helpers/settings
template, unsigned three-page sample, `PACKAGE-INFO.json`, and `SHA256SUMS.txt`.
The metadata records the exact source commit, build date, renderer version,
font hashes and PDF page counts. Runtime dependencies are downloaded by the
documented Homebrew/Python steps; vendor middleware and 1Password are not
redistributed. This is not an offline installer.

Fish is not a runtime dependency of the primary Zsh/Bash setup. The ZIP also
retains the optional Fish files for existing users. The Python CAdES port uses
the same OpenSSL/PKCS#11 pipeline and requires a first recipient-run hardware
sample test, separately from the generated-key software and shell tests.

The default document fonts are the existing macOS Arial, Arial Bold and Menlo
files. Their used subsets are embedded in the PDF; full system font files are
not put in the ZIP. Other hosts can explicitly supply local font files:
`--sans-font PATH --bold-font PATH --mono-font PATH`.

For the same commit, date, font bytes, pinned libraries and build environment,
the PDF metadata and ZIP timestamps/order/permissions are deterministic.
Different font files or rendering/compression libraries can change the output;
the metadata makes the relevant inputs inspectable.

## Verify and review

```fish
cd dist
shasum -a 256 -c signing-tools-macos-2026-11-05.zip.sha256
```

After extracting the ZIP, run `shasum -a 256 -c SHA256SUMS.txt` from its
top-level folder. The builder checks ZIP integrity and the structure of both
PDFs. It rejects source symlinks, development directories, local credential
filenames, source documents/certificate/key files and PEM private-key headers.
These guards complement review of the selected source revision; they are not
a general secret scanner or a publisher signature.

Render and visually inspect the resulting guide before sharing an updated
package, especially after changing text, fonts or layout. The guide is six
pages in the original layout; do not truncate it merely to retain that count.
Confirm that all commands remain readable and copy correctly from the PDF.
No card, PIN or real signed document is needed to build/review the package.

Tests, from the repository root with runtime and packaging requirements installed:

```fish
.venv-signpdf/bin/python -m unittest discover -s tests -v
node --test tests/test_placement_ui.cjs
fish --no-config --no-execute packaging/macos/install-fish-extras.fish
fish --no-config --no-execute packaging/macos/settings.example.fish
```

Distribution tests cover helper preservation/private file mode, preflight
non-disclosure, source snapshot isolation, unsafe-file rejection, manifest
validation and two byte-identical builds. Rendering integration tests require
ReportLab and the default macOS fonts; read skip results before claiming a
successful build. The original source's 78 Python/four UI results and hardware
tests are historical evidence, not a fresh test of another person's card.
