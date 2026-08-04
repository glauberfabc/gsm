# Radar LMR — Rótulo, Card RDC 81 e Cascata Tributária Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aplicar os 3 ajustes cirúrgicos do Radar LMR: renomear o rótulo da busca individual, adicionar o card "Resumo Regulatório e Viabilidade RDC 81/2008" e corrigir o motor de cálculo tributário para incidência em cascata (em vez de soma simples de alíquotas).

**Architecture:** `lmr_service.py` ganha um cálculo tributário em cascata (método puro, sem I/O) e uma nova consulta de registros ANVISA ativos (nova coleção `anvisa_registro_medicamentos_ativos`, populada pelo mesmo job de sincronização que já popula `anvisa_registro_medicamentos` com os inativos — sem alterar essa coleção existente). O frontend (`RadarLmrTab.jsx`) ganha um novo card que renderiza o campo novo da resposta da API.

**Tech Stack:** Python 3, pytest (sem pytest-asyncio — async via `asyncio.run()`), fakes de Mongo/aiohttp (sem rede/DB reais nos testes), React (sem test runner automatizado no repo — verificação via `npm run build` + checagem manual no navegador).

---

## Task 1: Cascata tributária em `_calcular_tributacao`

**Files:**
- Modify: `backend/services/lmr_service.py:178-213` (método `_calcular_tributacao`)
- Create: `backend/tests/test_lmr_service_unit.py`

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_lmr_service_unit.py`:

```python
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.lmr_service import LmrService, FAIXAS_MARGEM_IN428

svc = LmrService(db=None)  # _calcular_tributacao nao usa self.db


class TestCalcularTributacaoCascata:
    def test_carga_tributaria_total_maior_que_soma_simples_das_aliquotas(self):
        faixa = FAIXAS_MARGEM_IN428['sintetico']
        trib = svc._calcular_tributacao('lista_negativa', faixa, preco_ref=1000)

        soma_simples = trib['imposto_importacao'] + trib['icms'] + trib['pis'] + trib['cofins']
        assert trib['carga_tributaria_total'] > soma_simples

    def test_lista_negativa_valores_esperados(self):
        faixa = FAIXAS_MARGEM_IN428['sintetico']
        trib = svc._calcular_tributacao('lista_negativa', faixa, preco_ref=1000)

        # aliquotas nominais inalteradas
        assert trib['imposto_importacao'] == 8.0
        assert trib['icms'] == 18.0
        assert trib['pis'] == 1.65
        assert trib['cofins'] == 7.6

        # cascata: II=80, PIS=16.5, COFINS=76
        # base ICMS "por dentro" = (1000+80+16.5+76) / (1-0.18) = 1429.878048780488
        # ICMS = 1429.878048780488 * 0.18 = 257.37804878048783
        # carga = (80+16.5+76+257.37804878048783) / 1000 * 100 = 42.98780487804878 -> round(2) = 42.99
        # custo = (1000+80+16.5+76) + 257.37804878048783 = 1429.8780487804878 -> round(2) = 1429.88
        assert trib['carga_tributaria_total'] == 42.99
        assert trib['custo_importacao_estimado'] == 1429.88

    def test_judicial_sem_ii_nem_icms_mas_com_pis_cofins(self):
        faixa = FAIXAS_MARGEM_IN428['sintetico']
        trib = svc._calcular_tributacao('judicial', faixa, preco_ref=1000)

        assert trib['imposto_importacao'] == 0.0
        assert trib['icms'] == 0.0
        assert trib['custo_importacao_estimado'] == 1092.5  # CIF + PIS(16.5) + COFINS(76)

    def test_sem_preco_referencia_nao_calcula_custo(self):
        faixa = FAIXAS_MARGEM_IN428['sintetico']
        trib = svc._calcular_tributacao('lista_negativa', faixa, preco_ref=0)

        assert trib['custo_importacao_estimado'] is None

    def test_margem_distribuidora_e_farmacia_inalteradas(self):
        faixa = FAIXAS_MARGEM_IN428['biologico']
        trib = svc._calcular_tributacao('lista_positiva', faixa, preco_ref=1000)

        assert trib['margem_distribuidora'] == 21.0
        assert trib['margem_farmacia'] == 33.5
```

- [ ] **Step 2: Run tests to verify they fail**

Run (de `backend/`): `pytest tests/test_lmr_service_unit.py -v`
Expected: FAIL em `test_carga_tributaria_total_maior_que_soma_simples_das_aliquotas` e `test_lista_negativa_valores_esperados` (a implementação atual usa soma simples, então `carga_tributaria_total` não bate com o valor em cascata esperado)

- [ ] **Step 3: Reescrever `_calcular_tributacao`**

Em `backend/services/lmr_service.py`, substituir o método inteiro (linhas 178-213 do arquivo original):

```python
    def _calcular_tributacao(self, categoria: str, faixa: Dict, preco_ref: float) -> Dict:
        """
        Calcula a carga tributaria em cascata (modelo padrao de importacao
        brasileira):
          - II incide sobre o valor aduaneiro (CIF = preco de referencia).
          - PIS/COFINS-Importacao incidem sobre CIF + despesas aduaneiras.
          - ICMS incide "por dentro" (embutido na propria base: Lei
            Kandir, art. 13 par. 1 I), sobre CIF + II + PIS + COFINS +
            despesas aduaneiras e nao-aduaneiras, com a aliquota de
            destino (18% padrao SP, ou reduzida conforme categoria).
        Despesas aduaneiras/nao-aduaneiras (capatazia, armazenagem,
        SISCOMEX, despachante etc.) ainda nao tem valor de referencia
        confirmado - ficam em 0 ate validacao contra a tabela oficial;
        a formula ja esta pronta para recebe-las.
        """
        if categoria == 'excepcional':
            aliquota_ii = 0.0
            aliquota_icms = ALIQUOTAS_TRIBUTARIAS['icms_reduzido']
            beneficio_extra = 'Isencao II + ICMS reduzido (Art. 12, IN 428/2026)'
        elif categoria == 'judicial':
            aliquota_ii = 0.0
            aliquota_icms = 0.0
            beneficio_extra = 'Isencao total conforme liminar judicial'
        elif categoria == 'lista_positiva':
            aliquota_ii = ALIQUOTAS_TRIBUTARIAS['ii_medicamento'] * 0.5
            aliquota_icms = ALIQUOTAS_TRIBUTARIAS['icms_reduzido']
            beneficio_extra = 'Reducao II 50% + ICMS reduzido (LMR positiva)'
        else:
            aliquota_ii = ALIQUOTAS_TRIBUTARIAS['ii_medicamento']
            aliquota_icms = ALIQUOTAS_TRIBUTARIAS['icms_padrao']
            beneficio_extra = 'Sem beneficio tributario especial'

        aliquota_pis = ALIQUOTAS_TRIBUTARIAS['pis']
        aliquota_cofins = ALIQUOTAS_TRIBUTARIAS['cofins']
        despesas_aduaneiras = 0.0
        despesas_nao_aduaneiras = 0.0

        if preco_ref > 0:
            cif = preco_ref
            valor_ii = cif * aliquota_ii
            base_pis_cofins = cif + despesas_aduaneiras
            valor_pis = base_pis_cofins * aliquota_pis
            valor_cofins = base_pis_cofins * aliquota_cofins

            base_icms_sem_icms = (
                cif + valor_ii + valor_pis + valor_cofins
                + despesas_aduaneiras + despesas_nao_aduaneiras
            )
            if aliquota_icms > 0:
                base_icms = base_icms_sem_icms / (1 - aliquota_icms)
                valor_icms = base_icms * aliquota_icms
            else:
                valor_icms = 0.0

            custo_importacao_estimado = base_icms_sem_icms + valor_icms
            carga_tributaria_total = (
                (valor_ii + valor_pis + valor_cofins + valor_icms) / cif * 100
            )
        else:
            custo_importacao_estimado = 0
            carga_tributaria_total = (
                (aliquota_ii + aliquota_icms + aliquota_pis + aliquota_cofins) * 100
            )

        return {
            'imposto_importacao': round(aliquota_ii * 100, 2),
            'icms': round(aliquota_icms * 100, 2),
            'pis': round(aliquota_pis * 100, 2),
            'cofins': round(aliquota_cofins * 100, 2),
            'carga_tributaria_total': round(carga_tributaria_total, 2),
            'beneficio': beneficio_extra,
            'custo_importacao_estimado': round(custo_importacao_estimado, 2) if custo_importacao_estimado > 0 else None,
            'margem_distribuidora': round(faixa['margem_distribuidora'] * 100, 2),
            'margem_farmacia': round(faixa['margem_farmacia'] * 100, 2),
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_lmr_service_unit.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Rodar a suíte de margens existente (regressão)**

Run: `pytest tests/test_lmr_category_margins.py -v -k "margin"`
Nota: esses testes específicos batem em `BASE_URL` (integração ao vivo) — se não houver backend rodando/acessível, eles vão falhar por erro de conexão, não por lógica. Se isso acontecer, pule esta verificação e confirme apenas via `test_lmr_service_unit.py` (Step 4), que já cobre `margem_distribuidora`/`margem_farmacia` sem rede.

- [ ] **Step 6: Commit**

```bash
git add backend/services/lmr_service.py backend/tests/test_lmr_service_unit.py
git commit -m "fix: motor tributario do Radar LMR passa a calcular impostos em cascata"
```

---

## Task 2: `_montar_resumo_regulatorio`

**Files:**
- Modify: `backend/services/lmr_service.py`
- Modify: `backend/tests/test_lmr_service_unit.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_lmr_service_unit.py`:

```python
class TestMontarResumoRegulatorio:
    def test_via_judicial_e_viavel(self):
        classificacao = {'via_judicial': True, 'desabastecimento_detectado': False, 'janela_aberta': False, 'desabastecimento_info': None}
        resumo = svc._montar_resumo_regulatorio(classificacao, registros_ativos=[])
        assert resumo['viabilidade_importacao_rdc81'].startswith('VIÁVEL')

    def test_desabastecimento_sem_judicial_e_viavel(self):
        classificacao = {'via_judicial': False, 'desabastecimento_detectado': True, 'janela_aberta': True, 'desabastecimento_info': None}
        resumo = svc._montar_resumo_regulatorio(classificacao, registros_ativos=[])
        assert resumo['viabilidade_importacao_rdc81'].startswith('VIÁVEL')

    def test_registrado_sem_desabastecimento_e_nao_recomendado(self):
        classificacao = {'via_judicial': False, 'desabastecimento_detectado': False, 'janela_aberta': False, 'desabastecimento_info': None}
        registros = [{'empresa_detentora_registro': 'GSK'}, {'empresa_detentora_registro': 'GSK'}]
        resumo = svc._montar_resumo_regulatorio(classificacao, registros_ativos=registros)
        assert resumo['registrado_anvisa'] is True
        assert resumo['laboratorios_referencia'] == ['GSK']
        assert resumo['viabilidade_importacao_rdc81'].startswith('NÃO RECOMENDADA')

    def test_nada_encontrado_e_sem_similar_identificado(self):
        classificacao = {'via_judicial': False, 'desabastecimento_detectado': False, 'janela_aberta': False, 'desabastecimento_info': None}
        resumo = svc._montar_resumo_regulatorio(classificacao, registros_ativos=[])
        assert resumo['registrado_anvisa'] is False
        assert resumo['viabilidade_importacao_rdc81'].startswith('SEM SIMILAR ATIVO')

    def test_situacao_desabastecimento_usa_status_do_desab_info_quando_disponivel(self):
        classificacao = {
            'via_judicial': False, 'desabastecimento_detectado': True, 'janela_aberta': True,
            'desabastecimento_info': {'status': 'Confirmado pela ANVISA em 2026-01-10'},
        }
        resumo = svc._montar_resumo_regulatorio(classificacao, registros_ativos=[])
        assert resumo['situacao_desabastecimento'] == 'Confirmado pela ANVISA em 2026-01-10'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_lmr_service_unit.py -v -k Resumo`
Expected: FAIL com `AttributeError: 'LmrService' object has no attribute '_montar_resumo_regulatorio'`

- [ ] **Step 3: Implementar `_montar_resumo_regulatorio`**

Em `backend/services/lmr_service.py`, adicionar o método logo após `_calcular_tributacao` (antes de `_calcular_margem`):

```python
    def _montar_resumo_regulatorio(self, classificacao: Dict, registros_ativos: List[Dict]) -> Dict:
        """Monta o card 'Resumo Regulatorio e Viabilidade RDC 81/2008'."""
        registrado = len(registros_ativos) > 0
        laboratorios = sorted({
            r['empresa_detentora_registro'] for r in registros_ativos
            if r.get('empresa_detentora_registro')
        })

        desab_info = classificacao.get('desabastecimento_info')
        if desab_info and desab_info.get('status'):
            situacao_desabastecimento = desab_info['status']
        elif classificacao.get('janela_aberta'):
            situacao_desabastecimento = 'Indício de desabastecimento identificado (janela aberta)'
        else:
            situacao_desabastecimento = 'Sem indício de desabastecimento identificado'

        if classificacao.get('via_judicial'):
            viabilidade = 'VIÁVEL — importação amparada por ordem/decisão judicial'
        elif classificacao.get('desabastecimento_detectado') or classificacao.get('janela_aberta'):
            viabilidade = (
                'VIÁVEL — desabastecimento oficial reconhecido autoriza '
                'importação excepcional (RDC 81/2008)'
            )
        elif registrado:
            viabilidade = (
                'NÃO RECOMENDADA / INVIÁVEL por via administrativa ordinária — '
                'há similar registrado e ativo no Brasil (RDC 81/2008), salvo '
                'desabastecimento oficial ou ordem judicial'
            )
        else:
            viabilidade = (
                'SEM SIMILAR ATIVO IDENTIFICADO NA BASE ANVISA — avaliar '
                'viabilidade caso a caso'
            )

        return {
            'registrado_anvisa': registrado,
            'laboratorios_referencia': laboratorios,
            'situacao_desabastecimento': situacao_desabastecimento,
            'viabilidade_importacao_rdc81': viabilidade,
            'norma_referencia_viabilidade': (
                'RDC 81/2008 (ANVISA) — Regulamento Técnico de Importação de '
                'Produtos Sujeitos à Vigilância Sanitária'
            ),
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_lmr_service_unit.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/services/lmr_service.py backend/tests/test_lmr_service_unit.py
git commit -m "feat: monta resumo regulatorio e viabilidade RDC 81/2008"
```

---

## Task 3: `_verificar_registro_ativo` + wiring em `analisar_medicamento`

**Files:**
- Modify: `backend/services/lmr_service.py:67-114` (método `analisar_medicamento`)
- Modify: `backend/tests/test_lmr_service_unit.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_lmr_service_unit.py`:

```python
import asyncio


class _FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    def to_list(self, length=None):
        return self._to_list_async(length)

    async def _to_list_async(self, length):
        return list(self._docs)


class _FakeCollection:
    def __init__(self, docs):
        self._docs = docs

    def find(self, *args, **kwargs):
        return _FakeCursor(self._docs)

    def find_one(self, *args, **kwargs):
        return self._find_one_async()

    async def _find_one_async(self):
        return self._docs[0] if self._docs else None


class _FakeDb:
    def __init__(self, ativos=None, alertas=None, desabastecimento=None):
        self.anvisa_registro_medicamentos_ativos = _FakeCollection(ativos or [])
        self.anvisa_alertas = _FakeCollection(alertas or [])
        self.desabastecimento_inteligencia = _FakeCollection(desabastecimento or [])


class TestVerificarRegistroAtivo:
    def test_retorna_registros_que_casam_com_o_medicamento(self):
        db = _FakeDb(ativos=[{'nome_produto': 'Nucala', 'principio_ativo': 'MEPOLIZUMABE',
                               'empresa_detentora_registro': 'GSK'}])
        svc_local = LmrService(db)

        resultado = asyncio.run(svc_local._verificar_registro_ativo('Mepolizumabe'))

        assert len(resultado) == 1
        assert resultado[0]['empresa_detentora_registro'] == 'GSK'

    def test_retorna_lista_vazia_quando_nao_encontrado(self):
        db = _FakeDb(ativos=[])
        svc_local = LmrService(db)

        resultado = asyncio.run(svc_local._verificar_registro_ativo('Mepolizumabe'))

        assert resultado == []


class TestAnalisarMedicamentoIncluiResumoRegulatorio:
    def test_resposta_inclui_resumo_regulatorio_rdc81(self):
        db = _FakeDb(
            ativos=[{'nome_produto': 'Nucala', 'principio_ativo': 'MEPOLIZUMABE',
                     'empresa_detentora_registro': 'GSK'}],
            alertas=[],
            desabastecimento=[],
        )
        svc_local = LmrService(db)

        resultado = asyncio.run(svc_local.analisar_medicamento('Mepolizumabe', preco_referencia=0, tipo_produto='sintetico'))

        assert 'resumo_regulatorio_rdc81' in resultado
        assert resultado['resumo_regulatorio_rdc81']['registrado_anvisa'] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_lmr_service_unit.py -v -k "VerificarRegistroAtivo or IncluiResumoRegulatorio"`
Expected: FAIL — `TestVerificarRegistroAtivo` com `AttributeError: 'LmrService' object has no attribute '_verificar_registro_ativo'`; `TestAnalisarMedicamentoIncluiResumoRegulatorio` com `KeyError: 'resumo_regulatorio_rdc81'`

- [ ] **Step 3: Implementar `_verificar_registro_ativo` e integrar em `analisar_medicamento`**

Em `backend/services/lmr_service.py`, adicionar o método (pode ficar logo antes de `_classificar_lmr`):

```python
    async def _verificar_registro_ativo(self, medicamento: str) -> List[Dict]:
        """Retorna os registros ATIVOS da ANVISA que casam com o medicamento
        buscado (usado para responder se ha similar registrado no Brasil,
        conforme RDC 81/2008)."""
        try:
            docs = await self.db.anvisa_registro_medicamentos_ativos.find(
                {'$or': [
                    {'nome_produto': {'$regex': medicamento, '$options': 'i'}},
                    {'principio_ativo': {'$regex': medicamento, '$options': 'i'}},
                ]},
                {'_id': 0},
            ).to_list(length=20)
        except Exception:
            docs = []
        return docs
```

Onde hoje está (linhas 87-90 do arquivo original):

```python
        # 1. Verificar classificacao LMR
        classificacao = await self._classificar_lmr(medicamento)
        resultado['classificacao_lmr'] = classificacao
```

vira:

```python
        # 1. Verificar classificacao LMR
        classificacao = await self._classificar_lmr(medicamento)
        resultado['classificacao_lmr'] = classificacao

        # 1b. Resumo regulatorio e viabilidade RDC 81/2008
        registros_ativos = await self._verificar_registro_ativo(medicamento)
        resultado['resumo_regulatorio_rdc81'] = self._montar_resumo_regulatorio(
            classificacao, registros_ativos
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_lmr_service_unit.py -v`
Expected: PASS (13 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/services/lmr_service.py backend/tests/test_lmr_service_unit.py
git commit -m "feat: analisar_medicamento inclui resumo_regulatorio_rdc81 na resposta"
```

---

## Task 4: Sincronização passa a gravar registros ativos numa coleção separada

**Files:**
- Modify: `backend/services/anvisa_registro_service.py:76-122` (função `sincronizar_registro_medicamentos`)
- Create: `backend/tests/test_anvisa_registro_service_sync.py`

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_anvisa_registro_service_sync.py`:

```python
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import services.anvisa_registro_service as anvisa_registro_service


class _FakeResponse:
    def __init__(self, body: bytes, status: int = 200):
        self.status = status
        self._body = body

    async def read(self):
        return self._body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class _FakeSession:
    def __init__(self, body: bytes):
        self._body = body

    def get(self, url, ssl=None):
        return _FakeResponse(self._body)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class _FakeCollection:
    def __init__(self):
        self.deleted = False
        self.inserted = []

    async def delete_many(self, *args, **kwargs):
        self.deleted = True

    async def insert_many(self, docs):
        self.inserted = list(docs)


class _FakeDb:
    def __init__(self):
        self.anvisa_registro_medicamentos = _FakeCollection()
        self.anvisa_registro_medicamentos_ativos = _FakeCollection()


CSV_FAKE = (
    "NOME_PRODUTO;PRINCIPIO_ATIVO;SITUACAO_REGISTRO;DATA_FINALIZACAO_PROCESSO;"
    "DATA_VENCIMENTO_REGISTRO;CATEGORIA_REGULATORIA;CLASSE_TERAPEUTICA;"
    "EMPRESA_DETENTORA_REGISTRO;NUMERO_REGISTRO_PRODUTO\r\n"
    "Nucala;MEPOLIZUMABE;Ativo;;;Biologico;Antiasmatico;GSK;123456\r\n"
    "Xolair;OMALIZUMABE;Cancelado;2024-01-01;;Biologico;Antiasmatico;Roche;654321\r\n"
).encode('latin-1')


def test_sincronizar_separa_ativos_e_inativos_em_colecoes_diferentes(monkeypatch):
    monkeypatch.setattr(
        anvisa_registro_service.aiohttp, "ClientSession",
        lambda *a, **kw: _FakeSession(CSV_FAKE),
    )
    db = _FakeDb()

    total = asyncio.run(anvisa_registro_service.sincronizar_registro_medicamentos(db))

    assert total == 2
    assert len(db.anvisa_registro_medicamentos_ativos.inserted) == 1
    assert db.anvisa_registro_medicamentos_ativos.inserted[0]['nome_produto'] == 'Nucala'
    assert db.anvisa_registro_medicamentos_ativos.inserted[0]['empresa_detentora_registro'] == 'GSK'

    assert len(db.anvisa_registro_medicamentos.inserted) == 1
    assert db.anvisa_registro_medicamentos.inserted[0]['nome_produto'] == 'Xolair'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_anvisa_registro_service_sync.py -v`
Expected: FAIL — `db.anvisa_registro_medicamentos_ativos.inserted` fica vazio (`assert len(...) == 1` falha, pois a implementação atual descarta as linhas ativas e nunca grava em `anvisa_registro_medicamentos_ativos`, atributo que nem existe no fake sendo chamado)

- [ ] **Step 3: Reescrever `sincronizar_registro_medicamentos`**

Em `backend/services/anvisa_registro_service.py`, substituir a função inteira (linhas 76-122 do arquivo original):

```python
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

    if docs_inativos:
        await db.anvisa_registro_medicamentos.delete_many({})
        await db.anvisa_registro_medicamentos.insert_many(docs_inativos)
    if docs_ativos:
        await db.anvisa_registro_medicamentos_ativos.delete_many({})
        await db.anvisa_registro_medicamentos_ativos.insert_many(docs_ativos)

    logger.info(
        f"ANVISA registro: {len(docs_inativos)} nao-ativos + {len(docs_ativos)} ativos sincronizados"
    )
    return len(docs_inativos) + len(docs_ativos)
```

Note que o import `import aiohttp` no topo do arquivo já existe e não muda — o teste faz `monkeypatch.setattr(anvisa_registro_service.aiohttp, "ClientSession", ...)`, que funciona porque o módulo referencia `aiohttp.ClientSession` (atributo do módulo `aiohttp`), não uma referência importada separadamente.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_anvisa_registro_service_sync.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Sanity check — job agendado não muda**

Run: `grep -n "sincronizar_registro_medicamentos" backend/scheduler.py`
Expected: mesma chamada de antes (`from services.anvisa_registro_service import sincronizar_registro_medicamentos` / `await sincronizar_registro_medicamentos(_db)`) — a assinatura da função não mudou, então nenhuma edição é necessária em `scheduler.py`.

- [ ] **Step 6: Commit**

```bash
git add backend/services/anvisa_registro_service.py backend/tests/test_anvisa_registro_service_sync.py
git commit -m "feat: sincronizacao ANVISA passa a gravar registros ativos em colecao separada"
```

---

## Task 5: Frontend — rótulo e card de Resumo Regulatório

**Files:**
- Modify: `frontend/src/components/tabs/RadarLmrTab.jsx:115` (rótulo)
- Modify: `frontend/src/components/tabs/RadarLmrTab.jsx:306-394` (`AnaliseDetalheCard`, novo componente `ResumoRegulatorioCard`)

- [ ] **Step 1: Trocar o rótulo**

Onde hoje está (linha 115):

```jsx
          <span className="text-sm font-black text-slate-700 uppercase tracking-wide">Analise Individual LMR</span>
```

vira:

```jsx
          <span className="text-sm font-black text-slate-700 uppercase tracking-wide">Analise Individual do Medicamento e LMR</span>
```

- [ ] **Step 2: Adicionar a chamada do novo card em `AnaliseDetalheCard`**

Onde hoje está (linhas 330-347 do arquivo original):

```jsx
      <div className="p-5 space-y-4">
        {/* Classificacao */}
        <div>
          <h4 className="text-xs font-black text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-2">
            <ShieldCheck size={14}/> Classificacao LMR
          </h4>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <MiniStat label="Categoria" value={classif.categoria?.toUpperCase() || 'N/A'}
              color={classif.categoria === 'excepcional' ? 'purple' : classif.categoria === 'judicial' ? 'blue' : classif.categoria === 'lista_positiva' ? 'emerald' : 'slate'} />
            <MiniStat label="Risco Comercial" value={classif.risco_comercial || 'N/A'} color="amber" />
            <MiniStat label="Alertas ANVISA" value={classif.total_alertas || 0} color="red" />
            <MiniStat label="Janela Aberta" value={classif.janela_aberta ? 'SIM' : 'NAO'}
              color={classif.janela_aberta ? 'emerald' : 'slate'} />
          </div>
          <p className="text-xs text-slate-500 mt-2">{classif.descricao}</p>
          <p className="text-xs font-bold text-emerald-700 mt-1">{classif.beneficio_tributario}</p>
        </div>

        {/* Tributacao */}
```

vira:

```jsx
      <div className="p-5 space-y-4">
        {/* Classificacao */}
        <div>
          <h4 className="text-xs font-black text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-2">
            <ShieldCheck size={14}/> Classificacao LMR
          </h4>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <MiniStat label="Categoria" value={classif.categoria?.toUpperCase() || 'N/A'}
              color={classif.categoria === 'excepcional' ? 'purple' : classif.categoria === 'judicial' ? 'blue' : classif.categoria === 'lista_positiva' ? 'emerald' : 'slate'} />
            <MiniStat label="Risco Comercial" value={classif.risco_comercial || 'N/A'} color="amber" />
            <MiniStat label="Alertas ANVISA" value={classif.total_alertas || 0} color="red" />
            <MiniStat label="Janela Aberta" value={classif.janela_aberta ? 'SIM' : 'NAO'}
              color={classif.janela_aberta ? 'emerald' : 'slate'} />
          </div>
          <p className="text-xs text-slate-500 mt-2">{classif.descricao}</p>
          <p className="text-xs font-bold text-emerald-700 mt-1">{classif.beneficio_tributario}</p>
        </div>

        {/* Resumo Regulatorio e RDC 81 */}
        {data.resumo_regulatorio_rdc81 && (
          <ResumoRegulatorioCard resumo={data.resumo_regulatorio_rdc81} />
        )}

        {/* Tributacao */}
```

- [ ] **Step 3: Criar o componente `ResumoRegulatorioCard`**

No mesmo arquivo, adicionar a função logo após `TributoBadge` (após a linha 412 do arquivo original, antes de `function AlertaEmailPanel`):

```jsx
function ResumoRegulatorioCard({ resumo }) {
  const viavel = resumo.viabilidade_importacao_rdc81?.startsWith('VIÁVEL');
  return (
    <div className="bg-slate-50 border-2 border-slate-200 rounded-xl overflow-hidden" data-testid="resumo-regulatorio-rdc81">
      <div className="bg-slate-700 px-4 py-2">
        <p className="text-xs font-black text-white uppercase tracking-wide">
          📋 Análise Regulatória e Viabilidade RDC 81/2008
        </p>
      </div>
      <div className="p-4 space-y-3">
        <div>
          <p className="text-[10px] font-bold text-slate-400 uppercase">1. Registro na ANVISA</p>
          <p className="text-sm font-bold text-slate-700">
            {resumo.registrado_anvisa ? 'SIM' : 'NÃO'}
            {resumo.laboratorios_referencia?.length > 0 && (
              <span className="font-normal text-slate-500"> — {resumo.laboratorios_referencia.join(', ')}</span>
            )}
          </p>
        </div>
        <div>
          <p className="text-[10px] font-bold text-slate-400 uppercase">2. Situação de Falta / Desabastecimento</p>
          <p className="text-sm font-semibold text-slate-700">{resumo.situacao_desabastecimento}</p>
        </div>
        <div>
          <p className="text-[10px] font-bold text-slate-400 uppercase">3. Viabilidade de Importação (RDC 81/2008)</p>
          <p className={`text-sm font-bold ${viavel ? 'text-emerald-700' : 'text-red-700'}`}>
            {resumo.viabilidade_importacao_rdc81}
          </p>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Checagem de compilação**

Run (de `frontend/`): `npm run build`
Expected: build conclui sem erros de sintaxe/compilação relacionados a `RadarLmrTab.jsx`. (O repositório não tem testes automatizados de componente — não existe nenhum arquivo `*.test.jsx` em `frontend/src/` — então esta é a verificação automatizada disponível; a verificação visual final acontece manualmente no navegador, ver Task 6.)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/tabs/RadarLmrTab.jsx
git commit -m "feat: rotulo atualizado e card de Resumo Regulatorio RDC 81/2008 no Radar LMR"
```

---

## Task 6: Regressão + verificação manual no navegador

**Files:**
- Modify: `backend/tests/test_lmr_category_margins.py`

- [ ] **Step 1: Adicionar regressão de integração ao vivo**

Append à classe `TestLMRAnalysisEndpoint` em `backend/tests/test_lmr_category_margins.py` (após o método `test_lmr_analysis_response_structure`, antes do fechamento da classe):

```python
    def test_resposta_inclui_resumo_regulatorio_rdc81(self):
        """POST /api/dama/lmr-analise-medicamento inclui o novo campo resumo_regulatorio_rdc81"""
        response = requests.post(
            f"{BASE_URL}/api/dama/lmr-analise-medicamento",
            json={"medicamento": "TestResumoRegulatorio", "preco_referencia": 500, "tipo_produto": "sintetico"}
        )
        assert response.status_code == 200
        data = response.json()

        assert "resumo_regulatorio_rdc81" in data
        resumo = data["resumo_regulatorio_rdc81"]
        for campo in ("registrado_anvisa", "laboratorios_referencia", "situacao_desabastecimento",
                      "viabilidade_importacao_rdc81", "norma_referencia_viabilidade"):
            assert campo in resumo, f"resumo_regulatorio_rdc81 sem campo {campo}"
        print("✅ resumo_regulatorio_rdc81 presente e completo")
```

- [ ] **Step 2: Rodar contra o backend local (se disponível)**

Run: `pytest tests/test_lmr_category_margins.py -v -k resumo_regulatorio`
Expected: PASS se `REACT_APP_BACKEND_URL` apontar para um backend rodando com as mudanças desta plan aplicadas. Se não houver backend acessível, esta etapa fica marcada como pendente de verificação manual (ver Step 3) — não bloqueia o commit, já que os Testes das Tasks 1-4 (sem rede) já provam a lógica correta.

- [ ] **Step 3: Verificação manual no navegador**

Suba o backend e o frontend localmente (`cd backend && uvicorn server:app --reload` / `cd frontend && npm start`, ou os scripts equivalentes já usados no projeto), abra a aba Radar LMR, digite um medicamento na busca individual e clique "Analisar". Confirme visualmente:
- O rótulo lê "Analise Individual do Medicamento e LMR".
- O card "📋 Análise Regulatória e Viabilidade RDC 81/2008" aparece entre "Classificação LMR" e "Estratégia Tributária", com as 3 linhas (Registro ANVISA, Situação de Desabastecimento, Viabilidade).
- Os valores de II/ICMS/PIS/COFINS/Carga Total no card "Estratégia Tributária" continuam sendo exibidos normalmente (a mudança de fórmula não quebra a renderização).

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_lmr_category_margins.py
git commit -m "test: regressao para resumo_regulatorio_rdc81 na resposta do Radar LMR"
```

---

## Self-Review (already applied before saving this plan)

- **Cobertura da spec:** rótulo (Task 5 Step 1), card RDC 81 com dados de registro ativo/desabastecimento/viabilidade (Tasks 2-3-5), nova coleção de registros ativos sem tocar na existente (Task 4), cascata tributária com ICMS "por dentro" preservando alíquotas nominais e campos de resposta (Task 1). "Fora de escopo" da spec (despesas aduaneiras reais, endpoint manual de sync) não tem task correspondente, como esperado.
- **Consistência de tipos:** `_montar_resumo_regulatorio(classificacao, registros_ativos)` — mesma assinatura usada em `analisar_medicamento` (Task 3) e nos testes (Task 2). `_verificar_registro_ativo(medicamento)` retorna `List[Dict]`, consumido diretamente por `_montar_resumo_regulatorio`.
- **Sem placeholders:** todos os steps têm código completo; nenhum "TODO"/"adicionar validação apropriada".
- **Risco de regressão cruzada:** Task 4 explicitamente preserva o comportamento de `anvisa_registro_medicamentos` (só não-ativos) — a mesma coleção usada pela fonte "Registro ANVISA" da Janela ANVISA e pelo plano pausado de busca estrita (`docs/superpowers/plans/2026-08-04-busca-medicamento-strict-match.md`, Task 8), que não precisa de nenhum ajuste por causa desta mudança.
