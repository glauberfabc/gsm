"""
Test LMR Analysis with different tipo_produto (category) values
Verifies that biologico returns different margins than sintetico per IN 428/2026
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestLMRCategoryMargins:
    """Test that different product types return different tax margins"""
    
    def test_biologico_margin_is_21(self):
        """Biologico products should have margem_distribuidora = 21.0%"""
        response = requests.post(
            f"{BASE_URL}/api/dama/lmr-analise-medicamento",
            json={
                "medicamento": "TestBiologico",
                "preco_referencia": 1000,
                "tipo_produto": "biologico"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["tipo_produto"] == "biologico"
        assert data["estrategia_tributaria"]["margem_distribuidora"] == 21.0, \
            f"Expected margem_distribuidora=21.0 for biologico, got {data['estrategia_tributaria']['margem_distribuidora']}"
        print(f"✅ Biologico margem_distribuidora: {data['estrategia_tributaria']['margem_distribuidora']}%")
    
    def test_sintetico_margin_is_20_5(self):
        """Sintetico products should have margem_distribuidora = 20.5%"""
        response = requests.post(
            f"{BASE_URL}/api/dama/lmr-analise-medicamento",
            json={
                "medicamento": "TestSintetico",
                "preco_referencia": 1000,
                "tipo_produto": "sintetico"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["tipo_produto"] == "sintetico"
        assert data["estrategia_tributaria"]["margem_distribuidora"] == 20.5, \
            f"Expected margem_distribuidora=20.5 for sintetico, got {data['estrategia_tributaria']['margem_distribuidora']}"
        print(f"✅ Sintetico margem_distribuidora: {data['estrategia_tributaria']['margem_distribuidora']}%")
    
    def test_biologico_vs_sintetico_different_margins(self):
        """Biologico and sintetico should have different margins"""
        # Get biologico
        bio_response = requests.post(
            f"{BASE_URL}/api/dama/lmr-analise-medicamento",
            json={"medicamento": "TestMed", "preco_referencia": 1000, "tipo_produto": "biologico"}
        )
        bio_data = bio_response.json()
        
        # Get sintetico
        sin_response = requests.post(
            f"{BASE_URL}/api/dama/lmr-analise-medicamento",
            json={"medicamento": "TestMed", "preco_referencia": 1000, "tipo_produto": "sintetico"}
        )
        sin_data = sin_response.json()
        
        bio_margin = bio_data["estrategia_tributaria"]["margem_distribuidora"]
        sin_margin = sin_data["estrategia_tributaria"]["margem_distribuidora"]
        
        assert bio_margin != sin_margin, \
            f"Biologico ({bio_margin}%) and sintetico ({sin_margin}%) should have different margins"
        assert bio_margin > sin_margin, \
            f"Biologico margin ({bio_margin}%) should be higher than sintetico ({sin_margin}%)"
        print(f"✅ Margins differ: biologico={bio_margin}%, sintetico={sin_margin}%")
    
    def test_generico_margin(self):
        """Generico products should have specific margin"""
        response = requests.post(
            f"{BASE_URL}/api/dama/lmr-analise-medicamento",
            json={"medicamento": "TestGenerico", "preco_referencia": 1000, "tipo_produto": "generico"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["tipo_produto"] == "generico"
        print(f"✅ Generico margem_distribuidora: {data['estrategia_tributaria']['margem_distribuidora']}%")
    
    def test_similar_margin(self):
        """Similar products should have specific margin"""
        response = requests.post(
            f"{BASE_URL}/api/dama/lmr-analise-medicamento",
            json={"medicamento": "TestSimilar", "preco_referencia": 1000, "tipo_produto": "similar"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["tipo_produto"] == "similar"
        print(f"✅ Similar margem_distribuidora: {data['estrategia_tributaria']['margem_distribuidora']}%")
    
    def test_excepcional_margin(self):
        """Excepcional products should have specific margin"""
        response = requests.post(
            f"{BASE_URL}/api/dama/lmr-analise-medicamento",
            json={"medicamento": "TestExcepcional", "preco_referencia": 1000, "tipo_produto": "excepcional"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["tipo_produto"] == "excepcional"
        print(f"✅ Excepcional margem_distribuidora: {data['estrategia_tributaria']['margem_distribuidora']}%")


class TestLMRAnalysisEndpoint:
    """Test LMR analysis endpoint basic functionality"""
    
    def test_lmr_analysis_list(self):
        """GET /api/dama/lmr-analysis returns opportunities list"""
        response = requests.get(f"{BASE_URL}/api/dama/lmr-analysis?limite=10")
        assert response.status_code == 200
        data = response.json()
        assert "oportunidades" in data
        assert "total" in data
        assert "estatisticas" in data
        assert "norma_referencia" in data
        print(f"✅ LMR analysis list: {data['total']} opportunities")
    
    def test_lmr_analysis_response_structure(self):
        """POST /api/dama/lmr-analise-medicamento returns correct structure"""
        response = requests.post(
            f"{BASE_URL}/api/dama/lmr-analise-medicamento",
            json={"medicamento": "TestStructure", "preco_referencia": 500, "tipo_produto": "sintetico"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields
        assert "medicamento" in data
        assert "norma_referencia" in data
        assert "tipo_produto" in data
        assert "classificacao_lmr" in data
        assert "estrategia_tributaria" in data
        assert "analise_margem" in data
        assert "recomendacao" in data
        assert "oportunidade_score" in data
        
        # Check estrategia_tributaria structure
        trib = data["estrategia_tributaria"]
        assert "imposto_importacao" in trib
        assert "icms" in trib
        assert "pis" in trib
        assert "cofins" in trib
        assert "carga_tributaria_total" in trib
        assert "margem_distribuidora" in trib
        
        print("✅ Response structure is correct")


class TestNotificationsEndpoint:
    """Test notifications/alerts endpoints"""
    
    def test_notifications_list(self):
        """GET /api/notificacoes/oportunidades returns alerts"""
        response = requests.get(f"{BASE_URL}/api/notificacoes/oportunidades?limite=10")
        assert response.status_code == 200
        data = response.json()
        # Response is an object with alertas array
        assert "alertas" in data or isinstance(data, list)
        alerts = data.get("alertas", data) if isinstance(data, dict) else data
        print(f"✅ Notifications list: {len(alerts)} alerts")
    
    def test_get_alert_by_id(self):
        """GET /api/notificacoes/oportunidades/{id} returns alert details"""
        # Use known test alert ID
        alert_id = "ee57bbff-5e0c-4f16-b073-c86cf66d9389"
        response = requests.get(f"{BASE_URL}/api/notificacoes/oportunidades/{alert_id}")
        
        if response.status_code == 200:
            data = response.json()
            assert "alerta" in data
            assert "analise_lmr" in data or "pdf_url" in data
            print(f"✅ Alert {alert_id} retrieved successfully")
        elif response.status_code == 404:
            print(f"⚠️ Alert {alert_id} not found (may have been deleted)")
        else:
            pytest.fail(f"Unexpected status code: {response.status_code}")
    
    def test_get_nonexistent_alert(self):
        """GET /api/notificacoes/oportunidades/{invalid_id} returns 404"""
        response = requests.get(f"{BASE_URL}/api/notificacoes/oportunidades/nonexistent-id-12345")
        assert response.status_code == 404
        print("✅ Nonexistent alert returns 404")


class TestExistingEndpoints:
    """Regression tests for existing endpoints"""
    
    def test_empresas_list(self):
        """GET /api/empresas returns companies"""
        response = requests.get(f"{BASE_URL}/api/empresas")
        assert response.status_code == 200
        print("✅ /api/empresas works")
    
    def test_listas_list(self):
        """GET /api/listas returns lists"""
        response = requests.get(f"{BASE_URL}/api/listas")
        assert response.status_code == 200
        print("✅ /api/listas works")
    
    def test_radares_list(self):
        """GET /api/radares returns radars"""
        response = requests.get(f"{BASE_URL}/api/radares")
        assert response.status_code == 200
        print("✅ /api/radares works")
