"""
Cliente para scraping do portal BEC/e-NEGÓCIOS SP usando Playwright

Portal: https://www.bec.sp.gov.br
Estratégia: Navegação dupla com Playwright para capturar dados de licitações

ATUALIZADO 2024/2025:
- Seletores ajustados para integração com Compras.gov
- Estratégias múltiplas para resiliência
- Fallbacks para mudanças de DOM
"""

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
import asyncio
import os
import tempfile
import logging
import uuid
import re
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class BECSpClient:
    """
    Cliente robusto para scraping do BEC/e-NEGÓCIOS SP - ATUALIZADO 2024/2025
    
    Implementa:
    - Navegação assíncrona com Playwright (browser real)
    - Busca em Pregão Eletrônico e Dispensas
    - Navegação dupla: Lista → Detalhes → PDF
    - Extração completa de metadados
    - Múltiplas estratégias de seletores para resiliência
    """
    
    def __init__(self):
        self.base_url = 'https://www.bec.sp.gov.br'
        self.pregao_url = f'{self.base_url}/bec_pregao_UI/OC/pesquisa_publica.aspx'
        self.dispensa_url = f'{self.base_url}/BEC_Dispensa_UI/ui/BEC_DL_Pesquisa.aspx'
        
        # Carregar API Key para OCR (Gemini)
        self.api_key = os.environ.get('EMERGENT_LLM_KEY')
        
        # Seletores comuns atualizados (conforme exploração 2024/2025)
        self.selectors = {
            'campo_busca': [
                '#ctl00_conteudo_Wuc_OC1_Wuc_filtroPesquisaOc1_cItemDescricao',
                'input[name*="itemDescricao"]',
                'input[name*="objeto"]'
            ],
            'captcha_img': '#ctl00_conteudo_Wuc_OC1_imgNoRobot',
            'captcha_input': '#ctl00_conteudo_Wuc_OC1_noRobot',
            'botao_buscar': [
                '#ctl00_conteudo_Wuc_OC1_c_btnPesquisa',
                'input[type="submit"][value*="Pesquisar"]'
            ],
            'links_licitacao': [
                '#ctl00_conteudo_Wuc_OC1_grdOC a[id*="hnkOC"]',
                'a[href*="BecPR"]'
            ],
            'pesquisa_avancada_btn': 'a:has-text("Pesquisa Avançada")'
        }
    
    async def buscar_licitacoes(
        self, 
        termo_busca: str = None, 
        apenas_futuras: bool = False, 
        limit: int = 20
    ) -> List[Dict]:
        """
        Busca licitações no BEC/SP - MÉTODO ASSÍNCRONO ATUALIZADO
        
        Args:
            termo_busca: Termo para buscar (ex: "insulina", "canabidiol")
            apenas_futuras: Se True, retorna apenas licitações com data futura
            limit: Número máximo de resultados
            
        Returns:
            Lista de licitações com metadados completos
        """
        resultados = []
        
        try:
            logger.info(f"🔍 [BEC/SP] Iniciando busca: '{termo_busca or 'geral'}'")
            
            async with async_playwright() as p:
                # Iniciar browser com configurações robustas
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox']
                )
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    viewport={'width': 1920, 'height': 1080}
                )
                page = await context.new_page()
                
                try:
                    # ETAPA 1: Acessar página de busca
                    logger.info("  🌐 Acessando portal BEC/SP...")
                    await page.goto(self.pregao_url, wait_until='networkidle', timeout=30000)
                    
                    # ETAPA 1.1: Expandir Pesquisa Avançada se disponível (para ter campo de descrição mais preciso)
                    try:
                        logger.debug("    🔍 Tentando ativar Pesquisa Avançada...")
                        await page.click(self.selectors['pesquisa_avancada_btn'], timeout=3000)
                        await asyncio.sleep(1)
                    except Exception:
                        logger.debug("    ⏭️ Pesquisa Avançada já ativa ou não disponível")
                        
                    # ETAPA 2: Preencher formulário de busca
                    if termo_busca:
                        logger.info(f"  ✍️ Preenchendo busca: {termo_busca}")
                        
                        # Tentar preencher o objeto
                        campo_preenchido = False
                        for selector in self.selectors['campo_busca']:
                            try:
                                await page.wait_for_selector(selector, timeout=5000)
                                await page.fill(selector, termo_busca)
                                campo_preenchido = True
                                logger.debug(f"    ✅ Campo preenchido: {selector}")
                                break
                            except Exception:
                                continue
                        
                        if not campo_preenchido:
                            raise Exception("Não foi possível localizar o campo de busca")

                        # ETAPA 2.1: Resolver CAPTCHA
                        logger.info("  🤖 Resolvendo CAPTCHA do portal...")
                        captcha_text = await self._solve_captcha_ai(page)
                        
                        if captcha_text:
                            logger.info(f"    ✅ Texto extraído: {captcha_text}")
                            await page.fill(self.selectors['captcha_input'], captcha_text)
                        
                        # ETAPA 2.2: Clicar em Pesquisar
                        botao_clicado = False
                        for selector in self.selectors['botao_buscar']:
                            try:
                                await page.click(selector, timeout=3000)
                                # Aguardar navegação ou mensagem de erro
                                await asyncio.sleep(2)
                                botao_clicado = True
                                logger.debug(f"    ✅ Botão clicado: {selector}")
                                break
                            except Exception:
                                continue
                        
                        if not botao_clicado:
                             logger.warning("  ⚠️ Não foi possível clicar em buscar")
                    
                    await asyncio.sleep(2)
                    
                    # ETAPA 3: Extrair lista de licitações com múltiplas estratégias
                    logger.info("  📋 Extraindo lista de licitações...")
                    
                    try:
                        links_licitacoes = []
                        
                        # Tentar múltiplas estratégias para encontrar links
                        for selector in self.selectors['links_licitacao']:
                            try:
                                links = await page.query_selector_all(selector)
                                if links:
                                    links_licitacoes = links
                                    logger.debug(f"    ✅ Links encontrados com seletor: {selector}")
                                    break
                            except Exception:
                                continue
                        
                        if not links_licitacoes:
                            logger.warning("  ⚠️ Nenhum link de licitação encontrado com os seletores configurados")
                            # Tentar capturar todos os links como fallback
                            links_licitacoes = await page.query_selector_all('a[href]')
                            # Filtrar apenas links relevantes
                            links_filtrados = []
                            for link in links_licitacoes:
                                href = await link.get_attribute('href')
                                if href and any(x in href.lower() for x in ['oc', 'pr', 'detalhe', 'pregao']):
                                    links_filtrados.append(link)
                            links_licitacoes = links_filtrados
                        
                        logger.info(f"  ✅ Encontrados {len(links_licitacoes)} links de licitações")
                        
                        # IMPORTANTE: Extrair todos os dados dos links ANTES de navegar
                        # (o contexto é destruído durante navegação)
                        links_data = []
                        for link in links_licitacoes[:limit]:
                            try:
                                href = await link.get_attribute('href')
                                texto = await link.inner_text()
                                
                                if href and href != '#':
                                    # Garantir URL completa
                                    if href.startswith('/'):
                                        url_completa = f'{self.base_url}{href}'
                                    elif not href.startswith('http'):
                                        url_completa = f'{self.base_url}/{href}'
                                    else:
                                        url_completa = href
                                    
                                    links_data.append({
                                        'url': url_completa,
                                        'texto': texto
                                    })
                            except Exception as e:
                                logger.debug(f"    ⚠️ Erro ao extrair dados do link: {str(e)}")
                                continue
                        
                        # Processar cada link
                        for idx, link_info in enumerate(links_data, 1):
                            try:
                                logger.info(f"    📄 [{idx}/{len(links_data)}] Processando licitação...")
                                
                                # Navegar para página de detalhes
                                licitacao = await self._extrair_detalhes_licitacao(
                                    page, 
                                    link_info['url'], 
                                    link_info['texto']
                                )
                                
                                if licitacao:
                                    # Filtrar por data futura se solicitado
                                    if apenas_futuras:
                                        data_final = licitacao.get('data_final')
                                        if data_final and isinstance(data_final, datetime):
                                            if data_final < datetime.now():
                                                logger.debug("    ⏭️ Pulando licitação encerrada")
                                                continue
                                    
                                    resultados.append(licitacao)
                                    logger.info("    ✅ Licitação processada com sucesso")
                                
                                # Rate limiting
                                if idx < len(links_licitacoes):
                                    await asyncio.sleep(1.5)
                                
                            except Exception as e:
                                logger.error(f"    ❌ Erro ao processar licitação {idx}: {str(e)}")
                                continue
                    
                    except Exception as e:
                        logger.error(f"  ❌ Erro ao extrair lista: {str(e)}")
                        import traceback
                        logger.debug(traceback.format_exc())
                
                finally:
                    await browser.close()
            
            logger.info(f"🎯 [BEC/SP] Total processado: {len(resultados)} licitações válidas")
            
        except Exception as e:
            logger.error(f"❌ [BEC/SP] Erro geral na busca: {str(e)}")
            import traceback
            traceback.print_exc()
        
        return resultados
    
    async def _solve_captcha_ai(self, page) -> Optional[str]:
        """Resolve o CAPTCHA alfanumérico usando Gemini Vision"""
        try:
            # 1. Localizar elemento do captcha
            if not self.api_key:
                logger.warning("  ⚠️ API Key do Gemini não configurada, pulando captcha")
                return None
                
            captcha_elem = await page.query_selector(self.selectors['captcha_img'])
            if not captcha_elem:
                logger.warning("  ⚠️ Elemento de CAPTCHA não encontrado na página")
                return None
                
            # 2. Capturar imagem do captcha em memória
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                img_path = tmp.name
                
            try:
                await captcha_elem.screenshot(path=img_path)
                
                # 3. Invocar Gemini via emergentintegrations
                from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContentWithMimeType
                
                chat = LlmChat(
                    api_key=self.api_key,
                    session_id=f"bec-captcha-{uuid.uuid4()}",
                    system_message="Você é um assistente especializado em OCR. Extraia apenas os caracteres alfanuméricos da imagem fornecida."
                ).with_model("gemini", "gemini-2.5-flash") # Usando o modelo padrão do projeto
                
                img_file = FileContentWithMimeType(
                    file_path=img_path,
                    mime_type="image/png"
                )
                
                response = await chat.send_message(UserMessage(
                    text="Extraia o código alfanumérico desta imagem de CAPTCHA. Responda apenas o código, sem espaços ou texto adicional.",
                    file_contents=[img_file]
                ))
                
                # Limpar resposta (remover espaços e quebras de linha)
                captcha_text = response.strip().upper().replace(" ", "")
                return captcha_text
                
            finally:
                if os.path.exists(img_path):
                    os.remove(img_path)
                    
        except Exception as e:
            logger.error(f"  ❌ Erro ao resolver CAPTCHA via AI: {str(e)}")
            return None

    async def _extrair_detalhes_licitacao(self, page, url: str, titulo: str) -> Optional[Dict]:
        """
        Navega para página de detalhes e extrai metadados completos - ASYNC
        
        Args:
            page: Playwright page object (async)
            url: URL da página de detalhes
            titulo: Título da licitação
            
        Returns:
            Dict com dados completos ou None
        """
        try:
            logger.debug(f"      🔍 Acessando detalhes: {url[:80]}...")
            
            # Navegar para página de detalhes
            await page.goto(url, wait_until='domcontentloaded', timeout=20000)
            await asyncio.sleep(2)
            
            # Extrair conteúdo da página
            page_content = await page.content()
            
            # Extrair dados usando regex e parsing do HTML
            objeto_extraido = self._extrair_objeto(page_content)
            if objeto_extraido == 'Ver detalhes da licitação' or not objeto_extraido:
                objeto_extraido = titulo  # Usar título como fallback
            
            dados = {
                'id': str(uuid.uuid4()),
                'medicamento': self._extrair_medicamento(titulo, page_content),
                'principio_ativo': None,
                'estado': 'SP',
                'estado_uf': 'SP',
                'status': self._determinar_status(page_content),
                'status_aquisicao': self._determinar_status(page_content),
                'orgao_licitante': self._extrair_orgao(page_content),
                'modalidade': 'Pregão Eletrônico',
                'numero_processo': self._extrair_numero_processo(page_content, url),
                
                # Título da licitação
                'titulo_licitacao': titulo if titulo else objeto_extraido[:200],
                
                # Datas
                'data_referencia': datetime.now(),
                'data_abertura': self._extrair_data_abertura(page_content),
                'data_inicial': None,
                'data_final': self._extrair_data_final(page_content),
                'data_publicacao': None,
                
                # Links
                'link_origem': url,
                'link_documento': await self._extrair_link_pdf(page),
                
                # Metadados expandidos
                'fonte_nome': 'BEC/e-NEGÓCIOS SP - Bolsa Eletrônica de Compras',
                'fonte_id': f'bec-sp-{self._extrair_id_licitacao(url)}',
                'numero_pregao': self._extrair_numero_processo(page_content, url),
                'uasg': None,
                'esfera': 'Estadual',
                'objeto': objeto_extraido,
                
                # Itens
                'itens': self._extrair_itens(page_content),
                
                # Metadados
                'tags': self._extrair_tags(titulo, page_content),
                'is_mock': False,
                'fonte': 'BEC/SP'
            }
            
            return dados
            
        except PlaywrightTimeout:
            logger.warning("      ⏱️ Timeout ao acessar detalhes")
            return None
        except Exception as e:
            logger.error(f"      ❌ Erro ao extrair detalhes: {str(e)}")
            return None
    
    async def _extrair_link_pdf(self, page) -> Optional[str]:
        """Extrai link direto para PDF do edital - ASYNC"""
        try:
            # Buscar links para PDF
            pdf_links = await page.query_selector_all('a[href$=".pdf"]')
            
            for link in pdf_links:
                texto = (await link.inner_text()).lower()
                href = await link.get_attribute('href')
                
                if any(palavra in texto for palavra in ['edital', 'anexo', 'documento']):
                    # Garantir URL completa
                    if href.startswith('/'):
                        return f'{self.base_url}{href}'
                    elif not href.startswith('http'):
                        return f'{self.base_url}/{href}'
                    return href
            
            return None
        except Exception:
            return None
    
    def _extrair_medicamento(self, titulo: str, html: str) -> str:
        """Extrai nome do medicamento do título ou HTML - VERSÃO MELHORADA"""
        texto = f"{titulo} {html[:5000]}"
        texto_lower = texto.lower()
        
        # Lista expandida de medicamentos comuns em licitações
        medicamentos = [
            # Alto custo / especiais
            'insulina', 'canabidiol', 'adalimumabe', 'pembrolizumabe', 'infliximabe',
            'rituximabe', 'trastuzumabe', 'bevacizumabe', 'etanercepte', 'tocilizumabe',
            # Comum
            'metformina', 'omeprazol', 'paracetamol', 'dipirona', 'amoxicilina',
            'azitromicina', 'losartana', 'atenolol', 'captopril', 'enalapril',
            'ibuprofeno', 'cetoprofeno', 'diclofenaco', 'nimesulida', 'meloxicam',
            # Analgésicos/controle especial
            'tramadol', 'morfina', 'fentanil', 'codeína', 'oxicodona',
            # Psiquiátricos
            'clonazepam', 'sertralina', 'fluoxetina', 'amitriptilina', 'risperidona',
            'quetiapina', 'haloperidol', 'carbamazepina', 'fenitoína',
            # Antibióticos
            'ciprofloxacino', 'levofloxacino', 'cefalexina', 'ceftriaxona',
            'meropenem', 'vancomicina', 'gentamicina', 'clindamicina',
            # Outros
            'prednisona', 'dexametasona', 'hidrocortisona', 'omeprazol',
            'ranitidina', 'levotiroxina', 'sinvastatina', 'atorvastatina'
        ]
        
        for med in medicamentos:
            if med in texto_lower:
                return med.capitalize()
        
        # Tentar extrair da descrição/objeto
        import re
        # Padrão: "aquisição de [MEDICAMENTO]" ou similar
        patterns = [
            r'(?:aquisição|compra|fornecimento)\s+(?:de\s+)?([a-záéíóúâêôãõç]+(?:\s+[a-záéíóúâêôãõç]+)?)',
            r'medicamento[:\s]+([a-záéíóúâêôãõç]+)',
            r'fármaco[:\s]+([a-záéíóúâêôãõç]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, texto_lower)
            if match:
                nome = match.group(1).strip()
                if len(nome) > 3 and nome not in ['de', 'para', 'com', 'em', 'por']:
                    return nome.capitalize()
        
        # Se encontrou palavras-chave de saúde, indicar
        if any(kw in texto_lower for kw in ['medicamento', 'fármaco', 'hospitalar', 'saúde', 'farmácia']):
            return 'Medicamento (ver objeto)'
        
        return 'Não especificado'
    
    def _determinar_status(self, html: str) -> str:
        """Determina status da licitação - VERSÃO MELHORADA"""
        html_lower = html.lower()
        
        status_map = {
            'encerrada': 'Encerrada',
            'finalizada': 'Encerrada',
            'homologada': 'Homologada',
            'adjudicada': 'Adjudicada',
            'ativa': 'Ativa',
            'aberta': 'Ativa',
            'em andamento': 'Em Andamento',
            'suspensa': 'Suspensa',
            'cancelada': 'Cancelada',
            'revogada': 'Revogada',
            'deserta': 'Deserta',
            'fracassada': 'Fracassada',
            'em disputa': 'Em Disputa',
            'aguardando': 'Aguardando'
        }
        
        for key, value in status_map.items():
            if key in html_lower:
                return value
        
        return 'Em Licitação'
    
    def _extrair_orgao(self, html: str) -> str:
        """Extrai órgão licitante - VERSÃO MELHORADA"""
        import re
        
        # Padrões para encontrar órgão
        patterns = [
            r'(?:órgão|unidade|entidade|uge)[\s:]+([^<\n,]{10,150})',
            r'(?:secretaria|prefeitura|fundação|instituto|hospital|autarquia)[^<\n,]{5,100}',
            r'(?:uasg|uge)[\s:]+(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                orgao = match.group(1) if match.groups() else match.group(0)
                orgao = orgao.strip()
                # Limpar caracteres especiais
                orgao = re.sub(r'[<>].*', '', orgao).strip()
                if len(orgao) > 5:
                    return orgao[:200]
        
        # Buscar em tags específicas
        from bs4 import BeautifulSoup
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Buscar em spans/divs com class/id contendo 'orgao', 'uge', 'unidade'
            for selector in ['[class*="orgao"]', '[id*="orgao"]', '[class*="uge"]', '[class*="unidade"]']:
                elem = soup.select_one(selector)
                if elem:
                    texto = elem.get_text(strip=True)
                    if len(texto) > 5:
                        return texto[:200]
            
            # Buscar em tabelas - comum ter "Órgão:" seguido do nome
            tds = soup.find_all('td')
            for i, td in enumerate(tds):
                texto = td.get_text(strip=True).lower()
                if 'órgão' in texto or 'unidade' in texto:
                    # Próximo td geralmente tem o valor
                    if i + 1 < len(tds):
                        valor = tds[i + 1].get_text(strip=True)
                        if len(valor) > 3:
                            return valor[:200]
        except Exception:
            pass
        
        return 'Órgão SP'
    
    def _extrair_numero_processo(self, html: str, url: str) -> str:
        """Extrai número do processo/pregão - VERSÃO MELHORADA"""
        import re
        
        # Padrões comuns de número de pregão/processo
        patterns = [
            r'(?:pregão|pe|processo|oc|oferta\s+de\s+compra)[\s\-nº:]*(\d+[/-]?\d*[/-]?\d*)',
            r'nº[\s:]*(\d+[/-]\d{4})',
            r'(\d{4,}[/-]\d{4})',  # Formato 12345/2024
            r'oc[\s\-]*(\d+)',     # OC seguido de número
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                numero = match.group(1).strip()
                if len(numero) >= 3:
                    return numero
        
        # Tentar extrair do URL
        url_patterns = [
            r'oc=(\d+)',
            r'id=(\d+)',
            r'pregao=(\d+)',
            r'/(\d{5,})',
        ]
        
        for pattern in url_patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                return f"BEC-{match.group(1)}"
        
        return 'N/A'
    
    def _extrair_data_abertura(self, html: str) -> Optional[datetime]:
        """Extrai data de abertura - VERSÃO MELHORADA"""
        return self._parse_data_do_html(html, ['abertura', 'início', 'inicio', 'proposta', 'sessão', 'sessao'])
    
    def _extrair_data_final(self, html: str) -> Optional[datetime]:
        """Extrai data final/encerramento - VERSÃO MELHORADA"""
        return self._parse_data_do_html(html, ['encerramento', 'término', 'termino', 'limite', 'final', 'até', 'ate'])
    
    def _parse_data_do_html(self, html: str, palavras_chave: List[str]) -> Optional[datetime]:
        """Tenta extrair data do HTML baseado em palavras-chave - VERSÃO MELHORADA"""
        import re
        
        for palavra in palavras_chave:
            # Padrões de data mais flexíveis
            patterns = [
                fr'{palavra}[:\s]+(\d{{2}}[/-]\d{{2}}[/-]\d{{4}})',
                fr'{palavra}[:\s]+(\d{{2}}[/-]\d{{2}}[/-]\d{{2}})',
                fr'(\d{{2}}[/-]\d{{2}}[/-]\d{{4}})[\s]+{palavra}',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    data_str = match.group(1)
                    try:
                        # Tentar vários formatos
                        for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y', '%d-%m-%y']:
                            try:
                                return datetime.strptime(data_str, fmt)
                            except ValueError:
                                continue
                    except Exception:
                        continue
        
        # Fallback: buscar qualquer data no formato brasileiro
        match = re.search(r'(\d{2}[/-]\d{2}[/-]\d{4})', html)
        if match:
            try:
                return datetime.strptime(match.group(1).replace('-', '/'), '%d/%m/%Y')
            except Exception:
                pass
        
        return None
    
    def _extrair_objeto(self, html: str) -> str:
        """Extrai objeto da licitação - VERSÃO MELHORADA"""
        import re
        
        # Padrões para encontrar objeto/descrição
        patterns = [
            r'(?:objeto|descrição|descricao)[:\s]+([^<]{30,500})',
            r'(?:aquisição|compra|fornecimento|contratação)\s+(?:de\s+)?([^<]{30,300})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                objeto = match.group(1).strip()
                # Limpar HTML e caracteres especiais
                objeto = re.sub(r'<[^>]+>', '', objeto)
                objeto = re.sub(r'\s+', ' ', objeto).strip()
                if len(objeto) > 20:
                    return objeto[:500]
        
        # Buscar em tags específicas
        from bs4 import BeautifulSoup
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Buscar em elementos com class/id contendo 'objeto', 'descricao'
            for selector in ['[class*="objeto"]', '[id*="objeto"]', '[class*="descr"]', '.resumo', '.item']:
                elem = soup.select_one(selector)
                if elem:
                    texto = elem.get_text(strip=True)
                    if len(texto) > 20:
                        return texto[:500]
            
            # Buscar em tabelas
            tds = soup.find_all('td')
            for i, td in enumerate(tds):
                texto = td.get_text(strip=True).lower()
                if 'objeto' in texto or 'descrição' in texto:
                    if i + 1 < len(tds):
                        valor = tds[i + 1].get_text(strip=True)
                        if len(valor) > 20:
                            return valor[:500]
        except Exception:
            pass
        
        return 'Ver detalhes da licitação'
    
    def _extrair_itens(self, html: str) -> List[Dict]:
        """Extrai itens da licitação (simplificado)"""
        # TODO: Implementar parsing detalhado de itens quando necessário
        return []
    
    def _extrair_tags(self, titulo: str, html: str) -> List[str]:
        """Extrai tags relevantes"""
        texto = f"{titulo} {html[:2000]}".lower()
        tags = []
        
        if any(k in texto for k in ['alto custo', 'especializado']):
            tags.append('alto_custo')
        
        if any(k in texto for k in ['importado', 'importação']):
            tags.append('importado')
        
        if any(k in texto for k in ['judicial', 'liminar']):
            tags.append('judicial')
        
        return tags
    
    def _extrair_id_licitacao(self, url: str) -> str:
        """Extrai ID da licitação da URL"""
        match = re.search(r'(\d+)', url)
        if match:
            return match.group(1)
        return 'unknown'
