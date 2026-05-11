"""
Importador de Licitações de Goiás via CSV do Portal de Dados Abertos

FONTE: https://dadosabertos.go.gov.br/dataset/licitacoes-andamento
MÉTODO: Download de CSV mensal (arquivos desde 2008)

Vantagens:
- Sem CAPTCHA ou autenticação
- Dados de TODOS os órgãos estaduais de GO
- Histórico desde 2008 (17 anos!)
- Atualização mensal
- Arquivos leves (poucos KB por mês)

Campos do CSV:
- CODORGAO: Código do órgão
- ANOMES: Ano/Mês (AAAAMM)
- MODALIDADELICITACAO: Tipo de licitação
- DATASOLICITACAOAQUISICAO: Data da solicitação
- CODSOLICITACAOAQUISICAO: Código da solicitação
- NUMPROCESSO: Número do processo
- VALORAUTORIZADO: Valor autorizado
- SIGLAORGAO: Sigla do órgão (SES = Saúde)
- NUMEROEDITAL: Número do edital

Criado: Dezembro 2025
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


class GoiasCsvImporter:
    """
    Importador de licitações de Goiás via CSV do Portal de Dados Abertos
    
    Portal: https://dadosabertos.go.gov.br/dataset/licitacoes-andamento
    Método: Download CSV mensal
    Atualização: Mensal
    Cobertura: Todos os órgãos do Estado de GO
    """
    
    def __init__(self):
        self.base_url = 'https://dadosabertos.go.gov.br'
        self.dataset_url = f'{self.base_url}/dataset/licitacoes-andamento'
        
        # URL base para download de CSVs mensais
        self.download_base = f'{self.base_url}/dataset/f83e076e-5498-45fb-a26e-67b902296c16/resource'
        
        # Mapeamento de resource IDs por mês (2025)
        self.resource_ids_2025 = {
            '202510': '8eb056e8-c1f0-4591-9049-3c3a261c0dc0',
            '202509': '952e6843-81e7-4955-9fdc-59826468c938',
            '202508': 'ccfb40ea-342b-4bbb-a445-3fc2e7f44660',
            '202507': '7768cc7d-2224-4220-964a-eae91b2c4080',
            '202506': 'edf66d0c-8036-46cf-9169-7a6ed363e764',
            '202505': 'b8a0f0d5-2a39-4a3e-8a65-10a54cbd31db',
            '202504': '28675e6b-6c95-4eb7-bef3-b93b18d98489',
            '202503': 'c310c258-48f7-4f61-a2e7-caecdee9711e',
            '202502': 'd434cf73-5733-479e-9a12-e779774c17a2',
            '202501': 'f4c5c2f3-d14e-4e5c-a3df-dc8439ec8824'
        }
        
        self.estado = 'GO'
        self.fonte = 'Dados Abertos GO'
        
        # Headers para requisição
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # Mapeamento de modalidades
        self.modalidade_map = {
            'pregao eletronico': 'Pregão Eletrônico',
            'pregao presencial': 'Pregão Presencial',
            'aditivo contratual': 'Aditivo Contratual',
            'participante registro': 'Registro de Preços',
            'outras dispensas': 'Dispensa de Licitação',
            'dispensa': 'Dispensa de Licitação',
            'inexigibilidade': 'Inexigibilidade',
            'concorrencia': 'Concorrência',
            'tomada de precos': 'Tomada de Preços',
            'convite': 'Convite',
            'credenciamento': 'Credenciamento'
        }
        
        # Órgãos de saúde (siglas)
        self.orgaos_saude = ['SES', 'HGG', 'HUGO', 'HUGOL', 'HMI', 'CRER', 'LACEN']
    
    def _get_download_url(self, ano_mes: str) -> Optional[str]:
        """Gera URL de download para ano/mês específico"""
        if ano_mes in self.resource_ids_2025:
            resource_id = self.resource_ids_2025[ano_mes]
            return f'{self.download_base}/{resource_id}/download/licitacoesandamento_{ano_mes}.csv'
        return None
    
    def _get_available_months(self) -> List[str]:
        """Retorna meses disponíveis (2025)"""
        return list(self.resource_ids_2025.keys())
    
    async def buscar_licitacoes(
        self,
        termo_busca: str = None,
        ano_mes: str = None,
        apenas_saude: bool = True,
        apenas_futuras: bool = False,
        limit: int = 50
    ) -> List[Dict]:
        """
        Busca licitações de Goiás via CSV do Portal de Dados Abertos
        OTIMIZADO PARA PROSPECÇÃO FUTURA (P0 - Dezembro 2025)
        
        Args:
            termo_busca: Termo para filtrar
            ano_mes: Ano/Mês específico (formato AAAAMM, ex: '202510')
            apenas_saude: Se True, filtra apenas órgãos de saúde
            apenas_futuras: Se True, prioriza processos ABERTOS/FUTUROS
            limit: Número máximo de resultados
            
        Returns:
            Lista de dicionários com dados das licitações
        """
        resultados = []
        
        # Se não especificou mês, busca os últimos 3 meses
        if ano_mes is None:
            meses = self._get_available_months()[:3]  # Últimos 3 meses
        else:
            meses = [ano_mes]
        
        try:
            modo = "FUTUROS/ABERTOS" if apenas_futuras else "geral"
            logger.info(f"🔍 [GO] Iniciando importação CSV ({modo}): '{termo_busca or 'geral'}' - Meses: {meses}")
            
            for mes in meses:
                if len(resultados) >= limit:
                    break
                    
                download_url = self._get_download_url(mes)
                if not download_url:
                    continue
                
                logger.info(f"  📥 Baixando CSV de {mes}...")
                csv_content = await self._baixar_csv(download_url)
                
                if not csv_content:
                    continue
                
                # Processar CSV com filtro de prospecção
                licitacoes = self._processar_csv(
                    csv_content,
                    termo_busca=termo_busca,
                    apenas_saude=apenas_saude,
                    apenas_futuras=apenas_futuras,
                    limit=limit - len(resultados)
                )
                
                logger.info(f"  ✅ {mes}: {len(licitacoes)} licitações")
                resultados.extend(licitacoes)
            
            logger.info(f"🎯 [GO] Total processado: {len(resultados)} licitações")
            return resultados
            
        except Exception as e:
            logger.error(f"❌ [GO] Erro geral: {str(e)}")
            import traceback
            logger.debug(traceback.format_exc())
            return []
    
    async def _baixar_csv(self, url: str) -> Optional[str]:
        """Baixa o CSV"""
        try:
            response = requests.get(
                url,
                headers=self.headers,
                timeout=60
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
        """
        licitacoes = []
        licitacoes_unicas = set()
        hoje = datetime.now()
        
        # Contadores para log
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
                
                try:
                    # Limpar campos
                    row = {k.strip().strip('\ufeff'): v.strip() if v else '' 
                           for k, v in row.items() if k}
                    
                    # Extrair campos
                    cod_orgao = row.get('CODORGAO', '')
                    sigla_orgao = row.get('SIGLAORGAO', '')
                    modalidade = row.get('MODALIDADELICITACAO', '')
                    data_solicitacao = row.get('DATASOLICITACAOAQUISICAO', '')
                    cod_solicitacao = row.get('CODSOLICITACAOAQUISICAO', '')
                    num_processo = row.get('NUMPROCESSO', '')
                    valor = row.get('VALORAUTORIZADO', '')
                    num_edital = row.get('NUMEROEDITAL', '')
                    ano_mes = row.get('ANOMES', '')
                    
                    # ===============================================
                    # FILTRO DE PROSPECÇÃO (P0 - Processos Futuros)
                    # ===============================================
                    if apenas_futuras:
                        # Filtrar por DATA: processos recentes (últimos 60 dias)
                        dt_solicitacao = self._parse_date(data_solicitacao)
                        if dt_solicitacao:
                            from datetime import timedelta
                            if dt_solicitacao < (hoje - timedelta(days=60)):
                                filtrados_data += 1
                                continue
                    
                    # Criar chave única
                    chave_unica = f"go_{cod_solicitacao}_{num_processo}"
                    if chave_unica in licitacoes_unicas:
                        continue
                    
                    # Filtrar por saúde (por sigla do órgão)
                    if apenas_saude:
                        if sigla_orgao not in self.orgaos_saude:
                            continue
                    
                    # Filtrar por termo
                    if termo_busca:
                        termo_lower = termo_busca.lower()
                        texto_completo = f"{modalidade} {sigla_orgao}".lower()
                        if termo_lower not in texto_completo:
                            continue
                    
                    # Adicionar à lista de únicos
                    licitacoes_unicas.add(chave_unica)
                    
                    # Converter para formato padrão
                    resultado = self._converter_para_formato_padrao(
                        cod_orgao=cod_orgao,
                        sigla_orgao=sigla_orgao,
                        modalidade=modalidade,
                        data_solicitacao=data_solicitacao,
                        cod_solicitacao=cod_solicitacao,
                        num_processo=num_processo,
                        valor=valor,
                        num_edital=num_edital,
                        ano_mes=ano_mes
                    )
                    
                    if resultado:
                        licitacoes.append(resultado)
                        
                except Exception as e:
                    continue
            
            if apenas_futuras:
                logger.info(f"  📊 Prospecção GO: {filtrados_data} filtrados por data")
            
            return licitacoes
            
        except Exception as e:
            logger.error(f"  ❌ Erro ao processar CSV: {str(e)}")
            return []
    
    def _converter_para_formato_padrao(
        self,
        cod_orgao: str,
        sigla_orgao: str,
        modalidade: str,
        data_solicitacao: str,
        cod_solicitacao: str,
        num_processo: str,
        valor: str,
        num_edital: str,
        ano_mes: str
    ) -> Optional[Dict]:
        """Converte para formato padrão do sistema"""
        try:
            # Determinar nome do órgão
            orgao_nomes = {
                'SES': 'Secretaria de Estado da Saúde',
                'HGG': 'Hospital Geral de Goiânia',
                'HUGO': 'Hospital de Urgências de Goiânia',
                'HUGOL': 'Hospital de Urgências do Oeste',
                'HMI': 'Hospital Materno Infantil',
                'CRER': 'Centro de Reabilitação e Readaptação',
                'LACEN': 'Laboratório Central de Saúde',
                'GOINFRA': 'Agência Goiana de Infraestrutura',
                'CBMGO': 'Corpo de Bombeiros Militar de GO',
                'SGG': 'Secretaria de Governo'
            }
            
            nome_orgao = orgao_nomes.get(sigla_orgao, f'Órgão {sigla_orgao}')
            
            # Título da licitação
            titulo = f"{self._normalizar_modalidade(modalidade)} - {nome_orgao}"
            
            return {
                'id': str(uuid.uuid4()),
                'titulo_licitacao': titulo[:200],
                'medicamento': 'Não especificado' if sigla_orgao in self.orgaos_saude else 'N/A',
                'estado': self.estado,
                'estado_uf': self.estado,
                'orgao_licitante': nome_orgao[:200],
                'status': 'Em Andamento',
                'status_aquisicao': 'Em Andamento',
                'modalidade': self._normalizar_modalidade(modalidade),
                'numero_processo': num_processo or cod_solicitacao or 'N/A',
                'data_referencia': datetime.now(),
                'data_abertura': self._parse_date(data_solicitacao),
                'data_inicial': self._parse_date(data_solicitacao),
                'data_final': None,
                'data_limite': None,
                'link_origem': self.dataset_url,
                'link_documento': None,
                'fonte_nome': self.fonte,
                'fonte_id': f'go-{cod_solicitacao}',
                'numero_pregao': num_edital if num_edital != 'Não se aplica' else None,
                'uasg': None,
                'esfera': 'Estadual',
                'objeto': titulo,
                'valor_autorizado': self._parse_valor(valor),
                'sigla_orgao': sigla_orgao,
                'itens': [],
                'tags': ['saude'] if sigla_orgao in self.orgaos_saude else [],
                'is_mock': False,
                'fonte': 'GO-CSV'
            }
            
        except Exception as e:
            logger.error(f"  ❌ Erro ao converter: {str(e)}")
            return None
    
    def _normalizar_modalidade(self, modalidade: str) -> str:
        """Normaliza a modalidade"""
        if not modalidade:
            return 'Não informado'
        
        modalidade_lower = modalidade.lower().strip()
        
        for key, value in self.modalidade_map.items():
            if key in modalidade_lower:
                return value
        
        return modalidade[:50]
    
    def _parse_date(self, texto: str) -> Optional[datetime]:
        """Parse de data ISO"""
        if not texto:
            return None
        
        try:
            # Formato: 2025-10-14T00:00:00.000-03:00
            texto_limpo = texto.split('T')[0]
            return datetime.strptime(texto_limpo, '%Y-%m-%d')
        except:
            return None
    
    def _parse_valor(self, texto: str) -> Optional[float]:
        """Parse de valor"""
        if not texto or texto == '0':
            return None
        
        try:
            valor_limpo = re.sub(r'[^\d,.]', '', str(texto).strip())
            
            if ',' in valor_limpo and '.' in valor_limpo:
                valor_limpo = valor_limpo.replace('.', '').replace(',', '.')
            elif ',' in valor_limpo:
                valor_limpo = valor_limpo.replace(',', '.')
            
            return float(valor_limpo) if valor_limpo else None
        except:
            return None
    
    async def scrape(self, medicamento: str = None) -> List[Dict]:
        """Método de compatibilidade"""
        return await self.buscar_licitacoes(termo_busca=medicamento)
