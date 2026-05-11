import asyncio
import logging
import sys
import os

# Adicionar o diretório backend ao path para importar o scraper
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scrapers.bec_sp_client import BECSpClient

async def test_scraper():
    # Configurar logs detalhados
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Verificar API Key
    api_key = os.environ.get('EMERGENT_LLM_KEY')
    if not api_key:
        print("⚠️ AVISO: A variável de ambiente 'EMERGENT_LLM_KEY' não está configurada.")
        print("   O scraper não conseguirá resolver o CAPTCHA sem essa chave.")
    
    client = BECSpClient()
    termo = "insulina"
    
    print(f"🚀 Iniciando teste do scraper BEC SP para o termo: '{termo}'")
    
    try:
        resultados = await client.buscar_licitacoes(termo_busca=termo, limit=5)
        
        print("\n--- RESULTADOS ---")
        if not resultados:
            print("❌ Nenhum resultado encontrado.")
        else:
            print(f"✅ Encontrados {len(resultados)} resultados:")
            for idx, r in enumerate(resultados, 1):
                print(f"{idx}. {r.get('municipio', 'SP')} - {r.get('medicamento')} - {r.get('numero_pregao')}")
                print(f"   URL: {r.get('link_origem')}")
                print(f"   PDF: {r.get('link_documento')}")
                print("-" * 20)
                
    except Exception as e:
        print(f"💥 Erro fatal durante o teste: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_scraper())
