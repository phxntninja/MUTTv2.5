import asyncio
import signal
import os
import sys

# Add current directory to path so we can import mutt
sys.path.append(os.getcwd())

try:
    from mutt.processors.message_processor import MessageProcessor
except ImportError:
    MessageProcessor = None

async def test_processor_lifecycle():
    print("Testing Processor Lifecycle...")
    if MessageProcessor is None:
        raise ImportError("MessageProcessor not implemented yet")

    queue = asyncio.Queue()
    config = {
        "storage": {"db_path": "test_phase5.db"},
        "rules_file": "config/alert_rules.yaml" # Ensure this exists
    }
    
    # Create dummy config file if needed
    if not os.path.exists("config"): os.makedirs("config")
    with open("config/alert_rules.yaml", "w") as f:
        f.write("rules: []")

    proc = MessageProcessor(config, queue)
    
    # Start (Mocking internal components if necessary, but integration is better)
    # We will just verify it creates the tasks and stops without error
    await proc.start()
    print("✅ Processor Started")
    
    await asyncio.sleep(0.1)
    
    await proc.stop()
    print("✅ Processor Stopped")

async def main():
    try:
        await test_processor_lifecycle()
        print("PHASE 5 COMPLETE")
    except Exception as e:
        print(f"❌ FAILED: {e}")
        # import traceback
        # traceback.print_exc()
        exit(1)

if __name__ == "__main__":
    asyncio.run(main())
