"""
Lista curada de orgaos/entidades do portifolio federal de saude, usada pelo
filtro de escopo "Ministerio da Saude" na busca de licitacoes
(GET /api/search/unified?ministerio_saude=true).

Nao existe filtro de servidor por orgao/CNPJ na API oficial do PNCP (testado
e descartado durante o design - ver docs/superpowers/specs/2026-08-07-busca-
ministerio-saude-design.md). Por isso o matching e feito aqui, client-side,
por CNPJ exato OU por palavra-chave do nome do orgao (fallback para unidades
cujo CNPJ ainda nao foi confirmado).

CNPJ confirmado ao vivo via API do Compras.gov.br (razaoSocial retornado =
"MINISTERIO DA SAUDE"): 00394544000185. Esse CNPJ sozinho ja cobre DLOG,
INCA, DSEIs/SESAI e outros institutos nacionais - todos sao "unidades" sob o
mesmo CNPJ da administracao direta, nao entidades com CNPJ proprio.

Fiocruz: CNPJ ainda NAO confirmado. Consulta ao vivo em
1_consultarContratacoes_PNCP_14133 (sem filtro de orgao), varrendo
codigoModalidade=6 (pregao), 8 (dispensa) e 4 (concorrencia) na janela
2026-01-01..2026-08-07 (10 resultados por modalidade), nao retornou nenhum
resultado com "FIOCRUZ" ou "OSWALDO CRUZ" em orgaoEntidadeRazaoSocial (as
modalidades 8 e 4 nao retornaram nenhum resultado na amostra; a modalidade 6
retornou 10 resultados, nenhum da Fiocruz). Ate a Fiocruz aparecer numa
amostra e o CNPJ ser confirmado, o matching por keyword ('fiocruz',
'fundacao oswaldo cruz') e o unico mecanismo cobrindo essa unidade.
"""
from typing import Dict, List, Optional

from services.medicamento_query_parser import normalizar

ORGAOS_SAUDE_FEDERAL: List[Dict] = [
    {
        'nome': 'Ministério da Saúde - Administração Direta',
        'cnpj': '00394544000185',
        'keywords': [
            'ministerio da saude',
            'dlog', 'departamento de logistica em saude',
            'inca', 'instituto nacional de cancer',
            'dsei', 'saude indigena', 'sesai',
            'instituto nacional de cardiologia',
            'instituto nacional de traumato-ortopedia', 'instituto nacional de traumato ortopedia',
        ],
    },
    {
        'nome': 'Fiocruz - Fundação Oswaldo Cruz',
        'cnpj': None,  # TODO: confirmar (ver Task 1 Step 1) - matching por keyword ate la
        'keywords': ['fiocruz', 'fundacao oswaldo cruz'],
    },
]


def bate_orgao_saude(orgao_nome: Optional[str], orgao_cnpj: Optional[str]) -> bool:
    """Retorna True se orgao_nome/orgao_cnpj corresponde a alguma entrada de
    ORGAOS_SAUDE_FEDERAL, por CNPJ exato ou por palavra-chave do nome
    (normalizado sem acento/caixa)."""
    cnpj_normalizado = (orgao_cnpj or '').strip()
    nome_normalizado = normalizar(orgao_nome or '')

    for org in ORGAOS_SAUDE_FEDERAL:
        if org['cnpj'] and cnpj_normalizado == org['cnpj']:
            return True
        if nome_normalizado and any(kw in nome_normalizado for kw in org['keywords']):
            return True
    return False
