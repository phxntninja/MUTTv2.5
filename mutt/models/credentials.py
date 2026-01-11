"""
Credential models for SNMPv3 authentication and privacy.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class SNMPv3Credential:
    """
    Single SNMPv3 credential set (auth/priv pair).
    
    Attributes:
        priority: Lower number = higher priority for rotation
        auth_type: Authentication protocol (e.g., 'SHA', 'MD5')
        auth_password: Authentication password/key
        priv_type: Privacy protocol (e.g., 'AES', 'DES')
        priv_password: Privacy password/key
        active: Whether this credential is currently active
    """
    priority: int
    auth_type: str
    auth_password: str
    priv_type: str
    priv_password: str
    active: bool = True


@dataclass
class SNMPv3CredentialSet:
    """
    Collection of credentials for a single username.
    
    Attributes:
        username: The SNMPv3 security name
        credentials: List of available credentials for this user
    """
    username: str
    credentials: List[SNMPv3Credential] = field(default_factory=list)

    def get_active_credentials(self) -> List[SNMPv3Credential]:
        """
        Return active credentials sorted by priority.
        
        Returns:
            List of SNMPv3Credential objects that are active,
            sorted with the lowest priority number first.
        """
        active_creds = [c for c in self.credentials if c.active]
        return sorted(active_creds, key=lambda x: x.priority)
