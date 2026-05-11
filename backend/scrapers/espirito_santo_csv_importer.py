"""
Importador de Licitações do Espírito Santo via CSV do Portal de Dados Abertos

FONTE: https://dados.es.gov.br/dataset/portal-da-transparencia-compras-publicas
MÉTODO: Download de CSV anual (arquivos desde 2009)

Vantagens:
- Sem CAPTCHA ou autenticação
- Dados de TODOS os órgãos estaduais do ES
- Histórico desde 2009 (16 anos!)
- Atualização diária
- Dados detalhados com justificativa e objeto completo

Campos do CSV:
- IdLicitacao: ID único da licitação
- NomeOrgao: Nome do órgão licitante
- Modalidade: Tipo de licitação (Pregão, Dispensa, etc.)
- NumeroProcesso: Número do processo
- DataCriacao: Data de criação
- DataAbertura: Data de abertura
- Objeto: Descrição do objeto licitado
- RegistroPreco: Se é registro de preços (True/False)
- Situacao: Status (Encerrado, Em andamento, etc.)
- TipoLicitacao: Tipo (Menor Preço, etc.)
- Justificativa: Justificativa da contratação

Criado: Dezembro 2025
"""

from typing import List, Dict, Optional
from datetime import datetime, timedelta
from io import StringIO
import logging
import requests
import uuid
import csv
import re

logger = logging.getLogger(__name__)


class EspiritoSantoCsvImporter:
    """
    Importador de licitações do Espírito Santo via CSV do Portal de Dados Abertos
    
    Portal: https://dados.es.gov.br/dataset/portal-da-transparencia-compras-publicas
    Método: Download CSV anual
    Atualização: Diária
    Cobertura: Todos os órgãos do Estado do ES
    """
    
    def __init__(self):
        self.base_url = 'https://dados.es.gov.br'
        self.dataset_url = f'{self.base_url}/dataset/portal-da-transparencia-compras-publicas'
        
        # URLs de download por ano
        self.download_urls = {
            2025: f'{self.base_url}/dataset/ea970c7f-c524-45b0-a346-74ef5b1af218/resource/e48980a6-347b-4285-8b29-11d8210fc0a5/download/licitacoes-2025.csv',
            2024: f'{self.base_url}/dataset/ea970c7f-c524-45b0-a346-74ef5b1af218/resource/a7afb843-9a30-48f2-8066-07ffa0906dbb/download/licitacoes-2024.csv',
            2023: f'{self.base_url}/dataset/ea970c7f-c524-45b0-a346-74ef5b1af218/resource/4ba4c2fe-9b12-4a9a-a4dd-ee8c21874962/download/licitacoes-2023.csv',
            2022: f'{self.base_url}/dataset/ea970c7f-c524-45b0-a346-74ef5b1af218/resource/ee9dc8a8-be3e-42bd-8a6d-247e51dbb0f0/download/licitacoes-2022.csv'
        }
        
        self.estado = 'ES'
        self.fonte = 'Dados Abertos ES'
        
        # Headers para requisição
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # Mapeamento de modalidades
        self.modalidade_map = {
            'pregão eletrônico': 'Pregão Eletrônico',
            'pregao eletronico': 'Pregão Eletrônico',
            'pregão presencial': 'Pregão Presencial',
            'dispensa de licitação': 'Dispensa de Licitação',
            'dispensa': 'Dispensa de Licitação',
            'inexigibilidade': 'Inexigibilidade',
            'concorrência': 'Concorrência',
            'concorrencia': 'Concorrência',
            'tomada de preços': 'Tomada de Preços',
            'convite': 'Convite',
            'credenciamento': 'Credenciamento',
            'adesão': 'Adesão a Ata de Registro'
        }
        
        # Órgãos de saúde
        self.orgaos_saude = [
            'SAÚDE', 'SAUDE', 'SESA', 'HOSPITAL', 'IDAF', 'LACEN',
            'HEMOES', 'HEMOCENTRO', 'FARMÁCIA', 'FARMACIA', 'VIGILÂNCIA',
            'SANITÁRIA', 'SANITARIA', 'FUNDO ESTADUAL', 'CAPS'
        ]
        
        # Keywords de saúde para filtrar objetos
        self.keywords_saude = [
            'medicamento', 'fármaco', 'farmac', 'hospitalar', 'saúde', 'saude',
            'médico', 'medico', 'insumo', 'cirurg', 'laborat', 'diagnóstic',
            'vacina', 'seringa', 'agulha', 'luva', 'mascara', 'máscara',
            'semaglutida', 'insulina', 'canabidiol', 'quimioterápico'
        ]
    
    async def buscar_licitacoes(
        self,
        termo_busca: str = None,
        ano: int = None,
        apenas_saude: bool = True,
        apenas_futuras: bool = False,
        limit: int = 50
    ) -> List[Dict]:
        """
        Busca licitações do Espírito Santo via CSV do Portal de Dados Abertos
        OTIMIZADO PARA PROSPECÇÃO FUTURA (P0 - Dezembro 2025)
        
        Args:
            termo_busca: Termo para filtrar
            ano: Ano específico (default: 2025)
            apenas_saude: Se True, filtra apenas órgãos/objetos de saúde
            apenas_futuras: Se True, prioriza processos ABERTOS/FUTUROS
            limit: Número máximo de resultados
            
        Returns:
            Lista de dicionários com dados das licitações
        """
        resultados = []
        
        if ano is None:
            ano = 2025
        
        try:
            modo = "FUTUROS/ABERTOS" if apenas_futuras else "geral"
            logger.info(f"🔍 [ES] Iniciando importação CSV ({modo}): '{termo_busca or 'geral'}' - Ano: {ano}")
            
            download_url = self.download_urls.get(ano)
            if not download_url:
                logger.warning(f"  ⚠️ Ano {ano} não disponível")
                return []
            
            logger.info(f"  📥 Baixando CSV de {ano}...")
            csv_content = await self._baixar_csv(download_url)
            
            if not csv_content:
                logger.warning("  ⚠️ Falha no download do CSV")
                return []
            
            logger.info(f"  ✅ CSV baixado ({len(csv_content)/1024:.1f} KB)")
            
            # Processar CSV com filtro de prospecção
            resultados = self._processar_csv(
                csv_content,
                termo_busca=termo_busca,
                apenas_saude=apenas_saude,
                apenas_futuras=apenas_futuras,
                limit=limit
            )
            
            logger.info(f"🎯 [ES] Total processado: {len(resultados)} licitações")
            return resultados
            
        except Exception as e:
            logger.error(f"❌ [ES] Erro geral: {str(e)}")
            import traceback
            logger.debug(traceback.format_exc())
            return []
    
    async def _baixar_csv(self, url: str) -> Optional[str]:
        """Baixa o CSV"""
        try:
            response = requests.get(
                url,
                headers=self.headers,
                timeout=120
            )
            
            if response.status_code == 200:
                return response.text
            else:
                logger.warning(f"  ⚠️ HTTP {response.status_code}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error("  ❌ Timeout ao baixar CSV")
            return None
        except Exception as e:
            logger.error(f"  ❌ Erro: {str(e)}")
            return None
    
    def _processar_csv(
        self,
        csv_content: str,
        termo_busca: str = None,
        apenas_saude: bool = True,
        apenas_futuras: bool = False,
        limit: int = 50
    ) -> List[Dict]:
        """
        Processa o conteúdo CSV e retorna lista de licitações
        OTIMIZADO PARA PROSPECÇÃO FUTURA (P0)
        
        Filtros de prospecção (quando apenas_futuras=True):
        - Situação: 'Em andamento', 'Aberto' (não encerrado/cancelado)
        - Data de abertura: >= hoje (se disponível)
        """
        licitacoes = []
        licitacoes_unicas = set()
        hoje = datetime.now()
        
        # Contadores para log
        total_processados = 0
        filtrados_status = 0
        filtrados_data = 0
        
        try:
            # Detectar delimitador
            first_line = csv_content.split('\n')[0]
            delimiter = ';' if first_line.count(';') > first_line.count(',') else ','
            
            # Parse CSV
            reader = csv.DictReader(StringIO(csv_content), delimiter=delimiter)
            
            for row in reader:
                if len(licitacoes) >= limit:
                    break
                
                total_processados += 1
                
                try:
                    # Limpar campos (remover BOM)
                    row = {k.strip().strip('\ufeff'): v.strip() if v else '' 
                           for k, v in row.items() if k}
                    
                    # Extrair campos
                    id_licitacao = row.get('IdLicitacao', '')
                    nome_orgao = row.get('NomeOrgao', '')
                    modalidade = row.get('Modalidade', '')
                    numero_processo = row.get('NumeroProcesso', '')
                    data_criacao = row.get('DataCriacao', '')
                    data_abertura = row.get('DataAbertura', '')
                    objeto = row.get('Objeto', '')
                    registro_preco = row.get('RegistroPreco', '')
                    situacao = row.get('Situacao', '')
                    tipo_licitacao = row.get('TipoLicitacao', '')
                    justificativa = row.get('Justificativa', '')
                    
                    # ===============================================
                    # FILTRO DE PROSPECÇÃO (P0 - Processos Futuros)
                    # ===============================================
                    if apenas_futuras:
                        # 1. Filtrar por STATUS: apenas processos ABERTOS/EM ANDAMENTO
                        situacao_lower = situacao.lower() if situacao else ''
                        if any(s in situacao_lower for s in ['encerrad', 'cancelad', 'revogad', 'anulad', 'homolog', 'concluíd', 'concluido']):
                            filtrados_status += 1
                            continue
                        
                        # 2. Filtrar por DATA: priorizar datas futuras ou recentes
                        dt_abertura = self._parse_date(data_abertura)
                        if dt_abertura:
                            # Se a data de abertura já passou há mais de 30 dias, pular
                            if dt_abertura < (hoje - timedelta(days=30)):
                                filtrados_data += 1
                                continue
                    
                    # Criar chave única
                    chave_unica = f"es_{id_licitacao}"
                    if chave_unica in licitacoes_unicas:
                        continue
                    
                    # Filtrar por saúde
                    if apenas_saude:
                        texto_orgao = nome_orgao.upper()
                        texto_objeto = f"{objeto} {justificativa}".upper()
                        
                        is_saude_orgao = any(org in texto_orgao for org in self.orgaos_saude)
                        is_saude_objeto = any(kw.upper() in texto_objeto for kw in self.keywords_saude)
                        
                        if not (is_saude_orgao or is_saude_objeto):
                            continue
                    
                    # Filtrar por termo
                    if termo_busca:
                        termo_lower = termo_busca.lower()
                        texto_completo = f"{objeto} {nome_orgao} {justificativa}".lower()
                        if termo_lower not in texto_completo:
                            continue
                    
                    # Adicionar à lista de únicos
                    licitacoes_unicas.add(chave_unica)
                    
                    # Determinar status com lógica de prospecção
                    dt_abertura_parsed = self._parse_date(data_abertura)
                    status_final = self._normalizar_status_prospeccao(situacao, dt_abertura_parsed, hoje)
                    
                    # Converter para formato padrão
                    resultado = {
                        'id': str(uuid.uuid4()),
                        'titulo_licitacao': objeto[:200] if objeto else 'Sem título',
                        'medicamento': self._extrair_medicamento(objeto),
                        'estado': self.estado,
                        'estado_uf': self.estado,
                        'orgao_licitante': nome_orgao[:200] if nome_orgao else 'Governo do ES',
                        'status': status_final,
                        'status_aquisicao': status_final,
                        'modalidade': self._normalizar_modalidade(modalidade),
                        'numero_processo': numero_processo or id_licitacao or 'N/A',
                        'data_referencia': datetime.now(),
                        'data_abertura': dt_abertura_parsed,
                        'data_inicial': self._parse_date(data_criacao),
                        'data_final': None,
                        'data_limite': dt_abertura_parsed,
                        'link_origem': self.dataset_url,
                        'link_documento': None,
                        'fonte_nome': self.fonte,
                        'fonte_id': f'es-{id_licitacao}',
                        'numero_pregao': numero_processo,
                        'uasg': None,
                        'esfera': 'Estadual',
                        'objeto': objeto[:500] if objeto else '',
                        'registro_preco': registro_preco == 'True',
                        'tipo_licitacao': tipo_licitacao,
                        'itens': [],
                        'tags': self._extrair_tags(objeto, nome_orgao),
                        'is_mock': False,
                        'fonte': 'ES-CSV'
                    }
                    
                    licitacoes.append(resultado)
                        
                except Exception as e:
                    continue
            
            if apenas_futuras:
                logger.info(f"  📊 Prospecção: {total_processados} total, {filtrados_status} filtrados por status, {filtrados_data} filtrados por data")
            
            return licitacoes
            
        except Exception as e:
            logger.error(f"  ❌ Erro ao processar CSV: {str(e)}")
            return []
    
    def _normalizar_status_prospeccao(self, situacao: str, data_abertura: Optional[datetime], hoje: datetime) -> str:
        """
        Normaliza status com foco em PROSPECÇÃO
        
        Prioridade:
        1. Se data_abertura > hoje: 'Agendado'
        2. Se situação indica aberto/andamento: 'Aberto' ou 'Em Andamento'
        3. Fallback para normalização padrão
        """
        # PRIORIDADE 1: Data futura = Agendado
        if data_abertura and data_abertura > hoje:
            return 'Agendado'
        
        # PRIORIDADE 2: Usar situação normalizada
        return self._normalizar_status(situacao)
    
    def _normalizar_modalidade(self, modalidade: str) -> str:
        """Normaliza a modalidade"""
        if not modalidade:
            return 'Não informado'
        
        modalidade_lower = modalidade.lower().strip()
        
        for key, value in self.modalidade_map.items():
            if key in modalidade_lower:
                return value
        
        return modalidade[:50]
    
    def _normalizar_status(self, situacao: str) -> str:
        """Normaliza o status"""
        if not situacao:
            return 'Em Licitação'
        
        situacao_lower = situacao.lower().strip()
        
        if 'encerrad' in situacao_lower:
            return 'Encerrado'
        elif 'andamento' in situacao_lower:
            return 'Em Andamento'
        elif 'aberto' in situacao_lower:
            return 'Aberto'
        elif 'cancelad' in situacao_lower:
            return 'Cancelado'
        elif 'suspen' in situacao_lower:
            return 'Suspenso'
        elif 'homolog' in situacao_lower:
            return 'Homologado'
        elif 'adjudic' in situacao_lower:
            return 'Adjudicado'
        
        return 'Em Licitação'
    
    def _extrair_medicamento(self, texto: str) -> str:
        """Extrai nome do medicamento"""
        if not texto:
            return 'Não especificado'
        
        texto_lower = texto.lower()
        medicamentos = [
            'semaglutida', 'insulina', 'canabidiol', 'adalimumabe',
            'metformina', 'omeprazol', 'paracetamol', 'dipirona',
            'amoxicilina', 'azitromicina', 'losartana', 'atenolol'
        ]
        
        for med in medicamentos:
            if med in texto_lower:
                return med.capitalize()
        
        if any(kw in texto_lower for kw in ['medicamento', 'fármaco', 'hospitalar']):
            return 'Medicamento (ver objeto)'
        
        return 'Não especificado'
    
    def _extrair_tags(self, objeto: str, orgao: str) -> List[str]:
        """Extrai tags relevantes"""
        tags = []
        texto = f"{objeto} {orgao}".lower()
        
        if 'hospitalar' in texto:
            tags.append('hospitalar')
        if 'saúde' in texto or 'saude' in texto or 'sesa' in texto:
            tags.append('saude')
        if 'medicamento' in texto:
            tags.append('medicamento')
        if 'registro de preço' in texto:
            tags.append('registro_precos')
        if 'urgente' in texto or 'emergência' in texto:
            tags.append('urgente')
        
        return tags
    
    def _parse_date(self, texto: str) -> Optional[datetime]:
        """Parse de data"""
        if not texto:
            return None
        
        # Formato: 15/07/2025 16:11:20
        formatos = [
            '%d/%m/%Y %H:%M:%S',
            '%d/%m/%Y %H:%M',
            '%d/%m/%Y',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d'
        ]
        
        for formato in formatos:
            try:
                return datetime.strptime(texto.strip(), formato)
            except:
                continue
        
        return None
    
    async def scrape(self, medicamento: str = None) -> List[Dict]:
        """Método de compatibilidade"""
        return await self.buscar_licitacoes(termo_busca=medicamento)
