"""
Cria as notificacoes do sino do modulo Janela ANVISA (feed de
inteligencia regulatoria) a partir de duas fontes:

1. Pipeline de scraping ANVISA/DOU (anvisa_scraper.py +
   desabastecimento_service.py, roda a cada 12h) -> categorias
   'desabastecimento', 'cancelamento_suspensao', 'laboratorio'.
2. Sincronizacao diaria de registros ativos da ANVISA
   (anvisa_registro_service.py) -> categoria 'novo_registro'.

Cada notificacao e deduplicada por uma chave estavel (link/titulo para
a fonte 1, numero_registro_produto para a fonte 2) para nao repetir o
mesmo evento a cada execucao agendada.
"""
import uuid
from datetime import datetime, timezone
from typing import Dict, List

CATEGORIAS_BELL = {
    'desabastecimento': 'desabastecimento',
    'interrupção fabricação': 'desabastecimento',
    'descontinuação': 'cancelamento_suspensao',
    'recolhimento': 'cancelamento_suspensao',
    'proibição': 'cancelamento_suspensao',
    'laboratorio': 'laboratorio',
}


async def criar_a_partir_de_alertas_anvisa(db, alertas_processados: List[Dict]) -> int:
    """Cria notificacoes regulatorias (desabastecimento, cancelamento_suspensao,
    laboratorio) a partir da lista retornada por
    DesabastecimentoService.processar_alertas(). Deduplica por link (ou
    titulo, se nao houver link)."""
    criadas = 0
    for alerta in alertas_processados:
        categoria = CATEGORIAS_BELL.get(alerta.get('tipo_alerta'))
        if not categoria:
            continue

        chave_dedup = alerta.get('link') or (alerta.get('titulo') or '')[:120]
        if not chave_dedup:
            continue

        existente = await db.notificacoes_regulatorias.find_one({'chave_dedup': chave_dedup})
        if existente:
            continue

        doc = {
            'id': str(uuid.uuid4()),
            'categoria': categoria,
            'titulo': alerta.get('titulo', ''),
            'descricao': (alerta.get('descricao') or alerta.get('situacao') or '')[:500],
            'medicamento': alerta.get('medicamento_detectado') or alerta.get('medicamento') or '',
            'url_fonte_oficial': alerta.get('link', ''),
            'data_evento': alerta.get('data_publicacao', ''),
            'chave_dedup': chave_dedup,
            'lida': False,
            'criado_em': datetime.now(timezone.utc).isoformat(),
        }
        await db.notificacoes_regulatorias.insert_one(doc)
        criadas += 1

    return criadas


async def criar_a_partir_de_novos_registros(db, novos_registros: List[Dict]) -> int:
    """Cria notificacoes regulatorias (novo_registro) a partir dos
    registros detectados como novos por
    anvisa_registro_service._detectar_novos_registros(). Deduplica por
    numero_registro_produto.

    Nota: o dataset de dados abertos da ANVISA nao fornece uma URL por
    registro individual, entao url_fonte_oficial fica vazio aqui - o
    frontend nao mostra o botao de link para esta categoria.
    """
    criadas = 0
    for registro in novos_registros:
        numero = registro.get('numero_registro_produto', '')
        if not numero:
            continue

        existente = await db.notificacoes_regulatorias.find_one({'chave_dedup': numero})
        if existente:
            continue

        nome = registro.get('nome_produto', '')
        empresa = registro.get('empresa_detentora_registro', '')
        doc = {
            'id': str(uuid.uuid4()),
            'categoria': 'novo_registro',
            'titulo': f'Novo registro ANVISA - {nome}',
            'descricao': f"Empresa: {empresa} | Registro nº {numero}"[:500],
            'medicamento': nome,
            'url_fonte_oficial': '',
            'data_evento': registro.get('data_finalizacao_processo', ''),
            'chave_dedup': numero,
            'lida': False,
            'criado_em': datetime.now(timezone.utc).isoformat(),
        }
        await db.notificacoes_regulatorias.insert_one(doc)
        criadas += 1

    return criadas
