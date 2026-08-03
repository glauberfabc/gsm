"""
Sincronizacao do dataset aberto de medicamentos registrados na ANVISA.
Fonte oficial: https://dados.anvisa.gov.br/dados/DADOS_ABERTOS_MEDICAMENTOS.csv

Guarda apenas registros com SITUACAO_REGISTRO != 'Ativo' (cancelados, inativos,
vencidos etc.) na colecao anvisa_registro_medicamentos - um registro ativo nao
e evidencia de desabastecimento, entao nao ha necessidade de guarda-lo.

O arquivo tem ~8MB/dezenas de milhares de linhas, entao e baixado e processado
por um job agendado (nao a cada busca do usuario).
"""
import csv
import io
import logging
from datetime import datetime, timezone

import aiohttp

logger = logging.getLogger(__name__)

CSV_URL = "https://dados.anvisa.gov.br/dados/DADOS_ABERTOS_MEDICAMENTOS.csv"


async def sincronizar_registro_medicamentos(db) -> int:
    """Baixa o CSV aberto da ANVISA e substitui o conteudo de anvisa_registro_medicamentos."""
    timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(CSV_URL) as resp:
            if resp.status != 200:
                raise RuntimeError(f"CSV de dados abertos da ANVISA retornou status {resp.status}")
            raw = await resp.read()

    # Dataset legado do Datavisa: encoding Latin-1, delimitador ';'.
    text = raw.decode('latin-1')
    reader = csv.DictReader(io.StringIO(text), delimiter=';')

    agora = datetime.now(timezone.utc).isoformat()
    docs = []
    for row in reader:
        situacao = (row.get('SITUACAO_REGISTRO') or '').strip()
        if not situacao or situacao.lower() == 'ativo':
            continue

        nome = (row.get('NOME_PRODUTO') or '').strip()
        principio = (row.get('PRINCIPIO_ATIVO') or '').strip()
        if not nome and not principio:
            continue

        docs.append({
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
        })

    if not docs:
        logger.warning("ANVISA registro: CSV nao retornou nenhuma linha nao-ativa, mantendo dados atuais")
        return 0

    await db.anvisa_registro_medicamentos.delete_many({})
    await db.anvisa_registro_medicamentos.insert_many(docs)
    logger.info(f"ANVISA registro: {len(docs)} registros nao-ativos sincronizados")
    return len(docs)
