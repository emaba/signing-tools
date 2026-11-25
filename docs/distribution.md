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

## Release and upgrade

After tests, tag the fully reviewed source commit and generate the formula
against that immutable revision. Commit the formula afterwards, then fast-forward
the tap's default branch so normal `brew tap`/`brew upgrade` sees the version.
Do not move a published tag. For application/dependency changes, increment the
package version and refresh pinned resources deliberately.

The owner installs and updates through Homebrew. ZIP distribution is no longer
part of the normal process. Existing source-bundle scripts are retained only as
an optional offline/historical maintenance path and are not installed by Brew.

```sh
brew tap emaba/signp7m https://github.com/emaba/signp7m.git
brew install emaba/signp7m/signing-tools
env HOMEBREW_DEVELOPER=1 brew test emaba/signp7m/signing-tools
```

Test the built wheel outside the checkout as well as editable development.
Verify native imports, assets, a synthetic sample/list-fields operation, both
signing pipelines with generated keys, safe configuration and migration.
`brew test` runs only non-secret package/runtime checks, not a hardware signature.
For the remote Git source, verify that version/revision checkout and offline
wheel building both pass. The public source repository requires no GitHub authentication.

## Publication boundaries

The repository formula references the private source tag. A public tap/PyPI
release, licence choice, or repository visibility change is a separate decision.
No secrets, actual documents, personal certificates or configuration are release
inputs. The example op:// reference is a placeholder only.

## Initial 0.1.0 migration acceptance (November 25, 2026)

The owner installed the local formula on Apple Silicon through Homebrew and
reported that its formula test passed. All three installed commands resolved
to the formula's private runtime. Runtime checks, native imports, bundled assets,
unsigned sample generation and PDF field listing passed. The application code
also passed 137 automated Python checks and seven UI tests; 67 PDF tests passed
against an installed wheel outside the checkout. A subsequent release-metadata
regression test passed as well.

The explicit migration retired two legacy Fish files, retained exact backups
and the previous application, and created mode-600 reference-only configuration.
Full doctor/provider checks and the read-only rollback plan passed. No PIN was
resolved, no 1Password authentication was invoked, and no hardware signature was
performed as part of this migration. The first signature with the new installed
entry points remains an owner-run acceptance check.

Homebrew upgraded its required build tool uv from 0.13.9 to 0.13.10. Its plain
`brew test` also enabled persistent developer mode; `brew developer off` restores
that setting. Future diagnostic examples use `HOMEBREW_DEVELOPER=1` for that
single process to avoid changing the persistent mode.
