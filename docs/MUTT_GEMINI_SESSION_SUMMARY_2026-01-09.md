# Gemini Session Context: MUTT 2.5 Rebuild & Security Upgrade
**Date:** January 9, 2026
**Agent:** Gemini (Tech Lead)
**Project Root:** `~/Documents/Coding_folders/MUTTv2.5`

---

## 1. Session Objective
To architect, build, and verify **MUTT 2.5** (Multi-Use Telemetry Tool) using the `ai-hive` multi-agent framework, and subsequently upgrade it with robust SNMPv3 security features.

## 2. Methodology: "Rolling Context" Build
Instead of feeding the entire design document to the Hive Engineer at once, a phased approach was used to maintain context accuracy.

*   **Strategy:** Generate a specific `DESIGN.md` for Phase N -> Trigger Hive `/build` -> Verify -> Proceed to Phase N+1.
*   **Outcome:** Eliminated "context drift" and ensured each component (Models, Storage, Listeners) was fully functional before building dependencies on top of it.

## 3. Build History (Chronological)

### Phase 1: Foundation
*   **Action:** Defined `Message`, `SyslogMessage`, `SNMPTrap` data models and `ConfigLoader`.
*   **Result:** Core data structures established.

### Phase 2: Storage
*   **Action:** Implemented `aiosqlite` wrapper, `Schema` (messages, devices), and `DeviceRegistry` for auto-discovery.
*   **Key Decision:** Used async I/O for all DB operations to prevent blocking the event loop.

### Phase 3: Networking
*   **Action:** Built `SyslogListener` (UDP 5514) and `SNMPListener` (UDP 5162).
*   **Challenge:** `pysnmp` complexity was initially stubbed to ensure basic connectivity first.

### Phase 4: Processing Logic
*   **Action:** Implemented `Validator`, `PatternMatcher` (Regex/Keyword), `Enricher` (Reverse DNS), and `MessageRouter`.
*   **Fix:** Resolved a `TypeError` in dataclass inheritance (frozen vs. mutable) by standardizing on mutable dataclasses.

### Phase 5: Orchestration
*   **Action:** Created `MessageProcessor` to manage concurrent loops (Processing, Batch Writing, Archiving) and `MUTTDaemon` for signal handling.

### Phase 6: Integration
*   **Action:** Wired everything together with `run.sh` and a full end-to-end integration test.
*   **Result:** System verified operational.

## 4. Post-Build Upgrades (Manual Patching)
After the Hive build, Gemini assumed direct control to implement advanced features that required precise handling of legacy/modern library compatibility (`pysnmp-lextudio`).

**Applied Patches (1-11):**
1.  **Models:** Added `SNMPv3Credential` models.
2.  **Config:** Added `CredentialLoader` for YAML-based security config.
3.  **Security:** Created `snmpv3_credentials.yaml` template.
4.  **DB Schema:** Added `snmpv3_auth_failures` table.
5.  **Tracking:** Implemented `AuthFailureTracker` logic.
6.  **Listener Rewrite:** Completely rewrote `SNMPListener` to use `pysnmp`'s USM for v3 decryption.
7.  **Processor integration:** Wired tracker into the pipeline.
8.  **Daemon Update:** Loaded credentials on startup.
9.  **Dependencies:** Confirmed `pysnmp-lextudio` usage.
10. **Web Hook:** Added `get_snmpv3_auth_failures` to DB API.
11. **Dynamic Communities:** Added support for multiple v2c community strings via config.

## 5. Testing & Verification Results

### Infrastructure
*   **Env:** Dedicated `.venv` created and verified.
*   **Deps:** `aiosqlite`, `pyyaml`, `pysnmp-lextudio`, `pytest-asyncio`.

### Functional Tests
1.  **Unit Tests:** **100% Pass Rate** (72/72 tests). Fixed stale `test_frozen` test case.
2.  **Syslog:** **Verified.** 60+ messages generated and stored in DB.
3.  **SNMP:** **Partial.**
    *   **Success:** Daemon binds port 5162, receives packets, handles credentials.
    *   **Issue:** `pysnmp` callback signature mismatch causes `ProtocolError` on state reference lookup.
    *   **Mitigation:** Implemented error handling to prevent crash (defaults IP to 0.0.0.0), allowing the daemon to stay stable.

### Tool Repairs
*   **Trap Generator:** Fixed `engine.py` to use `pysnmp.hlapi.asyncio` instead of `v3arch` and corrected `ObjectIdentity` usage to fix "Malformed Object ID" errors.

## 6. Critical Context for Next Session
*   **Current State:** MUTT 2.5 is running and stable.
*   **Active Config:** `config/mutt_config.yaml`.
*   **Database:** `data/messages.db`.
*   **Known Limitation:** SNMP Trap source IP resolution is currently mocked to "0.0.0.0" due to library version conflicts. This needs a deep-dive fix in `mutt/listeners/snmp_listener.py` if accurate source IPs for traps are required.
*   **Next Steps:** Ready for UI development (Phase 7) or Webhook integration.

**End of Gemini Session Context**
