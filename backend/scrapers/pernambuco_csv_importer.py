"""
Importador de Licitações de Pernambuco via CSV do Portal de Dados Abertos

FONTE: https://dados.pe.gov.br/dataset/licitacoes-tce
MÉTODO: Download direto de CSV por ano (atualizado frequentemente)

Vantagens:
- Sem CAPTCHA ou autenticação
- Dados estruturados e completos
- Histórico desde 2008 (17 anos!)
- Link direto para documento TCE
- Atualização frequente

Campos do CSV:
- ug: Unidade Gestora (órgão)
- razaosocial: Fornecedor vencedor
- nomemodalidade: Modalidade da licitação
- numeroanoprocesso: Número/Ano do processo
- situacaolicitacao: Status da licitação
- datapublicacaohomologacao: Data de homologação
- totaladjudicadolicitacao: Valor adjudicado
- estagiolicitacao: Estágio atual
- descricaoobjeto: Categoria do objeto
- objetoconformeedital: Descrição completa do objeto
- linkarquivo: Link direto para documento TCE

Criado: Dezembro 2024/2025
"""

from typing import List, Dict, Optional
from datetime import datetime
from io import StringIO
import logging
import requests
import uuid
import csv
import re

logger = logging.getLogger(__name__)


class PernambucoCsvImporter:
    """
    Importador de licitações de Pernambuco via CSV do Portal de Dados Abertos
    
    Portal: https://dados.pe.gov.br/dataset/licitacoes-tce
    Método: Download CSV direto por ano
    Atualização: Frequente (última: 13/12/2025)
    """
    
    def __init__(self):
        self.base_url = 'https://dados.pe.gov.br'
        self.dataset_url = f'{self.base_url}/dataset/licitacoes-tce'
        
        # URLs de download por ano (atualizadas conforme portal)
        self.download_urls = {
            2025: 'https://dados.pe.gov.br/dataset/6fc265b9-aca3-4c32-86c9-320c3b197b6f/resource/41138266-769b-4837-a3e7-9559b8e0a5dd/download/licitacoes_2025_20251213.csv',
            2024: 'https://dados.pe.gov.br/dataset/6fc265b9-aca3-4c32-86c9-320c3b197b6f/resource/6686d455-7ba0-4392-a49a-0d1080b99d5b/download/licitacoes_2024_20241214.csv',
            2023: 'https://dados.pe.gov.br/dataset/6fc265b9-aca3-4c32-86c9-320c3b197b6f/resource/a769a788-2558-4f7c-8b62-fc7a36e6495c/download/licitacoes_2023_20231230.csv',
        }
        
        self.estado = 'PE'
        self.fonte = 'Portal de Dados Abertos PE (TCE)'
        
        # Headers para requisição
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # Mapeamento de situações
        self.status_map = {
            'concluído': 'Homologado',
            'concluido': 'Homologado',
            'em andamento': 'Em Licitação',
            'cancelado': 'Cancelado',
            'cancelada': 'Cancelada',
            'revogado': 'Revogado',
            'revogada': 'Revogada',
            'deserto': 'Deserto',
            'deserta': 'Deserta',
            'fracassado': 'Fracassado',
            'fracassada': 'Fracassada',
            'anulado': 'Anulado',
            'anulada': 'Anulada',
            'suspenso': 'Suspenso',
            'suspensa': 'Suspensa'
        }
        
        # Órgãos de saúde prioritários
        self.orgaos_saude = [
            'SAÚDE', 'SAUDE', 'SES', 'HOSPITAL', 'HEMOPE', 'IMIP',
            'PROCAPE', 'HOC', 'HGV', 'HR ', 'UPAE', 'UPA ',
            'FARMÁCIA', 'FARMACIA', 'MEDICAMENT', 'SAMU',
            'VIGILÂNCIA', 'VIGILANCIA', 'SANITÁRIA', 'SANITARIA'
        ]
    
    async def buscar_licitacoes(
        self,
        termo_busca: str = None,
        ano: int = None,
        apenas_saude: bool = True,
        limit: int = 50
    ) -> List[Dict]:
        """
        Busca licitações de Pernambuco via CSV do Portal de Dados Abertos
        
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
            logger.info(f"🔍 [PE] Iniciando importação CSV: '{termo_busca or 'geral'}' - Ano {ano}")
            
            # ETAPA 1: Obter URL do CSV para o ano
            csv_url = self._get_csv_url(ano)
            if not csv_url:
                logger.warning(f"  ⚠️ URL não encontrada para ano {ano}")
                return []
            
            # ETAPA 2: Baixar o CSV
            logger.info(f"  📥 Baixando CSV de licitações PE {ano}...")
            csv_content = await self._baixar_csv(csv_url)
            
            if not csv_content:
                logger.warning("  ⚠️ Falha no download do CSV")
                return []
            
            logger.info(f"  ✅ CSV baixado com sucesso ({len(csv_content)/1024/1024:.1f} MB)")
            
            # ETAPA 3: Processar CSV
            logger.info(f"  📊 Processando CSV...")
            licitacoes = self._processar_csv(
                csv_content,
                termo_busca=termo_busca,
                apenas_saude=apenas_saude,
                limit=limit
            )
            
            logger.info(f"  ✅ Processadas {len(licitacoes)} licitações")
            
            # ETAPA 4: Converter para formato padrão
            for lic in licitacoes:
                resultado = self._converter_para_formato_padrao(lic)
                if resultado:
                    resultados.append(resultado)
            
            logger.info(f"🎯 [PE] Total processado: {len(resultados)} licitações válidas")
            
            return resultados
            
        except Exception as e:
            logger.error(f"❌ [PE] Erro geral na importação: {str(e)}")
            import traceback
            logger.debug(traceback.format_exc())
            return []
    
    def _get_csv_url(self, ano: int) -> Optional[str]:
        """Obtém a URL do CSV para o ano especificado"""
        if ano in self.download_urls:
            return self.download_urls[ano]
        
        # Tentar construir URL padrão se não estiver no mapeamento
        # O padrão do portal é: licitacoes_{ano}_{data}.csv
        logger.warning(f"  ⚠️ Ano {ano} não está no mapeamento, usando ano atual")
        return self.download_urls.get(datetime.now().year)
    
    async def _baixar_csv(self, url: str) -> Optional[str]:
        """
        Baixa o CSV de licitações
        
        Args:
            url: URL do CSV
            
        Returns:
            Conteúdo do CSV como string ou None
        """
        try:
            response = requests.get(
                url,
                headers=self.headers,
                timeout=120,  # 2 minutos para download
                stream=False
            )
            
            if response.status_code == 200:
                # Tentar decodificar com diferentes encodings
                for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']:
                    try:
                        return response.content.decode(encoding)
                    except UnicodeDecodeError:
                        continue
                
                # Fallback: ignorar erros
                return response.content.decode('utf-8', errors='ignore')
            else:
                logger.error(f"  ❌ HTTP {response.status_code} ao baixar CSV")
                return None
                
        except requests.exceptions.Timeout:
            logger.error("  ❌ Timeout ao baixar CSV (>2min)")
            return None
        except Exception as e:
            logger.error(f"  ❌ Erro ao baixar CSV: {str(e)}")
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
            first_line = csv_content.split('\n')[0]
            delimiter = ',' if first_line.count(',') > first_line.count(';') else ';'
            
            # Parse CSV
            reader = csv.DictReader(StringIO(csv_content), delimiter=delimiter)
            
            # Contadores para log
            total_lidas = 0
            filtradas_saude = 0
            filtradas_termo = 0
            
            for row in reader:
                total_lidas += 1
                
                try:
                    # Limpar campos
                    row = {k.strip().strip('"'): v.strip().strip('"') if v else '' for k, v in row.items() if k}
                    
                    # Extrair campos principais
                    # Campos do CSV PE:
                    # ug, razaosocial, totaladjudicadolicitante, nomemodalidade,
                    # numeroanoprocesso, situacaolicitacao, datapublicacaohomologacao,
                    # totaladjudicadolicitacao, estagiolicitacao, resultadohabilitacao,
                    # adjudicada, descricaoobjeto, especificacaoobjeto, numeroprocesso,
                    # anoprocesso, caracteristicaobjeto, objetoconformeedital, linkarquivo
                    
                    ug = row.get('ug', '')
                    razao_social = row.get('razaosocial', '')
                    modalidade = row.get('nomemodalidade', '')
                    num_ano_processo = row.get('numeroanoprocesso', '')
                    situacao = row.get('situacaolicitacao', '')
                    data_homologacao = row.get('datapublicacaohomologacao', '')
                    valor_adjudicado = row.get('totaladjudicadolicitacao', '')
                    estagio = row.get('estagiolicitacao', '')
                    descricao_objeto = row.get('descricaoobjeto', '')
                    objeto_edital = row.get('objetoconformeedital', '')
                    link_arquivo = row.get('linkarquivo', '')
                    numero_processo = row.get('numeroprocesso', '')
                    ano_processo = row.get('anoprocesso', '')
                    
                    # Filtrar por órgãos de saúde
                    if apenas_saude:
                        texto_ug = ug.upper()
                        texto_objeto = f"{descricao_objeto} {objeto_edital}".upper()
                        
                        is_saude_orgao = any(org in texto_ug for org in self.orgaos_saude)
                        is_saude_objeto = any(kw in texto_objeto for kw in [
                            'MEDICAMENTO', 'FÁRMACO', 'FARMAC', 'HOSPITALAR',
                            'SAÚDE', 'SAUDE', 'MÉDICO', 'MEDICO', 'INSUMO',
                            'CIRURG', 'LABORAT', 'DIAGNÓSTIC', 'VACINA'
                        ])
                        
                        if not (is_saude_orgao or is_saude_objeto):
                            filtradas_saude += 1
                            continue
                    
                    # Filtrar por termo de busca
                    if termo_busca:
                        termo_lower = termo_busca.lower()
                        texto_completo = f"{objeto_edital} {descricao_objeto} {ug}".lower()
                        if termo_lower not in texto_completo:
                            filtradas_termo += 1
                            continue
                    
                    # Adicionar à lista
                    licitacoes.append({
                        'ug': ug,
                        'razao_social': razao_social,
                        'modalidade': modalidade,
                        'num_ano_processo': num_ano_processo,
                        'numero_processo': numero_processo,
                        'ano_processo': ano_processo,
                        'situacao': situacao.strip(),
                        'estagio': estagio,
                        'data_homologacao': data_homologacao,
                        'valor_adjudicado': valor_adjudicado,
                        'descricao_objeto': descricao_objeto,
                        'objeto_edital': objeto_edital[:500] if objeto_edital else '',
                        'link_arquivo': link_arquivo
                    })
                    
                    if len(licitacoes) >= limit:
                        break
                        
                except Exception as e:
                    logger.debug(f"  ⚠️ Erro ao processar linha: {str(e)}")
                    continue
            
            logger.debug(f"  📊 Estatísticas: Total={total_lidas}, Saúde={filtradas_saude}, Termo={filtradas_termo}")
            
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
            # Parse de data
            data_homologacao = self._parse_date(lic.get('data_homologacao', ''))
            
            # Normalizar modalidade
            modalidade = self._normalizar_modalidade(lic.get('modalidade', ''))
            
            # Normalizar status
            status = self._normalizar_status(lic.get('situacao', ''), lic.get('estagio', ''))
            
            # Extrair medicamento do objeto
            objeto = lic.get('objeto_edital', '') or lic.get('descricao_objeto', '')
            medicamento = self._extrair_medicamento(objeto)
            
            # Número do processo
            numero_processo = lic.get('num_ano_processo', '') or f"{lic.get('numero_processo', '')}/{lic.get('ano_processo', '')}"
            
            # Link do documento
            link_documento = lic.get('link_arquivo', '')
            
            # Parse de valor
            valor_adjudicado = self._parse_valor(lic.get('valor_adjudicado', ''))
            
            return {
                'id': str(uuid.uuid4()),
                
                # CAMPOS MANDATÓRIOS
                'titulo_licitacao': objeto[:200] if objeto else 'Sem título',
                'medicamento': medicamento,
                'estado': self.estado,
                'estado_uf': self.estado,
                'orgao_licitante': lic.get('ug', 'Governo de Pernambuco')[:200],
                'status': status,
                'status_aquisicao': status,
                'modalidade': modalidade,
                'numero_processo': numero_processo,
                
                # Datas
                'data_referencia': datetime.now(),
                'data_abertura': data_homologacao,
                'data_inicial': data_homologacao,
                'data_final': data_homologacao,
                'data_limite': data_homologacao,
                'data_homologacao': data_homologacao,
                
                # Links (NAVEGAÇÃO DUPLA - link direto para documento TCE!)
                'link_origem': self.dataset_url,
                'link_documento': link_documento if link_documento else None,
                
                # Metadados expandidos
                'fonte_nome': self.fonte,
                'fonte_id': f'pe-csv-{numero_processo.replace("/", "-").replace(" ", "")}',
                'numero_pregao': numero_processo,
                'uasg': None,
                'esfera': 'Estadual',
                'objeto': objeto[:500],
                
                # Extras
                'fornecedor': lic.get('razao_social', ''),
                'valor_adjudicado': valor_adjudicado,
                'estagio': lic.get('estagio', ''),
                
                # Itens
                'itens': [],
                
                # Tags
                'tags': self._extrair_tags(objeto),
                'is_mock': False,
                'fonte': 'PE'
            }
            
        except Exception as e:
            logger.error(f"  ❌ Erro ao converter licitação: {str(e)}")
            return None
    
    def _normalizar_modalidade(self, modalidade: str) -> str:
        """Normaliza a modalidade da licitação"""
        if not modalidade:
            return 'Pregão Eletrônico'
        
        modalidade_lower = modalidade.lower()
        
        if 'pregão eletrônico' in modalidade_lower or 'pregao eletronico' in modalidade_lower:
            return 'Pregão Eletrônico'
        elif 'pregão presencial' in modalidade_lower or 'pregao presencial' in modalidade_lower:
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
        elif 'procedimento' in modalidade_lower and 'próprio' in modalidade_lower:
            return 'Procedimento Próprio'
        
        return modalidade[:50] if len(modalidade) > 50 else modalidade
    
    def _normalizar_status(self, situacao: str, estagio: str = '') -> str:
        """Normaliza o status da licitação"""
        if not situacao:
            return 'Em Licitação'
        
        situacao_lower = situacao.lower().strip()
        
        for key, value in self.status_map.items():
            if key in situacao_lower:
                return value
        
        # Verificar estágio também
        if estagio:
            estagio_lower = estagio.lower()
            if 'homologado' in estagio_lower or 'adjudicado' in estagio_lower:
                return 'Homologado'
            elif 'publicado' in estagio_lower:
                return 'Publicado'
        
        return situacao[:30].strip() if situacao else 'Em Licitação'
    
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
        if any(kw in texto_lower for kw in ['saúde', 'ses', 'secretaria de saúde']):
            tags.append('saude')
        if any(kw in texto_lower for kw in ['registro de preço', 'ata de registro']):
            tags.append('registro_precos')
        
        return tags
    
    def _parse_date(self, texto: str) -> Optional[datetime]:
        """Parse de data em formato brasileiro/ISO"""
        if not texto:
            return None
        
        # Limpar texto
        texto_limpo = texto.strip()
        
        # Tentar vários formatos
        formatos = [
            '%Y/%m/%d %H:%M:%S.%f',  # Formato do PE: 2025/08/27 00:00:00.000
            '%Y/%m/%d %H:%M:%S',
            '%Y/%m/%d',
            '%d/%m/%Y %H:%M:%S',
            '%d/%m/%Y %H:%M',
            '%d/%m/%Y',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d'
        ]
        
        for formato in formatos:
            try:
                return datetime.strptime(texto_limpo[:23], formato)
            except ValueError:
                continue
        
        return None
    
    def _parse_valor(self, texto: str) -> Optional[float]:
        """Parse de valor monetário"""
        if not texto:
            return None
        
        try:
            # Remover caracteres não numéricos exceto vírgula e ponto
            valor_limpo = re.sub(r'[^\d,.]', '', str(texto).strip())
            
            # Se tiver vírgula como decimal (formato brasileiro)
            if ',' in valor_limpo and '.' in valor_limpo:
                # 1.234,56 -> 1234.56
                valor_limpo = valor_limpo.replace('.', '').replace(',', '.')
            elif ',' in valor_limpo:
                # 1234,56 -> 1234.56
                valor_limpo = valor_limpo.replace(',', '.')
            
            return float(valor_limpo)
        except ValueError:
            return None
    
    # Método de compatibilidade
    async def scrape(self, medicamento: str = None) -> List[Dict]:
        """Método de compatibilidade com interface padrão"""
        return await self.buscar_licitacoes(termo_busca=medicamento)
