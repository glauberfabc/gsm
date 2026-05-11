"""
LinkResolverService - Resolução de Links de Editais
====================================================

🔐 DIRETRIZ OBRIGATÓRIA (Padrão Portal)

Este serviço centraliza TODA a lógica de resolução de links de editais,
garantindo que o usuário SEMPRE consiga acessar o processo real.

Regra de Ouro: Link Útil ou Nada
- É proibido exibir links para datasets, portais de dados abertos ou páginas genéricas
- Se não houver link útil, indicar claramente ou usar fallback do PNCP

Prioridade de Resolução (OBRIGATÓRIA):
1. Link direto do processo no PNCP
2. Página oficial do processo no portal do órgão
3. PDF do edital ou aviso
4. Fallback documentado (portal do órgão com orientação)

Baseado no padrão Portal - Sistema de referência para licitações.

Autor: GSM Buscador de Editais
Data: 2025-12-18
"""

import re
import logging
from typing import Dict, Optional, Tuple
from urllib.parse import urlencode, quote

logger = logging.getLogger(__name__)


class LinkResolverService:
    """
    Serviço centralizado para resolução de links de editais.
    
    TODA resolução de link deve passar por este serviço.
    Nenhum outro componente deve construir URLs de editais diretamente.
    """
    
    # Padrões de URL por portal/fonte
    PORTAL_PATTERNS = {
        # PNCP - Portal Nacional de Contratações Públicas
        'pncp': {
            'base': 'https://pncp.gov.br/app/editais',
            'busca': 'https://pncp.gov.br/app/editais?q={query}',
            'detalhe': 'https://pncp.gov.br/app/editais/{cnpj}/{ano}/{sequencial}',
        },
        # ComprasNet - Portal Federal
        'comprasnet': {
            'base': 'https://cnetmobile.estaleiro.serpro.gov.br',
            'pregao': 'https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/public/compras/acompanhamento-compra?compra={uasg}/{numero}/{ano}',
            'busca': 'https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/public/compras?q={query}',
        },
        # Licitações-e (Banco do Brasil)
        'licitacoes_e': {
            'base': 'https://www.licitacoes-e.com.br',
            'detalhe': 'https://www.licitacoes-e.com.br/aop/lct/licitacao/consulta.do?licitacao={numero}',
        },
        # BEC/SP - Bolsa Eletrônica de Compras SP
        'bec_sp': {
            'base': 'https://www.bec.sp.gov.br',
            'busca': 'https://www.bec.sp.gov.br/BEC_Pesquisa_OC.aspx?chave={numero}',
        },
        # Portais Estaduais
        'mg': {
            'base': 'https://www.compras.mg.gov.br',
            'busca': 'https://www.compras.mg.gov.br/index.php?option=com_pesquisa&view=pesquisa&Itemid=105&q={query}',
        },
        'sp_tce': {
            'base': 'https://www.tce.sp.gov.br',
            'transparencia': 'https://www.transparencia.tce.sp.gov.br/conjunto-de-dados',
        },
        'pr': {
            'base': 'https://www.comprasparana.pr.gov.br',
            'busca': 'https://www.comprasparana.pr.gov.br/consultas?q={query}',
        },
        'go': {
            'base': 'https://www.comprasgovernamentais.go.gov.br',
        },
    }
    
    # URLs inválidas que devem ser rejeitadas
    INVALID_URL_PATTERNS = [
        r'dados\.gov\.br',  # Datasets
        r'transparencia.*conjunto-de-dados',  # Portais de dados abertos
        r'github\.com',  # Repositórios
        r'\.csv$',  # Arquivos CSV diretos
        r'\.json$',  # Arquivos JSON diretos
        r'#$',  # Hash vazio
        r'javascript:',  # JavaScript void
    ]
    
    def __init__(self):
        """Inicializa o serviço de resolução de links."""
        self._cache = {}  # Cache de links resolvidos
    
    def resolver_link(self, edital: Dict) -> Dict[str, Optional[str]]:
        """
        🔗 Resolve o melhor link disponível para um edital (Padrão Portal)
        
        REGRA CRÍTICA:
        - Links de BUSCA (?q=) NÃO são válidos
        - Apenas links DIRETOS para o edital/processo são aceitos
        - Se não há link válido, marcar como INVALIDO
        
        Prioridade obrigatória:
        1. Link DIRETO do processo no PNCP (/pncp-publicacao/{cnpj}/{ano}/{seq})
        2. Link do sistema de origem (linkSistemaOrigem - portal do órgão)
        3. PDF do edital ou aviso
        4. NENHUM link (status INVALIDO) - NÃO usar busca como fallback
        
        Args:
            edital: Dict com dados do edital
            
        Returns:
            Dict com:
                - link_principal: URL principal (ou None se inválido)
                - link_status: 'VALIDO' ou 'INVALIDO'
                - tipo_link: 'pncp_direto', 'portal_orgao', 'pdf', None
                - aviso: Mensagem explicativa
        """
        resultado = {
            'link_principal': None,
            'link_pncp': None,
            'link_portal': None,
            'link_pdf': None,
            'link_fallback': None,
            'tipo_link': None,
            'link_status': 'INVALIDO',  # Default: inválido até provar contrário
            'aviso': None,
        }
        
        # Extrair dados do edital
        link_documento = edital.get('link_documento') or edital.get('linkSistemaOrigem')
        
        # 1. Tentar link DIRETO do PNCP (PRIORIDADE MÁXIMA)
        link_pncp = self._resolver_pncp(edital)
        if link_pncp and self._validar_url_estrita(link_pncp):
            resultado['link_pncp'] = link_pncp
            resultado['link_principal'] = link_pncp
            resultado['tipo_link'] = 'pncp_direto'
            resultado['link_status'] = 'VALIDO'
            return resultado
        
        # 2. Tentar link do sistema de origem (portal do órgão)
        link_portal = self._resolver_portal(edital)
        if link_portal and self._validar_url_estrita(link_portal):
            resultado['link_portal'] = link_portal
            resultado['link_principal'] = link_portal
            resultado['tipo_link'] = 'portal_orgao'
            resultado['link_status'] = 'VALIDO'
            return resultado
        
        # 3. Verificar link de documento/PDF
        if link_documento and self._validar_url_estrita(link_documento):
            resultado['link_pdf'] = link_documento
            resultado['link_principal'] = link_documento
            resultado['tipo_link'] = 'pdf'
            resultado['link_status'] = 'VALIDO'
            return resultado
        
        # 4. NÃO há link válido - marcar como INVALIDO
        # NÃO usar busca (?q=) como fallback - isso engana o usuário
        resultado['link_status'] = 'INVALIDO'
        resultado['aviso'] = 'Link direto para edital não disponível. Buscar manualmente pelo número do processo.'
        
        return resultado
    
    def _validar_url_estrita(self, url: str) -> bool:
        """
        Validação ESTRITA de URL (Padrão Portal)
        
        REJEITA:
        - URLs de busca (?q=, ?search=, etc)
        - Datasets e portais de dados abertos
        - Páginas genéricas
        
        ACEITA:
        - URLs diretas para editais
        - URLs do sistema de origem
        - PDFs
        """
        if not url or not isinstance(url, str):
            return False
        
        url = url.strip()
        
        # Deve ser URL HTTP válida
        if not url.startswith(('http://', 'https://')):
            return False
        
        # REJEITAR padrões de busca
        busca_patterns = [
            r'\?q=',           # Busca genérica
            r'\?search=',      # Busca
            r'status=todos',   # Lista genérica
            r'&q=',            # Parâmetro de busca
        ]
        for pattern in busca_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                logger.debug(f"URL rejeitada (padrão de busca): {url}")
                return False
        
        # REJEITAR padrões inválidos existentes
        for pattern in self.INVALID_URL_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                logger.debug(f"URL rejeitada (padrão inválido): {url}")
                return False
        
        # URL não está incompleta
        if url.endswith('=') or url.endswith('chave='):
            return False
        
        return True
    
    def _resolver_pncp(self, edital: Dict) -> Optional[str]:
        """
        🔗 Constrói URL DIRETA do PNCP para o edital (Padrão Portal)
        
        REGRA CRÍTICA: 
        - URLs de BUSCA (?q=) NÃO são válidas
        - Apenas URLs DIRETAS para o edital são aceitas
        
        Formatos válidos:
        - https://pncp.gov.br/pncp-publicacao/{cnpj}/{ano}/{sequencial}
        - Link do sistema de origem (linkSistemaOrigem)
        """
        # 1. Verificar se já tem link PNCP direto
        link_pncp_direto = edital.get('link_pncp_direto')
        if link_pncp_direto and ('/app/editais/' in link_pncp_direto or '/pncp-publicacao/' in link_pncp_direto):
            # Converter formato antigo se necessário
            if '/pncp-publicacao/' in link_pncp_direto:
                link_pncp_direto = link_pncp_direto.replace('/pncp-publicacao/', '/app/editais/')
            return link_pncp_direto
        
        # 2. Verificar link de origem (linkSistemaOrigem - portal do órgão)
        link_origem = edital.get('link_origem') or edital.get('link_documento')
        if link_origem and link_origem.startswith('http'):
            # REJEITAR links de busca e datasets
            if ('?q=' not in link_origem and 
                'status=todos' not in link_origem and
                'dados.gov.br' not in link_origem and
                'conjunto-de-dados' not in link_origem):
                return link_origem
        
        # 3. Obter CNPJ (do edital ou do mapeamento de municípios)
        cnpj = edital.get('cnpj_orgao')
        
        if not cnpj:
            # Tentar obter CNPJ do mapeamento de municípios
            municipio = edital.get('municipio')
            uf = edital.get('uf') or edital.get('estado')
            
            if municipio:
                try:
                    from data.municipios_cnpj import obter_cnpj_municipio
                    cnpj = obter_cnpj_municipio(municipio, uf)
                except ImportError:
                    pass
        
        # 4. Tentar construir URL DIRETA com CNPJ + processo
        numero_processo = edital.get('numero_processo')
        
        if cnpj and numero_processo:
            numero_str = str(numero_processo)
            ano = None
            sequencial = None
            
            # Formato 1: YYYY/NNNN ou NNNN/YYYY
            match = re.search(r'(\d{4})[/\-](\d+)', numero_str)
            if not match:
                match = re.search(r'(\d+)[/\-](\d{4})', numero_str)
            
            if match:
                part1, part2 = match.groups()
                # Determinar qual é ano e qual é sequencial
                if len(part1) == 4 and int(part1) >= 2000:
                    ano, sequencial = part1, part2
                else:
                    ano, sequencial = part2, part1
            
            # Formato 2: Número contínuo começando com ano (ex: 2024240500834)
            elif len(numero_str) >= 8 and numero_str[:4].isdigit():
                ano_candidato = numero_str[:4]
                if 2000 <= int(ano_candidato) <= 2030:
                    ano = ano_candidato
                    sequencial = numero_str[4:]
            
            if ano and sequencial:
                # URL direta do PNCP (formato correto: /app/editais/{cnpj}/{ano}/{seq})
                return f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{sequencial}"
        
        # 5. Sem link válido disponível
        return None
    
    def _resolver_portal(self, edital: Dict) -> Optional[str]:
        """
        Resolve URL do portal específico do órgão.
        
        Suporta:
        - ComprasNet (Federal)
        - BEC/SP
        - Compras MG
        - Compras Paraná
        - Licitações-e
        """
        fonte = (edital.get('fonte') or '').upper()
        link_origem = edital.get('link_origem')
        numero = edital.get('numero_processo') or edital.get('numero_pregao')
        uasg = edital.get('uasg')
        
        # Se já tem link de origem válido, usar
        if link_origem and self._validar_url(link_origem):
            return link_origem
        
        # ComprasNet
        if 'COMPRASNET' in fonte and uasg and numero:
            # Extrair ano do número
            match = re.search(r'(\d+)[/\-](\d{4})', str(numero))
            if match:
                num = match.group(1)
                ano = match.group(2)
                return f"https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/public/compras/acompanhamento-compra?compra={uasg}/{num}/{ano}"
        
        # BEC/SP
        if 'BEC' in fonte or 'SP' in fonte:
            if numero:
                return f"https://www.bec.sp.gov.br/BEC_Pesquisa_OC.aspx?chave={quote(str(numero))}"
        
        # Licitações-e
        if 'LICITACOES-E' in fonte or 'BB' in fonte:
            if numero:
                return f"https://www.licitacoes-e.com.br/aop/lct/licitacao/consulta.do?licitacao={quote(str(numero))}"
        
        return None
    
    def _construir_fallback(self, edital: Dict) -> str:
        """
        Constrói URL de fallback quando não há link direto.
        
        Sempre direciona para busca no PNCP.
        """
        numero = edital.get('numero_processo') or edital.get('numero_pregao') or ''
        orgao = edital.get('orgao') or edital.get('orgao_licitante') or ''
        
        # Construir query de busca
        query_parts = []
        if numero:
            query_parts.append(str(numero))
        if orgao and len(orgao) > 5:
            # Pegar primeiras palavras do órgão
            palavras = orgao.split()[:3]
            query_parts.extend(palavras)
        
        query = ' '.join(query_parts) if query_parts else 'licitação'
        return f"https://pncp.gov.br/app/editais?q={quote(query)}"
    
    def _validar_url(self, url: str) -> bool:
        """
        Valida se URL é útil (não é dataset, página genérica, etc).
        
        Rejeita:
        - Portais de dados abertos
        - Datasets
        - Links vazios ou inválidos
        """
        if not url or not isinstance(url, str):
            return False
        
        url = url.strip()
        
        # Verificar se é URL válida
        if not url.startswith(('http://', 'https://')):
            return False
        
        # Verificar padrões inválidos
        for pattern in self.INVALID_URL_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                logger.debug(f"URL rejeitada (padrão inválido): {url}")
                return False
        
        # Verificar se URL não está incompleta
        if url.endswith('=') or url.endswith('chave='):
            return False
        
        return True
    
    def enriquecer_edital(self, edital: Dict) -> Dict:
        """
        Enriquece edital com links resolvidos.
        
        Este método deve ser chamado pelo NormalizadorGenerico
        durante o processo de normalização.
        
        Args:
            edital: Dict do edital
            
        Returns:
            Dict do edital com campos de link enriquecidos
        """
        links = self.resolver_link(edital)
        
        # Atualizar campos do edital
        edital['link_edital'] = links['link_principal']
        edital['link_pncp'] = links['link_pncp']
        edital['link_portal_orgao'] = links['link_portal']
        edital['link_pdf'] = links['link_pdf']
        edital['tipo_link'] = links['tipo_link']
        
        if links['aviso']:
            edital['aviso_link'] = links['aviso']
        
        return edital
    
    def formatar_numero_agregador(self, edital: Dict) -> str:
        """
        Formata número no padrão Portal.
        
        Formato: {Portal} - {Número}/{Ano} - {UASG}
        Exemplo: CN - 90029/2025 - 160143
        
        Args:
            edital: Dict do edital
            
        Returns:
            String formatada no padrão Portal
        """
        fonte = (edital.get('fonte') or 'OUTRO').upper()
        numero = edital.get('numero_processo') or edital.get('numero_pregao') or ''
        uasg = edital.get('uasg') or ''
        
        # Mapear fonte para sigla
        siglas = {
            'COMPRASNET': 'CN',
            'PNCP': 'PNCP',
            'BEC': 'BEC',
            'LICITACOES-E': 'LIC-E',
            'ESTADUAL': 'EST',
            'MUNICIPAL': 'MUN',
        }
        
        sigla = 'OUTRO'
        for key, value in siglas.items():
            if key in fonte:
                sigla = value
                break
        
        # Formatar número
        if uasg:
            return f"{sigla} - {numero} - {uasg}"
        else:
            return f"{sigla} - {numero}"


# Instância global (singleton)
_link_resolver_instance = None


def get_link_resolver() -> LinkResolverService:
    """Retorna instância do LinkResolverService (singleton)."""
    global _link_resolver_instance
    if _link_resolver_instance is None:
        _link_resolver_instance = LinkResolverService()
    return _link_resolver_instance
