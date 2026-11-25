# Installation brief for an assistant

Read [the complete quick start](quick-start.md). Install only when explicitly
requested by the Mac owner. Use the remote Homebrew tap documented there.
The application is a Python CLI, not a Fish/Zsh function collection. Do not
install Fish, change login shells or add application source lines. For a missing
Homebrew installation only, let the owner follow the official installer's printed
shell setup; do not add a separate signing-tools PATH modification.

1. Verify Apple Silicon/macOS compatibility and Command Line Tools. Current
   supported Homebrew setup requires macOS 15+; the formula's minimum alone is
   not an end-to-end support guarantee. The public tap needs no GitHub
   credentials. Preserve working
   Homebrew, Python, 1Password and signing dependencies; do not perform general
   upgrades, cleanup or unrelated removals.
2. Use brew tap and brew install from quick-start.md; no ZIP is needed.
   Inspect the installation plan and allow
   only required filesystem permissions. Do not redirect an installation to
   unrelated paths to bypass a denied permission.
3. Follow [Install SafeDive and connect the card](quick-start.md#3-install-safedive-and-connect-the-card)
   for an issuer-confirmed InfoCert JSafe card: official InfoCert drivers page,
   macOS SafeDive `.pkg`, normal macOS Installer, expected library file check.
   Verify middleware/native architecture compatibility without running a card
   login. Leave vendor/admin prompts to the owner. Do not install a Bit4id kit
   for a JSafe card by guesswork, bypass macOS security checks or modify
   firmware/useIFDCCID. Other cards require their own supported middleware/profile.
4. Existing setup: run signing-tools migrate --plan, review its status-only
   output, then migrate. It extracts only reference identifiers/settings and
   backs up retired legacy files. Never dump those files or the new TOML.
5. Fresh setup: the owner enters their correct signing PIN privately in a
   concealed 1Password Password field, enables CLI integration and uses that
   saved field's Copy Secret Reference menu. Run the default configure wizard;
   let the owner select the library, card and signing certificate locally,
   confirm the issuer's key ID and approve the complete summary. The key URI
   is derived consistently for P7M. Public certificate discovery uses read-only
   sessions without login, with a timeout; it does not verify the actual private
   key. If discovery is unavailable, use --manual with issuer-confirmed values.
   The hidden reference prompt accepts only that reference. Never fetch,
   print, request or validate the actual PIN, PUK, password or private key.
6. Run signing-tools doctor and both --help commands. These checks do not
   access the PIN or log in to the card. Keep serials and certificate metadata
   out of reports; inspect slot status locally without login only when needed.
   Doctor checks neither the actual PIN nor the card/key/slot selection. Verify
   the configured profile matches the owner's card; slot IDs are not list indices.
7. Ask the owner to perform the first real sample signatures and approve
   1Password themselves. Do not sign production documents or retry a wrong PIN.
8. Report actual installed commands/paths, migration/backup status and checks.
   Distinguish software tests from owner-confirmed hardware signing.

Never use op read, op inject, raw op item exports, clipboard inspection,
PKCS#11 spy/APDU traces, screenshots of revealed credentials or full environment
dumps. Only the normal op run signing child resolves the reference. The private
key stays on the card. No publication or repository visibility change is authorised
by this brief. Use documented rollback and preserve private configuration.
