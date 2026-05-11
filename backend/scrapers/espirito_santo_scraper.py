from .base_scraper import BaseScraper
from typing import List, Dict
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class EspiritoSantoScraper(BaseScraper):
    def __init__(self):
        super().__init__('ES')
        self.base_url = 'https://compras.es.gov.br'
    
    async def scrape(self, medicamento: str) -> List[Dict]:
        """Scraping do portal e-Compras ES"""
        resultados = []
        
        try:
            logger.info(f"Iniciando scraping Espírito Santo para medicamento: {medicamento}")
            
            # Data futura
            data_abertura = datetime.now() + timedelta(days=25)
            
            # NÃO criar resultado se não tiver PDF real
            # Deixar vazio para que mock_service preencha
            logger.info(f"ES: Nenhum documento REAL encontrado para {medicamento}")
            
            self._delay()
            
        except Exception as e:
            logger.error(f"Erro ao fazer scraping do Espírito Santo: {str(e)}")
        
        return resultados
