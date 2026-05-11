import asyncio
import aiohttp
import json

async def test_pncp_search():
    url = "https://pncp.gov.br/api/search/"
    params = {
        "q": "canabidiol",
        "tipos_documento": "edital",
        "ordenacao": "-data",
        "pagina": 1,
        "tam_pagina": 50
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            print(f"Status: {resp.status}")
            if resp.status == 200:
                data = await resp.json()
                print(f"Total found: {data.get('total')}")
                print(f"Items returned: {len(data.get('items', []))}")
                for item in data.get('items', [])[:3]:
                    print(f"- {item.get('objeto')[:100]}...")

if __name__ == "__main__":
    asyncio.run(test_pncp_search())
