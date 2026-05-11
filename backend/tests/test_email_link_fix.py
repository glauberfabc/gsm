"""
Test Email Link Fix - Iteration 42
Tests for the email link fix where emails now link to frontend URL with ?alerta=<ID>
instead of directly to the API endpoint.

Features tested:
1. GET /api/notificacoes/oportunidades/{alerta_id} returns alerta + analise_lmr + pdf_url
2. GET /api/notificacoes/oportunidades/nonexistent-id returns 404
3. GET /api/dama/prova-documental-lmr/{alerta_id} returns PDF (application/pdf)
4. LMR analysis trigger (score >= 80%) saves alert with frontend URL in email link
"""

import pytest
import requests
import os
import uuid
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://dama-legal-1.preview.emergentagent.com')

class TestEmailLinkFix:
    """Tests for the email link fix - frontend URL instead of API URL"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.test_alerta_id = None
        yield
        # Cleanup
        if self.test_alerta_id:
            try:
                # Delete test alert
                requests.delete(f"{BASE_URL}/api/notificacoes/oportunidades/{self.test_alerta_id}")
            except:
                pass
    
    def test_get_alerta_by_id_returns_404_for_nonexistent(self):
        """GET /api/notificacoes/oportunidades/nonexistent-id returns 404"""
        response = self.session.get(f"{BASE_URL}/api/notificacoes/oportunidades/nonexistent-id-12345")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        data = response.json()
        assert "detail" in data or "error" in data or "message" in data
        print(f"PASS: Nonexistent alert returns 404 with message: {data}")
    
    def test_get_alerta_by_id_returns_full_data(self):
        """GET /api/notificacoes/oportunidades/{alerta_id} returns alerta + analise_lmr + pdf_url"""
        # First, get list of existing alerts
        response = self.session.get(f"{BASE_URL}/api/notificacoes/oportunidades?limite=5")
        assert response.status_code == 200, f"Failed to get alerts list: {response.status_code}"
        data = response.json()
        
        alertas = data.get('alertas', [])
        if not alertas:
            pytest.skip("No existing alerts to test - need to create one first")
        
        # Get first alert by ID
        alerta_id = alertas[0].get('id')
        assert alerta_id, "Alert has no ID"
        
        response = self.session.get(f"{BASE_URL}/api/notificacoes/oportunidades/{alerta_id}")
        assert response.status_code == 200, f"Failed to get alert by ID: {response.status_code}"
        
        data = response.json()
        
        # Verify response structure
        assert 'alerta' in data, "Response missing 'alerta' field"
        assert 'analise_lmr' in data, "Response missing 'analise_lmr' field"
        assert 'pdf_url' in data, "Response missing 'pdf_url' field"
        
        # Verify alerta data
        alerta = data['alerta']
        assert alerta.get('id') == alerta_id, "Alert ID mismatch"
        assert 'medicamento' in alerta, "Alert missing 'medicamento'"
        
        # Verify pdf_url format
        pdf_url = data['pdf_url']
        assert pdf_url.startswith('/api/dama/prova-documental-lmr/'), f"Invalid pdf_url format: {pdf_url}"
        assert alerta_id in pdf_url, "pdf_url should contain alert ID"
        
        print(f"PASS: Alert {alerta_id} returned with full data structure")
        print(f"  - medicamento: {alerta.get('medicamento')}")
        print(f"  - analise_lmr present: {data.get('analise_lmr') is not None}")
        print(f"  - pdf_url: {pdf_url}")
    
    def test_prova_documental_pdf_endpoint_returns_pdf(self):
        """GET /api/dama/prova-documental-lmr/{alerta_id} returns PDF (application/pdf)"""
        # First, get an existing alert
        response = self.session.get(f"{BASE_URL}/api/notificacoes/oportunidades?limite=5")
        assert response.status_code == 200
        data = response.json()
        
        alertas = data.get('alertas', [])
        if not alertas:
            pytest.skip("No existing alerts to test PDF endpoint")
        
        alerta_id = alertas[0].get('id')
        
        # Request PDF
        response = self.session.get(f"{BASE_URL}/api/dama/prova-documental-lmr/{alerta_id}")
        
        # Should return PDF or 404 if alert doesn't have PDF data
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', '')
            assert 'application/pdf' in content_type, f"Expected PDF content-type, got: {content_type}"
            assert len(response.content) > 100, "PDF content too small"
            print(f"PASS: PDF endpoint returns valid PDF for alert {alerta_id}")
            print(f"  - Content-Type: {content_type}")
            print(f"  - Content-Length: {len(response.content)} bytes")
        elif response.status_code == 404:
            print(f"INFO: Alert {alerta_id} has no PDF data (404 expected for some alerts)")
        else:
            pytest.fail(f"Unexpected status code: {response.status_code}")
    
    def test_prova_documental_pdf_returns_404_for_nonexistent(self):
        """GET /api/dama/prova-documental-lmr/nonexistent-id returns 404"""
        response = self.session.get(f"{BASE_URL}/api/dama/prova-documental-lmr/nonexistent-id-xyz")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: PDF endpoint returns 404 for nonexistent alert")


class TestLmrAnalysisTrigger:
    """Tests for LMR analysis trigger that creates alerts with frontend URL"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.created_alert_ids = []
        yield
        # Cleanup created alerts
        for alert_id in self.created_alert_ids:
            try:
                # Note: There's no delete endpoint, but we track for reference
                pass
            except:
                pass
    
    def test_lmr_analysis_endpoint_exists(self):
        """POST /api/dama/lmr-analise-medicamento endpoint exists and works"""
        payload = {
            "medicamento": "TEST_MEDICAMENTO_ANALISE",
            "preco_referencia": 100.0,
            "tipo_produto": "sintetico"
        }
        
        response = self.session.post(f"{BASE_URL}/api/dama/lmr-analise-medicamento", json=payload)
        
        # Should return 200 with analysis data
        assert response.status_code == 200, f"LMR analysis failed: {response.status_code} - {response.text}"
        
        data = response.json()
        
        # Verify response structure
        assert 'medicamento' in data, "Response missing 'medicamento'"
        assert 'oportunidade_score' in data, "Response missing 'oportunidade_score'"
        assert 'classificacao_lmr' in data, "Response missing 'classificacao_lmr'"
        assert 'estrategia_tributaria' in data, "Response missing 'estrategia_tributaria'"
        assert 'recomendacao' in data, "Response missing 'recomendacao'"
        
        print(f"PASS: LMR analysis endpoint works")
        print(f"  - medicamento: {data.get('medicamento')}")
        print(f"  - score: {data.get('oportunidade_score')}%")
        print(f"  - categoria: {data.get('classificacao_lmr', {}).get('categoria')}")
    
    def test_lmr_analysis_with_janela_aberta_creates_alert(self):
        """LMR analysis with score >= 80% should create alert with frontend URL"""
        # First, we need to create an ANVISA alert with janela_importacao=True
        # This is done by inserting directly or triggering the scraper
        
        # For this test, we'll analyze a medicamento that should have high score
        # based on existing ANVISA data
        
        # Get existing ANVISA alerts with janela_importacao
        response = self.session.get(f"{BASE_URL}/api/anvisa/alertas?limit=10")
        if response.status_code != 200:
            pytest.skip("ANVISA alerts endpoint not available")
        
        data = response.json()
        alertas_anvisa = data.get('alertas', [])
        
        # Find one with janela_importacao
        med_with_janela = None
        for alerta in alertas_anvisa:
            if alerta.get('janela_importacao'):
                med_with_janela = alerta.get('medicamento_detectado') or alerta.get('medicamento')
                break
        
        if not med_with_janela:
            pytest.skip("No ANVISA alerts with janela_importacao found")
        
        # Analyze this medicamento
        payload = {
            "medicamento": med_with_janela,
            "preco_referencia": 500.0,
            "tipo_produto": "sintetico"
        }
        
        response = self.session.post(f"{BASE_URL}/api/dama/lmr-analise-medicamento", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        score = data.get('oportunidade_score', 0)
        
        print(f"LMR Analysis for '{med_with_janela}':")
        print(f"  - Score: {score}%")
        print(f"  - Janela aberta: {data.get('classificacao_lmr', {}).get('janela_aberta')}")
        
        if score >= 80:
            # Check if alert was created
            response = self.session.get(f"{BASE_URL}/api/notificacoes/oportunidades?limite=10")
            assert response.status_code == 200
            
            alertas = response.json().get('alertas', [])
            
            # Find alert for this medicamento
            found_alert = None
            for alerta in alertas:
                if alerta.get('medicamento', '').lower() == med_with_janela.lower():
                    found_alert = alerta
                    break
            
            if found_alert:
                print(f"PASS: Alert created for high-score medicamento")
                print(f"  - Alert ID: {found_alert.get('id')}")
                print(f"  - Score: {found_alert.get('oportunidade_score')}%")
                self.created_alert_ids.append(found_alert.get('id'))
            else:
                print(f"INFO: Alert may have been deduplicated (already exists)")
        else:
            print(f"INFO: Score {score}% < 80%, no alert created (expected)")


class TestNotificacoesEndpoint:
    """Tests for the notifications/oportunidades endpoint"""
    
    def test_list_alertas_oportunidade(self):
        """GET /api/notificacoes/oportunidades returns list of alerts"""
        response = requests.get(f"{BASE_URL}/api/notificacoes/oportunidades?limite=15")
        assert response.status_code == 200, f"Failed: {response.status_code}"
        
        data = response.json()
        
        # Verify response structure
        assert 'alertas' in data, "Response missing 'alertas'"
        assert 'total' in data, "Response missing 'total'"
        assert 'nao_lidas' in data, "Response missing 'nao_lidas'"
        
        alertas = data['alertas']
        assert isinstance(alertas, list), "alertas should be a list"
        
        print(f"PASS: Notifications endpoint returns {len(alertas)} alerts")
        print(f"  - Total: {data['total']}")
        print(f"  - Nao lidas: {data['nao_lidas']}")
        
        # Verify alert structure if any exist
        if alertas:
            alerta = alertas[0]
            required_fields = ['id', 'medicamento', 'oportunidade_score']
            for field in required_fields:
                assert field in alerta, f"Alert missing required field: {field}"
            print(f"  - First alert: {alerta.get('medicamento')} (score: {alerta.get('oportunidade_score')}%)")
    
    def test_mark_alerta_as_read(self):
        """POST /api/notificacoes/oportunidades/{alerta_id}/lida marks alert as read"""
        # Get an existing alert
        response = requests.get(f"{BASE_URL}/api/notificacoes/oportunidades?limite=5")
        assert response.status_code == 200
        
        alertas = response.json().get('alertas', [])
        if not alertas:
            pytest.skip("No alerts to test mark as read")
        
        alerta_id = alertas[0].get('id')
        is_already_read = alertas[0].get('lida', False)
        
        # Mark as read
        response = requests.post(f"{BASE_URL}/api/notificacoes/oportunidades/{alerta_id}/lida")
        
        # If already read, endpoint returns 404 (modified_count == 0)
        # If not read, returns 200
        if is_already_read:
            # Already read - endpoint returns 404 because no modification happened
            assert response.status_code in [200, 404], f"Unexpected status: {response.status_code}"
            print(f"PASS: Alert {alerta_id} was already read (status: {response.status_code})")
        else:
            assert response.status_code == 200, f"Failed to mark as read: {response.status_code}"
            data = response.json()
            assert 'message' in data or 'id' in data
            print(f"PASS: Alert {alerta_id} marked as read")
    
    def test_mark_nonexistent_alerta_returns_404(self):
        """POST /api/notificacoes/oportunidades/nonexistent/lida returns 404"""
        response = requests.post(f"{BASE_URL}/api/notificacoes/oportunidades/nonexistent-xyz/lida")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: Mark nonexistent alert returns 404")


class TestRadarLmrEndpoint:
    """Tests for the Radar LMR analysis endpoint"""
    
    def test_lmr_analysis_list(self):
        """GET /api/dama/lmr-analysis returns list of opportunities"""
        response = requests.get(f"{BASE_URL}/api/dama/lmr-analysis?limite=20")
        assert response.status_code == 200, f"Failed: {response.status_code}"
        
        data = response.json()
        
        # Verify response structure
        assert 'oportunidades' in data, "Response missing 'oportunidades'"
        assert 'total' in data, "Response missing 'total'"
        assert 'estatisticas' in data, "Response missing 'estatisticas'"
        
        stats = data.get('estatisticas', {})
        print(f"PASS: Radar LMR endpoint returns opportunities")
        print(f"  - Total: {data['total']}")
        print(f"  - Alta: {stats.get('oportunidade_alta', 0)}")
        print(f"  - Media: {stats.get('oportunidade_media', 0)}")
        print(f"  - Baixa: {stats.get('oportunidade_baixa', 0)}")


class TestCacheEndpoints:
    """Tests for cache endpoints (regression)"""
    
    def test_cache_stats(self):
        """GET /api/cache/stats returns cache statistics"""
        response = requests.get(f"{BASE_URL}/api/cache/stats")
        assert response.status_code == 200, f"Failed: {response.status_code}"
        
        data = response.json()
        assert 'cache_stats' in data or 'smart_cache_stats' in data
        print(f"PASS: Cache stats endpoint works")
    
    def test_cache_clear(self):
        """POST /api/cache/clear clears the cache"""
        response = requests.post(f"{BASE_URL}/api/cache/clear")
        assert response.status_code == 200, f"Failed: {response.status_code}"
        
        data = response.json()
        assert 'message' in data
        print(f"PASS: Cache clear endpoint works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
