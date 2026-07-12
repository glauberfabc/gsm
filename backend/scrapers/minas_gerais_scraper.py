"""
Scraper para Portal de Compras de Minas Gerais usando Playwright
URL: https://compras.mg.gov.br

Estratégia:
- Navegação com Playwright (browser real para JavaScript)
- Navegação dupla: Lista → Detalhes → PDF
- Extração de metadados completos
- Link direto para documento

Criado: Dezembro 2024
Atualizado: Playwright implementado seguindo padrão BEC/SP
"""

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from datetime import datetime
import logging
import asyncio
import re
import uuid

logger = logging.getLogger(__name__)

class MinasGeraisScraper:
    """
    Scraper para Portal de Compras de Minas Gerais - COM PLAYWRIGHT
    
    Portal: https://compras.mg.gov.br
    Modalidade: Pregão Eletrônico, Cotações, Concorrências
    Tecnologia: Playwright (navegador real para JavaScript)
    """
    
    def __init__(self):
        self.base_url = 'https://compras.mg.gov.br'
        self.search_url = f'{self.base_url}/acesso-a-informacoes/consultas/'
        
        # URLs específicas dos sistemas de consulta
        self.sistema_pregoes = 'https://www1.compras.mg.gov.br/processocompra/pregao/consulta/consultaPregoes.html'
        self.sistema_cotep = 'https://www1.compras.mg.gov.br/processocompra/cotacao/consulta/pesquisaConsultaCotacoesEletronicas.html'
        self.sistema_processos = 'https://www1.compras.mg.gov.br/processocompra/processo/consultaProcessoCompra.html'
        
        # URLs da nova lei (14.133/21) - Sistema REACT
        self.sistema_pregao_nova_lei = 'https://www1.compras.mg.gov.br/n/procedimentolei14133/consulta/publico'
        self.sistema_cotep_nova_lei = 'https://www1.compras.mg.gov.br/n/cotacao/consulta/publico'
        
        self.estado = 'MG'
        self.fonte = 'Portal MG'
    
    async def buscar_licitacoes(
        self, 
        termo_busca: str = None, 
        apenas_futuras: bool = False, 
        limit: int = 20
    ) -> List[Dict]:
        """
        Busca licitações no Portal de Minas Gerais - MÉTODO ASSÍNCRONO COM PLAYWRIGHT
        
        Args:
            termo_busca: Termo para filtrar (medicamento)
            apenas_futuras: Se True, retorna apenas licitações futuras
            limit: Número máximo de resultados
            
        Returns:
            Lista de dicionários com dados das licitações
        """
        resultados = []
        
        try:
            logger.info(f"🔍 [MG] Iniciando busca: '{termo_busca or 'geral'}'")
            
            async with async_playwright() as p:
                # Iniciar browser com configurações robustas (igual BEC/SP)
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
                    viewport={'width': 1920, 'height': 1080}
                )
                
                # Bloquear carregamento de imagens, fontes e CSS para economizar RAM
                await context.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font", "stylesheet"] else route.continue_())
                
                page = await context.new_page()
                
                try:
                    # ETAPA 1: Tentar sistema novo (Lei 14.133/21) primeiro
                    logger.info("  🌐 Acessando sistema novo (Lei 14.133)...")
                    links_licitacoes = await self._buscar_sistema_novo(page, termo_busca)
                    
                    # ETAPA 2: Se não encontrar, tentar sistema antigo (Lei 8.666)
                    if not links_licitacoes:
                        logger.info("  🔄 Tentando sistema antigo (Lei 8.666)...")
                        links_licitacoes = await self._buscar_sistema_antigo(page, termo_busca)
                    
                    logger.info(f"  ✅ Encontrados {len(links_licitacoes)} links")
            
                    # ETAPA 3: Processar cada licitação
                    for idx, link_info in enumerate(links_licitacoes[:limit], 1):
                        try:
                            logger.info(f"    📄 [{idx}/{min(len(links_licitacoes), limit)}] Processando...")
                            
                            # Navegação dupla: acessar detalhes (com Playwright)
                            licitacao = await self._extrair_detalhes_licitacao(
                                page,
                                link_info['url'],
                                link_info.get('texto', '')
                            )
                            
                            if licitacao:
                                # Filtrar por data se solicitado
                                if apenas_futuras:
                                    data_final = licitacao.get('data_final')
                                    if data_final and isinstance(data_final, datetime):
                                        if data_final < datetime.now():
                                            continue
                                
                                resultados.append(licitacao)
                                logger.info("    ✅ Licitação processada")
                            
                            # Rate limiting
                            await asyncio.sleep(1.5)
                            
                        except Exception as e:
                            logger.error(f"    ❌ Erro ao processar licitação {idx}: {str(e)}")
                            continue
                    
                    logger.info(f"🎯 [MG] Total processado: {len(resultados)} licitações")
                    
                finally:
                    await browser.close()
            
            return resultados
            
        except Exception as e:
            logger.error(f"❌ [MG] Erro geral: {str(e)}")
            return []
    
    async def _buscar_sistema_novo(self, page, termo_busca: str = None) -> List[Dict]:
        """
        Busca no sistema novo (Lei 14.133/21) - COM PLAYWRIGHT
        Sistemas: Pregão/Concorrência e COTEP
        
        Args:
            page: Playwright page object
            termo_busca: Termo para filtrar
            
        Returns:
            Lista de links de licitações
        """
        links = []
        
        try:
            # Acessar página de pregões com Playwright  
            logger.debug("    Carregando aplicação React...")
            await page.goto(self.sistema_pregao_nova_lei, wait_until='networkidle', timeout=30000)
            
            # Aguardar React renderizar
            try:
                await page.wait_for_selector('#react-root', timeout=5000)
                await asyncio.sleep(5)  # React App carregar
            except:
                await asyncio.sleep(8)
            
            # Extrair HTML após React
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            # React geralmente usa divs, tables ou grids
            seletores = [
                'table tbody tr',  # Tabelas React
                'div[role="row"]',  # Grid React
                'div.MuiDataGrid-row',  # Material-UI
                'div.row-item',
                'table tr',
                'div.card'
            ]
            
            for seletor in seletores:
                elementos = soup.select(seletor)
                if elementos:
                    for elem in elementos[:10]:  # Limitar a 10 primeiros
                        # Buscar link dentro do elemento
                        link_elem = elem.find('a')
                        if link_elem:
                            href = link_elem.get('href', '')
                            texto = elem.get_text(strip=True)
                            
                            if href and href != '#':
                                # Filtrar por termo
                                if termo_busca and termo_busca.lower() not in texto.lower():
                                    continue
                                
                                # URL completa
                                if not href.startswith('http'):
                                    href = f'{self.base_url}{href}' if href.startswith('/') else f'{self.base_url}/{href}'
                                
                                links.append({
                                    'url': href,
                                    'texto': texto[:200]
                                })
                    
                    if links:
                        break
            
            return links
            
        except Exception as e:
            logger.debug(f"    ⚠️ Erro sistema novo: {str(e)}")
            return []
    
    async def _buscar_sistema_antigo(self, page, termo_busca: str = None) -> List[Dict]:
        """
        Busca no sistema antigo (Lei 8.666/93 e 10.520/02) - COM PLAYWRIGHT
        Sistema: Pregões tradicionais
        
        Args:
            page: Playwright page object
            termo_busca: Termo para filtrar
            
        Returns:
            Lista de links de licitações
        """
        links = []
        
        try:
            # Acessar sistema de pregões antigo com Playwright
            await page.goto(self.sistema_pregoes, wait_until='domcontentloaded', timeout=20000)
            await asyncio.sleep(3)  # Aguardar JavaScript
            
            # Extrair HTML após JavaScript
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            # Sistema antigo geralmente usa tabelas
            tabelas = soup.find_all('table')
            for tabela in tabelas:
                linhas = tabela.find_all('tr')
                for linha in linhas[1:11]:  # Pular header, pegar 10
                    colunas = linha.find_all('td')
                    if colunas:
                        # Buscar link na linha
                        link_elem = linha.find('a')
                        if link_elem:
                            href = link_elem.get('href', '')
                            texto = linha.get_text(strip=True)
                            
                            if href and href != '#':
                                # Filtrar por termo
                                if termo_busca and termo_busca.lower() not in texto.lower():
                                    continue
                                
                                # URL completa
                                base_sistema = 'https://www1.compras.mg.gov.br'
                                if not href.startswith('http'):
                                    href = f'{base_sistema}{href}' if href.startswith('/') else f'{base_sistema}/{href}'
                                
                                links.append({
                                    'url': href,
                                    'texto': texto[:200]
                                })
                
                if links:
                    break
            
            return links
            
        except Exception as e:
            logger.debug(f"    ⚠️ Erro sistema antigo: {str(e)}")
            return []
    
    async def _extrair_detalhes_licitacao(
        self,
        page,
        url: str, 
        titulo: str
    ) -> Optional[Dict]:
        """
        Navega para página de detalhes e extrai metadados completos - COM PLAYWRIGHT
        Implementa NAVEGAÇÃO DUPLA para obter link direto do PDF
        
        Args:
            page: Playwright page object
            url: URL da página de detalhes
            titulo: Título/texto do link original
            
        Returns:
            Dict com dados completos ou None
        """
        try:
            logger.debug(f"      🔍 Acessando detalhes: {url[:80]}...")
            
            # Acessar página de detalhes com Playwright
            await page.goto(url, wait_until='domcontentloaded', timeout=20000)
            await asyncio.sleep(2)  # Aguardar JavaScript
            
            # Extrair HTML após JavaScript
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            # Extrair metadados
            dados = self._extrair_metadados(soup, titulo)
            
            # CRÍTICO: Extrair link direto do PDF (NAVEGAÇÃO DUPLA)
            link_documento = self._extrair_link_pdf(soup)
            
            # Montar resultado
            return {
                'id': str(uuid.uuid4()),
                'medicamento': dados.get('medicamento', 'Medicamento não especificado'),
                'estado': self.estado,
                'orgao_licitante': dados.get('orgao', 'Órgão MG'),
                'status': dados.get('status', 'Ativa'),
                'modalidade': dados.get('modalidade', 'Pregão Eletrônico'),
                'numero_processo': dados.get('numero_processo', 'N/A'),
                'data_final': dados.get('data_final'),
                'data_abertura': dados.get('data_abertura'),
                'link_origem': url,
                'link_documento': link_documento,
                'fonte': self.fonte,
                'esfera': 'Estadual',
                'objeto': dados.get('objeto', titulo[:200]),
                'is_mock': False
            }
            
        except Exception as e:
            logger.error(f"      ❌ Erro ao extrair detalhes: {str(e)}")
            return None
    
    def _extrair_metadados(
        self, 
        soup: BeautifulSoup, 
        titulo_fallback: str
    ) -> Dict:
        """
        Extrai metadados da página de detalhes
        
        Args:
            soup: BeautifulSoup da página
            titulo_fallback: Título para usar como fallback
            
        Returns:
            Dict com metadados extraídos
        """
        dados = {}
        
        try:
            # Objeto/Descrição
            objeto = None
            for seletor in ['div.objeto', 'p.descricao', 'div.detalhe-objeto']:
                elem = soup.select_one(seletor)
                if elem:
                    objeto = elem.get_text(strip=True)
                    break
            dados['objeto'] = objeto or titulo_fallback
            
            # Medicamento (extrair do objeto)
            dados['medicamento'] = self._extrair_medicamento_texto(dados['objeto'])
            
            # Órgão
            orgao = None
            for seletor in ['div.orgao', 'span.orgao', 'p.orgao']:
                elem = soup.select_one(seletor)
                if elem:
                    orgao = elem.get_text(strip=True)
                    break
            dados['orgao'] = orgao or 'Governo de Minas Gerais'
            
            # Modalidade
            modalidade = None
            for seletor in ['span.modalidade', 'div.tipo', 'p.modalidade']:
                elem = soup.select_one(seletor)
                if elem:
                    modalidade = elem.get_text(strip=True)
                    break
            dados['modalidade'] = modalidade or 'Pregão Eletrônico'
            
            # Número do processo
            numero = None
            for seletor in ['span.numero', 'div.processo', 'p.numero-processo']:
                elem = soup.select_one(seletor)
                if elem:
                    numero = elem.get_text(strip=True)
                    break
            dados['numero_processo'] = numero or 'N/A'
            
            # Datas
            dados['data_abertura'] = self._extrair_data(soup, 'abertura')
            dados['data_final'] = self._extrair_data(soup, 'encerramento')
            
            # Status
            dados['status'] = self._determinar_status(dados['data_final'])
            
            return dados
            
        except Exception as e:
            logger.debug(f"      ⚠️ Erro ao extrair metadados: {str(e)}")
            return dados
    
    def _extrair_link_pdf(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extrai link direto para PDF do edital
        NAVEGAÇÃO DUPLA implementada aqui
        
        Args:
            soup: BeautifulSoup da página de detalhes
            
        Returns:
            URL do PDF ou None
        """
        try:
            # Buscar links para PDF/documentos
            seletores_pdf = [
                'a[href$=".pdf"]',
                'a[href*="edital"][href*=".pdf"]',
                'a[href*="documento"]',
                'a.btn-download',
                'a[title*="Edital"]',
                'a:contains("Download")',
                'a:contains("Baixar")'
            ]
            
            for seletor in seletores_pdf:
                links = soup.select(seletor)
                for link in links:
                    href = link.get('href', '')
                    texto = link.get_text(strip=True).lower()
                    
                    # Priorizar edital
                    if 'edital' in texto or 'pdf' in href.lower():
                        # Construir URL completa
                        if href.startswith('http'):
                            return href
                        elif href.startswith('/'):
                            return f'{self.base_url}{href}'
                        else:
                            return f'{self.base_url}/{href}'
            
            return None
            
        except Exception as e:
            logger.debug(f"      ⚠️ Erro ao extrair PDF: {str(e)}")
            return None
    
    def _extrair_data(
        self, 
        soup: BeautifulSoup, 
        tipo: str
    ) -> Optional[datetime]:
        """
        Extrai data da página
        
        Args:
            soup: BeautifulSoup
            tipo: 'abertura' ou 'encerramento'
            
        Returns:
            datetime ou None
        """
        try:
            # Buscar elementos que contenham a data
            seletores = [
                f'span.data-{tipo}',
                f'div.{tipo}',
                f'p.data-{tipo}'
            ]
            
            for seletor in seletores:
                elem = soup.select_one(seletor)
                if elem:
                    texto = elem.get_text(strip=True)
                    return self._parse_date(texto)
            
            return None
            
        except Exception:
            return None
    
    def _extrair_medicamento_texto(self, texto: str) -> str:
        """
        Tenta extrair nome do medicamento do texto
        
        Args:
            texto: Texto do objeto/descrição
            
        Returns:
            Nome do medicamento ou texto truncado
        """
        if not texto:
            return 'Medicamento não especificado'
        
        # Lista de palavras-chave comuns
        palavras_medicamento = [
            'insulina', 'dipirona', 'paracetamol', 'ibuprofeno',
            'amoxicilina', 'azitromicina', 'metformina', 'losartana',
            'canabidiol', 'adalimumabe', 'pembrolizumabe'
        ]
        
        texto_lower = texto.lower()
        for palavra in palavras_medicamento:
            if palavra in texto_lower:
                return palavra.capitalize()
        
        # Fallback: primeiras palavras
        palavras = texto.split()
        return ' '.join(palavras[:3]) if len(palavras) > 3 else texto[:50]
    
    def _determinar_status(self, data_final: Optional[datetime]) -> str:
        """Determina status da licitação baseado na data final"""
        if not data_final:
            return 'Ativa'
        
        if data_final > datetime.now():
            return 'Ativa'
        else:
            return 'Encerrada'
    
    def _parse_date(self, texto: str) -> Optional[datetime]:
        """
        Parse de data em português
        
        Args:
            texto: String com data (ex: "15/12/2024 14:30")
            
        Returns:
            datetime ou None
        """
        if not texto:
            return None
        
        # Extrair apenas números e barras/dois-pontos
        texto_limpo = re.sub(r'[^\d/:\s]', '', texto)
        
        # Tentar vários formatos
        formatos = [
            '%d/%m/%Y %H:%M',
            '%d/%m/%Y',
            '%d-%m-%Y %H:%M',
            '%d-%m-%Y',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d'
        ]
        
        for formato in formatos:
            try:
                return datetime.strptime(texto_limpo.strip(), formato)
            except:
                continue
        
        return None
