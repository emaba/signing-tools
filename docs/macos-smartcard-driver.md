# macOS smart-card reader driver workaround

## Recorded state

On October 27, 2026, selecting the system-provided IFD CCID reader driver
allowed two consecutive signing operations to succeed with a Generic EMV
reader that had repeatedly failed with Apple's `usbsmartcardreaderd` driver.
The owner reported leaving the preference enabled.

On October 28, the owner rolled the change back: deleting the domain left an
empty 42-byte plist, which was then moved to
`com.apple.security.smartcard.plist.disabled-20261028` in the same directory.
The owner confirmed that the active `.plist` path was absent. A post-reboot
check and accessory-authorization test have not yet been reported.

On October 30, a read-only check again found no active preference file and no
`useIFDCCID` override; the disabled backup remained present. The owner then
confirmed that the newly purchased reader worked. This is owner-reported
functional evidence without the configured workaround. The reader model,
loaded driver, post-reboot state, and long-term reliability were not captured
in that confirmation. The workaround was not re-enabled.

This is a recorded workstation configuration change, not an installation step
required by `signp7m`. The function does not apply this setting automatically.

| Item | Recorded value |
| --- | --- |
| Reader manufacturer string | `Generic` |
| Reader product string | `EMV Smartcard Reader` |
| USB vendor/product IDs | `058f:9540` |
| USB product revision (`bcdDevice`) | `0x0120`, displayed as `1.20` |
| Previous preference | Domain/key absent in the owner's `defaults read` output |
| Applied preference | `useIFDCCID = true` |
| Scope | Machine-wide smart-card reader driver selection |
| Validation | Two consecutive successful signatures reported by the owner |
| Not yet validated | Signing after reboot; other readers with the new preference; long-term reliability |

Apple also documents an accessory-authorization interaction with this
preferences file at startup on supported Macs. That consequence has not been
tested on the owner's Mac. Read **Accessory authorization** below before
keeping the workaround as a permanent configuration.

The identifiers and revision match the libccid AU9540 reference descriptor.
They do not establish the exact physical board or a firmware upgrade target.
The USB product revision is not independent proof of the firmware version.
Local inspection during the investigation found the bundled IFD CCID driver
version `1.5.1` and a matching `058f:9540` entry. This does not establish that
the same driver version is present on every Mac.

## What the command changes

```fish
sudo defaults write /Library/Preferences/com.apple.security.smartcard useIFDCCID -bool YES
```

- `sudo` authorizes writing a system preference.
- `defaults write` stores or updates a preference key.
- `/Library/Preferences/com.apple.security.smartcard` selects the system
  preferences domain, normally backed by the corresponding `.plist` file.
- `useIFDCCID` selects the alternative IFD CCID reader driver path.
- `-bool YES` stores a Boolean true value.

The command updates this key, preserving any unrelated keys in the domain.
It selects an already installed reader driver; it does not install software,
change reader firmware, modify the smart card, change its PIN, export keys,
enable APDU logging, or change OpenSSL signature verification options.
SafeDive remains the card middleware used by `signp7m`.

The preference persists across shell sessions and reboots unless another
action changes or removes it. It is not limited to this function, reader,
USB port, or user account. Reconnect readers after changing it so that driver
selection can take effect. If behavior remains ambiguous, reboot and verify
again rather than assuming the new driver has loaded.

## Evidence and interpretation

Before the change, the owner reported that a Gemplus reader successfully
signed with the same JSafe card, SafeDive middleware, and installed function.
The Generic EMV reader failed and reportedly required USB disconnection to
recognize the token again; its LED turned red during the failure.

Two error captures from the Generic reader began with:

```text
Inbound chain: continuation reply has unexpected messageType (frame 2)
```

These were followed by failed APDU transfers and
`Error Domain=CryptoTokenKit Code=-2`. The first capture showed the USB status
`0xe0005000 (pipe stalled)`. The second showed nine USB timeouts with
`0xe00002d6 (timeout)` and ten failed APDU exchanges spanning about 46 seconds,
with intervals of about 5.1 seconds. The application reported `CMS_final`
failure. These captures identify communication failures, not their precise
firmware or driver implementation cause.

After setting `useIFDCCID` and reconnecting, the reader appeared as
`Alcor Micro AU9540`. This name change is consistent with the alternative
driver, but the name alone is not an independent trace of driver loading.
The owner supplied two consecutive runs with all of the following results:

```text
Signature completed successfully.
Cryptographic verification: PASSED
Document integrity: PASSED
CAdES attribute: PRESENT
```

This provides functional evidence that changing the reader driver avoided the
observed failure in those two runs. It does not prove that the firmware has no
defects or guarantee future reader compatibility. These hardware results came
from the owner's installed function; they are not a separate hardware
acceptance test of every repository revision.

The libccid project lists AU9540 under unsupported or partly supported readers,
with a report of unexpected card power-off. That is a separate historical
issue, not proof that power-off caused this incident. IOGEAR EEPROM procedures
for certain branded models are not validated for this generic reader and must
not be treated as a firmware patch for it.

## Possible effects

Other smart-card applications and readers on this Mac may use the selected
driver as well. Compatibility, timing, supported controls, or reader names can
differ, and middleware slot selection may need checking if hardware changes.
The two successful runs establish compatibility only for the tested setup.

The command does not disable System Integrity Protection, macOS signature
checks, or card PIN authentication. It does change which reader driver handles
communication, so it should be an explicit troubleshooting choice rather than
an unconditional setup command for all users.

The setting does not pin a particular driver build. After macOS updates or a
reader replacement, verify the preference and perform a signing test again.

### Accessory authorization

Apple's deployment documentation states that accessory security does not
function if `/Library/Preferences/com.apple.security.smartcard.plist` is
detected at startup. Apple describes this file in the context of smart-card
configuration profiles. Its separate accessory-access guide identifies the
Mac feature as applying to Apple-silicon laptops running macOS 13 or later.

The command in this note creates or updates that same file. Because Apple's
condition is expressed in terms of file presence, the manually created file
must be treated as potentially having the same effect. This is an inference
from the documented condition, not a measured result on this Mac. Successful
signatures do not validate accessory authorization after reboot.

The potentially affected protection asks permission before new USB,
Thunderbolt, or supported SD accessories communicate with the Mac. This is
separate from signature verification, PIN authentication, and System Integrity
Protection. Do not describe the workaround as having no security effects.
Prefer a reader that works with the default driver when that avoids retaining
this global override and file. Do not change the owner's configuration
automatically based on this note.

## Check or reproduce deliberately

Read only the relevant preference; do not dump card contents or credentials:

```fish
defaults read /Library/Preferences/com.apple.security.smartcard useIFDCCID
```

`1` means the preference is enabled. A missing domain/key means no explicit
override is stored; it is not a complete report of the running driver. Record
the original value before making a change on another machine.

To reproduce the recorded workaround, close applications using the card,
disconnect smart-card readers, run the write command above, and reconnect only
the reader being tested. Reopen the required middleware application and run
`signp7m` against a disposable, non-sensitive PDF. Require the four successful
results above. Repeat signing without disconnecting the reader between runs.
Also test after reboot and with other readers used on the machine.

Stop if the card reports an incorrect PIN or locked-card condition; repeated
PIN failures are not a useful driver test. Do not enable raw APDU/PKCS#11
payload logging or supply PINs, private keys, secret references, or document
contents when documenting results. Raw logs and signed documents are not
needed in this repository.

## Restore the recorded original state

The original preference was absent, so restore that state by removing only
the added key. Close applications using the card and disconnect readers first:

```fish
sudo defaults delete /Library/Preferences/com.apple.security.smartcard useIFDCCID
```

Reconnect readers afterward, and verify signing with the intended reader.
A subsequent `defaults read` should report a missing key/domain. This removes
the explicit override and lets macOS apply its default selection policy; it
does not assert which driver every macOS version chooses by default.

Removing the key is the driver-preference rollback. It is not proof that the
backing file has disappeared or that accessory authorization is restored.
Check file presence without displaying its contents, in Fish:

```fish
if test -e /Library/Preferences/com.apple.security.smartcard.plist
    echo "Smart-card preference file still exists."
else
    echo "Smart-card preference file is absent."
end
```

If the file remains, restoring the original file-absent state requires
confirming that no other settings or management profile need it, then
preserving/removing that file deliberately. Do not remove it blindly.
Restart and validate accessory authorization separately on supported Macs.

Do not delete the entire preferences domain or `.plist` file. On another Mac
where the key already existed, restore its recorded value instead of deleting
it. For a recorded Boolean false value:

```fish
sudo defaults write /Library/Preferences/com.apple.security.smartcard useIFDCCID -bool NO
```

## References

- Local macOS manual: `man 7 SmartCardServices`, section
  **USB SMART CARD READER DRIVERS**.
- [Reader driver selection explained by the libccid author](https://blog.apdu.fr/posts/2023/11/apple-own-ccid-driver-in-sonoma/).
  This article describes Sonoma; consult the local manual and test on the
  installed macOS version.
- [AU9540 reference USB descriptor](https://github.com/LudovicRousseau/CCID/blob/master/readers/AU9540.txt).
- [libccid reader limitations](https://ccid.apdu.fr/ccid/unsupported.html).
- [Apple: smart-card integration and accessory security](https://support.apple.com/guide/deployment/intro-to-smart-card-integration-depd0b888248/web).
- [Apple: accessory access on Apple-silicon Mac laptops](https://support.apple.com/guide/deployment/manage-accessory-access-depf8a4cb051/web).

This note records a successful workaround; it does not establish certificate
trust, revocation status, timestamping, or legal signature validity. See the
README's verification limits.
