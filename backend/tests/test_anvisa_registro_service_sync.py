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
