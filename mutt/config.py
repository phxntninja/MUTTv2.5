"""
Configuration and credential loading utilities for Mutt.
"""

import logging
import yaml
from typing import Dict, Any

from mutt.models.credentials import SNMPv3CredentialSet, SNMPv3Credential

logger = logging.getLogger(__name__)


def load_config(path: str) -> Dict[str, Any]:
    """
    Load configuration from a YAML file.
    
    Args:
        path: Path to the YAML configuration file
        
    Returns:
        Dictionary containing the configuration data
        
    Raises:
        FileNotFoundError: If the configuration file doesn't exist
        yaml.YAMLError: If the YAML file is malformed
    """
    try:
        with open(path, 'r', encoding='utf-8') as file:
            config_data = yaml.safe_load(file)
            return config_data if config_data is not None else {}
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file not found: {path}")
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Error parsing YAML file {path}: {e}")


class CredentialLoader:
    """Loader for SNMPv3 credentials from YAML."""

    @staticmethod
    def load_credentials(credentials_path: str) -> Dict[str, SNMPv3CredentialSet]:
        """
        Load SNMPv3 credentials from a YAML file.
        
        Args:
            credentials_path: Path to the credentials YAML file
            
        Returns:
            Dictionary keyed by username mapping to SNMPv3CredentialSet
        """
        try:
            with open(credentials_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            if not data or 'snmpv3_credentials' not in data:
                logger.warning(f"No SNMPv3 credentials found in {credentials_path}")
                return {}

            credentials_dict = {}
            for user_data in data['snmpv3_credentials']:
                username = user_data['username']
                creds_list = []
                
                for c in user_data.get('credentials', []):
                    credential = SNMPv3Credential(
                        priority=c['priority'],
                        auth_type=c['auth_type'],
                        auth_password=c['auth_password'],
                        priv_type=c['priv_type'],
                        priv_password=c['priv_password'],
                        active=c.get('active', True)
                    )
                    creds_list.append(credential)
                
                # Create set and ensure it's sorted by priority
                cred_set = SNMPv3CredentialSet(
                    username=username,
                    credentials=sorted(creds_list, key=lambda x: x.priority)
                )
                credentials_dict[username] = cred_set
                logger.info(f"Loaded credentials for user: {username}")
                
            return credentials_dict

        except FileNotFoundError:
            logger.warning(f"Credentials file not found: {credentials_path}")
            return {}
        except Exception as e:
            logger.error(f"Error loading credentials from {credentials_path}: {e}")
            return {}