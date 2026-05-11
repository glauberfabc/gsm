import asyncio
import logging
from services.pncp_search_service import PNCPSearchService

logging.basicConfig(level=logging.INFO)

async def test():
    search = PNCPSearchService()
    termo = "canabidiol"
    
    print(f"--- Buscando '{termo}' no PNCP ---")
    results = await search.buscar(termo, limite=100)
    print(f"Total encontrados pela API: {len(results)}")
    
    print("\n--- Resolvendo e Filtrando ---")
    resolvidos = await search.buscar_e_resolver(termo, limite=100)
    print(f"Total finais (com arquivos e itens GSM): {len(resolvidos)}")
    
    for idx, r in enumerate(resolvidos[:5]):
        print(f"[{idx+1}] {r.get('orgao')} - {r.get('objeto')[:100]}...")

if __name__ == "__main__":
    asyncio.run(test())
