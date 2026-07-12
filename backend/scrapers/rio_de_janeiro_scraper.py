"""
Scraper para Portal de Compras do Rio de Janeiro usando Playwright
URL: https://www.compras.rj.gov.br

Estratégia:
- Navegação com Playwright (browser real para JavaScript)
- Busca via formulário em /EditaisLicitacoes/buscar.action
- Navegação dupla: Lista → Detalhes → PDF
- Extração de metadados completos conforme especificação

Metadados MANDATÓRIOS:
- titulo_licitacao
- orgao_licitante
- modalidade (Pregão Eletrônico, Concorrência, etc.)
- numero_processo
- data_abertura/data_limite
- estado_uf (RJ)
- status_aquisicao
- link_documento (PDF direto via NAVEGAÇÃO DUPLA)

Criado: Dezembro 2024/2025
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


class RioDeJaneiroScraper:
    """
    Scraper para Portal de Compras do Estado do Rio de Janeiro - COM PLAYWRIGHT
    
    Portal: https://www.compras.rj.gov.br
    Sistema: SIGA - Sistema Integrado de Gestão de Aquisições
    Modalidades: Pregão Eletrônico, Concorrência, PED
    Tecnologia: Playwright (navegador real para JavaScript)
    """
    
    def __init__(self):
        self.base_url = 'https://www.compras.rj.gov.br'
        self.search_url = f'{self.base_url}/EditaisLicitacoes/buscar.action'
        
        self.estado = 'RJ'
        self.fonte = 'Portal Compras RJ (SIGA)'
        
        # Seletores CSS para o portal RJ (ATUALIZADOS)
        self.selectors = {
            'campo_objeto': [
                '#objetoLic',
                'input[name="filtro.objetoLic"]',
                'input[id="objetoLic"]'
            ],
            'botao_pesquisar': [
                'a.pesquisar',
                'a[href="#"]:has-text("PESQUISAR")',
                'a[onclick*="pesquisar"]',
                'button:has-text("PESQUISAR")',
                '#btnPesquisar'
            ],
            'tabela_resultados': [
                'table.data-table tbody tr',
                'table.tabela-resultado tbody tr',
                '#tabelaResultado tbody tr',
                'table tbody tr'
            ],
            'link_detalhe': [
                'a[href*="detalhar"]',
                'a[href*="Detalhar"]',
                'a[href*="visualizar"]',
                'td a[href]'
            ],
            'link_pdf': [
                'a[href$=".pdf"]',
                'a[href*="edital"]',
                'a[href*="documento"]',
                'a.btn-download',
                'a[title*="Edital"]',
                'a[title*="Download"]'
            ]
        }
    
    async def buscar_licitacoes(
        self, 
        termo_busca: str = None, 
        apenas_futuras: bool = False, 
        limit: int = 20
    ) -> List[Dict]:
        """
        Busca licitações no Portal de Compras do Rio de Janeiro - MÉTODO ASSÍNCRONO COM PLAYWRIGHT
        
        Args:
            termo_busca: Termo para filtrar (ex: 'insulina', 'medicamento')
            apenas_futuras: Se True, retorna apenas licitações futuras
            limit: Número máximo de resultados
            
        Returns:
            Lista de dicionários com dados das licitações
        """
        resultados = []
        
        try:
            logger.info(f"🔍 [RJ] Iniciando busca: '{termo_busca or 'geral'}'")
            
            async with async_playwright() as p:
                # Iniciar browser com configurações robustas (igual BEC/SP e MG)
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
                    # ETAPA 1: Acessar página de busca
                    logger.info("  🌐 Acessando portal RJ (SIGA)...")
                    await page.goto(self.search_url, wait_until='domcontentloaded', timeout=30000)
                    await asyncio.sleep(3)  # Aguardar JavaScript carregar
                    
                    # ETAPA 2: Preencher formulário de busca
                    if termo_busca:
                        logger.info(f"  ✍️ Preenchendo campo 'Objeto': {termo_busca}")
                        campo_preenchido = await self._preencher_campo_busca(page, termo_busca)
                        
                        if not campo_preenchido:
                            logger.warning("  ⚠️ Não foi possível preencher campo de busca")
                    
                    # ETAPA 3: Clicar em PESQUISAR
                    logger.info("  🔎 Executando pesquisa...")
                    botao_clicado = await self._clicar_pesquisar(page)
                    
                    if botao_clicado:
                        # Aguardar carregamento dos resultados
                        await asyncio.sleep(5)
                        
                        # Aguardar tabela de resultados aparecer
                        try:
                            await page.wait_for_selector('table', timeout=15000)
                        except PlaywrightTimeout:
                            logger.info("  ℹ️ Tabela não carregou - tentando continuar...")
                    
                    # ETAPA 4: Extrair lista de licitações
                    logger.info("  📋 Extraindo lista de licitações...")
                    links_licitacoes = await self._extrair_links_licitacoes(page)
                    
                    logger.info(f"  ✅ Encontrados {len(links_licitacoes)} links de licitações")
                    
                    # ETAPA 5: Processar cada licitação (NAVEGAÇÃO DUPLA)
                    for idx, link_info in enumerate(links_licitacoes[:limit], 1):
                        try:
                            logger.info(f"    📄 [{idx}/{min(len(links_licitacoes), limit)}] Processando: {link_info.get('titulo', 'N/A')[:50]}...")
                            
                            # Navegar para página de detalhes
                            licitacao = await self._extrair_detalhes_licitacao(
                                page,
                                link_info['url'],
                                link_info.get('titulo', ''),
                                link_info.get('dados_linha', {})
                            )
                            
                            if licitacao:
                                # Filtrar por data se solicitado
                                if apenas_futuras:
                                    data_final = licitacao.get('data_final')
                                    if data_final and isinstance(data_final, datetime):
                                        if data_final < datetime.now():
                                            logger.debug("    ⏭️ Pulando licitação encerrada")
                                            continue
                                
                                resultados.append(licitacao)
                                logger.info("    ✅ Licitação processada com sucesso")
                            
                            # Rate limiting para não sobrecarregar o servidor
                            await asyncio.sleep(2)
                            
                        except Exception as e:
                            logger.error(f"    ❌ Erro ao processar licitação {idx}: {str(e)}")
                            continue
                    
                    logger.info(f"🎯 [RJ] Total processado: {len(resultados)} licitações válidas")
                    
                finally:
                    await browser.close()
            
            return resultados
            
        except Exception as e:
            logger.error(f"❌ [RJ] Erro geral na busca: {str(e)}")
            import traceback
            logger.debug(traceback.format_exc())
            return []
    
    async def _preencher_campo_busca(self, page, termo: str) -> bool:
        """
        Preenche o campo de busca 'Objeto' com o termo
        
        Args:
            page: Playwright page object
            termo: Termo de busca
            
        Returns:
            True se preencheu com sucesso
        """
        for selector in self.selectors['campo_objeto']:
            try:
                await page.fill(selector, termo, timeout=3000)
                logger.debug(f"    ✅ Campo preenchido com seletor: {selector}")
                return True
            except Exception:
                continue
        return False
    
    async def _clicar_pesquisar(self, page) -> bool:
        """
        Clica no botão de pesquisar
        
        Args:
            page: Playwright page object
            
        Returns:
            True se clicou com sucesso
        """
        # Método 1: Tentar clicar no link PESQUISAR via JavaScript
        try:
            # O portal RJ usa links <a> com onclick para pesquisa
            result = await page.evaluate('''
                () => {
                    const links = document.querySelectorAll('a');
                    for (let link of links) {
                        if (link.textContent && link.textContent.trim().toUpperCase().includes('PESQUISAR')) {
                            link.click();
                            return true;
                        }
                    }
                    // Tentar submeter o formulário
                    const form = document.querySelector('form');
                    if (form) {
                        form.submit();
                        return true;
                    }
                    return false;
                }
            ''')
            if result:
                await page.wait_for_load_state('networkidle', timeout=15000)
                logger.debug("    ✅ Pesquisa via JavaScript")
                return True
        except Exception as e:
            logger.debug(f"    ⚠️ Erro JS: {str(e)}")
        
        # Método 2: Tentar seletores CSS
        for selector in self.selectors['botao_pesquisar']:
            try:
                await page.click(selector, timeout=3000)
                await page.wait_for_load_state('networkidle', timeout=15000)
                logger.debug(f"    ✅ Botão clicado com seletor: {selector}")
                return True
            except Exception:
                continue
        
        # Método 3: Fallback via Enter
        try:
            await page.keyboard.press('Enter')
            await page.wait_for_load_state('networkidle', timeout=15000)
            logger.debug("    ✅ Pesquisa via Enter")
            return True
        except Exception:
            pass
        
        return False
    
    async def _extrair_links_licitacoes(self, page) -> List[Dict]:
        """
        Extrai links das licitações da tabela de resultados
        
        Args:
            page: Playwright page object
            
        Returns:
            Lista de dicts com url, titulo e dados_linha
        """
        links = []
        
        try:
            # Obter HTML da página
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            # Buscar tabelas de dados - a tabela de resultados geralmente é a segunda
            tabelas = soup.find_all('table')
            
            for tabela in tabelas:
                linhas = tabela.find_all('tr')
                if len(linhas) < 2:
                    continue
                
                # Verificar se é a tabela correta (tem header com 'Identificador' ou 'Objeto')
                header_row = linhas[0]
                header_text = header_row.get_text().lower()
                if 'identificador' not in header_text and 'objeto' not in header_text:
                    continue
                
                # Extrair headers para mapear colunas
                headers = []
                for th in header_row.find_all(['th', 'td']):
                    h = th.get_text(strip=True).lower()
                    # Limpar caracteres especiais
                    h = ''.join(c for c in h if c.isalnum() or c == ' ')
                    headers.append(h)
                
                logger.debug(f"    📊 Headers encontrados: {headers}")
                
                # Processar linhas de dados
                for linha in linhas[1:]:
                    colunas = linha.find_all('td')
                    if not colunas:
                        continue
                    
                    # Extrair dados de cada coluna
                    dados_linha = {}
                    for idx, col in enumerate(colunas):
                        texto = col.get_text(strip=True)
                        if idx < len(headers):
                            dados_linha[headers[idx]] = texto
                        dados_linha[f'col_{idx}'] = texto
                    
                    # Buscar link na linha
                    link_elem = linha.find('a', href=True)
                    if link_elem:
                        href = link_elem.get('href', '')
                        
                        if href and href != '#' and 'javascript:' not in href.lower():
                            # Construir URL completa
                            if href.startswith('/'):
                                url_completa = f'{self.base_url}{href}'
                            elif not href.startswith('http'):
                                url_completa = f'{self.base_url}/{href}'
                            else:
                                url_completa = href
                            
                            # Extrair título - usar Objeto ou Identificador
                            titulo = dados_linha.get('objeto', '') or dados_linha.get('col_3', '')
                            if not titulo:
                                titulo = link_elem.get_text(strip=True) or dados_linha.get('identificador', 'Sem título')
                            
                            # Extrair dados já disponíveis na linha
                            links.append({
                                'url': url_completa,
                                'titulo': titulo[:200],
                                'dados_linha': {
                                    'identificador': dados_linha.get('identificador', dados_linha.get('col_0', '')),
                                    'unidade': dados_linha.get('unidade', dados_linha.get('col_1', '')),
                                    'processo': dados_linha.get('processo', dados_linha.get('col_2', '')),
                                    'objeto': dados_linha.get('objeto', dados_linha.get('col_3', '')),
                                    'modalidade': dados_linha.get('modalidade', dados_linha.get('col_4', '')),
                                    'data_publicacao': dados_linha.get('data de publicao', dados_linha.get('col_5', '')),
                                    'status': dados_linha.get('status', dados_linha.get('col_6', ''))
                                }
                            })
                
                # Se encontrou links nesta tabela, parar
                if links:
                    logger.info(f"    ✅ {len(links)} licitações encontradas na tabela")
                    break
            
            return links
            
        except Exception as e:
            logger.error(f"    ❌ Erro ao extrair links: {str(e)}")
            return []
    
    async def _extrair_detalhes_licitacao(
        self,
        page,
        url: str,
        titulo: str,
        dados_linha: Dict = None
    ) -> Optional[Dict]:
        """
        Navega para página de detalhes e extrai metadados completos - COM PLAYWRIGHT
        Implementa NAVEGAÇÃO DUPLA para obter link direto do PDF
        
        Args:
            page: Playwright page object
            url: URL da página de detalhes
            titulo: Título/texto do link original
            dados_linha: Dados extraídos da linha da tabela (já contém órgão, modalidade, etc.)
            
        Returns:
            Dict com dados completos ou None
        """
        dados_linha = dados_linha or {}
        
        try:
            logger.debug(f"      🔍 Acessando detalhes: {url[:80]}...")
            
            # Navegar para página de detalhes
            await page.goto(url, wait_until='domcontentloaded', timeout=20000)
            await asyncio.sleep(2)  # Aguardar JavaScript
            
            # Extrair HTML após JavaScript
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            # Extrair metadados adicionais da página de detalhes
            dados_detalhe = self._extrair_metadados(soup, titulo, dados_linha)
            
            # Mesclar dados da linha com dados do detalhe (linha tem prioridade para campos já preenchidos)
            orgao = dados_linha.get('unidade', '') or dados_detalhe.get('orgao', 'Órgão RJ')
            modalidade = dados_linha.get('modalidade', '') or dados_detalhe.get('modalidade', 'Pregão Eletrônico')
            status = dados_linha.get('status', '') or dados_detalhe.get('status', 'Em Licitação')
            numero_processo = dados_linha.get('processo', '') or dados_linha.get('identificador', '') or dados_detalhe.get('numero_processo', 'N/A')
            objeto = dados_linha.get('objeto', '') or dados_detalhe.get('objeto', titulo)
            
            # Parse de data de publicação
            data_pub_str = dados_linha.get('data_publicacao', '')
            data_publicacao = self._parse_date(data_pub_str) if data_pub_str else dados_detalhe.get('data_publicacao')
            
            # CRÍTICO: Extrair link direto do PDF (NAVEGAÇÃO DUPLA)
            link_documento = await self._extrair_link_pdf(page, soup)
            
            # Montar resultado completo
            return {
                'id': str(uuid.uuid4()),
                
                # CAMPOS MANDATÓRIOS
                'titulo_licitacao': objeto[:200] if objeto else titulo[:200],
                'medicamento': self._extrair_medicamento_texto(f"{objeto} {titulo}"),
                'estado': self.estado,
                'estado_uf': self.estado,
                'orgao_licitante': orgao[:200] if orgao else 'Órgão RJ',
                'status': status if status else 'Em Licitação',
                'status_aquisicao': status if status else 'Em Licitação',
                'modalidade': modalidade if modalidade else 'Pregão Eletrônico',
                'numero_processo': numero_processo if numero_processo else 'N/A',
                
                # Datas
                'data_referencia': datetime.now(),
                'data_abertura': dados_detalhe.get('data_abertura'),
                'data_inicial': dados_detalhe.get('data_abertura'),
                'data_final': dados_detalhe.get('data_final'),
                'data_limite': dados_detalhe.get('data_final'),
                'data_publicacao': data_publicacao,
                
                # Links (NAVEGAÇÃO DUPLA)
                'link_origem': url,
                'link_documento': link_documento,
                
                # Metadados expandidos
                'fonte_nome': self.fonte,
                'fonte_id': f'rj-siga-{dados_linha.get("identificador", str(uuid.uuid4())[:8])}',
                'numero_pregao': numero_processo,
                'uasg': None,
                'esfera': 'Estadual',
                'objeto': objeto[:500] if objeto else titulo[:500],
                
                # Itens
                'itens': [],
                
                # Metadados extras
                'tags': self._extrair_tags(f"{titulo} {objeto}", content),
                'is_mock': False,
                'fonte': 'RJ'
            }
            
        except PlaywrightTimeout:
            logger.warning("      ⏱️ Timeout ao acessar detalhes")
            return None
        except Exception as e:
            logger.error(f"      ❌ Erro ao extrair detalhes: {str(e)}")
            return None
    
    def _extrair_metadados(self, soup: BeautifulSoup, titulo: str, dados_linha: Dict) -> Dict:
        """
        Extrai metadados da página de detalhes
        
        Args:
            soup: BeautifulSoup da página
            titulo: Título original
            dados_linha: Dados da linha da tabela
            
        Returns:
            Dict com metadados extraídos
        """
        dados = {
            'titulo': titulo,
            'medicamento': 'Não especificado',
            'orgao': 'Órgão RJ',
            'status': 'Em Licitação',
            'modalidade': 'Pregão Eletrônico',
            'numero_processo': 'N/A',
            'data_abertura': None,
            'data_final': None,
            'data_publicacao': None,
            'objeto': titulo,
            'identificador': None
        }
        
        try:
            # Extrair texto completo da página para análise
            page_text = soup.get_text()
            
            # Extrair identificador/número
            match = re.search(r'(?:identificador|id|número|nº)[\s:]*(\d+[/-]?\d*)', page_text, re.IGNORECASE)
            if match:
                dados['identificador'] = match.group(1)
                dados['numero_processo'] = match.group(1)
            
            # Extrair processo
            match = re.search(r'processo[\s:]*([A-Z0-9/-]+)', page_text, re.IGNORECASE)
            if match:
                dados['numero_processo'] = match.group(1)
            
            # Extrair órgão/unidade
            patterns_orgao = [
                r'(?:órgão|unidade|entidade)[\s:]*([^<\n]+?)(?:\n|<|$)',
                r'(?:secretaria|fundação|instituto)[^<\n]{5,80}'
            ]
            for pattern in patterns_orgao:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    dados['orgao'] = match.group(1).strip()[:200] if match.groups() else match.group(0).strip()[:200]
                    break
            
            # Extrair modalidade
            modalidades = [
                'Pregão Eletrônico',
                'Pregão Presencial',
                'Concorrência',
                'Concorrência Eletrônica',
                'Tomada de Preços',
                'Convite',
                'Processo Eletrônico de Dispensa',
                'Dispensa de Licitação',
                'Inexigibilidade'
            ]
            for mod in modalidades:
                if mod.lower() in page_text.lower():
                    dados['modalidade'] = mod
                    break
            
            # Extrair status
            status_map = {
                'encerrad': 'Encerrada',
                'homologad': 'Homologada',
                'em andamento': 'Em Andamento',
                'aberta': 'Ativa',
                'ativa': 'Ativa',
                'suspensa': 'Suspensa',
                'cancelada': 'Cancelada',
                'disputa': 'Em Disputa',
                'envio de proposta': 'Recebendo Propostas'
            }
            page_text_lower = page_text.lower()
            for key, value in status_map.items():
                if key in page_text_lower:
                    dados['status'] = value
                    break
            
            # Extrair datas (formatos brasileiros)
            date_patterns = [
                (r'(?:abertura|início|data inicial)[\s:]*(\d{2}[/-]\d{2}[/-]\d{4})', 'data_abertura'),
                (r'(?:encerramento|término|limite|final)[\s:]*(\d{2}[/-]\d{2}[/-]\d{4})', 'data_final'),
                (r'(?:publicação|publicado)[\s:]*(\d{2}[/-]\d{2}[/-]\d{4})', 'data_publicacao')
            ]
            
            for pattern, campo in date_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    data_str = match.group(1)
                    dados[campo] = self._parse_date(data_str)
            
            # Extrair objeto/descrição
            match = re.search(r'(?:objeto|descrição)[\s:]*([^<\n]{20,500})', page_text, re.IGNORECASE)
            if match:
                dados['objeto'] = match.group(1).strip()
                dados['titulo'] = dados['objeto'][:200]
            
            # Extrair medicamento do texto
            dados['medicamento'] = self._extrair_medicamento_texto(page_text)
            
            return dados
            
        except Exception as e:
            logger.debug(f"      ⚠️ Erro ao extrair metadados: {str(e)}")
            return dados
    
    async def _extrair_link_pdf(self, page, soup: BeautifulSoup) -> Optional[str]:
        """
        Extrai link direto para PDF do edital - NAVEGAÇÃO DUPLA
        
        Args:
            page: Playwright page object
            soup: BeautifulSoup da página de detalhes
            
        Returns:
            URL do PDF ou None
        """
        try:
            # Método 1: Buscar links diretos para PDF via Playwright
            pdf_links = await page.query_selector_all('a[href$=".pdf"]')
            
            for link in pdf_links:
                try:
                    texto = (await link.inner_text()).lower()
                    href = await link.get_attribute('href')
                    
                    # Priorizar edital
                    if any(kw in texto for kw in ['edital', 'anexo', 'documento', 'download']):
                        return self._construir_url_completa(href)
                    
                    # Aceitar qualquer PDF se for relevante
                    if href and '.pdf' in href.lower():
                        return self._construir_url_completa(href)
                        
                except Exception:
                    continue
            
            # Método 2: Buscar via BeautifulSoup
            for selector in self.selectors['link_pdf']:
                links = soup.select(selector)
                for link in links:
                    href = link.get('href', '')
                    texto = link.get_text(strip=True).lower()
                    
                    if 'edital' in texto or '.pdf' in href.lower():
                        return self._construir_url_completa(href)
            
            # Método 3: Buscar qualquer link de download
            download_links = soup.find_all('a', href=True)
            for link in download_links:
                href = link.get('href', '')
                texto = link.get_text(strip=True).lower()
                
                if any(kw in texto for kw in ['download', 'baixar', 'edital', 'documento']):
                    if '.pdf' in href.lower() or 'documento' in href.lower():
                        return self._construir_url_completa(href)
            
            return None
            
        except Exception as e:
            logger.debug(f"      ⚠️ Erro ao extrair PDF: {str(e)}")
            return None
    
    def _construir_url_completa(self, href: str) -> str:
        """Constrói URL completa a partir de href relativa ou absoluta"""
        if not href:
            return None
        
        if href.startswith('http'):
            return href
        elif href.startswith('/'):
            return f'{self.base_url}{href}'
        else:
            return f'{self.base_url}/{href}'
    
    def _extrair_medicamento_texto(self, texto: str) -> str:
        """
        Tenta extrair nome do medicamento do texto
        
        Args:
            texto: Texto da página
            
        Returns:
            Nome do medicamento ou 'Não especificado'
        """
        if not texto:
            return 'Não especificado'
        
        texto_lower = texto.lower()
        
        # Lista de medicamentos comuns
        medicamentos = [
            'insulina', 'canabidiol', 'adalimumabe', 'pembrolizumabe',
            'metformina', 'omeprazol', 'paracetamol', 'dipirona',
            'amoxicilina', 'azitromicina', 'losartana', 'atenolol',
            'ibuprofeno', 'cetoprofeno', 'diclofenaco', 'tramadol',
            'morfina', 'fentanil', 'clonazepam', 'sertralina'
        ]
        
        for med in medicamentos:
            if med in texto_lower:
                return med.capitalize()
        
        # Se não encontrou, verificar se é licitação de saúde
        if any(kw in texto_lower for kw in ['medicamento', 'fármaco', 'remédio', 'hospitalar', 'saúde']):
            return 'Medicamento (ver objeto)'
        
        return 'Não especificado'
    
    def _extrair_tags(self, titulo: str, html: str) -> List[str]:
        """
        Extrai tags relevantes do conteúdo
        
        Args:
            titulo: Título da licitação
            html: HTML da página
            
        Returns:
            Lista de tags
        """
        texto = f"{titulo} {html[:3000]}".lower()
        tags = []
        
        if any(kw in texto for kw in ['alto custo', 'especializado']):
            tags.append('alto_custo')
        
        if any(kw in texto for kw in ['importado', 'importação']):
            tags.append('importado')
        
        if any(kw in texto for kw in ['judicial', 'liminar']):
            tags.append('judicial')
        
        if any(kw in texto for kw in ['urgente', 'urgência', 'emergência']):
            tags.append('urgente')
        
        if any(kw in texto for kw in ['hospitalar', 'hospital']):
            tags.append('hospitalar')
        
        if any(kw in texto for kw in ['ses', 'secretaria de saúde', 'fundo de saúde']):
            tags.append('saude')
        
        return tags
    
    def _parse_date(self, texto: str) -> Optional[datetime]:
        """
        Parse de data em formato brasileiro
        
        Args:
            texto: String com data (ex: "15/12/2024", "15-12-2024")
            
        Returns:
            datetime ou None
        """
        if not texto:
            return None
        
        # Limpar texto
        texto_limpo = re.sub(r'[^\d/\-:\s]', '', texto).strip()
        
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
            except ValueError:
                continue
        
        return None
    
    # Método de compatibilidade para integração com scraper_service
    async def scrape(self, medicamento: str = None) -> List[Dict]:
        """
        Método de compatibilidade com a interface padrão de scrapers
        
        Args:
            medicamento: Termo de busca
            
        Returns:
            Lista de licitações
        """
        return await self.buscar_licitacoes(termo_busca=medicamento)
