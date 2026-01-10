import asyncio
import os
import socket
import sqlite3
import time
import yaml
import pytest
from mutt.daemon import MUTTDaemon

@pytest.mark.asyncio
async def test_full_integration(tmp_path):
    # 1. Setup temporary paths
    db_path = tmp_path / "test_mutt.db"
    buffer_dir = tmp_path / "buffer"
    archive_dir = tmp_path / "archives"
    log_file = tmp_path / "mutt.log"
    config_path = tmp_path / "mutt_config.yaml"
    
    buffer_dir.mkdir()
    archive_dir.mkdir()
    
    # 2. Create test configuration
    config = {
        'storage': {
            'db_path': str(db_path),
            'buffer_dir': str(buffer_dir),
            'archive_dir': str(archive_dir)
        },
        'listeners': {
            'syslog': {
                'enabled': True,
                'port': 5514,
                'host': '127.0.0.1'
            },
            'snmp': {
                'enabled': False
            }
        },
        'logging': {
            'file': str(log_file),
            'debug': True
        },
        'batch_write_interval': 1  # Flush quickly for testing
    }
    
    with open(config_path, 'w') as f:
        yaml.dump(config, f)
        
    # 3. Start MUTTDaemon
    daemon = MUTTDaemon()
    
    # We need to mock sys.argv so _parse_args finds our config
    import sys
    from unittest.mock import patch
    
    with patch.object(sys, 'argv', ['mutt', '--config', str(config_path)]):
        # Start daemon.main() in a background task
        daemon_task = asyncio.create_task(daemon.main())
        
        # Give it a moment to start
        await asyncio.sleep(1)
        
        try:
            # 4. Send a UDP Syslog packet
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            message = b"<14>Oct 11 22:14:15 myhost test: integration-test-message"
            sock.sendto(message, ("127.0.0.1", 5514))
            sock.close()
            
            # 5. Wait for processing
            # The MessageProcessor buffers messages and flushes them on stop or interval
            await asyncio.sleep(2)
            
            # 6. Stop the Daemon
            daemon.shutdown_event.set()
            
            # Wait for daemon to finish
            await asyncio.wait_for(daemon_task, timeout=5)
            
        except Exception as e:
            daemon_task.cancel()
            raise e

    # 7. Check the database
    assert os.path.exists(db_path), "Database file should exist"
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if message arrived
    # We need to know the table name. Based on previous phases it should be 'messages'
    cursor.execute("SELECT COUNT(*) FROM messages WHERE payload LIKE '%integration-test-message%'")
    count = cursor.fetchone()[0]
    conn.close()
    
    assert count > 0, "Message should be stored in the database"

if __name__ == "__main__":
    import pytest
    pytest.main([__file__])
