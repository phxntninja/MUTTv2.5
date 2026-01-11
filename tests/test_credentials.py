import unittest
import tempfile
import os
import yaml
from mutt.models.credentials import SNMPv3Credential, SNMPv3CredentialSet
from mutt.config import CredentialLoader


class TestSNMPv3Credential(unittest.TestCase):
    """Test SNMPv3Credential dataclass."""

    def test_credential_creation(self):
        """Test creating a basic SNMPv3 credential."""
        cred = SNMPv3Credential(
            priority=1,
            auth_type='SHA',
            auth_password='authpass123',
            priv_type='AES',
            priv_password='privpass456',
            active=True
        )
        self.assertEqual(cred.priority, 1)
        self.assertEqual(cred.auth_type, 'SHA')
        self.assertEqual(cred.auth_password, 'authpass123')
        self.assertEqual(cred.priv_type, 'AES')
        self.assertEqual(cred.priv_password, 'privpass456')
        self.assertTrue(cred.active)

    def test_credential_default_active(self):
        """Test that active defaults to True."""
        cred = SNMPv3Credential(
            priority=1,
            auth_type='MD5',
            auth_password='auth',
            priv_type='DES',
            priv_password='priv'
        )
        self.assertTrue(cred.active)

    def test_credential_inactive(self):
        """Test creating an inactive credential."""
        cred = SNMPv3Credential(
            priority=2,
            auth_type='SHA',
            auth_password='newauth',
            priv_type='AES',
            priv_password='newpriv',
            active=False
        )
        self.assertFalse(cred.active)


class TestSNMPv3CredentialSet(unittest.TestCase):
    """Test SNMPv3CredentialSet dataclass."""

    def test_credential_set_creation(self):
        """Test creating a credential set."""
        cred_set = SNMPv3CredentialSet(
            username='snmpuser',
            credentials=[]
        )
        self.assertEqual(cred_set.username, 'snmpuser')
        self.assertEqual(len(cred_set.credentials), 0)

    def test_credential_set_with_credentials(self):
        """Test credential set with multiple credentials."""
        cred1 = SNMPv3Credential(
            priority=1,
            auth_type='SHA',
            auth_password='auth1',
            priv_type='AES',
            priv_password='priv1',
            active=True
        )
        cred2 = SNMPv3Credential(
            priority=2,
            auth_type='SHA',
            auth_password='auth2',
            priv_type='AES',
            priv_password='priv2',
            active=False
        )

        cred_set = SNMPv3CredentialSet(
            username='testuser',
            credentials=[cred1, cred2]
        )

        self.assertEqual(len(cred_set.credentials), 2)
        self.assertEqual(cred_set.credentials[0].priority, 1)
        self.assertEqual(cred_set.credentials[1].priority, 2)

    def test_get_active_credentials(self):
        """Test retrieving only active credentials."""
        cred1 = SNMPv3Credential(
            priority=1,
            auth_type='SHA',
            auth_password='auth1',
            priv_type='AES',
            priv_password='priv1',
            active=True
        )
        cred2 = SNMPv3Credential(
            priority=2,
            auth_type='SHA',
            auth_password='auth2',
            priv_type='AES',
            priv_password='priv2',
            active=False
        )
        cred3 = SNMPv3Credential(
            priority=3,
            auth_type='MD5',
            auth_password='auth3',
            priv_type='DES',
            priv_password='priv3',
            active=True
        )

        cred_set = SNMPv3CredentialSet(
            username='testuser',
            credentials=[cred2, cred3, cred1]  # Intentionally out of order
        )

        active = cred_set.get_active_credentials()

        # Should return only active credentials (cred1 and cred3)
        self.assertEqual(len(active), 2)
        # Should be sorted by priority (cred1 first, then cred3)
        self.assertEqual(active[0].priority, 1)
        self.assertEqual(active[1].priority, 3)

    def test_get_active_credentials_empty(self):
        """Test get_active_credentials when all are inactive."""
        cred1 = SNMPv3Credential(
            priority=1,
            auth_type='SHA',
            auth_password='auth1',
            priv_type='AES',
            priv_password='priv1',
            active=False
        )

        cred_set = SNMPv3CredentialSet(
            username='testuser',
            credentials=[cred1]
        )

        active = cred_set.get_active_credentials()
        self.assertEqual(len(active), 0)

    def test_priority_sorting(self):
        """Test that priority sorting works correctly (lower number = higher priority)."""
        creds = [
            SNMPv3Credential(priority=5, auth_type='SHA', auth_password='a5',
                           priv_type='AES', priv_password='p5', active=True),
            SNMPv3Credential(priority=1, auth_type='SHA', auth_password='a1',
                           priv_type='AES', priv_password='p1', active=True),
            SNMPv3Credential(priority=3, auth_type='SHA', auth_password='a3',
                           priv_type='AES', priv_password='p3', active=True),
        ]

        cred_set = SNMPv3CredentialSet(username='user', credentials=creds)
        active = cred_set.get_active_credentials()

        # Should be sorted: 1, 3, 5
        self.assertEqual(active[0].priority, 1)
        self.assertEqual(active[1].priority, 3)
        self.assertEqual(active[2].priority, 5)


class TestCredentialLoader(unittest.TestCase):
    """Test CredentialLoader class."""

    def setUp(self):
        """Create a temporary directory for test files."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_load_credentials_valid_file(self):
        """Test loading credentials from a valid YAML file."""
        yaml_content = {
            'snmpv3_credentials': [
                {
                    'username': 'snmpuser',
                    'credentials': [
                        {
                            'priority': 1,
                            'auth_type': 'SHA',
                            'auth_password': 'authpass123',
                            'priv_type': 'AES',
                            'priv_password': 'privpass456',
                            'active': True
                        }
                    ]
                }
            ]
        }

        file_path = os.path.join(self.temp_dir, 'credentials.yaml')
        with open(file_path, 'w') as f:
            yaml.dump(yaml_content, f)

        creds = CredentialLoader.load_credentials(file_path)

        self.assertEqual(len(creds), 1)
        self.assertIn('snmpuser', creds)
        self.assertEqual(creds['snmpuser'].username, 'snmpuser')
        self.assertEqual(len(creds['snmpuser'].credentials), 1)
        self.assertEqual(creds['snmpuser'].credentials[0].priority, 1)
        self.assertEqual(creds['snmpuser'].credentials[0].auth_type, 'SHA')

    def test_load_credentials_multiple_users(self):
        """Test loading credentials for multiple users."""
        yaml_content = {
            'snmpv3_credentials': [
                {
                    'username': 'user1',
                    'credentials': [
                        {
                            'priority': 1,
                            'auth_type': 'SHA',
                            'auth_password': 'auth1',
                            'priv_type': 'AES',
                            'priv_password': 'priv1',
                            'active': True
                        }
                    ]
                },
                {
                    'username': 'user2',
                    'credentials': [
                        {
                            'priority': 1,
                            'auth_type': 'MD5',
                            'auth_password': 'auth2',
                            'priv_type': 'DES',
                            'priv_password': 'priv2',
                            'active': True
                        }
                    ]
                }
            ]
        }

        file_path = os.path.join(self.temp_dir, 'credentials.yaml')
        with open(file_path, 'w') as f:
            yaml.dump(yaml_content, f)

        creds = CredentialLoader.load_credentials(file_path)

        self.assertEqual(len(creds), 2)
        self.assertIn('user1', creds)
        self.assertIn('user2', creds)
        self.assertEqual(creds['user1'].credentials[0].auth_type, 'SHA')
        self.assertEqual(creds['user2'].credentials[0].auth_type, 'MD5')

    def test_load_credentials_multiple_credentials_per_user(self):
        """Test loading multiple credentials for a single user."""
        yaml_content = {
            'snmpv3_credentials': [
                {
                    'username': 'rotationuser',
                    'credentials': [
                        {
                            'priority': 1,
                            'auth_type': 'SHA',
                            'auth_password': 'oldauth',
                            'priv_type': 'AES',
                            'priv_password': 'oldpriv',
                            'active': True
                        },
                        {
                            'priority': 2,
                            'auth_type': 'SHA',
                            'auth_password': 'newauth',
                            'priv_type': 'AES',
                            'priv_password': 'newpriv',
                            'active': False
                        }
                    ]
                }
            ]
        }

        file_path = os.path.join(self.temp_dir, 'credentials.yaml')
        with open(file_path, 'w') as f:
            yaml.dump(yaml_content, f)

        creds = CredentialLoader.load_credentials(file_path)

        self.assertEqual(len(creds['rotationuser'].credentials), 2)
        # Verify they are sorted by priority
        self.assertEqual(creds['rotationuser'].credentials[0].priority, 1)
        self.assertEqual(creds['rotationuser'].credentials[1].priority, 2)
        self.assertTrue(creds['rotationuser'].credentials[0].active)
        self.assertFalse(creds['rotationuser'].credentials[1].active)

    def test_load_credentials_missing_file(self):
        """Test loading credentials from a non-existent file."""
        file_path = os.path.join(self.temp_dir, 'nonexistent.yaml')
        creds = CredentialLoader.load_credentials(file_path)

        # Should return empty dict, not raise exception
        self.assertEqual(len(creds), 0)
        self.assertIsInstance(creds, dict)

    def test_load_credentials_empty_file(self):
        """Test loading credentials from an empty YAML file."""
        file_path = os.path.join(self.temp_dir, 'empty.yaml')
        with open(file_path, 'w') as f:
            f.write('')

        creds = CredentialLoader.load_credentials(file_path)

        # Should return empty dict
        self.assertEqual(len(creds), 0)

    def test_load_credentials_no_credentials_key(self):
        """Test loading a YAML file without 'snmpv3_credentials' key."""
        yaml_content = {
            'some_other_key': 'value'
        }

        file_path = os.path.join(self.temp_dir, 'wrong_key.yaml')
        with open(file_path, 'w') as f:
            yaml.dump(yaml_content, f)

        creds = CredentialLoader.load_credentials(file_path)

        # Should return empty dict
        self.assertEqual(len(creds), 0)

    def test_load_credentials_default_active_value(self):
        """Test that 'active' defaults to True when not specified."""
        yaml_content = {
            'snmpv3_credentials': [
                {
                    'username': 'defaultuser',
                    'credentials': [
                        {
                            'priority': 1,
                            'auth_type': 'SHA',
                            'auth_password': 'auth',
                            'priv_type': 'AES',
                            'priv_password': 'priv'
                            # Note: 'active' is not specified
                        }
                    ]
                }
            ]
        }

        file_path = os.path.join(self.temp_dir, 'default_active.yaml')
        with open(file_path, 'w') as f:
            yaml.dump(yaml_content, f)

        creds = CredentialLoader.load_credentials(file_path)

        # Should default to True
        self.assertTrue(creds['defaultuser'].credentials[0].active)


if __name__ == '__main__':
    unittest.main()
