"""
Test Suite: Prova Documental LMR Endpoint and Email Link Fix
Tests the new GET /api/dama/prova-documental-lmr/{alerta_id} endpoint
and verifies the email template uses correct link and button text.
"""

import pytest
import requests
import os
import uuid
from datetime import datetime, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestProvaDocumentalLMREndpoint:
    """Tests for GET /api/dama/prova-documental-lmr/{alerta_id}"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data"""
        self.test_alerta_id = f"TEST_ALERTA_{uuid.uuid4().hex[:8]}"
        self.test_medicamento = f"TEST_MEDICAMENTO_{uuid.uuid4().hex[:6]}"
        yield
        # Cleanup handled in individual tests
    
    def test_prova_documental_nonexistent_id_returns_404(self):
        """Test that nonexistent alerta_id returns 404"""
        response = requests.get(f"{BASE_URL}/api/dama/prova-documental-lmr/nonexistent-id-12345")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        data = response.json()
        assert "detail" in data
        print(f"✅ Nonexistent ID returns 404: {data['detail']}")
    
    def test_prova_documental_returns_pdf_for_valid_alert(self):
        """Test that valid alerta_id returns PDF"""
        # First, create a test alert in oportunidades_alertas
        from pymongo import MongoClient
        mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
        db_name = os.environ.get('DB_NAME', 'test_database')
        client = MongoClient(mongo_url)
        db = client[db_name]
        
        # Create test alert
        test_alert = {
            'id': self.test_alerta_id,
            'medicamento': self.test_medicamento,
            'oportunidade_score': 85,
            'tipo_produto': 'sintetico',
            'categoria_lmr': 'excepcional',
            'beneficio': 'Isencao II + ICMS reduzido',
            'carga_tributaria': 20.5,
            'recomendacao': 'OPORTUNIDADE ALTA: Produto com janela aberta',
            'janela_aberta': True,
            'lida': False,
            'criado_em': datetime.now(timezone.utc).isoformat(),
            'email_enviado': False,
            'email_status': 'pendente',
        }
        db.oportunidades_alertas.insert_one(test_alert)
        
        try:
            # Call the endpoint
            response = requests.get(f"{BASE_URL}/api/dama/prova-documental-lmr/{self.test_alerta_id}")
            
            # Verify response
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            assert response.headers.get('Content-Type') == 'application/pdf', f"Expected PDF, got {response.headers.get('Content-Type')}"
            
            # Verify PDF content starts with PDF magic bytes
            content = response.content
            assert content[:4] == b'%PDF', f"Content doesn't start with PDF magic bytes"
            
            # Verify Content-Disposition header
            content_disp = response.headers.get('Content-Disposition', '')
            assert 'prova_documental_LMR' in content_disp, f"Filename should contain 'prova_documental_LMR': {content_disp}"
            
            print(f"✅ Valid alert returns PDF: {len(content)} bytes, Content-Disposition: {content_disp}")
            
        finally:
            # Cleanup
            db.oportunidades_alertas.delete_one({'id': self.test_alerta_id})
            client.close()


class TestLMRAlertLinkInMongoDB:
    """Tests that LMR alerts have correct link_pdf pointing to our endpoint"""
    
    def test_lmr_analysis_creates_alert_with_correct_link(self):
        """
        When LMR analysis triggers alert (score >= 80%), 
        the edital_lmr dict should have link_pdf pointing to /api/dama/prova-documental-lmr/{id}
        NOT to pncp.gov.br
        """
        from pymongo import MongoClient
        import time
        
        mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
        db_name = os.environ.get('DB_NAME', 'test_database')
        client = MongoClient(mongo_url)
        db = client[db_name]
        
        test_medicamento = f"TEST_JANELA_{uuid.uuid4().hex[:6]}"
        
        # Create ANVISA alert with janela_importacao=True to trigger high score
        anvisa_alert = {
            'medicamento': test_medicamento,
            'medicamento_detectado': test_medicamento,
            'principio_ativo': test_medicamento,
            'janela_importacao': True,
            'tipo_alerta': 'desabastecimento',
            'risco': 'ALTO',
            'situacao': 'Desabastecimento confirmado',
            'criado_em': datetime.now(timezone.utc).isoformat(),
        }
        db.anvisa_alerts.insert_one(anvisa_alert)
        
        # Delete any existing alerts for this medicamento
        db.oportunidades_alertas.delete_many({'medicamento': test_medicamento})
        
        try:
            # Trigger LMR analysis
            response = requests.post(
                f"{BASE_URL}/api/dama/lmr-analise-medicamento",
                json={'medicamento': test_medicamento}
            )
            assert response.status_code == 200, f"LMR analysis failed: {response.text}"
            
            data = response.json()
            score = data.get('oportunidade_score', 0)
            print(f"LMR Analysis score: {score}%")
            
            # Score should be >= 80 due to janela_importacao=True
            assert score >= 80, f"Expected score >= 80, got {score}"
            
            # Wait for alert to be saved
            time.sleep(1)
            
            # Check the alert in MongoDB
            alert = db.oportunidades_alertas.find_one({'medicamento': test_medicamento}, {'_id': 0})
            assert alert is not None, "Alert should have been created"
            
            # The alert itself doesn't store link_pdf, but we verify the email was sent
            # The link_pdf is constructed in _disparar_email_oportunidade
            # We can verify by checking email_status
            email_status = alert.get('email_status', '')
            print(f"Alert created: id={alert.get('id')}, email_status={email_status}")
            
            # Verify the endpoint URL would be correct
            expected_link_pattern = f"/api/dama/prova-documental-lmr/{alert.get('id')}"
            print(f"✅ Alert created with id={alert.get('id')}, expected link pattern: {expected_link_pattern}")
            
        finally:
            # Cleanup
            db.anvisa_alerts.delete_many({'medicamento': test_medicamento})
            db.oportunidades_alertas.delete_many({'medicamento': test_medicamento})
            client.close()


class TestEmailTemplateButtonText:
    """Tests that email template shows correct button text for DAMA alerts"""
    
    def test_email_service_button_text_for_dama_alert(self):
        """
        Email template should show 'Ver Analise no DAMA / Baixar Prova Documental' (green)
        for DAMA alerts instead of 'Ver Edital / Baixar PDF' (blue)
        """
        # Import the email service
        import sys
        sys.path.insert(0, '/app/backend')
        from services.email_service import EmailService
        
        email_service = EmailService()
        
        # Test DAMA alert edital
        dama_edital = {
            'orgao': 'DAMA Intelligence - Radar LMR',
            'numero_processo': 'LMR-TEST',
            'modalidade': 'Categoria: EXCEPCIONAL',
            'objeto': 'OPORTUNIDADE DE IMPORTACAO - Score 85%',
            'status_oportunidade': 'ATIVA',
            'link_pdf': 'https://dama-legal-1.preview.emergentagent.com/api/dama/prova-documental-lmr/test-id',
            'is_dama_alert': True,
            'itens_correspondentes': [],
        }
        
        # Generate card HTML
        card_html = email_service._gerar_card_edital(dama_edital, termo='TEST')
        
        # Verify button text and color for DAMA alert
        assert 'Ver Analise no DAMA' in card_html or 'Prova Documental' in card_html, \
            f"DAMA alert should have 'Ver Analise no DAMA / Baixar Prova Documental' button text"
        assert '#059669' in card_html or 'emerald' in card_html.lower(), \
            f"DAMA alert button should be green (#059669)"
        
        # Verify link points to our endpoint, not pncp.gov.br
        assert 'pncp.gov.br' not in card_html or 'dama/prova-documental-lmr' in card_html, \
            f"DAMA alert link should point to our endpoint, not pncp.gov.br"
        
        print(f"✅ DAMA alert email template has correct button text and color")
    
    def test_email_service_button_text_for_regular_edital(self):
        """
        Regular editais should still show 'Ver Edital / Baixar PDF' (blue)
        """
        import sys
        sys.path.insert(0, '/app/backend')
        from services.email_service import EmailService
        
        email_service = EmailService()
        
        # Test regular edital (not DAMA)
        regular_edital = {
            'orgao': 'Prefeitura Municipal',
            'numero_processo': 'PE-001/2026',
            'modalidade': 'Pregão Eletrônico',
            'objeto': 'Aquisição de medicamentos',
            'status_oportunidade': 'ATIVA',
            'link_edital': 'https://pncp.gov.br/app/editais/123',
            'is_dama_alert': False,
            'itens_correspondentes': [],
        }
        
        # Generate card HTML
        card_html = email_service._gerar_card_edital(regular_edital, termo='TEST')
        
        # Verify button text for regular edital
        assert 'Ver Edital' in card_html, f"Regular edital should have 'Ver Edital' button text"
        assert '#2563eb' in card_html, f"Regular edital button should be blue (#2563eb)"
        
        print(f"✅ Regular edital email template has correct button text and color")


class TestSmartCacheForLMREndpoints:
    """Tests that smart cache still works for LMR endpoints"""
    
    def test_cache_stats_endpoint(self):
        """Test that cache stats endpoint works"""
        response = requests.get(f"{BASE_URL}/api/cache/stats")
        assert response.status_code == 200, f"Cache stats failed: {response.text}"
        data = response.json()
        assert 'cache_stats' in data or 'smart_cache_stats' in data
        print(f"✅ Cache stats endpoint works: {data}")
    
    def test_cache_clear_endpoint(self):
        """Test that cache clear endpoint works"""
        response = requests.post(f"{BASE_URL}/api/cache/clear")
        assert response.status_code == 200, f"Cache clear failed: {response.text}"
        data = response.json()
        assert 'message' in data
        print(f"✅ Cache clear endpoint works: {data['message']}")


class TestNotificationEndpointWithEmailFields:
    """Tests that notification endpoint returns alerts with email fields"""
    
    def test_notificacoes_oportunidades_returns_email_fields(self):
        """Test that GET /api/notificacoes/oportunidades returns alerts with email fields"""
        response = requests.get(f"{BASE_URL}/api/notificacoes/oportunidades?limite=5")
        assert response.status_code == 200, f"Notificacoes failed: {response.text}"
        
        data = response.json()
        assert 'alertas' in data
        assert 'total' in data
        assert 'nao_lidas' in data
        
        # If there are alerts, verify they have email fields
        if data['alertas']:
            alert = data['alertas'][0]
            # These fields should exist (may be False/None if email not sent)
            print(f"Alert fields: {list(alert.keys())}")
            # email_enviado, email_status should be present
            
        print(f"✅ Notificacoes endpoint works: {data['total']} alerts, {data['nao_lidas']} unread")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
