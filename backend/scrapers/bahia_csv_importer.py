"""
Importador de Licitações da Bahia via CSV do Portal de Dados Abertos

FONTE: https://dados.ba.gov.br/dataset/licitacoes
MÉTODO: Download do banco de dados CSV (atualizado diariamente)

Vantagens:
- Sem CAPTCHA ou autenticação
- Dados estruturados e completos
- Atualização diária pelo governo
- Mais de 100.000 processos de licitação

Arquivos do ZIP:
- VW_PROC_AQUISICAO_LIC_REQ.csv (Processos principais - ~106k registros)
- VW_PROC_AQUISICAO_ITEM.csv (Itens licitados - ~955k registros)
- VW_PROC_AQUISICAO_FORNEC.csv (Fornecedores)
- VW_PROC_AQUISICAO_ITEM_INSTRUMENTO.csv (Instrumentos)

Campos principais do CSV:
- N° da Licitação / N° da Licitação Formatado
- Modalidade (Pregão Presencial, Pregão Eletrônico, etc.)
- Situação (Homologada, Em andamento, etc.)
- Órgão Solicitante / Sigla do Órgão Solicitante
- Valor Estimado / Valor Homologado
- Data de Publicação DOE / Data de Abertura / Data de Homologação
- Objeto
- Registro de preço

Criado: Dezembro 2024/2025
"""

from typing import List, Dict, Optional
from datetime import datetime
from io import StringIO, BytesIO
import logging
import zipfile
import requests
import uuid
import csv
import os
import re

logger = logging.getLogger(__name__)


class BahiaCsvImporter:
    """
    Importador de licitações da Bahia via CSV do Portal de Dados Abertos
    
    Portal: https://dados.ba.gov.br/dataset/licitacoes
    Método: Download CSV com banco de dados completo
    Atualização: Diária
    """
    
    def __init__(self):
        self.base_url = 'https://dados.ba.gov.br'
        self.dataset_url = f'{self.base_url}/dataset/licitacoes'
        
        # URL direta do download (pode mudar - melhor obter dinamicamente)
        self.download_url = 'https://dados.ba.gov.br/dataset/36c792f9-1999-4f21-a669-752a178b06b7/resource/c5040c7d-4375-459e-93b0-beca841f63b4/download/licitacoes.zip'
        
        self.estado = 'BA'
        self.fonte = 'Portal de Dados Abertos BA (CSV)'
        
        # Diretório para armazenar downloads
        self.download_dir = '/tmp/ba_csv_downloads'
        
        # CSV principal a processar
        self.csv_principal = 'VW_PROC_AQUISICAO_LIC_REQ.csv'
        
        # Mapeamento de situações
        self.status_map = {
            'homologada': 'Homologada',
            'homologado': 'Homologado',
            'publicada': 'Publicada',
            'aberta': 'Em Licitação',
            'em andamento': 'Em Licitação',
            'cancelada': 'Cancelada',
            'revogada': 'Revogada',
            'deserta': 'Deserta',
            'fracassada': 'Fracassada',
            'anulada': 'Anulada',
            'suspensa': 'Suspensa',
            'adjudicada': 'Adjudicada'
        }
        
        # Órgãos de saúde prioritários
        self.orgaos_saude = [
            'SESAB', 'SAUDE', 'HOSPITAL', 'HEMOBA', 'PLANSERV',
            'FUNESA', 'FESF', 'LACEN', 'VIGILANCIA', 'SANITARIA',
            'FARMACIA', 'FARMACEUTIC', 'MEDICAMENT'
        ]
        
        # Headers para requisição
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    async def buscar_licitacoes(
        self,
        termo_busca: str = None,
        ano: int = None,
        apenas_saude: bool = True,
        limit: int = 50
    ) -> List[Dict]:
        """
        Busca licitações da Bahia via CSV do Portal de Dados Abertos
        
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
            logger.info(f"🔍 [BA] Iniciando importação CSV: '{termo_busca or 'geral'}' - Ano {ano}")
            
            # Garantir diretório de download existe
            os.makedirs(self.download_dir, exist_ok=True)
            
            # ETAPA 1: Baixar o ZIP
            logger.info(f"  📥 Baixando ZIP de licitações BA...")
            zip_content = await self._baixar_zip()
            
            if not zip_content:
                logger.warning("  ⚠️ Falha no download do ZIP")
                return []
            
            logger.info(f"  ✅ ZIP baixado com sucesso ({len(zip_content)/1024/1024:.1f} MB)")
            
            # ETAPA 2: Extrair CSV principal do ZIP
            logger.info(f"  📦 Extraindo {self.csv_principal}...")
            csv_content = self._extrair_csv_do_zip(zip_content)
            
            if not csv_content:
                logger.warning("  ⚠️ CSV principal não encontrado no ZIP")
                return []
            
            logger.info(f"  ✅ CSV extraído ({len(csv_content)/1024/1024:.1f} MB)")
            
            # ETAPA 3: Processar CSV
            logger.info(f"  📊 Processando CSV...")
            licitacoes = self._processar_csv(
                csv_content,
                termo_busca=termo_busca,
                ano=ano,
                apenas_saude=apenas_saude,
                limit=limit
            )
            
            logger.info(f"  ✅ Processadas {len(licitacoes)} licitações")
            
            # ETAPA 4: Converter para formato padrão
            for lic in licitacoes:
                resultado = self._converter_para_formato_padrao(lic)
                if resultado:
                    resultados.append(resultado)
            
            logger.info(f"🎯 [BA] Total processado: {len(resultados)} licitações válidas")
            
            return resultados
            
        except Exception as e:
            logger.error(f"❌ [BA] Erro geral na importação: {str(e)}")
            import traceback
            logger.debug(traceback.format_exc())
            return []
    
    async def _baixar_zip(self) -> Optional[bytes]:
        """
        Baixa o ZIP de licitações do Portal de Dados Abertos
        
        Returns:
            Conteúdo do ZIP como bytes ou None
        """
        try:
            # Usar requests com verify=False para contornar problema de SSL
            response = requests.get(
                self.download_url,
                headers=self.headers,
                verify=False,  # Ignorar verificação SSL (certificado do portal tem problema)
                timeout=300,  # 5 minutos para download de arquivo grande
                stream=True
            )
            
            if response.status_code == 200:
                content = response.content
                return content
            else:
                logger.error(f"  ❌ HTTP {response.status_code} ao baixar ZIP")
                return None
                
        except requests.exceptions.Timeout:
            logger.error("  ❌ Timeout ao baixar ZIP (>5min)")
            return None
        except Exception as e:
            logger.error(f"  ❌ Erro ao baixar ZIP: {str(e)}")
            return None
    
    def _extrair_csv_do_zip(self, zip_content: bytes) -> Optional[str]:
        """
        Extrai o CSV principal do ZIP
        
        Args:
            zip_content: Conteúdo do ZIP como bytes
            
        Returns:
            Conteúdo do CSV como string ou None
        """
        try:
            with zipfile.ZipFile(BytesIO(zip_content), 'r') as zf:
                # Listar arquivos
                file_list = zf.namelist()
                logger.debug(f"    📋 Arquivos no ZIP: {file_list}")
                
                # Encontrar CSV principal
                csv_file = None
                for name in file_list:
                    if self.csv_principal in name or 'LIC_REQ' in name.upper():
                        csv_file = name
                        break
                
                if not csv_file:
                    # Usar primeiro CSV se não encontrar o principal
                    for name in file_list:
                        if name.lower().endswith('.csv'):
                            csv_file = name
                            break
                
                if csv_file:
                    logger.info(f"    📄 Extraindo: {csv_file}")
                    csv_bytes = zf.read(csv_file)
                    
                    # Tentar decodificar com diferentes encodings
                    for encoding in ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
                        try:
                            return csv_bytes.decode(encoding)
                        except UnicodeDecodeError:
                            continue
                    
                    # Fallback: ignorar erros
                    return csv_bytes.decode('utf-8', errors='ignore')
                
                logger.warning("    ⚠️ Nenhum CSV encontrado no ZIP")
                return None
                
        except Exception as e:
            logger.error(f"    ❌ Erro ao extrair CSV do ZIP: {str(e)}")
            return None
    
    def _processar_csv(
        self,
        csv_content: str,
        termo_busca: str = None,
        ano: int = None,
        apenas_saude: bool = True,
        limit: int = 50
    ) -> List[Dict]:
        """
        Processa o conteúdo CSV e retorna lista de licitações
        
        Args:
            csv_content: Conteúdo do CSV como string
            termo_busca: Termo para filtrar
            ano: Ano específico para filtrar
            apenas_saude: Filtrar apenas órgãos de saúde
            limit: Limite de resultados
            
        Returns:
            Lista de dicionários com dados das licitações
        """
        licitacoes = []
        
        try:
            # Detectar delimitador (BA usa ponto-e-vírgula)
            delimiter = ';' if ';' in csv_content[:1000] else ','
            
            # Parse CSV
            reader = csv.DictReader(StringIO(csv_content), delimiter=delimiter)
            
            # Contadores para log
            total_lidas = 0
            filtradas_ano = 0
            filtradas_saude = 0
            filtradas_termo = 0
            
            for row in reader:
                total_lidas += 1
                
                try:
                    # Limpar BOM e aspas dos campos
                    row = {k.strip().strip('"').strip('\ufeff'): v.strip().strip('"') if v else '' for k, v in row.items()}
                    
                    # Extrair campos principais
                    # Colunas do CSV BA:
                    # "N° da Licitação", "N° da Licitação Formatado", "Modalidade", "Situação",
                    # "Sigla do Órgão Solicitante", "Órgão Solicitante", "Objeto",
                    # "Data de Abertura", "Data de Homologação", "Valor Estimado", "Registro de preço"
                    
                    num_licitacao = row.get('N° da Licitação Formatado', '') or row.get('N° da Licitação', '')
                    modalidade = row.get('Modalidade', '')
                    situacao = row.get('Situação', '')
                    sigla_orgao = row.get('Sigla do Órgão Solicitante', '')
                    orgao = row.get('Órgão Solicitante', '') or row.get('DESC_SECRETARIA_SOLICITANTE', '')
                    objeto = row.get('Objeto', '')
                    data_abertura = row.get('Data de Abertura', '')
                    data_homologacao = row.get('Data de Homologação', '') or row.get('Data de Homologação Tratada', '')
                    valor_estimado = row.get('Valor Estimado', '')
                    registro_preco = row.get('Registro de preço', '')
                    ano_aquisicao = row.get('Ano da Aquisição', '')
                    processo_sei = row.get('Processo SEI', '')
                    
                    # Filtrar por ano
                    if ano:
                        ano_str = str(ano)
                        ano_match = False
                        
                        # Verificar no campo Ano da Aquisição
                        if ano_aquisicao and ano_str in ano_aquisicao:
                            ano_match = True
                        # Verificar na data de abertura
                        elif data_abertura and ano_str in data_abertura:
                            ano_match = True
                        # Verificar no número da licitação
                        elif num_licitacao and ano_str in num_licitacao:
                            ano_match = True
                        
                        if not ano_match:
                            filtradas_ano += 1
                            continue
                    
                    # Filtrar por órgãos de saúde
                    if apenas_saude:
                        texto_orgao = f"{sigla_orgao} {orgao}".upper()
                        texto_objeto = objeto.upper()
                        
                        is_saude_orgao = any(org in texto_orgao for org in self.orgaos_saude)
                        is_saude_objeto = any(kw in texto_objeto for kw in [
                            'MEDICAMENTO', 'FÁRMACO', 'FARMAC', 'HOSPITALAR', 
                            'SAÚDE', 'SAUDE', 'MÉDICO', 'MEDICO', 'INSUMO',
                            'CIRURG', 'LABORAT', 'DIAGNÓSTIC'
                        ])
                        
                        if not (is_saude_orgao or is_saude_objeto):
                            filtradas_saude += 1
                            continue
                    
                    # Filtrar por termo de busca
                    if termo_busca:
                        termo_lower = termo_busca.lower()
                        texto_completo = f"{objeto} {orgao} {modalidade}".lower()
                        if termo_lower not in texto_completo:
                            filtradas_termo += 1
                            continue
                    
                    # Adicionar à lista
                    licitacoes.append({
                        'num_licitacao': num_licitacao,
                        'modalidade': modalidade,
                        'situacao': situacao.strip(),
                        'sigla_orgao': sigla_orgao,
                        'orgao': orgao,
                        'objeto': objeto[:500] if objeto else '',
                        'data_abertura': data_abertura,
                        'data_homologacao': data_homologacao,
                        'valor_estimado': valor_estimado,
                        'registro_preco': registro_preco,
                        'processo_sei': processo_sei,
                        'ano': ano_aquisicao or str(ano)
                    })
                    
                    if len(licitacoes) >= limit:
                        break
                        
                except Exception as e:
                    logger.debug(f"  ⚠️ Erro ao processar linha: {str(e)}")
                    continue
            
            logger.debug(f"  📊 Estatísticas: Total={total_lidas}, Ano={filtradas_ano}, Saúde={filtradas_saude}, Termo={filtradas_termo}")
            
            return licitacoes
            
        except Exception as e:
            logger.error(f"  ❌ Erro ao processar CSV: {str(e)}")
            return []
    
    def _converter_para_formato_padrao(self, lic: Dict) -> Optional[Dict]:
        """
        Converte licitação do CSV para formato padrão do sistema
        
        Args:
            lic: Dicionário com dados da licitação
            
        Returns:
            Dicionário no formato padrão ou None
        """
        try:
            # Parse de datas
            data_abertura = self._parse_date(lic.get('data_abertura', ''))
            data_homologacao = self._parse_date(lic.get('data_homologacao', ''))
            
            # Normalizar modalidade
            modalidade = self._normalizar_modalidade(lic.get('modalidade', ''))
            
            # Normalizar status
            status = self._normalizar_status(lic.get('situacao', ''))
            
            # Extrair medicamento do objeto
            objeto = lic.get('objeto', '')
            medicamento = self._extrair_medicamento(objeto)
            
            # Construir link do portal (se disponível)
            link_origem = 'https://www.comprasnet.ba.gov.br'
            
            # Número do processo formatado
            num_licitacao = lic.get('num_licitacao', 'N/A')
            
            # Parse de valor
            valor_estimado = self._parse_valor(lic.get('valor_estimado', ''))
            
            return {
                'id': str(uuid.uuid4()),
                
                # CAMPOS MANDATÓRIOS
                'titulo_licitacao': objeto[:200] if objeto else 'Sem título',
                'medicamento': medicamento,
                'estado': self.estado,
                'estado_uf': self.estado,
                'orgao_licitante': (lic.get('orgao', '') or lic.get('sigla_orgao', '') or 'Governo da Bahia')[:200],
                'status': status,
                'status_aquisicao': status,
                'modalidade': modalidade,
                'numero_processo': num_licitacao,
                
                # Datas
                'data_referencia': datetime.now(),
                'data_abertura': data_abertura,
                'data_inicial': data_abertura,
                'data_final': data_abertura,
                'data_limite': data_abertura,
                'data_homologacao': data_homologacao,
                
                # Links
                'link_origem': link_origem,
                'link_documento': None,
                
                # Metadados expandidos
                'fonte_nome': self.fonte,
                'fonte_id': f'ba-csv-{num_licitacao.replace("/", "-").replace(".", "-")}',
                'numero_pregao': num_licitacao,
                'uasg': None,
                'esfera': 'Estadual',
                'objeto': objeto[:500],
                
                # Extras
                'registro_preco': lic.get('registro_preco', '').upper() in ['SIM', 'S', 'TRUE', '1'],
                'valor_estimado': valor_estimado,
                'processo_sei': lic.get('processo_sei', ''),
                
                # Itens
                'itens': [],
                
                # Tags
                'tags': self._extrair_tags(objeto),
                'is_mock': False,
                'fonte': 'BA'
            }
            
        except Exception as e:
            logger.error(f"  ❌ Erro ao converter licitação: {str(e)}")
            return None
    
    def _normalizar_modalidade(self, modalidade: str) -> str:
        """Normaliza a modalidade da licitação"""
        if not modalidade:
            return 'Pregão Eletrônico'
        
        modalidade_lower = modalidade.lower()
        
        if 'pregão eletrônico' in modalidade_lower or 'pe' == modalidade_lower:
            return 'Pregão Eletrônico'
        elif 'pregão presencial' in modalidade_lower or 'pp' == modalidade_lower:
            return 'Pregão Presencial'
        elif 'concorrência' in modalidade_lower or 'concorrencia' in modalidade_lower:
            if 'eletrônica' in modalidade_lower or 'eletronica' in modalidade_lower:
                return 'Concorrência Eletrônica'
            return 'Concorrência'
        elif 'dispensa' in modalidade_lower:
            return 'Dispensa de Licitação'
        elif 'inexigibilidade' in modalidade_lower:
            return 'Inexigibilidade'
        elif 'credenciamento' in modalidade_lower:
            return 'Credenciamento'
        elif 'leilão' in modalidade_lower or 'leilao' in modalidade_lower:
            return 'Leilão'
        elif 'tomada de preço' in modalidade_lower:
            return 'Tomada de Preços'
        elif 'convite' in modalidade_lower:
            return 'Convite'
        
        return modalidade[:50] if len(modalidade) > 50 else modalidade
    
    def _normalizar_status(self, situacao: str) -> str:
        """Normaliza o status da licitação"""
        if not situacao:
            return 'Em Licitação'
        
        situacao_lower = situacao.lower().strip()
        
        for key, value in self.status_map.items():
            if key in situacao_lower:
                return value
        
        return situacao[:30].strip()
    
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
        if any(kw in texto_lower for kw in ['saúde', 'sesab', 'secretaria de saúde']):
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
            '%d/%m/%Y %H:%M:%S',
            '%d/%m/%Y %H:%M',
            '%d/%m/%Y',
            '%d-%m-%Y %H:%M:%S',
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
    
    def _parse_valor(self, texto: str) -> Optional[float]:
        """Parse de valor monetário"""
        if not texto:
            return None
        
        try:
            # Remover caracteres não numéricos exceto vírgula e ponto
            valor_limpo = re.sub(r'[^\d,.]', '', texto)
            
            # Converter formato brasileiro (1.234,56) para float
            if ',' in valor_limpo:
                valor_limpo = valor_limpo.replace('.', '').replace(',', '.')
            
            return float(valor_limpo)
        except ValueError:
            return None
    
    # Método de compatibilidade
    async def scrape(self, medicamento: str = None) -> List[Dict]:
        """Método de compatibilidade com interface padrão"""
        return await self.buscar_licitacoes(termo_busca=medicamento)
