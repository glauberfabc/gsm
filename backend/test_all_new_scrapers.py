import asyncio
import logging
import sys
import os

# Adicionar o diretório pai ao path para permitir imports do backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.scrapers.rio_grande_do_sul_scraper import RioGrandeDoSulScraper
from backend.scrapers.santa_catarina_scraper import SantaCatarinaScraper
from backend.scrapers.rio_de_janeiro_scraper import RioDeJaneiroScraper
from backend.scrapers.minas_gerais_scraper import MinasGeraisScraper

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_scraper(name, scraper_instance, term):
    logger.info(f"\n--- Testando {name} ---")
    try:
        # RS e SC usam o método 'scrape' (padrão BaseScraper)
        # RJ e MG podem usar 'buscar_licitacoes' ou 'scrape' (depende da implementação)
        if hasattr(scraper_instance, 'scrape'):
            results = await scraper_instance.scrape(term)
        else:
            results = await scraper_instance.buscar_licitacoes(term)
            
        logger.info(f"✅ {name}: Encontrados {len(results)} resultados.")
        
        if results:
            first = results[0]
            logger.info(f"   Exemplo: {first.get('numero_processo', 'Sem número')} - {first.get('objeto', '')[:100]}...")
            logger.info(f"   Link: {first.get('link_origem', 'Sem link')}")
            if first.get('link_documento'):
                logger.info(f"   📄 Documento: {first.get('link_documento')}")
            else:
                logger.warning(f"   ⚠️ Sem link direto para documento no {name}")
    except Exception as e:
        logger.error(f"❌ Erro ao testar {name}: {str(e)}")

async def main():
    term = "medicamento"
    
    scrapers = [
        ("Rio Grande do Sul", RioGrandeDoSulScraper()),
        ("Santa Catarina", SantaCatarinaScraper()),
        ("Rio de Janeiro", RioDeJaneiroScraper()),
        ("Minas Gerais", MinasGeraisScraper())
    ]
    
    tasks = []
    for name, instance in scrapers:
        tasks.append(test_scraper(name, instance, term))
    
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
