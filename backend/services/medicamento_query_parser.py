"""
Parser e matching estrito para a busca de medicamento na Janela ANVISA (DAMA).

Extrai princípio ativo / concentração / forma farmacêutica de uma string
livre (ex: "MEPOLIZUMABE 100 MG/ML CANETA APLICADORA") e expõe funções de
correspondência por fronteira de palavra, usadas por
`medicamento_search_service.py` para substituir o matching por substring
solta que causava falsos positivos (ex: PNCP aceitando qualquer edital cujos
4 primeiros caracteres do termo buscado aparecessem em qualquer lugar do
texto).
"""
import re
from typing import List, Optional, TypedDict

_ACCENT_MAP = str.maketrans(
    'ÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇáàâãäéèêëíìîïóòôõöúùûüç',
    'AAAAAEEEEIIIIOOOOOUUUUCaaaaaeeeeiiiiooooouuuuc',
)


class QueryEstruturada(TypedDict):
    termo_original: str
    principio_ativo: str
    concentracao: Optional[str]
    forma_farmaceutica: Optional[str]


def _remover_acentos(texto: str) -> str:
    """Mapeamento 1:1 por caractere — preserva o comprimento da string,
    o que permite reusar os índices encontrados em `parse_query` para
    recortar o texto original sem acento."""
    return texto.translate(_ACCENT_MAP)


def normalizar(texto: str) -> str:
    """minúsculas, sem acento, espaços colapsados."""
    if not texto:
        return ''
    sem_acento = _remover_acentos(texto)
    return re.sub(r'\s+', ' ', sem_acento.lower()).strip()


def contem_termo_estrito(texto: str, termo: str) -> bool:
    """
    True se TODAS as palavras significativas (>2 chars) de `termo`
    aparecem em `texto`, cada uma respeitando fronteira de palavra,
    após normalizar ambos (evita 'Aciclovir' casar dentro de
    'Valaciclovir').
    """
    texto_norm = normalizar(texto)
    palavras = [p for p in normalizar(termo).split(' ') if len(p) > 2]
    if not palavras:
        return False
    return all(re.search(r'\b' + re.escape(p) + r'\b', texto_norm) for p in palavras)
