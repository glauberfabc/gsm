"""
Resolvedor de Municípios (IBGE)
================================
Resolve nome de município digitado pelo usuário (com ou sem acentos,
maiúsculas/minúsculas variadas) para o código IBGE usado pela API
oficial de Consulta do PNCP (parâmetro codigoMunicipioIbge).

Fonte: API pública do IBGE (Localidades) — sem autenticação.
"""

import re
import unicodedata
import asyncio
import logging
import aiohttp
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

IBGE_MUNICIPIOS_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"

_cache: List[Dict] = []
_lock = asyncio.Lock()


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize('NFKD', texto or '').encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[^A-Z0-9 ]', '', texto.upper()).strip()


async def _carregar_cache():
    global _cache
    if _cache:
        return
    async with _lock:
        if _cache:
            return
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                async with session.get(IBGE_MUNICIPIOS_URL) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        carregados = []
                        for m in data:
                            try:
                                uf_sigla = m['microrregiao']['mesorregiao']['UF']['sigla']
                            except (KeyError, TypeError):
                                uf_sigla = ''
                            carregados.append({
                                'codigo_ibge': str(m['id']),
                                'nome': m['nome'],
                                'nome_norm': _normalizar(m['nome']),
                                'uf': uf_sigla
                            })
                        _cache = carregados
                        logger.info(f"✅ [MUNICIPIOS] Cache IBGE carregado: {len(_cache)} municípios")
                    else:
                        logger.error(f"Erro ao carregar municípios IBGE: HTTP {resp.status}")
        except Exception as e:
            logger.error(f"Erro ao carregar municípios IBGE: {e}")


async def resolver_municipio(nome: str, uf: Optional[str] = None) -> Optional[Dict]:
    """
    Resolve o nome de um município para {codigo_ibge, nome, uf}.
    Se uf for informado, restringe a busca àquele estado (evita ambiguidade
    entre municípios homônimos de estados diferentes).
    """
    if not nome or not nome.strip():
        return None

    await _carregar_cache()
    if not _cache:
        return None

    alvo = _normalizar(nome)
    candidatos = [m for m in _cache if (not uf or m['uf'] == uf.upper())]

    for m in candidatos:
        if m['nome_norm'] == alvo:
            return m
    for m in candidatos:
        if m['nome_norm'].startswith(alvo):
            return m
    for m in candidatos:
        if alvo in m['nome_norm']:
            return m
    return None
