"""
Importador de Licitações do Paraná via CSV do Portal da Transparência

FONTE: https://www.transparencia.pr.gov.br/pte/compras/licitacoes/pesquisar-param
MÉTODO: Download do banco de dados CSV (atualizado diariamente)

Vantagens:
- Sem CAPTCHA (bypass completo do GMS)
- Dados estruturados e completos
- Atualização diária pelo governo
- Todos os editais desde 2015

Estrutura do CSV (esperada):
- Modalidade
- Resumo do Edital (Número/Ano)
- Órgão Responsável
- Órgãos Participantes
- Objeto
- Data de Abertura
- Data de Apresentação
- Registro de Preço
- Situação
- Protocolo
- Edital (link)

Criado: Dezembro 2024/2025
"""

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from typing import List, Dict, Optional
from datetime import datetime
from io import StringIO, BytesIO
import logging
import asyncio
import zipfile
import uuid
import csv
import os
import re

logger = logging.getLogger(__name__)


class ParanaCsvImporter:
    """
    Importador de licitações do Paraná via CSV do Portal da Transparência
    
    Portal: https://www.transparencia.pr.gov.br
    Método: Download CSV com banco de dados completo
    Atualização: Diária (aproximadamente 05:00)
    """
    
    def __init__(self):
        self.base_url = 'https://www.transparencia.pr.gov.br'
        self.consulta_url = f'{self.base_url}/pte/compras/licitacoes/pesquisar-param'
        
        self.estado = 'PR'
        self.fonte = 'Portal da Transparência PR (CSV)'
        
        # User agent
        self.user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        
        # Diretório para armazenar downloads
        self.download_dir = '/tmp/pr_csv_downloads'
        
        # Mapeamento de situações
        self.status_map = {
            'publicado': 'Publicado',
            'homologado': 'Homologado',
            'homologado parcialmente': 'Homologado Parcialmente',
            'adjudicado': 'Adjudicado',
            'adjudicado parcialmente': 'Adjudicado Parcialmente',
            'cancelado': 'Cancelado',
            'revogado': 'Revogado',
            'deserto': 'Deserto',
            'fracassado': 'Fracassado',
            'fase certame': 'Em Licitação',
            'suspenso': 'Suspenso'
        }
        
        # Órgãos de saúde prioritários
        self.orgaos_saude = [
            'SESA', 'FUNSAUDE', 'FUNEAS', 'HPM', 'HUOP', 'HURCG', 
            'UEM', 'UEL', 'UEPG', 'Hospital', 'Saúde'
        ]
    
    async def buscar_licitacoes(
        self,
        termo_busca: str = None,
        ano: int = None,
        apenas_saude: bool = True,
        limit: int = 50
    ) -> List[Dict]:
        """
        Busca licitações do Paraná via CSV do Portal da Transparência
        
        Args:
            termo_busca: Termo para filtrar (ex: 'medicamento', 'insulina')
            ano: Ano específico (default: ano atual)
            apenas_saude: Se True, filtra apenas órgãos de saúde
            limit: Número máximo de resultados
            
        Returns:
            Lista de dicionários com dados das licitações
        """
        resultados = []
        
        if ano is None:
            ano = datetime.now().year
        
        try:
            logger.info(f"🔍 [PR] Iniciando importação CSV: '{termo_busca or 'geral'}' - Ano {ano}")
            
            # Garantir diretório de download existe
            os.makedirs(self.download_dir, exist_ok=True)
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
                )
                
                # Configurar contexto com diretório de download
                context = await browser.new_context(
                    user_agent=self.user_agent,
                    viewport={'width': 1920, 'height': 1080},
                    accept_downloads=True
                )
                page = await context.new_page()
                
                try:
                    # ETAPA 1: Acessar página de consulta
                    logger.info(f"  🌐 Acessando Portal da Transparência PR...")
                    await page.goto(self.consulta_url, wait_until='networkidle', timeout=60000)
                    await asyncio.sleep(3)
                    
                    # ETAPA 2: Selecionar ano
                    logger.info(f"  📅 Selecionando ano {ano}...")
                    await self._selecionar_ano(page, ano)
                    await asyncio.sleep(2)
                    
                    # ETAPA 3: Clicar no botão de download do banco de dados
                    logger.info(f"  📥 Iniciando download do CSV...")
                    csv_content = await self._baixar_csv(page)
                    
                    if not csv_content:
                        logger.warning("  ⚠️ CSV vazio ou falha no download")
                        return []
                    
                    logger.info(f"  ✅ CSV baixado com sucesso ({len(csv_content)} bytes)")
                    
                    # ETAPA 4: Processar CSV
                    logger.info(f"  📊 Processando CSV...")
                    licitacoes = self._processar_csv(
                        csv_content,
                        termo_busca=termo_busca,
                        apenas_saude=apenas_saude,
                        limit=limit
                    )
                    
                    logger.info(f"  ✅ Processadas {len(licitacoes)} licitações")
                    
                    # ETAPA 5: Converter para formato padrão
                    for lic in licitacoes:
                        resultado = self._converter_para_formato_padrao(lic)
                        if resultado:
                            resultados.append(resultado)
                    
                    logger.info(f"🎯 [PR] Total processado: {len(resultados)} licitações válidas")
                    
                finally:
                    await browser.close()
            
            return resultados
            
        except Exception as e:
            logger.error(f"❌ [PR] Erro geral na importação: {str(e)}")
            import traceback
            logger.debug(traceback.format_exc())
            return []
    
    async def _selecionar_ano(self, page, ano: int) -> bool:
        """Seleciona o ano no dropdown"""
        try:
            # Tentar via select
            select_selector = 'select[id*="ano"], select[name*="ano"]'
            select = await page.query_selector(select_selector)
            
            if select:
                await select.select_option(value=str(ano))
                return True
            
            # Tentar via dropdown PrimeFaces
            dropdown_selectors = [
                f'#formPesquisa\\:ano_label',
                '.ui-selectonemenu-label',
                '[id*="ano"]'
            ]
            
            for selector in dropdown_selectors:
                try:
                    dropdown = await page.query_selector(selector)
                    if dropdown:
                        await dropdown.click()
                        await asyncio.sleep(1)
                        
                        # Selecionar item do ano
                        item = await page.query_selector(f'li[data-label="{ano}"], li:text("{ano}")')
                        if item:
                            await item.click()
                            return True
                except Exception:
                    continue
            
            return False
            
        except Exception as e:
            logger.debug(f"  ⚠️ Erro ao selecionar ano: {str(e)}")
            return False
    
    async def _baixar_csv(self, page) -> Optional[str]:
        """
        Baixa o CSV clicando no botão de download
        O arquivo vem como ZIP, então precisamos extrair o CSV
        
        Returns:
            Conteúdo do CSV como string ou None
        """
        try:
            # Encontrar botão de download
            download_selectors = [
                '#formPesquisa\\:lnkDownloadBD',
                'button:has-text("DOWNLOAD DO BANCO DE DADOS")',
                '[id*="DownloadBD"]',
                '.ui-button-download:has-text("DOWNLOAD")'
            ]
            
            for selector in download_selectors:
                try:
                    btn = await page.query_selector(selector)
                    if btn:
                        # Iniciar download com expectativa
                        async with page.expect_download(timeout=120000) as download_info:
                            await btn.click()
                        
                        download = await download_info.value
                        
                        # Salvar arquivo temporariamente
                        download_path = os.path.join(self.download_dir, f"pr_licitacoes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip")
                        await download.save_as(download_path)
                        
                        # Verificar se é um ZIP e extrair CSV
                        content = self._extrair_csv_do_zip(download_path)
                        
                        # Limpar arquivo temporário
                        try:
                            os.remove(download_path)
                        except Exception:
                            pass
                        
                        return content
                        
                except PlaywrightTimeout:
                    logger.debug(f"    ⏱️ Timeout no download via {selector}")
                    continue
                except Exception as e:
                    logger.debug(f"    ⚠️ Erro com {selector}: {str(e)}")
                    continue
            
            # Fallback: tentar extrair dados da tabela HTML diretamente
            logger.info("  📋 Tentando extração via tabela HTML...")
            return await self._extrair_tabela_html(page)
            
        except Exception as e:
            logger.error(f"  ❌ Erro no download do CSV: {str(e)}")
            return None
    
    def _extrair_csv_do_zip(self, zip_path: str) -> Optional[str]:
        """
        Extrai o conteúdo CSV de um arquivo ZIP
        
        Args:
            zip_path: Caminho do arquivo ZIP
            
        Returns:
            Conteúdo do CSV como string ou None
        """
        try:
            with open(zip_path, 'rb') as f:
                file_content = f.read()
            
            # Verificar se é um ZIP
            if file_content[:2] == b'PK':
                logger.info("    📦 Arquivo é ZIP, extraindo CSV...")
                
                with zipfile.ZipFile(BytesIO(file_content), 'r') as zf:
                    # Listar arquivos no ZIP
                    file_list = zf.namelist()
                    logger.debug(f"    📋 Arquivos no ZIP: {file_list}")
                    
                    # Encontrar arquivo CSV
                    csv_file = None
                    for name in file_list:
                        if name.lower().endswith('.csv'):
                            csv_file = name
                            break
                    
                    if not csv_file and file_list:
                        # Usar o primeiro arquivo se não encontrar .csv
                        csv_file = file_list[0]
                    
                    if csv_file:
                        logger.info(f"    📄 Extraindo: {csv_file}")
                        csv_content = zf.read(csv_file)
                        
                        # Tentar decodificar com diferentes encodings
                        for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
                            try:
                                return csv_content.decode(encoding)
                            except UnicodeDecodeError:
                                continue
                        
                        # Fallback: ignorar erros
                        return csv_content.decode('utf-8', errors='ignore')
                    
                    logger.warning("    ⚠️ Nenhum arquivo CSV encontrado no ZIP")
                    return None
            else:
                # Não é ZIP, tentar ler como CSV diretamente
                logger.info("    📄 Arquivo não é ZIP, lendo como CSV...")
                for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
                    try:
                        return file_content.decode(encoding)
                    except UnicodeDecodeError:
                        continue
                
                return file_content.decode('utf-8', errors='ignore')
                
        except Exception as e:
            logger.error(f"    ❌ Erro ao extrair CSV do ZIP: {str(e)}")
            return None
    
    async def _extrair_tabela_html(self, page) -> Optional[str]:
        """
        Fallback: Extrai dados da tabela HTML e converte para CSV
        """
        try:
            # Executar pesquisa primeiro
            pesquisar_btn = await page.query_selector('#formPesquisa\\:btnPesquisar, button:has-text("Pesquisar")')
            if pesquisar_btn:
                await pesquisar_btn.click()
                await asyncio.sleep(5)
            
            # Extrair tabela
            content = await page.content()
            
            # Parse simples da tabela
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, 'html.parser')
            
            # Encontrar tabela de licitações
            table = soup.find('table', {'id': lambda x: x and 'licitacoes' in x.lower()}) or soup.find('table')
            
            if not table:
                return None
            
            # Converter para CSV
            rows = []
            headers = []
            
            # Extrair headers
            header_row = table.find('tr')
            if header_row:
                headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
                rows.append(headers)
            
            # Extrair dados
            for row in table.find_all('tr')[1:]:
                cells = [td.get_text(strip=True) for td in row.find_all('td')]
                if cells:
                    rows.append(cells)
            
            # Converter para CSV string
            if rows:
                output = StringIO()
                writer = csv.writer(output, delimiter=';')
                writer.writerows(rows)
                return output.getvalue()
            
            return None
            
        except Exception as e:
            logger.debug(f"  ⚠️ Erro na extração HTML: {str(e)}")
            return None
    
    def _processar_csv(
        self,
        csv_content: str,
        termo_busca: str = None,
        apenas_saude: bool = True,
        limit: int = 50
    ) -> List[Dict]:
        """
        Processa o conteúdo CSV e retorna lista de licitações
        
        Args:
            csv_content: Conteúdo do CSV como string
            termo_busca: Termo para filtrar
            apenas_saude: Filtrar apenas órgãos de saúde
            limit: Limite de resultados
            
        Returns:
            Lista de dicionários com dados das licitações
        """
        licitacoes = []
        
        try:
            # Detectar delimitador
            delimiter = ';' if ';' in csv_content[:1000] else ','
            
            # Parse CSV
            reader = csv.DictReader(StringIO(csv_content), delimiter=delimiter)
            
            for row in reader:
                try:
                    # Colunas reais do CSV do Portal Transparência PR:
                    # numprocesso, ano, modalidade, situacao, objeto, orgao, registrodepreco,
                    # vigenciaata, revogacaoata, criteriojulgamento, valor_estimado, 
                    # valor_ou_desconto_homologado, dataabertura, datahomologacao, 
                    # localdisputa, idlicitacoes, protocolo, tempoprazocontrato
                    
                    modalidade = row.get('modalidade', '')
                    numero_processo = row.get('numprocesso', '')
                    ano = row.get('ano', '')
                    orgao = row.get('orgao', '')
                    objeto = row.get('objeto', '')
                    data_abertura = row.get('dataabertura', '')
                    situacao = row.get('situacao', '')
                    protocolo = row.get('protocolo', '')
                    registro_preco = row.get('registrodepreco', '')
                    valor_estimado = row.get('valor_estimado', '')
                    
                    # Filtrar por termo de busca
                    if termo_busca:
                        termo_lower = termo_busca.lower()
                        texto_completo = f"{objeto} {orgao} {modalidade}".lower()
                        if termo_lower not in texto_completo:
                            continue
                    
                    # Filtrar por órgãos de saúde
                    if apenas_saude:
                        orgao_upper = orgao.upper()
                        is_saude = any(org in orgao_upper for org in self.orgaos_saude)
                        objeto_lower = objeto.lower()
                        is_medicamento = any(kw in objeto_lower for kw in ['medicamento', 'fármaco', 'hospitalar', 'saúde', 'médico', 'farmacêutico', 'insumo'])
                        
                        if not (is_saude or is_medicamento):
                            continue
                    
                    # Formatar número do edital
                    edital = f"{numero_processo}/{ano}" if numero_processo and ano else numero_processo
                    
                    # Adicionar à lista
                    licitacoes.append({
                        'modalidade': modalidade,
                        'edital': edital,
                        'numero_processo': numero_processo,
                        'ano': ano,
                        'orgao': orgao,
                        'objeto': objeto[:500] if objeto else '',
                        'data_abertura': data_abertura,
                        'situacao': situacao,
                        'protocolo': protocolo,
                        'registro_preco': registro_preco,
                        'valor_estimado': valor_estimado
                    })
                    
                    if len(licitacoes) >= limit:
                        break
                        
                except Exception as e:
                    logger.debug(f"  ⚠️ Erro ao processar linha: {str(e)}")
                    continue
            
            return licitacoes
            
        except Exception as e:
            logger.error(f"  ❌ Erro ao processar CSV: {str(e)}")
            return []
    
    def _normalizar_key(self, key: str) -> str:
        """Normaliza chave do CSV para comparação"""
        if not key:
            return ''
        
        # Remover acentos e converter para lowercase
        key = key.lower().strip()
        key = key.replace('á', 'a').replace('é', 'e').replace('í', 'i')
        key = key.replace('ó', 'o').replace('ú', 'u').replace('ã', 'a')
        key = key.replace('ç', 'c').replace('ê', 'e').replace('ô', 'o')
        
        # Substituir espaços por underscore
        key = re.sub(r'\s+', '_', key)
        key = re.sub(r'[^a-z0-9_]', '', key)
        
        return key
    
    def _converter_para_formato_padrao(self, lic: Dict) -> Optional[Dict]:
        """
        Converte licitação do CSV para formato padrão do sistema
        
        Args:
            lic: Dicionário com dados da licitação
            
        Returns:
            Dicionário no formato padrão ou None
        """
        try:
            # Parse de data
            data_abertura = self._parse_date(lic.get('data_abertura', ''))
            
            # Extrair número do edital
            numero_processo = lic.get('edital', 'N/A')
            if '(' in numero_processo:
                numero_processo = numero_processo.split('(')[0].strip()
            
            # Normalizar modalidade
            modalidade = self._normalizar_modalidade(lic.get('modalidade', ''))
            
            # Normalizar status
            status = self._normalizar_status(lic.get('situacao', ''))
            
            # Extrair medicamento do objeto
            objeto = lic.get('objeto', '')
            medicamento = self._extrair_medicamento(objeto)
            
            # Construir link do protocolo (e-protocolo)
            protocolo = lic.get('protocolo', '')
            link_origem = None
            if protocolo:
                # Limpar protocolo
                protocolo_limpo = re.sub(r'[^\d]', '', protocolo)
                if protocolo_limpo:
                    link_origem = f'https://www.eprotocolo.pr.gov.br/spiweb/consultarProtocoloDigital.do?action=pesquisar&numeroProtocolo={protocolo_limpo}'
            
            return {
                'id': str(uuid.uuid4()),
                
                # CAMPOS MANDATÓRIOS
                'titulo_licitacao': objeto[:200] if objeto else 'Sem título',
                'medicamento': medicamento,
                'estado': self.estado,
                'estado_uf': self.estado,
                'orgao_licitante': lic.get('orgao', 'Governo do Paraná')[:200],
                'status': status,
                'status_aquisicao': status,
                'modalidade': modalidade,
                'numero_processo': numero_processo,
                
                # Datas
                'data_referencia': datetime.now(),
                'data_abertura': data_abertura,
                'data_inicial': data_abertura,
                'data_final': data_abertura,
                'data_limite': data_abertura,
                
                # Links
                'link_origem': link_origem or self.consulta_url,
                'link_documento': None,  # CSV não fornece link direto do PDF
                
                # Metadados expandidos
                'fonte_nome': self.fonte,
                'fonte_id': f'pr-csv-{numero_processo.replace("/", "-")}',
                'numero_pregao': numero_processo,
                'uasg': None,
                'esfera': 'Estadual',
                'objeto': objeto[:500],
                
                # Extras
                'registro_preco': lic.get('registro_preco', '').upper() == 'SIM',
                'protocolo': lic.get('protocolo', ''),
                
                # Itens
                'itens': [],
                
                # Tags
                'tags': self._extrair_tags(objeto),
                'is_mock': False,
                'fonte': 'PR'
            }
            
        except Exception as e:
            logger.error(f"  ❌ Erro ao converter licitação: {str(e)}")
            return None
    
    def _normalizar_modalidade(self, modalidade: str) -> str:
        """Normaliza a modalidade da licitação"""
        if not modalidade:
            return 'Pregão Eletrônico'
        
        modalidade_lower = modalidade.lower()
        
        if 'pregão eletrônico' in modalidade_lower or 'preg-e' in modalidade_lower:
            return 'Pregão Eletrônico'
        elif 'pregão presencial' in modalidade_lower or 'preg-p' in modalidade_lower:
            return 'Pregão Presencial'
        elif 'concorrência eletrônica' in modalidade_lower or 'conc-e' in modalidade_lower:
            return 'Concorrência Eletrônica'
        elif 'concorrência' in modalidade_lower:
            return 'Concorrência'
        elif 'dispensa' in modalidade_lower:
            return 'Dispensa de Licitação'
        elif 'inexigibilidade' in modalidade_lower:
            return 'Inexigibilidade'
        elif 'credenciamento' in modalidade_lower:
            return 'Credenciamento'
        elif 'leilão' in modalidade_lower:
            return 'Leilão'
        elif 'tomada de preço' in modalidade_lower:
            return 'Tomada de Preços'
        
        return modalidade[:50] if len(modalidade) > 50 else modalidade
    
    def _normalizar_status(self, situacao: str) -> str:
        """Normaliza o status da licitação"""
        if not situacao:
            return 'Em Licitação'
        
        situacao_lower = situacao.lower().strip()
        
        return self.status_map.get(situacao_lower, situacao[:30])
    
    def _extrair_medicamento(self, texto: str) -> str:
        """Extrai nome do medicamento do texto"""
        if not texto:
            return 'Não especificado'
        
        texto_lower = texto.lower()
        
        medicamentos = [
            'insulina', 'canabidiol', 'adalimumabe', 'pembrolizumabe', 'infliximabe',
            'metformina', 'omeprazol', 'paracetamol', 'dipirona', 'amoxicilina',
            'azitromicina', 'losartana', 'atenolol', 'ibuprofeno', 'diclofenaco',
            'tramadol', 'morfina', 'clonazepam', 'sertralina', 'fluoxetina',
            'cloroquina', 'hidroxicloroquina', 'ivermectina',
            'ritonavir', 'tocilizumabe', 'dexametasona', 'heparina', 'enoxaparina'
        ]
        
        for med in medicamentos:
            if med in texto_lower:
                return med.capitalize()
        
        if any(kw in texto_lower for kw in ['medicamento', 'fármaco', 'hospitalar', 'saúde', 'farmacêutico']):
            return 'Medicamento (ver objeto)'
        
        return 'Não especificado'
    
    def _extrair_tags(self, texto: str) -> List[str]:
        """Extrai tags relevantes do texto"""
        if not texto:
            return []
        
        texto_lower = texto.lower()
        tags = []
        
        if any(kw in texto_lower for kw in ['alto custo', 'especializado']):
            tags.append('alto_custo')
        if any(kw in texto_lower for kw in ['hospitalar', 'hospital']):
            tags.append('hospitalar')
        if any(kw in texto_lower for kw in ['urgente', 'emergência']):
            tags.append('urgente')
        if any(kw in texto_lower for kw in ['saúde', 'sesa', 'secretaria de saúde']):
            tags.append('saude')
        if any(kw in texto_lower for kw in ['registro de preço', 'ata de registro']):
            tags.append('registro_precos')
        
        return tags
    
    def _parse_date(self, texto: str) -> Optional[datetime]:
        """Parse de data em formato brasileiro"""
        if not texto:
            return None
        
        # Limpar texto
        texto_limpo = re.sub(r'[^\d/\-:\s]', '', texto).strip()
        
        # Tentar vários formatos
        formatos = [
            '%d/%m/%Y %H:%M',
            '%d/%m/%Y %H:%M:%S',
            '%d/%m/%Y',
            '%d-%m-%Y %H:%M',
            '%d-%m-%Y',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d'
        ]
        
        for formato in formatos:
            try:
                return datetime.strptime(texto_limpo.strip()[:19], formato)
            except ValueError:
                continue
        
        return None
    
    # Método de compatibilidade
    async def scrape(self, medicamento: str = None) -> List[Dict]:
        """Método de compatibilidade com interface padrão"""
        return await self.buscar_licitacoes(termo_busca=medicamento)
