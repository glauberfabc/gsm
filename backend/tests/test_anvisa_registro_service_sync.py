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


class _FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    async def to_list(self, length=None):
        return list(self._docs)


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


class _FakeCollectionInsertFails(_FakeCollection):
    """Simula uma falha de rede/Mongo no meio do insert_many da colecao temp."""

    async def insert_many(self, docs):
        raise RuntimeError("insert_many falhou (simulado)")


class _FakeDb:
    def __init__(self):
        self._collections = {}

    def __getitem__(self, name):
        if name not in self._collections:
            self._collections[name] = _FakeCollection(db=self, name=name)
        return self._collections[name]

    def __setitem__(self, name, collection):
        collection._db = self
        collection.name = name
        self._collections[name] = collection

    def __getattr__(self, name):
        # Motor/pymongo expoe colecoes como atributos (db.minha_colecao);
        # aqui delegamos para o mesmo dict usado por __getitem__ para que
        # ambas as formas de acesso retornem a MESMA instancia.
        if name.startswith('_'):
            raise AttributeError(name)
        return self[name]


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


def test_falha_no_insert_many_da_colecao_temp_nao_apaga_dados_existentes(monkeypatch):
    """Se o insert_many na colecao temp falhar no meio do sync (rede caiu,
    Mongo com hiccup), a colecao REAL anvisa_registro_medicamentos_ativos
    nao pode ficar vazia - ela deve manter o conteudo da sincronizacao
    anterior ate a proxima tentativa bem-sucedida. E exatamente essa
    propriedade que o swap via rename (em vez de delete_many+insert_many)
    garante."""
    monkeypatch.setattr(
        anvisa_registro_service.aiohttp, "ClientSession",
        lambda *a, **kw: _FakeSession(CSV_FAKE),
    )
    db = _FakeDb()

    # Simula conteudo de uma sincronizacao anterior bem-sucedida.
    conteudo_anterior = [{'nome_produto': 'Existente', 'situacao_registro': 'Ativo'}]
    db.anvisa_registro_medicamentos_ativos.inserted = list(conteudo_anterior)

    # Injeta uma colecao temp que falha no insert_many, simulando a queda
    # de rede/Mongo no meio da sincronizacao dos registros ativos.
    db['anvisa_registro_medicamentos_ativos__sync_tmp'] = _FakeCollectionInsertFails()

    raised = False
    try:
        asyncio.run(anvisa_registro_service.sincronizar_registro_medicamentos(db))
    except RuntimeError:
        raised = True

    assert raised, "esperava que a falha no insert_many propagasse"
    # A colecao real nao deve ter sido apagada - continua com o conteudo anterior.
    assert db.anvisa_registro_medicamentos_ativos.inserted == conteudo_anterior


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
