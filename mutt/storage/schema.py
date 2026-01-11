"""
Database schema definition for Mutt network monitoring system.
"""

SCHEMA_SQL = """
-- Devices table: Stores discovered network devices
CREATE TABLE IF NOT EXISTS devices (
    ip TEXT PRIMARY KEY,
    hostname TEXT,
    last_seen TIMESTAMP,
    snmp_version TEXT,
    notes TEXT
);

-- Messages table: Stores collected SNMP traps and syslog messages
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    timestamp TIMESTAMP,
    source_ip TEXT,
    type TEXT,
    severity TEXT,
    payload TEXT,
    metadata TEXT
);

-- Archives table: Tracks archived message files
CREATE TABLE IF NOT EXISTS archives (
    filename TEXT PRIMARY KEY,
    start_date TIMESTAMP,
    end_date TIMESTAMP,
    record_count INTEGER
);

-- SNMPv3 Auth Failures table: Tracks failed authentication attempts
CREATE TABLE IF NOT EXISTS snmpv3_auth_failures (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    hostname TEXT,
    num_failures INTEGER DEFAULT 1,
    last_failure DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_source_ip ON messages(source_ip);
CREATE INDEX IF NOT EXISTS idx_messages_type ON messages(type);
CREATE INDEX IF NOT EXISTS idx_messages_severity ON messages(severity);
CREATE INDEX IF NOT EXISTS idx_devices_last_seen ON devices(last_seen);
CREATE INDEX IF NOT EXISTS idx_archives_dates ON archives(start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_snmpv3_failures_username ON snmpv3_auth_failures(username);
"""