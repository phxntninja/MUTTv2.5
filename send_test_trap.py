import asyncio
from pysnmp.hlapi.asyncio import *

async def run():
    errorIndication, errorStatus, errorIndex, varBinds = await send_notification(
        SnmpEngine(),
        CommunityData('public', mpModel=1), # v2c
        await UdpTransportTarget.create(('127.0.0.1', 8162)),
        ContextData(),
        'trap',
        NotificationType(ObjectIdentity('1.3.6.1.6.3.1.1.5.1'))
    )

    if errorIndication:
        print(f"Error: {errorIndication}")
    else:
        print("Trap sent successfully")

if __name__ == "__main__":
    asyncio.run(run())
