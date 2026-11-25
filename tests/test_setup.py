"""Guided configuration uses synthetic public certificates, never card PINs."""

from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from signing_tools import cli, config, setup


CARDS = [dict(slot='0x7', reader='Synthetic reader', token_label='Test; card', unavailable=False,
              certificates=[dict(id='0102', label='Signing', name='Synthetic signer',
                                 expires='2099-01-01', valid=True, purpose='content commitment / signing')])]


class WizardTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='signing-setup-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.path = self.root / 'private/config.toml'
        self.module = self.root / 'middleware.dylib'
        self.module.touch()
        self.reference = 'op://SYNTHETIC_PRIVATE_METADATA/Item/Field'

    def configure(self, answers, *, args=(), reference=None):
        output = io.StringIO()
        with patch.dict(os.environ, {'SIGNING_TOOLS_CONFIG': str(self.path)}), \
             patch('getpass.getpass', return_value=self.reference if reference is None else reference), \
             patch('builtins.input', side_effect=answers), \
             patch.object(setup, 'library_path', return_value=str(self.module)), \
             patch.object(setup, 'discover', return_value=CARDS) as discovery, \
             redirect_stdout(output), redirect_stderr(output):
            code = cli.main(['configure', *args])
        self.assertNotIn(self.reference, output.getvalue())
        return code, output.getvalue(), discovery

    def test_default_wizard_saves_coherent_profile_with_confirmation_and_private_mode(self):
        code, output, discovery = self.configure(['1', '1', '', 'y'])
        self.assertEqual(code, 0, output)
        settings = config.load(self.path)['signing']
        self.assertEqual(settings, dict(pin_reference=self.reference, module=str(self.module), slot='0x7',
                                       token_label='Test; card', certificate_id='0102', key_id='0102',
                                       key_uri='pkcs11:token=Test%3B%20card;id=%01%02;type=private', raw_mechanism=False))
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        discovery.assert_called_once_with(str(self.module))

    def test_distinct_certificate_and_private_key_ids_are_supported(self):
        code, output, _ = self.configure(['1', '1', 'A0FF', 'yes'])
        self.assertEqual(code, 0, output)
        settings = config.load(self.path)['signing']
        self.assertEqual(settings['key_id'], 'a0ff')
        self.assertEqual(settings['certificate_id'], '0102')
        self.assertIn('id=%A0%FF', settings['key_uri'])
        with patch.dict(os.environ, {}, clear=True), config.environment({'signing': settings}):
            self.assertEqual(os.environ['SIGNP7M_CERT_ID'], '0102')
            self.assertEqual(os.environ['SIGNPDF_CERT_ID'], '0102')
            self.assertEqual(os.environ['SIGNPDF_KEY_ID'], 'a0ff')

    def test_existing_distinct_key_id_is_retained_for_same_selected_certificate(self):
        config.create({'signing': {'pin_reference': self.reference, 'module': str(self.module),
                                  'token_label': 'Test; card', 'certificate_id': '0102', 'key_id': 'a0ff'}}, self.path)
        code, output, _ = self.configure(['1', '1', '', 'y'], reference='')
        self.assertEqual(code, 0, output)
        self.assertEqual(config.load(self.path)['signing']['key_id'], 'a0ff')

    def test_manual_mode_sets_every_field_without_card_discovery(self):
        code, output, discovery = self.configure(['0x9', 'Manual card', '1020', '3040', 'y', 'y'], args=['--manual'])
        self.assertEqual(code, 0, output)
        discovery.assert_not_called()
        settings = config.load(self.path)['signing']
        self.assertEqual(settings['slot'], '0x9')
        self.assertEqual(settings['certificate_id'], '1020')
        self.assertEqual(settings['key_id'], '3040')
        self.assertEqual(settings['raw_mechanism'], True)
        self.assertIn('id=%30%40', settings['key_uri'])

    def test_cancel_eof_and_invalid_key_leave_existing_configuration_byte_identical(self):
        original = {'schema': 1, 'signing': {'pin_reference': self.reference, 'key_id': '03'}}
        config.create(original, self.path)
        before = self.path.read_bytes()
        for answers in (['1', '1', '', 'n'], ['1', '1', 'odd', 'y'], ['1', '1', '', EOFError()]):
            code, output, _ = self.configure(answers, reference='')
            self.assertEqual(code, 1, output)
            self.assertEqual(self.path.read_bytes(), before)
            self.assertEqual(list(self.path.parent.glob('*.tmp-*')), [])

    def test_invalid_selection_and_no_certificates_do_not_save(self):
        for answers, cards in ((['99'], CARDS), (['1'], [dict(CARDS[0], certificates=[])]),
                               ([], []), (['1'], [dict(CARDS[0]), dict(CARDS[0])])):
            with self.subTest(answers=answers), patch.object(setup, 'discover', return_value=cards):
                output = io.StringIO()
                with patch('builtins.input', side_effect=answers), redirect_stdout(output):
                    with self.assertRaises(config.ConfigError):
                        with patch.object(setup, 'library_path', return_value=str(self.module)):
                            setup.guided({'pin_reference': self.reference})
            self.assertFalse(self.path.exists())

    def test_invalid_or_expired_certificates_are_not_selected(self):
        expired = [dict(CARDS[0], certificates=[dict(CARDS[0]['certificates'][0], valid=False)])]
        with patch.object(setup, 'discover', return_value=expired), \
             patch.object(setup, 'library_path', return_value=str(self.module)), \
             patch('builtins.input', return_value='1'), redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(config.ConfigError, 'no currently valid'):
                setup.guided({})

    def test_explicit_key_or_label_change_regenerates_uri(self):
        config.create({'signing': {'pin_reference': self.reference, 'token_label': 'Old',
                                  'key_id': '01', 'key_uri': 'pkcs11:token=Old;id=%01;type=private'}}, self.path)
        code, output, discovery = self.configure([], args=['--token-label', 'New / card', '--key-id', '0203'])
        self.assertEqual(code, 0, output)
        discovery.assert_not_called()
        self.assertEqual(config.load(self.path)['signing']['key_uri'],
                         'pkcs11:token=New%20%2F%20card;id=%02%03;type=private')

    def test_explicit_slot_update_preserves_existing_qualified_uri(self):
        uri = 'pkcs11:token=Old;serial=synthetic;id=%01;type=private'
        config.create({'signing': {'pin_reference': self.reference, 'token_label': 'Old', 'key_id': '01',
                                  'key_uri': uri}}, self.path)
        code, output, _ = self.configure([], args=['--slot', '7'])
        self.assertEqual(code, 0, output)
        self.assertEqual(config.load(self.path)['signing']['key_uri'], uri)
        self.assertEqual(config.load(self.path)['signing']['slot'], '0x7')

    def test_explicit_identity_update_refuses_to_drop_custom_uri_qualifiers(self):
        config.create({'signing': {'pin_reference': self.reference, 'token_label': 'Old', 'key_id': '01',
                                  'key_uri': 'pkcs11:token=Old;serial=synthetic;id=%01;type=private'}}, self.path)
        before = self.path.read_bytes()
        code, output, discovery = self.configure([], args=['--key-id', '02'])
        self.assertEqual(code, 1, output)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertIn('custom key URI', output)
        discovery.assert_not_called()

    def test_timeout_and_native_errors_never_echo_vendor_output(self):
        for result in (subprocess.CompletedProcess([], 1, 'SYNTHETIC_PRIVATE_METADATA', 'PRIVATE'),
                       subprocess.CompletedProcess([], 0, 'SYNTHETIC_PRIVATE_METADATA', ''),
                       subprocess.TimeoutExpired([], 20)):
            with patch.object(setup.subprocess, 'run', side_effect=result if isinstance(result, Exception) else None,
                              return_value=result) as run:
                with self.assertRaises(config.ConfigError) as error:
                    setup.discover(str(self.module))
                self.assertNotIn('SYNTHETIC_PRIVATE_METADATA', str(error.exception))
                self.assertEqual(run.call_args.kwargs['timeout'], 20)

    def test_discovery_child_receives_no_pin_or_reference_environment(self):
        env = {'SIGNPDF_WORKER_PIN': 'SYNTHETIC_PIN', 'PKCS11_PIN': 'SYNTHETIC_PIN',
               'SIGNP7M_PIN_REF': self.reference, 'OP_SESSION_test': 'SYNTHETIC_SESSION',
               'OP_SERVICE_ACCOUNT_TOKEN': 'SYNTHETIC_TOKEN', 'PATH': '/usr/bin'}
        with patch.dict(os.environ, env, clear=True), \
             patch.object(setup.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '[]', '')) as run:
            self.assertEqual(setup.discover(str(self.module)), [])
        self.assertEqual(run.call_args.kwargs['env'], {'PATH': '/usr/bin'})
        self.assertEqual(run.call_args.args[0][-1], str(self.module))

    def test_library_chooser_supports_issuer_path_and_rejects_missing_library(self):
        with patch('builtins.input', side_effect=['', str(self.root / 'missing.dylib')]), \
             redirect_stdout(io.StringIO()), patch.object(Path, 'is_file', return_value=False):
            with self.assertRaises(config.ConfigError):
                setup.library_path({})

    def test_terminal_labels_are_sanitized(self):
        self.assertEqual(setup.display('label\n\x1b[31m'), 'label??[31m')


class PublicDiscoveryTests(unittest.TestCase):
    def certificate(self, *, expired=False, ca=False, encryption_only=False):
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.x509.oid import NameOID
        key = ec.generate_private_key(ec.SECP256R1())
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Synthetic signer')])
        now = datetime.now(timezone.utc)
        cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
                .serial_number(1).not_valid_before(now - timedelta(days=2))
                .not_valid_after(now + timedelta(days=-1 if expired else 2))
                .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
                .add_extension(x509.KeyUsage(digital_signature=not encryption_only, content_commitment=not encryption_only,
                                             key_encipherment=encryption_only, data_encipherment=False,
                                             key_agreement=False, key_cert_sign=ca, crl_sign=ca,
                                             encipher_only=False, decipher_only=False), critical=True)
                .sign(key, hashes.SHA256()))
        return cert.public_bytes(serialization.Encoding.DER)

    def test_public_certificate_enumeration_never_logs_in_or_queries_private_keys(self):
        import pkcs11
        slot = MagicMock(slot_id=7, slot_description='Synthetic reader')
        token = slot.get_token.return_value
        token.label = 'Synthetic card'
        session = token.open.return_value.__enter__.return_value
        objects = [{pkcs11.Attribute.ID: b'\x01', pkcs11.Attribute.LABEL: 'Signing',
                    pkcs11.Attribute.VALUE: self.certificate()},
                   {pkcs11.Attribute.ID: b'\x02', pkcs11.Attribute.LABEL: 'Expired',
                    pkcs11.Attribute.VALUE: self.certificate(expired=True)},
                   {pkcs11.Attribute.ID: b'\x03', pkcs11.Attribute.LABEL: 'CA',
                    pkcs11.Attribute.VALUE: self.certificate(ca=True)},
                   {pkcs11.Attribute.ID: b'\x04', pkcs11.Attribute.LABEL: 'Encryption',
                    pkcs11.Attribute.VALUE: self.certificate(encryption_only=True)}]
        session.get_objects.return_value = objects
        with patch.object(pkcs11, 'lib') as library:
            library.return_value.get_slots.return_value = [slot]
            cards = setup.inspect_module('/synthetic/library')
        token.open.assert_called_once_with(rw=False)
        session.get_objects.assert_called_once_with({pkcs11.Attribute.CLASS: pkcs11.ObjectClass.CERTIFICATE})
        self.assertEqual([cert['id'] for cert in cards[0]['certificates']], ['01', '02'])
        self.assertTrue(cards[0]['certificates'][0]['valid'])
        self.assertFalse(cards[0]['certificates'][1]['valid'])
        self.assertNotIn('serial', json.dumps(cards))

    def test_locked_or_unreadable_token_is_not_retried_with_authentication(self):
        import pkcs11
        slot = MagicMock(slot_id=7, slot_description='Synthetic reader')
        token = slot.get_token.return_value
        token.label = 'Synthetic card'
        token.open.side_effect = RuntimeError('SYNTHETIC_PRIVATE_METADATA')
        with patch.object(pkcs11, 'lib') as library:
            library.return_value.get_slots.return_value = [slot]
            cards = setup.inspect_module('/synthetic/library')
        token.open.assert_called_once_with(rw=False)
        self.assertTrue(cards[0]['unavailable'])
        self.assertEqual(cards[0]['certificates'], [])
        self.assertNotIn('SYNTHETIC_PRIVATE_METADATA', json.dumps(cards))


if __name__ == '__main__':
    unittest.main()
