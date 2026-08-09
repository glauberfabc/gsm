import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import services.comprasgov_service as comprasgov_service_module
from services.comprasgov_service import get_comprasgov_service


class _FakeMongoDatabase:
    """Reproduz o comportamento real do pymongo.database.Database:
    bool(db) levanta NotImplementedError - comparar um objeto de banco
    diretamente com 'if db' ou 'db and ...' e um erro comum e proibido
    de proposito pelo driver."""
    def __bool__(self):
        raise NotImplementedError(
            "Database objects do not implement truth value testing or bool(). "
            "Please compare with None instead: database is not None"
        )


def test_get_comprasgov_service_nao_avalia_db_como_booleano(monkeypatch):
    """get_comprasgov_service(db=...) nao deve levantar NotImplementedError
    ao receber um objeto de banco real (Motor/PyMongo) numa segunda
    chamada, quando a instancia singleton ja existe."""
    monkeypatch.setattr(comprasgov_service_module, '_instance', None)

    primeira = get_comprasgov_service(db=None)
    assert primeira is not None

    fake_db = _FakeMongoDatabase()
    # Antes da correcao, esta linha levantava NotImplementedError porque
    # get_comprasgov_service fazia "elif db and ...", avaliando o objeto
    # de banco como booleano.
    segunda = get_comprasgov_service(db=fake_db)

    assert segunda is primeira
    assert segunda.db is fake_db
