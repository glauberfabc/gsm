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
