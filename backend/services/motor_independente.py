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
PNCP_CONSULTA = "https://pncp.gov.br/api/consulta/v1"
COMPRAS_GOV = "https://dadosabertos.compras.gov.br"

from backend.services.comprasgov_service import get_comprasgov_service


class MotorBuscaIndependente:
    """Motor 100% independente - PNCP + Compras.gov.br."""

    def __init__(self, db=None):
        self.db = db
        self.timeout = aiohttp.ClientTimeout(total=25)

    async def buscar(
        self,
        termo: str = '',
        pagina: int = 1,
        uf: str = None,
        modalidade: str = None,
        limit: int = 50,
        apenas_ministerio_saude: bool = False,
        **kwargs
    ) -> Dict:
        termo = (termo or '').strip()
        uf_final = uf or kwargs.get('estados')
        municipio_busca = kwargs.get('municipio')

        # v80.0: Busca SEM termo — apenas por Município e/ou UF.
        # A busca full-text (ElasticSearch) do PNCP não filtra por localização
        # no servidor, então usamos a API oficial de Consulta (contratacoes/proposta),
        # que suporta uf e codigoMunicipioIbge nativamente.
        if not termo and (uf_final or municipio_busca):
            return await self._buscar_por_localizacao(
                uf=uf_final,
                municipio=municipio_busca,
                pagina=pagina,
                limit=limit,
                modalidade=modalidade
            )

        # Busca SEM termo, escopo Ministério da Saúde ("buscar todos")
        if not termo and apenas_ministerio_saude:
            return await self._buscar_ministerio_saude_sem_termo(
                pagina=pagina,
                limit=limit,
            )

        # Remove duplicados preservando a ordem e define limite de até 20 termos
        termos_unicos = []
        for t in termo.split(','):
            t_clean = t.strip()
            if t_clean and t_clean not in termos_unicos:
                termos_unicos.append(t_clean)
        termos = termos_unicos[:20]

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

        if apenas_ministerio_saude:
            from services.orgaos_saude_federal import bate_orgao_saude
            todos = [
                r for r in todos
                if bate_orgao_saude(
                    r.get('orgao') or r.get('orgao_nome'),
                    r.get('_pncp_cnpj') or r.get('orgao_cnpj')
                )
            ]

        # Filtros de Pós-Processamento
        if uf_final:
            todos = [r for r in todos if (r.get('uf') or '').upper() == uf_final.upper()]

        if municipio_busca:
            m_comp = municipio_busca.lower()
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

    # ─── PNCP — Busca por Localização (sem termo) ─────────
    async def _buscar_por_localizacao(
        self,
        uf: str = None,
        municipio: str = None,
        pagina: int = 1,
        limit: int = 50,
        modalidade: str = None
    ) -> Dict:
        """
        Lista TODOS os editais com propostas abertas de um Município e/ou UF,
        usando a API oficial de Consulta do PNCP (filtra no servidor por
        uf/codigoMunicipioIbge — ao contrário da busca full-text por termo).
        """
        from services.municipio_resolver import resolver_municipio

        codigo_ibge = None
        if municipio:
            info = await resolver_municipio(municipio, uf)
            if info:
                codigo_ibge = info['codigo_ibge']
                if not uf:
                    uf = info['uf']
            else:
                logger.warning(f"⚠️ [LOCALIZACAO] Município '{municipio}' não encontrado na base do IBGE")
                return {'resultados': [], 'total': 0, 'pagina': pagina, 'fontes': {'pncp_gov_br': 0, 'compras_gov_br': 0}, 'fonte_disponivel': True}

        cache_key = f"{(uf or '').upper()}|{codigo_ibge or (municipio or '').strip().lower()}|{pagina}|{limit}|{modalidade or ''}"

        PNCP_PAGE_SIZE = 50
        idx_inicio = (pagina - 1) * limit
        idx_fim = pagina * limit
        pg_inicio = (idx_inicio // PNCP_PAGE_SIZE) + 1
        pg_fim = max(pg_inicio, -(-idx_fim // PNCP_PAGE_SIZE))  # ceil division

        hoje = datetime.now()
        params_base = {
            'dataInicial': (hoje - timedelta(days=60)).strftime('%Y%m%d'),
            'dataFinal': (hoje + timedelta(days=180)).strftime('%Y%m%d'),
            'tamanhoPagina': PNCP_PAGE_SIZE
        }
        if uf:
            params_base['uf'] = uf.upper()
        if codigo_ibge:
            params_base['codigoMunicipioIbge'] = codigo_ibge

        brutos = []
        total = 0
        pncp_respondeu = False
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as s:
                for pg in range(pg_inicio, pg_fim + 1):
                    params = {**params_base, 'pagina': pg}
                    async with s.get(f"{PNCP_CONSULTA}/contratacoes/proposta", params=params) as r:
                        if r.status != 200:
                            break
                        pncp_respondeu = True
                        data = await r.json()
                        total = data.get('totalRegistros', 0)
                        itens = data.get('data', [])
                        if not itens:
                            break
                        brutos.extend(itens)
        except Exception as e:
            logger.error(f"Erro busca por localização (uf={uf}, municipio={municipio}): {e}")

        # v80.1: PNCP Consulta API é conhecida por instabilidade (pool de conexão
        # do lado deles, timeouts completos em horário de pico). Quando ele não
        # responde, servimos a última busca com sucesso em cache (se houver) em
        # vez de mostrar "0 resultados", que é enganoso.
        if not pncp_respondeu:
            cache_resultado = await self._buscar_cache_localizacao(cache_key)
            if cache_resultado:
                logger.warning(f"⚠️ [PNCP-INSTAVEL] uf={uf} municipio={municipio}: servindo resultado em cache")
                cache_resultado['fonte_disponivel'] = False
                cache_resultado['aviso'] = 'O PNCP está instável no momento. Exibindo a última busca disponível em cache.'
                return cache_resultado

            logger.error(f"❌ [PNCP-INSTAVEL] uf={uf} municipio={municipio}: sem cache disponível")
            return {
                'resultados': [],
                'total': 0,
                'pagina': pagina,
                'fontes': {'pncp_gov_br': 0, 'compras_gov_br': 0},
                'fonte_disponivel': False,
                'aviso': 'O PNCP está instável/indisponível no momento para busca por localização. Tente novamente em alguns minutos.'
            }

        mapeados = [m for it in brutos if (m := self._map_consulta_proposta(it))]

        if modalidade:
            mapeados = [r for r in mapeados if modalidade.lower() in (r.get('modalidade') or '').lower()]

        mapeados = self._dedup(mapeados)

        # Recorta exatamente a fatia pedida dentro do bloco de páginas PNCP buscado
        offset_local = idx_inicio - (pg_inicio - 1) * PNCP_PAGE_SIZE
        pagina_resultados = mapeados[offset_local: offset_local + limit]

        logger.info(f"🌍 [PNCP-LOCALIZACAO] uf={uf} municipio={municipio}: {len(pagina_resultados)} de {total} totais")

        resultado_final = {
            'resultados': pagina_resultados,
            'total': total,
            'pagina': pagina,
            'fontes': {'pncp_gov_br': total, 'compras_gov_br': 0},
            'fonte_disponivel': True
        }
        await self._salvar_cache_localizacao(cache_key, resultado_final)
        return resultado_final

    # ─── Compras.gov.br — Ministério da Saúde sem termo ("buscar todos") ──
    MODALIDADES_RELEVANTES = [4, 6, 8, 9]  # concorrencia, pregao eletronico, dispensa, inexigibilidade

    async def _buscar_ministerio_saude_sem_termo(
        self,
        pagina: int = 1,
        limit: int = 50,
    ) -> Dict:
        """
        Lista contratações recentes do Ministério da Saúde (CNPJ
        00394544000185) sem exigir termo de busca, via Compras.gov.br
        (consultar_contratacoes_pncp com filtro de CNPJ - mecanismo
        validado ao vivo durante o design; a API oficial do PNCP não tem
        filtro de órgão funcional).
        """
        from services.orgaos_saude_federal import ORGAOS_SAUDE_FEDERAL
        from backend.scrapers.comprasgov_client import consultar_contratacoes_pncp

        cache_key = f"MS|{pagina}|{limit}"

        hoje = datetime.now()
        data_inicial = (hoje - timedelta(days=180)).strftime('%Y-%m-%d')
        data_final = hoje.strftime('%Y-%m-%d')

        async def _consultar(cnpj: str, modalidade: int) -> List[Dict]:
            resultado = await consultar_contratacoes_pncp(
                data_publicacao_inicial=data_inicial,
                data_publicacao_final=data_final,
                cnpj_orgao=cnpj,
                modalidade=modalidade,
                max_pages=5,
            )
            return resultado.get('resultado', [])

        chamadas = [
            (org['cnpj'], modalidade)
            for org in ORGAOS_SAUDE_FEDERAL if org.get('cnpj')
            for modalidade in self.MODALIDADES_RELEVANTES
        ]
        respostas = await asyncio.gather(
            *(_consultar(cnpj, modalidade) for cnpj, modalidade in chamadas),
            return_exceptions=True
        )

        brutos = []
        algum_sucesso = False
        for (cnpj, modalidade), r in zip(chamadas, respostas):
            if isinstance(r, Exception):
                logger.error(f"Erro consultando CNPJ {cnpj} modalidade {modalidade}: {r}")
                continue
            algum_sucesso = True
            brutos.extend(r)

        mapeados = [m for it in brutos if (m := self._map_comprasgov_contratacao(it))]
        mapeados = self._dedup(mapeados)

        # v80.2: a checagem de "sem resultado" precisa ocorrer APÓS o
        # mapeamento, não sobre `brutos`/`algum_sucesso` crus - se toda
        # chamada teve sucesso mas `_map_comprasgov_contratacao` falhar em
        # 100% dos itens (ex.: API mudou de formato), cair no branch de
        # sucesso com total=0 e sem aviso seria exatamente a falha
        # silenciosa que este método existe para evitar.
        if not mapeados:
            if not algum_sucesso:
                # Só cai para um cache possivelmente obsoleto quando a API
                # de fato falhou hoje - se algum_sucesso for True, a
                # resposta "zero resultados" já é fresca e confiável, não
                # precisa (nem deve) ser substituída por uma stale.
                cache_resultado = await self._buscar_cache_localizacao(cache_key)
                if cache_resultado:
                    logger.warning("⚠️ [MS-SEM-TERMO] API indisponível: servindo resultado em cache")
                    cache_resultado['fonte_disponivel'] = False
                    cache_resultado['aviso'] = (
                        'A fonte de dados do Ministério da Saúde está instável no momento. '
                        'Exibindo a última busca disponível em cache.'
                    )
                    return cache_resultado

                return {
                    'resultados': [],
                    'total': 0,
                    'pagina': pagina,
                    'fontes': {'pncp_gov_br': 0, 'compras_gov_br': 0},
                    'fonte_disponivel': False,
                    'aviso': 'A fonte de dados do Ministério da Saúde está instável/indisponível no momento. Tente novamente em alguns minutos.',
                }

            # As chamadas à API funcionaram (HTTP 200), só não havia
            # contratações no período - bem diferente de instabilidade.
            return {
                'resultados': [],
                'total': 0,
                'pagina': pagina,
                'fontes': {'pncp_gov_br': 0, 'compras_gov_br': 0},
                'fonte_disponivel': True,
                'aviso': 'Nenhuma contratação encontrada para o Ministério da Saúde nos últimos 180 dias.',
            }

        mapeados.sort(key=lambda x: x.get('data_publicacao') or '', reverse=True)

        idx_inicio = (pagina - 1) * limit
        pagina_resultados = mapeados[idx_inicio: idx_inicio + limit]

        resultado_final = {
            'resultados': pagina_resultados,
            'total': len(mapeados),
            'pagina': pagina,
            'fontes': {'pncp_gov_br': 0, 'compras_gov_br': len(mapeados)},
            'fonte_disponivel': True,
        }
        await self._salvar_cache_localizacao(cache_key, resultado_final)
        return resultado_final

    def _map_comprasgov_contratacao(self, item: Dict) -> Optional[Dict]:
        """Mapeia uma contratação do Compras.gov.br (modulo-contratacoes)
        para o mesmo schema usado por _map_pncp/_map_consulta_proposta."""
        try:
            cnpj = item.get('orgaoEntidadeCnpj', '')
            orgao = item.get('orgaoEntidadeRazaoSocial', '') or item.get('unidadeOrgaoNomeUnidade', '')
            uf = item.get('unidadeOrgaoUfSigla', '')
            municipio = item.get('unidadeOrgaoMunicipioNome', '')
            objeto = (item.get('objetoCompra', '') or '').upper()
            numero_pncp = item.get('numeroControlePNCP', '')
            ano = str(item.get('anoCompra', ''))
            seq = str(item.get('sequencialCompra', ''))

            link_pagina = f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{seq}" if (cnpj and ano and seq) else ''
            link_download = f"/api/editais/download/{cnpj}/{ano}/{seq}" if (cnpj and ano and seq) else ''
            id_gsm = hashlib.md5(f"PNCP-{numero_pncp}".encode()).hexdigest() if numero_pncp else ''

            return {
                'id': id_gsm,
                'id_gsm': id_gsm,
                'id_externo': numero_pncp,
                'numero_controle_pncp': numero_pncp,
                'fonte': 'COMPRAS_GOV',
                'portal_captura': f"Compras.gov ({uf})" if uf else 'Compras.gov',
                'objeto': objeto,
                'orgao': orgao,
                'uf': uf,
                'municipio': municipio,
                'modalidade': item.get('modalidadeNome', ''),
                'data_publicacao': item.get('dataPublicacaoPncp', ''),
                'data_abertura': item.get('dataAberturaPropostaPncp', ''),
                'data_final': item.get('dataEncerramentoPropostaPncp', ''),
                'valor_estimado': item.get('valorTotalEstimado', 0),
                'link_portal': link_pagina,
                'link_pdf': link_download,
                'link_edital': link_pagina,
                '_pncp_cnpj': cnpj,
                '_pncp_ano': ano,
                '_pncp_seq': seq,
                'itens': '',
                'ativo': True,
            }
        except Exception as e:
            logger.error(f"Erro mapeando contratação Compras.gov: {e}")
            return None

    # ─── Cache de resiliência (PNCP Consulta API é instável) ──
    CACHE_COLLECTION = 'cache_busca_localizacao'
    CACHE_TTL_SEGUNDOS = 6 * 3600  # 6 horas

    async def _garantir_indice_cache(self):
        if self.db is None:
            return
        try:
            await self.db[self.CACHE_COLLECTION].create_index(
                'criado_em', expireAfterSeconds=self.CACHE_TTL_SEGUNDOS
            )
        except Exception as e:
            logger.debug(f"Índice TTL cache_busca_localizacao já existe ou falhou: {e}")

    async def _buscar_cache_localizacao(self, cache_key: str) -> Optional[Dict]:
        if self.db is None:
            return None
        try:
            doc = await self.db[self.CACHE_COLLECTION].find_one({'_id': cache_key})
            if doc:
                return doc.get('resultado')
        except Exception as e:
            logger.error(f"Erro lendo cache_busca_localizacao: {e}")
        return None

    async def _salvar_cache_localizacao(self, cache_key: str, resultado: Dict):
        if self.db is None:
            return
        try:
            await self._garantir_indice_cache()
            await self.db[self.CACHE_COLLECTION].update_one(
                {'_id': cache_key},
                {'$set': {'resultado': resultado, 'criado_em': datetime.now(timezone.utc)}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Erro salvando cache_busca_localizacao: {e}")

    def _map_consulta_proposta(self, item: Dict) -> Optional[Dict]:
        """Mapeia contratação da API de Consulta (/contratacoes/proposta) para o schema GSM."""
        try:
            orgao_entidade = item.get('orgaoEntidade', {}) or {}
            unidade = item.get('unidadeOrgao', {}) or {}

            cnpj = orgao_entidade.get('cnpj', '')
            ano = str(item.get('anoCompra', ''))
            seq = str(item.get('sequencialCompra', ''))
            uf = unidade.get('ufSigla', '')
            municipio = unidade.get('municipioNome', '')
            orgao = orgao_entidade.get('razaoSocial', '') or unidade.get('nomeUnidade', '')
            objeto = (item.get('objetoCompra', '') or '').upper()
            numero_pncp = item.get('numeroControlePNCP', '')

            link_pagina = f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{seq}" if (cnpj and ano and seq) else ''
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
                'orgao': orgao,
                'uf': uf,
                'municipio': municipio,
                'modalidade': item.get('modalidadeNome', ''),
                'data_publicacao': item.get('dataPublicacaoPncp', ''),
                'data_abertura': item.get('dataAberturaProposta', ''),
                'data_final': item.get('dataEncerramentoProposta', ''),
                'valor_estimado': item.get('valorTotalEstimado', 0),
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
            logger.error(f"Erro mapeando contratação (localização): {e}")
            return None

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
