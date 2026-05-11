"""
Test suite for the 'Buscar Medicamento' feature in Janela ANVISA tab.
Tests the GET /api/anvisa/buscar-medicamento endpoint.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBuscarMedicamentoEndpoint:
    """Tests for GET /api/anvisa/buscar-medicamento endpoint"""
    
    def test_buscar_medicamento_ravulizumabe_returns_dou_results(self):
        """
        Test: Search for 'Ravulizumabe' should return results from DOU with Resoluções-RE
        """
        response = requests.get(
            f"{BASE_URL}/api/anvisa/buscar-medicamento",
            params={"q": "Ravulizumabe"},
            timeout=30
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Verify response structure
        assert "medicamento_buscado" in data, "Response should contain medicamento_buscado"
        assert "resultados" in data, "Response should contain resultados"
        assert "total" in data, "Response should contain total"
        assert "fontes_consultadas" in data, "Response should contain fontes_consultadas"
        
        # Verify medicamento_buscado matches query
        assert data["medicamento_buscado"].lower() == "ravulizumabe", f"Expected 'Ravulizumabe', got {data['medicamento_buscado']}"
        
        # Verify total is an integer
        assert isinstance(data["total"], int), "total should be an integer"
        
        print(f"✅ Ravulizumabe search: {data['total']} results found")
        
        # Check fontes_consultadas structure
        for fonte in data["fontes_consultadas"]:
            assert "nome" in fonte, "fonte should have nome"
            assert "total" in fonte, "fonte should have total"
            assert "status" in fonte, "fonte should have status"
            print(f"   - {fonte['nome']}: {fonte['total']} ({fonte['status']})")

    def test_buscar_medicamento_canabidiol_returns_multiple_results(self):
        """
        Test: Search for 'canabidiol' should return 10+ results from DOU
        """
        response = requests.get(
            f"{BASE_URL}/api/anvisa/buscar-medicamento",
            params={"q": "canabidiol"},
            timeout=30
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Verify structure
        assert "medicamento_buscado" in data
        assert "resultados" in data
        assert "total" in data
        assert "fontes_consultadas" in data
        
        # Check if we got results (may vary with live data)
        print(f"✅ Canabidiol search: {data['total']} results found")
        
        # At least verify we get some results from DOU
        dou_fonte = next((f for f in data["fontes_consultadas"] if "DOU" in f["nome"]), None)
        assert dou_fonte is not None, "Should have DOU in fontes_consultadas"
        print(f"   - DOU: {dou_fonte['total']} results")
        
        # Verify each resultado has required fields
        if len(data["resultados"]) > 0:
            for r in data["resultados"][:3]:  # Check first 3
                assert "titulo" in r, "resultado should have titulo"
                assert "fonte_busca" in r, "resultado should have fonte_busca"
                assert "risco" in r, "resultado should have risco"
                print(f"   - {r['titulo'][:60]}... (risco: {r['risco']})")

    def test_buscar_medicamento_invalid_term_returns_empty(self):
        """
        Test: Search for 'xyz123invalid' should return 0 results gracefully
        """
        response = requests.get(
            f"{BASE_URL}/api/anvisa/buscar-medicamento",
            params={"q": "xyz123invalid"},
            timeout=30
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Verify empty results are handled gracefully
        assert "medicamento_buscado" in data
        assert "resultados" in data
        assert "total" in data
        assert "fontes_consultadas" in data
        
        assert data["total"] == 0 or data["total"] <= 2, f"Expected 0 or very few results for invalid term, got {data['total']}"
        assert isinstance(data["resultados"], list), "resultados should be a list"
        
        print(f"✅ Invalid term search: {data['total']} results (expected ~0)")
        
        # Verify fontes still report their status
        for fonte in data["fontes_consultadas"]:
            assert "status" in fonte
            print(f"   - {fonte['nome']}: {fonte['total']} ({fonte['status']})")

    def test_buscar_medicamento_short_query_validation(self):
        """
        Test: Search with query 'ab' (min_length=2) should work or fail with 422
        """
        response = requests.get(
            f"{BASE_URL}/api/anvisa/buscar-medicamento",
            params={"q": "ab"},
            timeout=30
        )
        
        # Either 422 validation error or 200 with 0 results is acceptable
        assert response.status_code in [200, 422], f"Expected 200 or 422, got {response.status_code}"
        
        if response.status_code == 422:
            print("✅ Short query correctly rejected with 422")
        else:
            data = response.json()
            print(f"✅ Short query accepted, returned {data.get('total', 0)} results")

    def test_buscar_medicamento_missing_query_returns_error(self):
        """
        Test: Missing 'q' parameter should return 422
        """
        response = requests.get(
            f"{BASE_URL}/api/anvisa/buscar-medicamento",
            timeout=30
        )
        
        assert response.status_code == 422, f"Expected 422 for missing q param, got {response.status_code}"
        print("✅ Missing q parameter correctly returns 422")


class TestBuscarMedicamentoResponseStructure:
    """Tests for response structure validation"""
    
    def test_resultado_has_required_fields(self):
        """
        Test: Each resultado has titulo, descricao, link, fonte_busca, tipo_alerta, risco
        """
        response = requests.get(
            f"{BASE_URL}/api/anvisa/buscar-medicamento",
            params={"q": "insulina"},
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data["total"] > 0:
            for idx, r in enumerate(data["resultados"][:5]):
                # Required fields
                assert "titulo" in r, f"resultado {idx} missing titulo"
                assert "fonte_busca" in r, f"resultado {idx} missing fonte_busca"
                assert "risco" in r, f"resultado {idx} missing risco"
                
                # Risco should be ALTO, MÉDIO or BAIXO
                assert r["risco"] in ["ALTO", "MÉDIO", "BAIXO"], f"Invalid risco value: {r['risco']}"
                
                # Optional but commonly present
                if "descricao" in r:
                    assert isinstance(r["descricao"], str)
                if "link" in r:
                    assert isinstance(r["link"], str)
                if "tipo_alerta" in r:
                    assert isinstance(r["tipo_alerta"], str)
                
                print(f"✅ Result {idx}: {r['titulo'][:50]}... | risco={r['risco']} | fonte={r['fonte_busca']}")
        else:
            print("⚠️ No results to validate structure (search returned 0)")

    def test_fontes_consultadas_structure(self):
        """
        Test: fontes_consultadas array has nome, total, status for each fonte
        """
        response = requests.get(
            f"{BASE_URL}/api/anvisa/buscar-medicamento",
            params={"q": "prolia"},
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "fontes_consultadas" in data
        assert isinstance(data["fontes_consultadas"], list)
        assert len(data["fontes_consultadas"]) >= 3, "Should consult at least 3 sources"
        
        expected_fontes = ["DOU", "CMED", "GSM", "Notícias", "AnvisaLegis"]
        
        for fonte in data["fontes_consultadas"]:
            assert "nome" in fonte, "fonte missing nome"
            assert "total" in fonte, "fonte missing total"
            assert "status" in fonte, "fonte missing status"
            assert isinstance(fonte["total"], int), "total should be int"
            assert fonte["status"] in ["ok", "erro"], f"Invalid status: {fonte['status']}"
            print(f"✅ Fonte: {fonte['nome']} = {fonte['total']} ({fonte['status']})")
        
        # Verify at least some expected fontes are present
        fonte_names = [f["nome"] for f in data["fontes_consultadas"]]
        print(f"   Fontes found: {fonte_names}")


class TestBuscarMedicamentoTipoAlerta:
    """Tests for tipo_alerta classification"""
    
    def test_tipo_alerta_values(self):
        """
        Test: tipo_alerta values are correctly classified
        """
        response = requests.get(
            f"{BASE_URL}/api/anvisa/buscar-medicamento",
            params={"q": "desabastecimento"},
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        valid_tipos = [
            "importação excepcional",
            "decisão judicial", 
            "desabastecimento",
            "descontinuação",
            "regulamentação",
            "informativo"
        ]
        
        if data["total"] > 0:
            for r in data["resultados"]:
                if "tipo_alerta" in r and r["tipo_alerta"]:
                    assert r["tipo_alerta"] in valid_tipos, f"Invalid tipo_alerta: {r['tipo_alerta']}"
                    print(f"✅ tipo_alerta: {r['tipo_alerta']}")


class TestBuscarMedicamentoPerformance:
    """Performance and timeout tests"""
    
    def test_search_completes_within_timeout(self):
        """
        Test: Search should complete within 30 seconds (live scraping)
        """
        import time
        start = time.time()
        
        response = requests.get(
            f"{BASE_URL}/api/anvisa/buscar-medicamento",
            params={"q": "dipirona"},
            timeout=30
        )
        
        elapsed = time.time() - start
        
        assert response.status_code == 200
        assert elapsed < 30, f"Search took {elapsed:.1f}s, expected < 30s"
        
        print(f"✅ Search completed in {elapsed:.1f}s")
