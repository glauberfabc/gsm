"""
Importador de Licitações de Minas Gerais via CSV do Portal de Dados Abertos

FONTE: https://dados.mg.gov.br/dataset/compras_contratos
ARQUIVO: dm_processo.csv.gz (Processos de Compra)
MÉTODO: Download de CSV GZIP com processamento em chunks

Vantagens:
- Sem CAPTCHA ou bloqueio (alternativa ao portal compras.mg.gov.br bloqueado por 403)
- Dados de TODOS os órgãos estaduais de MG
- Histórico desde 2010 (15 anos!)
- Atualização diária pelo portal
- Link direto para edital (quando disponível)

Campos do CSV:
- id_processo: ID único do processo
- orgao: Nome do órgão licitante
- procedimento: Tipo de procedimento (Pregão, Dispensa, Inexigibilidade...)
- objeto: Descrição do objeto licitado
- situacao: Status (Concluído, Em andamento, Cancelado...)
- tp_licitacao: Tipo de licitação (Menor Preço, Melhor Técnica...)
- dt_cad_processo: Data de cadastro do processo
- vr_referencia: Valor de referência
- vr_homologado: Valor homologado
- url_edital: Link direto para o edital

Criado: Dezembro 2025
"""

from typing import List, Dict, Optional, Generator
from datetime import datetime
from io import BytesIO
import logging
import gzip
import requests
import uuid
import csv
import re

logger = logging.getLogger(__name__)

# Configuração de chunking para economia de memória
CHUNK_SIZE = 10000  # Processar 10.000 registros por vez


class MinasGeraisCsvImporter:
    """
    Importador de licitações de Minas Gerais via CSV do Portal de Dados Abertos
    
    Portal: https://dados.mg.gov.br/dataset/compras_contratos
    Arquivo: dm_processo.csv.gz
    Método: Download CSV GZIP com processamento em chunks
    Atualização: Diária
    Cobertura: Todos os órgãos do Estado de MG
    """
    
    def __init__(self):
        self.base_url = 'https://dados.mg.gov.br'
        self.dataset_url = f'{self.base_url}/dataset/compras_contratos'
        
        # URL direta do arquivo dm_processo.csv.gz
        self.csv_url = f'{self.base_url}/dataset/86e157db-d2c5-4151-9b16-9c5987462cba/resource/b929ee51-e78a-4e7c-9f6e-ed6d58e7d820/download/dm_processo.csv.gz'
        
        self.estado = 'MG'
        self.fonte = 'Dados Abertos MG'
        
        # Headers para requisição (necessário para evitar 403)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            'Referer': 'https://dados.mg.gov.br/dataset/compras_contratos'
        }
        
        # Mapeamento de procedimentos para modalidades
        self.modalidade_map = {
            'pregao eletronico': 'Pregão Eletrônico',
            'pregao presencial': 'Pregão Presencial',
            'pregão': 'Pregão',
            'concorrencia': 'Concorrência',
            'tomada de precos': 'Tomada de Preços',
            'convite': 'Convite',
            'leilao': 'Leilão',
            'dispensa': 'Dispensa de Licitação',
            'inexigibilidade': 'Inexigibilidade',
            'credenciamento': 'Credenciamento',
            'chamamento': 'Chamamento Público',
            'registro de precos': 'Registro de Preços',
            'cotacao': 'Cotação Eletrônica',
            'adesao': 'Adesão a Ata de Registro'
        }
        
        # Órgãos de saúde prioritários
        self.orgaos_saude = [
            'SAÚDE', 'SAUDE', 'HOSPITAL', 'FHEMIG', 'HEMOMINAS',
            'FUNED', 'FUNDAÇÃO EZEQUIEL', 'SES', 'SECRETARIA DE SAÚDE',
            'FUNDO ESTADUAL DE SAÚDE', 'VIGILÂNCIA', 'SANITÁRIA',
            'ESP-MG', 'FUNDAÇÃO HOSPITALAR', 'FARMÁCIA', 'FARMACIA'
        ]
        
        # Keywords de saúde para filtrar objetos
        self.keywords_saude = [
            'medicamento', 'fármaco', 'farmac', 'hospitalar', 'saúde', 'saude',
            'médico', 'medico', 'insumo', 'cirurg', 'laborat', 'diagnóstic',
            'vacina', 'seringa', 'agulha', 'luva', 'mascara', 'máscara',
            'material hospitalar', 'equipamento médico', 'ambulância'
        ]
    
    async def buscar_licitacoes(
        self,
        termo_busca: str = None,
        apenas_saude: bool = True,
        apenas_futuras: bool = False,
        limit: int = 50
    ) -> List[Dict]:
        """
        Busca licitações de Minas Gerais via CSV do Portal de Dados Abertos
        OTIMIZADO: Usa chunking para economia de memória
        OTIMIZADO PARA PROSPECÇÃO FUTURA (P0 - Dezembro 2025)
        
        Args:
            termo_busca: Termo para filtrar (ex: 'medicamento', 'insulina')
            apenas_saude: Se True, filtra apenas órgãos/objetos de saúde
            apenas_futuras: Se True, prioriza processos ABERTOS/FUTUROS
            limit: Número máximo de resultados
            
        Returns:
            Lista de dicionários com dados das licitações
        """
        resultados = []
        
        try:
            modo = "FUTUROS/ABERTOS" if apenas_futuras else "geral"
            logger.info(f"🔍 [MG] Iniciando importação CSV ({modo}) com CHUNKING: '{termo_busca or 'geral'}'")
            
            # ETAPA 1: Baixar o GZIP
            logger.info(f"  📥 Baixando CSV GZIP de MG...")
            gzip_content = await self._baixar_gzip()
            
            if not gzip_content:
                logger.warning("  ⚠️ Falha no download do GZIP")
                return []
            
            logger.info(f"  ✅ GZIP baixado ({len(gzip_content)/1024/1024:.1f} MB)")
            
            # ETAPA 2: Processar CSV com CHUNKING e filtro de prospecção
            logger.info(f"  📊 Processando CSV em chunks de {CHUNK_SIZE} registros...")
            
            chunk_index = 0
            for chunk_resultados in self._processar_gzip_em_chunks(
                gzip_content,
                termo_busca=termo_busca,
                apenas_saude=apenas_saude,
                apenas_futuras=apenas_futuras,
                limit=limit
            ):
                chunk_index += 1
                resultados.extend(chunk_resultados)
                logger.debug(f"    Chunk {chunk_index}: +{len(chunk_resultados)} resultados")
                
                # Parar se atingiu o limite
                if len(resultados) >= limit:
                    resultados = resultados[:limit]
                    break
            
            logger.info(f"🎯 [MG] Total processado: {len(resultados)} licitações")
            return resultados
            
        except Exception as e:
            logger.error(f"❌ [MG] Erro geral: {str(e)}")
            import traceback
            logger.debug(traceback.format_exc())
            return []
    
    async def _baixar_gzip(self) -> Optional[bytes]:
        """Baixa o GZIP com streaming para economia de memória"""
        try:
            response = requests.get(
                self.csv_url,
                headers=self.headers,
                timeout=180,
                stream=True
            )
            
            if response.status_code == 200:
                # Ler em chunks para não sobrecarregar memória
                chunks = []
                for chunk in response.iter_content(chunk_size=1024*1024):  # 1MB por vez
                    chunks.append(chunk)
                return b''.join(chunks)
            elif response.status_code == 403:
                logger.error("  ❌ Acesso negado (403) - verificar headers")
                return None
            else:
                logger.error(f"  ❌ HTTP {response.status_code}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error("  ❌ Timeout ao baixar GZIP")
            return None
        except Exception as e:
            logger.error(f"  ❌ Erro: {str(e)}")
            return None
    
    def _processar_gzip_em_chunks(
        self,
        gzip_content: bytes,
        termo_busca: str = None,
        apenas_saude: bool = True,
        apenas_futuras: bool = False,
        limit: int = 50
    ) -> Generator[List[Dict], None, None]:
        """
        PROCESSAMENTO EM CHUNKS: Gera resultados em blocos para economia de memória
        OTIMIZADO PARA PROSPECÇÃO FUTURA (P0)
        
        Yields:
            Lista de licitações processadas (um chunk por vez)
        """
        # Contadores para log de prospecção
        filtrados_status = 0
        filtrados_data = 0
        
        try:
            # Descomprimir GZIP
            with gzip.GzipFile(fileobj=BytesIO(gzip_content)) as gz:
                # Detectar encoding
                content_sample = gz.read(10000)
                gz.seek(0)
                
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
                text_wrapper = io.TextIOWrapper(gz, encoding=encoding, errors='ignore')
                
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
                        # Limpar campos (remover BOM e espaços)
                        row = {k.strip().strip('\ufeff'): v.strip() if v else '' 
                               for k, v in row.items() if k}
                        
                        # Processar linha com filtro de prospecção
                        resultado = self._processar_linha(
                            row, 
                            licitacoes_unicas,
                            termo_busca, 
                            apenas_saude,
                            apenas_futuras
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
                    
        except gzip.BadGzipFile:
            logger.error("    ❌ Arquivo GZIP corrompido")
        except Exception as e:
            logger.error(f"    ❌ Erro: {str(e)}")
    
    def _processar_linha(
        self, 
        row: Dict, 
        licitacoes_unicas: set,
        termo_busca: str = None,
        apenas_saude: bool = True,
        apenas_futuras: bool = False
    ) -> Optional[Dict]:
        """
        Processa uma linha do CSV e retorna no formato padrão
        OTIMIZADO PARA PROSPECÇÃO FUTURA (P0)
        """
        hoje = datetime.now()
        
        # Extrair campos
        id_processo = row.get('id_processo', '')
        orgao = row.get('orgao', '')
        procedimento = row.get('procedimento', '')
        objeto = row.get('objeto', '')
        situacao = row.get('situacao', '')
        tp_licitacao = row.get('tp_licitacao', '')
        dt_processo = row.get('dt_cad_processo', '')
        vr_referencia = row.get('vr_referencia', '')
        vr_homologado = row.get('vr_homologado', '')
        url_edital = row.get('url_edital', '')
        cd_processo = row.get('cd_processo_formatado', row.get('cd_processo', ''))
        
        # ===============================================
        # FILTRO DE PROSPECÇÃO (P0 - Processos Futuros)
        # ===============================================
        if apenas_futuras:
            # 1. Filtrar por STATUS: apenas processos NÃO ENCERRADOS
            situacao_lower = situacao.lower() if situacao else ''
            if any(s in situacao_lower for s in ['concluíd', 'concluido', 'cancelad', 'revogad', 'anulad', 'desert', 'fracassad']):
                return None
            
            # 2. Filtrar por DATA: processos recentes (últimos 60 dias)
            dt_processo_parsed = self._parse_date(dt_processo)
            if dt_processo_parsed:
                from datetime import timedelta
                if dt_processo_parsed < (hoje - timedelta(days=60)):
                    return None
        
        # Criar chave única
        chave_unica = f"mg_{id_processo}"
        if chave_unica in licitacoes_unicas:
            return None
        
        # Filtrar por saúde
        if apenas_saude:
            texto_orgao = orgao.upper()
            texto_objeto = objeto.upper()
            
            is_saude_orgao = any(org in texto_orgao for org in self.orgaos_saude)
            is_saude_objeto = any(kw.upper() in texto_objeto for kw in self.keywords_saude)
            
            if not (is_saude_orgao or is_saude_objeto):
                return None
        
        # Filtrar por termo
        if termo_busca:
            termo_lower = termo_busca.lower()
            texto_completo = f"{objeto} {orgao} {procedimento}".lower()
            if termo_lower not in texto_completo:
                return None
        
        # Adicionar à lista de únicos
        licitacoes_unicas.add(chave_unica)
        
        # Determinar status com lógica de prospecção
        dt_processo_final = self._parse_date(dt_processo)
        status_final = self._normalizar_status_prospeccao(situacao, dt_processo_final, hoje)
        
        # Converter para formato padrão
        return {
            'id': str(uuid.uuid4()),
            'titulo_licitacao': objeto[:200] if objeto else 'Sem título',
            'medicamento': self._extrair_medicamento(objeto),
            'estado': self.estado,
            'estado_uf': self.estado,
            'orgao_licitante': orgao[:200] if orgao else 'Governo de Minas Gerais',
            'status': status_final,
            'status_aquisicao': status_final,
            'modalidade': self._normalizar_modalidade(procedimento),
            'numero_processo': cd_processo or id_processo or 'N/A',
            'data_referencia': datetime.now(),
            'data_abertura': dt_processo_final,
            'data_inicial': dt_processo_final,
            'data_final': None,
            'data_limite': None,
            'link_origem': url_edital if url_edital else self.dataset_url,
            'link_documento': url_edital if url_edital and url_edital.strip() else None,
            'fonte_nome': self.fonte,
            'fonte_id': f'mg-{id_processo}',
            'numero_pregao': cd_processo,
            'uasg': None,
            'esfera': 'Estadual',
            'objeto': objeto[:500] if objeto else '',
            'valor_referencia': self._parse_valor(vr_referencia),
            'valor_homologado': self._parse_valor(vr_homologado),
            'tipo_licitacao': tp_licitacao,
            'itens': [],
            'tags': self._extrair_tags(objeto),
            'is_mock': False,
            'fonte': 'MG-CSV'
        }
    
    def _normalizar_status_prospeccao(self, situacao: str, data_processo: Optional[datetime], hoje: datetime) -> str:
        """
        Normaliza status com foco em PROSPECÇÃO
        """
        # Usar situação da API primeiro
        if situacao:
            situacao_lower = situacao.lower()
            
            # Status de PROCESSO EM ANDAMENTO (alta prioridade)
            if 'andamento' in situacao_lower:
                return 'Em Andamento'
            elif any(s in situacao_lower for s in ['aberto', 'publicad', 'recebendo']):
                return 'Aberto'
        
        # Fallback para normalização padrão
        return self._normalizar_status(situacao)
    
    def _normalizar_modalidade(self, procedimento: str) -> str:
        """Normaliza o tipo de procedimento para modalidade padrão"""
        if not procedimento:
            return 'Não informado'
        
        procedimento_lower = procedimento.lower().strip()
        
        for key, value in self.modalidade_map.items():
            if key in procedimento_lower:
                return value
        
        if 'dispensa' in procedimento_lower:
            return 'Dispensa de Licitação'
        elif 'inexigibilidade' in procedimento_lower:
            return 'Inexigibilidade'
        elif 'pregão' in procedimento_lower or 'pregao' in procedimento_lower:
            return 'Pregão Eletrônico'
        elif 'concorrência' in procedimento_lower or 'concorrencia' in procedimento_lower:
            return 'Concorrência'
        elif 'registro' in procedimento_lower and 'preco' in procedimento_lower:
            return 'Registro de Preços'
        
        return procedimento[:50]
    
    def _normalizar_status(self, situacao: str) -> str:
        """Normaliza o status da licitação"""
        if not situacao:
            return 'Em Licitação'
        
        situacao_lower = situacao.lower().strip()
        
        if 'concluíd' in situacao_lower or 'concluido' in situacao_lower:
            return 'Concluído'
        elif 'andamento' in situacao_lower:
            return 'Em Andamento'
        elif 'cancelad' in situacao_lower:
            return 'Cancelado'
        elif 'suspen' in situacao_lower:
            return 'Suspenso'
        elif 'revogad' in situacao_lower:
            return 'Revogado'
        elif 'desert' in situacao_lower:
            return 'Deserto'
        elif 'fracassad' in situacao_lower:
            return 'Fracassado'
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
            'insulina', 'metformina', 'omeprazol', 'paracetamol', 'dipirona',
            'amoxicilina', 'azitromicina', 'losartana', 'atenolol', 'ibuprofeno',
            'canabidiol', 'adalimumabe', 'pembrolizumabe', 'infliximabe'
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
        if 'urgente' in texto_lower or 'emergência' in texto_lower:
            tags.append('urgente')
        
        return tags
    
    def _parse_date(self, texto: str) -> Optional[datetime]:
        """Parse de data"""
        if not texto:
            return None
        
        texto_limpo = texto.strip()
        
        formatos = ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y']
        
        for formato in formatos:
            try:
                return datetime.strptime(texto_limpo[:10], formato)
            except:
                continue
        
        return None
    
    def _parse_valor(self, texto: str) -> Optional[float]:
        """Parse de valor monetário"""
        if not texto:
            return None
        
        try:
            valor_limpo = re.sub(r'[^\d,.]', '', str(texto).strip())
            
            if ',' in valor_limpo and '.' in valor_limpo:
                valor_limpo = valor_limpo.replace('.', '').replace(',', '.')
            elif ',' in valor_limpo:
                valor_limpo = valor_limpo.replace(',', '.')
            
            return float(valor_limpo) if valor_limpo else None
        except ValueError:
            return None
    
    async def scrape(self, medicamento: str = None) -> List[Dict]:
        """Método de compatibilidade com interface padrão"""
        return await self.buscar_licitacoes(termo_busca=medicamento)
