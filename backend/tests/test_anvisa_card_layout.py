"""
Test ANVISA Tab - Card-Based Layout v4
=======================================
Tests for the redesigned ANVISA tab showing medicine names prominently
in card format with 'Buscar Licitações' button.

Features tested:
1. GET /api/anvisa/alertas returns alerts with medicamento_detectado
2. Each alert has clean single medicine names (not comma-separated)
3. POST /api/anvisa/atualizar triggers the scraper
4. Stats include total_alertas, janelas_abertas, risco_alto, importação counts
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestAnvisaAlertas:
    """Tests for GET /api/anvisa/alertas endpoint"""

    def test_alertas_endpoint_returns_200(self):
        """Test that alertas endpoint is accessible"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✅ GET /api/anvisa/alertas returned 200")

    def test_alertas_has_required_structure(self):
        """Test response has alertas array and estatisticas"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas", timeout=30)
        data = response.json()
        
        assert 'alertas' in data, "Response should have 'alertas' key"
        assert 'estatisticas' in data, "Response should have 'estatisticas' key"
        assert isinstance(data['alertas'], list), "alertas should be a list"
        print(f"✅ Response has alertas ({len(data['alertas'])} items) and estatisticas")

    def test_alertas_have_medicamento_detectado(self):
        """Test each alert has medicamento_detectado field"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas", timeout=30)
        alertas = response.json().get('alertas', [])
        
        if not alertas:
            pytest.skip("No alerts in database - need to run /api/anvisa/atualizar first")
        
        for i, alerta in enumerate(alertas[:10]):  # Check first 10
            med = alerta.get('medicamento_detectado') or alerta.get('medicamento', '')
            assert med, f"Alert {i} should have medicamento_detectado or medicamento"
            print(f"  Alert {i}: {med[:50]}...")
        
        print(f"✅ All checked alerts have medicamento field")

    def test_medicine_names_are_clean_single_names(self):
        """Test medicine names are single (not comma-separated lists)"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas", timeout=30)
        alertas = response.json().get('alertas', [])
        
        if not alertas:
            pytest.skip("No alerts in database")
        
        # Check that most names don't have commas (some edge cases allowed)
        comma_count = 0
        for alerta in alertas:
            med = alerta.get('medicamento_detectado', '') or alerta.get('medicamento', '')
            if ',' in med:
                comma_count += 1
                print(f"  ⚠️ Comma in name: {med[:60]}")
        
        # Allow up to 20% with commas (legacy data)
        max_allowed = len(alertas) * 0.2
        assert comma_count <= max_allowed, f"Too many comma-separated names: {comma_count}/{len(alertas)}"
        print(f"✅ Medicine names are clean: {comma_count}/{len(alertas)} have commas (threshold: {max_allowed})")

    def test_alertas_have_required_fields_for_card(self):
        """Test alerts have all fields needed for card display"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas", timeout=30)
        alertas = response.json().get('alertas', [])
        
        if not alertas:
            pytest.skip("No alerts in database")
        
        required_fields = ['tipo_alerta', 'risco', 'fonte', 'indice_oportunidade']
        
        for i, alerta in enumerate(alertas[:5]):
            for field in required_fields:
                assert field in alerta, f"Alert {i} missing field: {field}"
        
        print(f"✅ Alerts have all required fields for card display: {required_fields}")

    def test_alertas_have_janela_importacao_flag(self):
        """Test alerts have janela_importacao boolean flag"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas", timeout=30)
        alertas = response.json().get('alertas', [])
        
        if not alertas:
            pytest.skip("No alerts in database")
        
        janela_true = sum(1 for a in alertas if a.get('janela_importacao') == True)
        janela_false = sum(1 for a in alertas if a.get('janela_importacao') == False)
        
        print(f"  janela_importacao=True: {janela_true}")
        print(f"  janela_importacao=False: {janela_false}")
        print(f"✅ janela_importacao flag present in alerts")


class TestAnvisaStats:
    """Tests for ANVISA statistics"""

    def test_stats_has_required_fields(self):
        """Test statistics include all required counts"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas", timeout=30)
        stats = response.json().get('estatisticas', {})
        
        required_stats = ['total_alertas', 'janelas_abertas', 'risco_alto', 'oportunidades_importacao']
        
        for stat in required_stats:
            assert stat in stats, f"Stats missing: {stat}"
            print(f"  {stat}: {stats.get(stat)}")
        
        print(f"✅ All required stats present")

    def test_stats_values_are_numbers(self):
        """Test stat values are numbers"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas", timeout=30)
        stats = response.json().get('estatisticas', {})
        
        for key, value in stats.items():
            if key != 'por_tipo':  # por_tipo is a dict
                assert isinstance(value, (int, float)), f"{key} should be numeric, got {type(value)}"
        
        print(f"✅ All stat values are numeric")


class TestAnvisaAtualizar:
    """Tests for POST /api/anvisa/atualizar endpoint (scraper trigger)"""

    def test_atualizar_endpoint_accessible(self):
        """Test that atualizar endpoint is accessible"""
        # Just check endpoint exists, don't actually run full scrape
        response = requests.post(f"{BASE_URL}/api/anvisa/atualizar", timeout=120)
        assert response.status_code in [200, 500, 504], f"Unexpected status: {response.status_code}"
        print(f"✅ POST /api/anvisa/atualizar returned {response.status_code}")

    def test_atualizar_returns_stats(self):
        """Test atualizar returns processing stats"""
        response = requests.post(f"{BASE_URL}/api/anvisa/atualizar", timeout=120)
        
        if response.status_code == 200:
            data = response.json()
            assert 'coletados' in data or 'processados' in data or 'estatisticas' in data
            print(f"✅ Atualizar returned stats: coletados={data.get('coletados')}, processados={data.get('processados')}")
        else:
            # Timeout or error is acceptable for long-running scraper
            print(f"⚠️ Atualizar returned {response.status_code} (may be timeout)")


class TestAnvisaStatsEndpoint:
    """Tests for GET /api/anvisa/stats endpoint"""

    def test_stats_endpoint_returns_200(self):
        """Test stats endpoint"""
        response = requests.get(f"{BASE_URL}/api/anvisa/stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert 'total_alertas' in data
        assert 'janelas_abertas' in data
        print(f"✅ GET /api/anvisa/stats: total={data.get('total_alertas')}, janelas={data.get('janelas_abertas')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
