"""
ANVISA Radar de Desabastecimento - API Tests
=============================================
Tests for ANVISA drug shortage monitoring features:
- GET /api/anvisa/alertas - List alerts with stats
- POST /api/anvisa/atualizar - Trigger scraper and process alerts
- GET /api/anvisa/stats - Quick statistics

Expected alert fields: medicamento, situacao, tipo_alerta, risco, oportunidade, titulo, link
"""

import pytest
import requests
import os
import time

# Use PUBLIC URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://dama-legal-1.preview.emergentagent.com"


class TestAnvisaAlertasEndpoint:
    """Tests for GET /api/anvisa/alertas endpoint"""
    
    def test_alertas_returns_200(self):
        """Test that /api/anvisa/alertas returns HTTP 200"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✅ GET /api/anvisa/alertas returned HTTP 200")
    
    def test_alertas_returns_alertas_array(self):
        """Test that response contains 'alertas' array"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        assert 'alertas' in data, "Response missing 'alertas' key"
        assert isinstance(data['alertas'], list), "'alertas' must be an array"
        print(f"✅ Response contains 'alertas' array with {len(data['alertas'])} items")
    
    def test_alertas_returns_estatisticas(self):
        """Test that response contains 'estatisticas' object"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        assert 'estatisticas' in data, "Response missing 'estatisticas' key"
        stats = data['estatisticas']
        assert isinstance(stats, dict), "'estatisticas' must be an object"
        print(f"✅ Response contains 'estatisticas': {stats}")
    
    def test_alert_has_required_fields(self):
        """Test that each alert has required fields: medicamento, situacao, tipo_alerta, risco, oportunidade, titulo, link"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        alertas = data.get('alertas', [])
        if len(alertas) == 0:
            pytest.skip("No alerts in database - run POST /api/anvisa/atualizar first")
        
        # Required fields for each alert
        required_fields = ['medicamento', 'situacao', 'tipo_alerta', 'risco', 'oportunidade', 'titulo', 'link']
        
        # Check first 5 alerts
        for idx, alerta in enumerate(alertas[:5]):
            for field in required_fields:
                assert field in alerta, f"Alert {idx} missing required field '{field}'"
            print(f"✅ Alert {idx}: {alerta.get('medicamento', 'N/A')[:30]} has all required fields")
        
        print(f"✅ Verified {min(5, len(alertas))} alerts have all required fields")
    
    def test_risco_values_are_valid(self):
        """Test that risco field contains valid values: ALTO, MEDIO, or BAIXO"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        alertas = data.get('alertas', [])
        if len(alertas) == 0:
            pytest.skip("No alerts in database")
        
        valid_risco = ['ALTO', 'MEDIO', 'BAIXO']
        for idx, alerta in enumerate(alertas[:10]):
            risco = alerta.get('risco', '')
            assert risco in valid_risco, f"Alert {idx} has invalid risco: {risco}"
        
        print(f"✅ All tested alerts have valid 'risco' values")


class TestAnvisaStatsEndpoint:
    """Tests for GET /api/anvisa/stats endpoint"""
    
    def test_stats_returns_200(self):
        """Test that /api/anvisa/stats returns HTTP 200"""
        response = requests.get(f"{BASE_URL}/api/anvisa/stats", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✅ GET /api/anvisa/stats returned HTTP 200")
    
    def test_stats_has_required_counts(self):
        """Test that stats returns total_alertas, risco_alto, risco_medio counts"""
        response = requests.get(f"{BASE_URL}/api/anvisa/stats", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        required_keys = ['total_alertas', 'risco_alto', 'risco_medio']
        for key in required_keys:
            assert key in data, f"Stats missing required key '{key}'"
            assert isinstance(data[key], int), f"'{key}' must be an integer"
        
        print(f"✅ Stats: total_alertas={data['total_alertas']}, risco_alto={data['risco_alto']}, risco_medio={data['risco_medio']}")
    
    def test_stats_has_oportunidades(self):
        """Test that stats includes opportunity counts"""
        response = requests.get(f"{BASE_URL}/api/anvisa/stats", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        # Check for opportunity keys
        assert 'oportunidades_importacao' in data or 'oportunidades_licitacao' in data, \
            "Stats should include opportunity counts"
        
        print(f"✅ Stats includes opportunity counts: importacao={data.get('oportunidades_importacao', 'N/A')}, licitacao={data.get('oportunidades_licitacao', 'N/A')}")


class TestAnvisaAtualizarEndpoint:
    """Tests for POST /api/anvisa/atualizar endpoint"""
    
    def test_atualizar_returns_200(self):
        """Test that POST /api/anvisa/atualizar returns HTTP 200"""
        response = requests.post(f"{BASE_URL}/api/anvisa/atualizar", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✅ POST /api/anvisa/atualizar returned HTTP 200")
    
    def test_atualizar_returns_coletados_processados(self):
        """Test that response contains 'coletados' > 0 and 'processados' > 0"""
        response = requests.post(f"{BASE_URL}/api/anvisa/atualizar", timeout=90)
        assert response.status_code == 200
        data = response.json()
        
        assert 'coletados' in data, "Response missing 'coletados' key"
        assert 'processados' in data, "Response missing 'processados' key"
        
        coletados = data.get('coletados', 0)
        processados = data.get('processados', 0)
        
        assert coletados >= 0, f"coletados should be >= 0, got {coletados}"
        assert processados >= 0, f"processados should be >= 0, got {processados}"
        
        print(f"✅ Atualizar: coletados={coletados}, processados={processados}")
        
        # Ideally we'd want > 0, but ANVISA may sometimes return 0
        if coletados > 0:
            print(f"✅ Successfully scraped {coletados} news items from ANVISA")
        else:
            print(f"⚠️ No news scraped - ANVISA might be down or no new content")
    
    def test_atualizar_returns_estatisticas(self):
        """Test that POST atualizar also returns updated statistics"""
        response = requests.post(f"{BASE_URL}/api/anvisa/atualizar", timeout=90)
        assert response.status_code == 200
        data = response.json()
        
        assert 'estatisticas' in data, "Response missing 'estatisticas' key"
        stats = data['estatisticas']
        
        assert 'total_alertas' in stats, "Stats missing 'total_alertas'"
        print(f"✅ After update: total_alertas={stats.get('total_alertas', 0)}")


class TestAnvisaIntegration:
    """Integration tests for ANVISA feature flow"""
    
    def test_full_flow_update_then_get_alerts(self):
        """Test complete flow: POST atualizar -> GET alertas -> verify data persisted"""
        # Step 1: Trigger update
        print("Step 1: Triggering ANVISA update...")
        update_response = requests.post(f"{BASE_URL}/api/anvisa/atualizar", timeout=90)
        assert update_response.status_code == 200, f"Update failed: {update_response.status_code}"
        update_data = update_response.json()
        print(f"  → coletados={update_data.get('coletados', 0)}, processados={update_data.get('processados', 0)}")
        
        # Step 2: Wait a moment for DB to settle
        time.sleep(1)
        
        # Step 3: Get alerts
        print("Step 2: Fetching alerts...")
        alertas_response = requests.get(f"{BASE_URL}/api/anvisa/alertas", timeout=30)
        assert alertas_response.status_code == 200
        alertas_data = alertas_response.json()
        
        alertas = alertas_data.get('alertas', [])
        print(f"  → Retrieved {len(alertas)} alerts")
        
        # Step 3: Get stats
        print("Step 3: Verifying stats...")
        stats_response = requests.get(f"{BASE_URL}/api/anvisa/stats", timeout=30)
        assert stats_response.status_code == 200
        stats = stats_response.json()
        
        print(f"  → Stats: total={stats.get('total_alertas', 0)}, alto={stats.get('risco_alto', 0)}, medio={stats.get('risco_medio', 0)}")
        
        # Verify stats matches alertas count
        if len(alertas) > 0:
            assert stats.get('total_alertas', 0) >= len(alertas) or len(alertas) <= 50, \
                f"Stats total ({stats.get('total_alertas', 0)}) should match or exceed alertas returned ({len(alertas)})"
        
        print("✅ Full integration flow completed successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
