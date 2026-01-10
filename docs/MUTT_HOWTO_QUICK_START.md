# MUTT Documentation - Quick Start Guide

**Last Updated:** January 10, 2026  
**Status:** SNMPv3 Credential Support Complete

---

## 📂 Files in This Package

You have 4 main documents:

1. **MUTT_Design_Complete.md** — The bible (reference)
   - Full architectural design with code examples
   - Data models, component descriptions, database schema
   - Use this when you need implementation details

2. **MUTT_Implementation_Phases.md** — Phase overview
   - High-level breakdown of 6 phases
   - What gets built in each phase
   - Dependencies between phases

3. **MUTT_REBUILD_GUIDE_HIVE.md** — For rebuilding from scratch
   - Complete phase-by-phase rebuild instructions
   - Ready-to-use prompts for ai-hive Engineer agent
   - Use this if you need to rebuild MUTT completely

4. **MUTT_PATCH_GUIDE_GEMINI.md** — For patching existing code
   - 10 surgical patches to add SNMPv3 support
   - Each patch is independent and testable
   - Use this to upgrade your existing MUTT 2.5 codebase

---

## 🚀 Quick Start Scenarios

### Scenario 1: Upgrade Existing MUTT Code with SNMPv3

**You have:** Working MUTT 2.5 codebase  
**You want:** Add SNMPv3 credential support  
**Use:** MUTT_PATCH_GUIDE_GEMINI.md

**Steps:**
1. Open MUTT_PATCH_GUIDE_GEMINI.md
2. For each patch (1-9), copy the prompt for Gemini
3. Paste prompt into Claude/Gemini
4. Apply the generated code to your codebase
5. Test using the verification instructions
6. Move to next patch

**Time estimate:** 30-45 minutes (1 patch every 3-5 minutes)

---

### Scenario 2: Rebuild MUTT from Scratch

**You have:** Nothing, starting fresh  
**You want:** Complete MUTT with SNMPv3 built in  
**Use:** MUTT_REBUILD_GUIDE_HIVE.md

**Steps:**
1. Create Python virtual environment
2. Open MUTT_REBUILD_GUIDE_HIVE.md
3. For each phase (1-6):
   - Copy the phase prompt for Engineer agent
   - Feed to ai-hive
   - Review generated code
   - Test imports
   - Commit code
   - Move to next phase

**Time estimate:** 2-3 hours (6 phases × 20-30 min per phase)

---

### Scenario 3: Understand the Architecture

**You have:** A question about design  
**You want:** To understand how something works  
**Use:** MUTT_Design_Complete.md

**Examples:**
- "How does SNMPv3 credential lookup work?" → Search "6.1 SNMP Listener"
- "What tables does the database have?" → Search "7.1 Database Schema"
- "How does credential rotation work?" → Search "SNMPv3" or "priority"

---

## 🔧 Key Components Overview

### SNMPv3 Credential System

**What it does:**
- Loads SNMPv3 credentials from YAML file
- Tries credentials in priority order (1, 2, 3...)
- Tracks failed authentication attempts
- Allows credential rotation (old + new creds at same time)

**Key files:**
- `config/snmpv3_credentials.yaml` — Credentials definition
- `mutt/models/credentials.py` — Data structures
- `mutt/listeners/snmp_listener.py` — v3 decryption logic
- `mutt/storage/auth_failure_tracker.py` — Failure tracking

**Web UI feature:**
- Can display failed auth attempts by username
- Helps identify devices with bad credentials

---

### Database

**Main tables:**
- `messages` — All SNMP/syslog messages
- `devices` — Tracked devices (hostname, SNMP version, syslog seen)
- `snmpv3_auth_failures` — Failed v3 auth attempts
- `archives` — Metadata about archived message files

**Key feature:**
- Auto-archives messages > 1 day old when DB > 500MB
- Keeps device registry forever (useful for compliance)

---

### Message Pipeline

```
Network Device
    ↓
Listener (SNMP/Syslog)
    ↓
Shared Queue (asyncio.Queue)
    ↓
Message Processor
    ├─ Validator (check required fields)
    ├─ Pattern Matcher (regex/keyword rules)
    ├─ Enricher (DNS lookup, device tracking)
    └─ Message Router (STORE/WEBHOOK/DISCARD)
    ↓
Database (aiosqlite)
    ↓
Web UI (reads from DB)
```

---

## 📋 Patching Checklist

If using Gemini patches:

- [ ] **Patch 1:** Create credentials.py (new file)
- [ ] **Patch 2:** Add CredentialLoader to config.py
- [ ] **Patch 3:** Create snmpv3_credentials.yaml
- [ ] **Patch 4:** Add auth_failures table to schema.py
- [ ] **Patch 5:** Create auth_failure_tracker.py (new file)
- [ ] **Patch 6:** Update SNMPListener for v3
- [ ] **Patch 7:** Update MessageProcessor
- [ ] **Patch 8:** Update MUTTDaemon
- [ ] **Patch 9:** Update requirements.txt
- [ ] **Test:** Verify all imports work
- [ ] **Test:** Daemon starts cleanly
- [ ] **Test:** Send test data (syslog/SNMP)

---

## 🧪 Testing Quick Commands

### Test imports
```bash
python -c "from mutt.daemon import MUTTDaemon; print('OK')"
```

### Start daemon (30 sec test)
```bash
timeout 30 python -m mutt.daemon || true
```

### Send test syslog
```bash
echo "<14>Jan 10 12:00:00 testhost test: Hello" | nc -u -w0 127.0.0.1 5514
```

### Check database
```bash
sqlite3 data/messages.db "SELECT * FROM messages LIMIT 1;"
sqlite3 data/messages.db "SELECT * FROM devices;"
sqlite3 data/messages.db "SELECT * FROM snmpv3_auth_failures;"
```

---

## 📞 Which Document to Use When

| Question | Document |
|----------|----------|
| "How do I upgrade my existing code?" | PATCH_GUIDE_GEMINI |
| "How do I rebuild from scratch?" | REBUILD_GUIDE_HIVE |
| "What does component X do?" | DESIGN_COMPLETE |
| "What are the phases?" | IMPLEMENTATION_PHASES |
| "How do I authenticate SNMPv3?" | DESIGN_COMPLETE (section 5A) |
| "What's in the database?" | DESIGN_COMPLETE (section 7) |
| "I'm stuck, need details" | DESIGN_COMPLETE |

---

## 🎯 Most Likely Scenarios

### "I want to patch my existing code"
1. Read: **PATCH_GUIDE_GEMINI.md** (entire document)
2. Reference: **DESIGN_COMPLETE.md** (if you get stuck)
3. Execute: Patches 1-9 sequentially
4. Test: Using verification commands

### "I need to rebuild completely"
1. Read: **REBUILD_GUIDE_HIVE.md** (entire document)
2. Reference: **DESIGN_COMPLETE.md** (for code examples)
3. Execute: Phases 1-6 with Engineer agent
4. Test: After each phase

### "I need to understand SNMPv3 flow"
1. Search: **DESIGN_COMPLETE.md** for "SNMPv3"
2. Look at: Section 5A (Credential Loader)
3. Look at: Section 6.1 (SNMP Listener)
4. Look at: Section 7.6 (Auth Failure Tracker)

---

## 🔑 Key Features Recap

✅ **High-volume ingestion** — 9,000 messages/minute  
✅ **Async-first** — Non-blocking with asyncio  
✅ **SNMPv3 support** — Username-based credentials with priority rotation  
✅ **Auth failure tracking** — See which devices have bad creds  
✅ **Device inventory** — Track SNMP versions across infrastructure  
✅ **Message archiving** — Auto-archive to CSV when DB gets large  
✅ **Pattern matching** — Regex, keyword, exact matching rules  
✅ **Message routing** — STORE/WEBHOOK/DISCARD actions  
✅ **Graceful degradation** — File buffer when database fails  

---

## 🚨 Troubleshooting

**"Module not found"**
→ Check requirements.txt installed: `pip install -r requirements.txt`

**"Database not found"**
→ Normal on first run, will be created automatically

**"Port already in use"**
→ MUTT already running, or another service on 5162/5514

**"SNMPv3 auth fails"**
→ Check `snmpv3_credentials.yaml` exists and credentials are correct

**"Daemon crashes"**
→ Check log file at path configured in `mutt_config.yaml`

---

## 📚 Documentation Structure

```
├── MUTT_Design_Complete.md
│   ├── Executive Summary
│   ├── Architecture Overview
│   ├── Data Models (5, 5A)
│   ├── Components (6.1-7.6)
│   ├── Build Instructions (10)
│   └── Deployment Checklist (14)
│
├── MUTT_Implementation_Phases.md
│   ├── Phase 1: Models & Config
│   ├── Phase 2: Storage
│   ├── Phase 3: Listeners
│   ├── Phase 4: Processors
│   ├── Phase 5: Main Daemon
│   └── Phase 6: Integration
│
├── MUTT_REBUILD_GUIDE_HIVE.md
│   ├── Overview
│   ├── Phase 1-6 with full prompts
│   ├── Testing instructions
│   └── Hive workflow notes
│
└── MUTT_PATCH_GUIDE_GEMINI.md
    ├── Overview
    ├── Patch 1-9 with full prompts
    ├── Testing after each patch
    └── Rollback plan
```

---

## 💾 Recommended Workflow

**If patching existing code:**

1. Download all 4 files
2. Read PATCH_GUIDE_GEMINI completely (30 min)
3. Have DESIGN_COMPLETE nearby for reference
4. Apply patches 1-9 sequentially
5. Test after each patch
6. Done!

**If rebuilding:**

1. Download all 4 files
2. Read REBUILD_GUIDE_HIVE completely (20 min)
3. Have DESIGN_COMPLETE nearby for reference
4. Run phases 1-6 with Engineer agent
5. Test after each phase
6. Done!

---

## 📖 How to Read the Design Doc

MUTT_Design_Complete.md is structured as:

**Sections 1-4:** Background (skim these)  
**Sections 5-7:** Data structures and components (READ if you're implementing)  
**Section 8:** Main daemon (READ if implementing)  
**Sections 9-14:** Reference material (look up as needed)

Use Ctrl+F to search for:
- Component names: "SNMPListener", "Database", etc.
- Features: "SNMPv3", "credential", "archive", etc.
- Table names: "messages", "devices", etc.

---

## ✅ Final Checklist Before You Go

- [ ] All 4 files downloaded
- [ ] Understand which scenario applies to you
- [ ] Know which document to use first
- [ ] Saved somewhere accessible later
- [ ] Ready to start patching or rebuilding

---

**You're all set!**

The documentation is self-contained. You can pick it up anytime and make progress.

Start with either:
- **MUTT_PATCH_GUIDE_GEMINI.md** (if you have existing code to upgrade)
- **MUTT_REBUILD_GUIDE_HIVE.md** (if you're building from scratch)

Good luck! 🚀
