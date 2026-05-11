"""
Motor de Busca GSM v78.0 - 100% INDEPENDENTE
==============================================
Busca LIVE usando APENAS APIs públicas do governo:
  1. PNCP (Portal Nacional de Contratações Públicas) - busca + download PDF
  2. Compras.gov.br - dados federais complementares

ZERO dependência de Conlicitação ou qualquer terceiro.
PDFs baixados DIRETO do PNCP (API oficial do governo).

Portais cobertos: TODOS que publicam no PNCP por força de lei
(BLL, BNC, ComprasNet, Compras Públicas, Licitanet, BBMNet, etc.)
"""

import re
import asyncio
import logging
import aiohttp
import hashlib
from typing import Dict, List, Optional
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

PNCP_SEARCH = "https://pncp.gov.br/api/search/"
PNCP_API = "https://pncp.gov.br/pncp-api/v1"
COMPRAS_GOV = "https://dadosabertos.compras.gov.br"

from backend.services.comprasgov_service import get_comprasgov_service


class MotorBuscaIndependente:
    """Motor 100% independente - PNCP + Compras.gov.br."""

    def __init__(self, db=None):
        self.db = db
        self.timeout = aiohttp.ClientTimeout(total=25)

    async def buscar(
        self,
        termo: str,
        pagina: int = 1,
        uf: str = None,
        modalidade: str = None,
        limit: int = 50,
        **kwargs
    ) -> Dict:
        termos = [t.strip() for t in termo.split(',') if t.strip()][:3]

        tasks = {}
        for i, t in enumerate(termos):
            tasks[f'pncp_{i}'] = self._buscar_pncp(t, pagina)
            tasks[f'compras_{i}'] = self._buscar_compras_gov(t, pagina)

        keys = list(tasks.keys())
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        todos = []
        total_pncp = 0
        total_compras = 0

        for i, k in enumerate(keys):
            r = results[i]
            if isinstance(r, dict):
                todos.extend(r.get('resultados', []))
                if k.startswith('pncp'):
                    total_pncp += r.get('total', 0)
                elif k.startswith('compras'):
                    total_compras += r.get('total', 0)
            elif isinstance(r, Exception):
                logger.error(f"Motor {k}: {r}")

        todos = self._dedup(todos)

        # Filtros de Pós-Processamento
        uf_final = uf or kwargs.get('estados')
        municipio = kwargs.get('municipio')

        if uf_final:
            todos = [r for r in todos if (r.get('uf') or '').upper() == uf_final.upper()]
        
        if municipio:
            m_comp = municipio.lower()
            todos = [r for r in todos if m_comp in (r.get('municipio') or '').lower()]

        if modalidade:
            todos = [r for r in todos if modalidade.lower() in (r.get('modalidade') or '').lower()]

        todos.sort(key=lambda x: x.get('data_publicacao') or '', reverse=True)

        return {
            'resultados': todos[:limit],
            'total': len(todos),
            'pagina': pagina,
            'fontes': {
                'pncp_gov_br': total_pncp,
                'compras_gov_br': total_compras
            }
        }

    # ─── PNCP (fonte principal) ───────────────────────────
    async def _buscar_pncp(self, termo: str, pagina: int) -> Dict:
        """
        Busca no PNCP usando a API de busca (ElasticSearch proxy).
        
        v79.0: Corrigido para:
        1. Usar status=recebendo_proposta (igual ao portal PNCP)
        2. Paginar automaticamente para capturar TODOS os resultados ativos
        3. Fallback por 'item' funciona corretamente com filtro de status
        
        A API retorna 10 items por página. Sem paginação, perdíamos ~2/3 dos resultados.
        """
        resultados = []
        total = 0
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as s:
                # 1. Busca por EDITAL com status ATIVO (recebendo_proposta)
                # CRÍTICO: Sem este filtro, a API retorna milhares de editais vencidos
                # e cada página traz apenas 10 aleatórios, a maioria já encerrados.
                params = {
                    'q': termo,
                    'tipos_documento': 'edital',
                    'status': 'recebendo_proposta',
                    'pagina': pagina,
                    'ordenacao': '-data'
                }
                
                # Primeira página
                async with s.get(PNCP_SEARCH, params=params) as r:
                    if r.status == 200:
                        data = await r.json()
                        items = data.get('items', [])
                        total = data.get('total', 0)
                        for item in items:
                            mapped = self._map_pncp(item)
                            if mapped:
                                resultados.append(mapped)
                
                # Paginar para capturar TODOS os resultados ativos (Parallel Boost)
                if pagina == 1 and total > 10:
                    max_paginas = min((total // 10) + 1, 200)  # Aumentado para 200 páginas (2000 items)
                    
                    page_tasks = []
                    for pg in range(2, max_paginas + 1):
                        p = params.copy()
                        p['pagina'] = pg
                        page_tasks.append(s.get(PNCP_SEARCH, params=p))
                    
                    responses = await asyncio.gather(*page_tasks, return_exceptions=True)
                    for resp in responses:
                        if isinstance(resp, aiohttp.ClientResponse) and resp.status == 200:
                            p_data = await resp.json()
                            p_items = p_data.get('items', [])
                            for item in p_items:
                                mapped = self._map_pncp(item)
                                if mapped:
                                    resultados.append(mapped)

                # 2. Busca complementar por ITEM (recall boost)
                # Ativado quando poucos editais ativos encontrados
                if total < 15 and pagina == 1:
                    logger.info(f"🚀 [PNCP-RECALL] Poucos editais ativos ({total}) para '{termo}', buscando nos itens...")
                    params_item = {
                        'q': termo,
                        'tipos_documento': 'item',
                        'status': 'recebendo_proposta',
                        'pagina': 1,
                        'ordenacao': '-data'
                    }
                    async with s.get(PNCP_SEARCH, params=params_item) as r:
                        if r.status == 200:
                            data = await r.json()
                            items_res = data.get('items', [])
                            total_item = data.get('total', 0)
                            for it in items_res:
                                mapped = self._map_pncp(it)
                                if mapped:
                                    resultados.append(mapped)
                            
                            # Paginar itens também se necessário
                            if total_item > 10:
                                for pg in range(2, min((total_item // 10) + 1, 5) + 1):
                                    try:
                                        params_item['pagina'] = pg
                                        async with s.get(PNCP_SEARCH, params=params_item) as r:
                                            if r.status == 200:
                                                data = await r.json()
                                                items_pg = data.get('items', [])
                                                if not items_pg:
                                                    break
                                                for it in items_pg:
                                                    mapped = self._map_pncp(it)
                                                    if mapped:
                                                        resultados.append(mapped)
                                    except Exception:
                                        break
                            
                            total = max(total, total_item)
                            logger.info(f"🚀 [PNCP-RECALL] Itens: +{len(items_res)} encontrados")

                # 3. Fallback SEM filtro de status se não encontrou NADA com filtro
                if not resultados and pagina == 1:
                    logger.info(f"⚠️ [PNCP-FALLBACK] Nenhum resultado ativo para '{termo}', buscando sem filtro de status...")
                    params_fallback = {
                        'q': termo,
                        'tipos_documento': 'edital',
                        'pagina': 1,
                        'ordenacao': '-data'
                    }
                    async with s.get(PNCP_SEARCH, params=params_fallback) as r:
                        if r.status == 200:
                            data = await r.json()
                            items = data.get('items', [])
                            total = data.get('total', 0)
                            for item in items:
                                mapped = self._map_pncp(item)
                                if mapped:
                                    resultados.append(mapped)

        except Exception as e:
            logger.error(f"PNCP busca '{termo}': {e}")
        
        logger.info(f"🔍 [PNCP] '{termo}': {len(resultados)} resultados (total API: {total})")
        
        # Dedup e retorno
        resultados = self._dedup(resultados)
        return {'resultados': resultados, 'total': total}

    def _map_pncp(self, item: Dict) -> Optional[Dict]:
        """Mapeia o retorno da API de busca do PNCP"""
        try:
            agora = datetime.now()
            
            # Dados básicos
            cnpj = item.get('orgao_cnpj', '')
            orgao = item.get('unidade_nome') or item.get('orgao_nome', '')
            uf = item.get('uf', '')
            municipio = item.get('municipio_nome', '')
            objeto = (item.get('description', '') or item.get('title', '')).upper()
            numero_pncp = item.get('numero_controle_pncp', '')
            
            # Datas
            data_pub = item.get('data_publicacao_pncp', '')
            data_abertura = item.get('data_inicio_vigencia', '')
            data_enc = item.get('data_fim_vigencia', '')

            # Extrair ano e sequencial da URL
            item_url = item.get('item_url', '')
            ano, seq = '', ''
            if item_url:
                parts = item_url.strip('/').split('/')
                if len(parts) >= 3:
                    ano = parts[-2]
                    seq = parts[-1]
            
            link_pagina = f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{seq}" if (cnpj and ano and seq) else ''
            link_download = f"/api/editais/download/{cnpj}/{ano}/{seq}" if (cnpj and ano and seq) else ''
            id_gsm = hashlib.md5(f"PNCP-{numero_pncp}".encode()).hexdigest() if numero_pncp else ''

            return {
                'id': id_gsm,
                'id_gsm': id_gsm,
                'id_externo': numero_pncp,
                'fonte': 'PNCP',
                'portal_captura': f"PNCP ({uf})" if uf else 'PNCP',
                'objeto': objeto,
                'orgao': orgao,
                'uf': uf,
                'municipio': municipio,
                'modalidade': item.get('modalidade_licitacao_nome', ''),
                'data_publicacao': data_pub,
                'data_abertura': data_abertura,
                'data_final': data_enc,
                'valor_estimado': item.get('valor_global', 0),
                'link_portal': link_pagina,
                'link_pdf': link_download,
                'link_edital': link_pagina,
                '_pncp_cnpj': cnpj,
                '_pncp_ano': ano,
                '_pncp_seq': seq,
                'itens': [],
                'ativo': True
            }
        except Exception as e:
            return None

    def _map_pncp(self, item: Dict) -> Optional[Dict]:
        try:
            agora = datetime.now()

            # Filtrar editais vencidos
            data_fim = item.get('data_fim_vigencia') or ''
            data_pub = item.get('data_publicacao_pncp') or ''

            if data_fim:
                try:
                    fim = datetime.fromisoformat(data_fim.replace('Z', '+00:00'))
                    if fim.replace(tzinfo=None) < agora - timedelta(days=1):
                        return None  # Prazo vencido
                except (ValueError, TypeError):
                    pass
            elif data_pub:
                # Sem data final: filtrar se publicado há mais de 90 dias
                try:
                    pub = datetime.fromisoformat(data_pub.replace('Z', '+00:00'))
                    if pub.replace(tzinfo=None) < agora - timedelta(days=90):
                        return None  # Muito antigo, provavelmente vencido
                except (ValueError, TypeError):
                    pass

            item_url = item.get('item_url', '')
            cnpj = item.get('orgao_cnpj', '')
            orgao = item.get('orgao_nome', '')
            unidade = item.get('unidade_nome', '')
            uf = item.get('uf', '')
            municipio = item.get('municipio_nome', '')
            objeto = (item.get('description', '') or item.get('title', '')).upper()
            numero_pncp = item.get('numero_controle_pncp', '')

            # Extrair ano e sequencial da URL: /compras/{cnpj}/{ano}/{seq}
            ano, seq = '', ''
            if item_url:
                parts = item_url.strip('/').split('/')
                if len(parts) >= 3:
                    ano = parts[-2]
                    seq = parts[-1]

            # URL da página do edital no PNCP (com botão de download)
            link_pagina = f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{seq}" if (cnpj and ano and seq) else ''

            # Download via NOSSO proxy (evita aba em branco)
            link_download = f"/api/editais/download/{cnpj}/{ano}/{seq}" if (cnpj and ano and seq) else ''

            id_gsm = hashlib.md5(f"PNCP-{numero_pncp}".encode()).hexdigest() if numero_pncp else ''

            return {
                'id': id_gsm,
                'id_gsm': id_gsm,
                'id_externo': numero_pncp,
                'numero_controle_pncp': numero_pncp,
                'fonte': 'PNCP',
                'portal_captura': f"PNCP ({uf})" if uf else 'PNCP',
                'objeto': objeto,
                'orgao': unidade or orgao,
                'uf': uf,
                'municipio': municipio,
                'modalidade': item.get('modalidade_licitacao_nome', ''),
                'data_publicacao': item.get('data_publicacao_pncp', ''),
                'data_abertura': item.get('data_inicio_vigencia', ''),
                'data_final': item.get('data_fim_vigencia', ''),
                'valor_estimado': item.get('valor_global', 0),
                # LINKS 100% INDEPENDENTES - direto do governo
                'link_portal': link_pagina,
                'link_pdf': link_download,
                'link_edital': link_pagina,
                # Metadados para download
                '_pncp_cnpj': cnpj,
                '_pncp_ano': ano,
                '_pncp_seq': seq,
                'itens': '',
                'ativo': True
            }
        except Exception as e:
            logger.error(f"PNCP map: {e}")
            return None

    # ─── COMPRAS.GOV.BR (complementar) ────────────────────
    async def _buscar_compras_gov(self, termo: str, pagina: int) -> Dict:
        """Busca no Compras.gov.br usando o novo serviço robusto."""
        try:
            service = get_comprasgov_service(db=self.db)
            # Busca nos últimos 60 dias para garantir bom recall
            result = await service.buscar_contratacoes_por_objeto(
                termo=termo,
                dias_atras=60,
                max_pages=200 # Aumentado para 2000 resultados
            )
            
            com_termo = result.get('com_termo', [])
            total = result.get('total', 0)
            
            # Adicionar flag de fonte
            for r in com_termo:
                r['fonte_api'] = 'comprasgov_v3'
                
            return {'resultados': com_termo, 'total': total}
        except Exception as e:
            logger.error(f"Erro ao buscar Compras.gov via Serviço: {e}")
            return {'resultados': [], 'total': 0}

    def _map_compras_gov(self, item: Dict) -> Optional[Dict]:
        try:
            agora = datetime.now()
            # Filtrar vencidos
            data_enc = item.get('data_encerramento_proposta') or ''
            data_pub = item.get('data_publicacao_pncp') or ''

            if data_enc:
                try:
                    enc = datetime.fromisoformat(data_enc.replace('Z', '+00:00'))
                    if enc.replace(tzinfo=None) < agora - timedelta(days=1):
                        return None
                except (ValueError, TypeError):
                    pass
            elif data_pub:
                try:
                    pub = datetime.fromisoformat(data_pub.replace('Z', '+00:00'))
                    if pub.replace(tzinfo=None) < agora - timedelta(days=90):
                        return None
                except (ValueError, TypeError):
                    pass

            cnpj = item.get('cnpj_orgao', '') or item.get('cnpj', '')
            ano = str(item.get('ano', ''))
            seq = str(item.get('numero_sequencial', ''))
            objeto = (item.get('objeto_compra', '') or '').upper()
            orgao = item.get('nome_orgao', '') or item.get('nome_unidade', '')
            uf = item.get('sigla_uf', '')

            link_pagina = f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{seq}" if (cnpj and ano and seq) else ''
            link_download = f"/api/editais/download/{cnpj}/{ano}/{seq}" if (cnpj and ano and seq) else ''

            id_gsm = hashlib.md5(f"CGOV-{cnpj}-{ano}-{seq}".encode()).hexdigest()

            return {
                'id': id_gsm,
                'id_gsm': id_gsm,
                'id_externo': f"{cnpj}-{ano}-{seq}",
                'fonte': 'COMPRAS_GOV',
                'portal_captura': f"Compras.gov ({uf})" if uf else 'Compras.gov',
                'objeto': objeto,
                'orgao': orgao,
                'uf': uf,
                'municipio': item.get('nome_municipio', ''),
                'modalidade': item.get('modalidade_nome', ''),
                'data_publicacao': item.get('data_publicacao_pncp', ''),
                'data_abertura': item.get('data_abertura_proposta', ''),
                'data_final': item.get('data_encerramento_proposta', ''),
                'valor_estimado': item.get('valor_global', 0),
                'link_portal': link_pagina,
                'link_pdf': link_download,
                'link_edital': link_pagina,
                '_pncp_cnpj': cnpj,
                '_pncp_ano': ano,
                '_pncp_seq': seq,
                'itens': '',
                'ativo': True
            }
        except Exception as e:
            logger.error(f"Compras.gov map: {e}")
            return None

    # ─── HELPERS ──────────────────────────────────────────
    @staticmethod
    def _dedup(items: List[Dict]) -> List[Dict]:
        seen = set()
        out = []
        for r in items:
            key = r.get('numero_controle_pncp') or r.get('id_externo') or r.get('link_portal') or ''
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            out.append(r)
        return out

    async def listar_arquivos(self, cnpj: str, ano: str, seq: str) -> List[Dict]:
        """Lista todos os arquivos/documentos de um edital no PNCP."""
        try:
            url = f"{PNCP_API}/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos"
            async with aiohttp.ClientSession(timeout=self.timeout) as s:
                async with s.get(url) as r:
                    if r.status == 200:
                        data = await r.json()
                        return [{
                            'seq': arq.get('sequencialDocumento', 1),
                            'titulo': arq.get('titulo', ''),
                            'tipo': arq.get('tipoDocumentoNome', ''),
                            'url': arq.get('url', f"{PNCP_API}/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos/{arq.get('sequencialDocumento', 1)}")
                        } for arq in (data if isinstance(data, list) else [])]
        except Exception as e:
            logger.error(f"PNCP listar_arquivos: {e}")
        return []

    async def buscar_itens(self, cnpj: str, ano: str, seq: str) -> List[Dict]:
        """Busca TODOS os itens de uma contratação no PNCP."""
        try:
            url = f"{PNCP_API}/orgaos/{cnpj}/compras/{ano}/{seq}/itens"
            async with aiohttp.ClientSession(timeout=self.timeout) as s:
                async with s.get(url, params={'tamanhoPagina': 500}) as r:
                    if r.status == 200:
                        data = await r.json()
                        return [{
                            'numero': str(it.get('numeroItem', idx + 1)),
                            'descricao': it.get('descricao', ''),
                            'quantidade': str(it.get('quantidade', '')),
                            'unidade': it.get('unidadeMedida', ''),
                            'valor_unitario': it.get('valorUnitarioEstimado'),
                            'valor_total': it.get('valorTotal')
                        } for idx, it in enumerate(data if isinstance(data, list) else [])]
        except Exception as e:
            logger.error(f"PNCP buscar_itens: {e}")
        return []
