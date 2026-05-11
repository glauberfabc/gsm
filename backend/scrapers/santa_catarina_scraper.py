"""
Scraper para o Portal de Compras de Santa Catarina usando Playwright
Portal: https://www.compras.sc.gov.br
"""

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from typing import List, Dict, Optional
import asyncio
import logging
import uuid
from datetime import datetime
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

class SantaCatarinaScraper(BaseScraper):
    """
    Scraper robusto para o portal Compras SC (compras.sc.gov.br)
    Este portal utiliza uma interface moderna baseada em componentes.
    """
    
    def __init__(self):
        super().__init__('SC')
        self.base_url = 'https://www.compras.sc.gov.br'
        self.search_url = f'{self.base_url}/sou-fornecedor'
        self.fonte = 'Compras SC'
        
    async def scrape(self, medicamento: str) -> List[Dict]:
        """
        Executa o scraping no portal SC procurando pelo medicamento fornecido.
        """
        resultados = []
        
        try:
            logger.info(f"🔍 [SC] Iniciando busca: '{medicamento}'")
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox']
                )
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    viewport={'width': 1280, 'height': 800}
                )
                page = await context.new_page()
                
                try:
                    # 1. Acessar página de busca
                    logger.info(f"  🌐 Acessando {self.search_url}...")
                    await page.goto(self.search_url, wait_until='networkidle', timeout=30000)
                    
                    # 2. Preencher filtros
                    logger.info(f"  ⌨️ Preenchendo palavra-chave: '{medicamento}'...")
                    await page.fill('input#palavraChave', medicamento)
                    
                    # 3. Pesquisar
                    logger.info("  🖱️ Clicando em Pesquisar...")
                    await page.click('button:has-text("Buscar")') # Nome visto no screenshot
                    await page.keyboard.press('Enter')
                    
                    # Esperar carregar resultados (cards)
                    try:
                        await page.wait_for_selector('button:has-text("Ver detalhes")', timeout=10000)
                    except:
                        logger.warning("  ⚠️ Timeout esperando cards. Tentando extrair o que houver.")
                    
                    # 4. Extrair cards
                    logger.info("  🗂️ Extraindo cards de resultados...")
                    # Seletor mais robusto para os cards de SC
                    cards = await page.query_selector_all('div.card-body, div.edital-card, .card')
                    
                    if not cards:
                        # Tentar encontrar via links de detalhes
                        detalhes = await page.query_selector_all('button:has-text("Ver detalhes"), a:has-text("Ver detalhes")')
                        cards = [await d.evaluate_handle('el => el.closest("div")') for d in detalhes]
                        
                    for card in cards:
                        text_content = await card.inner_text()
                        
                        # Filtro por medicamento
                        if medicamento.lower() in text_content.lower():
                            # Tentar extrair link de detalhes
                            link_elem = await card.query_selector('a')
                            link_detalhes = await link_elem.get_attribute('href') if link_elem else None
                            
                            # Extração básica de metadados do texto do card
                            licitacao = {
                                'id': str(uuid.uuid4()),
                                'medicamento': medicamento.capitalize(),
                                'estado': 'SC',
                                'orgao_licitante': self._extract_field(text_content, 'Órgão', 'Governo de SC'),
                                'status': 'Ativa',
                                'modalidade': self._extract_field(text_content, 'Modalidade', 'Pregão'),
                                'numero_processo': self._extract_field(text_content, 'Número', 'N/A'),
                                'data_abertura': None, # Difícil extrair sem seletor exato, deixamos para detalhes
                                'link_origem': f"{self.base_url}{link_detalhes}" if link_detalhes and link_detalhes.startswith('/') else (link_detalhes or self.base_url),
                                'link_documento': None,
                                'fonte': self.fonte,
                                'esfera': 'Estadual',
                                'objeto': text_content[:500],
                                'tags': self._extract_tags(text_content)
                            }
                            resultados.append(licitacao)
                            
                    logger.info(f"  ✅ Encontradas {len(resultados)} licitações no SC.")
                    
                finally:
                    await browser.close()
                    
            return resultados
            
        except Exception as e:
            logger.error(f"❌ [SC] Erro no scraping: {str(e)}")
            return []

    def _extract_field(self, text: str, field_name: str, default: str) -> str:
        """Extração rudimentar de campo em texto não estruturado"""
        pattern = f"{field_name}:? (.+)"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip().split('\n')[0]
        return default
