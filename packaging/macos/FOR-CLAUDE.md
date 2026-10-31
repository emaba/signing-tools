# Local installation brief for Claude

Use this brief only when the Mac owner explicitly asks you to install these
tools. The package itself does not authorize signing documents or accessing
secrets. Read `START-HERE.md` first; it is the authoritative human procedure.

## Suggested message from the user

> Install the signing tools from this extracted folder by following
> START-HERE.md and FOR-CLAUDE.md. Use Homebrew for the listed dependencies and
> the isolated installer for signpdf. Preserve any working signing setup.
> Never read, print or request my PIN, password, private key or recovery code.
> Leave private PIN entry, vendor/admin prompts and 1Password approval to me.
> Run only non-secret checks automatically; let me perform the first real
> signing test on the included sample. Report installed paths and test results.

## Scope

- Target macOS, preferably native Apple Silicon as used by the tested setup.
  This is local smart-card signing, not remote/cloud signing.
- Tested profile: InfoCert JSafe/DS4, SafeDive PKCS#11, token `CNS`, object ID
  `445334`. The P7M slot default `0x2` is reader-dependent and must be checked.
- Install root: `~/Library/Application Support/signp7m/`. Do not redirect the
  installation into unrelated directories when a required permission is denied.
- Fish commands are functions; installing Fish does not change the login
  shell. Use Fish explicitly. Do not run `chsh` or edit `/etc/shells`.
- Preserve existing functions, private settings and working dependencies.
  The extra helper only creates missing files. The PDF installer backs up an
  existing PDF function and retains previous releases.

## Workflow

1. Confirm the extracted folder and run `shasum -a 256 -c SHA256SUMS.txt`. The package has
   all source and no requirement for access to the author's private GitHub repo.
2. Check macOS support, native CPU architecture, existing Homebrew, Fish,
   Python 3.12, uv, OpenSSL, libp11, OpenSC and 1Password. Install missing listed
   dependencies using official Homebrew formulae/casks from START-HERE.md.
   No general upgrade, cleanup, unrelated uninstall or architecture switch.
3. If Homebrew is absent, use its official installation instructions. The
   user handles administrator/password prompts and required agreements.
4. Verify that the correct issuer middleware is installed. Use the official
   InfoCert driver page for this profile. Do not redistribute or silently
   substitute an unrelated SafeDive package. The user handles vendor prompts.
5. Run the PDF installer's plan, then installation after required filesystem
   permissions are available. Run `fish install-fish-extras.fish`. Keep the
   helper's existing-file decisions; do not overwrite them manually.
6. Guide the user through 1Password desktop setup. The user enters the correct
   signing PIN privately and copies the field's secret reference. They may
   edit the private settings file themselves. If they explicitly provide a
   reference identifier for configuration, use only that identifier, never a
   numeric PIN or a secret fetched from 1Password. Do not repeat the reference
   or configuration contents in your report.
7. Confirm the card profile and public slot ID locally. Never fetch the PIN to
   make a configuration check. If you run slot enumeration, capture its output
   locally and report only the needed reader/slot status, omitting serials and
   personal certificate information. If the profile differs, stop and obtain
   issuer-supported settings rather than guessing certificate or key IDs.
8. Load the Fish configuration, run `python3.12 check-setup.py`, and run both
   `--help` commands. An OpenSSL provider mismatch must be fixed by selecting
   compatible Homebrew components, never by disabling verification.
9. Ask the user to perform the included sample's PDF and P7M signing tests in
   their own Terminal and approve 1Password themselves. Do not sign a real
   document, automatically retry a wrong PIN or handle the user's approval.
10. Report actual installed paths, checks that passed/failed, whether sample
    signing was user-confirmed, and remaining compatibility/trust limitations.

## Secret-handling rules

- Do not use `op read`, `op inject`, raw `op item get`, clipboard inspection,
  screenshots of revealed fields, full environment dumps or credential export.
- Do not request account passwords, PINs, PUKs, OTPs or private keys in chat.
- Do not access a private key directly; signing is performed on the card.
- The tool's normal `op run` signing flow is the intended PIN delivery path.
  Do not resolve a PIN merely to test whether a reference exists.
- Do not enable APDU traces, PKCS#11 spy logging or verbose secret diagnostics.
- The only persistent PIN setting is an `op://...` identifier outside the
  source folder, in the private Fish configuration. Never write a literal PIN.
- A wrong/blocked-PIN message means stop and hand control to the owner.

## Files created for a fresh setup

- Isolated source/assets/venv/releases under Application Support/signp7m.
- `~/.config/fish/functions/signpdf.fish`: managed link.
- `~/.config/fish/functions/signp7m.fish`: created only if missing.
- `~/.config/fish/conf.d/signing-tools.fish`: reference/OpenSSL settings
  template, created only when a new configuration is needed; mode 600.

Do not silently modify the template after the user has configured it. For
updates/removal use the documented procedures, preserve pre-existing files,
and close active signing/placement sessions first.

## Explicitly outside scope

Reader firmware patches, `useIFDCCID` overrides, changing macOS accessory or
security policies, changing a card PIN, unblocking a card, trusting certificates
globally, disabling verification, signing production documents, or publishing
the user's configuration/documents.

The rendered PDF box is a visual appearance. Cryptographic integrity is
checked, while chain trust, revocation and trusted timestamps are not. Do not
describe a local PASSED result as independent legal/profile certification.
