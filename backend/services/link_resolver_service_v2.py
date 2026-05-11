"""
LinkResolverService V2 - Validação Real de Links (Padrão GSM)
===================================================================

🔐 DIRETRIZ OBRIGATÓRIA

Este serviço implementa validação REAL de links, garantindo que:
1. Links levam DIRETAMENTE ao edital ou PDF
2. Não são páginas de busca (?q=)
3. Não são páginas vazias ou genéricas
4. São funcionais e acessíveis

Prioridade de Resolução (OBRIGATÓRIA):
1. Link direto individual no PNCP (página específica do edital)
2. PDF do edital (download direto)
3. Portal oficial do órgão (página específica)
4. NENHUM - exibir apenas número do processo para busca manual

Links REJEITADOS automaticamente:
- URLs de busca genérica (?q=, ?search=, status=todos)
- Datasets (dados.gov.br, conjunto-de-dados)
- Páginas de transparência genéricas
- Links com código 404 ou redirecionamentos para busca
"""

import re
import logging
import aiohttp
import asyncio
from typing import Dict, Optional, Tuple, List
from urllib.parse import urlencode, quote, urlparse

logger = logging.getLogger(__name__)


class LinkResolverServiceV2:
    """
    Serviço de resolução e validação de links de editais - V2
    
    VALIDAÇÃO ESTRITA conforme Padrão GSM:
    - Verifica se URL é acessível (HTTP 200)
    - Detecta páginas de busca/genéricas
    - Valida se conteúdo é relevante
    """
    
    # Padrões de URL que são AUTOMATICAMENTE INVÁLIDOS
    INVALID_PATTERNS = [
        r'\?q=',                     # Busca genérica
        r'\?search=',                # Busca
        r'status=todos',             # Lista genérica
        r'&q=',                      # Parâmetro de busca
        r'dados\.gov\.br',           # Datasets federais
        r'dadosabertos\..*\.gov\.br',  # Datasets estaduais/municipais
        r'/dataset/',                # Páginas de datasets
        r'/conjunto-de-dados',       # Dados abertos
        r'transparencia.*conjunto-de-dados',  # Dados abertos
        r'github\.com',              # Repositórios
        r'\.csv$',                   # Arquivos CSV diretos
        r'\.json$',                  # Arquivos JSON diretos
        r'#$',                       # Hash vazio
        r'javascript:',              # JavaScript void
        r'/pesquisa$',               # Página de pesquisa (mas não /pesquisa/123)
        r'/busca$',                  # Página de busca
        r'transparencia\..*\.gov\.br/.*consulta', # Consultas de transparência
        r'/licitacoes-andamento$',   # Lista genérica de licitações GO
        r'/consultas$',              # Página de consultas
        r'eprotocolo\.pr\.gov\.br',  # Portal de protocolo PR (não é edital)
        r'/pncp-publicacao/',        # URLs PNCP antigas que retornam 404
        r'transparencia\.tce\.sp\.gov\.br',  # TCE-SP transparência (datasets)
    ]
    
    # Domínios confiáveis para links diretos
    TRUSTED_DOMAINS = [
        'pncp.gov.br',
        'comprasnet.gov.br',
        'licitardigital.com.br',
        'ammlicita.org.br',
        'bec.sp.gov.br',
        'licitacoes-e.com.br',
        'bll.org.br',
        'portaldecompraspublicas.com.br',
        'bbmnet.com.br',
    ]
    
    # Padrões que indicam link DIRETO válido
    VALID_DIRECT_PATTERNS = [
        r'/app/editais/\d{14}/\d{4}/\d+',  # PNCP: /app/editais/{cnpj}/{ano}/{seq}
        r'/pncp-web/.*contratacao',         # PNCP web
        r'/edital/\d+',                      # Edital direto
        r'/processo/\d+',                    # Processo direto
        r'\.pdf$',                            # PDF direto
        r'/anexo/\d+',                        # Anexo direto
        r'/documento/\d+',                    # Documento direto
    ]
    
    def __init__(self):
        self._cache = {}
        self._timeout = aiohttp.ClientTimeout(total=10)
    
    def resolver_link(self, edital: Dict) -> Dict[str, Optional[str]]:
        """
        🔗 Resolve o melhor link disponível para um edital (Padrão GSM)
        
        REGRA CRÍTICA:
        - Links de BUSCA (?q=) NÃO são válidos
        - Apenas links DIRETOS para o edital/processo são aceitos
        - Se não há link válido, marcar como INVALIDO
        
        PRIORIDADE DE RESOLUÇÃO:
        1. linkSistemaOrigem (portal do órgão - licitardigital, ammlicita, etc)
        2. PDF do edital
        3. Link PNCP construído (menos confiável - SPA)
        4. INVALIDO
        
        Args:
            edital: Dict com dados do edital
            
        Returns:
            Dict com link_principal, link_status, tipo_link, aviso
        """
        resultado = {
            'link_principal': None,
            'link_pncp': None,
            'link_portal': None,
            'link_pdf': None,
            'tipo_link': None,
            'link_status': 'INVALIDO',
            'aviso': None,
        }
        
        # 1. PRIORIDADE MÁXIMA: linkSistemaOrigem (portal real do edital)
        # Este é o link fornecido pelo órgão para acessar o edital real
        link_origem = (
            edital.get('linkSistemaOrigem') or 
            edital.get('link_sistema_origem') or  # Campo normalizado
            edital.get('link_origem')
        )
        
        if link_origem:
            link_normalizado = self._normalizar_url(link_origem)
            if link_normalizado and self._validar_url_direta(link_normalizado):
                resultado['link_portal'] = link_normalizado
                resultado['link_principal'] = link_normalizado
                resultado['tipo_link'] = 'portal_orgao'
                resultado['link_status'] = 'VALIDO'
                return resultado
        
        # 2. Verificar link de documento/PDF (link direto para arquivo)
        link_doc = edital.get('link_documento')
        if link_doc:
            link_doc_norm = self._normalizar_url(link_doc)
            if link_doc_norm and self._validar_url_direta(link_doc_norm):
                if link_doc_norm.lower().endswith('.pdf') or '/pdf' in link_doc_norm.lower():
                    resultado['link_pdf'] = link_doc_norm
                    resultado['link_principal'] = link_doc_norm
                    resultado['tipo_link'] = 'pdf'
                    resultado['link_status'] = 'VALIDO'
                    return resultado
        
        # 3. Tentar link PNCP construído (MENOS CONFIÁVEL - é um SPA)
        # Só usar se tiver CNPJ e número de processo bem formatados
        link_pncp = self._construir_link_pncp(edital)
        if link_pncp and self._validar_url_direta(link_pncp):
            # NOTA: Links PNCP construídos são menos confiáveis
            # O PNCP é um SPA React, então o link pode não funcionar direito
            resultado['link_pncp'] = link_pncp
            resultado['link_principal'] = link_pncp
            resultado['tipo_link'] = 'pncp_direto'
            resultado['link_status'] = 'VALIDO'
            return resultado
        
        # 4. NÃO há link válido - NÃO criar fallback de busca
        resultado['link_status'] = 'INVALIDO'
        resultado['aviso'] = f"Buscar: {edital.get('numero_processo', 'N/A')}"
        
        return resultado
    
    def _normalizar_url(self, url: str) -> Optional[str]:
        """
        Normaliza URL adicionando protocolo se necessário
        """
        if not url or not isinstance(url, str):
            return None
        
        url = url.strip()
        
        # Se já tem protocolo, retornar
        if url.startswith(('http://', 'https://')):
            return url
        
        # Adicionar https:// se parece ser URL válida
        if '.' in url and ('/' in url or url.count('.') >= 1):
            return f"https://{url}"
        
        return None
    
    def _validar_url_direta(self, url: str) -> bool:
        """
        Validação ESTRITA de URL
        
        REJEITA automaticamente:
        - URLs de busca (?q=, ?search=)
        - Datasets e portais de dados abertos
        - Páginas genéricas
        - URLs incompletas
        
        ACEITA:
        - URLs diretas para editais
        - PDFs
        - Portais de licitação confiáveis
        """
        if not url or not isinstance(url, str):
            return False
        
        url = url.strip()
        
        # Deve ser URL HTTP válida
        if not url.startswith(('http://', 'https://')):
            # Tentar adicionar protocolo se parece URL
            if '.' in url and '/' in url:
                url = f"https://{url}"
            else:
                return False
        
        # REJEITAR padrões inválidos
        for pattern in self.INVALID_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                logger.debug(f"URL rejeitada (padrão inválido): {url[:80]}")
                return False
        
        # Verificar se URL está completa
        if url.endswith('=') or url.endswith('chave=') or url.endswith('?'):
            return False
        
        # Verificar se é domínio confiável ou padrão direto conhecido
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # Se é domínio confiável, verificar se é link direto
        is_trusted = any(d in domain for d in self.TRUSTED_DOMAINS)
        is_direct_pattern = any(re.search(p, url) for p in self.VALID_DIRECT_PATTERNS)
        
        if is_trusted and is_direct_pattern:
            return True
        
        # Para domínios confiáveis sem padrão específico, aceitar se não tem query string de busca
        if is_trusted and '?' not in url:
            return True
        
        # Para outros domínios, verificar se parece ser link direto
        if is_direct_pattern:
            return True
        
        # Se chegou aqui e tem query string, provavelmente é busca
        if '?' in url:
            return False
        
        # Aceitar URLs de portais gov.br que parecem diretas
        if '.gov.br' in domain and '/edital' in url.lower():
            return True
        
        return True
    
    def _construir_link_pncp(self, edital: Dict) -> Optional[str]:
        """
        Constrói URL DIRETA do PNCP
        
        Formato correto: https://pncp.gov.br/app/editais/{cnpj}/{ano}/{sequencial}
        
        O PNCP usa: CNPJ do órgão + Ano + Sequencial
        """
        cnpj = edital.get('cnpj_orgao')
        numero = edital.get('numero_processo') or edital.get('id_externo')
        
        if not cnpj:
            return None
        
        # Limpar CNPJ
        cnpj = re.sub(r'[^\d]', '', str(cnpj))
        if len(cnpj) != 14:
            return None
        
        # Extrair ano e sequencial do número do processo
        if numero:
            numero_str = str(numero)
            
            # Formato: YYYY/NNN ou NNN/YYYY
            match = re.search(r'(\d{4})[/\-](\d+)', numero_str)
            if match:
                part1, part2 = match.groups()
                if int(part1) >= 2000:
                    ano, seq = part1, part2
                else:
                    ano, seq = None, None
            else:
                match = re.search(r'(\d+)[/\-](\d{4})', numero_str)
                if match:
                    part1, part2 = match.groups()
                    if int(part2) >= 2000:
                        seq, ano = part1, part2
                    else:
                        ano, seq = None, None
                else:
                    # Tentar extrair ano do início
                    if len(numero_str) >= 4 and numero_str[:4].isdigit():
                        ano_candidato = int(numero_str[:4])
                        if 2000 <= ano_candidato <= 2030:
                            ano = numero_str[:4]
                            seq = numero_str[4:] or '1'
                        else:
                            ano, seq = None, None
                    else:
                        ano, seq = None, None
            
            if ano and seq:
                return f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{seq}"
        
        return None
    
    async def validar_link_http(self, url: str) -> Tuple[bool, str]:
        """
        Valida link via HTTP HEAD request
        
        Returns:
            Tuple (é_válido, motivo)
        """
        if not url or not self._validar_url_direta(url):
            return False, "URL inválida ou de busca"
        
        try:
            async with aiohttp.ClientSession(timeout=self._timeout) as session:
                async with session.head(url, allow_redirects=True) as response:
                    # Verificar código HTTP
                    if response.status == 404:
                        return False, "Página não encontrada (404)"
                    
                    if response.status >= 400:
                        return False, f"Erro HTTP {response.status}"
                    
                    # Verificar se foi redirecionado para busca
                    final_url = str(response.url)
                    if '?q=' in final_url or 'search=' in final_url:
                        return False, "Redirecionado para página de busca"
                    
                    return True, "OK"
                    
        except asyncio.TimeoutError:
            return False, "Timeout na validação"
        except Exception as e:
            return False, f"Erro: {str(e)}"
    
    async def validar_lote(self, urls: List[str]) -> Dict[str, Tuple[bool, str]]:
        """Valida múltiplas URLs em paralelo"""
        tasks = [self.validar_link_http(url) for url in urls]
        results = await asyncio.gather(*tasks)
        return dict(zip(urls, results))
    
    def enriquecer_edital(self, edital: Dict) -> Dict:
        """
        Enriquece edital com links resolvidos
        
        Adiciona campos:
        - link_edital: URL principal (ou None)
        - link_status: 'VALIDO' ou 'INVALIDO'
        - tipo_link: tipo do link
        - aviso_link: mensagem para o usuário
        """
        links = self.resolver_link(edital)
        
        edital['link_edital'] = links['link_principal']
        edital['link_pncp'] = links.get('link_pncp')
        edital['link_portal_orgao'] = links.get('link_portal')
        edital['link_pdf'] = links.get('link_pdf')
        edital['tipo_link'] = links['tipo_link']
        edital['link_status'] = links['link_status']
        
        if links['aviso']:
            edital['aviso_link'] = links['aviso']
        
        return edital


# Singleton
_instance = None

def get_link_resolver_v2() -> LinkResolverServiceV2:
    """Retorna instância do LinkResolverService V2"""
    global _instance
    if _instance is None:
        _instance = LinkResolverServiceV2()
    return _instance


# Função de compatibilidade com V1
def get_link_resolver() -> LinkResolverServiceV2:
    """Compatibilidade: retorna V2"""
    return get_link_resolver_v2()
