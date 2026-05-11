"""
Cliente PNCP Aprimorado com Suporte a Autenticação OAuth 2.0

PNCP - Portal Nacional de Contratações Públicas
API: https://pncp.gov.br/api/pncp/v1

Este cliente implementa:
1. Autenticação OAuth 2.0 (quando credenciais disponíveis)
2. Fallback para API pública (sem auth)
3. Rate limiting com exponential backoff
4. Retries automáticos para erros transitórios
5. Paginação completa para grandes conjuntos de dados

Documentação PNCP: https://www.gov.br/pncp/pt-br/acesso-a-informacao/manuais
"""

import requests
import logging
import time
import os
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from functools import wraps

logger = logging.getLogger(__name__)


def retry_with_backoff(max_retries: int = 5, initial_delay: float = 1.0):
    """
    Decorator para retry com exponential backoff
    
    Handles:
    - 429 Too Many Requests
    - 500, 502, 503, 504 Server Errors
    - Connection timeouts
    - Network errors
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.HTTPError as e:
                    response = e.response
                    status_code = response.status_code if response else 0
                    
                    # 401 Unauthorized - Token expirado
                    if status_code == 401:
                        logger.warning(f"  ⚠️ Token expirado (401). Tentativa {attempt + 1}/{max_retries}")
                        # Invalidar token para forçar refresh
                        if hasattr(args[0], '_invalidate_token'):
                            args[0]._invalidate_token()
                        if attempt < max_retries - 1:
                            time.sleep(delay)
                            delay *= 2
                            continue
                    
                    # 429 Too Many Requests - Rate limited
                    elif status_code == 429:
                        retry_after = int(response.headers.get('Retry-After', delay * 2))
                        logger.warning(f"  ⚠️ Rate limited (429). Aguardando {retry_after}s...")
                        time.sleep(retry_after)
                        delay *= 2
                        continue
                    
                    # 5xx Server errors - Transitórios
                    elif status_code >= 500:
                        logger.warning(f"  ⚠️ Erro servidor ({status_code}). Tentativa {attempt + 1}/{max_retries}")
                        if attempt < max_retries - 1:
                            time.sleep(delay)
                            delay *= 2
                            continue
                    
                    # Outros erros HTTP - Não recuperáveis
                    else:
                        raise
                    
                    last_exception = e
                    
                except requests.exceptions.Timeout:
                    logger.warning(f"  ⏱️ Timeout. Tentativa {attempt + 1}/{max_retries}")
                    if attempt < max_retries - 1:
                        time.sleep(delay)
                        delay *= 2
                        continue
                    last_exception = requests.exceptions.Timeout("Max retries exceeded")
                    
                except requests.exceptions.ConnectionError as e:
                    logger.warning(f"  🔌 Erro de conexão. Tentativa {attempt + 1}/{max_retries}")
                    if attempt < max_retries - 1:
                        time.sleep(delay)
                        delay *= 2
                        continue
                    last_exception = e
            
            # Todas as tentativas falharam
            if last_exception:
                raise last_exception
            return None
            
        return wrapper
    return decorator


class PNCPAuthenticatedClient:
    """
    Cliente PNCP com suporte a autenticação OAuth 2.0
    
    Modos de operação:
    1. Autenticado: Usa credenciais OAuth para acesso completo à API
    2. Público: Fallback para endpoints públicos (limitados)
    
    Configuração via variáveis de ambiente:
    - PNCP_CLIENT_ID: Client ID OAuth
    - PNCP_CLIENT_SECRET: Client Secret OAuth
    - PNCP_AUTH_URL: URL de autenticação (opcional)
    """
    
    # URLs da API PNCP (2024/2025)
    BASE_URL = 'https://pncp.gov.br/api/pncp/v1'
    AUTH_URL = 'https://pncp.gov.br/api/pncp/v1/auth/token'  # URL de auth (verificar docs oficiais)
    APP_URL = 'https://pncp.gov.br/app'
    
    # Configurações de rate limiting
    MAX_RETRIES = 5
    INITIAL_DELAY = 1.0
    REQUEST_DELAY = 1.5  # Delay entre requisições
    
    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        use_auth: bool = True
    ):
        """
        Inicializa o cliente PNCP
        
        Args:
            client_id: OAuth Client ID (ou via PNCP_CLIENT_ID env)
            client_secret: OAuth Client Secret (ou via PNCP_CLIENT_SECRET env)
            use_auth: Se True, tenta autenticar; se False, usa apenas API pública
        """
        self.client_id = client_id or os.environ.get('PNCP_CLIENT_ID')
        self.client_secret = client_secret or os.environ.get('PNCP_CLIENT_SECRET')
        self.use_auth = use_auth and self.client_id and self.client_secret
        
        # Token de acesso
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0
        
        # Sessão HTTP persistente
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'GSM-Licitacoes/1.0 (Buscador de Editais)',
            'Accept': 'application/json',
            'Accept-Language': 'pt-BR,pt;q=0.9',
            'Origin': 'https://pncp.gov.br',
            'Referer': 'https://pncp.gov.br/'
        })
        
        # Cache de órgãos de saúde
        self.orgaos_saude = self._carregar_orgaos_saude()
        
        logger.info(f"🔧 [PNCP] Cliente inicializado. Modo: {'Autenticado' if self.use_auth else 'Público'}")
    
    def _carregar_orgaos_saude(self) -> List[Dict]:
        """Carrega lista de órgãos de saúde conhecidos"""
        return [
            {'cnpj': '00394544000145', 'nome': 'Ministério da Saúde', 'uf': 'DF'},
            {'cnpj': '26990000000119', 'nome': 'FIOCRUZ', 'uf': 'RJ'},
            {'cnpj': '61144955000130', 'nome': 'FUNASA', 'uf': 'DF'},
            {'cnpj': '33530486000109', 'nome': 'ANVISA', 'uf': 'DF'},
            {'cnpj': '00360305000104', 'nome': 'ANS', 'uf': 'RJ'},
            {'cnpj': '03426420000118', 'nome': 'Hospital das Clínicas SP', 'uf': 'SP'},
            {'cnpj': '60979457000167', 'nome': 'INCA', 'uf': 'RJ'},
            {'cnpj': '46374500000194', 'nome': 'Secretaria de Saúde SP', 'uf': 'SP'},
            {'cnpj': '42498600000100', 'nome': 'Secretaria de Saúde RS', 'uf': 'RS'},
            {'cnpj': '08778268000156', 'nome': 'Secretaria de Saúde MG', 'uf': 'MG'},
            {'cnpj': '10572022000108', 'nome': 'Secretaria de Saúde BA', 'uf': 'BA'},
            {'cnpj': '07954590000188', 'nome': 'Secretaria de Saúde CE', 'uf': 'CE'},
            {'cnpj': '10572013000108', 'nome': 'Secretaria de Saúde PE', 'uf': 'PE'},
        ]
    
    # =============================================
    # AUTENTICAÇÃO OAUTH 2.0
    # =============================================
    
    def _authenticate(self) -> bool:
        """
        Autentica com o PNCP via OAuth 2.0 Client Credentials
        
        Returns:
            True se autenticação bem-sucedida, False caso contrário
        """
        if not self.use_auth:
            logger.debug("  ℹ️ Autenticação desabilitada")
            return False
        
        logger.info("  🔐 Autenticando no PNCP...")
        
        try:
            payload = {
                'grant_type': 'client_credentials',
                'client_id': self.client_id,
                'client_secret': self.client_secret
            }
            
            response = self.session.post(
                self.AUTH_URL,
                data=payload,
                timeout=15,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            if response.status_code == 200:
                data = response.json()
                self._access_token = data.get('access_token')
                expires_in = data.get('expires_in', 3600)
                # Margem de segurança de 5%
                self._token_expiry = time.time() + (expires_in * 0.95)
                logger.info("  ✅ Autenticação PNCP bem-sucedida")
                return True
            else:
                logger.warning(f"  ⚠️ Falha na autenticação: HTTP {response.status_code}")
                self._access_token = None
                self._token_expiry = 0
                return False
                
        except requests.RequestException as e:
            logger.error(f"  ❌ Erro na autenticação: {str(e)}")
            self._access_token = None
            self._token_expiry = 0
            return False
    
    def _get_token(self) -> Optional[str]:
        """
        Retorna token de acesso válido, realizando refresh se necessário
        """
        if not self.use_auth:
            return None
        
        # Verificar se token está ausente ou expirado
        if not self._access_token or time.time() >= self._token_expiry:
            if not self._authenticate():
                return None
        
        return self._access_token
    
    def _invalidate_token(self):
        """Invalida o token atual para forçar refresh"""
        self._access_token = None
        self._token_expiry = 0
    
    def _get_headers(self) -> Dict[str, str]:
        """Retorna headers para requisição, incluindo token se disponível"""
        headers = dict(self.session.headers)
        
        token = self._get_token()
        if token:
            headers['Authorization'] = f'Bearer {token}'
        
        return headers
    
    # =============================================
    # REQUISIÇÕES HTTP
    # =============================================
    
    @retry_with_backoff(max_retries=5, initial_delay=1.0)
    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Faz requisição HTTP com retry e backoff
        
        Args:
            method: GET, POST, etc.
            endpoint: Endpoint da API (ex: /orgaos/{cnpj}/compras)
            params: Query parameters
            data: Body data para POST
            
        Returns:
            JSON response ou None
        """
        url = f"{self.BASE_URL}{endpoint}"
        headers = self._get_headers()
        
        response = self.session.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=data,
            timeout=30
        )
        
        response.raise_for_status()
        
        return response.json() if response.content else {}
    
    def _delay(self, seconds: float = None):
        """Rate limiting delay"""
        time.sleep(seconds or self.REQUEST_DELAY)
    
    # =============================================
    # BUSCA DE LICITAÇÕES (OTIMIZADO PARA PROSPECÇÃO FUTURA - P0)
    # =============================================
    
    async def buscar_licitacoes(
        self,
        termo_busca: str = None,
        apenas_futuras: bool = False,
        limit: int = 20
    ) -> List[Dict]:
        """
        Busca licitações no PNCP - OTIMIZADO PARA PROSPECÇÃO FUTURA
        
        Estratégia PROATIVA (v2.0 - Dezembro 2025):
        1. Prioriza busca de AVISOS/CONTRATAÇÕES com propostas abertas
        2. Aplica filtros de data e status NA REQUISIÇÃO (não pós-filtro)
        3. Usa endpoint de consulta pública otimizado
        
        Args:
            termo_busca: Termo para filtrar (ex: 'insulina')
            apenas_futuras: Se True, aplica filtros proativos para processos futuros
            limit: Número máximo de resultados
            
        Returns:
            Lista de licitações no formato padrão
        """
        resultados = []
        
        try:
            logger.info(f"🔍 [PNCP] Iniciando busca PROATIVA: '{termo_busca or 'geral'}' (apenas_futuras={apenas_futuras})")
            
            # ESTRATÉGIA 1: Buscar contratações com propostas ABERTAS (maior prioridade)
            if apenas_futuras:
                logger.info("  🚀 [PRIORIDADE] Buscando contratações com propostas ABERTAS...")
                resultados_abertos = await self._buscar_propostas_abertas(termo_busca, limit)
                resultados.extend(resultados_abertos)
                logger.info(f"  ✅ Propostas abertas: {len(resultados_abertos)} encontradas")
            
            # ESTRATÉGIA 2: Buscar publicações recentes (complementar)
            if len(resultados) < limit:
                logger.info("  📰 Buscando publicações recentes...")
                resultados_publicados = await self._buscar_publicacoes_recentes(
                    termo_busca, 
                    limit - len(resultados),
                    apenas_futuras=apenas_futuras
                )
                resultados.extend(resultados_publicados)
                logger.info(f"  ✅ Publicações recentes: {len(resultados_publicados)} encontradas")
            
            # ESTRATÉGIA 3: Fallback para órgãos conhecidos (se ainda não atingiu limite)
            if len(resultados) < limit and not apenas_futuras:
                logger.info("  📖 Complementando com órgãos conhecidos...")
                resultados_orgaos = await self._buscar_publico(termo_busca, limit - len(resultados))
                resultados.extend(resultados_orgaos)
            
            # Remover duplicatas por fonte_id
            resultados = self._remover_duplicatas(resultados)
            
            logger.info(f"🎯 [PNCP] Total processado: {len(resultados)} licitações (únicas)")
            return resultados[:limit]
            
        except Exception as e:
            logger.error(f"❌ [PNCP] Erro geral: {str(e)}")
            import traceback
            logger.debug(traceback.format_exc())
            return []
    
    async def _buscar_propostas_abertas(self, termo_busca: str, limit: int) -> List[Dict]:
        """
        NOVO: Busca PROATIVA de contratações com recebimento de propostas ABERTO
        
        Endpoint: /contratacoes/proposta ou /contratacoes com filtros
        Filtros aplicados NA REQUISIÇÃO:
        - dataAberturaProposta >= hoje
        - situacaoCompra = 'Publicado' ou 'Divulgada'
        """
        logger.info("  🔐 Buscando propostas abertas (filtros proativos)")
        
        resultados = []
        pagina = 1
        hoje = datetime.now()
        
        # Formato de data para API PNCP: YYYYMMDD ou ISO
        data_inicio = hoje.strftime('%Y%m%d')
        
        while len(resultados) < limit:
            try:
                # PARÂMETROS PROATIVOS - Filtros aplicados na requisição
                params = {
                    'pagina': pagina,
                    'tamanhoPagina': min(50, limit - len(resultados)),
                    # Filtro de data PROATIVO: apenas propostas que abrem HOJE ou no FUTURO
                    'dataAberturaPropostaInicial': data_inicio,
                    # Ordenar por data de abertura (mais próximas primeiro)
                    'ordenacao': 'dataAberturaPropostaAscendente'
                }
                
                if termo_busca:
                    params['q'] = termo_busca
                
                # Tentar endpoint de contratações com filtro
                response = self._make_request('GET', '/contratacoes', params=params)
                
                if not response:
                    # Fallback: tentar endpoint alternativo
                    response = self._make_request('GET', '/compras', params=params)
                
                if not response:
                    break
                
                # Extrair dados (a estrutura pode variar)
                compras = (
                    response.get('data', []) or 
                    response.get('dadosContratacoes', []) or 
                    response.get('dadosLicitacoes', []) or
                    response.get('resultado', [])
                )
                
                if not compras:
                    break
                
                for compra in compras:
                    # Validar se é realmente futuro (dupla verificação)
                    data_abertura = compra.get('dataAberturaProposta')
                    if data_abertura:
                        try:
                            dt_abertura = self._parse_date(data_abertura)
                            if dt_abertura and dt_abertura < hoje:
                                continue  # Pular se já passou
                        except:
                            pass
                    
                    # Verificar situação (apenas publicados/ativos)
                    situacao = compra.get('situacaoCompra', compra.get('situacao', '')).lower()
                    if situacao and any(s in situacao for s in ['encerrad', 'cancelad', 'revogad', 'anulad']):
                        continue  # Pular processos encerrados
                    
                    licitacao = self._processar_compra(compra)
                    if licitacao:
                        # Marcar como processo futuro/aberto
                        licitacao['status'] = 'Aberto'
                        licitacao['tags'].append('proposta_aberta')
                        resultados.append(licitacao)
                
                # Verificar se há mais páginas
                total_paginas = response.get('quantidadePaginas', response.get('totalPaginas', 1))
                if pagina >= total_paginas:
                    break
                    
                pagina += 1
                self._delay(0.8)
                
            except Exception as e:
                logger.error(f"  ❌ Erro na busca de propostas abertas: {str(e)}")
                break
        
        return resultados[:limit]
    
    async def _buscar_publicacoes_recentes(
        self, 
        termo_busca: str, 
        limit: int,
        apenas_futuras: bool = False
    ) -> List[Dict]:
        """
        NOVO: Busca publicações recentes com filtros de status
        
        Estratégia: Buscar por data de publicação recente e filtrar por situação ativa
        """
        logger.info("  📰 Buscando publicações recentes (últimos 30 dias)")
        
        resultados = []
        pagina = 1
        hoje = datetime.now()
        
        # Buscar publicações dos últimos 30 dias
        data_inicio = (hoje - timedelta(days=30)).strftime('%Y%m%d')
        
        while len(resultados) < limit:
            try:
                params = {
                    'pagina': pagina,
                    'tamanhoPagina': min(50, limit - len(resultados)),
                    'dataPublicacaoPncpInicial': data_inicio,
                    'ordenacao': 'dataPublicacaoPncpDescendente'
                }
                
                if termo_busca:
                    params['q'] = termo_busca
                
                response = self._make_request('GET', '/contratacoes/publicacao', params=params)
                
                if not response:
                    response = self._make_request('GET', '/compras', params=params)
                
                if not response:
                    break
                
                compras = (
                    response.get('data', []) or 
                    response.get('dadosContratacoes', []) or 
                    response.get('resultado', [])
                )
                
                if not compras:
                    break
                
                for compra in compras:
                    # Se apenas_futuras, verificar data de abertura
                    if apenas_futuras:
                        data_abertura = compra.get('dataAberturaProposta')
                        if data_abertura:
                            try:
                                dt_abertura = self._parse_date(data_abertura)
                                if dt_abertura and dt_abertura < hoje:
                                    continue  # Pular se já passou
                            except:
                                pass
                        
                        # Verificar situação
                        situacao = compra.get('situacaoCompra', '').lower()
                        if situacao and any(s in situacao for s in ['encerrad', 'cancelad', 'revogad']):
                            continue
                    
                    licitacao = self._processar_compra(compra)
                    if licitacao:
                        resultados.append(licitacao)
                
                total_paginas = response.get('quantidadePaginas', 1)
                if pagina >= total_paginas:
                    break
                    
                pagina += 1
                self._delay(0.8)
                
            except Exception as e:
                logger.error(f"  ❌ Erro na busca de publicações: {str(e)}")
                break
        
        return resultados[:limit]
    
    async def _buscar_autenticado(self, termo_busca: str, limit: int) -> List[Dict]:
        """
        Busca autenticada com acesso completo à API
        
        Usa endpoint de busca com filtros avançados
        """
        logger.info("  🔐 Usando modo autenticado")
        
        resultados = []
        pagina = 1
        
        while len(resultados) < limit:
            try:
                # Endpoint de busca (verificar documentação oficial)
                params = {
                    'pagina': pagina,
                    'tamanhoPagina': min(50, limit - len(resultados)),
                    'ordenacao': 'dataPublicacaoDescendente'
                }
                
                if termo_busca:
                    params['q'] = termo_busca
                
                response = self._make_request('GET', '/compras', params=params)
                
                if not response or 'data' not in response:
                    break
                
                compras = response.get('data', [])
                
                if not compras:
                    break
                
                for compra in compras:
                    licitacao = self._processar_compra(compra)
                    if licitacao:
                        resultados.append(licitacao)
                
                pagina += 1
                self._delay(0.8)
                
            except Exception as e:
                logger.error(f"  ❌ Erro na busca autenticada: {str(e)}")
                break
        
        return resultados[:limit]
    
    async def _buscar_publico(self, termo_busca: str, limit: int) -> List[Dict]:
        """
        Busca pública em órgãos de saúde conhecidos
        
        Estratégia de fallback quando não há autenticação
        """
        logger.info("  📖 Usando modo público (órgãos conhecidos)")
        
        resultados = []
        ano_atual = datetime.now().year
        
        for orgao in self.orgaos_saude:
            if len(resultados) >= limit:
                break
            
            try:
                cnpj = orgao['cnpj']
                nome = orgao['nome']
                
                logger.debug(f"    Consultando: {nome}")
                
                # Buscar compras do órgão
                response = self._make_request(
                    'GET',
                    f'/orgaos/{cnpj}/compras/{ano_atual}',
                    params={'pagina': 1, 'tamanhoPagina': 10}
                )
                
                if not response:
                    continue
                
                compras = response.get('data', [])
                
                for compra in compras:
                    # Filtrar por termo de busca
                    objeto = compra.get('objetoCompra', '').lower()
                    
                    if termo_busca and termo_busca.lower() not in objeto:
                        continue
                    
                    # Processar compra
                    compra['orgao_info'] = orgao  # Adicionar info do órgão
                    licitacao = self._processar_compra(compra)
                    
                    if licitacao:
                        resultados.append(licitacao)
                
                self._delay(1.0)
                
            except Exception as e:
                logger.debug(f"    ⚠️ {orgao['nome']}: {str(e)}")
                continue
        
        return resultados[:limit]
    
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
    
    def _processar_compra(self, compra: Dict) -> Optional[Dict]:
        """
        Processa dados de compra para formato padrão
        """
        try:
            # Extrair dados básicos
            cnpj = compra.get('cnpjOrgao', compra.get('orgao_info', {}).get('cnpj', ''))
            ano = compra.get('anoCompra', datetime.now().year)
            sequencial = compra.get('sequencialCompra', '')
            
            if not cnpj or not sequencial:
                return None
            
            # Órgão
            orgao_entidade = compra.get('orgaoEntidade', compra.get('orgao_info', {}))
            razao_social = orgao_entidade.get('razaoSocial', orgao_entidade.get('nome', 'Órgão não identificado'))
            uf = orgao_entidade.get('uf', 'BR')
            
            # Datas
            data_pub = compra.get('dataPublicacaoPncp')
            data_abertura = compra.get('dataAberturaProposta')
            data_encerramento = compra.get('dataEncerramentoProposta')
            
            # Converter datas
            data_publicacao_dt = self._parse_date(data_pub)
            data_abertura_dt = self._parse_date(data_abertura)
            data_final_dt = self._parse_date(data_encerramento)
            
            # Objeto
            objeto = compra.get('objetoCompra', 'Objeto não especificado')
            
            # Modalidade
            modalidade = compra.get('modalidadeNome', compra.get('modalidade', 'Não informada'))
            
            # Status - OTIMIZADO para prospecção (usa data_abertura)
            situacao = compra.get('situacaoCompra', 'Em andamento')
            status = self._determinar_status(data_final_dt, situacao, data_abertura_dt)
            
            # Número do processo
            numero_processo = compra.get('numeroControlePNCP', f'{ano}/{sequencial}')
            
            # Links
            link_origem = f"{self.APP_URL}/editais/{cnpj}/{ano}/{sequencial}"
            
            # Gerar ID único
            import uuid
            licitacao_id = str(uuid.uuid4())
            
            return {
                'id': licitacao_id,
                'medicamento': self._extrair_medicamento(objeto),
                'principio_ativo': None,
                'estado': uf,
                'estado_uf': uf,
                'status': status,
                'status_aquisicao': status,
                'orgao_licitante': razao_social,
                'modalidade': modalidade,
                'numero_processo': numero_processo,
                
                # Datas
                'data_referencia': data_publicacao_dt or datetime.now(),
                'data_abertura': data_abertura_dt,
                'data_inicial': data_abertura_dt,
                'data_final': data_final_dt,
                'data_limite': data_final_dt,
                'data_publicacao': data_publicacao_dt,
                
                # Links
                'link_origem': link_origem,
                'link_documento': None,
                
                # Metadados
                'fonte_nome': 'PNCP - Portal Nacional de Contratações Públicas',
                'fonte_id': f'pncp-{cnpj}-{ano}-{sequencial}',
                'numero_pregao': numero_processo,
                'uasg': cnpj,
                'esfera': self._determinar_esfera(orgao_entidade, uf),
                'objeto': objeto[:500],
                
                # Itens
                'itens': [],
                
                # Tags
                'tags': self._extrair_tags(objeto),
                'is_mock': False,
                'fonte': 'PNCP'
            }
            
        except Exception as e:
            logger.error(f"    ❌ Erro ao processar compra: {str(e)}")
            return None
    
    # =============================================
    # HELPERS
    # =============================================
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Converte string de data para datetime"""
        if not date_str:
            return None
        try:
            clean_str = date_str.replace('Z', '').replace('+00:00', '')
            return datetime.fromisoformat(clean_str)
        except (ValueError, AttributeError):
            return None
    
    def _determinar_status(
        self, 
        data_final: Optional[datetime], 
        situacao_api: Optional[str],
        data_abertura: Optional[datetime] = None
    ) -> str:
        """
        Determina status da licitação - OTIMIZADO PARA PROSPECÇÃO
        
        Hierarquia de decisão:
        1. Se data_abertura > hoje: 'Agendado' (FUTURO)
        2. Se data_abertura <= hoje < data_final: 'Aberto' (EM ANDAMENTO)
        3. Se data_final < hoje: 'Encerrado'
        4. Fallback para situação da API
        """
        hoje = datetime.now()
        
        # PRIORIDADE 1: Verificar se é processo FUTURO (agendado)
        if data_abertura and data_abertura > hoje:
            return 'Agendado'
        
        # PRIORIDADE 2: Verificar se está ABERTO (em andamento)
        if data_final:
            if data_final > hoje:
                # Se data_abertura já passou ou não existe, está aberto
                if not data_abertura or data_abertura <= hoje:
                    return 'Aberto'
                else:
                    return 'Agendado'
            else:
                return 'Encerrado'
        
        # PRIORIDADE 3: Usar situação da API
        if situacao_api:
            situacao_lower = situacao_api.lower()
            
            # Status de PROCESSO FUTURO/ABERTO (alta prioridade)
            if any(s in situacao_lower for s in ['publicad', 'divulgad', 'aberto', 'recebendo']):
                return 'Aberto'
            elif 'agendad' in situacao_lower:
                return 'Agendado'
            # Status de PROCESSO EM ANDAMENTO
            elif any(s in situacao_lower for s in ['andamento', 'ativo', 'vigente']):
                return 'Em Andamento'
            # Status de PROCESSO ENCERRADO
            elif any(s in situacao_lower for s in ['encerrad', 'finaliz', 'concluíd', 'concluido', 'homolog', 'adjudic']):
                return 'Encerrado'
            # Status de PROCESSO CANCELADO
            elif any(s in situacao_lower for s in ['cancelad', 'revogad', 'anulad', 'desert', 'fracassad']):
                return 'Cancelado'
        
        return 'Em Licitação'
    
    def _determinar_esfera(self, orgao: Dict, uf: str) -> str:
        """Determina esfera administrativa"""
        razao = orgao.get('razaoSocial', orgao.get('nome', '')).lower()
        
        if 'federal' in razao or 'ministério' in razao or 'ministerio' in razao:
            return 'Federal'
        elif 'municipal' in razao or 'prefeitura' in razao:
            return 'Municipal'
        elif uf and uf != 'BR':
            return 'Estadual'
        
        return 'Não identificada'
    
    def _extrair_medicamento(self, texto: str) -> str:
        """Extrai nome do medicamento do objeto"""
        if not texto:
            return 'Não especificado'
        
        texto_lower = texto.lower()
        
        medicamentos = [
            'adalimumabe', 'pembrolizumabe', 'insulina', 'metformina',
            'omeprazol', 'paracetamol', 'dipirona', 'amoxicilina',
            'losartana', 'atorvastatina', 'semaglutida', 'canabidiol',
            'azitromicina', 'dexametasona', 'ivermectina', 'hidroxicloroquina'
        ]
        
        for med in medicamentos:
            if med in texto_lower:
                return med.capitalize()
        
        if any(kw in texto_lower for kw in ['medicamento', 'fármaco', 'hospitalar']):
            return 'Medicamento (ver objeto)'
        
        return 'Não especificado'
    
    def _extrair_tags(self, texto: str) -> List[str]:
        """Extrai tags do objeto"""
        texto_lower = texto.lower()
        tags = []
        
        if any(k in texto_lower for k in ['alto custo', 'especializado', 'ceaf']):
            tags.append('alto_custo')
        if any(k in texto_lower for k in ['hospitalar', 'hospital']):
            tags.append('hospitalar')
        if any(k in texto_lower for k in ['urgente', 'emergência']):
            tags.append('urgente')
        if any(k in texto_lower for k in ['registro de preço', 'ata de registro']):
            tags.append('registro_precos')
        
        return tags
    
    # Método de compatibilidade com interface antiga
    async def scrape(self, medicamento: str = None) -> List[Dict]:
        """Método de compatibilidade"""
        return await self.buscar_licitacoes(termo_busca=medicamento)
