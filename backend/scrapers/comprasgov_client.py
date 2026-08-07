"""
Cliente API Dados Abertos Compras.gov.br — v1.0
=================================================
Implementação completa conforme docs/comprasgov_api_implementacao.md

Base URL: https://dadosabertos.compras.gov.br
Formato: REST / HTTP 1.1 com retorno em JSON
Autenticação: Não requer token para consultas públicas

Módulos implementados:
  - Contratações PNCP 14133 (principal)
  - Itens das Contratações
  - Resultado dos Itens
  - Legado (licitações antigas)
  - Itens de Licitações Legado
  - Pesquisa de Preço (Material e Serviço)
  - ARP (Ata de Registro de Preços)
  - Contratos
  - Fornecedores
  - UASG / Órgãos
  - CATMAT / CATSER
  - OCDS
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional
from datetime import datetime

import aiohttp

logger = logging.getLogger(__name__)

BASE_URL = "https://dadosabertos.compras.gov.br"

# ─── Configuração ────────────────────────────────────────
DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=30)
DEFAULT_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": "GSM-RadarLicitacoes/1.0"
}
DEFAULT_PAGE_SIZE = 500
MAX_RETRIES = 3
DELAY_BETWEEN_PAGES_MS = 300
BACKOFF_BASE_MS = 1000


# ─────────────────────────────────────────────────────────
#  Função genérica de paginação com retry e backoff
# ─────────────────────────────────────────────────────────
async def fetch_paginated(
    endpoint: str,
    params: Optional[Dict[str, Any]] = None,
    tamanho_pagina: int = DEFAULT_PAGE_SIZE,
    max_pages: int = 9999,
    timeout: aiohttp.ClientTimeout = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """
    Busca paginada genérica para qualquer endpoint da API Compras.gov.br.

    Retorna:
        {
            "resultado": [...],
            "totalRegistros": int,
            "totalPaginas": int,
            "paginas_lidas": int,
            "tempo_segundos": float,
            "erros": [str]
        }
    """
    params = dict(params or {})
    all_results: List[Dict] = []
    pagina = 1
    total_paginas = 1
    total_registros = 0
    erros: List[str] = []
    t0 = time.monotonic()

    url = f"{BASE_URL}{endpoint}"

    async with aiohttp.ClientSession(timeout=timeout, headers=DEFAULT_HEADERS) as session:
        while pagina <= total_paginas and pagina <= max_pages:
            params["pagina"] = pagina
            params["tamanhoPagina"] = tamanho_pagina

            data = await _request_with_retry(session, url, params, erros)

            if data is None:
                break

            # Extrair resultados — a API usa 'resultado' ou lista direta
            results = data.get("resultado", [])
            if not results and isinstance(data, list):
                results = data

            all_results.extend(results)

            # Controle de paginação
            total_registros = data.get("totalRegistros", total_registros) or len(all_results)
            total_paginas = data.get("totalPaginas", total_paginas) or 1
            paginas_restantes = data.get("paginasRestantes", 0)

            # Condição de parada
            if not results:
                break
            if paginas_restantes <= 0 and pagina >= total_paginas:
                break

            pagina += 1
            await asyncio.sleep(DELAY_BETWEEN_PAGES_MS / 1000)

    elapsed = round(time.monotonic() - t0, 2)

    logger.info(
        f"📦 [ComprasGov] {endpoint} → {len(all_results)} registros "
        f"em {pagina} págs ({elapsed}s)"
    )

    return {
        "resultado": all_results,
        "totalRegistros": total_registros,
        "totalPaginas": total_paginas,
        "paginas_lidas": pagina,
        "tempo_segundos": elapsed,
        "erros": erros,
    }


async def _request_with_retry(
    session: aiohttp.ClientSession,
    url: str,
    params: Dict,
    erros: List[str],
) -> Optional[Dict]:
    """Executa request com retry e backoff exponencial."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    return await resp.json()
                elif resp.status == 429:
                    wait = BACKOFF_BASE_MS * attempt / 1000
                    logger.warning(f"⚠️ Rate-limited (429), aguardando {wait}s...")
                    await asyncio.sleep(wait)
                elif resp.status >= 500:
                    wait = BACKOFF_BASE_MS * attempt / 1000
                    logger.warning(f"⚠️ Erro {resp.status}, retry {attempt}/{MAX_RETRIES} em {wait}s")
                    await asyncio.sleep(wait)
                else:
                    erros.append(f"HTTP {resp.status} em {url}")
                    return None
        except asyncio.TimeoutError:
            erros.append(f"Timeout tentativa {attempt}/{MAX_RETRIES}")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(BACKOFF_BASE_MS * attempt / 1000)
        except Exception as e:
            erros.append(f"Erro tentativa {attempt}: {str(e)}")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(BACKOFF_BASE_MS * attempt / 1000)

    return None


# ═════════════════════════════════════════════════════════
#  MÓDULO CONTRATAÇÕES — Lei 14.133/2021 / PNCP
# ═════════════════════════════════════════════════════════

async def consultar_contratacoes_pncp(
    data_publicacao_inicial: Optional[str] = None,
    data_publicacao_final: Optional[str] = None,
    cnpj_orgao: Optional[str] = None,
    uf: Optional[str] = None,
    modalidade: Optional[int] = None,
    tamanho_pagina: int = 500,
    max_pages: int = 100,
    **extra_params,
) -> Dict[str, Any]:
    """
    Busca contratações PNCP Lei 14.133/2021.
    
    Endpoint: /modulo-contratacoes/1_consultarContratacoes_PNCP_14133
    """
    params: Dict[str, Any] = {}
    if data_publicacao_inicial:
        params["dataPublicacaoPncpInicial"] = data_publicacao_inicial
    if data_publicacao_final:
        params["dataPublicacaoPncpFinal"] = data_publicacao_final
    if cnpj_orgao:
        params["orgaoEntidadeCnpj"] = cnpj_orgao
    if uf:
        params["uf"] = uf
    if modalidade is not None:
        params["codigoModalidade"] = modalidade
    params.update(extra_params)

    return await fetch_paginated(
        "/modulo-contratacoes/1_consultarContratacoes_PNCP_14133",
        params=params,
        tamanho_pagina=tamanho_pagina,
        max_pages=max_pages,
    )


async def consultar_itens_contratacoes_pncp(
    id_compra: Optional[str] = None,
    tamanho_pagina: int = 500,
    max_pages: int = 50,
    **extra_params,
) -> Dict[str, Any]:
    """
    Busca itens das contratações PNCP.
    
    Endpoint: /modulo-contratacoes/2_consultarItensContratacoes_PNCP_14133
    """
    params: Dict[str, Any] = {}
    if id_compra:
        params["idCompra"] = id_compra
    params.update(extra_params)

    return await fetch_paginated(
        "/modulo-contratacoes/2_consultarItensContratacoes_PNCP_14133",
        params=params,
        tamanho_pagina=tamanho_pagina,
        max_pages=max_pages,
    )


async def consultar_resultado_itens_pncp(
    id_compra: Optional[str] = None,
    tamanho_pagina: int = 500,
    max_pages: int = 50,
    **extra_params,
) -> Dict[str, Any]:
    """
    Busca resultado dos itens PNCP (vencedores).
    
    Endpoint: /modulo-contratacoes/3_consultarResultadoItensContratacoes_PNCP_14133
    """
    params: Dict[str, Any] = {}
    if id_compra:
        params["idCompra"] = id_compra
    params.update(extra_params)

    return await fetch_paginated(
        "/modulo-contratacoes/3_consultarResultadoItensContratacoes_PNCP_14133",
        params=params,
        tamanho_pagina=tamanho_pagina,
        max_pages=max_pages,
    )


# ═════════════════════════════════════════════════════════
#  MÓDULO LEGADO
# ═════════════════════════════════════════════════════════

async def consultar_licitacao_legado(
    modalidade: Optional[int] = None,
    uasg: Optional[str] = None,
    tamanho_pagina: int = 500,
    max_pages: int = 100,
    **extra_params,
) -> Dict[str, Any]:
    """
    Busca licitações do modelo anterior (pré-PNCP).
    
    Endpoint: /modulo-legado/1_consultarLicitacao
    """
    params: Dict[str, Any] = {}
    if modalidade is not None:
        params["modalidade"] = modalidade
    if uasg:
        params["uasg"] = uasg
    params.update(extra_params)

    return await fetch_paginated(
        "/modulo-legado/1_consultarLicitacao",
        params=params,
        tamanho_pagina=tamanho_pagina,
        max_pages=max_pages,
    )


async def consultar_itens_licitacao_legado(
    uasg: Optional[str] = None,
    numero_aviso: Optional[str] = None,
    modalidade: Optional[int] = None,
    tamanho_pagina: int = 500,
    max_pages: int = 50,
    **extra_params,
) -> Dict[str, Any]:
    """
    Busca itens de licitações legado.
    
    Endpoint: /modulo-legado/2_consultarItemLicitacao
    """
    params: Dict[str, Any] = {}
    if uasg:
        params["uasg"] = uasg
    if numero_aviso:
        params["numero_aviso"] = numero_aviso
    if modalidade is not None:
        params["modalidade"] = modalidade
    params.update(extra_params)

    return await fetch_paginated(
        "/modulo-legado/2_consultarItemLicitacao",
        params=params,
        tamanho_pagina=tamanho_pagina,
        max_pages=max_pages,
    )


async def consultar_pregao(
    uasg: Optional[str] = None,
    tamanho_pagina: int = 500,
    max_pages: int = 50,
    **extra_params,
) -> Dict[str, Any]:
    """
    Busca pregões (legado).
    
    Endpoint: /modulo-legado/3_consultarPregao
    """
    params: Dict[str, Any] = {}
    if uasg:
        params["uasg"] = uasg
    params.update(extra_params)

    return await fetch_paginated(
        "/modulo-legado/3_consultarPregao",
        params=params,
        tamanho_pagina=tamanho_pagina,
        max_pages=max_pages,
    )


# ═════════════════════════════════════════════════════════
#  MÓDULO PESQUISA DE PREÇO
# ═════════════════════════════════════════════════════════

async def consultar_preco_material(
    descricao_item: Optional[str] = None,
    codigo_item: Optional[str] = None,
    tamanho_pagina: int = 500,
    max_pages: int = 50,
    **extra_params,
) -> Dict[str, Any]:
    """
    Consulta histórico de preços de material.
    
    Endpoint: /modulo-pesquisa-preco/1_consultarMaterial
    """
    params: Dict[str, Any] = {}
    if descricao_item:
        params["descricaoItem"] = descricao_item
    if codigo_item:
        params["codigoItemCatalogo"] = codigo_item
    params.update(extra_params)

    return await fetch_paginated(
        "/modulo-pesquisa-preco/1_consultarMaterial",
        params=params,
        tamanho_pagina=tamanho_pagina,
        max_pages=max_pages,
    )


async def consultar_preco_material_detalhe(
    tamanho_pagina: int = 500,
    max_pages: int = 50,
    **extra_params,
) -> Dict[str, Any]:
    """
    Detalhe de preço de material.
    
    Endpoint: /modulo-pesquisa-preco/2_consultarMaterialDetalhe
    """
    return await fetch_paginated(
        "/modulo-pesquisa-preco/2_consultarMaterialDetalhe",
        params=extra_params,
        tamanho_pagina=tamanho_pagina,
        max_pages=max_pages,
    )


async def consultar_preco_servico(
    descricao_item: Optional[str] = None,
    tamanho_pagina: int = 500,
    max_pages: int = 50,
    **extra_params,
) -> Dict[str, Any]:
    """
    Consulta histórico de preços de serviço.
    
    Endpoint: /modulo-pesquisa-preco/3_consultarServico
    """
    params: Dict[str, Any] = {}
    if descricao_item:
        params["descricaoItem"] = descricao_item
    params.update(extra_params)

    return await fetch_paginated(
        "/modulo-pesquisa-preco/3_consultarServico",
        params=params,
        tamanho_pagina=tamanho_pagina,
        max_pages=max_pages,
    )


# ═════════════════════════════════════════════════════════
#  MÓDULO ARP — Ata de Registro de Preços
# ═════════════════════════════════════════════════════════

async def consultar_arp(
    tamanho_pagina: int = 500,
    max_pages: int = 50,
    **extra_params,
) -> Dict[str, Any]:
    """
    Busca Atas de Registro de Preços.
    
    Endpoint: /modulo-arp/1_consultarARP
    """
    return await fetch_paginated(
        "/modulo-arp/1_consultarARP",
        params=extra_params,
        tamanho_pagina=tamanho_pagina,
        max_pages=max_pages,
    )


async def consultar_itens_arp(
    tamanho_pagina: int = 500,
    max_pages: int = 50,
    **extra_params,
) -> Dict[str, Any]:
    """
    Busca itens de uma ARP.
    
    Endpoint: /modulo-arp/2_consultarItensARP
    """
    return await fetch_paginated(
        "/modulo-arp/2_consultarItensARP",
        params=extra_params,
        tamanho_pagina=tamanho_pagina,
        max_pages=max_pages,
    )


# ═════════════════════════════════════════════════════════
#  MÓDULO CONTRATOS
# ═════════════════════════════════════════════════════════

async def consultar_contratos(
    codigo_orgao: Optional[str] = None,
    numero_contrato: Optional[str] = None,
    tamanho_pagina: int = 500,
    max_pages: int = 50,
    **extra_params,
) -> Dict[str, Any]:
    """
    Busca contratos.
    
    Endpoint: /modulo-contratos/1_consultarContratos
    """
    params: Dict[str, Any] = {}
    if codigo_orgao:
        params["codigoOrgao"] = codigo_orgao
    if numero_contrato:
        params["numeroContrato"] = numero_contrato
    params.update(extra_params)

    return await fetch_paginated(
        "/modulo-contratos/1_consultarContratos",
        params=params,
        tamanho_pagina=tamanho_pagina,
        max_pages=max_pages,
    )


async def consultar_itens_contrato(
    tamanho_pagina: int = 500,
    max_pages: int = 50,
    **extra_params,
) -> Dict[str, Any]:
    """
    Busca itens de contrato.
    
    Endpoint: /modulo-contratos/2_consultarItensContrato
    """
    return await fetch_paginated(
        "/modulo-contratos/2_consultarItensContrato",
        params=extra_params,
        tamanho_pagina=tamanho_pagina,
        max_pages=max_pages,
    )


# ═════════════════════════════════════════════════════════
#  MÓDULO FORNECEDOR
# ═════════════════════════════════════════════════════════

async def consultar_fornecedor(
    cnpj: Optional[str] = None,
    cpf: Optional[str] = None,
    tamanho_pagina: int = 500,
    max_pages: int = 50,
    **extra_params,
) -> Dict[str, Any]:
    """
    Busca dados cadastrais de fornecedores.
    
    Endpoint: /modulo-fornecedor/1_consultarFornecedor
    """
    params: Dict[str, Any] = {}
    if cnpj:
        params["cnpj"] = cnpj
    if cpf:
        params["cpf"] = cpf
    params.update(extra_params)

    return await fetch_paginated(
        "/modulo-fornecedor/1_consultarFornecedor",
        params=params,
        tamanho_pagina=tamanho_pagina,
        max_pages=max_pages,
    )


# ═════════════════════════════════════════════════════════
#  MÓDULO UASG / ÓRGÃOS
# ═════════════════════════════════════════════════════════

async def consultar_uasg(
    codigo_uasg: Optional[str] = None,
    tamanho_pagina: int = 500,
    max_pages: int = 50,
    **extra_params,
) -> Dict[str, Any]:
    """
    Consulta UASGs.
    
    Endpoint: /modulo-uasg/1_consultarUasg
    """
    params: Dict[str, Any] = {}
    if codigo_uasg:
        params["codigoUasg"] = codigo_uasg
    params.update(extra_params)

    return await fetch_paginated(
        "/modulo-uasg/1_consultarUasg",
        params=params,
        tamanho_pagina=tamanho_pagina,
        max_pages=max_pages,
    )


async def consultar_orgao(
    codigo_orgao: Optional[str] = None,
    tamanho_pagina: int = 500,
    max_pages: int = 50,
    **extra_params,
) -> Dict[str, Any]:
    """
    Consulta órgãos.
    
    Endpoint: /modulo-uasg/2_consultarOrgao
    """
    params: Dict[str, Any] = {}
    if codigo_orgao:
        params["codigoOrgao"] = codigo_orgao
    params.update(extra_params)

    return await fetch_paginated(
        "/modulo-uasg/2_consultarOrgao",
        params=params,
        tamanho_pagina=tamanho_pagina,
        max_pages=max_pages,
    )


# ═════════════════════════════════════════════════════════
#  MÓDULO MATERIAL — CATMAT
# ═════════════════════════════════════════════════════════

async def consultar_item_material(
    codigo_item: Optional[str] = None,
    tamanho_pagina: int = 500,
    max_pages: int = 50,
    **extra_params,
) -> Dict[str, Any]:
    """
    Consulta itens de material (CATMAT).
    
    Endpoint: /modulo-material/4_consultarItemMaterial
    """
    params: Dict[str, Any] = {}
    if codigo_item:
        params["codigoItem"] = codigo_item
    params.update(extra_params)

    return await fetch_paginated(
        "/modulo-material/4_consultarItemMaterial",
        params=params,
        tamanho_pagina=tamanho_pagina,
        max_pages=max_pages,
    )


async def consultar_grupo_material(
    tamanho_pagina: int = 500,
    max_pages: int = 50,
    **extra_params,
) -> Dict[str, Any]:
    """
    Consulta grupos de material.
    
    Endpoint: /modulo-material/1_consultarGrupoMaterial
    """
    return await fetch_paginated(
        "/modulo-material/1_consultarGrupoMaterial",
        params=extra_params,
        tamanho_pagina=tamanho_pagina,
        max_pages=max_pages,
    )


# ═════════════════════════════════════════════════════════
#  MÓDULO SERVIÇO — CATSER
# ═════════════════════════════════════════════════════════

async def consultar_item_servico(
    tamanho_pagina: int = 500,
    max_pages: int = 50,
    **extra_params,
) -> Dict[str, Any]:
    """
    Consulta itens de serviço (CATSER).
    
    Endpoint: /modulo-servico/6_consultarItemServico
    """
    return await fetch_paginated(
        "/modulo-servico/6_consultarItemServico",
        params=extra_params,
        tamanho_pagina=tamanho_pagina,
        max_pages=max_pages,
    )


# ═════════════════════════════════════════════════════════
#  MÓDULO PGC — Planejamento de Contratações
# ═════════════════════════════════════════════════════════

async def consultar_pgc_detalhe(
    tamanho_pagina: int = 500,
    max_pages: int = 50,
    **extra_params,
) -> Dict[str, Any]:
    """
    Consulta PGC Detalhe (planejamento de contratações).
    
    Endpoint: /modulo-pgc/1_consultarPGCDetalhe
    """
    return await fetch_paginated(
        "/modulo-pgc/1_consultarPGCDetalhe",
        params=extra_params,
        tamanho_pagina=tamanho_pagina,
        max_pages=max_pages,
    )


# ═════════════════════════════════════════════════════════
#  MÓDULO OCDS — Open Contracting Data Standard
# ═════════════════════════════════════════════════════════

async def consultar_ocds_releases(
    buyer_id: str,
    release_start_date: str,
    release_end_date: str,
    offset: int = 500,
    max_pages: int = 50,
) -> Dict[str, Any]:
    """
    Consulta releases OCDS.
    
    Endpoint: /modulo-ocds/1_releases
    
    Note: Este endpoint usa 'page' e 'offset' ao invés de 'pagina' e 'tamanhoPagina'.
    """
    all_results: List[Dict] = []
    page = 1
    erros: List[str] = []
    t0 = time.monotonic()

    url = f"{BASE_URL}/modulo-ocds/1_releases"

    async with aiohttp.ClientSession(timeout=DEFAULT_TIMEOUT, headers=DEFAULT_HEADERS) as session:
        while page <= max_pages:
            params = {
                "buyerID": buyer_id,
                "releaseStartDate": release_start_date,
                "releaseEndDate": release_end_date,
                "page": page,
                "offset": offset,
            }

            data = await _request_with_retry(session, url, params, erros)
            if data is None:
                break

            releases = data.get("releases", [])
            if not releases:
                break

            all_results.extend(releases)
            page += 1
            await asyncio.sleep(DELAY_BETWEEN_PAGES_MS / 1000)

    elapsed = round(time.monotonic() - t0, 2)

    return {
        "resultado": all_results,
        "totalRegistros": len(all_results),
        "paginas_lidas": page - 1,
        "tempo_segundos": elapsed,
        "erros": erros,
    }


# ═════════════════════════════════════════════════════════
#  NORMALIZADORES
# ═════════════════════════════════════════════════════════

def normalizar_contratacao_pncp(row: Dict) -> Dict:
    """
    Normaliza uma contratação PNCP 14.133 para o formato interno GSM.
    """
    return {
        "fonte": "comprasgov",
        "modulo": "contratacoes",
        "endpoint": "1_consultarContratacoes_PNCP_14133",
        "id_compra": row.get("idCompra"),
        "numero_controle_pncp": row.get("numeroControlePNCP"),
        "numero_compra": row.get("numeroCompra"),
        "numero_processo": row.get("processo"),
        "orgao_cnpj": row.get("orgaoEntidadeCnpj"),
        "orgao_nome": row.get("orgaoEntidadeRazaoSocial"),
        "uf": row.get("unidadeOrgaoUfSigla"),
        "municipio": row.get("unidadeOrgaoMunicipioNome"),
        "modalidade_codigo": row.get("codigoModalidade"),
        "modalidade_nome": row.get("modalidadeNome"),
        "modo_disputa_codigo": row.get("codigoModoDisputa"),
        "modo_disputa_nome": None,
        "objeto": row.get("objetoCompra"),
        "informacao_complementar": row.get("informacaoComplementar"),
        "valor_estimado": row.get("valorTotalEstimado"),
        "valor_homologado": row.get("valorTotalHomologado"),
        "data_publicacao": row.get("dataPublicacaoPncp"),
        "data_abertura_proposta": row.get("dataAberturaPropostaPncp"),
        "data_encerramento_proposta": row.get("dataEncerramentoPropostaPncp"),
        "data_atualizacao": row.get("dataAtualizacao"),
        "situacao": row.get("situacaoCompraNomePncp"),
        "srp": row.get("srp"),
        "amparo_legal": row.get("amparoLegalNome"),
        "link_origem": f"https://pncp.gov.br/app/editais/{row.get('orgaoEntidadeCnpj','')}/{row.get('anoCompra','')}/{row.get('sequencialCompra','')}",
        "raw": row,
    }


def normalizar_licitacao_legado(row: Dict) -> Dict:
    """
    Normaliza uma licitação do módulo legado.
    """
    return {
        "fonte": "comprasgov",
        "modulo": "legado",
        "endpoint": "1_consultarLicitacao",
        "id_compra": row.get("id_compra"),
        "numero_controle_pncp": None,
        "numero_compra": row.get("numero_aviso"),
        "numero_processo": row.get("numero_processo"),
        "orgao_cnpj": None,
        "orgao_nome": row.get("nome_uasg"),
        "uasg_codigo": row.get("uasg"),
        "uf": None,
        "municipio": None,
        "modalidade_codigo": row.get("modalidade"),
        "modalidade_nome": row.get("nome_modalidade"),
        "objeto": row.get("objeto"),
        "valor_estimado": row.get("valor_estimado_total"),
        "valor_homologado": row.get("valor_homologado_total"),
        "data_publicacao": row.get("data_publicacao"),
        "data_abertura_proposta": row.get("data_abertura_proposta"),
        "data_encerramento_proposta": row.get("data_entrega_proposta"),
        "situacao": row.get("situacao_aviso"),
        "raw": row,
    }


def normalizar_item_contratacao(row: Dict) -> Dict:
    """
    Normaliza um item de contratação PNCP.
    """
    return {
        "id_compra": row.get("idCompra"),
        "id_item_compra": row.get("idItemCompra"),
        "numero_item": row.get("numeroItem"),
        "tipo_item": row.get("tipoItem"),
        "codigo_item": row.get("codigoItemCatalogo"),
        "descricao_item": row.get("descricaoItem"),
        "quantidade": row.get("quantidade"),
        "unidade": row.get("unidadeMedida"),
        "valor_estimado": row.get("valorEstimado"),
        "valor_unitario": row.get("valorUnitario"),
        "valor_total": row.get("valorTotal"),
        "fornecedor_documento": row.get("niFornecedor"),
        "fornecedor_nome": row.get("nomeFornecedor"),
        "raw": row,
    }


def normalizar_contrato(row: Dict) -> Dict:
    """
    Normaliza um contrato.
    """
    return {
        "fonte": "comprasgov",
        "modulo": "contratos",
        "numero_contrato": row.get("numeroContrato"),
        "orgao_codigo": row.get("codigoOrgao"),
        "orgao_nome": row.get("nomeOrgao"),
        "fornecedor_cnpj": row.get("cnpjFornecedor"),
        "fornecedor_nome": row.get("nomeFornecedor"),
        "objeto": row.get("objeto"),
        "valor": row.get("valorInicial"),
        "data_inicio": row.get("dataInicioVigencia"),
        "data_fim": row.get("dataFimVigencia"),
        "raw": row,
    }


def normalizar_arp(row: Dict) -> Dict:
    """
    Normaliza uma ARP.
    """
    return {
        "fonte": "comprasgov",
        "modulo": "arp",
        "numero_arp": row.get("numeroARP"),
        "uasg": row.get("codigoUasg"),
        "orgao_nome": row.get("nomeUasg"),
        "fornecedor_cnpj": row.get("cnpjFornecedor"),
        "fornecedor_nome": row.get("nomeFornecedor"),
        "data_publicacao": row.get("dataPublicacao"),
        "data_vigencia_inicio": row.get("dataInicioVigencia"),
        "data_vigencia_fim": row.get("dataFimVigencia"),
        "raw": row,
    }


def normalizar_fornecedor(row: Dict) -> Dict:
    """
    Normaliza dados de fornecedor.
    """
    return {
        "fonte": "comprasgov",
        "ativo": row.get("ativo"),
        "cnpj": row.get("cnpj"),
        "cpf": row.get("cpf"),
        "razao_social": row.get("nomeRazaoSocialFornecedor"),
        "nome_fantasia": row.get("nomeFantasiaFornecedor"),
        "cnae": row.get("codigoCnae"),
        "municipio": row.get("municipio"),
        "uf": row.get("uf"),
        "natureza_juridica": row.get("naturezaJuridica"),
        "porte": row.get("porteEmpresaNome"),
        "raw": row,
    }
