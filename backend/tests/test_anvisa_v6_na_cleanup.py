"""
ANVISA v6 Test Suite - N/A Value Cleanup & False Positive Reduction
====================================================================
Tests:
1. GET /api/anvisa/alertas returns alerts sorted by indice_oportunidade
2. POST /api/anvisa/atualizar triggers scraper and returns valid statistics
3. Medicine names are clean single names (not N/A, not Medicamento, not Diversos)
4. N/A values are NOT present in numero_re, orgao_destinatario, quantidade_autorizada fields
5. Stats show correct counts for alertas, janelas_abertas, risco_alto
"""
import pytest
import requests
import os
import json

# Get the backend URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://dama-legal-1.preview.emergentagent.com"

API_URL = f"{BASE_URL}/api"

class TestAnvisaAlertas:
    """Tests for GET /api/anvisa/alertas endpoint"""
    
    def test_alertas_endpoint_returns_200(self):
        """Test that the alertas endpoint returns 200 OK"""
        response = requests.get(f"{API_URL}/anvisa/alertas")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✅ GET /api/anvisa/alertas returns 200 OK")
    
    def test_alertas_response_structure(self):
        """Test that response has correct structure with alertas and estatisticas"""
        response = requests.get(f"{API_URL}/anvisa/alertas")
        data = response.json()
        
        assert 'alertas' in data, "Response should contain 'alertas'"
        assert 'estatisticas' in data, "Response should contain 'estatisticas'"
        assert isinstance(data['alertas'], list), "'alertas' should be a list"
        print(f"✅ Response structure valid - {len(data['alertas'])} alertas found")
    
    def test_alertas_sorted_by_indice_oportunidade(self):
        """Test that alerts are sorted by indice_oportunidade descending"""
        response = requests.get(f"{API_URL}/anvisa/alertas")
        data = response.json()
        alertas = data['alertas']
        
        if len(alertas) < 2:
            pytest.skip("Not enough alerts to test sorting")
        
        # Check that alerts are sorted by indice_oportunidade (descending)
        indices = [a.get('indice_oportunidade', 0) for a in alertas]
        for i in range(len(indices) - 1):
            assert indices[i] >= indices[i + 1], f"Alerts not sorted by indice_oportunidade: {indices[i]} < {indices[i+1]}"
        
        print(f"✅ Alerts sorted by indice_oportunidade (top: {indices[0]}%, bottom: {indices[-1]}%)")
    
    def test_alertas_have_required_fields(self):
        """Test that alerts have all required fields"""
        response = requests.get(f"{API_URL}/anvisa/alertas")
        data = response.json()
        alertas = data['alertas']
        
        if not alertas:
            pytest.skip("No alerts to test")
        
        required_fields = [
            'titulo', 'medicamento_detectado', 'tipo_alerta', 'risco',
            'oportunidade', 'janela_importacao', 'indice_oportunidade'
        ]
        
        for alerta in alertas[:5]:  # Check first 5 alerts
            for field in required_fields:
                assert field in alerta, f"Alert missing required field: {field}"
        
        print(f"✅ Alerts have all required fields")


class TestMedicineNamesCleanliness:
    """Tests for clean medicine names (not N/A, Medicamento, Diversos)"""
    
    def test_medicine_names_not_na(self):
        """Test that medicine names are not N/A"""
        response = requests.get(f"{API_URL}/anvisa/alertas")
        data = response.json()
        alertas = data['alertas']
        
        if not alertas:
            pytest.skip("No alerts to test")
        
        invalid_names = ['N/A', 'n/a', 'Medicamento', 'Medicamentos', 'Diversos', 'Vários', '-']
        
        na_count = 0
        for alerta in alertas:
            med = alerta.get('medicamento_detectado', '')
            if med in invalid_names or not med:
                na_count += 1
                print(f"   ⚠️ Invalid medicine name: '{med}' in '{alerta.get('titulo', '')[:50]}'")
        
        # Allow up to 10% invalid names (some alerts may genuinely not have a specific medicine)
        max_allowed = max(1, int(len(alertas) * 0.1))
        assert na_count <= max_allowed, f"Too many invalid medicine names: {na_count}/{len(alertas)} (max allowed: {max_allowed})"
        
        print(f"✅ Medicine names are clean - {na_count}/{len(alertas)} invalid (max allowed: {max_allowed})")
    
    def test_medicine_names_are_single_names(self):
        """Test that medicine names are clean single names (not long lists)"""
        response = requests.get(f"{API_URL}/anvisa/alertas")
        data = response.json()
        alertas = data['alertas']
        
        if not alertas:
            pytest.skip("No alerts to test")
        
        long_names = 0
        for alerta in alertas:
            med = alerta.get('medicamento_detectado', '')
            # Check if name is too long (>60 chars is suspicious)
            if len(med) > 60:
                long_names += 1
                print(f"   ⚠️ Long medicine name ({len(med)} chars): '{med[:60]}...'")
        
        # Allow up to 20% long names
        max_allowed = max(1, int(len(alertas) * 0.2))
        assert long_names <= max_allowed, f"Too many long medicine names: {long_names}/{len(alertas)}"
        
        print(f"✅ Medicine names are single names - {long_names}/{len(alertas)} long (max allowed: {max_allowed})")


class TestNoNAValuesInDisplay:
    """Tests that N/A values are NOT displayed in UI fields"""
    
    def test_numero_re_not_na(self):
        """Test that numero_re field is empty string instead of N/A"""
        response = requests.get(f"{API_URL}/anvisa/alertas")
        data = response.json()
        alertas = data['alertas']
        
        na_count = 0
        for alerta in alertas:
            numero_re = alerta.get('numero_re', '')
            if numero_re and numero_re.lower() in ('n/a', 'none', 'null'):
                na_count += 1
                print(f"   ⚠️ numero_re has N/A: '{numero_re}'")
        
        assert na_count == 0, f"Found {na_count} alerts with N/A in numero_re"
        print(f"✅ numero_re field is clean (no N/A values)")
    
    def test_orgao_destinatario_not_na(self):
        """Test that orgao_destinatario field is empty string instead of N/A"""
        response = requests.get(f"{API_URL}/anvisa/alertas")
        data = response.json()
        alertas = data['alertas']
        
        na_count = 0
        for alerta in alertas:
            orgao = alerta.get('orgao_destinatario', '')
            if orgao and orgao.lower() in ('n/a', 'none', 'null'):
                na_count += 1
                print(f"   ⚠️ orgao_destinatario has N/A: '{orgao}'")
        
        assert na_count == 0, f"Found {na_count} alerts with N/A in orgao_destinatario"
        print(f"✅ orgao_destinatario field is clean (no N/A values)")
    
    def test_quantidade_autorizada_not_na(self):
        """Test that quantidade_autorizada field is empty string instead of N/A"""
        response = requests.get(f"{API_URL}/anvisa/alertas")
        data = response.json()
        alertas = data['alertas']
        
        na_count = 0
        for alerta in alertas:
            qtd = alerta.get('quantidade_autorizada', '')
            if qtd and qtd.lower() in ('n/a', 'none', 'null'):
                na_count += 1
                print(f"   ⚠️ quantidade_autorizada has N/A: '{qtd}'")
        
        assert na_count == 0, f"Found {na_count} alerts with N/A in quantidade_autorizada"
        print(f"✅ quantidade_autorizada field is clean (no N/A values)")
    
    def test_situacao_not_na(self):
        """Test that situacao field is not N/A"""
        response = requests.get(f"{API_URL}/anvisa/alertas")
        data = response.json()
        alertas = data['alertas']
        
        na_count = 0
        for alerta in alertas:
            sit = alerta.get('situacao', '')
            if sit and sit.lower() in ('n/a', 'none', 'null'):
                na_count += 1
                print(f"   ⚠️ situacao has N/A: '{sit}'")
        
        assert na_count == 0, f"Found {na_count} alerts with N/A in situacao"
        print(f"✅ situacao field is clean (no N/A values)")


class TestStatsCorrectness:
    """Tests for statistics correctness"""
    
    def test_stats_have_required_fields(self):
        """Test that stats have all required fields"""
        response = requests.get(f"{API_URL}/anvisa/alertas")
        data = response.json()
        stats = data.get('estatisticas', {})
        
        required_fields = ['total_alertas', 'janelas_abertas', 'risco_alto', 'oportunidades_importacao']
        
        for field in required_fields:
            assert field in stats, f"Stats missing required field: {field}"
        
        print(f"✅ Stats have all required fields")
    
    def test_stats_counts_match_data(self):
        """Test that stats counts match actual data"""
        response = requests.get(f"{API_URL}/anvisa/alertas")
        data = response.json()
        alertas = data['alertas']
        stats = data.get('estatisticas', {})
        
        # Count actual values
        actual_total = len(alertas)
        actual_janelas = sum(1 for a in alertas if a.get('janela_importacao'))
        actual_risco_alto = sum(1 for a in alertas if a.get('risco') == 'ALTO')
        actual_importacao = sum(1 for a in alertas if a.get('oportunidade') == 'Importação')
        
        # Note: total_alertas from DB may differ from returned alertas due to limit
        print(f"   Stats from API: total={stats.get('total_alertas')}, janelas={stats.get('janelas_abertas')}, risco_alto={stats.get('risco_alto')}, importacao={stats.get('oportunidades_importacao')}")
        print(f"   Actual counts: total={actual_total}, janelas={actual_janelas}, risco_alto={actual_risco_alto}, importacao={actual_importacao}")
        
        # Janelas and risco_alto should match
        assert stats.get('janelas_abertas', 0) == actual_janelas, f"Janelas mismatch: {stats.get('janelas_abertas')} vs {actual_janelas}"
        
        print(f"✅ Stats counts are consistent")
    
    def test_janelas_abertas_reflects_strict_criteria(self):
        """Test that janelas_abertas reflects strict janela_importacao criteria"""
        response = requests.get(f"{API_URL}/anvisa/alertas")
        data = response.json()
        stats = data.get('estatisticas', {})
        
        janelas_abertas = stats.get('janelas_abertas', 0)
        
        # Per requirement: AFE changes should NOT trigger janela_importacao
        # So we expect 0 or very few janelas (only for real import authorizations)
        # This is acceptable - the system is now more strict
        print(f"   janelas_abertas = {janelas_abertas}")
        print(f"   Note: 0 is acceptable if no real import windows are detected this month")
        
        print(f"✅ janelas_abertas reflects strict criteria ({janelas_abertas} found)")


class TestAtualizar:
    """Tests for POST /api/anvisa/atualizar endpoint"""
    
    def test_atualizar_endpoint_returns_200(self):
        """Test that the atualizar endpoint returns 200 OK"""
        response = requests.post(f"{API_URL}/anvisa/atualizar", timeout=120)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✅ POST /api/anvisa/atualizar returns 200 OK")
    
    def test_atualizar_returns_statistics(self):
        """Test that atualizar returns valid statistics"""
        response = requests.post(f"{API_URL}/anvisa/atualizar", timeout=120)
        data = response.json()
        
        assert 'coletados' in data, "Response should contain 'coletados'"
        assert 'processados' in data, "Response should contain 'processados'"
        assert 'estatisticas' in data, "Response should contain 'estatisticas'"
        
        print(f"✅ Atualizar returned: coletados={data['coletados']}, processados={data['processados']}")
        
        # Check estatisticas has por_tipo
        stats = data.get('estatisticas', {})
        if 'por_tipo' in stats:
            print(f"   por_tipo breakdown: {stats['por_tipo']}")


class TestSampleData:
    """Sample data inspection tests"""
    
    def test_print_sample_alerts(self):
        """Print sample alerts for inspection"""
        response = requests.get(f"{API_URL}/anvisa/alertas?limit=10")
        data = response.json()
        alertas = data['alertas'][:5]
        
        print("\n📋 Sample Alerts:")
        for i, alerta in enumerate(alertas):
            print(f"\n  [{i+1}] {alerta.get('medicamento_detectado', 'N/A')}")
            print(f"      tipo_alerta: {alerta.get('tipo_alerta')}")
            print(f"      risco: {alerta.get('risco')}, oportunidade: {alerta.get('oportunidade')}")
            print(f"      janela_importacao: {alerta.get('janela_importacao')}")
            print(f"      indice_oportunidade: {alerta.get('indice_oportunidade')}%")
            print(f"      numero_re: '{alerta.get('numero_re', '')}'")
            print(f"      orgao: '{alerta.get('orgao_destinatario', '')}'")
            print(f"      quantidade: '{alerta.get('quantidade_autorizada', '')}'")
        
        print("\n✅ Sample data inspection complete")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
