"""
Integration test for SNMPv3 functionality.
Tests the complete flow of SNMPv3 credential loading, trap processing, and auth failure tracking.
"""

import asyncio
import os
import tempfile
import unittest
import yaml
from unittest.mock import Mock, patch

from mutt.config import CredentialLoader
from mutt.listeners.snmp_listener import SNMPListener
from mutt.storage.database import Database
from mutt.storage.auth_failure_tracker import AuthFailureTracker
from mutt.models.credentials import SNMPv3Credential, SNMPv3CredentialSet
from mutt.models.message import SNMPTrap, MessageType


class TestSNMPv3Integration(unittest.IsolatedAsyncioTestCase):
    """Integration tests for SNMPv3 end-to-end functionality."""

    async def asyncSetUp(self):
        """Set up test environment."""
        # Create temporary directory
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test_snmpv3.db')

        # Create test credentials file
        self.creds_path = os.path.join(self.temp_dir, 'snmpv3_credentials.yaml')
        creds_data = {
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
                        },
                        {
                            'priority': 2,
                            'auth_type': 'SHA',
                            'auth_password': 'authpass_new',
                            'priv_type': 'AES',
                            'priv_password': 'privpass_new',
                            'active': False
                        }
                    ]
                },
                {
                    'username': 'adminuser',
                    'credentials': [
                        {
                            'priority': 1,
                            'auth_type': 'MD5',
                            'auth_password': 'adminauth789',
                            'priv_type': 'DES',
                            'priv_password': 'adminpriv000',
                            'active': True
                        }
                    ]
                }
            ]
        }

        with open(self.creds_path, 'w') as f:
            yaml.dump(creds_data, f)

        # Initialize database
        self.database = Database(self.db_path)
        await self.database.initialize()

        # Initialize auth failure tracker
        self.auth_tracker = AuthFailureTracker(self.database)

    async def asyncTearDown(self):
        """Clean up test environment."""
        if self.database.connection:
            await self.database.connection.close()

        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    async def test_credential_loading_integration(self):
        """Test loading credentials from file and using them in listener."""
        # Load credentials
        credentials_dict = CredentialLoader.load_credentials(self.creds_path)

        # Verify credentials loaded
        self.assertEqual(len(credentials_dict), 2)
        self.assertIn('snmpuser', credentials_dict)
        self.assertIn('adminuser', credentials_dict)

        # Create listener with loaded credentials
        queue = asyncio.Queue()
        config = {
            'listeners': {
                'snmp': {
                    'communities': ['public']
                }
            }
        }

        listener = SNMPListener(
            queue=queue,
            config=config,
            credentials_dict=credentials_dict,
            auth_failure_tracker=self.auth_tracker
        )

        # Verify listener has credentials
        self.assertEqual(len(listener.credentials_dict), 2)
        self.assertIsNotNone(listener.auth_failure_tracker)

    async def test_auth_failure_tracking_integration(self):
        """Test auth failure tracking integration with database."""
        # Load credentials
        credentials_dict = CredentialLoader.load_credentials(self.creds_path)

        # Create listener
        queue = asyncio.Queue()
        listener = SNMPListener(
            queue=queue,
            credentials_dict=credentials_dict,
            auth_failure_tracker=self.auth_tracker
        )

        # Record some failures
        await self.auth_tracker.record_failure('snmpuser', 'device1.example.com')
        await self.auth_tracker.record_failure('snmpuser', 'device1.example.com')
        await self.auth_tracker.record_failure('adminuser', 'device2.example.com')

        # Get failures
        failures = await self.auth_tracker.get_all_failures()

        # Verify failures recorded
        self.assertEqual(len(failures), 2)

        # Find snmpuser failures
        snmpuser_failure = next(f for f in failures if f['username'] == 'snmpuser')
        self.assertEqual(snmpuser_failure['num_failures'], 2)
        self.assertEqual(snmpuser_failure['hostname'], 'device1.example.com')

        # Clear failures for snmpuser (simulating successful auth)
        await self.auth_tracker.clear_failure('snmpuser')

        # Verify only adminuser remains
        failures = await self.auth_tracker.get_all_failures()
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]['username'], 'adminuser')

    async def test_credential_rotation_integration(self):
        """Test credential rotation scenario."""
        # Load initial credentials
        credentials_dict = CredentialLoader.load_credentials(self.creds_path)

        # Verify snmpuser has 2 credentials, only 1 active
        snmpuser_set = credentials_dict['snmpuser']
        active_creds = snmpuser_set.get_active_credentials()

        self.assertEqual(len(snmpuser_set.credentials), 2)
        self.assertEqual(len(active_creds), 1)
        self.assertEqual(active_creds[0].priority, 1)
        self.assertEqual(active_creds[0].auth_password, 'authpass123')

        # Simulate rotation: deactivate old, activate new
        snmpuser_set.credentials[0].active = False
        snmpuser_set.credentials[1].active = True

        # Get new active credentials
        active_creds = snmpuser_set.get_active_credentials()

        # Verify rotation worked
        self.assertEqual(len(active_creds), 1)
        self.assertEqual(active_creds[0].priority, 2)
        self.assertEqual(active_creds[0].auth_password, 'authpass_new')

    async def test_trap_processing_with_auth_tracker(self):
        """Test trap processing with auth failure tracking."""
        # Load credentials
        credentials_dict = CredentialLoader.load_credentials(self.creds_path)

        # Create listener
        queue = asyncio.Queue()
        listener = SNMPListener(
            queue=queue,
            credentials_dict=credentials_dict,
            auth_failure_tracker=self.auth_tracker
        )

        # Create mock varbinds for a trap
        mock_varbind1 = Mock()
        mock_varbind1.prettyPrint.return_value = 'SNMPv2-MIB::snmpTrapOID.0'
        mock_value1 = Mock()
        mock_value1.prettyPrint.return_value = '1.3.6.1.4.1.9.9.41.2.0.1'

        mock_varbind2 = Mock()
        mock_varbind2.prettyPrint.return_value = 'IF-MIB::ifIndex.1'
        mock_value2 = Mock()
        mock_value2.prettyPrint.return_value = '1'

        varBinds = [(mock_varbind1, mock_value1), (mock_varbind2, mock_value2)]

        # Process trap
        await listener.process_trap(varBinds, '192.168.1.50', None)

        # Verify trap was queued
        self.assertFalse(queue.empty())

        # Get the trap message
        trap = await queue.get()

        # Verify trap details
        self.assertIsInstance(trap, SNMPTrap)
        self.assertEqual(trap.source_ip, '192.168.1.50')
        self.assertEqual(trap.message_type, MessageType.SNMP_TRAP)
        self.assertEqual(trap.oid, '1.3.6.1.4.1.9.9.41.2.0.1')
        self.assertIn('SNMPv2-MIB::snmpTrapOID.0', trap.varbinds)

    async def test_multiple_user_credentials_integration(self):
        """Test listener with multiple users."""
        # Load credentials
        credentials_dict = CredentialLoader.load_credentials(self.creds_path)

        # Create listener
        queue = asyncio.Queue()
        config = {
            'listeners': {
                'snmp': {
                    'communities': ['public', 'private']
                }
            }
        }

        listener = SNMPListener(
            queue=queue,
            config=config,
            credentials_dict=credentials_dict,
            auth_failure_tracker=self.auth_tracker
        )

        # Setup v3 credentials in engine
        listener._setup_v3_credentials()

        # Verify both users are available
        self.assertIn('snmpuser', listener.credentials_dict)
        self.assertIn('adminuser', listener.credentials_dict)

        # Verify different auth types
        snmpuser_creds = listener.credentials_dict['snmpuser'].get_active_credentials()
        adminuser_creds = listener.credentials_dict['adminuser'].get_active_credentials()

        self.assertEqual(snmpuser_creds[0].auth_type, 'SHA')
        self.assertEqual(adminuser_creds[0].auth_type, 'MD5')

    @patch('mutt.listeners.snmp_listener.config')
    @patch('mutt.listeners.snmp_listener.udp')
    async def test_full_listener_startup_with_v3(self, mock_udp, mock_config):
        """Test complete listener startup with SNMPv3 credentials."""
        # Load credentials
        credentials_dict = CredentialLoader.load_credentials(self.creds_path)

        # Create config
        config = {
            'listeners': {
                'snmp': {
                    'communities': ['public', 'monitoring']
                }
            }
        }

        # Create listener
        queue = asyncio.Queue()
        listener = SNMPListener(
            queue=queue,
            config=config,
            port=5162,
            host='0.0.0.0',
            credentials_dict=credentials_dict,
            auth_failure_tracker=self.auth_tracker
        )

        # Mock the transport
        mock_transport = Mock()
        mock_udp.UdpAsyncioTransport.return_value = mock_transport
        mock_transport.openServerMode.return_value = mock_transport

        # Start listener
        await listener.start()

        # Verify listener is running
        self.assertTrue(listener._is_running)

        # Verify credentials are loaded
        self.assertEqual(len(listener.credentials_dict), 2)

        # Stop listener
        listener.snmp_engine.transportDispatcher = Mock()
        listener.snmp_engine.transportDispatcher.closeDispatcher = Mock()
        await listener.stop()

        self.assertFalse(listener._is_running)

    async def test_database_schema_for_auth_failures(self):
        """Test that database schema includes auth failures table."""
        # Query the schema
        cursor = await self.database.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='snmpv3_auth_failures'"
        )
        result = await cursor.fetchone()

        # Verify table exists
        self.assertIsNotNone(result)
        self.assertEqual(result[0], 'snmpv3_auth_failures')

        # Verify table structure
        cursor = await self.database.execute("PRAGMA table_info(snmpv3_auth_failures)")
        columns = await cursor.fetchall()

        column_names = [col[1] for col in columns]
        self.assertIn('id', column_names)
        self.assertIn('username', column_names)
        self.assertIn('hostname', column_names)
        self.assertIn('num_failures', column_names)
        self.assertIn('last_failure', column_names)

    async def test_priority_based_credential_selection(self):
        """Test that credentials are tried in priority order."""
        # Load credentials
        credentials_dict = CredentialLoader.load_credentials(self.creds_path)

        # Get snmpuser credentials
        snmpuser_set = credentials_dict['snmpuser']

        # Verify credentials are sorted by priority
        self.assertEqual(len(snmpuser_set.credentials), 2)
        self.assertEqual(snmpuser_set.credentials[0].priority, 1)
        self.assertEqual(snmpuser_set.credentials[1].priority, 2)

        # Get active credentials (should return priority 1 first)
        active = snmpuser_set.get_active_credentials()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].priority, 1)

    async def test_auth_failure_persistence(self):
        """Test that auth failures persist in database across tracker instances."""
        # Record failures
        await self.auth_tracker.record_failure('testuser', 'testhost')
        await self.auth_tracker.record_failure('testuser', 'testhost')

        # Get failures
        failures1 = await self.auth_tracker.get_all_failures()
        self.assertEqual(len(failures1), 1)
        self.assertEqual(failures1[0]['num_failures'], 2)

        # Create new tracker instance (simulating restart)
        new_tracker = AuthFailureTracker(self.database)

        # Get failures from new instance
        failures2 = await new_tracker.get_all_failures()

        # Verify persistence
        self.assertEqual(len(failures2), 1)
        self.assertEqual(failures2[0]['username'], 'testuser')
        self.assertEqual(failures2[0]['num_failures'], 2)


if __name__ == '__main__':
    unittest.main()
