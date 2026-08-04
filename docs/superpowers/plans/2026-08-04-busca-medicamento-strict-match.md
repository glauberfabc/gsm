# Motor de Busca Estrita — Janela ANVISA (Etapa 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminar falsos positivos no endpoint `GET /api/anvisa/buscar-medicamento` exigindo correspondência estrita por princípio ativo (obrigatória) e concentração (quando informada), nas 7 fontes já existentes.

**Architecture:** Um novo módulo puro (`medicamento_query_parser.py`) extrai princípio ativo/concentração/forma farmacêutica de uma string livre e expõe funções de matching por fronteira de palavra. `medicamento_search_service.py` passa a computar essa estrutura uma vez em `buscar()` e usá-la para filtrar/pontuar os resultados de todas as fontes, em vez do matching por substring solta atual.

**Tech Stack:** Python 3, pytest (sem pytest-asyncio — testes async usam `asyncio.run()`), Motor/pymongo (mockado nos testes com fakes simples, sem Mongo real), aiohttp (não mockado — fontes de rede continuam verificadas manualmente/via teste de integração existente, ver nota abaixo).

**Nota sobre estratégia de teste:** o parser (`medicamento_query_parser.py`) e as 3 fontes que só leem do Mongo (Base GSM, CMED-risco, Registro ANVISA) são testados com TDD real (funções puras + fakes de coleção Mongo, sem rede/DB de verdade). As 4 fontes que fazem scraping HTTP (DOU, PNCP, Notícias ANVISA, ANVISA Descontinuação) já não tinham testes unitários no repo — só testes de integração ao vivo (`test_buscar_medicamento_v2_dama.py`, `test_buscar_medicamento_v3_janela_refactor.py`, que batem em `REACT_APP_BACKEND_URL`). Mantemos essa convenção: a lógica de filtragem em si (que é a parte nova) usa as mesmas funções já testadas do parser, e a Task final estende o teste de integração existente para cobrir os campos novos (`search_query_parsed`, `concentracao_confirmada`) contra o backend rodando de verdade.

---

## Task 1: Módulo do parser — `normalizar` e `contem_termo_estrito`

**Files:**
- Create: `backend/services/medicamento_query_parser.py`
- Create: `backend/tests/test_medicamento_query_parser.py`

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_medicamento_query_parser.py`:

```python
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.medicamento_query_parser import normalizar, contem_termo_estrito


class TestNormalizar:
    def test_remove_acentos_e_minusculas(self):
        assert normalizar("Pó Liofilizado") == "po liofilizado"

    def test_colapsa_espacos(self):
        assert normalizar("  Mepolizumabe   100  ") == "mepolizumabe 100"

    def test_string_vazia(self):
        assert normalizar("") == ""


class TestContemTermoEstrito:
    def test_nao_confunde_aciclovir_com_valaciclovir(self):
        assert contem_termo_estrito("Bula de Valaciclovir 500mg", "Aciclovir") is False

    def test_aciclovir_bate_em_texto_com_aciclovir(self):
        assert contem_termo_estrito("Edital de Aciclovir comprimido", "Aciclovir") is True

    def test_exige_todas_as_palavras_do_termo_composto(self):
        assert contem_termo_estrito("Licitação de Ácido Fólico", "Acido Valproico") is False
        assert contem_termo_estrito("Licitação de Ácido Valproico 250mg", "Acido Valproico") is True

    def test_ignora_acentuacao_e_caixa(self):
        assert contem_termo_estrito("MEPOLIZUMABE injetável", "mepolizumabe") is True

    def test_ignora_palavras_curtas_do_termo(self):
        # "de" tem 2 letras e não entra na exigência de match
        assert contem_termo_estrito("Edital de Aciclovir", "Aciclovir de") is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `backend/`): `pytest tests/test_medicamento_query_parser.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.medicamento_query_parser'`

- [ ] **Step 3: Create the module with `normalizar` and `contem_termo_estrito`**

`backend/services/medicamento_query_parser.py`:

```python
"""
Parser e matching estrito para a busca de medicamento na Janela ANVISA (DAMA).

Extrai princípio ativo / concentração / forma farmacêutica de uma string
livre (ex: "MEPOLIZUMABE 100 MG/ML CANETA APLICADORA") e expõe funções de
correspondência por fronteira de palavra, usadas por
`medicamento_search_service.py` para substituir o matching por substring
solta que causava falsos positivos (ex: PNCP aceitando qualquer edital cujos
4 primeiros caracteres do termo aparecessem em qualquer lugar do texto).
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_medicamento_query_parser.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/services/medicamento_query_parser.py backend/tests/test_medicamento_query_parser.py
git commit -m "feat: normalizar/contem_termo_estrito para matching por fronteira de palavra"
```

---

## Task 2: `contem_concentracao`

**Files:**
- Modify: `backend/services/medicamento_query_parser.py`
- Modify: `backend/tests/test_medicamento_query_parser.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_medicamento_query_parser.py`:

```python
from services.medicamento_query_parser import contem_concentracao


class TestContemConcentracao:
    def test_tolera_variacao_de_espaco(self):
        assert contem_concentracao("Frasco 100mg/ml pronto uso", "100 MG/ML") is True

    def test_tolera_espaco_ao_redor_da_barra(self):
        assert contem_concentracao("Frasco 100 MG / ML pronto uso", "100 MG/ML") is True

    def test_nao_bate_com_dose_diferente(self):
        assert contem_concentracao("Frasco 50 MG/ML", "100 MG/ML") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_medicamento_query_parser.py -v`
Expected: FAIL with `ImportError: cannot import name 'contem_concentracao'`

- [ ] **Step 3: Implement `contem_concentracao`**

Append to `backend/services/medicamento_query_parser.py`:

```python
def contem_concentracao(texto: str, concentracao: str) -> bool:
    """
    Compara concentração tolerando variação de espaço em torno de
    unidades (ex.: '100mg/ml' == '100 MG/ML' == '100 MG / ML').
    """
    def compactar(s: str) -> str:
        return re.sub(r'\s+', '', normalizar(s))

    return compactar(concentracao) in compactar(texto)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_medicamento_query_parser.py -v`
Expected: PASS (12 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/services/medicamento_query_parser.py backend/tests/test_medicamento_query_parser.py
git commit -m "feat: contem_concentracao com tolerancia a espacamento"
```

---

## Task 3: `parse_query` — extração de concentração e forma farmacêutica

**Files:**
- Modify: `backend/services/medicamento_query_parser.py`
- Modify: `backend/tests/test_medicamento_query_parser.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_medicamento_query_parser.py`:

```python
from services.medicamento_query_parser import parse_query


class TestParseQuery:
    def test_extrai_principio_ativo_concentracao_e_forma(self):
        q = parse_query("MEPOLIZUMABE 100 MG/ML CANETA APLICADORA")
        assert q["principio_ativo"] == "MEPOLIZUMABE"
        assert q["concentracao"] == "100 MG/ML"
        assert q["forma_farmaceutica"] == "CANETA APLICADORA"

    def test_extrai_concentracao_sem_forma(self):
        q = parse_query("MEPOLIZUMABE 100 MG/ML")
        assert q["principio_ativo"] == "MEPOLIZUMABE"
        assert q["concentracao"] == "100 MG/ML"
        assert q["forma_farmaceutica"] is None

    def test_busca_so_com_nome_mantem_termo_inteiro(self):
        q = parse_query("Mepolizumabe")
        assert q["principio_ativo"] == "Mepolizumabe"
        assert q["concentracao"] is None
        assert q["forma_farmaceutica"] is None

    def test_concentracao_simples_mg(self):
        q = parse_query("Somatropina 4mg")
        assert q["principio_ativo"] == "Somatropina"
        assert q["concentracao"] == "4mg"

    def test_forma_farmaceutica_com_acento_no_termo_original(self):
        q = parse_query("Ocitocina 5 UI Pó Liofilizado")
        assert q["principio_ativo"] == "Ocitocina"
        assert q["forma_farmaceutica"] == "Pó Liofilizado"

    def test_termo_original_preservado(self):
        q = parse_query("  Mepolizumabe 100 MG/ML  ")
        assert q["termo_original"] == "Mepolizumabe 100 MG/ML"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_medicamento_query_parser.py -v`
Expected: FAIL with `ImportError: cannot import name 'parse_query'`

- [ ] **Step 3: Implement `parse_query`**

Append to `backend/services/medicamento_query_parser.py`:

```python
_REGEX_CONCENTRACAO_COMPOSTA = re.compile(
    r'\d+[.,]?\d*\s*(?:MG|MCG|G|UI)\s*/\s*(?:ML|G|DOSE)'
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
    for forma in FORMAS_FARMACEUTICAS:
        idx = busca.find(forma)
        if idx != -1:
            span_forma = (idx, idx + len(forma))
            forma_farmaceutica = termo[idx:idx + len(forma)]
            break

    principio_ativo = termo
    spans = [s for s in (span_concentracao, span_forma) if s]
    # Remove do fim para o começo para não invalidar os índices dos
    # spans anteriores (nenhum span se sobrepõe).
    for start, end in sorted(spans, key=lambda s: s[0], reverse=True):
        principio_ativo = principio_ativo[:start] + ' ' + principio_ativo[end:]
    principio_ativo = re.sub(r'\s+', ' ', principio_ativo).strip()
    if not principio_ativo:
        principio_ativo = termo

    return QueryEstruturada(
        termo_original=termo,
        principio_ativo=principio_ativo,
        concentracao=concentracao,
        forma_farmaceutica=forma_farmaceutica,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_medicamento_query_parser.py -v`
Expected: PASS (18 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/services/medicamento_query_parser.py backend/tests/test_medicamento_query_parser.py
git commit -m "feat: parse_query extrai concentracao e forma farmaceutica do termo livre"
```

---

## Task 4: `dividir_termo` e `parse_termo_completo` — suporte a nomes compostos com `/`

**Files:**
- Modify: `backend/services/medicamento_query_parser.py`
- Modify: `backend/tests/test_medicamento_query_parser.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_medicamento_query_parser.py`:

```python
from services.medicamento_query_parser import dividir_termo, parse_termo_completo


class TestDividirTermo:
    def test_sem_barra_retorna_termo_unico(self):
        assert dividir_termo("Mepolizumabe") == ["Mepolizumabe"]

    def test_com_barra_divide_em_partes(self):
        partes = dividir_termo("Synvisc Classic 2ml / Hilano G-F 20")
        assert partes == ["Synvisc Classic 2ml", "Hilano G-F 20"]

    def test_barra_com_espacos_extras(self):
        assert dividir_termo("A /  B  / C") == ["A", "B", "C"]


class TestParseTermoCompleto:
    def test_termo_simples_gera_uma_query(self):
        queries = parse_termo_completo("Mepolizumabe 100 MG/ML")
        assert len(queries) == 1
        assert queries[0]["principio_ativo"] == "Mepolizumabe"

    def test_nome_composto_gera_duas_queries(self):
        queries = parse_termo_completo("Synvisc Classic 2ml / Hilano G-F 20")
        assert len(queries) == 2
        assert queries[0]["principio_ativo"] == "Synvisc Classic"
        assert queries[0]["concentracao"] == "2ml"
        assert queries[1]["principio_ativo"] == "Hilano G-F 20"
        assert queries[1]["concentracao"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_medicamento_query_parser.py -v`
Expected: FAIL with `ImportError: cannot import name 'dividir_termo'`

- [ ] **Step 3: Implement `dividir_termo` e `parse_termo_completo`**

Append to `backend/services/medicamento_query_parser.py`:

```python
def dividir_termo(termo: str) -> List[str]:
    """
    Divide nomes compostos com '/' (ex.: 'Synvisc Classic 2ml / Hilano
    G-F 20') em partes individuais, pois o banco pode ter armazenado
    apenas uma das formas do nome. Sem '/', retorna o termo inteiro.
    """
    if '/' in termo:
        partes = [p.strip() for p in termo.split('/') if p.strip()]
        if partes:
            return partes
    return [termo]


def parse_termo_completo(termo: str) -> List[QueryEstruturada]:
    """Aplica `parse_query` a cada parte de `dividir_termo(termo)`."""
    return [parse_query(parte) for parte in dividir_termo(termo)]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_medicamento_query_parser.py -v`
Expected: PASS (23 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/services/medicamento_query_parser.py backend/tests/test_medicamento_query_parser.py
git commit -m "feat: dividir_termo/parse_termo_completo para nomes compostos com barra"
```

---

## Task 5: `resultado_relevante`

**Files:**
- Modify: `backend/services/medicamento_query_parser.py`
- Modify: `backend/tests/test_medicamento_query_parser.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_medicamento_query_parser.py`:

```python
from services.medicamento_query_parser import resultado_relevante


class TestResultadoRelevante:
    def test_retorna_a_query_que_bateu(self):
        queries = parse_termo_completo("Synvisc Classic 2ml / Hilano G-F 20")
        match = resultado_relevante("Edital de Hilano G-F 20 para joelho", queries)
        assert match is not None
        assert match["principio_ativo"] == "Hilano G-F 20"

    def test_retorna_none_quando_nenhuma_parte_bate(self):
        queries = parse_termo_completo("Mepolizumabe 100 MG/ML")
        assert resultado_relevante("Edital de Omalizumabe 75mg", queries) is None

    def test_retorna_primeira_query_que_bater(self):
        queries = parse_termo_completo("Mepolizumabe 100 MG/ML")
        match = resultado_relevante("Bula de Mepolizumabe injetável", queries)
        assert match is not None
        assert match["principio_ativo"] == "Mepolizumabe"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_medicamento_query_parser.py -v`
Expected: FAIL with `ImportError: cannot import name 'resultado_relevante'`

- [ ] **Step 3: Implement `resultado_relevante`**

Append to `backend/services/medicamento_query_parser.py`:

```python
def resultado_relevante(texto: str, queries: List[QueryEstruturada]) -> Optional[QueryEstruturada]:
    """
    Retorna a primeira `QueryEstruturada` cujo `principio_ativo` bate em
    `texto` (via `contem_termo_estrito`), ou None se nenhuma bater.
    Usado pelas 7 fontes de `medicamento_search_service.py` para decidir
    se um resultado é relevante e, em caso positivo, qual concentração
    verificar.
    """
    for q in queries:
        if contem_termo_estrito(texto, q['principio_ativo']):
            return q
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_medicamento_query_parser.py -v`
Expected: PASS (26 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/services/medicamento_query_parser.py backend/tests/test_medicamento_query_parser.py
git commit -m "feat: resultado_relevante seleciona a query estruturada que casa com um texto"
```

---

## Task 6: Fakes de Mongo para testar as fontes de DB + wiring da fonte Base GSM

**Files:**
- Create: `backend/tests/test_medicamento_search_service_unit.py`
- Modify: `backend/services/medicamento_search_service.py:339-363` (método `_buscar_alertas_db`)

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_medicamento_search_service_unit.py`:

```python
"""
Testes unitarios das fontes de busca da Janela ANVISA que so leem do
Mongo (Base GSM, CMED-risco, Registro ANVISA) usando um fake de
colecao/cursor, sem Mongo real e sem rede. As fontes que fazem
scraping HTTP (DOU, PNCP, Noticias ANVISA, ANVISA Descontinuacao) sao
cobertas pelo teste de integracao ao vivo existente
(test_buscar_medicamento_v3_janela_refactor.py), como ja era antes
desta mudanca.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.medicamento_search_service import MedicamentoSearchService
from services.medicamento_query_parser import parse_termo_completo


class _FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, *args, **kwargs):
        return self

    def limit(self, n):
        return self

    async def to_list(self, length=None):
        return list(self._docs)


class _FakeCollection:
    def __init__(self, docs):
        self._docs = docs

    def find(self, *args, **kwargs):
        return _FakeCursor(self._docs)


class _FakeDb:
    def __init__(self, anvisa_alertas=None, anvisa_registro_medicamentos=None):
        self.anvisa_alertas = _FakeCollection(anvisa_alertas or [])
        self.anvisa_registro_medicamentos = _FakeCollection(anvisa_registro_medicamentos or [])


class TestBuscarAlertasDb:
    def test_descarta_falso_positivo_por_substring(self):
        docs = [
            {"principio_ativo": "VALACICLOVIR", "titulo": "Alerta Valaciclovir",
             "medicamento_detectado": "Valaciclovir", "medicamento": ""},
            {"principio_ativo": "ACICLOVIR", "titulo": "Alerta Aciclovir 200mg",
             "medicamento_detectado": "Aciclovir", "medicamento": ""},
        ]
        db = _FakeDb(anvisa_alertas=docs)
        svc = MedicamentoSearchService(db)
        queries = parse_termo_completo("Aciclovir")

        results = asyncio.run(svc._buscar_alertas_db(queries))

        titulos = [r["titulo"] for r in results]
        assert "Alerta Aciclovir 200mg" in titulos
        assert "Alerta Valaciclovir" not in titulos

    def test_marca_concentracao_nao_confirmada_quando_ausente_no_texto(self):
        docs = [{"principio_ativo": "MEPOLIZUMABE", "titulo": "Alerta Mepolizumabe",
                  "medicamento_detectado": "", "medicamento": ""}]
        db = _FakeDb(anvisa_alertas=docs)
        svc = MedicamentoSearchService(db)
        queries = parse_termo_completo("Mepolizumabe 100 MG/ML")

        results = asyncio.run(svc._buscar_alertas_db(queries))

        assert len(results) == 1
        assert results[0]["concentracao_confirmada"] is False

    def test_marca_concentracao_confirmada_quando_presente_no_texto(self):
        docs = [{"principio_ativo": "MEPOLIZUMABE", "titulo": "Alerta Mepolizumabe 100 MG/ML",
                  "medicamento_detectado": "", "medicamento": ""}]
        db = _FakeDb(anvisa_alertas=docs)
        svc = MedicamentoSearchService(db)
        queries = parse_termo_completo("Mepolizumabe 100 MG/ML")

        results = asyncio.run(svc._buscar_alertas_db(queries))

        assert results[0]["concentracao_confirmada"] is True

    def test_nome_composto_com_barra_bate_em_qualquer_metade(self):
        docs = [{"principio_ativo": "", "titulo": "Alerta Hilano G-F 20",
                  "medicamento_detectado": "Hilano G-F 20", "medicamento": ""}]
        db = _FakeDb(anvisa_alertas=docs)
        svc = MedicamentoSearchService(db)
        queries = parse_termo_completo("Synvisc Classic 2ml / Hilano G-F 20")

        results = asyncio.run(svc._buscar_alertas_db(queries))

        assert len(results) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_medicamento_search_service_unit.py -v`
Expected: FAIL with `TypeError: _buscar_alertas_db() takes 1 positional argument but 2 were given` (assinatura atual é `_buscar_alertas_db(self, termo)`)

- [ ] **Step 3: Reescrever `_buscar_alertas_db`**

Em `backend/services/medicamento_search_service.py`, no topo do arquivo, adicionar o import (junto aos demais imports, após a linha `from bs4 import BeautifulSoup`):

```python
from services.medicamento_query_parser import (
    QueryEstruturada, dividir_termo, parse_termo_completo,
    contem_termo_estrito, contem_concentracao, resultado_relevante,
)
```

Substituir o método inteiro (linhas 339-363):

```python
    # ===================== FONTE 2: DB ALERTAS =====================
    async def _buscar_alertas_db(self, queries_estruturadas: List[QueryEstruturada]) -> List[Dict]:
        or_conditions = []
        for q in queries_estruturadas:
            r = re.compile(re.escape(q['principio_ativo']), re.IGNORECASE)
            or_conditions.extend([
                {"medicamento_detectado": r},
                {"principio_ativo": r},
                {"titulo": r},
                {"medicamento": r},
            ])

        cursor = self.db.anvisa_alertas.find(
            {"$or": or_conditions},
            {"_id": 0}
        ).sort("coletado_em", -1).limit(20)
        candidatos = await cursor.to_list(length=20)

        resultados = []
        for r in candidatos:
            texto = ' '.join(str(r.get(campo, '')) for campo in
                              ('medicamento_detectado', 'principio_ativo', 'titulo', 'medicamento'))
            match = resultado_relevante(texto, queries_estruturadas)
            if not match:
                continue
            r['fonte_busca'] = 'Base GSM'
            r['concentracao_confirmada'] = (
                contem_concentracao(texto, match['concentracao']) if match['concentracao'] else None
            )
            resultados.append(r)
        return resultados
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_medicamento_search_service_unit.py -v`
Expected: PASS (4 tests). Também rode `pytest tests/test_medicamento_query_parser.py -v` para garantir que nada quebrou (26 tests, PASS).

- [ ] **Step 5: Commit**

```bash
git add backend/services/medicamento_search_service.py backend/tests/test_medicamento_search_service_unit.py
git commit -m "fix: Base GSM usa matching estrito em vez de substring solta"
```

---

## Task 7: Wiring da fonte CMED-risco

**Files:**
- Modify: `backend/services/medicamento_search_service.py:365-387` (método `_buscar_cmed_db`)
- Modify: `backend/tests/test_medicamento_search_service_unit.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_medicamento_search_service_unit.py`:

```python
class TestBuscarCmedDb:
    def test_descarta_falso_positivo_por_substring(self):
        docs = [
            {"principio_ativo": "OMALIZUMABE", "titulo": "Risco Omalizumabe", "is_cmed": True},
            {"principio_ativo": "MEPOLIZUMABE", "titulo": "Risco Mepolizumabe 100 MG/ML", "is_cmed": True},
        ]
        db = _FakeDb(anvisa_alertas=docs)
        svc = MedicamentoSearchService(db)
        queries = parse_termo_completo("Mepolizumabe 100 MG/ML")

        results = asyncio.run(svc._buscar_cmed_db(queries))

        titulos = [r["titulo"] for r in results]
        assert "Risco Mepolizumabe 100 MG/ML" in titulos
        assert "Risco Omalizumabe" not in titulos
        assert results[0]["concentracao_confirmada"] is True
        assert results[0]["fonte_busca"] == "CMED"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_medicamento_search_service_unit.py -v`
Expected: FAIL with `TypeError: _buscar_cmed_db() takes 1 positional argument but 2 were given`

- [ ] **Step 3: Reescrever `_buscar_cmed_db`**

Substituir o método inteiro (linhas 365-387 do arquivo original) por:

```python
    # ===================== FONTE 3: CMED DB =====================
    async def _buscar_cmed_db(self, queries_estruturadas: List[QueryEstruturada]) -> List[Dict]:
        or_conditions = []
        for q in queries_estruturadas:
            r = re.compile(re.escape(q['principio_ativo']), re.IGNORECASE)
            or_conditions.extend([
                {"medicamento_detectado": r},
                {"principio_ativo": r},
                {"titulo": r},
            ])
        cursor = self.db.anvisa_alertas.find(
            {"$and": [
                {"is_cmed": True},
                {"$or": or_conditions},
            ]},
            {"_id": 0}
        ).limit(10)
        candidatos = await cursor.to_list(length=10)

        resultados = []
        for r in candidatos:
            texto = ' '.join(str(r.get(campo, '')) for campo in
                              ('medicamento_detectado', 'principio_ativo', 'titulo'))
            match = resultado_relevante(texto, queries_estruturadas)
            if not match:
                continue
            r['fonte_busca'] = 'CMED'
            r['concentracao_confirmada'] = (
                contem_concentracao(texto, match['concentracao']) if match['concentracao'] else None
            )
            resultados.append(r)
        return resultados
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_medicamento_search_service_unit.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/services/medicamento_search_service.py backend/tests/test_medicamento_search_service_unit.py
git commit -m "fix: CMED-risco usa matching estrito em vez de substring solta"
```

---

## Task 8: Wiring da fonte Registro ANVISA (dados abertos)

**Files:**
- Modify: `backend/services/medicamento_search_service.py:581-629` (método `_buscar_registro_cancelado`)
- Modify: `backend/tests/test_medicamento_search_service_unit.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_medicamento_search_service_unit.py`:

```python
class TestBuscarRegistroCancelado:
    def test_descarta_falso_positivo_por_substring(self):
        docs = [
            {"nome_produto": "Xolair", "principio_ativo": "OMALIZUMABE",
             "situacao_registro": "cancelado", "empresa_detentora_registro": "Lab A",
             "data_finalizacao_processo": "2025-01-01"},
            {"nome_produto": "Nucala", "principio_ativo": "MEPOLIZUMABE",
             "situacao_registro": "cancelado", "empresa_detentora_registro": "Lab B",
             "data_finalizacao_processo": "2025-02-01"},
        ]
        db = _FakeDb(anvisa_registro_medicamentos=docs)
        svc = MedicamentoSearchService(db)
        queries = parse_termo_completo("Mepolizumabe")

        results = asyncio.run(svc._buscar_registro_cancelado(queries))

        assert len(results) == 1
        assert "Nucala" in results[0]["titulo"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_medicamento_search_service_unit.py -v`
Expected: FAIL with `TypeError: _buscar_registro_cancelado() takes 1 positional argument but 2 were given`

- [ ] **Step 3: Reescrever `_buscar_registro_cancelado`**

Substituir o método inteiro (linhas 581-629 do arquivo original) por:

```python
    # ===================== FONTE 7: REGISTRO ANVISA (DADOS ABERTOS) =====================
    async def _buscar_registro_cancelado(self, queries_estruturadas: List[QueryEstruturada]) -> List[Dict]:
        """
        Busca registros de medicamentos cancelados/inativos/vencidos no dataset
        aberto da ANVISA (sincronizado periodicamente por job, ver
        services/anvisa_registro_service.py). Registro ativo não é indício de
        nada, por isso a coleção só guarda os não-ativos.

        Classificado como indicador de mercado (mesma categoria do PNCP), não
        como prova legal - um registro cancelado não comprova sozinho que o
        medicamento está em falta (pode haver outros produtos com o mesmo
        princípio ativo ainda ativos no mercado).
        """
        or_conditions = []
        for q in queries_estruturadas:
            r = re.compile(re.escape(q['principio_ativo']), re.IGNORECASE)
            or_conditions.extend([
                {"nome_produto": r},
                {"principio_ativo": r},
            ])

        cursor = self.db.anvisa_registro_medicamentos.find(
            {"$or": or_conditions}, {"_id": 0}
        ).sort("data_finalizacao_processo", -1).limit(15)
        candidatos = await cursor.to_list(length=15)

        resultados = []
        for d in candidatos:
            texto = f"{d.get('nome_produto', '')} {d.get('principio_ativo', '')}"
            match = resultado_relevante(texto, queries_estruturadas)
            if not match:
                continue

            situacao = d.get('situacao_registro', '')
            nome = d.get('nome_produto', '')
            empresa = d.get('empresa_detentora_registro', '')
            resultados.append({
                'titulo': f'Registro {situacao.upper()} - {nome}',
                'descricao': (
                    f"Princípio ativo: {d.get('principio_ativo', '')} | "
                    f"Empresa: {empresa} | Situação: {situacao}"
                )[:300],
                'link': '',
                'data_publicacao': d.get('data_finalizacao_processo', ''),
                'fonte': 'ANVISA Registro',
                'fonte_busca': 'Registro ANVISA (dados abertos)',
                'tipo_alerta': 'indicador mercado',
                'tipo_documento': 'Situação de registro',
                'indicador_mercado': True,
                'situacao_licitacao': f'REGISTRO {situacao.upper()}',
                'concentracao_confirmada': (
                    contem_concentracao(texto, match['concentracao']) if match['concentracao'] else None
                ),
            })
        return resultados
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_medicamento_search_service_unit.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/services/medicamento_search_service.py backend/tests/test_medicamento_search_service_unit.py
git commit -m "fix: Registro ANVISA usa matching estrito em vez de substring solta"
```

---

## Task 9: Wiring da fonte DOU

**Files:**
- Modify: `backend/services/medicamento_search_service.py:252-315` (método `_buscar_dou`)

- [ ] **Step 1: Reescrever `_buscar_dou`**

Não há teste unitário novo aqui (fonte de rede — ver nota de estratégia de teste no topo do plano; a Task 13 estende o teste de integração ao vivo). Substituir o método inteiro (linhas 252-315 do arquivo original) por:

```python
    # ===================== FONTE 1: DOU =====================
    async def _buscar_dou(self, session, termo: str, queries_estruturadas: List[QueryEstruturada]) -> List[Dict]:
        """Busca no DOU com frases exatas estratégicas."""
        resultados = []
        queries = [
            termo,
            f'{termo} desabastecimento',
            f'{termo} dispensa de licitação',
        ]

        for query in queries:
            try:
                encoded = urllib.parse.quote(query)
                url = f'https://www.in.gov.br/consulta/-/buscar/dou?q={encoded}&s=todos&exactDate=ano'
                async with session.get(url) as resp:
                    if resp.status != 200:
                        continue
                    html = await resp.text()

                items = self._extract_dou_json(html)
                for item in items[:12]:
                    titulo = item.get('title', '').strip()
                    if not titulo or len(titulo) < 10:
                        continue

                    # O DOU retorna o trecho relevante no campo 'content' (com o termo
                    # buscado destacado em <span class='highlight'>), não em 'abstract'.
                    # 'abstract' não existe mais no formato atual da API; mantido como
                    # fallback caso volte a aparecer em formatos antigos.
                    abstract_raw = item.get('abstract') or item.get('content') or ''
                    abstract = re.sub(r'<[^>]+>', ' ', abstract_raw)
                    abstract = re.sub(r'\s+', ' ', abstract).strip()

                    # Filtro de relevância estrito: título+abstract precisa bater com
                    # o princípio ativo de alguma das partes do termo buscado.
                    texto_item = titulo + ' ' + abstract
                    match = resultado_relevante(texto_item, queries_estruturadas)
                    if not match:
                        continue

                    href = item.get('urlTitle', '')
                    link = f"https://www.in.gov.br/web/dou/-/{href}" if href else ''

                    resultados.append({
                        'titulo': titulo,
                        'descricao': abstract[:300] if abstract else '',
                        'link': link,
                        'data_publicacao': item.get('pubDate', ''),
                        'fonte': 'DOU',
                        'fonte_busca': 'DOU',
                        'tipo_documento': item.get('artType', 'Publicação DOU'),
                        'secao': item.get('pubName', ''),
                        'tipo_alerta': self._detectar_tipo_alerta(titulo + ' ' + abstract),
                        'concentracao_confirmada': (
                            contem_concentracao(texto_item, match['concentracao']) if match['concentracao'] else None
                        ),
                    })
            except Exception as e:
                logger.error(f"DOU search error for '{query}': {e}")

        return resultados
```

- [ ] **Step 2: Sanity check de sintaxe**

Run (de `backend/`): `python -m py_compile services/medicamento_search_service.py`
Expected: sem output (sucesso silencioso)

- [ ] **Step 3: Commit**

```bash
git add backend/services/medicamento_search_service.py
git commit -m "fix: DOU usa matching estrito em vez de qualquer token >3 chars"
```

---

## Task 10: Wiring da fonte PNCP Deserto/Fracassado

**Files:**
- Modify: `backend/services/medicamento_search_service.py:458-539` (método `_buscar_pncp_deserto`)

- [ ] **Step 1: Reescrever `_buscar_pncp_deserto`**

Substituir o método inteiro (linhas 458-539 do arquivo original). A única mudança de lógica é a linha do filtro de relevância (`if termo.lower()[:4] not in full: continue` vira o filtro estrito) e a adição de `concentracao_confirmada` no dict do resultado — o resto do método (parsing de link, classificação de status) fica igual:

```python
    # ===================== FONTE 5: PNCP DESERTO/FRACASSADO =====================
    async def _buscar_pncp_deserto(self, session, termo: str, queries_estruturadas: List[QueryEstruturada]) -> List[Dict]:
        """
        Busca licitações no PNCP como INDICADORES DE MERCADO:
        - Contratação Direta / Dispensa / Deserto / Fracassado
        - NÃO ativa 'Janela Aberta' (precisa de publicação oficial DOU/ANVISA)
        """
        resultados = []
        encoded = urllib.parse.quote(termo)
        url = f'https://pncp.gov.br/api/search/?q={encoded}&tipos_documento=edital&pagina=1&tam_pagina=30'

        try:
            headers = {**self.headers, 'Accept': 'application/json'}
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()

            items = data.get('items', [])

            for item in items[:30]:
                title = item.get('title', '')
                desc = item.get('description', '')
                full = title + ' ' + desc
                created = item.get('createdAt', '')[:10]

                # Verificar relevância estrita do princípio ativo (substitui o
                # antigo `termo.lower()[:4] not in full`, que aceitava qualquer
                # edital cujos 4 primeiros caracteres do termo aparecessem em
                # qualquer lugar do texto).
                match = resultado_relevante(full, queries_estruturadas)
                if not match:
                    continue

                full_lower = full.lower()

                # Detect patterns indicating JANELA ABERTA
                is_contratacao_direta = 'contratação direta' in full_lower or 'contratacao direta' in full_lower
                is_dispensa = 'dispensa' in full_lower
                is_deserto = 'deserto' in full_lower or 'desert' in full_lower
                is_fracassado = 'fracassado' in full_lower or 'fracass' in full_lower
                is_emergencial = 'emergencial' in full_lower or 'emergência' in full_lower or 'emergencia' in full_lower

                if not any([is_contratacao_direta, is_dispensa, is_deserto, is_fracassado, is_emergencial]):
                    continue

                # Build PNCP link
                orgao_cnpj = item.get('orgao_cnpj', '')
                ano = item.get('ano', '')
                seq = item.get('numero_sequencial', '')
                link_pncp = ''
                if orgao_cnpj and ano and seq:
                    link_pncp = f'https://pncp.gov.br/app/editais/{orgao_cnpj}/{ano}/{seq}'
                elif item.get('item_url'):
                    link_pncp = item['item_url']
                    if not link_pncp.startswith('http'):
                        link_pncp = f'https://pncp.gov.br{link_pncp}'

                # Classify - PNCP é indicador de mercado, NÃO prova legal
                if is_deserto or is_fracassado:
                    status_text = 'DESERTO/FRACASSADO'
                    tipo_alerta = 'indicador mercado'
                elif is_emergencial:
                    status_text = 'DISPENSA EMERGENCIAL'
                    tipo_alerta = 'indicador mercado'
                elif is_contratacao_direta:
                    status_text = 'CONTRATAÇÃO DIRETA'
                    tipo_alerta = 'indicador mercado'
                else:
                    status_text = 'DISPENSA'
                    tipo_alerta = 'indicador mercado'

                resultados.append({
                    'titulo': f'{status_text} - {title[:80]}',
                    'descricao': desc[:250],
                    'link': link_pncp,
                    'data_publicacao': created,
                    'fonte': 'PNCP',
                    'fonte_busca': f'PNCP {status_text}',
                    'tipo_alerta': tipo_alerta,
                    'tipo_documento': f'Licitação {status_text}',
                    'indicador_mercado': True,
                    'situacao_licitacao': status_text,
                    'concentracao_confirmada': (
                        contem_concentracao(full, match['concentracao']) if match['concentracao'] else None
                    ),
                })

        except Exception as e:
            logger.error(f"PNCP deserto search: {e}")

        return resultados
```

- [ ] **Step 2: Sanity check de sintaxe**

Run: `python -m py_compile services/medicamento_search_service.py`
Expected: sem output

- [ ] **Step 3: Commit**

```bash
git add backend/services/medicamento_search_service.py
git commit -m "fix: PNCP usa matching estrito em vez de 'termo[:4] in full'"
```

---

## Task 11: Wiring das fontes Notícias ANVISA e ANVISA Descontinuação

**Files:**
- Modify: `backend/services/medicamento_search_service.py:390-455` (método `_buscar_noticias_anvisa`)
- Modify: `backend/services/medicamento_search_service.py:542-578` (método `_buscar_descontinuacao`)

- [ ] **Step 1: Reescrever `_buscar_noticias_anvisa`**

Trocar a assinatura e o bloco de filtro. Onde hoje está:

```python
    async def _buscar_noticias_anvisa(self, session, termo: str) -> List[Dict]:
```

vira:

```python
    async def _buscar_noticias_anvisa(self, session, termo: str, queries_estruturadas: List[QueryEstruturada]) -> List[Dict]:
```

E onde hoje está (dentro do método, substitui o bloco `words = ...` e o `if words and not any(...)`):

```python
            words = [w.lower() for w in termo.split() if len(w) >= 3]
            for li in lista.find_all('li', recursive=False)[:10]:
```

vira (remove a linha `words = ...`, mantém o loop):

```python
            for li in lista.find_all('li', recursive=False)[:10]:
```

E onde hoje está:

```python
                    full = (titulo + ' ' + descricao).lower()
                    if words and not any(w in full for w in words):
                        continue

                    resultados.append({
                        'titulo': titulo,
                        'link': link,
                        'data_publicacao': data_pub,
                        'descricao': descricao,
                        'fonte': 'Notícias ANVISA',
                        'fonte_busca': 'Notícias ANVISA',
                        'tipo_alerta': self._detectar_tipo_alerta(titulo + ' ' + descricao),
                    })
```

vira:

```python
                    texto_item = titulo + ' ' + descricao
                    match = resultado_relevante(texto_item, queries_estruturadas)
                    if not match:
                        continue

                    resultados.append({
                        'titulo': titulo,
                        'link': link,
                        'data_publicacao': data_pub,
                        'descricao': descricao,
                        'fonte': 'Notícias ANVISA',
                        'fonte_busca': 'Notícias ANVISA',
                        'tipo_alerta': self._detectar_tipo_alerta(titulo + ' ' + descricao),
                        'concentracao_confirmada': (
                            contem_concentracao(texto_item, match['concentracao']) if match['concentracao'] else None
                        ),
                    })
```

- [ ] **Step 2: Reescrever `_buscar_descontinuacao`**

Substituir o método inteiro (linhas 542-578 do arquivo original) por:

```python
    # ===================== FONTE 6: ANVISA DESCONTINUAÇÃO =====================
    async def _buscar_descontinuacao(self, session, termo: str, queries_estruturadas: List[QueryEstruturada]) -> List[Dict]:
        """Busca na página ANVISA de descontinuação de medicamentos."""
        resultados = []
        url = 'https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/descontinuacao-de-medicamentos'

        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return []
                html = await resp.text()

            soup = BeautifulSoup(html, 'html.parser')
            content = soup.find('div', id='content-core') or soup.find('article') or soup
            text = content.get_text(separator='\n', strip=True)

            match = resultado_relevante(text, queries_estruturadas)
            if match:
                lines = text.split('\n')
                relevant = [ln.strip() for ln in lines if contem_termo_estrito(ln, match['principio_ativo'])]

                if relevant:
                    resultados.append({
                        'titulo': f'{termo} - Descontinuação ANVISA detectada',
                        'descricao': ' | '.join(relevant[:3])[:300],
                        'link': url,
                        'fonte': 'ANVISA',
                        'fonte_busca': 'ANVISA Descontinuação',
                        'tipo_alerta': 'descontinuação',
                        'risco': 'ALTO',
                        'concentracao_confirmada': (
                            contem_concentracao(text, match['concentracao']) if match['concentracao'] else None
                        ),
                    })
        except Exception as e:
            logger.error(f"ANVISA descontinuação search: {e}")

        return resultados
```

- [ ] **Step 3: Sanity check de sintaxe**

Run: `python -m py_compile services/medicamento_search_service.py`
Expected: sem output

- [ ] **Step 4: Commit**

```bash
git add backend/services/medicamento_search_service.py
git commit -m "fix: Noticias ANVISA e ANVISA Descontinuacao usam matching estrito"
```

---

## Task 12: Wiring de `buscar()` — computar `queries_estruturadas` uma vez e repassar

**Files:**
- Modify: `backend/services/medicamento_search_service.py:112-136` (início do método `buscar`)

- [ ] **Step 1: Atualizar o corpo de `buscar()`**

Onde hoje está:

```python
    async def buscar(self, medicamento: str) -> Dict:
        """Busca completa com priorização dinâmica DAMA."""
        termo = medicamento.strip()
        if not termo:
            return {"resultados": [], "total": 0, "fontes_consultadas": []}

        resultados = []
        fontes = []

        async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as session:
            # As 6 fontes são consultadas em paralelo via asyncio.gather() - cada uma
            # com seu próprio try/except isolado, para que uma fonte lenta ou com erro
            # não atrase nem derrube as demais.
            tasks = [
                self._buscar_fonte("DOU - Diário Oficial da União", self._buscar_dou(session, termo)),
                self._buscar_fonte("Base de Alertas GSM", self._buscar_alertas_db(termo)),
                self._buscar_fonte("CMED - Risco de Desabastecimento", self._buscar_cmed_db(termo)),
                self._buscar_fonte("Notícias ANVISA", self._buscar_noticias_anvisa(session, termo)),
                self._buscar_fonte("PNCP - Licitações Desertas/Fracassadas", self._buscar_pncp_deserto(session, termo)),
                self._buscar_fonte("ANVISA - Descontinuação", self._buscar_descontinuacao(session, termo)),
                self._buscar_fonte("Registro ANVISA (Cancelados/Inativos)", self._buscar_registro_cancelado(termo)),
            ]
            for nome, items, status in await asyncio.gather(*tasks):
                resultados.extend(items)
                fontes.append({"nome": nome, "total": len(items), "status": status})
```

vira:

```python
    async def buscar(self, medicamento: str) -> Dict:
        """Busca completa com priorização dinâmica DAMA."""
        termo = medicamento.strip()
        if not termo:
            return {"resultados": [], "total": 0, "fontes_consultadas": []}

        queries_estruturadas = parse_termo_completo(termo)

        resultados = []
        fontes = []

        async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as session:
            # As 7 fontes são consultadas em paralelo via asyncio.gather() - cada uma
            # com seu próprio try/except isolado, para que uma fonte lenta ou com erro
            # não atrase nem derrube as demais. Todas usam `queries_estruturadas` para
            # exigir correspondência estrita por princípio ativo (ver
            # medicamento_query_parser.py).
            tasks = [
                self._buscar_fonte("DOU - Diário Oficial da União", self._buscar_dou(session, termo, queries_estruturadas)),
                self._buscar_fonte("Base de Alertas GSM", self._buscar_alertas_db(queries_estruturadas)),
                self._buscar_fonte("CMED - Risco de Desabastecimento", self._buscar_cmed_db(queries_estruturadas)),
                self._buscar_fonte("Notícias ANVISA", self._buscar_noticias_anvisa(session, termo, queries_estruturadas)),
                self._buscar_fonte("PNCP - Licitações Desertas/Fracassadas", self._buscar_pncp_deserto(session, termo, queries_estruturadas)),
                self._buscar_fonte("ANVISA - Descontinuação", self._buscar_descontinuacao(session, termo, queries_estruturadas)),
                self._buscar_fonte("Registro ANVISA (Cancelados/Inativos)", self._buscar_registro_cancelado(queries_estruturadas)),
            ]
            for nome, items, status in await asyncio.gather(*tasks):
                resultados.extend(items)
                fontes.append({"nome": nome, "total": len(items), "status": status})
```

- [ ] **Step 2: Sanity check de sintaxe**

Run: `python -m py_compile services/medicamento_search_service.py`
Expected: sem output

- [ ] **Step 3: Commit**

```bash
git add backend/services/medicamento_search_service.py
git commit -m "feat: buscar() calcula queries_estruturadas uma vez e repassa as 7 fontes"
```

---

## Task 13: Penalidade de prioridade + `search_query_parsed` na resposta

**Files:**
- Modify: `backend/services/medicamento_search_service.py:816-858` (método `_calcular_prioridade`)
- Modify: `backend/services/medicamento_search_service.py:236-249` (dict de retorno de `buscar()`)

- [ ] **Step 1: Atualizar `_calcular_prioridade`**

Onde hoje está:

```python
    def _calcular_prioridade(self, item: Dict, now: datetime) -> int:
        """
        Prioridade dinâmica com penalização de rotina:
        0 = PNCP deserto/fracassado (prova material)
        1 = Impacto confirmado + recente (90 dias)
        2 = Impacto + 2025/2026
        3 = Indício recente
        4 = Indício normal
        5 = Rotina (SEMPRE rebaixado)
        6 = Obsoleto
        """
        classificacao = item.get('classificacao_dama', 'indicio')
        parsed = item.get('_parsed_date')
        is_recente = item.get('tag_recente', False)
        is_obsoleto = item.get('_obsoleto', False)

        # Rotina = SEMPRE rebaixado (antes de obsoleto)
        if classificacao == 'rotina':
            return 5

        # Obsoleto perde tudo
        if is_obsoleto:
            return 6

        # PNCP deserto/fracassado = indicador de mercado (prioridade alta, mas não máxima)
        if item.get('indicador_mercado'):
            situacao = item.get('situacao_licitacao', '').upper()
            if 'DESERTO' in situacao or 'FRACASSADO' in situacao:
                return 1
            return 2

        # Impacto confirmado
        if classificacao == 'impacto':
            if parsed:
                days_ago = (now - parsed).days
                if days_ago <= 90:
                    return 1
            return 2 if is_recente else 3

        # Indício
        if is_recente:
            return 3
        return 4
```

vira:

```python
    def _calcular_prioridade(self, item: Dict, now: datetime) -> int:
        """
        Prioridade dinâmica com penalização de rotina:
        0 = PNCP deserto/fracassado (prova material)
        1 = Impacto confirmado + recente (90 dias)
        2 = Impacto + 2025/2026
        3 = Indício recente
        4 = Indício normal
        5 = Rotina (SEMPRE rebaixado)
        6 = Obsoleto

        Quando a busca informou concentração e o resultado não a confirma no
        texto (`concentracao_confirmada is False`), soma-se +1 à prioridade
        calculada (exceto para rotina/obsoleto, que já são o pior nível).
        """
        classificacao = item.get('classificacao_dama', 'indicio')
        parsed = item.get('_parsed_date')
        is_recente = item.get('tag_recente', False)
        is_obsoleto = item.get('_obsoleto', False)

        # Rotina = SEMPRE rebaixado (antes de obsoleto)
        if classificacao == 'rotina':
            return 5

        # Obsoleto perde tudo
        if is_obsoleto:
            return 6

        penalidade_concentracao = 1 if item.get('concentracao_confirmada') is False else 0

        # PNCP deserto/fracassado = indicador de mercado (prioridade alta, mas não máxima)
        if item.get('indicador_mercado'):
            situacao = item.get('situacao_licitacao', '').upper()
            if 'DESERTO' in situacao or 'FRACASSADO' in situacao:
                return 1 + penalidade_concentracao
            return 2 + penalidade_concentracao

        # Impacto confirmado
        if classificacao == 'impacto':
            if parsed:
                days_ago = (now - parsed).days
                if days_ago <= 90:
                    return 1 + penalidade_concentracao
            return (2 if is_recente else 3) + penalidade_concentracao

        # Indício
        if is_recente:
            return 3 + penalidade_concentracao
        return 4 + penalidade_concentracao
```

- [ ] **Step 2: Adicionar `search_query_parsed` ao retorno de `buscar()`**

Onde hoje está:

```python
        return {
            "medicamento_buscado": termo,
            "resultados": processed,
            "total": len(processed),
            "fontes_consultadas": fontes,
            "janela_aberta": janela_aberta,
            "filtro_temporal": ">=2025",
            "analise_dama": {
                "impacto": impacto_count,
                "rotina": rotina_count,
                "aviso": aviso_analise,
                "has_publicacao_oficial": has_publicacao_oficial,
            },
        }
```

vira:

```python
        return {
            "medicamento_buscado": termo,
            "search_query_parsed": {
                "principio_ativo": queries_estruturadas[0]["principio_ativo"],
                "concentracao": queries_estruturadas[0]["concentracao"],
                "forma_farmaceutica": queries_estruturadas[0]["forma_farmaceutica"],
            },
            "resultados": processed,
            "total": len(processed),
            "fontes_consultadas": fontes,
            "janela_aberta": janela_aberta,
            "filtro_temporal": ">=2025",
            "analise_dama": {
                "impacto": impacto_count,
                "rotina": rotina_count,
                "aviso": aviso_analise,
                "has_publicacao_oficial": has_publicacao_oficial,
            },
        }
```

- [ ] **Step 3: Sanity check de sintaxe**

Run: `python -m py_compile services/medicamento_search_service.py`
Expected: sem output

- [ ] **Step 4: Rodar toda a suíte unitária nova**

Run: `pytest tests/test_medicamento_query_parser.py tests/test_medicamento_search_service_unit.py -v`
Expected: PASS (todos os testes das Tasks 1-8)

- [ ] **Step 5: Commit**

```bash
git add backend/services/medicamento_search_service.py
git commit -m "feat: penaliza prioridade quando concentracao nao confirmada + search_query_parsed na resposta"
```

---

## Task 14: Regressão de integração ao vivo (novos campos)

**Files:**
- Modify: `backend/tests/test_buscar_medicamento_v3_janela_refactor.py`

- [ ] **Step 1: Adicionar testes de integração para os novos campos**

Append ao final de `backend/tests/test_buscar_medicamento_v3_janela_refactor.py` (antes do fechamento do arquivo, mantendo o padrão de fixture `scope="module"` já usado):

```python
@pytest.fixture(scope="module")
def mepolizumabe_response():
    r = requests.get(
        f"{BASE_URL}/api/anvisa/buscar-medicamento",
        params={"q": "Mepolizumabe 100 MG/ML"}, timeout=TIMEOUT,
    )
    assert r.status_code == 200, f"HTTP {r.status_code}: {r.text[:300]}"
    return r.json()


class TestSearchQueryParsed:
    def test_search_query_parsed_field_exists(self, mepolizumabe_response):
        assert "search_query_parsed" in mepolizumabe_response

    def test_search_query_parsed_extrai_principio_ativo_e_concentracao(self, mepolizumabe_response):
        parsed = mepolizumabe_response["search_query_parsed"]
        assert parsed["principio_ativo"].strip().upper() == "MEPOLIZUMABE"
        assert parsed["concentracao"] is not None

    def test_resultados_tem_campo_concentracao_confirmada(self, mepolizumabe_response):
        for r in mepolizumabe_response["resultados"]:
            assert "concentracao_confirmada" in r
            assert r["concentracao_confirmada"] in (True, False, None)

    def test_omalizumabe_nao_aparece_em_busca_por_mepolizumabe(self, mepolizumabe_response):
        for r in mepolizumabe_response["resultados"]:
            texto = (r.get("titulo", "") + " " + r.get("descricao", "")).upper()
            assert "OMALIZUMABE" not in texto or "MEPOLIZUMABE" in texto
```

- [ ] **Step 2: Rodar contra o backend local (precisa do servidor rodando)**

Run: `pytest tests/test_buscar_medicamento_v3_janela_refactor.py -v -k SearchQueryParsed`
Expected: PASS. Se `REACT_APP_BACKEND_URL` não estiver setado, o teste usa o default `https://anvisa-radar.preview.emergentagent.com` do arquivo — ajuste a variável de ambiente para apontar ao backend local se estiver testando uma alteração ainda não deployada.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_buscar_medicamento_v3_janela_refactor.py
git commit -m "test: regressao para search_query_parsed e concentracao_confirmada"
```

---

## Self-Review (already applied before saving this plan)

- **Cobertura da spec:** parser estruturado (Tasks 1-4), matching estrito nas 7 fontes (Tasks 6-11), split por `/` unificado (Task 4 + uso em Task 12), penalidade de concentração não confirmada (Task 13), `search_query_parsed`/`concentracao_confirmada` na resposta (Tasks 13-14). Limitação conhecida do PNCP a nível de edital e exclusão de "similares terapêuticos" ficam documentadas como fora de escopo na spec — nenhuma task tenta implementá-las.
- **Assinaturas consistentes:** `_buscar_alertas_db`/`_buscar_cmed_db`/`_buscar_registro_cancelado` recebem só `queries_estruturadas` (não usam mais `termo`); `_buscar_dou`/`_buscar_noticias_anvisa`/`_buscar_pncp_deserto`/`_buscar_descontinuacao` recebem `termo` (para as URLs de busca externas) + `queries_estruturadas`. Task 12 chama todas com a assinatura nova.
- **Import necessário:** Task 6 adiciona o import de `services.medicamento_query_parser` já incluindo `contem_termo_estrito` (usado só a partir da Task 11), além de `QueryEstruturada`, `dividir_termo`, `parse_termo_completo`, `contem_concentracao` e `resultado_relevante`.
