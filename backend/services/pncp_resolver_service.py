"""
PNCP Resolver Service - Resolução de Links PNCP até Arquivos
==============================================================

🎯 OBJETIVO: Replicar EXATAMENTE o comportamento do Agregador

O Agregador usa PNCP como fonte, mas NÃO usa links genéricos SPA.
Ele resolve cada edital até encontrar os arquivos (PDFs) para download.

FLUXO:
1. Recebe edital com dados do PNCP (cnpj, ano, sequencial)
2. Chama API de arquivos: /api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/arquivos
3. Se tiver arquivos válidos → retorna URL do PDF principal
4. Se não tiver arquivos → retorna None (descartar)

REGRA: Edital sem arquivos acessíveis = NÃO FUNCIONAL = DESCARTADO
"""

import asyncio
import logging
import re
from typing import Dict, List, Optional, Tuple
import aiohttp
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class PNCPResolverService:
    """
    Serviço para resolver links PNCP até a página final com arquivos.
    Replica o comportamento do Agregador.
    """
    
    # Base URL da API PNCP
    PNCP_API_BASE = "https://pncp.gov.br/api/pncp/v1"
    PNCP_PNCP_API_BASE = "https://pncp.gov.br/pncp-api/v1"
    
    # Timeout para requisições
    REQUEST_TIMEOUT = 15
    
    # Cache de resoluções (evita requisições repetidas)
    _cache: Dict[str, Optional[Dict]] = {}
    _cache_ttl = 3600  # 1 hora
    
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Obtém ou cria sessão HTTP"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.REQUEST_TIMEOUT)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
    
    async def close(self):
        """Fecha sessão HTTP"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def _extrair_dados_pncp(self, edital: Dict) -> Optional[Tuple[str, str, str]]:
        """
        Extrai CNPJ, ano e sequencial de um edital PNCP.
        
        Fontes possíveis:
        - item_url: /compras/{cnpj}/{ano}/{sequencial}
        - numero_controle_pncp: {cnpj}-{tipo}-{sequencial}/{ano}
        - Campos diretos: orgao_cnpj, ano, numero_sequencial
        
        Returns:
            Tuple (cnpj, ano, sequencial) ou None se não conseguir extrair
        """
        # Tentar campos diretos primeiro
        cnpj = edital.get('orgao_cnpj') or edital.get('cnpj')
        ano = edital.get('ano')
        sequencial = edital.get('numero_sequencial') or edital.get('sequencial')
        
        if cnpj and ano and sequencial:
            return (str(cnpj), str(ano), str(sequencial))
        
        # Tentar extrair de item_url
        item_url = edital.get('item_url', '')
        if item_url:
            # /compras/43863467000178/2025/11
            match = re.search(r'/compras/(\d+)/(\d+)/(\d+)', item_url)
            if match:
                return (match.group(1), match.group(2), match.group(3))
        
        # Tentar extrair de numero_controle_pncp
        numero_controle = edital.get('numero_controle_pncp', '')
        if numero_controle:
            # 43863467000178-1-000011/2025
            match = re.search(r'(\d{14})-\d+-(\d+)/(\d+)', numero_controle)
            if match:
                return (match.group(1), match.group(3), match.group(2).lstrip('0') or '1')
        
        # Tentar extrair de link_pncp ou link_edital
        for campo in ['link_pncp', 'link_edital', 'link']:
            link = edital.get(campo, '')
            if 'pncp.gov.br' in link:
                # https://pncp.gov.br/app/editais/43863467000178/2025/11
                match = re.search(r'/(\d{14})/(\d{4})/(\d+)', link)
                if match:
                    return (match.group(1), match.group(2), match.group(3))
        
        return None
    
    async def resolver_arquivos(self, cnpj: str, ano: str, sequencial: str) -> Optional[Dict]:
        """
        Busca arquivos de um edital PNCP.
        
        Args:
            cnpj: CNPJ do órgão
            ano: Ano da compra
            sequencial: Número sequencial
            
        Returns:
            Dict com informações dos arquivos ou None se não encontrar
        """
        cache_key = f"{cnpj}/{ano}/{sequencial}"
        
        # Verificar cache
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        session = await self._get_session()
        
        # 1. Buscar arquivos
        url_arquivos = f"{self.PNCP_API_BASE}/orgaos/{cnpj}/compras/{ano}/{sequencial}/arquivos"
        
        # 2. Buscar itens REAIS do edital (CRÍTICO - Padrão GSM)
        url_itens = f"{self.PNCP_API_BASE}/orgaos/{cnpj}/compras/{ano}/{sequencial}/itens"
        
        arquivos = []
        itens_reais = []
        
        try:
            # Buscar arquivos
            async with session.get(url_arquivos) as resp:
                if resp.status == 200:
                    arquivos = await resp.json()
            
            # Buscar itens REAIS (OBRIGATÓRIO - Padrão GSM)
            async with session.get(url_itens) as resp:
                if resp.status == 200:
                    itens_api = await resp.json()
                    
                    # Normalizar itens para formato padrão
                    for item in itens_api:
                        itens_reais.append({
                            "numero_item": item.get("numeroItem", 0),
                            "descricao": item.get("descricao", ""),
                            "quantidade": item.get("quantidade", 0),
                            "unidade": item.get("unidadeMedida", ""),
                            "valor_unitario": item.get("valorUnitarioEstimado", 0),
                            "valor_total": item.get("valorTotal", 0),
                            "fonte": "PNCP_API"  # Indica que é do edital real
                        })
                    
                    logger.debug(f"✅ [PNCP] {len(itens_reais)} itens REAIS extraídos de {cnpj}/{ano}/{sequencial}")
            
            if arquivos and len(arquivos) > 0:
                # 🆕 v4.4: Classificar TODOS os arquivos por tipo
                arquivos_classificados = self._classificar_arquivos(arquivos)
                
                # Encontrar o arquivo principal (edital)
                arquivo_principal = self._encontrar_arquivo_principal(arquivos)
                
                resultado = {
                    "status": "FUNCIONAL",
                    "total_arquivos": len(arquivos),
                    "arquivos": arquivos_classificados,  # 🆕 v4.4: Agora com tipo_documento
                    "arquivo_principal": arquivo_principal,
                    "link_edital": arquivo_principal.get("url") if arquivo_principal else None,
                    "itens_reais": itens_reais,  # ✅ ITENS REAIS DO EDITAL
                    "total_itens": len(itens_reais),
                    "resolvido_em": datetime.now(timezone.utc).isoformat()
                }
                
                self._cache[cache_key] = resultado
                return resultado
            else:
                # Sem arquivos = não funcional
                self._cache[cache_key] = None
                return None
                    
        except asyncio.TimeoutError:
            logger.warning(f"Timeout ao buscar arquivos PNCP: {cache_key}")
            return None
        except Exception as e:
            logger.error(f"Erro ao buscar arquivos PNCP {cache_key}: {e}")
            return None
    
    def _encontrar_arquivo_principal(self, arquivos: List[Dict]) -> Optional[Dict]:
        """
        Encontra o arquivo principal (edital) na lista de documentos.
        
        Prioridade:
        1. Arquivo com "edital" no título
        2. Arquivo com "termo de referência" no título
        3. Primeiro PDF da lista
        """
        # Normalizar para busca
        def normalizar(texto: str) -> str:
            return texto.lower().strip() if texto else ""
        
        # Prioridade 1: Edital ou Aviso de Contratação (Principal)
        for arq in arquivos:
            titulo = normalizar(arq.get("titulo", "") or arq.get("nome", ""))
            if any(k in titulo for k in ["edital", "aviso de contrata", "aviso"]) and "anexo" not in titulo:
                return arq
        
        # Prioridade 2: Termo de Referência
        for arq in arquivos:
            titulo = normalizar(arq.get("titulo", "") or arq.get("nome", ""))
            if "termo de referencia" in titulo or "termo de referência" in titulo or "tr" == titulo:
                return arq
        
        # Prioridade 3: Dispensa ou Ratificação
        for arq in arquivos:
            titulo = normalizar(arq.get("titulo", "") or arq.get("nome", ""))
            if "dispensa" in titulo or "ratificacao" in titulo or "ratificação" in titulo:
                return arq
        
        # Prioridade 3: Primeiro arquivo que seja PDF
        for arq in arquivos:
            url = arq.get("url", "")
            titulo = normalizar(arq.get("titulo", "") or arq.get("nome", ""))
            if ".pdf" in url.lower() or ".pdf" in titulo:
                return arq
        
        # Fallback: primeiro arquivo
        return arquivos[0] if arquivos else None
    
    def _classificar_arquivos(self, arquivos: List[Dict]) -> List[Dict]:
        """
        🆕 v4.4: Classifica todos os arquivos do edital por tipo
        
        Tipos detectados:
        - EDITAL: Documento principal do edital
        - TR: Termo de Referência
        - ETP: Estudo Técnico Preliminar
        - MINUTA: Minuta de Contrato
        - ANEXO: Anexos em geral
        - ATA: Ata de Registro de Preços
        - OUTROS: Outros documentos
        
        Returns:
            Lista de arquivos com campo 'tipo_documento' adicionado
        """
        def normalizar(texto: str) -> str:
            return texto.lower().strip() if texto else ""
        
        arquivos_classificados = []
        
        for arq in arquivos:
            titulo = normalizar(arq.get("titulo", "") or arq.get("nome", ""))
            url = arq.get("url", "")
            
            # Classificar tipo
            tipo = "OUTROS"
            
            if "edital" in titulo and "anexo" not in titulo:
                tipo = "EDITAL"
            elif "termo de referencia" in titulo or "termo de referência" in titulo or titulo.startswith("tr ") or titulo.endswith(" tr"):
                tipo = "TR"
            elif "estudo tecnico" in titulo or "estudo técnico" in titulo or "etp" in titulo:
                tipo = "ETP"
            elif "minuta" in titulo:
                tipo = "MINUTA"
            elif "anexo" in titulo:
                tipo = "ANEXO"
            elif "ata" in titulo and "registro" in titulo:
                tipo = "ATA"
            elif "aviso" in titulo:
                tipo = "AVISO"
            elif "declaracao" in titulo or "declaração" in titulo:
                tipo = "DECLARACAO"
            
            # Criar cópia com tipo
            arq_classificado = arq.copy()
            arq_classificado["tipo_documento"] = tipo
            arq_classificado["titulo_original"] = arq.get("titulo", "") or arq.get("nome", "Documento")
            
            arquivos_classificados.append(arq_classificado)
        
        # Ordenar: EDITAL primeiro, depois TR, ETP, etc
        ordem = {"EDITAL": 0, "TR": 1, "ETP": 2, "MINUTA": 3, "ATA": 4, "ANEXO": 5, "AVISO": 6, "DECLARACAO": 7, "OUTROS": 8}
        arquivos_classificados.sort(key=lambda x: ordem.get(x.get("tipo_documento", "OUTROS"), 8))
        
        return arquivos_classificados
    
    async def resolver_edital(self, edital: Dict) -> Dict:
        """
        Resolve um edital PNCP até seus arquivos E itens REAIS.
        
        🎯 PADRÃO GSM:
        - Extrai itens REAIS do edital via API PNCP
        - NÃO inventa ou infere itens
        - Mantém descrição, quantidade e valores fiéis ao edital
        
        Args:
            edital: Dict com dados do edital
            
        Returns:
            Edital atualizado com link funcional e itens REAIS
        """
        # Extrair dados PNCP
        dados_pncp = self._extrair_dados_pncp(edital)
        
        if not dados_pncp:
            # Não é possível resolver - verificar se já tem link funcional
            link_atual = edital.get('link_sistema_origem', '') or edital.get('link_edital', '')
            if link_atual and 'pncp.gov.br' not in link_atual.lower():
                # Já tem link não-PNCP, manter
                edital['link_status'] = 'VALIDO'
                edital['tipo_link'] = 'externo'
            else:
                edital['link_status'] = 'NAO_RESOLVIDO'
                edital['tipo_link'] = 'pncp_nao_resolvido'
            return edital
        
        cnpj, ano, sequencial = dados_pncp
        
        # Buscar arquivos E itens REAIS
        resultado = await self.resolver_arquivos(cnpj, ano, sequencial)
        
        if resultado and resultado.get('link_edital'):
            # ✅ FUNCIONAL - tem arquivos acessíveis
            edital['link_edital'] = resultado['link_edital']
            edital['link_status'] = 'VALIDO'
            edital['tipo_link'] = 'pncp_resolvido'
            edital['pncp_arquivos'] = resultado.get('total_arquivos', 0)
            
            # 🆕 v4.4: Adicionar TODOS os arquivos classificados por tipo
            if resultado.get('arquivos'):
                edital['arquivos_disponiveis'] = resultado['arquivos']  # Já classificados com tipo_documento
            
            # ✅ ITENS REAIS DO EDITAL (PADRÃO GSM)
            # NUNCA inventar ou inferir itens - usar apenas os da API PNCP
            if resultado.get('itens_reais'):
                edital['itens_edital'] = resultado['itens_reais']  # Itens REAIS do edital
                edital['total_itens_edital'] = resultado.get('total_itens', 0)
                logger.debug(f"✅ PNCP resolvido: {cnpj}/{ano}/{sequencial} → {resultado['total_arquivos']} arquivos, {resultado.get('total_itens', 0)} itens REAIS")
            else:
                edital['itens_edital'] = []
                edital['total_itens_edital'] = 0
                logger.debug(f"✅ PNCP resolvido: {cnpj}/{ano}/{sequencial} → {resultado['total_arquivos']} arquivos (sem itens estruturados)")
        else:
            # ❌ NÃO FUNCIONAL - sem arquivos
            edital['link_status'] = 'SEM_ARQUIVOS'
            edital['tipo_link'] = 'pncp_sem_arquivos'
            logger.debug(f"❌ PNCP sem arquivos: {cnpj}/{ano}/{sequencial}")
        
        return edital
    
    async def resolver_lote(self, editais: List[Dict], max_concurrent: int = 10) -> List[Dict]:
        """
        Resolve um lote de editais em paralelo.
        
        Args:
            editais: Lista de editais para resolver
            max_concurrent: Máximo de requisições simultâneas
            
        Returns:
            Lista de editais com links resolvidos
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def resolver_com_limite(edital: Dict) -> Dict:
            async with semaphore:
                return await self.resolver_edital(edital)
        
        tasks = [resolver_com_limite(e) for e in editais]
        resultados = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filtrar exceções
        editais_resolvidos = []
        for i, resultado in enumerate(resultados):
            if isinstance(resultado, Exception):
                logger.error(f"Erro ao resolver edital {i}: {resultado}")
                editais_resolvidos.append(editais[i])  # Manter original
            else:
                editais_resolvidos.append(resultado)
        
        # Estatísticas
        funcionais = sum(1 for e in editais_resolvidos if e.get('link_status') == 'VALIDO')
        sem_arquivos = sum(1 for e in editais_resolvidos if e.get('link_status') == 'SEM_ARQUIVOS')
        
        logger.info(f"📊 [PNCP-RESOLVER] {len(editais)} editais: {funcionais} funcionais, {sem_arquivos} sem arquivos")
        
        return editais_resolvidos
    
    def limpar_cache(self):
        """Limpa cache de resoluções"""
        self._cache.clear()
        logger.info("🧹 Cache PNCP limpo")


# Singleton
_pncp_resolver: Optional[PNCPResolverService] = None


def get_pncp_resolver() -> PNCPResolverService:
    """Obtém instância singleton do resolver"""
    global _pncp_resolver
    if _pncp_resolver is None:
        _pncp_resolver = PNCPResolverService()
    return _pncp_resolver
