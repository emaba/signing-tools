# Build and maintain the CLI distribution

## Package and dependencies

`pyproject.toml` defines the standard wheel/source package and three console
entry points. It includes the preview HTML/CSS/JS, cursive font and its licence.
`requirements-runtime.lock` preserves the exact runtime versions tested in the
previous installation. New package versions must keep tests/hardware acceptance
separate from dependency upgrades.

The initial third-party formula uses checked upstream wheels for Apple Silicon
macOS 13+ / CPython 3.12. `cryptography==50.0.2` has no upstream Intel macOS
wheel, so this formula deliberately restricts architecture rather than claiming
untested Intel support. Native source builds or a separately verified Intel
lock can be added later. This wheel-based private tap is not a Core submission.
No application code/dependencies are fetched dynamically at runtime.

## Development and validation

From a checkout, use a private Python 3.12 environment:

```sh
uv venv --python python3.12 .venv-cli
uv pip install --python .venv-cli/bin/python -c requirements-runtime.lock -e .
.venv-cli/bin/python -m unittest discover -s tests
node --test tests/test_placement_ui.cjs
```

Migration tests use synthetic homes and reference metadata, including failed
activation, changed paths, rollback and restoration. Cryptographic tests use
synthetic keys; no real PIN, card or 1Password session is used.

## Homebrew resources and formula

Install `packaging` in a development environment for resource selection, then:

```sh
python scripts/collect_homebrew_resources.py
python scripts/generate_homebrew_formula.py --revision SOURCE_COMMIT --tag v0.1.0
```

The collector selects compatible wheels from official PyPI metadata and records
the exact URL and SHA-256. Missing wheels fail the build instead of silently
resolving another version. Review changes to `homebrew/resources.json`.
The formula installs all resources in its private `libexec`, builds the project
offline with the pinned backend, and exposes only console executables in `bin`.
Homebrew manages upgrades, links and removal; user configuration is external.

Tag the fully reviewed source commit. The formula can be committed afterwards
and point to that immutable tag/revision without a circular source hash.
The repository remains private; tag publication does not change visibility.

## Release bundle

Commit reviewed changes before generating artifacts. In the development env:

```sh
python scripts/build_cli_release.py --ref HEAD --output-dir dist
```

The builder uses a committed Git archive, builds wheel/sdist with the commit's
SOURCE_DATE_EPOCH, and includes a local-tap helper, exact resource metadata,
English instructions, package provenance and per-file/outer checksums. It
never reads user configuration. The old PDF-guide bundle builder is retained
for reproducing historical releases; new CLI distributions use this builder.

From an extracted release:

```sh
shasum -a 256 -c SHA256SUMS.txt
python3.12 prepare-local-tap.py
brew tap emaba/signing-tools-local "$PWD/homebrew-tap"
brew install emaba/signing-tools-local/signing-tools
brew test emaba/signing-tools-local/signing-tools
```

The local formula uses the supplied source archive and SHA-256, so GitHub read
access is unnecessary. Keep the package for future rebuilds. Runtime operation
does not depend on the extracted Downloads directory.

Test the built wheel outside the checkout as well as editable development.
Verify native imports, assets, a synthetic sample/list-fields operation, both
signing pipelines with generated keys, safe configuration and migration.
`brew test` runs only non-secret package/runtime checks, not a hardware signature.

## Publication boundaries

The repository formula references the private source tag. A public tap/PyPI
release, licence choice, or repository visibility change is a separate decision.
No secrets, actual documents, personal certificates or configuration are release
inputs. The example op:// reference is a placeholder only.
