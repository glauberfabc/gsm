"""
Scraper para o Portal de Compras do Rio Grande do Sul usando Playwright
Portal: https://www.compras.rs.gov.br
"""

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from typing import List, Dict, Optional
import asyncio
import logging
import uuid
import re
from datetime import datetime, timedelta
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

class RioGrandeDoSulScraper(BaseScraper):
    """
    Scraper robusto para o portal Compras RS (compras.rs.gov.br)
    Utiliza Playwright para navegação e extração de dados.
    """
    
    def __init__(self):
        super().__init__('RS')
        self.base_url = 'https://www.compras.rs.gov.br'
        self.search_url = f'{self.base_url}/editais/pesquisar'
        self.fonte = 'Compras RS'
        
    async def scrape(self, medicamento: str) -> List[Dict]:
        """
        Executa o scraping no portal RS procurando pelo medicamento fornecido.
        """
        resultados = []
        
        try:
            logger.info(f"🔍 [RS] Iniciando busca: '{medicamento}'")
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox', 
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--no-zygote',
                        '--disable-extensions'
                    ]
                )
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    viewport={'width': 1280, 'height': 800}
                )
                
                # Bloquear carregamento de imagens, fontes e CSS para economizar RAM
                await context.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font", "stylesheet"] else route.continue_())
                
                page = await context.new_page()
                
                try:
                    # 1. Acessar página de busca
                    logger.info(f"  🌐 Acessando {self.search_url}...")
                    await page.goto(self.search_url, wait_until='networkidle', timeout=30000)
                    
                    # Aceitar cookies se aparecer
                    try:
                        await page.click('button:has-text("Aceitar")', timeout=3000)
                    except:
                        pass
                        
                    # 2. Preencher filtros
                    logger.info(f"  ⌨️ Preenchendo filtros para '{medicamento}'...")
                    
                    # Descrição do Objeto
                    await page.fill('input#description', medicamento)
                    
                    # Datas (últimos 90 dias para garantir resultados)
                    data_fim = datetime.now()
                    data_inicio = data_fim - timedelta(days=90)
                    
                    await page.fill('input#publicationStartDate', data_inicio.strftime('%d/%m/%Y'))
                    await page.fill('input#publicationEndDate', data_fim.strftime('%d/%m/%Y'))
                    
                    # 3. Clicar em Pesquisar
                    logger.info("  🖱️ Clicando em Pesquisar...")
                    # Tentar vários seletores para o botão de pesquisa
                    btn_search = await page.query_selector('button#PsButton_pesquisar, button:has-text("Pesquisar"), .btn-success')
                    if btn_search:
                        await btn_search.click()
                    else:
                        await page.keyboard.press('Enter')
                    
                    # Esperar resultados ou mensagem de "nenhum registro"
                    try:
                        await page.wait_for_selector('table#resultTable', timeout=10000)
                    except PlaywrightTimeout:
                        logger.info(f"  ℹ️ Nenhum resultado encontrado para '{medicamento}' no RS.")
                        return []
                    
                    # 4. Extrair dados da tabela
                    logger.info("  📊 Extraindo dados da tabela de resultados...")
                    rows = await page.query_selector_all('table#resultTable tbody tr[role="row"]')
                    
                    for row in rows:
                        cols = await row.query_selector_all('td')
                        if len(cols) >= 7:
                            # 1. Central de Compras | 2. Processo | 3. Edital | 4. Publicação | 5. Modalidade | 6. Objeto | 7. Abertura
                            
                            processo_text = await cols[1].inner_text()
                            edital_elem = await cols[2].query_selector('a.table-link')
                            edital_text = await edital_elem.inner_text() if edital_elem else "N/A"
                            link_detalhes = await edital_elem.get_attribute('href') if edital_elem else None
                            
                            data_pub_text = await cols[3].inner_text()
                            modalidade = await cols[4].inner_text()
                            objeto = await cols[5].inner_text()
                            data_abertura_text = await cols[6].inner_text()
                            
                            # Filtro extra no objeto (case-insensitive)
                            if medicamento.lower() in objeto.lower():
                                licitacao = {
                                    'id': str(uuid.uuid4()),
                                    'medicamento': medicamento.capitalize(),
                                    'estado': 'RS',
                                    'orgao_licitante': await cols[0].inner_text(),
                                    'status': 'Ativa',
                                    'modalidade': modalidade,
                                    'numero_processo': f"{processo_text} / {edital_text}",
                                    'data_abertura': self._parse_date_rs(data_abertura_text),
                                    'link_origem': f"{self.base_url}{link_detalhes}" if link_detalhes else self.base_url,
                                    'link_documento': None, # Será extraído em navegação profunda se necessário
                                    'fonte': self.fonte,
                                    'esfera': 'Estadual',
                                    'objeto': objeto[:500],
                                    'tags': self._extract_tags(objeto)
                                }
                                resultados.append(licitacao)
                                
                    logger.info(f"  ✅ Encontradas {len(resultados)} licitações no RS.")
                    
                finally:
                    await browser.close()
                    
            return resultados
            
        except Exception as e:
            logger.error(f"❌ [RS] Erro no scraping: {str(e)}")
            return []

    def _parse_date_rs(self, text: str) -> Optional[datetime]:
        """Parse de data do formato RS: dd/mm/aaaa hh:mm"""
        if not text:
            return None
        try:
            # Remover tags HTML se houver
            text = re.sub(r'<[^>]*>', '', text).strip()
            # Formatos comuns no portal RS
            for fmt in ('%d/%m/%Y %H:%M', '%d/%m/%Y'):
                try:
                    return datetime.strptime(text, fmt)
                except ValueError:
                    continue
            return None
        except:
            return None
