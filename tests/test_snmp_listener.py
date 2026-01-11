import unittest
import asyncio
from unittest.mock import Mock, MagicMock, patch
from mutt.listeners.snmp_listener import SNMPListener
from mutt.models.message import SNMPTrap, MessageType, Severity
from mutt.models.credentials import SNMPv3CredentialSet, SNMPv3Credential
from mutt.storage.auth_failure_tracker import AuthFailureTracker


class TestSNMPListener(unittest.IsolatedAsyncioTestCase):
    """Test SNMPListener class."""

    def setUp(self):
        """Set up test fixtures."""
        self.queue = asyncio.Queue()
        self.config = {
            'listeners': {
                'snmp': {
                    'communities': ['public', 'private']
                }
            }
        }

    async def test_listener_initialization_basic(self):
        """Test basic listener initialization."""
        listener = SNMPListener(
            queue=self.queue,
            port=5162,
            host='0.0.0.0'
        )

        self.assertEqual(listener.port, 5162)
        self.assertEqual(listener.host, '0.0.0.0')
        self.assertEqual(listener.queue, self.queue)
        self.assertIsNotNone(listener.snmp_engine)

    async def test_listener_initialization_with_config(self):
        """Test listener initialization with configuration."""
        listener = SNMPListener(
            queue=self.queue,
            config=self.config,
            port=162,
            host='127.0.0.1'
        )

        self.assertEqual(listener.config, self.config)
        self.assertEqual(listener.port, 162)

    async def test_listener_initialization_with_credentials(self):
        """Test listener initialization with SNMPv3 credentials."""
        cred1 = SNMPv3Credential(
            priority=1,
            auth_type='SHA',
            auth_password='authpass',
            priv_type='AES',
            priv_password='privpass',
            active=True
        )

        cred_set = SNMPv3CredentialSet(
            username='testuser',
            credentials=[cred1]
        )

        credentials_dict = {'testuser': cred_set}

        listener = SNMPListener(
            queue=self.queue,
            credentials_dict=credentials_dict
        )

        self.assertEqual(len(listener.credentials_dict), 1)
        self.assertIn('testuser', listener.credentials_dict)

    async def test_listener_initialization_with_auth_tracker(self):
        """Test listener initialization with auth failure tracker."""
        mock_tracker = Mock(spec=AuthFailureTracker)

        listener = SNMPListener(
            queue=self.queue,
            auth_failure_tracker=mock_tracker
        )

        self.assertEqual(listener.auth_failure_tracker, mock_tracker)

    async def test_add_user_to_engine_sha_aes(self):
        """Test adding a user with SHA+AES to the SNMP engine."""
        listener = SNMPListener(queue=self.queue)

        cred = SNMPv3Credential(
            priority=1,
            auth_type='SHA',
            auth_password='authpass123',
            priv_type='AES',
            priv_password='privpass456',
            active=True
        )

        # This should not raise an exception
        listener._add_user_to_engine('testuser', cred)

    async def test_add_user_to_engine_md5_des(self):
        """Test adding a user with MD5+DES to the SNMP engine."""
        listener = SNMPListener(queue=self.queue)

        cred = SNMPv3Credential(
            priority=1,
            auth_type='MD5',
            auth_password='authpass',
            priv_type='DES',
            priv_password='privpass',
            active=True
        )

        # This should not raise an exception
        listener._add_user_to_engine('md5user', cred)

    async def test_setup_v3_credentials(self):
        """Test setting up V3 credentials in the engine."""
        cred1 = SNMPv3Credential(
            priority=1,
            auth_type='SHA',
            auth_password='authpass1',
            priv_type='AES',
            priv_password='privpass1',
            active=True
        )
        cred2 = SNMPv3Credential(
            priority=2,
            auth_type='SHA',
            auth_password='authpass2',
            priv_type='AES',
            priv_password='privpass2',
            active=False
        )

        cred_set = SNMPv3CredentialSet(
            username='rotationuser',
            credentials=[cred1, cred2]
        )

        credentials_dict = {'rotationuser': cred_set}

        listener = SNMPListener(
            queue=self.queue,
            credentials_dict=credentials_dict
        )

        # Setup credentials
        listener._setup_v3_credentials()

        # Should register the active credential (priority 1)
        # We can't easily verify this without inspecting pysnmp internals,
        # but we can at least verify it doesn't crash

    async def test_setup_v3_credentials_multiple_users(self):
        """Test setting up V3 credentials for multiple users."""
        cred1 = SNMPv3Credential(
            priority=1,
            auth_type='SHA',
            auth_password='authpass1',
            priv_type='AES',
            priv_password='privpass1',
            active=True
        )
        cred2 = SNMPv3Credential(
            priority=1,
            auth_type='MD5',
            auth_password='authpass2',
            priv_type='DES',
            priv_password='privpass2',
            active=True
        )

        cred_set1 = SNMPv3CredentialSet(username='user1', credentials=[cred1])
        cred_set2 = SNMPv3CredentialSet(username='user2', credentials=[cred2])

        credentials_dict = {
            'user1': cred_set1,
            'user2': cred_set2
        }

        listener = SNMPListener(
            queue=self.queue,
            credentials_dict=credentials_dict
        )

        # Should not raise an exception
        listener._setup_v3_credentials()

    async def test_setup_v3_credentials_no_active(self):
        """Test setting up V3 credentials when all are inactive."""
        cred1 = SNMPv3Credential(
            priority=1,
            auth_type='SHA',
            auth_password='authpass1',
            priv_type='AES',
            priv_password='privpass1',
            active=False
        )

        cred_set = SNMPv3CredentialSet(username='inactiveuser', credentials=[cred1])
        credentials_dict = {'inactiveuser': cred_set}

        listener = SNMPListener(
            queue=self.queue,
            credentials_dict=credentials_dict
        )

        # Should handle inactive credentials gracefully
        listener._setup_v3_credentials()

    async def test_process_trap_basic(self):
        """Test basic trap processing."""
        listener = SNMPListener(queue=self.queue)

        # Create mock varbinds
        mock_varbind1 = Mock()
        mock_varbind1.prettyPrint.return_value = '1.3.6.1.2.1.1.3.0'
        mock_value1 = Mock()
        mock_value1.prettyPrint.return_value = '12345'

        varBinds = [(mock_varbind1, mock_value1)]

        # Process the trap
        await listener.process_trap(varBinds, '192.168.1.100', None)

        # Verify a message was queued
        self.assertFalse(self.queue.empty())

        msg = await self.queue.get()
        self.assertIsInstance(msg, SNMPTrap)
        self.assertEqual(msg.source_ip, '192.168.1.100')
        self.assertEqual(msg.message_type, MessageType.SNMP_TRAP)

    async def test_process_trap_with_oid(self):
        """Test trap processing with snmpTrapOID extraction."""
        listener = SNMPListener(queue=self.queue)

        # Create mock varbinds with trap OID
        mock_varbind1 = Mock()
        mock_varbind1.prettyPrint.return_value = 'SNMPv2-MIB::snmpTrapOID.0'
        mock_value1 = Mock()
        mock_value1.prettyPrint.return_value = '1.3.6.1.4.1.9.9.41.2.0.1'

        mock_varbind2 = Mock()
        mock_varbind2.prettyPrint.return_value = 'IF-MIB::ifIndex.1'
        mock_value2 = Mock()
        mock_value2.prettyPrint.return_value = '1'

        varBinds = [(mock_varbind1, mock_value1), (mock_varbind2, mock_value2)]

        await listener.process_trap(varBinds, '10.0.0.1', None)

        msg = await self.queue.get()
        self.assertEqual(msg.oid, '1.3.6.1.4.1.9.9.41.2.0.1')

    async def test_process_trap_error_handling(self):
        """Test that trap processing handles errors gracefully."""
        listener = SNMPListener(queue=self.queue)

        # Create mock varbinds that will cause an error
        mock_varbind = Mock()
        mock_varbind.prettyPrint.side_effect = Exception("Mock error")

        varBinds = [(mock_varbind, Mock())]

        # Should not raise exception
        await listener.process_trap(varBinds, '192.168.1.1', None)

        # Queue should still be empty due to error
        self.assertTrue(self.queue.empty())

    async def test_process_data_is_dummy(self):
        """Test that process_data is a dummy method (no-op)."""
        listener = SNMPListener(queue=self.queue)

        # Should not raise exception and should not queue anything
        listener.process_data(b'dummy_data', ('127.0.0.1', 12345))

        # Queue should be empty since process_data is a dummy
        self.assertTrue(self.queue.empty())

    @patch('mutt.listeners.snmp_listener.config')
    @patch('mutt.listeners.snmp_listener.udp')
    async def test_start_with_communities(self, mock_udp, mock_config):
        """Test starting the listener with community strings."""
        config_dict = {
            'listeners': {
                'snmp': {
                    'communities': ['public', 'private', 'monitoring']
                }
            }
        }

        listener = SNMPListener(
            queue=self.queue,
            config=config_dict,
            port=5162,
            host='0.0.0.0'
        )

        # Mock the transport
        mock_transport = Mock()
        mock_udp.UdpAsyncioTransport.return_value = mock_transport
        mock_transport.openServerMode.return_value = mock_transport

        await listener.start()

        # Verify listener is running
        self.assertTrue(listener._is_running)

    @patch('mutt.listeners.snmp_listener.config')
    @patch('mutt.listeners.snmp_listener.udp')
    async def test_start_with_v3_credentials(self, mock_udp, mock_config):
        """Test starting the listener with V3 credentials."""
        cred = SNMPv3Credential(
            priority=1,
            auth_type='SHA',
            auth_password='authpass',
            priv_type='AES',
            priv_password='privpass',
            active=True
        )
        cred_set = SNMPv3CredentialSet(username='v3user', credentials=[cred])
        credentials_dict = {'v3user': cred_set}

        config_dict = {
            'listeners': {
                'snmp': {
                    'communities': ['public']
                }
            }
        }

        listener = SNMPListener(
            queue=self.queue,
            config=config_dict,
            credentials_dict=credentials_dict
        )

        # Mock the transport
        mock_transport = Mock()
        mock_udp.UdpAsyncioTransport.return_value = mock_transport
        mock_transport.openServerMode.return_value = mock_transport

        await listener.start()

        self.assertTrue(listener._is_running)

    async def test_stop_listener(self):
        """Test stopping the listener."""
        listener = SNMPListener(queue=self.queue)
        listener._is_running = True

        # Mock the dispatcher
        listener.snmp_engine.transportDispatcher = Mock()
        listener.snmp_engine.transportDispatcher.closeDispatcher = Mock()

        await listener.stop()

        self.assertFalse(listener._is_running)
        listener.snmp_engine.transportDispatcher.closeDispatcher.assert_called_once()


class TestSNMPListenerAuthProtocols(unittest.TestCase):
    """Test SNMPv3 authentication protocol mapping."""

    def test_auth_protocol_mapping(self):
        """Test that auth protocol types map correctly."""
        listener = SNMPListener(queue=asyncio.Queue())

        # Test various auth types
        test_cases = [
            'SHA', 'MD5', 'SHA224', 'SHA256', 'SHA384', 'SHA512'
        ]

        for auth_type in test_cases:
            cred = SNMPv3Credential(
                priority=1,
                auth_type=auth_type,
                auth_password='testpass',
                priv_type='AES',
                priv_password='testpass',
                active=True
            )
            # Should not raise exception
            listener._add_user_to_engine(f'user_{auth_type}', cred)

    def test_priv_protocol_mapping(self):
        """Test that privacy protocol types map correctly."""
        listener = SNMPListener(queue=asyncio.Queue())

        # Test various privacy types
        test_cases = [
            'AES', 'AES128', 'AES192', 'AES256', 'DES', '3DES'
        ]

        for priv_type in test_cases:
            cred = SNMPv3Credential(
                priority=1,
                auth_type='SHA',
                auth_password='testpass',
                priv_type=priv_type,
                priv_password='testpass',
                active=True
            )
            # Should not raise exception
            listener._add_user_to_engine(f'user_{priv_type}', cred)


if __name__ == '__main__':
    unittest.main()
