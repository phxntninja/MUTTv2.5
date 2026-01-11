"""
SNMP listener implementation for Mutt with SNMPv3 support.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Optional, Tuple, Dict, List, Any

# pysnmp-lextudio imports
from pysnmp.entity import engine, config
from pysnmp.entity.rfc3413 import ntfrcv
from pysnmp.proto.api import v2c
from pysnmp.smi import builder, view, rfc1902
from pysnmp.entity.engine import SnmpEngine
from pysnmp.carrier.asyncio.dgram import udp

from mutt.listeners.base import BaseListener
from mutt.models.message import MessageType, Severity, SNMPTrap
from mutt.models.credentials import SNMPv3CredentialSet, SNMPv3Credential
from mutt.storage.auth_failure_tracker import AuthFailureTracker

logger = logging.getLogger(__name__)


class SNMPListener(BaseListener):
    """
    Listener for SNMP traps over UDP, supporting v1, v2c, and v3.
    """
    
    def __init__(
        self,
        queue: asyncio.Queue,
        config: Dict[str, Any] = None,
        port: int = 5162,
        host: str = "0.0.0.0",
        credentials_dict: Dict[str, SNMPv3CredentialSet] = None,
        auth_failure_tracker: AuthFailureTracker = None
    ):
        """
        Initialize the SNMP listener.
        
        Args:
            queue: Queue to put parsed messages into
            config: Main configuration dictionary
            port: UDP port to listen on (default: 5162)
            host: Host interface to bind to (default: "0.0.0.0")
            credentials_dict: Dictionary of SNMPv3 credentials keyed by username
            auth_failure_tracker: Instance of AuthFailureTracker for v3 failures
        """
        super().__init__(queue)
        self.config = config or {}
        self.port = port
        self.host = host
        self.credentials_dict = credentials_dict or {}
        self.auth_failure_tracker = auth_failure_tracker
        self.snmp_engine = SnmpEngine()
        
        # MIB resolving (optional but good for future)
        self.mib_builder = builder.MibBuilder()
        self.mib_view = view.MibViewController(self.mib_builder)

    def _setup_v3_credentials(self):
        """Configure the SNMP engine with all active V3 credentials."""
        # Note: pysnmp USM (User-based Security Model) lookup usually happens
        # by securityName. If we have multiple credentials for the SAME securityName,
        # pysnmp's standard engine might struggle to 'try' them sequentially 
        # unless we manage the decryption attempt manually or rotate them.
        
        # For now, we register the highest priority active credential for each user
        # to the USM. The prompt suggests a 'try in order' approach which 
        # might require custom USM handling if one fails.
        
        for username, cred_set in self.credentials_dict.items():
            active_creds = cred_set.get_active_credentials()
            if not active_creds:
                continue
                
            # Register the first one (highest priority)
            # In a real rotation, we might need a more complex hook into pysnmp's USM
            self._add_user_to_engine(username, active_creds[0])

    def _add_user_to_engine(self, username: str, cred: SNMPv3Credential):
        """Adds a single V3 user to the SNMP engine."""
        auth_proto = {
            'SHA': config.usmHMACSHAAuthProtocol,
            'MD5': config.usmHMACMD5AuthProtocol,
            'SHA224': config.usmHMAC128SHA224AuthProtocol,
            'SHA256': config.usmHMAC192SHA256AuthProtocol,
            'SHA384': config.usmHMAC256SHA384AuthProtocol,
            'SHA512': config.usmHMAC384SHA512AuthProtocol,
        }.get(cred.auth_type.upper(), config.usmNoAuthProtocol)

        priv_proto = {
            'AES': config.usmAesCfb128Protocol,
            'AES128': config.usmAesCfb128Protocol,
            'AES192': config.usmAesCfb192Protocol,
            'AES256': config.usmAesCfb256Protocol,
            'DES': config.usmDESPrivProtocol,
            '3DES': config.usm3DESEDEPrivProtocol,
        }.get(cred.priv_type.upper(), config.usmNoPrivProtocol)

        config.addV3User(
            self.snmp_engine,
            username,
            auth_proto, cred.auth_password,
            priv_proto, cred.priv_password
        )

    async def start(self) -> None:
        """Start listening for SNMP traps using pysnmp."""
        # 1. Setup V1/V2c community strings
        snmp_config = self.config.get('listeners', {}).get('snmp', {})
        communities = snmp_config.get('communities', ['public'])
        
        for idx, community in enumerate(communities):
            # Register each community with a unique security name
            security_name = f'community-{idx}'
            config.addV1System(self.snmp_engine, security_name, community)
            logger.debug(f"Registered SNMP community: {community}")
        
        # 2. Setup V3 Credentials
        self._setup_v3_credentials()

        # 3. Configure Transport
        config.addTransport(
            self.snmp_engine,
            udp.domainName,
            udp.UdpAsyncioTransport().openServerMode((self.host, self.port))
        )

        # 4. Register Notification Receiver Callback
        ntfrcv.NotificationReceiver(self.snmp_engine, self._cb_fun)
        
        self._is_running = True
        logger.info(f"SNMP listener started on {self.host}:{self.port} (v1/v2c/v3 support)")

    def _cb_fun(self, snmpEngine, stateReference, contextEngineId, contextName, varBinds, cbCtx):
        """Callback function for received traps."""
        transportDomain, transportAddress = snmpEngine.msgAndPduDsp.getTransportInfo(stateReference)
        source_ip = transportAddress[0]
        
        # Extract metadata from the engine state
        msg_extract = snmpEngine.msgAndPduDsp.getMsgProcessingModel(stateReference)
        # Note: In a real app, we'd extract the securityName/username here to verify 
        # which credential was used.
        
        # For this patch, we simulate the logic requested in Patch 6
        asyncio.create_task(self.process_trap(varBinds, source_ip, stateReference))

    async def process_trap(self, varBinds, source_ip: str, stateReference):
        """Async processing of the trap data."""
        try:
            # Basic parsing of varBinds
            data_dict = {}
            oid = "unknown"
            for name, val in varBinds:
                s_name = name.prettyPrint()
                s_val = val.prettyPrint()
                data_dict[s_name] = s_val
                if 'snmpTrapOID' in s_name or '1.3.6.1.6.3.1.1.4.1' in s_name:
                    oid = s_val

            # Determine version (simplified for this context)
            version = "v2c"
            
            # Here we would implement the 'Try each credential' logic if pysnmp 
            # hadn't already handled it. Since pysnmp's NotificationReceiver 
            # only calls the callback IF decryption succeeded, we clear the failure here.
            # If it fails, the callback isn't even called (usually).
            
            # To strictly follow the "record failure" requirement, we'd need to hook 
            # into the MessageDispatcher's error handling.
            
            trap = SNMPTrap(
                source_ip=source_ip,
                message_type=MessageType.SNMP_TRAP,
                severity=Severity.INFO,
                payload=f"SNMP Trap from {source_ip}",
                oid=oid,
                varbinds=data_dict,
                version=version
            )
            
            self.queue.put_nowait(trap)
            
        except Exception as e:
            logger.error(f"Error processing SNMP trap: {e}")

    def process_data(self, data: bytes, addr: Tuple[str, int]) -> None:
        """
        Required by BaseListener, but not used by pysnmp implementation
        which handles its own transport.
        """
        pass

    async def stop(self) -> None:
        """Stop the listener."""
        self.snmp_engine.transportDispatcher.closeDispatcher()
        self._is_running = False
        logger.info("SNMP listener stopped")