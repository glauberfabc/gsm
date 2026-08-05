"""
Tests for the JANELA ABERTA refactor (iteration 35).

New definition:
- JANELA ABERTA = legal backing for Esclarecimento (Licitação Deserta/Fracassada,
  DOU desabastecimento/descontinuação, CMED risk).
- Contratação Direta and Dispensa Emergencial NO LONGER trigger JANELA ABERTA.

Endpoint under test: GET /api/anvisa/buscar-medicamento?q={term}
New response field: motivo_janela (null when janela_aberta=False).
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://anvisa-radar.preview.emergentagent.com").rstrip("/")
TIMEOUT = 90


# Module-level cached responses to avoid re-running expensive scrape calls
@pytest.fixture(scope="module")
def heparina_response():
    r = requests.get(f"{BASE_URL}/api/anvisa/buscar-medicamento", params={"q": "Heparina Sodica"}, timeout=TIMEOUT)
    assert r.status_code == 200, f"HTTP {r.status_code}: {r.text[:300]}"
    return r.json()


@pytest.fixture(scope="module")
def canabidiol_response():
    r = requests.get(f"{BASE_URL}/api/anvisa/buscar-medicamento", params={"q": "Canabidiol"}, timeout=TIMEOUT)
    assert r.status_code == 200, f"HTTP {r.status_code}: {r.text[:300]}"
    return r.json()


# ---------- Response structure ----------
class TestResponseStructure:
    def test_motivo_janela_field_exists(self, heparina_response):
        assert "motivo_janela" in heparina_response, "New 'motivo_janela' field missing"

    def test_required_fields_present(self, heparina_response):
        for f in ["medicamento_buscado", "resultados", "total", "fontes_consultadas",
                  "janela_aberta", "motivo_janela", "filtro_temporal", "analise_dama"]:
            assert f in heparina_response, f"Missing field {f}"

    def test_filtro_temporal_value(self, heparina_response):
        assert heparina_response["filtro_temporal"] == ">=2025"


# ---------- Heparina Sodica refactor expectations ----------
class TestHeparinaJanelaFalse:
    """Heparina Sodica: Contratação Direta no longer triggers janela_aberta."""

    def test_janela_aberta_false(self, heparina_response):
        # Per refactor, Contratação Direta no longer triggers janela_aberta
        assert heparina_response["janela_aberta"] is False, (
            f"Expected janela_aberta=False, got {heparina_response['janela_aberta']}"
        )

    def test_motivo_janela_null_when_false(self, heparina_response):
        assert heparina_response["motivo_janela"] is None

    def test_returns_results(self, heparina_response):
        assert heparina_response["total"] >= 1


# ---------- Canabidiol DAMA classification ----------
class TestCanabidiolClassification:
    def test_returns_results(self, canabidiol_response):
        assert canabidiol_response["total"] >= 1

    def test_dama_classification_values_valid(self, canabidiol_response):
        valid = {"impacto", "rotina", "indicio"}
        for r in canabidiol_response["resultados"]:
            cls = r.get("classificacao_dama")
            assert cls in valid, f"Invalid classificacao_dama: {cls}"

    def test_risco_values_valid(self, canabidiol_response):
        valid = {"BAIXO", "MÉDIO", "ALTO", "CRÍTICO"}
        for r in canabidiol_response["resultados"]:
            assert r.get("risco") in valid

    def test_motivo_janela_consistent(self, canabidiol_response):
        if canabidiol_response["janela_aberta"]:
            assert canabidiol_response["motivo_janela"] is not None
            assert isinstance(canabidiol_response["motivo_janela"], str)
            assert len(canabidiol_response["motivo_janela"]) > 0
        else:
            assert canabidiol_response["motivo_janela"] is None


# ---------- Refactor invariants ----------
class TestRefactorInvariants:
    def test_contratacao_direta_does_not_set_janela_flag(self, heparina_response):
        """Per refactor: PNCP contratação direta results should NOT have janela_aberta_detectada=True."""
        for r in heparina_response["resultados"]:
            tipo = (r.get("tipo_alerta") or "").lower()
            if "contratação direta" in tipo or "dispensa emergencial" in tipo:
                assert r.get("janela_aberta_detectada") is not True, (
                    f"Contratação Direta/Dispensa Emergencial should NOT set janela_aberta_detectada=True, "
                    f"got: {r}"
                )

    def test_six_sources_consulted(self, heparina_response):
        fontes = heparina_response["fontes_consultadas"]
        assert len(fontes) >= 5, f"Expected at least 5 sources, got {len(fontes)}"
        names = [f.get("nome", "") for f in fontes]
        # PNCP source must be the Deserta/Fracassada one (not contratação direta as primary trigger)
        assert any("Deserta" in n or "Fracassada" in n for n in names), (
            f"PNCP Deserta/Fracassada source missing. Got: {names}"
        )


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
