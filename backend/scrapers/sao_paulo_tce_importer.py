"""
Importador de Licitações de São Paulo via CSV do Portal TCE-SP

FONTE: https://www.transparencia.tce.sp.gov.br/conjunto-de-dados
MÉTODO: Download de CSV mensal (arquivos ZIP por mês desde 2018)

OTIMIZAÇÃO DE MEMÓRIA: Implementa processamento em blocos (chunking)
para evitar estouro de memória com arquivos grandes (25-50MB por mês).

Vantagens:
- Sem CAPTCHA ou autenticação (alternativa ao BEC/SP bloqueado)
- Dados de TODOS os municípios paulistas (~645 municípios)
- Histórico desde Janeiro/2018 (7 anos!)
- Atualização esporádica pelo TCE-SP
- Dados granulares por item licitado

Campos do CSV:
- Município: Nome do município
- Entidade: Órgão/entidade licitante
- Código da Licitação: ID único
- Modalidade de licitação: Tipo de licitação
- Objeto: Categoria geral
- Descrição do objeto contratado: Descrição detalhada
- Produto (item): Nome do produto/serviço
- Número do edital: Número do edital
- Data do edital: Data de publicação

Criado: Dezembro 2025
"""

from typing import List, Dict, Optional, Generator
from datetime import datetime
from io import StringIO, BytesIO
import logging
import zipfile
import requests
import uuid
import csv
import re

logger = logging.getLogger(__name__)

# Configuração de chunking para economia de memória
CHUNK_SIZE = 5000  # Processar 5.000 registros por vez


class SaoPauloTceCsvImporter:
    """
    Importador de licitações de São Paulo via CSV do Portal TCE-SP
    
    Portal: https://www.transparencia.tce.sp.gov.br/conjunto-de-dados
    Método: Download CSV mensal (ZIP) com processamento em chunks
    Atualização: Esporádica (última: Jul/2025)
    Cobertura: Todos os municípios do Estado de SP
    """
    
    def __init__(self):
        self.base_url = 'https://www.transparencia.tce.sp.gov.br'
        self.dataset_url = f'{self.base_url}/conjunto-de-dados'
        
        # URLs de download por mês
        self.download_base = f'{self.base_url}/sites/default/files/conjunto-dados/licitacoes-contratos'
        
        self.estado = 'SP'
        self.fonte = 'Portal TCE-SP (Transparência Municipal)'
        
        # Headers para requisição
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # Mapeamento de modalidades
        self.modalidade_map = {
            'pregao eletronico': 'Pregão Eletrônico',
            'pregao presencial': 'Pregão Presencial',
            'concorrencia': 'Concorrência',
            'dispensa': 'Dispensa de Licitação',
            'contratacao direta': 'Contratação Direta',
            'inexigibilidade': 'Inexigibilidade',
            'credenciamento': 'Credenciamento'
        }
        
        # Órgãos de saúde prioritários
        self.orgaos_saude = [
            'SAÚDE', 'SAUDE', 'HOSPITAL', 'UBS', 'UPA', 'SAMU',
            'FARMÁCIA', 'FARMACIA', 'MEDICAMENT', 'FUNDO MUNICIPAL DE SAÚDE',
            'VIGILÂNCIA', 'VIGILANCIA', 'SANITÁRIA', 'SANITARIA',
            'PRONTO SOCORRO', 'SECRETARIA DE SAÚDE', 'SMS'
        ]
        
        # Keywords de saúde para filtrar objetos
        self.keywords_saude = [
            'medicamento', 'fármaco', 'farmac', 'hospitalar', 'saúde', 'saude',
            'médico', 'medico', 'insumo', 'cirurg', 'laborat', 'diagnóstic',
            'vacina', 'seringa', 'agulha', 'luva', 'mascara', 'máscara'
        ]
    
    def _get_download_url(self, ano: int, mes: int) -> str:
        """Gera URL de download para ano/mês específico"""
        return f'{self.download_base}/licitacao-{ano}-{mes:02d}_0.zip'
    
    def _get_available_months(self, ano: int) -> List[int]:
        """Retorna meses disponíveis para o ano"""
        if ano < 2018:
            return []
        elif ano == 2024:
            return list(range(1, 13))  # Todos os meses
        elif ano == 2023:
            return list(range(1, 13))
        elif ano >= 2025:
            return []  # 2025 ainda não tem dados
        elif ano >= 2018:
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
        Busca licitações de São Paulo via CSV do Portal TCE-SP
        OTIMIZADO: Usa chunking para economia de memória
        
        Args:
            termo_busca: Termo para filtrar (ex: 'medicamento', 'insulina')
            ano: Ano específico (default: 2024)
            mes: Mês específico (default: último disponível)
            apenas_saude: Se True, filtra apenas órgãos/objetos de saúde
            limit: Número máximo de resultados
            
        Returns:
            Lista de dicionários com dados das licitações
        """
        resultados = []
        
        # Usar 2024 como padrão (último ano com dados completos)
        if ano is None:
            ano = 2024
        
        if mes is None:
            meses_disponiveis = self._get_available_months(ano)
            mes = meses_disponiveis[-1] if meses_disponiveis else 12
        
        try:
            logger.info(f"🔍 [SP-TCE] Iniciando importação com CHUNKING: '{termo_busca or 'geral'}' - {mes:02d}/{ano}")
            
            # ETAPA 1: Baixar o ZIP
            download_url = self._get_download_url(ano, mes)
            logger.info(f"  📥 Baixando ZIP ({mes:02d}/{ano})...")
            zip_content = await self._baixar_zip(download_url)
            
            if not zip_content:
                # Tentar mês anterior
                logger.warning(f"  ⚠️ Mês {mes:02d}/{ano} não disponível, tentando anterior...")
                mes = mes - 1 if mes > 1 else 12
                ano = ano if mes > 1 else ano - 1
                download_url = self._get_download_url(ano, mes)
                zip_content = await self._baixar_zip(download_url)
                
                if not zip_content:
                    logger.warning("  ⚠️ Falha no download do ZIP")
                    return []
            
            logger.info(f"  ✅ ZIP baixado ({len(zip_content)/1024/1024:.1f} MB)")
            
            # ETAPA 2: Processar CSV com CHUNKING
            logger.info(f"  📊 Processando CSV em chunks de {CHUNK_SIZE} registros...")
            
            chunk_index = 0
            for chunk_resultados in self._processar_csv_em_chunks(
                zip_content,
                termo_busca=termo_busca,
                apenas_saude=apenas_saude,
                limit=limit
            ):
                chunk_index += 1
                resultados.extend(chunk_resultados)
                logger.debug(f"    Chunk {chunk_index}: +{len(chunk_resultados)} resultados")
                
                # Parar se atingiu o limite
                if len(resultados) >= limit:
                    resultados = resultados[:limit]
                    break
            
            logger.info(f"🎯 [SP-TCE] Total processado: {len(resultados)} licitações")
            return resultados
            
        except Exception as e:
            logger.error(f"❌ [SP-TCE] Erro geral: {str(e)}")
            import traceback
            logger.debug(traceback.format_exc())
            return []
    
    async def _baixar_zip(self, url: str) -> Optional[bytes]:
        """Baixa o ZIP com streaming para economia de memória"""
        try:
            response = requests.get(
                url,
                headers=self.headers,
                verify=False,
                timeout=180,
                stream=True  # Streaming para economia de memória
            )
            
            if response.status_code == 200:
                # Ler em chunks para não sobrecarregar memória
                chunks = []
                for chunk in response.iter_content(chunk_size=1024*1024):  # 1MB por vez
                    chunks.append(chunk)
                return b''.join(chunks)
            elif response.status_code == 404:
                logger.warning(f"  ⚠️ Arquivo não encontrado: {url}")
                return None
            else:
                logger.error(f"  ❌ HTTP {response.status_code}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error("  ❌ Timeout ao baixar ZIP")
            return None
        except Exception as e:
            logger.error(f"  ❌ Erro: {str(e)}")
            return None
    
    def _processar_csv_em_chunks(
        self,
        zip_content: bytes,
        termo_busca: str = None,
        apenas_saude: bool = True,
        limit: int = 50
    ) -> Generator[List[Dict], None, None]:
        """
        PROCESSAMENTO EM CHUNKS: Gera resultados em blocos para economia de memória
        
        Yields:
            Lista de licitações processadas (um chunk por vez)
        """
        try:
            with zipfile.ZipFile(BytesIO(zip_content), 'r') as zf:
                # Encontrar CSV
                csv_file = None
                for name in zf.namelist():
                    if name.lower().endswith('.csv'):
                        csv_file = name
                        break
                
                if not csv_file:
                    logger.error("    ❌ CSV não encontrado no ZIP")
                    return
                
                # Abrir e processar em chunks
                with zf.open(csv_file) as f:
                    # Ler encoding
                    content_sample = f.read(10000)
                    f.seek(0)
                    
                    # Detectar encoding
                    encoding = 'utf-8'
                    for enc in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']:
                        try:
                            content_sample.decode(enc)
                            encoding = enc
                            break
                        except:
                            continue
                    
                    # Criar wrapper de texto
                    import io
                    text_wrapper = io.TextIOWrapper(f, encoding=encoding, errors='ignore')
                    
                    # Detectar delimitador
                    first_line = text_wrapper.readline()
                    text_wrapper.seek(0)
                    delimiter = ';' if first_line.count(';') > first_line.count(',') else ','
                    
                    # Processar em chunks
                    reader = csv.DictReader(text_wrapper, delimiter=delimiter)
                    
                    chunk_buffer = []
                    licitacoes_unicas = set()
                    total_processado = 0
                    
                    for row in reader:
                        if total_processado >= limit:
                            break
                        
                        try:
                            # Limpar campos
                            row = {k.strip().strip('"'): v.strip().strip('"') if v else '' 
                                   for k, v in row.items() if k}
                            
                            # Processar linha
                            resultado = self._processar_linha(
                                row, 
                                licitacoes_unicas,
                                termo_busca, 
                                apenas_saude
                            )
                            
                            if resultado:
                                chunk_buffer.append(resultado)
                                total_processado += 1
                                
                                # Yield chunk quando atingir o tamanho
                                if len(chunk_buffer) >= CHUNK_SIZE:
                                    yield chunk_buffer
                                    chunk_buffer = []  # Liberar memória
                                    
                        except Exception as e:
                            continue
                    
                    # Yield último chunk
                    if chunk_buffer:
                        yield chunk_buffer
                        
        except zipfile.BadZipFile:
            logger.error("    ❌ ZIP corrompido")
        except Exception as e:
            logger.error(f"    ❌ Erro: {str(e)}")
    
    def _processar_linha(
        self, 
        row: Dict, 
        licitacoes_unicas: set,
        termo_busca: str = None,
        apenas_saude: bool = True
    ) -> Optional[Dict]:
        """Processa uma linha do CSV e retorna no formato padrão"""
        
        # Extrair campos
        municipio = row.get('Município', row.get('Municipio', ''))
        entidade = row.get('Entidade', '')
        codigo_lic = row.get('Código da Licitação', row.get('Codigo da Licitacao', ''))
        modalidade = row.get('Modalidade de licitação', row.get('Modalidade de licitacao', ''))
        objeto = row.get('Objeto', '')
        descricao = row.get('Descrição do objeto contratado', row.get('Descricao do objeto contratado', ''))
        produto = row.get('Produto (item)', '')
        numero_edital = row.get('Número do edital', row.get('Numero do edital', ''))
        data_edital = row.get('Data do edital', '')
        
        # Criar chave única
        chave_unica = f"{municipio}_{codigo_lic}_{numero_edital}"
        if chave_unica in licitacoes_unicas:
            return None
        
        # Filtrar por saúde
        if apenas_saude:
            texto_entidade = entidade.upper()
            texto_objeto = f"{objeto} {descricao} {produto}".upper()
            
            is_saude_entidade = any(org in texto_entidade for org in self.orgaos_saude)
            is_saude_objeto = any(kw.upper() in texto_objeto for kw in self.keywords_saude)
            
            if not (is_saude_entidade or is_saude_objeto):
                return None
        
        # Filtrar por termo
        if termo_busca:
            termo_lower = termo_busca.lower()
            texto_completo = f"{objeto} {descricao} {produto} {entidade}".lower()
            if termo_lower not in texto_completo:
                return None
        
        # Adicionar à lista de únicos
        licitacoes_unicas.add(chave_unica)
        
        # Converter para formato padrão
        texto_objeto_full = f"{objeto} {descricao} {produto}".strip()
        
        return {
            'id': str(uuid.uuid4()),
            'titulo_licitacao': texto_objeto_full[:200] if texto_objeto_full else 'Sem título',
            'medicamento': self._extrair_medicamento(texto_objeto_full),
            'estado': self.estado,
            'estado_uf': self.estado,
            'orgao_licitante': entidade[:200] if entidade else f'Prefeitura de {municipio}',
            'status': 'Em Licitação',
            'status_aquisicao': 'Em Licitação',
            'modalidade': self._normalizar_modalidade(modalidade),
            'numero_processo': numero_edital or codigo_lic or 'N/A',
            'data_referencia': datetime.now(),
            'data_abertura': self._parse_date(data_edital),
            'data_inicial': self._parse_date(data_edital),
            'data_final': None,
            'data_limite': None,
            'link_origem': self.dataset_url,
            'link_documento': None,
            'fonte_nome': self.fonte,
            'fonte_id': f'sp-tce-{codigo_lic}'.replace('/', '-') if codigo_lic else str(uuid.uuid4()),
            'numero_pregao': numero_edital,
            'uasg': None,
            'esfera': 'Municipal',
            'objeto': texto_objeto_full[:500],
            'municipio': municipio,
            'itens': [],
            'tags': self._extrair_tags(texto_objeto_full),
            'is_mock': False,
            'fonte': 'SP-TCE'
        }
    
    def _normalizar_modalidade(self, modalidade: str) -> str:
        """Normaliza a modalidade"""
        if not modalidade:
            return 'Não informado'
        
        modalidade_lower = modalidade.lower().strip()
        
        for key, value in self.modalidade_map.items():
            if key in modalidade_lower:
                return value
        
        if 'dispensa' in modalidade_lower:
            return 'Dispensa de Licitação'
        elif 'pregão' in modalidade_lower or 'pregao' in modalidade_lower:
            return 'Pregão Eletrônico' if 'eletron' in modalidade_lower else 'Pregão'
        
        return modalidade[:50]
    
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
    
    def _extrair_tags(self, texto: str) -> List[str]:
        """Extrai tags relevantes"""
        if not texto:
            return []
        
        texto_lower = texto.lower()
        tags = []
        
        if 'hospitalar' in texto_lower:
            tags.append('hospitalar')
        if 'saúde' in texto_lower or 'saude' in texto_lower:
            tags.append('saude')
        if 'medicamento' in texto_lower:
            tags.append('medicamento')
        
        return tags
    
    def _parse_date(self, texto: str) -> Optional[datetime]:
        """Parse de data"""
        if not texto:
            return None
        
        texto_limpo = re.sub(r'[^\d/\-:\s]', '', texto).strip()
        
        formatos = ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d']
        
        for formato in formatos:
            try:
                return datetime.strptime(texto_limpo[:10], formato)
            except:
                continue
        
        return None
    
    async def scrape(self, medicamento: str = None) -> List[Dict]:
        """Método de compatibilidade"""
        return await self.buscar_licitacoes(termo_busca=medicamento)
