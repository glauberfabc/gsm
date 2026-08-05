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


def contem_concentracao(texto: str, concentracao: str) -> bool:
    """
    Compara concentração tolerando variação de espaço em torno de
    unidades (ex.: '100mg/ml' == '100 MG/ML' == '100 MG / ML').
    """
    def compactar(s: str) -> str:
        return re.sub(r'\s+', '', normalizar(s))

    return compactar(concentracao) in compactar(texto)


_REGEX_CONCENTRACAO_COMPOSTA = re.compile(
    r'\d+[.,]?\d*\s*(?:MG|MCG|G|UI)\s*/\s*(?:ML|G|DOSE)\b'
)
_REGEX_CONCENTRACAO_SIMPLES = re.compile(
    r'\d+[.,]?\d*\s*(?:MG|MCG|G|UI|ML)\b'
)

FORMAS_FARMACEUTICAS = [
    'CANETA APLICADORA', 'CANETA PRE-CHEIA', 'CANETA PRE CHEIA',
    'SERINGA PREENCHIDA', 'FRASCO-AMPOLA', 'FRASCO AMPOLA',
    'PO LIOFILIZADO', 'PO PARA SOLUCAO', 'SOLUCAO INJETAVEL',
    'SUSPENSAO ORAL', 'COMPRIMIDO', 'CAPSULA', 'XAROPE',
    'CREME', 'POMADA', 'GEL',
]


def parse_query(termo: str) -> QueryEstruturada:
    """
    Extrai princípio ativo / concentração / forma farmacêutica de uma
    string livre. Nunca recebe '/' (a divisão de nomes compostos
    acontece antes, em `dividir_termo`/`parse_termo_completo`).
    """
    termo = termo.strip()
    # Busca em maiúsculas sem acento, com o MESMO comprimento do termo
    # original (mapeamento 1:1), para os índices do regex/find valerem
    # também para recortar `termo`.
    busca = _remover_acentos(termo).upper()

    concentracao = None
    span_concentracao = None
    m = _REGEX_CONCENTRACAO_COMPOSTA.search(busca) or _REGEX_CONCENTRACAO_SIMPLES.search(busca)
    if m:
        concentracao = termo[m.start():m.end()]
        span_concentracao = (m.start(), m.end())

    forma_farmaceutica = None
    span_forma = None
    melhor_tamanho = -1
    for forma in FORMAS_FARMACEUTICAS:
        idx = busca.find(forma)
        if idx != -1 and len(forma) > melhor_tamanho:
            span_forma = (idx, idx + len(forma))
            forma_farmaceutica = termo[idx:idx + len(forma)]
            melhor_tamanho = len(forma)

    principio_ativo = termo
    spans = [s for s in (span_concentracao, span_forma) if s]
    # Remove do fim para o começo para não invalidar os índices dos
    # spans anteriores (nenhum span se sobrepõe).
    for start, end in sorted(spans, key=lambda s: s[0], reverse=True):
        principio_ativo = principio_ativo[:start] + ' ' + principio_ativo[end:]
    # '/' órfão pode sobrar entre a concentração e uma forma farmacêutica
    # adjacente (ex.: "5G/GEL" -> concentração "5G" + forma "GEL" deixa o
    # separador "/" solto no meio). A função nunca recebe '/' como parte
    # legítima do princípio ativo (ver docstring), então é seguro tratá-lo
    # como ruído de formatação da concentração aqui.
    principio_ativo = re.sub(r'\s*/\s*', ' ', principio_ativo)
    principio_ativo = re.sub(r'\s+', ' ', principio_ativo).strip()
    if not principio_ativo:
        principio_ativo = termo

    return QueryEstruturada(
        termo_original=termo,
        principio_ativo=principio_ativo,
        concentracao=concentracao,
        forma_farmaceutica=forma_farmaceutica,
    )


def dividir_termo(termo: str) -> List[str]:
    """
    Divide nomes compostos com '/' cercada de espaço em pelo menos um
    dos lados (ex.: 'Synvisc Classic 2ml / Hilano G-F 20') em partes
    individuais, pois o banco pode ter armazenado apenas uma das
    formas do nome.

    Uma barra "grudada" nos dois lados (ex.: '100 MG/ML', '5G/GEL') é
    tratada como parte de uma notação de concentração, não como
    separador de nome composto - senão uma busca com concentração
    composta quebraria em duas partes erradas (ex.: 'Mepolizumabe 100
    MG/ML' viraria 'Mepolizumabe 100 MG' + 'ML', e essa segunda parte
    bateria em qualquer texto contendo a palavra "ml").
    """
    partes = [p.strip() for p in re.split(r'(?<=\s)/|/(?=\s)', termo) if p.strip()]
    return partes if len(partes) > 1 else [termo]


def parse_termo_completo(termo: str) -> List[QueryEstruturada]:
    """Aplica `parse_query` a cada parte de `dividir_termo(termo)`."""
    return [parse_query(parte) for parte in dividir_termo(termo)]
