"""
PNCP Search Service - Busca Direta na API PNCP
===============================================

🎯 OBJETIVO: Buscar editais diretamente na API PNCP e resolver até arquivos

Este serviço é usado quando os dados locais não são suficientes.
Replica o comportamento do Agregador de buscar no PNCP e resolver links.
"""

import asyncio
import logging
import re
from typing import Dict, List, Optional
import aiohttp
from datetime import datetime, timezone

from services.pncp_resolver_service import get_pncp_resolver

logger = logging.getLogger(__name__)


class PNCPSearchService:
    """
    Serviço para busca direta na API PNCP com resolução de arquivos.
    """
    
    PNCP_SEARCH_URL = "https://pncp.gov.br/api/search/"
    REQUEST_TIMEOUT = 30
    
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
    
    async def buscar(
        self,
        termo: str,
        limite: int = 50,
        apenas_ativas: bool = True
    ) -> List[Dict]:
        """
        Busca editais na API PNCP.
        Implementa estratégia de alto recall: se encontrar poucos editais pelo objeto, busca nos itens.
        """
        session = await self._get_session()
        
        # 1. Busca por EDITAL (Objeto/Título)
        params = {
            "q": termo,
            "tipos_documento": "edital",
            "ordenacao": "-data",
            "pagina": 1,
            "tam_pagina": min(limite, 100)
        }
        
        try:
            items = []
            total = 0
            async with session.get(self.PNCP_SEARCH_URL, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    items = data.get('items', [])
                    total = data.get('total', 0)
            
            # 2. SE poucos resultados, busca por ITEM (Recall Boost)
            if total < 10:
                logger.info(f"🚀 [PNCP-RECALL-BOOST] Baixo retorno para '{termo}' no objeto ({total}). Buscando nos itens...")
                params_item = params.copy()
                params_item["tipos_documento"] = "item"
                async with session.get(self.PNCP_SEARCH_URL, params=params_item) as resp_item:
                    if resp_item.status == 200:
                        data_item = await resp_item.json()
                        items_item = data_item.get('items', [])
                        # Adicionar itens à lista (eles serão normalizados como editais)
                        items.extend(items_item)
            
            logger.info(f"🔍 [PNCP-SEARCH] '{termo}': {len(items)} resultados brutos (objeto + itens)")
            
            # Normalizar resultados
            editais = []
            ids_vistos = set()
            agora = datetime.now(timezone.utc)
            
            for item in items:
                edital = self._normalizar_item(item)
                
                # Deduplicação por numero_controle_pncp
                num_pncp = edital.get('numero_controle_pncp')
                if num_pncp in ids_vistos:
                    continue
                ids_vistos.add(num_pncp)
                
                # Filtrar por data se necessário
                if apenas_ativas:
                    data_fim = edital.get('data_abertura') or edital.get('data_fim_vigencia')
                    if data_fim:
                        try:
                            if isinstance(data_fim, str):
                                # Lidar com formatos diferentes de data do PNCP
                                try:
                                    dt_val = datetime.fromisoformat(data_fim.replace('Z', '+00:00'))
                                except:
                                    dt_val = datetime.strptime(data_fim[:10], '%Y-%m-%d').replace(tzinfo=timezone.utc)
                                
                                if dt_val.tzinfo is None:
                                    dt_val = dt_val.replace(tzinfo=timezone.utc)
                                
                                if dt_val < agora:
                                    continue  # Edital encerrado
                            elif isinstance(data_fim, datetime):
                                if data_fim.tzinfo is None:
                                    data_fim = data_fim.replace(tzinfo=timezone.utc)
                                if data_fim < agora:
                                    continue
                        except Exception as e:
                            logger.warning(f"Erro ao validar data {data_fim}: {e}")
                
                editais.append(edital)
            
            return editais
                
        except asyncio.TimeoutError:
            logger.error(f"Timeout na busca PNCP: '{termo}'")
            return []
        except Exception as e:
            logger.error(f"Erro na busca PNCP: {e}")
            return []
    
    def _normalizar_item(self, item: Dict) -> Dict:
        """
        Normaliza item da API PNCP para formato padrão.
        """
        # Extrair dados para resolução
        item_url = item.get('item_url', '')
        cnpj = ''
        ano = ''
        sequencial = ''
        
        if item_url:
            # /compras/43863467000178/2025/11
            match = re.search(r'/compras/(\d+)/(\d+)/(\d+)', item_url)
            if match:
                cnpj = match.group(1)
                ano = match.group(2)
                sequencial = match.group(3)
        
        # Fallback para campos diretos
        if not cnpj:
            cnpj = item.get('orgao_cnpj', '')
        if not ano:
            ano = str(item.get('ano', ''))
        if not sequencial:
            sequencial = str(item.get('numero_sequencial', ''))
        
        # v65.0: Garantir campos de numeração para deduplicação correta
        num_processo = item.get('numero_processo') or item.get('processo') or ''
        num_licitacao = item.get('numero_licitacao') or item.get('numero_compra') or f"{sequencial}/{ano}"
        
        return {
            "id_externo": item.get('id', ''),
            "objeto": item.get('description', item.get('title', '')),
            "orgao": item.get('orgao_nome', ''),
            "orgao_cnpj": cnpj,
            "ano": ano,
            "numero_sequencial": sequencial,
            "numero_processo": num_processo,
            "numero_licitacao": num_licitacao,
            "licitacao_num": num_licitacao,
            "item_url": item_url,
            "numero_controle_pncp": item.get('numero_controle_pncp', ''),
            "uf": item.get('uf', ''),
            "municipio": item.get('municipio_nome', ''),
            "esfera": item.get('esfera_nome', ''),
            "modalidade": item.get('modalidade_licitacao_nome', ''),
            "situacao": item.get('situacao_nome', ''),
            "data_publicacao": item.get('data_publicacao_pncp', ''),
            "data_abertura": item.get('data_fim_vigencia', ''),
            "data_fim_vigencia": item.get('data_fim_vigencia', ''),
            "fonte": "PNCP_API",
            "is_saude": True,  # Assumir saúde por padrão
            "link_pncp": f"https://pncp.gov.br{item_url}" if item_url else '',
            # Campos para resolução
            "_pncp_cnpj": cnpj,
            "_pncp_ano": ano,
            "_pncp_sequencial": sequencial,
        }
    
    async def buscar_e_resolver(
        self,
        termo: str,
        limite: int = 50,
        apenas_ativas: bool = True
    ) -> List[Dict]:
        """
        Busca editais na API PNCP e resolve links até arquivos.
        
        Esta é a função principal que replica o comportamento do Agregador:
        1. Busca no PNCP
        2. Resolve cada edital até seus arquivos E itens REAIS
        3. Filtra itens que correspondem ao termo de busca
        4. Descarta editais sem arquivos
        
        Args:
            termo: Termo de busca
            limite: Máximo de resultados
            apenas_ativas: Se True, filtra apenas editais ativos
            
        Returns:
            Lista de editais com links funcionais e itens REAIS correspondentes
        """
        # 1. Buscar no PNCP
        editais = await self.buscar(termo, limite * 2, apenas_ativas)  # Buscar mais para ter margem
        
        if not editais:
            return []
        
        # 2. Resolver links até arquivos E buscar itens REAIS
        pncp_resolver = get_pncp_resolver()
        editais_resolvidos = await pncp_resolver.resolver_lote(editais, max_concurrent=10)
        
        # 3. Filtrar apenas funcionais E fazer matching de itens com o termo
        editais_funcionais = []
        termo_lower = termo.lower()
        termos = [t.strip() for t in termo_lower.split() if len(t.strip()) > 2]
        
        # 🆕 v4.4: Incluir o termo original completo na lista de busca
        if termo_lower not in termos:
            termos.insert(0, termo_lower)
        
        for edital in editais_resolvidos:
            if not (edital.get('link_status') == 'VALIDO' and edital.get('link_edital')):
                continue
            
            # 🔴 v4.4 MATA-LIXO RADICAL: Verificar se o termo existe no objeto OU itens
            objeto = (edital.get('objeto') or '').lower()
            tem_match_objeto = any(t in objeto for t in termos)
            
            # ✅ MATCHING DE ITENS REAIS COM O TERMO (PADRÃO GSM)
            itens_edital = edital.get('itens_edital', [])
            itens_correspondentes = []
            tem_match_itens = False
            
            for item in itens_edital:
                descricao = item.get('descricao', '').lower()
                
                # Verificar se algum termo da busca está na descrição do item
                for t in termos:
                    if t in descricao:
                        tem_match_itens = True
                        # Item corresponde ao termo
                        itens_correspondentes.append({
                            "numero_item": item.get('numero_item', 0),
                            "descricao": item.get('descricao', ''),
                            "quantidade": item.get('quantidade', 0),
                            "unidade": item.get('unidade', ''),
                            "valor_unitario": item.get('valor_unitario', 0),
                            "valor_total": item.get('valor_total', 0),
                            "termo_match": t,
                            "confirmado_no_item": True,  # 🆕 v4.4: Flag de confirmação
                            "fonte": "EDITAL_REAL"  # ✅ Indica que é do edital, não inferido
                        })
                        break  # Não duplicar se múltiplos termos correspondem
            
            # 🔴 v4.4 MATA-LIXO RADICAL: DESCARTAR se não houver match no objeto NEM nos itens
            if not (tem_match_objeto or tem_match_itens):
                logger.debug(f"🔴 [PNCP-MATA-LIXO] Descartado: {edital.get('orgao', '?')[:30]} - sem match para '{termo}'")
                continue
            
            # Adicionar itens correspondentes ao edital
            edital['itens_correspondentes'] = itens_correspondentes
            edital['total_itens_match'] = len(itens_correspondentes)
            
            editais_funcionais.append(edital)
        
        logger.info(f"✅ [PNCP-SEARCH] '{termo}': {len(editais)} encontrados → {len(editais_funcionais)} com arquivos e itens")
        
        return editais_funcionais[:limite]


# Singleton
_pncp_search: Optional[PNCPSearchService] = None


def get_pncp_search() -> PNCPSearchService:
    """Obtém instância singleton do serviço de busca PNCP"""
    global _pncp_search
    if _pncp_search is None:
        _pncp_search = PNCPSearchService()
    return _pncp_search
