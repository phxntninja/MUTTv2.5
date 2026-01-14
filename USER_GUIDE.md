# MUTT User Guide
**Multi-Use Telemetry Transport (MUTT)**

This guide provides comprehensive instructions for installing, configuring, using, monitoring, and troubleshooting the MUTT system.

---

## 1. Getting Started

### Installation and Setup

1.  **Prerequisites:**
    *   Python 3.10 or higher
    *   `virtualenv` (recommended)
    *   `sqlite3` (for CLI analysis)

2.  **Clone and Setup:**
    ```bash
    # Navigate to the project directory
    cd Coding_folders/MUTTv2.5

    # Create a virtual environment
    python3 -m venv .venv

    # Activate the environment
    source .venv/bin/activate

    # Install dependencies
    pip install -r requirements.txt
    ```

### Configuration (`mutt_config.yaml`)

The main configuration file is located at `config/mutt_config.yaml`.

```yaml
network:
  syslog_port: 8514      # Port for Syslog listener
  snmp_port: 8162        # Port for SNMP Trap listener

storage:
  db_path: "data/messages.db"       # Main storage database
  buffer_dir: "buffer"              # Temporary buffer for high-speed writes
  batch_write_interval: 2           # Seconds between DB commits (Lower = less data loss risk, Higher = better I/O)

listeners:
  syslog:
    enabled: true
    port: 8514
    host: '0.0.0.0'
  snmp:
    enabled: true
    port: 8162
    host: '0.0.0.0'
    communities:         # Allowed SNMP v1/v2c communities
      - 'public'
```

### Starting and Stopping the Daemon

**To Start (Foreground):**
```bash
python3 -m mutt.daemon --config config/mutt_config.yaml
```

**To Start (Background / Production):**
```bash
nohup python3 -m mutt.daemon --config config/mutt_config.yaml > mutt.out 2>&1 &
```

**To Stop:**
Find the process ID (PID) and kill it, or use `pkill`:
```bash
pkill -f "mutt.daemon"
```

### Verifying MUTT is Running
1.  **Check Processes:**
    ```bash
    ps aux | grep mutt
    ```
2.  **Check Listeners:**
    ```bash
    # Check if ports 8514 (Syslog) and 8162 (SNMP) are open
    ss -ulnp | grep -E "8514|8162"
    ```
3.  **Check Logs:**
    ```bash
    tail -f logs/mutt.log
    ```
    You should see `INFO | __main__ | MUTT daemon is running`.

---

## 2. Using MUTT

### Sending Test Messages

**Syslog Test (using `netcat`):**
```bash
# Send a basic UDP message to port 8514
echo "<13>Jan 13 10:00:00 localhost test-process: Hello MUTT" | nc -u -w 1 127.0.0.1 8514
```

**SNMP Trap Test (using included generator):**
We include a trap generator in the `trap_generator` folder.
```bash
# Activate generator venv if separate, or use main venv
python3 Coding_folders/trap_generator/main.py --target 127.0.0.1 --port 8162 --count 1
```

### Querying the Database

MUTT stores everything in `data/messages.db`. You can use the `sqlite3` CLI tool.

**Basic Query:**
```bash
sqlite3 -header -column data/messages.db "SELECT * FROM messages ORDER BY timestamp DESC LIMIT 5;"
```

**Filtering by Type:**
```bash
sqlite3 -header -column data/messages.db "SELECT timestamp, source_ip, payload FROM messages WHERE type='SNMP_TRAP' LIMIT 5;"
```

### Message Schema

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | TEXT | UUID, unique identifier for the message |
| `timestamp` | TEXT | ISO8601 timestamp (UTC) |
| `source_ip` | TEXT | IP address of the sender |
| `type` | TEXT | `SYSLOG`, `SNMP_TRAP`, etc. |
| `severity` | TEXT | `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `payload` | TEXT | The raw message content or human-readable summary |
| `metadata` | TEXT | JSON string containing parsed details (e.g., OIDs, facility) |

---

## 3. Performance Analysis

### Batch Write Logs
Check `logs/mutt.log` for throughput indicators.
```
INFO | mutt.processors.message_processor | Batch write: flushed 1046 messages to database
```
*   **High Flush Count:** System is handling high load efficiently.
*   **Low/Zero Count:** System is idle.

### Calculating Throughput (MPS)
Run this SQL query to see Messages Per Second for the last hour:
```bash
sqlite3 -header -column data/messages.db "SELECT strftime('%Y-%m-%d %H:%M:%S', timestamp) as time_sec, count(*) as mps FROM messages WHERE timestamp > datetime('now', '-1 hour') GROUP BY time_sec ORDER BY mps DESC LIMIT 10;"
```

### Monitoring Queue Depth
If MUTT cannot keep up with incoming traffic, the internal queue will fill up.
*   **Log Warning:** Look for `Message queue depth high` in `logs/mutt.log`.
*   **Remediation:** Increase `batch_write_interval` slightly if disk I/O is the bottleneck, or ensure your disk is fast (SSD).

---

## 4. Troubleshooting

### Common Issues

**1. "Address already in use" Error**
*   **Cause:** Another instance of MUTT is running, or another service (like rsyslog or snmptrapd) is holding the port.
*   **Fix:**
    ```bash
    # Find who is using the port
    sudo ss -ulnp | grep 8514
    # Kill the process
    kill <PID>
    ```

**2. Python `pysnmp` Dependencies (The "Dependency Hell")**
*   **Context:** `pysnmp` v7.x changed internal API names (e.g., `getTransportInfo` -> `get_transport_info`).
*   **Fix:** Ensure you are using the patched version of `snmp_listener.py` provided in MUTT v2.5. Do not manually downgrade `pysnmp` unless you revert the code changes.

**3. Messages Not Appearing in DB**
*   **Check 1:** Is the daemon running? (`ps aux | grep mutt`)
*   **Check 2:** Are ports blocked by firewall (`ufw`)?
*   **Check 3:** Verify the **Batch Interval**. Messages are buffered in memory and only written every `batch_write_interval` seconds (default 2s). Wait a few seconds and query again.

**4. High Packet Loss (UDP)**
*   **Symptoms:** You sent 7000 messages but only 4000 are in the DB.
*   **Diagnosis:** The OS UDP buffer is overflowing.
*   **Fix:**
    1.  Ensure `mutt_config.yaml` has a low `batch_write_interval` (e.g., 2).
    2.  Increase OS UDP buffers:
        ```bash
        sudo sysctl -w net.core.rmem_max=26214400
        sudo sysctl -w net.core.rmem_default=26214400
        ```

### Log Files
*   **Application Log:** `logs/mutt.log` (Main source of truth)
*   **Standard Output:** `mutt.out` (If running via nohup, contains startup crashes)

### Database Issues
If the database is locked:
*   MUTT uses WAL (Write-Ahead Logging) mode for concurrency.
*   Ensure no other process is holding an exclusive lock (e.g., a long-running open transaction in `sqlite3` CLI).
