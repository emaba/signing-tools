# Pre-publication security and privacy review — November 25, 2026

## Scope and result

The review covered all reachable branches and tags, including deleted/replaced
files, the installed CLI source, browser preview, credential handoff, dependency
pins, Homebrew formula and distribution inputs. The initial history contained
21 commits and 167 distinct file blobs. The final publication candidate was
scanned again after changes and identity rewriting.

No actual PIN, password, access token, private key, certificate, signed/original
user document, diagnostic dump, owner home-directory path or private network
address was found in the reviewed content. The owner's configured 1Password
reference was compared privately against all historical blobs and had no matches.
Only placeholder/synthetic references occur in source/tests. No reference values
or personal configuration are included in this report.

The only historical binary is the unmodified, publicly distributed Kaushan
Script font. Its upstream provenance and SIL OFL attribution are preserved.
Email addresses in that third-party licence are public copyright attribution;
example addresses and Git SSH URLs are not owner credentials.

## Findings and corrections

1. Git author/committer metadata contained a non-public personal email address.
   At the owner's request, names/emails in the publication history were replaced
   with the public GitHub handle and its GitHub noreply address. The original
   repository remains a separate private history archive; the public repository
   is populated from the rewritten history, not a fork of the original network.
   This avoids publishing old metadata through leftover original commit objects.
2. The initial runtime lock had 109 advisory records affecting Pillow 12.3.0 and
   pypdf 6.10.0. Not every vulnerable code path is necessarily reachable through
   this application, but those versions were unsuitable for the public release.
   Release 0.1.1 pins Pillow 13.0.0 and pypdf 7.1.1 and refreshes PDFium's wrapper
   to pypdfium2 5.15.2. Checksummed ARM64 resources were regenerated from official
   PyPI metadata. The signing engine remains pyHanko 0.38.0.
3. The configuration prompt now refuses to continue if hidden terminal input is
   unavailable. The PDF signing child also drops inherited PIN-variable values
   before assigning its one intended reference. Synthetic regression tests cover
   both cases; no real credentials were used.

Gitleaks 8.30.1 reported one generic-key match in the legacy-settings map:
`SIGNP7M_KEY_URI` is a configuration variable name, not a credential. It was
manually reviewed and classified as a false positive. No broad scanner exclusion
was added. Bandit reported only low-severity subprocess/path warnings: calls use
argument arrays without a shell; installed native tools use the formula's pinned
dependency paths. Explicit local overrides and trusted PATH remain user authority.

## Validation

- Full-history and working-tree secret scans used complete redaction in reports.
- pip-audit checked all 27 runtime packages plus the pinned setuptools build
  backend: no known vulnerabilities and no skipped packages at review time.
- All 140 Python tests and seven interface tests passed; 67 PDF tests also
  passed against an independently installed 0.1.1 wheel. Automated checks cover
  synthetic CAdES/PAdES signatures, prior-signature and
  modification checks, incompatible PDFs, hostile browser requests, loopback
  binding, server closure before authentication, migration and rollback.
- The preview accepts no signing/PIN endpoint, serves only predefined resources
  and renders text as text. It binds exclusively to IPv4 127.0.0.1, requires a
  random capability URL, rejects foreign origins/hosts and uses no external UI
  resources. JSON submission size and socket timeouts are bounded.
- Temporary signing directories are private; outputs are published only after
  cryptographic/integrity checks. The private key stays on the card.
- User configuration and migration backups remain outside Git and the Cellar.

## Review dimensions

| Dimension | Rating | Evidence and practical limits |
| --- | --- | --- |
| Security | Reviewed; identified issues corrected | [Hidden-input configuration](../src/signing_tools/cli.py#L40), [credential handoff](../src/signing_tools/signpdf.py#L499), [private workspace](../src/signing_tools/signpdf.py#L536), and [loopback request checks](../src/signing_tools/signpdf_picker.py#L120). No unresolved high/medium finding in this review; this is not a security guarantee. |
| Performance | Adequate for a local tool; not benchmarked | [Rendering](../src/signing_tools/signpdf_picker.py#L77) limits image dimensions and retains only two page images. Native parsing/rendering of a malicious document is not covered by an application-wide execution-time limit. |
| Correctness | Automated regression passed | [Signature verification](../src/signing_tools/signpdf.py#L381), synthetic cryptographic fixtures, tampering rejection and prior-signature checks. Hardware acceptance remains owner-run. |
| Maintainability | Improved | Standard console entry points, one user configuration, Homebrew ownership, and checked [migration](../src/signing_tools/migration.py#L157)/[rollback](../src/signing_tools/migration.py#L220) with private backups. |

## Publication and owner-installation postflight

The new repository was verified as public without authentication. An original
private-history commit was unavailable anonymously. Only rewritten branches and
the reviewed 0.1.1 tag were uploaded; the original remains a separate private,
archived repository. No old Git identity or private reference was present in the
new local object database, including unreachable objects.

The owner then re-created the tap, installed 0.1.1 from the public Git source,
and passed `brew test`. Homebrew verified the source and all wheel resources.
Read-only postflight confirmed all three executable links target 0.1.1, the
installed receipt initially names `emaba/signp7m` (before the project rename), all full doctor/provider checks pass,
the temporary local tap is removed, personal configuration is byte-identical,
and the rollback plan remains valid. No PIN resolution, card login or signature
was requested during these checks. Open a new terminal to discard old functions
already loaded in an existing shell.

## Repository rename and 0.1.2 postflight

The active public repository is now
[emaba/signing-tools](https://github.com/emaba/signing-tools). The original public
URL redirects to it, retaining the same repository identity and history.
Release 0.1.2 updates package repository metadata, formula source/homepage,
installation instructions and the active Git remote. Runtime dependencies and
signing behaviour are unchanged from the reviewed 0.1.1 release.

The owner installed the new `emaba/signing-tools/signing-tools` formula, passed
`brew test`, and removed the previous `emaba/signp7m` tap. Read-only postflight
confirmed all three commands resolve to 0.1.2, the installed package metadata
points to the renamed repository, all doctor/provider checks pass, personal
configuration is byte-identical and the rollback plan remains valid. The nine
packaging checks passed, the secret scan retained only the previously reviewed
variable-name false positive, and all commit emails still use GitHub noreply.
These checks did not resolve a PIN or request a card login/signature.

## Current-tree simplification (0.1.3)

The current source tree was reduced from 70 to 43 tracked files. Obsolete shell
scripts, compatibility launchers, standalone installers, ZIP/PDF bundle builders,
duplicate requirements and their installation-only tests were removed. Current
CAdES tests now invoke the installed Python CLI directly, retaining the contract
and generated-key CMS verification without requiring Fish. PAdES, credential,
preview and migration tests remain. All 110 current Python tests and seven UI
tests passed; the built wheel contains the package and required assets without
legacy shell launchers. Historical implementations remain in Git history.

The simple Homebrew guide now lives in [quick-start.md](quick-start.md); the
[assistant brief](assistant-installation.md) is separate from obsolete packaging.
This source cleanup changes dependency-repair instructions but not the signing
algorithm, credential resolution or loopback restriction.

## Owner cleanup postflight

The owner upgraded to 0.1.3 and passed `brew test`. A transactional owner-run
cleanup moved 27 identified legacy applications, checkouts, installers and test
artifacts (about 1.1 GiB apparent size) to a private Trash folder with a recovery
manifest. It verified configuration bytes before/after and ran the full doctor
without resolving a PIN. Signed user test PDFs and the active checkout were kept.

Read-only postflight confirmed the old application/work directory and retired
migration files are absent, the only active user settings file is mode-600
`config.toml`, and only 0.1.3 remains installed in the Cellar. Package-scoped
Homebrew cleanup removed the previous package/cache (reported 89.3 MB). Homebrew
developer mode is disabled and its checkout is stable 7.0.16. Trash contents
remain recoverable; their space is released only on permanent deletion.
The current CLI no longer has an active legacy rollback record; restoring that
old setup would require recovering its retired application and migration files.

## Limits and continued maintenance

This is an evidence-based review, not a proof that the program or every native
component is vulnerability-free. Advisory databases change; Python-package
advisories do not exhaustively audit bundled PDFium/native code, vendor middleware,
1Password, Homebrew dependencies or macOS. A compromised account, root process,
malicious local tool/font/middleware or browser extension is outside the protection
provided by a loopback URL. Process memory and crash/snapshot secure erasure are
not guaranteed. Document trust, revocation and trusted timestamps are not validated.
See [SECURITY.md](../SECURITY.md).

Repeat dependency and full-history secret scans before releases. Keep all release
resources checked by SHA-256, maintain a private reference-only configuration,
and use synthetic documents/keys for automated tests. Hardware acceptance and
1Password authorisation remain owner-run steps.

## Primary references

- [GitHub: removing sensitive data and cached-history limits](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)
- [pypdf releases/security advisories](https://github.com/py-pdf/pypdf/security/advisories)
- [Pillow security advisories](https://github.com/python-pillow/Pillow/security/advisories)
- [Homebrew: private source download authentication](https://docs.brew.sh/FAQ#how-do-i-authenticate-private-git-source-downloads)
- [Gitleaks](https://github.com/gitleaks/gitleaks), [pip-audit](https://github.com/pypa/pip-audit), [Bandit](https://github.com/PyCQA/bandit)
