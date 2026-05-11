from abc import ABC, abstractmethod
from typing import List, Dict
import time
import random
from bs4 import BeautifulSoup
import requests
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class BaseScraper(ABC):
    def __init__(self, estado: str):
        self.estado = estado
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
    
    def _delay(self, min_seconds: float = 1.0, max_seconds: float = 3.0):
        """Rate limiting com delay aleatório"""
        time.sleep(random.uniform(min_seconds, max_seconds))
    
    def _validar_url(self, url: str) -> bool:
        """Valida se é URL HTTP(S) pública válida"""
        if not url:
            return False
        
        # CRÍTICO: Nunca permitir caminhos internos como /api/edital/...
        if url.startswith('/api/') or url.startswith('/edital/'):
            logger.error(f"URL inválida (caminho interno): {url}")
            return False
        
        # Deve começar com http:// ou https://
        if not url.startswith('http://') and not url.startswith('https://'):
            logger.error(f"URL inválida (não é HTTP/HTTPS): {url}")
            return False
        
        return True
    
    def _extract_tags(self, text: str) -> List[str]:
        """Extrai tags baseado em palavras-chave ESPECÍFICAS"""
        text_lower = text.lower()
        tags = []
        
        # Alto custo
        if any(keyword in text_lower for keyword in [
            'alto custo', 'componente especializado', 'ceaf'
        ]):
            tags.append('alto_custo')
        
        # IMPORTADO - CRITÉRIOS EXCLUSIVOS E ESPECÍFICOS
        # Só marca como importado se encontrar termos MUITO específicos de importação
        termos_importacao = [
            'aquisição de medicamentos importados',
            'aquisição de produtos importados',
            'núcleo de importação',
            'proforma invoice',
            'regulamento aduaneiro',
            'importacao.ce@saude.ce.gov.br',
            'importacao@saude',
            'sem registro no país',
            'ausência de registro anvisa',
            'sem registro anvisa',
            'rdc 660/2022',
            'rdc 660',
            'rdc 81/2009',
            'rdc 81',
            'portaria anvisa',
            'siscomex',
            'declaração de importação',
            'di - declaração',
            'excepcionalidade',
            'importação em caráter excepcional',
            'importação excepcional',
            'inexigibilidade',  # Forte indicativo de importado
            'dispensa de licitação'  # Forte indicativo
        ]
        
        if any(termo in text_lower for termo in termos_importacao):
            tags.append('importado')
        
        # Judicial
        if any(keyword in text_lower for keyword in [
            'judicial', 'ação judicial', 'determinação judicial', 
            'liminar', 'mandado de segurança', 'fornecimento via judicial'
        ]):
            tags.append('judicial')
        
        return tags
    
    @abstractmethod
    async def scrape(self, medicamento: str) -> List[Dict]:
        """Método abstrato para implementação do scraping"""
        pass
