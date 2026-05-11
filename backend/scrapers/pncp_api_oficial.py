"""
PNCP API Oficial - Importador de Dados Abertos
Portal Nacional de Contratações Públicas

API Documentação: https://pncp.gov.br/api/consulta/swagger-ui/index.html

ENDPOINTS PRINCIPAIS:
- GET /v1/contratacoes/proposta - Contratações com propostas ABERTAS (P0 - Prospecção)
- GET /v1/contratacoes/publicacao - Contratações por data de publicação
- GET /v1/contratacoes/atualizacao - Contratações por data de atualização
- GET /v1/atas - Atas de Registro de Preços
- GET /v1/contratos - Contratos por data de publicação

Este importador usa a API PÚBLICA OFICIAL sem necessidade de autenticação.
"""

import aiohttp
import asyncio
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import uuid

logger = logging.getLogger(__name__)

class PNCPApiOficial:
    """
    Cliente oficial da API de Dados Abertos do PNCP
    Usa endpoints públicos sem necessidade de autenticação
    """
    
    BASE_URL = "https://pncp.gov.br/api/consulta/v1"
    
    # Keywords de saúde para filtro
    KEYWORDS_SAUDE = [
        'medicament', 'farmac', 'hospital', 'saúde', 'saude', 'médic', 'medic',
        'insulina', 'vacina', 'seringa', 'insumo', 'laborat', 'exame',
        'cirurg', 'ambulat', 'upa ', 'ubs ', 'pronto', 'samu',
        'oncolog', 'quimio', 'radio', 'hemodi', 'transplant'
    ]
    
    def __init__(self):
        self.fonte = "PNCP-API-OFICIAL"
        self.timeout = aiohttp.ClientTimeout(total=60)
        self.headers = {
            'Accept': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://pncp.gov.br/app/editais'
        }
        # URL da API de busca do portal (ElasticSearch proxy)
        self.SEARCH_URL = "https://pncp.gov.br/api/search/"
    
    async def buscar_propostas_abertas(
        self,
        termo_busca: str = None,
        apenas_saude: bool = True,
        limit: int = 50,
        pagina: int = 1
    ) -> List[Dict]:
        """
        🎯 ENDPOINT PRINCIPAL PARA PROSPECÇÃO
        
        Busca contratações com recebimento de propostas ABERTO
        Este é o endpoint mais importante para encontrar licitações FUTURAS
        
        GET /v1/contratacoes/proposta
        Parâmetros obrigatórios: dataInicial, dataFinal
        """
        resultados = []
        hoje = datetime.now()
        
        try:
            logger.info(f"🔍 [PNCP-OFICIAL] Buscando propostas ABERTAS...")
            
            async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as session:
                # Parâmetros da API PNCP - máximo 50 por página
                # Período: de 60 dias atrás até 90 dias no futuro
                params = {
                    'dataInicial': (hoje - timedelta(days=60)).strftime('%Y%m%d'),
                    'dataFinal': (hoje + timedelta(days=90)).strftime('%Y%m%d'),
                    'pagina': pagina,
                    'tamanhoPagina': 50  # Máximo permitido pela API é 50
                }
                
                url = f"{self.BASE_URL}/contratacoes/proposta"
                
                # Buscar até 10 páginas se for busca geral, ou 3 se for específica
                max_paginas = 3 if termo_busca else 10
                
                for pag in range(max_paginas):
                    if len(resultados) >= limit:
                        break
                    
                    params['pagina'] = pag + 1
                    
                    async with session.get(url, params=params) as response:
                        if response.status != 200:
                            logger.error(f"  ❌ Erro HTTP: {response.status}")
                            break
                        
                        data = await response.json()
                        
                        # Extrair dados
                        contratacoes = data.get('data', [])
                        total = data.get('totalRegistros', 0)
                        
                        if pag == 0:
                            logger.info(f"  ✅ API retornou {total} contratações com propostas abertas")
                        
                        if not contratacoes:
                            break
                        
                        for contratacao in contratacoes:
                            if len(resultados) >= limit:
                                break
                            
                            objeto = contratacao.get('objetoCompra', '').lower()
                            orgao = contratacao.get('orgaoEntidade', {}).get('razaoSocial', '').lower()
                            texto_completo = f"{objeto} {orgao}"
                            
                            # Filtrar por termo (se especificado)
                            if termo_busca:
                                termo = termo_busca.lower()
                                # Se o termo estiver no objeto, aceita
                                if termo not in texto_completo:
                                    continue
                            
                            # Filtrar por saúde (se especificado E não há termo de busca)
                            # Quando há termo de busca específico, não aplicamos filtro de saúde
                            if apenas_saude and not termo_busca:
                                if not any(kw in texto_completo for kw in self.KEYWORDS_SAUDE):
                                    continue
                            
                            # Converter para formato padrão
                            resultado = self._converter_contratacao(contratacao)
                            if resultado:
                                resultados.append(resultado)
            
            logger.info(f"🎯 [PNCP-OFICIAL] Propostas abertas: {len(resultados)} licitações de saúde")
            return resultados
            
        except Exception as e:
            logger.error(f"❌ [PNCP-OFICIAL] Erro: {str(e)}")
            import traceback
            logger.debug(traceback.format_exc())
            return []

    async def buscar_via_portal_search(
        self,
        termo_busca: str,
        limit: int = 50,
        pagina: int = 1,
        apenas_saude: bool = True
    ) -> List[Dict]:
        """
        🚀 BUSCA DE ALTA PERFORMANCE (PORTAL SEARCH)
        
        Usa o endpoint de busca do próprio portal PNCP (ElasticSearch)
        Este endpoint suporta o parâmetro 'q' (query) e retorna resultados do sistema todo.
        """
        resultados = []
        try:
            logger.info(f"🚀 [PNCP-OFICIAL] Buscando via Portal Search: '{termo_busca}'")
            
            async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as session:
                params = {
                    'q': termo_busca,
                    'tipos_documento': 'edital',
                    'ordenacao': '-data',
                    'pagina': pagina,
                    'tam_pagina': limit,
                    'status': 'recebendo_proposta' # Foco em editais ativos
                }
                
                async with session.get(self.SEARCH_URL, params=params) as response:
                    if response.status != 200:
                        logger.error(f"  ❌ Erro HTTP no Portal Search: {response.status}")
                        return []
                    
                    data = await response.json()
                    items = data.get('items', [])
                    total = data.get('total', 0)
                    
                    logger.info(f"  ✅ Portal Search encontrou {total} resultados para '{termo_busca}'")
                    
                    for item in items:
                        # O Portal Search já filtra por termo, mas podemos validar saúde se solicitado
                        if apenas_saude:
                            objeto = item.get('description', '').lower()
                            orgao = item.get('orgao_nome', '').lower()
                            if not any(kw in f"{objeto} {orgao}" for kw in self.KEYWORDS_SAUDE):
                                # Se o termo de busca for específico (ex: canabidiol), ignore o filtro de saúde
                                # pois o termo já implica interesse na saúde.
                                if termo_busca.lower() not in f"{objeto} {orgao}":
                                    continue
                        
                        resultado = self._converter_item_portal(item)
                        if resultado:
                            resultados.append(resultado)
            
            return resultados
            
        except Exception as e:
            logger.error(f"❌ [PNCP-OFICIAL] Erro no Portal Search: {str(e)}")
            return []

    def _converter_item_portal(self, item: Dict) -> Optional[Dict]:
        """Converte item do Portal Search para formato padrão GSM"""
        try:
            # Extrair chaves
            cnpj = item.get('orgao_cnpj', '')
            ano = item.get('ano', '')
            sequencial = item.get('numero_sequencial', '')
            
            # Datas
            data_abertura = self._parse_date(item.get('data_inicio_vigencia'))
            data_final = self._parse_date(item.get('data_fim_vigencia'))
            data_pub = self._parse_date(item.get('data_publicacao_pncp'))
            
            # URL do Edital
            # Formato oficial do portal: https://pncp.gov.br/app/editais/{cnpj}/{ano}/{sequencial}
            link_origem = f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{sequencial}"
            
            objeto = item.get('description', 'Sem descrição')
            
            return {
                'id': str(uuid.uuid4()),
                'titulo_licitacao': item.get('title', 'Licitação PNCP')[:200],
                'medicamento': self._extrair_medicamento(objeto),
                'estado': item.get('uf', 'BR'),
                'estado_uf': item.get('uf', 'BR'),
                'orgao_licitante': item.get('orgao_nome', 'Órgão não identificado')[:200],
                'status': 'Ativa', # Se veio da busca com status=recebendo_proposta
                'status_aquisicao': 'FUTURA',
                'modalidade': item.get('modalidade_licitacao_nome', 'Não especificada'),
                'numero_processo': item.get('numero_controle_pncp', f"{ano}/{sequencial}"),
                'data_referencia': datetime.now(),
                'data_abertura': data_abertura,
                'data_inicial': data_abertura,
                'data_final': data_final,
                'data_publicacao': data_pub,
                'link_origem': link_origem,
                'link_documento': link_origem,
                'fonte_nome': 'PNCP - Portal Oficial',
                'fonte_id': f"pncp-{cnpj}-{ano}-{sequencial}",
                'uasg': cnpj,
                'esfera': item.get('esfera_nome', 'Não identificada'),
                'objeto': objeto[:500],
                'tags': self._extrair_tags(objeto),
                'is_mock': False,
                'fonte': 'PNCP-OFICIAL'
            }
        except Exception as e:
            logger.debug(f"  ⚠️ Erro ao converter item portal: {e}")
            return None
    
    async def buscar_por_publicacao(
        self,
        data_inicio: datetime = None,
        data_fim: datetime = None,
        termo_busca: str = None,
        apenas_saude: bool = True,
        limit: int = 50
    ) -> List[Dict]:
        """
        Busca contratações por data de publicação
        
        GET /v1/contratacoes/publicacao
        
        NOTA: Este endpoint requer codigoModalidadeContratacao
        Vamos usar o endpoint de propostas como alternativa
        """
        # Usar o endpoint de propostas abertas que não requer modalidade
        return await self.buscar_propostas_abertas(
            termo_busca=termo_busca,
            apenas_saude=apenas_saude,
            limit=limit
        )
    
    async def _buscar_por_publicacao_legado(
        self,
        data_inicio: datetime = None,
        data_fim: datetime = None,
        termo_busca: str = None,
        apenas_saude: bool = True,
        limit: int = 50
    ) -> List[Dict]:
        """
        Busca contratações por data de publicação (LEGADO - requer modalidade)
        
        GET /v1/contratacoes/publicacao
        
        Parâmetros:
        - dataInicial: Data inicial no formato YYYYMMDD
        - dataFinal: Data final no formato YYYYMMDD
        - codigoModalidadeContratacao: Código da modalidade (obrigatório)
        """
        resultados = []
        
        # Default: últimos 30 dias
        if not data_fim:
            data_fim = datetime.now()
        if not data_inicio:
            data_inicio = data_fim - timedelta(days=30)
        
        try:
            logger.info(f"🔍 [PNCP-OFICIAL] Buscando publicações de {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}...")
            
            async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as session:
                # Modalidades: 1=Pregão, 2=Concorrência, 3=Tomada de Preços, etc.
                params = {
                    'dataInicial': data_inicio.strftime('%Y%m%d'),
                    'dataFinal': data_fim.strftime('%Y%m%d'),
                    'codigoModalidadeContratacao': 6,  # 6 = Pregão Eletrônico
                    'pagina': 1,
                    'tamanhoPagina': min(500, limit * 2)
                }
                
                url = f"{self.BASE_URL}/contratacoes/publicacao"
                
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        logger.error(f"  ❌ Erro HTTP: {response.status}")
                        return []
                    
                    data = await response.json()
                    contratacoes = data.get('data', [])
                    total = data.get('totalRegistros', 0)
                    
                    logger.info(f"  ✅ Recebidos {len(contratacoes)} de {total} publicações")
                    
                    for contratacao in contratacoes:
                        if len(resultados) >= limit:
                            break
                        
                        # Filtrar por saúde
                        if apenas_saude:
                            objeto = contratacao.get('objetoCompra', '').lower()
                            orgao = contratacao.get('nomeOrgao', contratacao.get('orgaoEntidade', {}).get('razaoSocial', '')).lower()
                            texto = f"{objeto} {orgao}"
                            
                            if not any(kw in texto for kw in self.KEYWORDS_SAUDE):
                                continue
                        
                        # Filtrar por termo
                        if termo_busca:
                            objeto = contratacao.get('objetoCompra', '').lower()
                            if termo_busca.lower() not in objeto:
                                continue
                        
                        resultado = self._converter_contratacao(contratacao)
                        if resultado:
                            resultados.append(resultado)
            
            logger.info(f"🎯 [PNCP-OFICIAL] Publicações: {len(resultados)} licitações")
            return resultados
            
        except Exception as e:
            logger.error(f"❌ [PNCP-OFICIAL] Erro: {str(e)}")
            return []
    
    async def buscar_atas_registro_preco(
        self,
        termo_busca: str = None,
        apenas_saude: bool = True,
        limit: int = 30
    ) -> List[Dict]:
        """
        Busca Atas de Registro de Preços vigentes
        
        GET /v1/atas
        """
        resultados = []
        hoje = datetime.now()
        
        try:
            logger.info(f"🔍 [PNCP-OFICIAL] Buscando Atas de Registro de Preços vigentes...")
            
            async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as session:
                params = {
                    'dataVigenciaInicial': (hoje - timedelta(days=365)).strftime('%Y%m%d'),
                    'dataVigenciaFinal': (hoje + timedelta(days=365)).strftime('%Y%m%d'),
                    'pagina': 1,
                    'tamanhoPagina': min(200, limit * 2)
                }
                
                url = f"{self.BASE_URL}/atas"
                
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        logger.error(f"  ❌ Erro HTTP: {response.status}")
                        return []
                    
                    data = await response.json()
                    atas = data.get('data', [])
                    
                    logger.info(f"  ✅ Recebidas {len(atas)} atas de registro de preços")
                    
                    for ata in atas:
                        if len(resultados) >= limit:
                            break
                        
                        # Filtrar por saúde (se tiver descrição)
                        if apenas_saude:
                            descricao = ata.get('descricaoObjeto', '').lower()
                            if not any(kw in descricao for kw in self.KEYWORDS_SAUDE):
                                continue
                        
                        resultado = self._converter_ata(ata)
                        if resultado:
                            resultados.append(resultado)
            
            logger.info(f"🎯 [PNCP-OFICIAL] Atas SRP: {len(resultados)}")
            return resultados
            
        except Exception as e:
            logger.error(f"❌ [PNCP-OFICIAL] Erro: {str(e)}")
            return []
    
    async def buscar_licitacoes(
        self,
        termo_busca: str = None,
        apenas_futuras: bool = True,
        apenas_saude: bool = True,
        limit: int = 50
    ) -> List[Dict]:
        """
        Método principal de busca - combina múltiplas fontes
        
        Estratégia:
        1. Se apenas_futuras: Prioriza endpoint de propostas abertas
        2. Complementa com publicações recentes
        3. Opcionalmente inclui atas de registro de preços
        """
        resultados = []
        
        try:
            logger.info(f"🔍 [PNCP-OFICIAL] Busca combinada: '{termo_busca or 'geral'}' (futuras={apenas_futuras})")
            
            # PRIORIDADE 1: Se houver termo, usar busca do portal (muito mais eficiente)
            if termo_busca:
                resultados_portal = await self.buscar_via_portal_search(
                    termo_busca=termo_busca,
                    limit=limit,
                    apenas_saude=apenas_saude
                )
                if resultados_portal:
                    resultados.extend(resultados_portal)
                    logger.info(f"  ⚡ Portal Search: {len(resultados_portal)} resultados")
                
                # Se já temos o limite, encerra por aqui
                if len(resultados) >= limit:
                    return resultados[:limit]

            # PRIORIDADE 2: Propostas abertas (método tradicional)
            if apenas_futuras:
                propostas = await self.buscar_propostas_abertas(
                    termo_busca=termo_busca,
                    apenas_saude=apenas_saude,
                    limit=limit - len(resultados)
                )
                resultados.extend(propostas)
                logger.info(f"  ✅ Propostas abertas: {len(propostas)}")
            
            # PRIORIDADE 3: Publicações recentes
            if len(resultados) < limit:
                publicacoes = await self.buscar_por_publicacao(
                    termo_busca=termo_busca,
                    apenas_saude=apenas_saude,
                    limit=limit - len(resultados)
                )
                resultados.extend(publicacoes)
                logger.info(f"  ✅ Publicações recentes: {len(publicacoes)}")
            
            # Remover duplicatas por fonte_id
            resultados = self._remover_duplicatas(resultados)
            
            logger.info(f"🎯 [PNCP-OFICIAL] Total: {len(resultados)} licitações únicas")
            return resultados[:limit]
            
        except Exception as e:
            logger.error(f"❌ [PNCP-OFICIAL] Erro geral: {str(e)}")
            return []
    
    def _converter_contratacao(self, contratacao: Dict) -> Optional[Dict]:
        """Converte contratação do PNCP para formato padrão GSM"""
        try:
            # Extrair dados básicos
            cnpj = contratacao.get('orgaoEntidade', {}).get('cnpj', '')
            ano = contratacao.get('anoCompra', '')
            sequencial = contratacao.get('sequencialCompra', '')
            
            # Extrair datas
            data_abertura = self._parse_date(contratacao.get('dataAberturaProposta'))
            data_encerramento = self._parse_date(contratacao.get('dataEncerramentoProposta'))
            data_publicacao = self._parse_date(contratacao.get('dataPublicacaoPncp'))
            
            # Determinar status
            status = self._determinar_status(data_abertura, data_encerramento)
            
            # Extrair UF
            uf = contratacao.get('orgaoEntidade', {}).get('ufSigla', '')
            if not uf:
                uf = contratacao.get('unidadeOrgao', {}).get('ufSigla', 'BR')
            
            # Objeto
            objeto = contratacao.get('objetoCompra', 'Sem descrição')
            
            return {
                'id': str(uuid.uuid4()),
                'titulo_licitacao': objeto[:200],
                'medicamento': self._extrair_medicamento(objeto),
                'estado': uf,
                'estado_uf': uf,
                'orgao_licitante': contratacao.get('orgaoEntidade', {}).get('razaoSocial', 'Órgão não identificado')[:200],
                'status': status,
                'status_aquisicao': status,
                'modalidade': contratacao.get('modalidadeNome', 'Não especificada'),
                'numero_processo': f"{ano}/{sequencial}",
                'data_referencia': datetime.now(),
                'data_abertura': data_abertura,
                'data_inicial': data_abertura,
                'data_final': data_encerramento,
                'data_limite': data_encerramento,
                'data_publicacao': data_publicacao,
                # 🔗 Link DIRETO para o edital (Sistema GSM)
                # Prioridade: linkSistemaOrigem > URL PNCP construída
                'link_origem': contratacao.get('linkSistemaOrigem') or f"https://pncp.gov.br/pncp-publicacao/{cnpj}/{ano}/{sequencial}",
                'link_documento': contratacao.get('linkSistemaOrigem'),
                'link_pncp_direto': f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{sequencial}",
                'fonte_nome': 'PNCP - API Oficial',
                'fonte_id': f"pncp-{cnpj}-{ano}-{sequencial}",
                'numero_pregao': contratacao.get('numeroCompra'),
                'uasg': cnpj,
                'esfera': self._determinar_esfera(contratacao),
                'objeto': objeto[:500],
                'registro_preco': contratacao.get('srp', False),
                'valor_total': contratacao.get('valorTotalEstimado'),
                'itens': [],
                'tags': self._extrair_tags(objeto),
                'is_mock': False,
                'fonte': 'PNCP-OFICIAL'
            }
        except Exception as e:
            logger.debug(f"  ⚠️ Erro ao converter contratação: {e}")
            return None
    
    def _converter_ata(self, ata: Dict) -> Optional[Dict]:
        """Converte ata de registro de preços para formato padrão GSM"""
        try:
            return {
                'id': str(uuid.uuid4()),
                'titulo_licitacao': ata.get('descricaoObjeto', 'Ata de Registro de Preços')[:200],
                'medicamento': self._extrair_medicamento(ata.get('descricaoObjeto', '')),
                'estado': 'BR',
                'estado_uf': 'BR',
                'orgao_licitante': ata.get('orgaoGerenciador', {}).get('razaoSocial', 'Órgão não identificado'),
                'status': 'Vigente',
                'modalidade': 'Ata de Registro de Preços',
                'numero_processo': ata.get('numeroAta', 'N/A'),
                'data_referencia': datetime.now(),
                'data_abertura': self._parse_date(ata.get('dataVigenciaInicio')),
                'data_final': self._parse_date(ata.get('dataVigenciaFim')),
                'link_origem': 'https://pncp.gov.br/app/atas',
                'fonte_nome': 'PNCP - Atas SRP',
                'fonte_id': f"pncp-ata-{ata.get('numeroAta', '')}",
                'esfera': 'Federal',
                'objeto': ata.get('descricaoObjeto', '')[:500],
                'registro_preco': True,
                'tags': ['SRP', 'Ata'],
                'is_mock': False,
                'fonte': 'PNCP-ATA'
            }
        except Exception as e:
            logger.debug(f"  ⚠️ Erro ao converter ata: {e}")
            return None
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse de data do PNCP"""
        if not date_str:
            return None
        
        formatos = [
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%S.%f',
            '%Y-%m-%d',
            '%d/%m/%Y'
        ]
        
        for fmt in formatos:
            try:
                return datetime.strptime(date_str[:19], fmt)
            except:
                continue
        return None
    
    def _determinar_status(self, data_abertura: datetime, data_encerramento: datetime) -> str:
        """Determina status baseado nas datas"""
        hoje = datetime.now()
        
        if data_abertura and data_abertura > hoje:
            return 'Agendado'
        
        if data_encerramento:
            if data_encerramento > hoje:
                return 'Aberto'
            else:
                return 'Encerrado'
        
        if data_abertura and data_abertura <= hoje:
            return 'Em Andamento'
        
        return 'Publicado'
    
    def _determinar_esfera(self, contratacao: Dict) -> str:
        """Determina esfera (Federal/Estadual/Municipal)"""
        poder = contratacao.get('orgaoEntidade', {}).get('poderId', '')
        esfera = contratacao.get('orgaoEntidade', {}).get('esferaId', '')
        
        if esfera == 'F' or poder in ['E', 'L', 'J']:
            return 'Federal'
        elif esfera == 'E':
            return 'Estadual'
        elif esfera == 'M':
            return 'Municipal'
        
        return 'Federal'
    
    def _extrair_medicamento(self, objeto: str) -> str:
        """Extrai nome de medicamento do objeto"""
        if not objeto:
            return ''
        
        # Lista expandida de medicamentos para melhorar detecção
        medicamentos = [
            'canabidiol', 'insulina', 'metformina', 'atorvastatina', 'losartana', 'omeprazol',
            'dipirona', 'paracetamol', 'ibuprofeno', 'amoxicilina', 'azitromicina',
            'adalimumabe', 'rituximabe', 'pembrolizumabe', 'lenalidomida'
        ]
        
        objeto_lower = objeto.lower()
        for med in medicamentos:
            if med in objeto_lower:
                return med.capitalize()
        
        # Se não achou na lista, tenta pegar a primeira palavra após "aquisição de" ou similar
        import re
        padrao = re.compile(r'(?:aquisição|aquisicao|fornecimento|compra|item)\s+(?:de\s+)?([a-z]{5,})', re.IGNORECASE)
        match = padrao.search(objeto)
        if match:
            return match.group(1).capitalize()

        return ''
    
    def _extrair_tags(self, objeto: str) -> List[str]:
        """Extrai tags relevantes do objeto"""
        tags = []
        objeto_lower = objeto.lower()
        
        categorias = {
            'medicamento': ['medicament', 'fármac', 'farmac', 'remédio'],
            'equipamento': ['equipament', 'aparelho', 'máquina'],
            'material': ['material', 'insumo', 'descartável'],
            'serviço': ['serviço', 'manutenção', 'consultoria'],
            'saúde': ['saúde', 'saude', 'hospital', 'médic', 'medic']
        }
        
        for tag, keywords in categorias.items():
            if any(kw in objeto_lower for kw in keywords):
                tags.append(tag)
        
        return tags
    
    def _remover_duplicatas(self, resultados: List[Dict]) -> List[Dict]:
        """Remove duplicatas por fonte_id"""
        vistos = set()
        unicos = []
        for r in resultados:
            fonte_id = r.get('fonte_id', r.get('id'))
            if fonte_id not in vistos:
                vistos.add(fonte_id)
                unicos.append(r)
        return unicos
