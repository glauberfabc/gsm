# Sino de Notificações — Feed de Inteligência Regulatória Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformar o sino de notificações do módulo Janela ANVISA num feed de inteligência regulatória, disparando exclusivamente para desabastecimento, novos registros, cancelamentos/suspensões (RE) e notícias de laboratório — cada um com link rastreável até a fonte oficial.

**Architecture:** Nova coleção `notificacoes_regulatorias` + módulo dedicado `notificacoes_regulatorias_service.py` que cria notificações a partir de duas fontes já existentes: (1) o pipeline de scraping ANVISA/DOU (`anvisa_scraper.py` + `desabastecimento_service.py`, rodando a cada 12h), ganhando uma nova categoria de classificação `laboratorio`; (2) a sincronização diária de registros ativos da ANVISA (`anvisa_registro_service.py`), ganhando detecção de registros novos por diff antes da troca atômica de coleção. O sino (`Header.jsx`) troca de fonte via `useNotificacoes.js`, sem alterar o motor de oportunidade LMR (que continua existindo, só sai do sino).

**Tech Stack:** Python 3, pytest (sem pytest-asyncio — async via `asyncio.run()`), fakes de Mongo (sem DB real nos testes), React (verificação via `npm run build`, sem testes automatizados de componente no repo).

---

## Task 1: Módulo `notificacoes_regulatorias_service.py`

**Files:**
- Create: `backend/services/notificacoes_regulatorias_service.py`
- Create: `backend/tests/test_notificacoes_regulatorias_service.py`

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_notificacoes_regulatorias_service.py`:

```python
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.notificacoes_regulatorias_service import (
    criar_a_partir_de_alertas_anvisa,
    criar_a_partir_de_novos_registros,
)


class _FakeCollection:
    def __init__(self):
        self.docs = []

    async def find_one(self, query):
        chave = query.get('chave_dedup')
        for d in self.docs:
            if d['chave_dedup'] == chave:
                return d
        return None

    async def insert_one(self, doc):
        self.docs.append(doc)


class _FakeDb:
    def __init__(self):
        self.notificacoes_regulatorias = _FakeCollection()


class TestCriarAPartirDeAlertasAnvisa:
    def test_mapeia_tipo_alerta_para_categoria_do_sino(self):
        db = _FakeDb()
        alertas = [
            {'tipo_alerta': 'desabastecimento', 'titulo': 'Falta de X', 'link': 'https://a.gov.br/1'},
            {'tipo_alerta': 'interrupção fabricação', 'titulo': 'Interrupção Y', 'link': 'https://a.gov.br/2'},
            {'tipo_alerta': 'descontinuação', 'titulo': 'Cancelamento Z', 'link': 'https://a.gov.br/3'},
            {'tipo_alerta': 'recolhimento', 'titulo': 'Recall W', 'link': 'https://a.gov.br/4'},
            {'tipo_alerta': 'proibição', 'titulo': 'Interdição V', 'link': 'https://a.gov.br/5'},
            {'tipo_alerta': 'laboratorio', 'titulo': 'Titularidade U', 'link': 'https://a.gov.br/6'},
        ]

        criadas = asyncio.run(criar_a_partir_de_alertas_anvisa(db, alertas))

        assert criadas == 6
        categorias = {d['titulo']: d['categoria'] for d in db.notificacoes_regulatorias.docs}
        assert categorias['Falta de X'] == 'desabastecimento'
        assert categorias['Interrupção Y'] == 'desabastecimento'
        assert categorias['Cancelamento Z'] == 'cancelamento_suspensao'
        assert categorias['Recall W'] == 'cancelamento_suspensao'
        assert categorias['Interdição V'] == 'cancelamento_suspensao'
        assert categorias['Titularidade U'] == 'laboratorio'

    def test_tipos_fora_de_escopo_nao_geram_notificacao(self):
        db = _FakeDb()
        alertas = [
            {'tipo_alerta': 'importação excepcional', 'titulo': 'A', 'link': 'https://a.gov.br/1'},
            {'tipo_alerta': 'decisão judicial', 'titulo': 'B', 'link': 'https://a.gov.br/2'},
            {'tipo_alerta': 'regulamentação', 'titulo': 'C', 'link': 'https://a.gov.br/3'},
            {'tipo_alerta': 'informativo', 'titulo': 'D', 'link': 'https://a.gov.br/4'},
        ]

        criadas = asyncio.run(criar_a_partir_de_alertas_anvisa(db, alertas))

        assert criadas == 0
        assert db.notificacoes_regulatorias.docs == []

    def test_dedup_por_link_nao_cria_duplicata(self):
        db = _FakeDb()
        alerta = {'tipo_alerta': 'desabastecimento', 'titulo': 'Falta de X', 'link': 'https://a.gov.br/1'}

        primeira = asyncio.run(criar_a_partir_de_alertas_anvisa(db, [alerta]))
        segunda = asyncio.run(criar_a_partir_de_alertas_anvisa(db, [alerta]))

        assert primeira == 1
        assert segunda == 0
        assert len(db.notificacoes_regulatorias.docs) == 1

    def test_campos_do_documento_criado(self):
        db = _FakeDb()
        alerta = {
            'tipo_alerta': 'desabastecimento',
            'titulo': 'Falta de Insulina',
            'descricao': 'Descrição completa',
            'link': 'https://in.gov.br/materia/123',
            'medicamento_detectado': 'Insulina Glargina',
            'data_publicacao': '2026-08-01',
        }

        asyncio.run(criar_a_partir_de_alertas_anvisa(db, [alerta]))

        doc = db.notificacoes_regulatorias.docs[0]
        assert doc['categoria'] == 'desabastecimento'
        assert doc['titulo'] == 'Falta de Insulina'
        assert doc['descricao'] == 'Descrição completa'
        assert doc['medicamento'] == 'Insulina Glargina'
        assert doc['url_fonte_oficial'] == 'https://in.gov.br/materia/123'
        assert doc['data_evento'] == '2026-08-01'
        assert doc['lida'] is False
        assert 'id' in doc
        assert 'criado_em' in doc


class TestCriarAPartirDeNovosRegistros:
    def test_cria_notificacao_para_cada_registro_novo(self):
        db = _FakeDb()
        novos = [
            {'numero_registro_produto': '123456', 'nome_produto': 'Nucala', 'empresa_detentora_registro': 'GSK',
             'data_finalizacao_processo': '2026-08-01'},
        ]

        criadas = asyncio.run(criar_a_partir_de_novos_registros(db, novos))

        assert criadas == 1
        doc = db.notificacoes_regulatorias.docs[0]
        assert doc['categoria'] == 'novo_registro'
        assert 'Nucala' in doc['titulo']
        assert doc['medicamento'] == 'Nucala'
        assert doc['url_fonte_oficial'] == ''
        assert doc['chave_dedup'] == '123456'

    def test_dedup_por_numero_registro_produto(self):
        db = _FakeDb()
        registro = {'numero_registro_produto': '123456', 'nome_produto': 'Nucala',
                     'empresa_detentora_registro': 'GSK', 'data_finalizacao_processo': '2026-08-01'}

        primeira = asyncio.run(criar_a_partir_de_novos_registros(db, [registro]))
        segunda = asyncio.run(criar_a_partir_de_novos_registros(db, [registro]))

        assert primeira == 1
        assert segunda == 0

    def test_ignora_registro_sem_numero(self):
        db = _FakeDb()
        registro = {'nome_produto': 'Sem numero', 'empresa_detentora_registro': 'X'}

        criadas = asyncio.run(criar_a_partir_de_novos_registros(db, [registro]))

        assert criadas == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run (de `backend/`): `pytest tests/test_notificacoes_regulatorias_service.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'services.notificacoes_regulatorias_service'`

- [ ] **Step 3: Criar o módulo**

`backend/services/notificacoes_regulatorias_service.py`:

```python
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

        chave_dedup = alerta.get('link') or alerta.get('titulo', '')[:120]
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_notificacoes_regulatorias_service.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/services/notificacoes_regulatorias_service.py backend/tests/test_notificacoes_regulatorias_service.py
git commit -m "feat: modulo de criacao de notificacoes regulatorias (sino)"
```

---

## Task 2: Detecção de novos registros na sincronização ANVISA

**Files:**
- Modify: `backend/services/anvisa_registro_service.py`
- Modify: `backend/tests/test_anvisa_registro_service_sync.py`

- [ ] **Step 1: Atualizar o `_FakeCollection` do arquivo de teste para suportar `find`/`find_one`/`insert_one`**

O `_FakeCollection` hoje em `backend/tests/test_anvisa_registro_service_sync.py`
(confirmado lendo o arquivo atual) é:

```python
class _FakeCollection:
    def __init__(self, db=None, name=None):
        self._db = db
        self.name = name
        self.deleted = False
        self.inserted = []

    async def delete_many(self, *args, **kwargs):
        self.deleted = True
        self.inserted = []

    async def insert_many(self, docs):
        self.inserted = list(docs)

    async def rename(self, new_name, dropTarget=False):
        # Simula a troca atomica: copia o conteudo desta colecao (temp)
        # para a colecao de destino real no fake db.
        target = self._db[new_name]
        target.inserted = list(self.inserted)
```

Só tem `delete_many`/`insert_many`/`rename` — falta suporte a `find()` (com filtro
`$in`, usado por `_detectar_novos_registros`) e `find_one`/`insert_one` (usados por
`notificacoes_regulatorias_service.py`, Task 1 deste plano). Adicionar, no mesmo
arquivo, logo antes da classe `_FakeCollection`:

```python
class _FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    async def to_list(self, length=None):
        return list(self._docs)
```

E substituir a classe `_FakeCollection` inteira por:

```python
class _FakeCollection:
    def __init__(self, db=None, name=None):
        self._db = db
        self.name = name
        self.deleted = False
        self.inserted = []

    async def delete_many(self, *args, **kwargs):
        self.deleted = True
        self.inserted = []

    async def insert_many(self, docs):
        self.inserted = list(docs)

    async def rename(self, new_name, dropTarget=False):
        # Simula a troca atomica: copia o conteudo desta colecao (temp)
        # para a colecao de destino real no fake db.
        target = self._db[new_name]
        target.inserted = list(self.inserted)

    def find(self, query=None, projection=None):
        query = query or {}
        docs = self.inserted
        for campo, condicao in query.items():
            if isinstance(condicao, dict) and '$in' in condicao:
                valores = set(condicao['$in'])
                docs = [d for d in docs if d.get(campo) in valores]
            else:
                docs = [d for d in docs if d.get(campo) == condicao]
        return _FakeCursor(docs)

    async def find_one(self, query):
        docs = await self.find(query).to_list()
        return docs[0] if docs else None

    async def insert_one(self, doc):
        self.inserted.append(doc)
```

`_FakeDb` **não precisa mudar** — `__getattr__`/`__getitem__` já criam qualquer
coleção sob demanda (incluindo `notificacoes_regulatorias`, que nunca foi acessada
antes neste arquivo), então basta a classe `_FakeCollection` ganhar os métodos
novos.

- [ ] **Step 2: Write the failing tests**

Append ao mesmo arquivo:

```python
class TestDetectarNovosRegistros:
    def test_retorna_apenas_registros_com_numero_novo(self):
        db = _FakeDb()
        db.anvisa_registro_medicamentos_ativos.inserted = [
            {'numero_registro_produto': '111', 'nome_produto': 'Ja Existia'},
        ]
        docs_ativos = [
            {'numero_registro_produto': '111', 'nome_produto': 'Ja Existia'},
            {'numero_registro_produto': '222', 'nome_produto': 'Novo Registro'},
        ]

        novos = asyncio.run(anvisa_registro_service._detectar_novos_registros(db, docs_ativos))

        assert len(novos) == 1
        assert novos[0]['numero_registro_produto'] == '222'

    def test_colecao_antiga_vazia_marca_tudo_como_novo(self):
        db = _FakeDb()
        docs_ativos = [
            {'numero_registro_produto': '111', 'nome_produto': 'A'},
            {'numero_registro_produto': '222', 'nome_produto': 'B'},
        ]

        novos = asyncio.run(anvisa_registro_service._detectar_novos_registros(db, docs_ativos))

        assert len(novos) == 2

    def test_lista_vazia_retorna_vazio(self):
        db = _FakeDb()
        novos = asyncio.run(anvisa_registro_service._detectar_novos_registros(db, []))
        assert novos == []


def test_sincronizar_cria_notificacao_para_registro_novo(monkeypatch):
    monkeypatch.setattr(
        anvisa_registro_service.aiohttp, "ClientSession",
        lambda *a, **kw: _FakeSession(CSV_FAKE),
    )
    db = _FakeDb()
    # "Nucala" (Ativo, no CSV_FAKE) e novo porque a colecao de ativos comeca
    # vazia nesta primeira sincronizacao.
    asyncio.run(anvisa_registro_service.sincronizar_registro_medicamentos(db))

    notificacoes = db.notificacoes_regulatorias.inserted
    assert len(notificacoes) == 1
    assert notificacoes[0]['categoria'] == 'novo_registro'
    assert 'Nucala' in notificacoes[0]['titulo']


def test_sincronizar_nao_duplica_notificacao_em_segunda_execucao(monkeypatch):
    monkeypatch.setattr(
        anvisa_registro_service.aiohttp, "ClientSession",
        lambda *a, **kw: _FakeSession(CSV_FAKE),
    )
    db = _FakeDb()

    asyncio.run(anvisa_registro_service.sincronizar_registro_medicamentos(db))
    asyncio.run(anvisa_registro_service.sincronizar_registro_medicamentos(db))

    notificacoes = db.notificacoes_regulatorias.inserted
    assert len(notificacoes) == 1
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_anvisa_registro_service_sync.py -v -k "DetectarNovosRegistros or registro_novo or nao_duplica"`
Expected: FAIL com `AttributeError: module 'services.anvisa_registro_service' has no attribute '_detectar_novos_registros'`

- [ ] **Step 4: Implementar `_detectar_novos_registros` e integrar em `sincronizar_registro_medicamentos`**

Em `backend/services/anvisa_registro_service.py`, adicionar a função logo após
`_substituir_colecao` (antes de `sincronizar_registro_medicamentos`):

```python
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
```

E onde hoje está (dentro de `sincronizar_registro_medicamentos`):

```python
    if not docs_inativos and not docs_ativos:
        logger.warning("ANVISA registro: CSV nao retornou nenhuma linha valida, mantendo dados atuais")
        return 0

    if docs_inativos:
        await _substituir_colecao(db, 'anvisa_registro_medicamentos', docs_inativos)
    if docs_ativos:
        await _substituir_colecao(db, 'anvisa_registro_medicamentos_ativos', docs_ativos)

    logger.info(
        f"ANVISA registro: {len(docs_inativos)} nao-ativos + {len(docs_ativos)} ativos sincronizados"
    )
    return len(docs_inativos) + len(docs_ativos)
```

vira:

```python
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
```

Note que a detecção acontece **antes** da troca atômica (`_substituir_colecao`),
enquanto a coleção `anvisa_registro_medicamentos_ativos` ainda tem o conteúdo
"antigo" — essencial para o diff funcionar.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_anvisa_registro_service_sync.py -v`
Expected: PASS (7 tests — 2 já existentes + 5 novos: 3 em `TestDetectarNovosRegistros`,
`test_sincronizar_cria_notificacao_para_registro_novo`,
`test_sincronizar_nao_duplica_notificacao_em_segunda_execucao`)

- [ ] **Step 6: Commit**

```bash
git add backend/services/anvisa_registro_service.py backend/tests/test_anvisa_registro_service_sync.py
git commit -m "feat: detecta registros ANVISA novos e gera notificacao regulatoria"
```

---

## Task 3: `KW_LABORATORIO` e filtro de relevância do scraper

**Files:**
- Modify: `backend/services/anvisa_scraper.py`
- Create: `backend/tests/test_anvisa_scraper_filtro_laboratorio.py`

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_anvisa_scraper_filtro_laboratorio.py`:

```python
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.anvisa_scraper import AnvisaScraper

scraper = AnvisaScraper()


class TestFiltrarRelevantesLaboratorio:
    def test_item_com_transferencia_titularidade_passa_no_filtro(self):
        # Titulo deliberadamente SEM nenhuma palavra de KW_SAUDE (ex: "medicamento",
        # "farmácia") para provar que e o KW_LABORATORIO novo que faz o item passar,
        # nao uma coincidencia com uma keyword ja existente.
        items = [{
            'titulo': 'ANVISA publica resolução sobre transferência de titularidade de registro sanitário',
            'descricao': '',
            'link': 'https://in.gov.br/materia/1',
        }]

        resultado = scraper._filtrar_relevantes(items)

        assert len(resultado) == 1

    def test_item_sem_nenhum_gatilho_nao_passa(self):
        items = [{
            'titulo': 'Notícia qualquer sem relação com o setor',
            'descricao': 'Texto genérico sem nenhuma palavra-chave relevante',
            'link': 'https://in.gov.br/materia/2',
        }]

        resultado = scraper._filtrar_relevantes(items)

        assert len(resultado) == 0

    def test_item_com_atualizacao_de_bula_passa(self):
        # Idem: sem "medicamento"/"farmácia"/etc., so o novo gatilho de bula.
        items = [{
            'titulo': 'Laboratório Beta comunica atualização de bula do produto',
            'descricao': '',
            'link': 'https://in.gov.br/materia/3',
        }]

        resultado = scraper._filtrar_relevantes(items)

        assert len(resultado) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_anvisa_scraper_filtro_laboratorio.py -v`
Expected: FAIL em `test_item_com_transferencia_titularidade_passa_no_filtro` e
`test_item_com_atualizacao_de_bula_passa` (os títulos foram escolhidos para não
bater em nenhuma keyword existente — `KW_IMPORTACAO`/`KW_JUDICIAL`/
`KW_DESABASTECIMENTO`/`KW_SAUDE` — nem ter `numero_re`/`tipo_documento`, então hoje
são descartados pelo filtro; só passam depois que `KW_LABORATORIO` existir)

- [ ] **Step 3: Adicionar `KW_LABORATORIO` e atualizar `_filtrar_relevantes`**

Em `backend/services/anvisa_scraper.py`, logo após o bloco `KW_SAUDE` (linhas 51-55
do arquivo original):

```python
KW_SAUDE = [
    'medicamento', 'farmácia', 'princípio ativo',
    'suplemento', 'recolhimento', 'recall', 'interdição',
    'proibição', 'falsificação', 'farmacovigilância',
]
```

adicionar logo abaixo:

```python
KW_LABORATORIO = [
    'transferência de titularidade', 'transferencia de titularidade',
    'alteração pós-registro', 'alteracao pos-registro',
    'atualização de bula', 'atualizacao de bula',
    'alteração de rotulagem', 'alteracao de rotulagem',
    'mudança de titularidade', 'mudanca de titularidade',
]
```

Em `_filtrar_relevantes` (linha 409 do arquivo original), onde hoje está:

```python
            # Verificar relevância
            is_importacao = any(kw in texto for kw in KW_IMPORTACAO)
            is_judicial = any(kw in texto for kw in KW_JUDICIAL)
            is_desabastecimento = any(kw in texto for kw in KW_DESABASTECIMENTO)
            is_saude = any(kw in texto for kw in KW_SAUDE)
            has_re = bool(item.get('numero_re'))
            has_tipo_doc = bool(item.get('tipo_documento'))

            if not (is_importacao or is_judicial or is_desabastecimento or is_saude or has_re or has_tipo_doc):
                continue
```

vira:

```python
            # Verificar relevância
            is_importacao = any(kw in texto for kw in KW_IMPORTACAO)
            is_judicial = any(kw in texto for kw in KW_JUDICIAL)
            is_desabastecimento = any(kw in texto for kw in KW_DESABASTECIMENTO)
            is_saude = any(kw in texto for kw in KW_SAUDE)
            is_laboratorio = any(kw in texto for kw in KW_LABORATORIO)
            has_re = bool(item.get('numero_re'))
            has_tipo_doc = bool(item.get('tipo_documento'))

            if not (is_importacao or is_judicial or is_desabastecimento or is_saude or is_laboratorio or has_re or has_tipo_doc):
                continue
```

Alguns parágrafos abaixo, onde hoje está:

```python
            alertas.append({
                **item,
                'tipo_alerta': tipo,
                'is_importacao': is_importacao,
                'is_judicial': is_judicial,
                'is_desabastecimento': is_desabastecimento,
                'palavra_chave': self._primeira_keyword(texto),
            })
```

vira:

```python
            alertas.append({
                **item,
                'tipo_alerta': tipo,
                'is_importacao': is_importacao,
                'is_judicial': is_judicial,
                'is_desabastecimento': is_desabastecimento,
                'is_laboratorio': is_laboratorio,
                'palavra_chave': self._primeira_keyword(texto),
            })
```

Por fim, `_primeira_keyword` (linha 465 do arquivo original) ganha `KW_LABORATORIO`
na busca, para que `palavra_chave` também capture o gatilho quando for esse o caso:

```python
    @staticmethod
    def _primeira_keyword(texto: str) -> str:
        for kw in KW_IMPORTACAO + KW_JUDICIAL + KW_DESABASTECIMENTO:
            if kw in texto:
                return kw
        return ''
```

vira:

```python
    @staticmethod
    def _primeira_keyword(texto: str) -> str:
        for kw in KW_IMPORTACAO + KW_JUDICIAL + KW_DESABASTECIMENTO + KW_LABORATORIO:
            if kw in texto:
                return kw
        return ''
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_anvisa_scraper_filtro_laboratorio.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/services/anvisa_scraper.py backend/tests/test_anvisa_scraper_filtro_laboratorio.py
git commit -m "feat: filtro de relevancia do scraper reconhece noticias de laboratorio"
```

---

## Task 4: Classificação `laboratorio` — fallback por palavra-chave e prompt do Gemini

**Files:**
- Modify: `backend/services/desabastecimento_service.py`
- Create: `backend/tests/test_desabastecimento_analise_keywords_laboratorio.py`

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_desabastecimento_analise_keywords_laboratorio.py`:

```python
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.desabastecimento_service import DesabastecimentoService

svc = DesabastecimentoService(db=None)  # _analise_keywords nao usa self.db


class TestAnaliseKeywordsLaboratorio:
    def test_transferencia_titularidade_classifica_como_laboratorio(self):
        alertas = [{
            'titulo': 'ANVISA aprova transferência de titularidade do medicamento X',
            'descricao': '',
            'link': 'https://in.gov.br/materia/1',
        }]

        resultado = svc._analise_keywords(alertas)

        assert resultado[0]['tipo_alerta'] == 'laboratorio'

    def test_atualizacao_de_bula_classifica_como_laboratorio(self):
        alertas = [{
            'titulo': 'Laboratório Y comunica atualização de bula',
            'descricao': '',
            'link': 'https://in.gov.br/materia/2',
        }]

        resultado = svc._analise_keywords(alertas)

        assert resultado[0]['tipo_alerta'] == 'laboratorio'

    def test_desabastecimento_continua_tendo_prioridade_sobre_laboratorio(self):
        # Um texto que mistura os dois - desabastecimento tem prioridade
        # porque e checado antes na cadeia if/elif.
        alertas = [{
            'titulo': 'Desabastecimento de medicamento X após transferência de titularidade',
            'descricao': '',
            'link': 'https://in.gov.br/materia/3',
        }]

        resultado = svc._analise_keywords(alertas)

        assert resultado[0]['tipo_alerta'] == 'desabastecimento'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_desabastecimento_analise_keywords_laboratorio.py -v`
Expected: FAIL em `test_transferencia_titularidade_classifica_como_laboratorio` e
`test_atualizacao_de_bula_classifica_como_laboratorio` (hoje caem no `else:
informativo`, já que não batem em nenhuma das categorias existentes)

- [ ] **Step 3: Adicionar branch `laboratorio` em `_analise_keywords`**

Em `backend/services/desabastecimento_service.py`, dentro de `_analise_keywords`,
onde hoje está:

```python
            is_import = any(kw in texto for kw in ['importação excepcional', 'rdc 488', 'rdc 203', 'importação sem registro', 'resolução-re'])
            is_judicial = any(kw in texto for kw in ['decisão judicial', 'ação judicial', 'processo judicial', 'cumprimento de decisão'])
            is_desab = any(kw in texto for kw in ['desabastecimento', 'falta', 'ruptura', 'indisponibilidade'])
            is_interr = any(kw in texto for kw in ['interrupção', 'suspensão fabricação', 'parada produção'])
            is_desc = any(kw in texto for kw in ['descontinuação', 'descontinuado', 'cancelamento registro'])
            is_recolh = any(kw in texto for kw in ['recolhimento', 'recall', 'proíbe', 'proibição', 'interdição', 'apreensão'])

            if is_import:
                tipo, sit, risco, oport = 'importação excepcional', 'importação excepcional autorizada', 'ALTO', 'Importação'
                janela, motivo = True, 'Autorização de importação excepcional detectada'
            elif is_judicial:
                tipo, sit, risco, oport = 'decisão judicial', 'cumprimento de decisão judicial', 'ALTO', 'Importação'
                janela, motivo = True, 'Decisão judicial autoriza importação sem registro'
            elif is_desab:
                tipo, sit, risco, oport = 'desabastecimento', 'falta de medicamento detectada', 'ALTO', 'Importação'
                janela, motivo = True, 'Desabastecimento confirmado pode gerar janela de importação'
            elif is_interr:
                tipo, sit, risco, oport = 'interrupção fabricação', 'interrupção temporária', 'ALTO', 'Importação'
                janela, motivo = True, 'Interrupção de fabricação pode gerar importação excepcional'
            elif is_desc:
                tipo, sit, risco, oport = 'descontinuação', 'saída do mercado', 'ALTO', 'Importação'
                janela, motivo = True, 'Descontinuação pode abrir janela de importação'
            elif is_recolh:
                tipo, sit, risco, oport = 'recolhimento', 'recolhimento em curso', 'ALTO', 'Licitação provável'
                janela, motivo = False, ''
            else:
                tipo, sit, risco, oport = 'informativo', alerta.get('palavra_chave', 'alerta'), 'BAIXO', 'Monitorar'
                janela, motivo = False, ''
```

vira:

```python
            is_import = any(kw in texto for kw in ['importação excepcional', 'rdc 488', 'rdc 203', 'importação sem registro', 'resolução-re'])
            is_judicial = any(kw in texto for kw in ['decisão judicial', 'ação judicial', 'processo judicial', 'cumprimento de decisão'])
            is_desab = any(kw in texto for kw in ['desabastecimento', 'falta', 'ruptura', 'indisponibilidade'])
            is_interr = any(kw in texto for kw in ['interrupção', 'suspensão fabricação', 'parada produção'])
            is_desc = any(kw in texto for kw in ['descontinuação', 'descontinuado', 'cancelamento registro'])
            is_recolh = any(kw in texto for kw in ['recolhimento', 'recall', 'proíbe', 'proibição', 'interdição', 'apreensão'])
            is_laboratorio = any(kw in texto for kw in [
                'transferência de titularidade', 'transferencia de titularidade',
                'alteração pós-registro', 'alteracao pos-registro',
                'atualização de bula', 'atualizacao de bula',
                'alteração de rotulagem', 'alteracao de rotulagem',
                'mudança de titularidade', 'mudanca de titularidade',
            ])

            if is_import:
                tipo, sit, risco, oport = 'importação excepcional', 'importação excepcional autorizada', 'ALTO', 'Importação'
                janela, motivo = True, 'Autorização de importação excepcional detectada'
            elif is_judicial:
                tipo, sit, risco, oport = 'decisão judicial', 'cumprimento de decisão judicial', 'ALTO', 'Importação'
                janela, motivo = True, 'Decisão judicial autoriza importação sem registro'
            elif is_desab:
                tipo, sit, risco, oport = 'desabastecimento', 'falta de medicamento detectada', 'ALTO', 'Importação'
                janela, motivo = True, 'Desabastecimento confirmado pode gerar janela de importação'
            elif is_interr:
                tipo, sit, risco, oport = 'interrupção fabricação', 'interrupção temporária', 'ALTO', 'Importação'
                janela, motivo = True, 'Interrupção de fabricação pode gerar importação excepcional'
            elif is_desc:
                tipo, sit, risco, oport = 'descontinuação', 'saída do mercado', 'ALTO', 'Importação'
                janela, motivo = True, 'Descontinuação pode abrir janela de importação'
            elif is_recolh:
                tipo, sit, risco, oport = 'recolhimento', 'recolhimento em curso', 'ALTO', 'Licitação provável'
                janela, motivo = False, ''
            elif is_laboratorio:
                tipo, sit, risco, oport = 'laboratorio', 'alteração corporativa/regulatória de laboratório', 'BAIXO', 'Monitorar'
                janela, motivo = False, ''
            else:
                tipo, sit, risco, oport = 'informativo', alerta.get('palavra_chave', 'alerta'), 'BAIXO', 'Monitorar'
                janela, motivo = False, ''
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_desabastecimento_analise_keywords_laboratorio.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Adicionar `laboratorio` ao enum do prompt do Gemini**

No mesmo arquivo, dentro de `_analisar_com_ia`, no `system_message`, onde hoje está:

```
3. "tipo_alerta": "importação excepcional" | "decisão judicial" | "desabastecimento" | "descontinuação" | "interrupção fabricação" | "recolhimento" | "proibição" | "regulamentação" | "informativo"
```

vira:

```
3. "tipo_alerta": "importação excepcional" | "decisão judicial" | "desabastecimento" | "descontinuação" | "interrupção fabricação" | "recolhimento" | "proibição" | "regulamentação" | "laboratorio" | "informativo"
   - Use "laboratorio" para: mudança de titularidade de registro, alteração pós-registro, atualização de bula ou alteração de rotulagem crítica por parte do laboratório detentor (quando NÃO envolve desabastecimento nem cancelamento de registro)
```

Essa parte não tem teste automatizado (chamaria a API real do Gemini) — é uma
edição de texto direta. Confirme visualmente que a string ficou correta (aspas
balanceadas, sem quebrar o parsing do `system_message` que é uma string Python
multi-linha) rodando:

Run: `python -c "from services.desabastecimento_service import DesabastecimentoService"`
Expected: nenhum erro de sintaxe/import

- [ ] **Step 6: Commit**

```bash
git add backend/services/desabastecimento_service.py backend/tests/test_desabastecimento_analise_keywords_laboratorio.py
git commit -m "feat: classificacao 'laboratorio' no fallback de keywords e no prompt do Gemini"
```

---

## Task 5: Wiring de `job_anvisa_radar` — criar notificações a partir dos alertas processados

**Files:**
- Modify: `backend/scheduler.py`

- [ ] **Step 1: Atualizar `job_anvisa_radar`**

Onde hoje está (dentro da função que registra o Job 10):

```python
        # Job 10: Radar ANVISA - Desabastecimento (a cada 12h)
        async def job_anvisa_radar():
            try:
                from services.anvisa_scraper import AnvisaScraper
                from services.desabastecimento_service import DesabastecimentoService
                scraper = AnvisaScraper()
                alertas = await scraper.coletar_tudo()
                descont = await scraper.coletar_descontinuacao()
                alertas.extend(descont)
                svc = DesabastecimentoService(_db)
                await svc.processar_alertas(alertas)
                logger.info(f"ANVISA Radar: {len(alertas)} alertas coletados e processados")
            except Exception as e:
                logger.error(f"ANVISA Radar erro: {e}")
```

vira:

```python
        # Job 10: Radar ANVISA - Desabastecimento (a cada 12h)
        async def job_anvisa_radar():
            try:
                from services.anvisa_scraper import AnvisaScraper
                from services.desabastecimento_service import DesabastecimentoService
                from services.notificacoes_regulatorias_service import criar_a_partir_de_alertas_anvisa
                scraper = AnvisaScraper()
                alertas = await scraper.coletar_tudo()
                descont = await scraper.coletar_descontinuacao()
                alertas.extend(descont)
                svc = DesabastecimentoService(_db)
                alertas_processados = await svc.processar_alertas(alertas)
                notificacoes_criadas = await criar_a_partir_de_alertas_anvisa(_db, alertas_processados)
                logger.info(
                    f"ANVISA Radar: {len(alertas)} alertas coletados e processados, "
                    f"{notificacoes_criadas} notificacao(oes) regulatoria(s) criada(s)"
                )
            except Exception as e:
                logger.error(f"ANVISA Radar erro: {e}")
```

- [ ] **Step 2: Sanity check de sintaxe**

Run (de `backend/`): `python -m py_compile scheduler.py`
Expected: sem output (sucesso silencioso)

- [ ] **Step 3: Commit**

```bash
git add backend/scheduler.py
git commit -m "feat: job_anvisa_radar cria notificacoes regulatorias apos processar alertas"
```

---

## Task 6: Endpoints `GET/POST /api/notificacoes/regulatorias*`

**Files:**
- Modify: `backend/server.py`

- [ ] **Step 1: Adicionar os dois novos endpoints**

Em `backend/server.py`, logo após o bloco de rotas
`# ==================== NOTIFICACOES DE OPORTUNIDADE (P4) ====================`
e suas 3 rotas existentes (`/notificacoes/oportunidades`,
`/notificacoes/oportunidades/{alerta_id}/lida`,
`/notificacoes/oportunidades/{alerta_id}`), adicionar um novo bloco:

```python
# ==================== NOTIFICACOES REGULATORIAS (SINO - JANELA ANVISA) ====================

@api_router.get("/notificacoes/regulatorias")
async def listar_notificacoes_regulatorias(limite: int = Query(15, ge=1, le=50)):
    """
    Lista notificacoes regulatorias (sino do modulo Janela ANVISA):
    desabastecimento, cancelamento/suspensao (RE), novo registro,
    noticias de laboratorio. Ordenadas da mais recente para a mais
    antiga.
    """
    try:
        notificacoes = await db.notificacoes_regulatorias.find(
            {}, {"_id": 0}
        ).sort("criado_em", -1).to_list(length=limite)
        nao_lidas = sum(1 for n in notificacoes if not n.get('lida'))
        return {
            "alertas": notificacoes,
            "total": len(notificacoes),
            "nao_lidas": nao_lidas,
        }
    except Exception as e:
        logger.error(f"Erro ao listar notificacoes regulatorias: {e}")
        return {"alertas": [], "total": 0, "nao_lidas": 0}


@api_router.post("/notificacoes/regulatorias/{notificacao_id}/lida")
async def marcar_notificacao_regulatoria_lida(notificacao_id: str):
    """Marca uma notificacao regulatoria como lida."""
    try:
        result = await db.notificacoes_regulatorias.update_one(
            {"id": notificacao_id},
            {"$set": {"lida": True}}
        )
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Notificacao nao encontrada")
        return {"message": "Notificacao marcada como lida", "id": notificacao_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao marcar notificacao regulatoria: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

O formato de resposta (`alertas`/`total`/`nao_lidas`) é intencionalmente igual ao
de `GET /api/notificacoes/oportunidades`, para o hook `useNotificacoes.js` (Task 7)
só precisar trocar a URL, sem mudar a forma de consumir a resposta.

- [ ] **Step 2: Sanity check de sintaxe**

Run (de `backend/`): `python -m py_compile server.py`
Expected: sem output

- [ ] **Step 3: Commit**

```bash
git add backend/server.py
git commit -m "feat: endpoints GET/POST /notificacoes/regulatorias para o sino"
```

---

## Task 7: Frontend — `useNotificacoes.js` aponta para o novo endpoint

**Files:**
- Modify: `frontend/src/hooks/useNotificacoes.js`

- [ ] **Step 1: Trocar as URLs**

Onde hoje está:

```javascript
  const carregarNotificacoes = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/notificacoes/oportunidades?limite=15`);
      setNotificacoes(res.data.alertas || []);
    } catch (err) {
      console.error('Erro ao carregar notificacoes:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const marcarLida = useCallback(async (alertaId) => {
    try {
      await axios.post(`${API}/notificacoes/oportunidades/${alertaId}/lida`);
      setNotificacoes(prev => prev.map(n => n.id === alertaId ? { ...n, lida: true } : n));
    } catch (err) {
      console.error('Erro ao marcar notificacao:', err);
    }
  }, []);
```

vira:

```javascript
  const carregarNotificacoes = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/notificacoes/regulatorias?limite=15`);
      setNotificacoes(res.data.alertas || []);
    } catch (err) {
      console.error('Erro ao carregar notificacoes:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const marcarLida = useCallback(async (alertaId) => {
    try {
      await axios.post(`${API}/notificacoes/regulatorias/${alertaId}/lida`);
      setNotificacoes(prev => prev.map(n => n.id === alertaId ? { ...n, lida: true } : n));
    } catch (err) {
      console.error('Erro ao marcar notificacao:', err);
    }
  }, []);
```

Nenhuma outra parte do hook muda (`naoLidas`, `showDropdown`, `carregarNotificacoes`
no `useEffect` de montagem, etc. seguem iguais).

- [ ] **Step 2: Checagem de compilação**

Run (de `frontend/`): `npm run build`
Expected: build conclui sem erros

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useNotificacoes.js
git commit -m "feat: useNotificacoes aponta para /notificacoes/regulatorias"
```

---

## Task 8: Frontend — reescrever o dropdown do sino em `Header.jsx`

**Files:**
- Modify: `frontend/src/components/layout/Header.jsx`

- [ ] **Step 1: Adicionar `useState` ao import do React**

Onde hoje está (linha 1 do arquivo original):

```jsx
import React, { useRef, useEffect } from 'react';
```

vira:

```jsx
import React, { useRef, useEffect, useState } from 'react';
```

- [ ] **Step 2: Adicionar estado de expansão do item**

Onde hoje está (dentro da função `Header`, logo após a linha que desestrutura
`notificacoes`):

```jsx
  const { notificacoes: alertas = [], naoLidas = 0, showDropdown, setShowDropdown, marcarLida } = notificacoes || {};
  const dropdownRef = useRef(null);
```

vira:

```jsx
  const { notificacoes: alertas = [], naoLidas = 0, showDropdown, setShowDropdown, marcarLida } = notificacoes || {};
  const dropdownRef = useRef(null);
  const [notifExpandidaId, setNotifExpandidaId] = useState(null);
```

- [ ] **Step 3: Reescrever o bloco do dropdown**

Onde hoje está (o bloco completo do dropdown, dentro do `<div className="relative"
ref={dropdownRef}>` do sino):

```jsx
            {showDropdown && (
              <div data-testid="notificacao-dropdown"
                className="absolute right-0 top-full mt-2 w-96 bg-white rounded-2xl shadow-2xl border-2 border-slate-200 z-[100] overflow-hidden">
                <div className="bg-gradient-to-r from-amber-500 to-emerald-500 px-4 py-2.5 flex items-center justify-between">
                  <span className="text-white font-black text-xs uppercase tracking-wider flex items-center gap-2">
                    <Zap size={14}/> Alertas de Oportunidade
                  </span>
                  <span className="text-white/80 text-[10px] font-bold">{naoLidas} nova(s)</span>
                </div>
                <div className="max-h-80 overflow-y-auto divide-y divide-slate-100">
                  {alertas.length === 0 ? (
                    <div className="px-4 py-8 text-center">
                      <Bell size={28} className="text-slate-300 mx-auto mb-2"/>
                      <p className="text-slate-400 text-xs font-bold">Nenhum alerta ainda</p>
                      <p className="text-slate-300 text-[10px]">Alertas aparecem quando score &gt;= 80%</p>
                    </div>
                  ) : alertas.map((a, i) => (
                    <div key={a.id || i}
                      data-testid={`notificacao-item-${i}`}
                      onClick={() => marcarLida?.(a.id)}
                      className={`px-4 py-3 cursor-pointer transition-colors hover:bg-slate-50 ${!a.lida ? 'bg-amber-50/50' : ''}`}>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="bg-gradient-to-r from-amber-400 to-emerald-400 text-slate-900 px-2.5 py-0.5 rounded-full text-[10px] font-black shadow-sm">
                          {a.oportunidade_score}%
                        </span>
                        <span className="text-xs font-black text-slate-800 uppercase truncate">{a.medicamento}</span>
                        {!a.lida && <span className="w-2 h-2 bg-amber-500 rounded-full flex-shrink-0 animate-pulse"/>}
                      </div>
                      <p className="text-[10px] text-slate-500 font-medium line-clamp-2">{a.recomendacao}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-[9px] text-slate-400">{a.categoria_lmr?.toUpperCase()}</span>
                        <span className="text-[9px] text-slate-400">Carga: {a.carga_tributaria}%</span>
                        {a.email_enviado && (
                          <span className="text-[9px] text-emerald-500 font-bold">E-mail enviado</span>
                        )}
                        {a.email_status === 'erro' && (
                          <span className="text-[9px] text-red-500 font-bold">E-mail falhou</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
```

vira:

```jsx
            {showDropdown && (
              <div data-testid="notificacao-dropdown"
                className="absolute right-0 top-full mt-2 w-96 bg-white rounded-2xl shadow-2xl border-2 border-slate-200 z-[100] overflow-hidden">
                <div className="bg-gradient-to-r from-slate-700 to-slate-800 px-4 py-2.5 flex items-center justify-between">
                  <span className="text-white font-black text-xs uppercase tracking-wider flex items-center gap-2">
                    📋 Feed Regulatório ANVISA/DOU
                  </span>
                  <span className="text-white/80 text-[10px] font-bold">{naoLidas} nova(s)</span>
                </div>
                <div className="max-h-80 overflow-y-auto divide-y divide-slate-100">
                  {alertas.length === 0 ? (
                    <div className="px-4 py-8 text-center">
                      <Bell size={28} className="text-slate-300 mx-auto mb-2"/>
                      <p className="text-slate-400 text-xs font-bold">Nenhuma notificação ainda</p>
                      <p className="text-slate-300 text-[10px]">Desabastecimento, novos registros, cancelamentos e notícias de laboratório aparecem aqui</p>
                    </div>
                  ) : alertas.map((a, i) => {
                    const expandida = notifExpandidaId === a.id;
                    const CATEGORIA_COR = {
                      desabastecimento: 'bg-red-100 text-red-700',
                      cancelamento_suspensao: 'bg-orange-100 text-orange-700',
                      novo_registro: 'bg-blue-100 text-blue-700',
                      laboratorio: 'bg-purple-100 text-purple-700',
                    };
                    const CATEGORIA_LABEL = {
                      desabastecimento: 'Desabastecimento',
                      cancelamento_suspensao: 'Cancelamento/Suspensão',
                      novo_registro: 'Novo Registro',
                      laboratorio: 'Laboratório',
                    };
                    return (
                      <div key={a.id || i}
                        data-testid={`notificacao-item-${i}`}
                        onClick={() => { setNotifExpandidaId(expandida ? null : a.id); marcarLida?.(a.id); }}
                        className={`px-4 py-3 cursor-pointer transition-colors hover:bg-slate-50 ${!a.lida ? 'bg-amber-50/50' : ''}`}>
                        <div className="flex items-center gap-2 mb-1">
                          <span className={`px-2 py-0.5 rounded-full text-[10px] font-black shadow-sm ${CATEGORIA_COR[a.categoria] || 'bg-slate-100 text-slate-700'}`}>
                            {CATEGORIA_LABEL[a.categoria] || a.categoria}
                          </span>
                          {!a.lida && <span className="w-2 h-2 bg-amber-500 rounded-full flex-shrink-0 animate-pulse"/>}
                        </div>
                        <p className="text-xs font-bold text-slate-800 line-clamp-2">{a.titulo}</p>
                        <div className="flex items-center gap-2 mt-1">
                          {a.medicamento && <span className="text-[9px] text-slate-400">{a.medicamento}</span>}
                          {a.data_evento && <span className="text-[9px] text-slate-400">{a.data_evento}</span>}
                        </div>
                        {expandida && (
                          <div className="mt-2 pt-2 border-t border-slate-100">
                            <p className="text-[10px] text-slate-500">{a.descricao}</p>
                            {a.url_fonte_oficial && (
                              <a href={a.url_fonte_oficial} target="_blank" rel="noopener noreferrer"
                                onClick={(e) => e.stopPropagation()}
                                className="inline-flex items-center gap-1 mt-2 text-[10px] font-bold text-blue-600 hover:text-blue-800">
                                🔗 Acessar Documento Oficial
                              </a>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
```

- [ ] **Step 4: Checagem de compilação**

Run (de `frontend/`): `npm run build`
Expected: build conclui sem erros

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/layout/Header.jsx
git commit -m "feat: sino renderiza feed regulatorio com expand e link para fonte oficial"
```

---

## Task 9: Regressão de integração

**Files:**
- Modify: `backend/tests/test_lmr_category_margins.py` (ou outro arquivo de
  integração ao vivo já existente — usar o mesmo padrão `BASE_URL`/`requests`)

- [ ] **Step 1: Adicionar teste de estrutura da resposta**

Append a um novo bloco no arquivo (pode ser uma nova classe no mesmo arquivo, ou um
novo arquivo `backend/tests/test_notificacoes_regulatorias_integracao.py` seguindo
o padrão já usado — este plano usa um novo arquivo por clareza):

```python
"""
Regressao de integracao para o feed regulatorio do sino
(GET /api/notificacoes/regulatorias). Bate no endpoint real, seguindo o
mesmo padrao dos demais testes de integracao deste diretorio.
"""
import os
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestNotificacoesRegulatorias:
    def test_endpoint_retorna_estrutura_esperada(self):
        response = requests.get(f"{BASE_URL}/api/notificacoes/regulatorias?limite=15")
        assert response.status_code == 200

        data = response.json()
        assert "alertas" in data
        assert "total" in data
        assert "nao_lidas" in data

        for item in data["alertas"]:
            for campo in ("id", "categoria", "titulo", "descricao", "medicamento",
                          "url_fonte_oficial", "data_evento", "lida", "criado_em"):
                assert campo in item, f"Notificacao sem campo {campo}"
            assert item["categoria"] in (
                "desabastecimento", "cancelamento_suspensao", "novo_registro", "laboratorio"
            ), f"Categoria fora do esperado: {item['categoria']}"
        print(f"✅ /notificacoes/regulatorias: {data['total']} notificacao(oes), estrutura ok")
```

- [ ] **Step 2: Rodar contra o backend local (se disponível)**

Run: `pytest tests/test_notificacoes_regulatorias_integracao.py -v`
Expected: PASS se houver um backend rodando com as mudanças deste plano aplicadas.
Se não houver, é esperado `ConnectionError` (mesmo padrão já visto nas sessões
anteriores) — não bloqueia o commit.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_notificacoes_regulatorias_integracao.py
git commit -m "test: regressao de integracao para GET /notificacoes/regulatorias"
```

---

## Self-Review (already applied before saving this plan)

- **Cobertura da spec:** 4 categorias mapeadas (Task 1), detecção de novos
  registros via diff pré-swap (Task 2), filtro de relevância + classificação
  `laboratorio` no fallback e no prompt Gemini (Tasks 3-4), wiring nos dois jobs
  agendados (Tasks 2 e 5), endpoints novos (Task 6), frontend (Tasks 7-8),
  regressão (Task 9). "Fora de escopo" da spec (e-mail para notificações
  regulatórias, sistema de licitação, URL por registro individual) não tem task
  correspondente, como esperado.
- **Risco cruzado verificado:** Task 2 só lê/escreve nas coleções já dedicadas
  (`anvisa_registro_medicamentos_ativos`, `notificacoes_regulatorias`) — não altera
  `anvisa_registro_medicamentos` (não-ativos), preservando o consumidor existente
  (`_buscar_registro_cancelado`, do plano pausado de busca estrita) e o card RDC 81
  do Radar LMR (`_verificar_registro_ativo`), que só lê, nunca escreve, na coleção
  de ativos.
- **Consistência de nomes:** `criar_a_partir_de_alertas_anvisa` e
  `criar_a_partir_de_novos_registros` usados com a mesma assinatura em todos os
  pontos de chamada (Task 1 define, Tasks 2 e 5 chamam). `CATEGORIAS_BELL` definido
  uma vez em `notificacoes_regulatorias_service.py`, não duplicado em nenhum outro
  arquivo.
- **Sem placeholders:** todos os steps têm código completo.
