# Installation brief for an assistant

Read quick-start.md. Install only when explicitly requested by the Mac owner.
Use the remote Homebrew tap documented in quick-start.md.
The application is a Python CLI, not a Fish/Zsh function collection. Do not
install Fish, change login shells, edit PATH or add source lines.

1. Verify Apple Silicon/macOS compatibility. The public tap needs no GitHub
   credentials. Preserve working
   Homebrew, Python, 1Password and signing dependencies; do not perform general
   upgrades, cleanup or unrelated removals.
2. Use brew tap and brew install from quick-start.md; no ZIP is needed.
   Inspect the installation plan and allow
   only required filesystem permissions. Do not redirect an installation to
   unrelated paths to bypass a denied permission.
3. Verify the issuer-supported PKCS#11 middleware and native architecture.
   Leave vendor/admin prompts to the owner. Do not modify firmware/useIFDCCID.
4. Existing setup: run signing-tools migrate --plan, review its status-only
   output, then migrate. It extracts only reference identifiers/settings and
   backs up retired legacy files. Never dump those files or the new TOML.
5. Fresh setup: the owner enters their correct signing PIN privately in a
   concealed 1Password field, enables CLI integration and copies its secret
   reference. The configure prompt accepts only that reference. Never fetch,
   print, request or validate the actual PIN, PUK, password or private key.
6. Run signing-tools doctor and both --help commands. These checks do not
   access the PIN or log in to the card. Keep serials and certificate metadata
   out of reports; inspect public slot status locally only when needed.
7. Ask the owner to perform the first real sample signatures and approve
   1Password themselves. Do not sign production documents or retry a wrong PIN.
8. Report actual installed commands/paths, migration/backup status and checks.
   Distinguish software tests from owner-confirmed hardware signing.

Never use op read, op inject, raw op item exports, clipboard inspection,
PKCS#11 spy/APDU traces, screenshots of revealed credentials or full environment
dumps. Only the normal op run signing child resolves the reference. The private
key stays on the card. No publication or repository visibility change is authorised
by this brief. Use documented rollback and preserve private configuration.
