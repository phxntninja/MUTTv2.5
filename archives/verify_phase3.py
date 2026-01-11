import asyncio
import socket
import sys
import os

# Add current directory to sys.path to import mutt
sys.path.append(os.getcwd())

try:
    from mutt.listeners.syslog_listener import SyslogListener
    from mutt.listeners.snmp_listener import SNMPListener
except ImportError as e:
    print(f"Import Error: {e}")
    SyslogListener = None
    SNMPListener = None

async def send_udp(port, message):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(message, ("127.0.0.1", port))
    sock.close()

async def test_syslog():
    print("Testing Syslog Listener...")
    if SyslogListener is None:
        print("❌ SyslogListener not implemented")
        return False
    
    from mutt.models.message import Severity
    
    queue = asyncio.Queue()
    listener = SyslogListener(queue, port=5514)
    await listener.start()
    
    # Send RFC 3164 message
    raw_msg = b"<134>Jan 09 20:30:00 myhost myproc: test message"
    await send_udp(5514, raw_msg)
    
    # Wait for processing
    try:
        msg = await asyncio.wait_for(queue.get(), timeout=2.0)
        print(f"Received message: {msg}")
        assert msg.payload == "test message"
        assert msg.hostname == "myhost"
        # PRI 134: 134 >> 3 = 16 (Facility), 134 & 7 = 6 (Severity)
        assert msg.severity == Severity.INFO
        print("✅ Syslog Parsed OK")
        return True
    except asyncio.TimeoutError:
        print("❌ Syslog Timeout - No message received")
        return False
    except Exception as e:
        print(f"❌ Syslog Test Failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await listener.stop()

async def main():
    success = True
    try:
        if not await test_syslog():
            success = False
            
        if SNMPListener is None:
            print("❌ SNMPListener not implemented")
            success = False
        else:
            s = SNMPListener(asyncio.Queue(), port=5162)
            print("✅ SNMP Listener instantiated OK")
            
        if success:
            print("PHASE 3 COMPLETE")
        else:
            print("PHASE 3 INCOMPLETE")
            sys.exit(1)
    except Exception as e:
        print(f"❌ FAILED: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
