"""
Sincronizacao do dataset aberto de medicamentos registrados na ANVISA.
Fonte oficial: https://dados.anvisa.gov.br/dados/DADOS_ABERTOS_MEDICAMENTOS.csv

Guarda registros com SITUACAO_REGISTRO != 'Ativo' (cancelados, inativos,
vencidos etc.) na colecao anvisa_registro_medicamentos - um registro ativo nao
e evidencia de desabastecimento, entao a Janela ANVISA nao precisa dele.
Registros ativos vao para a colecao separada anvisa_registro_medicamentos_ativos,
usada pelo Radar LMR para checar similar registrado no Brasil (RDC 81/2008).

O arquivo tem ~8MB/dezenas de milhares de linhas, entao e baixado e processado
por um job agendado (nao a cada busca do usuario).
"""
import csv
import io
import logging
import ssl
from datetime import datetime, timezone

import aiohttp

logger = logging.getLogger(__name__)

CSV_URL = "https://dados.anvisa.gov.br/dados/DADOS_ABERTOS_MEDICAMENTOS.csv"

# dados.anvisa.gov.br nao envia o certificado intermediario da cadeia TLS
# (confirmado com `openssl s_client`: "unable to verify the first certificate"),
# entao a verificacao padrao falha mesmo com a raiz Sectigo sendo confiavel.
# Isso e uma falha de configuracao do lado do servidor, nao algo que da pra
# corrigir por config nossa. Em vez de desabilitar a verificacao TLS, carregamos
# o intermediario que falta (obtido via AIA da propria ANVISA, valido ate 2036)
# para completar a cadeia e manter a verificacao real ligada.
_SECTIGO_INTERMEDIATE_PEM = """-----BEGIN CERTIFICATE-----
MIIGTDCCBDSgAwIBAgIQLBo8dulD3d3/GRsxiQrtcTANBgkqhkiG9w0BAQwFADBf
MQswCQYDVQQGEwJHQjEYMBYGA1UEChMPU2VjdGlnbyBMaW1pdGVkMTYwNAYDVQQD
Ey1TZWN0aWdvIFB1YmxpYyBTZXJ2ZXIgQXV0aGVudGljYXRpb24gUm9vdCBSNDYw
HhcNMjEwMzIyMDAwMDAwWhcNMzYwMzIxMjM1OTU5WjBgMQswCQYDVQQGEwJHQjEY
MBYGA1UEChMPU2VjdGlnbyBMaW1pdGVkMTcwNQYDVQQDEy5TZWN0aWdvIFB1Ymxp
YyBTZXJ2ZXIgQXV0aGVudGljYXRpb24gQ0EgT1YgUjM2MIIBojANBgkqhkiG9w0B
AQEFAAOCAY8AMIIBigKCAYEApkMtJ3R06jo0fceI0M52B7K+TyMeGcv2BQ5AVc3j
lYt76TvHIu/nNe22W/RJXX9rWUD/2GE6GF5x0V4bsY7K3IeJ8E7+KzG/TGboySfD
u+F52jqQBbY62ofhYjMeiAbLI02+FqwHeM8uIrUtcX8b2RCxF358TB0NHVccAXZc
FYgZndZCeXxjuca7pJJ20LLUnXtgXcjAE1vY4WvbReW0W6mkeZyNGdmpTcFs5Y+s
yy6LtE5Zocji9J9NlNnReox2RWVyEXpA1ChZ4gqN+ZpVSIQ0HBorVFbBKyhdZyEX
gZgNSNtBRwxqwIzJePJhYd4ZUhO1vk+/uP3nwDk0p95q/j7naXNCSvESnrHPypaB
WRK066nKfPRPi9m9kIOhMdYfS8giFRTcdgL24Ycilj7ecAK9Trh0VbjwouJ4WH+x
bt47u68ZFCD/ac55I0DNHkCpaPruj6e9Rmr7K46wZDAYXuEAqB7tGG/jd6JAA+H2
O44CV98NRsU213f1kScIZntNAgMBAAGjggGBMIIBfTAfBgNVHSMEGDAWgBRWc1hk
lfmSGrASKgRieaFAFYghSTAdBgNVHQ4EFgQU42Z0u3BojSxdTg6mSo+bNyKcgpIw
DgYDVR0PAQH/BAQDAgGGMBIGA1UdEwEB/wQIMAYBAf8CAQAwHQYDVR0lBBYwFAYI
KwYBBQUHAwEGCCsGAQUFBwMCMBsGA1UdIAQUMBIwBgYEVR0gADAIBgZngQwBAgIw
VAYDVR0fBE0wSzBJoEegRYZDaHR0cDovL2NybC5zZWN0aWdvLmNvbS9TZWN0aWdv
UHVibGljU2VydmVyQXV0aGVudGljYXRpb25Sb290UjQ2LmNybDCBhAYIKwYBBQUH
AQEEeDB2ME8GCCsGAQUFBzAChkNodHRwOi8vY3J0LnNlY3RpZ28uY29tL1NlY3Rp
Z29QdWJsaWNTZXJ2ZXJBdXRoZW50aWNhdGlvblJvb3RSNDYucDdjMCMGCCsGAQUF
BzABhhdodHRwOi8vb2NzcC5zZWN0aWdvLmNvbTANBgkqhkiG9w0BAQwFAAOCAgEA
BZXWDHWC3cubb/e1I1kzi8lPFiK/ZUoH09ufmVOrc5ObYH/XKkWUexSPqRkwKFKr
7r8OuG+p7VNB8rifX6uopqKAgsvZtZsq7iAFw04To6vNcxeBt1Eush3cQ4b8nbQR
MQLChgEAqwhuXp9P48T4QEBSksYav7+aFjNySsLYlPzNqVM3RNwvBdvp6vgDtGwc
xlKQZVuuNVIaoYyls8swhxDeSHKpRdxRauTLZ+pl+wGvy0pnrLEJGSz9mOEmfbod
e/XopR2NGqaHJ6bIjyxPu6UtyQGI26En7UAEozACrHz06Nx2jTAY9E6NeB6XuobE
wLK025ZRmvglcURG1BrV24tGHHTgxCe8M3oGlpUSMTKQ2dkgljZVYt+gKdFtWELZ
MuRdi+X3XsrR8LFz+aLUiDRfQqhmw3RxjIyVKvvu9UPYY1nsvxYmFnUSeM+2q1z/
iPUry+xDY9MC6+IhleKT094VKdFVp7LXH42+wvU+17lRolQ2mK2N/nBLVBwaIhib
QXw4VYKwB86Bc6eS6iqsc94KEgD/U4VsjmgfhK+Xp4NM+VYzTTa3QeV3p8xOM0cw
q1p8oZFA+OBcz3FYWpDIe5j0NWKlw9hXsTyPY/HeZUV59akskSOSRSmDfe8wJDPX
58uB9/7lud0G3x0pxQAcffP0ayKavNwDTw4UfJ34cEw=
-----END CERTIFICATE-----
"""


def _ssl_context_com_intermediario() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.load_verify_locations(cadata=_SECTIGO_INTERMEDIATE_PEM)
    return ctx


async def _substituir_colecao(db, nome_colecao: str, docs: list):
    """Substitui o conteudo de uma colecao de forma atomica: escreve os
    docs novos numa colecao temporaria e troca via rename com
    dropTarget=True (operacao atomica do MongoDB), em vez de
    delete_many+insert_many (que deixa a colecao vazia se insert_many
    falhar no meio)."""
    nome_temp = f"{nome_colecao}__sync_tmp"
    temp = db[nome_temp]
    await temp.delete_many({})  # limpa resto de uma tentativa anterior que falhou
    await temp.insert_many(docs)
    await temp.rename(nome_colecao, dropTarget=True)


async def _detectar_novos_registros(db, docs_ativos: list) -> list:
    """Retorna os docs de docs_ativos cujo numero_registro_produto nao
    estava na colecao anvisa_registro_medicamentos_ativos antes desta
    sincronizacao (precisa ser chamado ANTES da troca atomica de
    colecao, enquanto o snapshot antigo ainda esta live)."""
    numeros_novos = {d['numero_registro_produto'] for d in docs_ativos if d.get('numero_registro_produto')}
    if not numeros_novos:
        return []
    existentes = await db.anvisa_registro_medicamentos_ativos.find(
        {'numero_registro_produto': {'$in': list(numeros_novos)}},
        {'_id': 0, 'numero_registro_produto': 1},
    ).to_list(length=len(numeros_novos))
    numeros_existentes = {e['numero_registro_produto'] for e in existentes}
    return [d for d in docs_ativos if d.get('numero_registro_produto') and d['numero_registro_produto'] not in numeros_existentes]


async def sincronizar_registro_medicamentos(db) -> int:
    """Baixa o CSV aberto da ANVISA uma vez e atualiza DUAS colecoes:
    - anvisa_registro_medicamentos: so nao-ativos (cancelados/vencidos/
      inativos) - inalterado, usado pela Janela ANVISA como indicador de
      mercado.
    - anvisa_registro_medicamentos_ativos: so ativos - usado pelo Radar
      LMR para responder se ha similar registrado no Brasil (RDC 81/2008).
    """
    timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(CSV_URL, ssl=_ssl_context_com_intermediario()) as resp:
            if resp.status != 200:
                raise RuntimeError(f"CSV de dados abertos da ANVISA retornou status {resp.status}")
            raw = await resp.read()

    # Dataset legado do Datavisa: encoding Latin-1, delimitador ';'.
    text = raw.decode('latin-1')
    reader = csv.DictReader(io.StringIO(text), delimiter=';')

    agora = datetime.now(timezone.utc).isoformat()
    docs_inativos = []
    docs_ativos = []
    for row in reader:
        situacao = (row.get('SITUACAO_REGISTRO') or '').strip()
        nome = (row.get('NOME_PRODUTO') or '').strip()
        principio = (row.get('PRINCIPIO_ATIVO') or '').strip()
        if not situacao or (not nome and not principio):
            continue

        doc = {
            'nome_produto': nome,
            'principio_ativo': principio,
            'situacao_registro': situacao,
            'data_finalizacao_processo': (row.get('DATA_FINALIZACAO_PROCESSO') or '').strip(),
            'data_vencimento_registro': (row.get('DATA_VENCIMENTO_REGISTRO') or '').strip(),
            'categoria_regulatoria': (row.get('CATEGORIA_REGULATORIA') or '').strip(),
            'classe_terapeutica': (row.get('CLASSE_TERAPEUTICA') or '').strip(),
            'empresa_detentora_registro': (row.get('EMPRESA_DETENTORA_REGISTRO') or '').strip(),
            'numero_registro_produto': (row.get('NUMERO_REGISTRO_PRODUTO') or '').strip(),
            'atualizado_em': agora,
        }

        if situacao.lower() == 'ativo':
            docs_ativos.append(doc)
        else:
            docs_inativos.append(doc)

    if not docs_inativos and not docs_ativos:
        logger.warning("ANVISA registro: CSV nao retornou nenhuma linha valida, mantendo dados atuais")
        return 0

    novos_registros = await _detectar_novos_registros(db, docs_ativos) if docs_ativos else []

    if docs_inativos:
        await _substituir_colecao(db, 'anvisa_registro_medicamentos', docs_inativos)
    if docs_ativos:
        await _substituir_colecao(db, 'anvisa_registro_medicamentos_ativos', docs_ativos)

    if novos_registros:
        from services.notificacoes_regulatorias_service import criar_a_partir_de_novos_registros
        criadas = await criar_a_partir_de_novos_registros(db, novos_registros)
        logger.info(f"ANVISA registro: {criadas} notificacao(oes) de novo registro criada(s)")

    logger.info(
        f"ANVISA registro: {len(docs_inativos)} nao-ativos + {len(docs_ativos)} ativos sincronizados"
    )
    return len(docs_inativos) + len(docs_ativos)
