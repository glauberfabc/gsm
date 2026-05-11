"""
Test suite for CMED Scraper feature (iteration 26)
Tests the new CMED desabastecimento scraper that collects medicines from ANVISA's 
CMED page: https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/cmed/risco-de-desabastecimento

Tests cover:
- GET /api/anvisa/alertas returns CMED items with fonte='CMED/ANVISA'
- All CMED items have janela_importacao=true
- CMED items include expected medicines (Amicacina, Dopamina, etc.)
- Each CMED item has dose and fase_cmed fields
- Stats show correct janelas_abertas count
- POST /api/anvisa/esclarecimento works with CMED medicines
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://dama-legal-1.preview.emergentagent.com').rstrip('/')

# Expected CMED medicines (from review request)
EXPECTED_CMED_MEDICINES = [
    'SULFATO DE AMICACINA',
    'AMINOFILINA',
    'CLORIDRATO DE DOPAMINA',
    'DIPIRONA',
    'IMUNOGLOBULINA HUMANA',
    'SULFATO DE MAGNÉSIO',
    'FITOMENADIONA',
    'SULFATO DE SALBUTAMOL',
    'OCITOCINA',
    'HEPARINA SÓDICA SUÍNA',
    'HEPARINA SÓDICA BOVINA',
]


class TestCMEDApiEndpoints:
    """Tests for GET /api/anvisa/alertas with CMED items"""
    
    @pytest.fixture
    def alertas_response(self):
        """Fetch alertas once for reuse in multiple tests"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas?limit=100")
        assert response.status_code == 200
        return response.json()
    
    def test_alertas_endpoint_returns_200(self, alertas_response):
        """GET /api/anvisa/alertas returns 200"""
        assert alertas_response is not None
        assert 'alertas' in alertas_response
        print(f"✅ GET /api/anvisa/alertas returns 200")
    
    def test_cmed_items_have_correct_fonte(self, alertas_response):
        """CMED items have fonte='CMED/ANVISA'"""
        alertas = alertas_response.get('alertas', [])
        cmed_items = [a for a in alertas if a.get('fonte') == 'CMED/ANVISA']
        
        assert len(cmed_items) >= 10, f"Expected at least 10 CMED items, got {len(cmed_items)}"
        
        # All CMED items should have fonte='CMED/ANVISA'
        for item in cmed_items:
            assert item.get('fonte') == 'CMED/ANVISA', f"Item {item.get('medicamento_detectado')} has wrong fonte: {item.get('fonte')}"
        
        print(f"✅ Found {len(cmed_items)} CMED items with fonte='CMED/ANVISA'")
    
    def test_cmed_items_have_janela_importacao_true(self, alertas_response):
        """All CMED items must have janela_importacao=true"""
        alertas = alertas_response.get('alertas', [])
        cmed_items = [a for a in alertas if a.get('fonte') == 'CMED/ANVISA']
        
        for item in cmed_items:
            assert item.get('janela_importacao') is True, \
                f"Item {item.get('medicamento_detectado')} should have janela_importacao=true"
        
        print(f"✅ All {len(cmed_items)} CMED items have janela_importacao=true")
    
    def test_cmed_items_have_dose_field(self, alertas_response):
        """Each CMED item has dose field"""
        alertas = alertas_response.get('alertas', [])
        cmed_items = [a for a in alertas if a.get('fonte') == 'CMED/ANVISA']
        
        for item in cmed_items:
            dose = item.get('dose', '')
            assert dose, f"Item {item.get('medicamento_detectado')} is missing dose field"
            print(f"  - {item.get('medicamento_detectado')}: dose='{dose}'")
        
        print(f"✅ All {len(cmed_items)} CMED items have dose field")
    
    def test_cmed_items_have_fase_cmed_field(self, alertas_response):
        """Each CMED item has fase_cmed field (e.g., '1ª FASE')"""
        alertas = alertas_response.get('alertas', [])
        cmed_items = [a for a in alertas if a.get('fonte') == 'CMED/ANVISA']
        
        valid_fases = ['1ª FASE', '2ª FASE', '3ª FASE', '4ª FASE', 'CMED']
        
        for item in cmed_items:
            fase = item.get('fase_cmed', '')
            assert fase, f"Item {item.get('medicamento_detectado')} is missing fase_cmed field"
            assert fase in valid_fases, f"Item {item.get('medicamento_detectado')} has invalid fase_cmed: '{fase}'"
            print(f"  - {item.get('medicamento_detectado')}: fase_cmed='{fase}'")
        
        print(f"✅ All {len(cmed_items)} CMED items have valid fase_cmed field")
    
    def test_expected_cmed_medicines_present(self, alertas_response):
        """Verify expected CMED medicines are present"""
        alertas = alertas_response.get('alertas', [])
        cmed_items = [a for a in alertas if a.get('fonte') == 'CMED/ANVISA']
        
        # Extract medicine names
        found_medicines = set()
        for item in cmed_items:
            med_name = item.get('medicamento_detectado', '').upper()
            found_medicines.add(med_name)
        
        # Check each expected medicine
        found_count = 0
        for expected in EXPECTED_CMED_MEDICINES:
            if expected.upper() in found_medicines:
                found_count += 1
                print(f"  ✓ {expected}")
            else:
                print(f"  ✗ {expected} - NOT FOUND")
        
        # At least 9 out of 11 expected medicines should be present
        assert found_count >= 9, f"Expected at least 9/11 medicines, found {found_count}"
        print(f"✅ Found {found_count}/{len(EXPECTED_CMED_MEDICINES)} expected CMED medicines")


class TestCMEDStats:
    """Tests for statistics related to CMED items"""
    
    def test_stats_janelas_abertas_count(self):
        """Stats should show 11 janelas_abertas (CMED items)"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas")
        assert response.status_code == 200
        
        data = response.json()
        stats = data.get('estatisticas', {})
        
        janelas_abertas = stats.get('janelas_abertas', 0)
        
        # Should have at least 11 janelas abertas (from CMED)
        assert janelas_abertas >= 11, f"Expected at least 11 janelas_abertas, got {janelas_abertas}"
        
        print(f"✅ Stats show {janelas_abertas} janelas_abertas (expected >= 11)")
    
    def test_cmed_count_matches_janelas_abertas(self):
        """CMED item count should match janelas_abertas in stats"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas")
        assert response.status_code == 200
        
        data = response.json()
        alertas = data.get('alertas', [])
        stats = data.get('estatisticas', {})
        
        # Count items with janela_importacao=true
        janela_true_count = len([a for a in alertas if a.get('janela_importacao') is True])
        stats_janelas = stats.get('janelas_abertas', 0)
        
        assert janela_true_count == stats_janelas, \
            f"Mismatch: {janela_true_count} items with janela_importacao=true vs {stats_janelas} in stats"
        
        print(f"✅ {janela_true_count} items with janela_importacao=true matches stats.janelas_abertas")


class TestCMEDEsclarecimento:
    """Tests for esclarecimento generation with CMED medicines"""
    
    def test_esclarecimento_with_cmed_medicine(self):
        """POST /api/anvisa/esclarecimento works with CMED medicine"""
        # Get a CMED item first
        alertas_resp = requests.get(f"{BASE_URL}/api/anvisa/alertas")
        assert alertas_resp.status_code == 200
        
        alertas = alertas_resp.json().get('alertas', [])
        cmed_items = [a for a in alertas if a.get('fonte') == 'CMED/ANVISA']
        
        assert len(cmed_items) > 0, "No CMED items available for testing"
        
        # Use first CMED item
        cmed_item = cmed_items[0]
        
        payload = {
            "medicamento": cmed_item.get('medicamento_detectado', 'SULFATO DE AMICACINA'),
            "principio_ativo": cmed_item.get('principio_ativo', ''),
            "situacao": cmed_item.get('situacao', 'Risco de desabastecimento'),
            "link_prova": cmed_item.get('link', 'https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/cmed/risco-de-desabastecimento'),
            "tipo_alerta": cmed_item.get('tipo_alerta', 'desabastecimento'),
            "empresa_id": "c1"  # HC IMPORTAÇÕES
        }
        
        response = requests.post(f"{BASE_URL}/api/anvisa/esclarecimento", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert 'texto' in data, "Response should contain 'texto' field"
        
        texto = data.get('texto', '')
        assert len(texto) > 500, f"Generated text too short: {len(texto)} chars"
        
        # Text should mention the medicine
        med_name = cmed_item.get('medicamento_detectado', '')
        # Check if medicine name or part of it is in the text (case-insensitive)
        med_found = any(part.lower() in texto.lower() for part in med_name.split()[:2] if len(part) > 3)
        assert med_found, f"Generated text doesn't mention medicine: {med_name[:50]}"
        
        print(f"✅ Esclarecimento generated for CMED medicine: {med_name}")
        print(f"   Text length: {len(texto)} chars")


class TestCMEDItemStructure:
    """Tests for CMED item data structure"""
    
    def test_cmed_item_required_fields(self):
        """Verify CMED items have all required fields"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas")
        assert response.status_code == 200
        
        alertas = response.json().get('alertas', [])
        cmed_items = [a for a in alertas if a.get('fonte') == 'CMED/ANVISA']
        
        required_fields = [
            'titulo',
            'medicamento_detectado',
            'principio_ativo',
            'dose',
            'tipo_alerta',
            'situacao',
            'fonte',
            'link',
            'risco',
            'oportunidade',
            'janela_importacao',
            'motivo_janela',
            'fase_cmed',
            'base_legal',
            'coletado_em',
        ]
        
        for item in cmed_items[:3]:  # Check first 3 items
            missing = []
            for field in required_fields:
                if field not in item or item.get(field) is None:
                    missing.append(field)
            
            assert len(missing) == 0, \
                f"Item {item.get('medicamento_detectado')} missing fields: {missing}"
            
            print(f"  ✓ {item.get('medicamento_detectado')} has all required fields")
        
        print(f"✅ CMED items have all required fields")
    
    def test_cmed_item_risco_is_alto(self):
        """CMED items should have risco='ALTO'"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas")
        assert response.status_code == 200
        
        alertas = response.json().get('alertas', [])
        cmed_items = [a for a in alertas if a.get('fonte') == 'CMED/ANVISA']
        
        for item in cmed_items:
            assert item.get('risco') == 'ALTO', \
                f"Item {item.get('medicamento_detectado')} should have risco='ALTO', got '{item.get('risco')}'"
        
        print(f"✅ All {len(cmed_items)} CMED items have risco='ALTO'")
    
    def test_cmed_item_oportunidade_is_importacao(self):
        """CMED items should have oportunidade='Importação'"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas")
        assert response.status_code == 200
        
        alertas = response.json().get('alertas', [])
        cmed_items = [a for a in alertas if a.get('fonte') == 'CMED/ANVISA']
        
        for item in cmed_items:
            assert item.get('oportunidade') == 'Importação', \
                f"Item {item.get('medicamento_detectado')} should have oportunidade='Importação', got '{item.get('oportunidade')}'"
        
        print(f"✅ All {len(cmed_items)} CMED items have oportunidade='Importação'")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
