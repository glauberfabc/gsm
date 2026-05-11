"""
Importador de Licitações - Mato Grosso do Sul (MS)

STATUS: PENDENTE - Portal SIGA MS requer autenticação

Fonte investigada: https://www.siga.ms.gov.br/licitacao/#/licitacoes
Resultado: Requer login (sistema fechado)

ALTERNATIVA ATIVA: PNCP API Oficial já cobre MS via endpoint nacional
Ver: /app/backend/scrapers/pncp_api_oficial.py

Portal de Compras MS: https://www.compras.ms.gov.br/
Portal Transparência MS: https://www.transparencia.ms.gov.br (instável)

Campos do CSV:
- _id: ID do registro
- N_Processo: Número do processo
- Orgao: Sigla do órgão (SES = Saúde)
- Situacao_Orgao: Status do órgão
- Modalidade: Tipo de licitação
- Objeto: Descrição do objeto
- Itens_Licitado: Detalhes dos itens
- Valor_Total_Previsto: Valor previsto
- Valor_Total_Realizado: Valor realizado
- N_Edital: Número do edital
- Data_Publicação: Data de publicação
- Data_Abertura: Data de abertura
- CPF_CNPJ: CNPJ do fornecedor
- Razao_Social: Nome do fornecedor

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


class MatoGrossoSulCsvImporter:
    """
    Importador de licitações do Mato Grosso do Sul via CSV do Portal de Dados Abertos
    
    Portal: https://www.dados.ms.gov.br/dataset/compras
    Método: Download CSV mensal
    Atualização: Diária
    Cobertura: Todos os órgãos do Estado do MS
    """
    
    def __init__(self):
        self.base_url = 'https://www.dados.ms.gov.br'
        self.dataset_url = f'{self.base_url}/dataset/compras'
        
        # URL base para download (formato: compras-{MM}_{YYYY})
        self.download_base = f'{self.base_url}/datastore/dump/compras'
        
        self.estado = 'MS'
        self.fonte = 'Dados Abertos MS'
        
        # Headers para requisição
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # Órgãos de saúde (siglas)
        self.orgaos_saude = [
            'SES', 'FUNSAU', 'HRMS', 'HU', 'LACEN', 'HEMOSUL',
            'AGEPEN', 'FUNRESPMS'
        ]
        
        # Keywords de saúde para filtrar objetos
        self.keywords_saude = [
            'medicamento', 'fármaco', 'farmac', 'hospitalar', 'saúde', 'saude',
            'médico', 'medico', 'insumo', 'cirurg', 'laborat', 'diagnóstic',
            'vacina', 'seringa', 'agulha', 'luva', 'mascara', 'máscara'
        ]
    
    def _get_download_url(self, ano: int, mes: int) -> str:
        """Gera URL de download para ano/mês específico"""
        return f'{self.download_base}-{mes:02d}_{ano}'
    
    def _get_available_months(self, ano: int) -> List[int]:
        """Retorna meses disponíveis para o ano"""
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        if ano < 2018:
            return []
        elif ano == current_year:
            return list(range(1, current_month + 1))
        elif ano <= 2025:
            return list(range(1, 13))
        return []
    
    async def buscar_licitacoes(
        self,
        termo_busca: str = None,
        ano: int = None,
        mes: int = None,
        apenas_saude: bool = True,
        limit: int = 50
    ) -> List[Dict]:
        """
        Busca licitações do Mato Grosso do Sul via CSV
        
        Args:
            termo_busca: Termo para filtrar
            ano: Ano específico (default: ano atual)
            mes: Mês específico (default: último disponível)
            apenas_saude: Se True, filtra apenas órgãos/objetos de saúde
            limit: Número máximo de resultados
            
        Returns:
            Lista de dicionários com dados das licitações
        """
        resultados = []
        
        if ano is None:
            ano = datetime.now().year
        
        if mes is None:
            meses = self._get_available_months(ano)
            mes = meses[-1] if meses else 11
        
        try:
            logger.info(f"🔍 [MS] Iniciando importação CSV: '{termo_busca or 'geral'}' - {mes:02d}/{ano}")
            
            download_url = self._get_download_url(ano, mes)
            logger.info(f"  📥 Baixando CSV de {mes:02d}/{ano}...")
            
            csv_content = await self._baixar_csv(download_url)
            
            if not csv_content:
                # Tentar mês anterior
                mes = mes - 1 if mes > 1 else 12
                ano = ano if mes > 1 else ano - 1
                download_url = self._get_download_url(ano, mes)
                logger.info(f"  📥 Tentando {mes:02d}/{ano}...")
                csv_content = await self._baixar_csv(download_url)
            
            if not csv_content:
                logger.warning("  ⚠️ Falha no download do CSV")
                return []
            
            logger.info(f"  ✅ CSV baixado ({len(csv_content)/1024:.1f} KB)")
            
            # Processar CSV
            resultados = self._processar_csv(
                csv_content,
                termo_busca=termo_busca,
                apenas_saude=apenas_saude,
                limit=limit
            )
            
            logger.info(f"🎯 [MS] Total processado: {len(resultados)} licitações")
            return resultados
            
        except Exception as e:
            logger.error(f"❌ [MS] Erro geral: {str(e)}")
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
        limit: int = 50
    ) -> List[Dict]:
        """Processa o conteúdo CSV e retorna lista de licitações"""
        licitacoes = []
        licitacoes_unicas = set()
        
        try:
            # Parse CSV
            reader = csv.DictReader(StringIO(csv_content))
            
            for row in reader:
                if len(licitacoes) >= limit:
                    break
                
                try:
                    # Extrair campos
                    id_registro = row.get('_id', '')
                    n_processo = row.get('N_Processo', '')
                    orgao = row.get('Orgao', '')
                    modalidade = row.get('Modalidade', '')
                    objeto = row.get('Objeto', '')
                    itens = row.get('Itens_Licitado', '')
                    valor_previsto = row.get('Valor_Total_Previsto', '')
                    valor_realizado = row.get('Valor_Total_Realizado', '')
                    n_edital = row.get('N_Edital', '')
                    data_publicacao = row.get('Data_Publicação', '')
                    cnpj_fornecedor = row.get('CPF_CNPJ', '')
                    razao_social = row.get('Razao_Social', '')
                    
                    # Criar chave única
                    chave_unica = f"ms_{n_processo}_{id_registro}"
                    if chave_unica in licitacoes_unicas:
                        continue
                    
                    # Filtrar por saúde
                    if apenas_saude:
                        texto_orgao = orgao.upper()
                        texto_objeto = f"{objeto} {itens}".upper()
                        
                        is_saude_orgao = any(org in texto_orgao for org in self.orgaos_saude)
                        is_saude_objeto = any(kw.upper() in texto_objeto for kw in self.keywords_saude)
                        
                        if not (is_saude_orgao or is_saude_objeto):
                            continue
                    
                    # Filtrar por termo
                    if termo_busca:
                        termo_lower = termo_busca.lower()
                        texto_completo = f"{objeto} {itens} {orgao}".lower()
                        if termo_lower not in texto_completo:
                            continue
                    
                    # Adicionar à lista de únicos
                    licitacoes_unicas.add(chave_unica)
                    
                    # Converter para formato padrão
                    resultado = {
                        'id': str(uuid.uuid4()),
                        'titulo_licitacao': objeto[:200] if objeto else 'Sem título',
                        'medicamento': self._extrair_medicamento(f"{objeto} {itens}"),
                        'estado': self.estado,
                        'estado_uf': self.estado,
                        'orgao_licitante': orgao[:200] if orgao else 'Governo do MS',
                        'status': 'Encerrado',  # Dados são de compras encerradas
                        'status_aquisicao': 'Encerrado',
                        'modalidade': modalidade if modalidade else 'Não informado',
                        'numero_processo': n_processo or id_registro or 'N/A',
                        'data_referencia': datetime.now(),
                        'data_abertura': self._parse_date(data_publicacao),
                        'data_inicial': self._parse_date(data_publicacao),
                        'data_final': None,
                        'data_limite': None,
                        'link_origem': self.dataset_url,
                        'link_documento': None,
                        'fonte_nome': self.fonte,
                        'fonte_id': f'ms-{n_processo}-{id_registro}',
                        'numero_pregao': n_edital,
                        'uasg': None,
                        'esfera': 'Estadual',
                        'objeto': objeto[:500] if objeto else '',
                        'valor_previsto': self._parse_valor(valor_previsto),
                        'valor_realizado': self._parse_valor(valor_realizado),
                        'fornecedor': razao_social,
                        'cnpj_fornecedor': cnpj_fornecedor,
                        'itens': [],
                        'tags': self._extrair_tags(f"{objeto} {itens}", orgao),
                        'is_mock': False,
                        'fonte': 'MS-CSV'
                    }
                    
                    licitacoes.append(resultado)
                        
                except Exception as e:
                    continue
            
            return licitacoes
            
        except Exception as e:
            logger.error(f"  ❌ Erro ao processar CSV: {str(e)}")
            return []
    
    def _extrair_medicamento(self, texto: str) -> str:
        """Extrai nome do medicamento"""
        if not texto:
            return 'Não especificado'
        
        texto_lower = texto.lower()
        medicamentos = [
            'insulina', 'metformina', 'omeprazol', 'paracetamol', 'dipirona',
            'amoxicilina', 'azitromicina', 'losartana', 'atenolol', 'ibuprofeno'
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
        if 'saúde' in texto or 'saude' in texto or 'ses' in texto:
            tags.append('saude')
        if 'medicamento' in texto:
            tags.append('medicamento')
        
        return tags
    
    def _parse_date(self, texto: str) -> Optional[datetime]:
        """Parse de data"""
        if not texto:
            return None
        
        try:
            # Formato: YYYYMMDD
            if len(texto) == 8 and texto.isdigit():
                return datetime.strptime(texto, '%Y%m%d')
            # Formato: DD/MM/YYYY
            elif '/' in texto:
                return datetime.strptime(texto[:10], '%d/%m/%Y')
        except:
            pass
        
        return None
    
    def _parse_valor(self, texto: str) -> Optional[float]:
        """Parse de valor (formato brasileiro)"""
        if not texto:
            return None
        
        try:
            # Remove espaços e substitui vírgula por ponto
            valor_limpo = texto.strip().replace(',', '.')
            # Remove zeros à direita extras
            return float(valor_limpo)
        except:
            return None
    
    async def scrape(self, medicamento: str = None) -> List[Dict]:
        """Método de compatibilidade"""
        return await self.buscar_licitacoes(termo_busca=medicamento)
