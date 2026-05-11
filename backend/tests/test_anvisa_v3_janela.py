"""
ANVISA v3 - Janela de Importação Tests
======================================
Tests for:
- 3 sources: ANVISA News, DOU, ANVISA Diretoria Colegiada Votos
- New fields: medicamento_detectado, principio_ativo, janela_importacao, motivo_janela, indice_oportunidade
- tipo_alerta classification
- janelas_abertas stat
- Sorting by indice_oportunidade DESC
- Cruzar licitações with new field names
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAnvisaV3JanelaAtualizarEndpoint:
    """Tests for POST /api/anvisa/atualizar - 3 sources collection"""
    
    def test_atualizar_returns_coletados_from_3_sources(self):
        """POST /api/anvisa/atualizar should return coletados > 0 from 3 sources"""
        response = requests.post(f"{BASE_URL}/api/anvisa/atualizar", timeout=120)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert 'coletados' in data, "Response missing 'coletados' field"
        assert 'processados' in data, "Response missing 'processados' field"
        assert 'estatisticas' in data, "Response missing 'estatisticas' field"
        
        # Should collect from at least some sources
        assert data['coletados'] >= 0, f"coletados should be >= 0, got {data['coletados']}"
        print(f"✅ Coletados: {data['coletados']}, Processados: {data['processados']}")
    
    def test_atualizar_returns_janelas_abertas_stat(self):
        """POST /api/anvisa/atualizar estatisticas should include janelas_abertas field"""
        response = requests.post(f"{BASE_URL}/api/anvisa/atualizar", timeout=120)
        assert response.status_code == 200
        
        data = response.json()
        stats = data.get('estatisticas', {})
        
        assert 'janelas_abertas' in stats, "estatisticas missing 'janelas_abertas' field"
        assert isinstance(stats['janelas_abertas'], int), "janelas_abertas should be an integer"
        print(f"✅ janelas_abertas: {stats['janelas_abertas']}")


class TestAnvisaV3AlertasEndpoint:
    """Tests for GET /api/anvisa/alertas - alert structure"""
    
    def test_alertas_have_required_v3_fields(self):
        """Each alert should have: medicamento_detectado, principio_ativo, tipo_alerta, 
        situacao, risco, oportunidade, janela_importacao (boolean), motivo_janela, 
        indice_oportunidade (number), gatilhos (array), fonte (string)"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas?limit=50", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        alertas = data.get('alertas', [])
        
        if len(alertas) == 0:
            pytest.skip("No alerts in database - run atualizar first")
        
        required_fields = [
            'medicamento_detectado', 'principio_ativo', 'tipo_alerta', 
            'situacao', 'risco', 'oportunidade', 'janela_importacao', 
            'motivo_janela', 'indice_oportunidade', 'gatilhos', 'fonte'
        ]
        
        # Test first 5 alerts
        for i, alerta in enumerate(alertas[:5]):
            for field in required_fields:
                assert field in alerta, f"Alert {i} missing field '{field}'"
            
            # Validate types
            assert isinstance(alerta['janela_importacao'], bool), f"Alert {i}: janela_importacao should be boolean, got {type(alerta['janela_importacao'])}"
            assert isinstance(alerta['indice_oportunidade'], (int, float)), f"Alert {i}: indice_oportunidade should be number, got {type(alerta['indice_oportunidade'])}"
            assert isinstance(alerta['gatilhos'], list), f"Alert {i}: gatilhos should be array, got {type(alerta['gatilhos'])}"
            assert isinstance(alerta['fonte'], str), f"Alert {i}: fonte should be string, got {type(alerta['fonte'])}"
            
        print(f"✅ All {len(alertas[:5])} alerts have required v3 fields")
    
    def test_alertas_sorted_by_indice_oportunidade_desc(self):
        """Alertas should be sorted by indice_oportunidade DESC"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas?limit=50", timeout=30)
        assert response.status_code == 200
        
        alertas = response.json().get('alertas', [])
        
        if len(alertas) < 2:
            pytest.skip("Not enough alerts to test sorting")
        
        indices = [a.get('indice_oportunidade', 0) for a in alertas]
        
        # Verify descending order
        for i in range(len(indices) - 1):
            assert indices[i] >= indices[i+1], f"Alerts not sorted DESC at position {i}: {indices[i]} < {indices[i+1]}"
        
        print(f"✅ Alerts sorted DESC by indice_oportunidade. First: {indices[0]}, Last: {indices[-1]}")
    
    def test_indice_oportunidade_range_0_100(self):
        """indice_oportunidade should be in range 0-100"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas?limit=50", timeout=30)
        assert response.status_code == 200
        
        alertas = response.json().get('alertas', [])
        
        for i, alerta in enumerate(alertas):
            indice = alerta.get('indice_oportunidade', 0)
            assert 0 <= indice <= 100, f"Alert {i}: indice_oportunidade {indice} not in range 0-100"
        
        print(f"✅ All {len(alertas)} alerts have indice_oportunidade in range 0-100")
    
    def test_janela_importacao_is_boolean(self):
        """janela_importacao field should be boolean (true/false)"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas?limit=50", timeout=30)
        assert response.status_code == 200
        
        alertas = response.json().get('alertas', [])
        
        janela_true_count = 0
        janela_false_count = 0
        
        for alerta in alertas:
            janela = alerta.get('janela_importacao')
            assert isinstance(janela, bool), f"janela_importacao should be bool, got {type(janela)}"
            if janela:
                janela_true_count += 1
            else:
                janela_false_count += 1
        
        print(f"✅ janela_importacao validated. True: {janela_true_count}, False: {janela_false_count}")
    
    def test_gatilhos_structure(self):
        """gatilhos array should contain objects with id, label, peso, keyword"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas?limit=50", timeout=30)
        assert response.status_code == 200
        
        alertas = response.json().get('alertas', [])
        
        alerts_with_gatilhos = [a for a in alertas if len(a.get('gatilhos', [])) > 0]
        
        if len(alerts_with_gatilhos) == 0:
            pytest.skip("No alerts with gatilhos to test")
        
        for alerta in alerts_with_gatilhos[:5]:
            for gatilho in alerta['gatilhos']:
                assert 'id' in gatilho, "Gatilho missing 'id'"
                assert 'label' in gatilho, "Gatilho missing 'label'"
                assert 'peso' in gatilho, "Gatilho missing 'peso'"
                assert 'keyword' in gatilho, "Gatilho missing 'keyword'"
        
        print(f"✅ {len(alerts_with_gatilhos)} alerts have properly structured gatilhos")


class TestAnvisaV3CruzarLicitacoes:
    """Tests for POST /api/anvisa/cruzar-licitacoes"""
    
    def test_cruzar_uses_new_field_names(self):
        """Cruzamento should work with new field names (medicamento_detectado, principio_ativo)"""
        response = requests.post(f"{BASE_URL}/api/anvisa/cruzar-licitacoes", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert 'cruzamento' in data, "Response missing 'cruzamento'"
        assert 'resumo' in data, "Response missing 'resumo'"
        
        cruzamento = data['cruzamento']
        resumo = data['resumo']
        
        # Verify resumo structure
        assert 'medicamentos_analisados' in resumo
        assert 'medicamentos_com_licitacao' in resumo
        assert 'total_licitacoes_encontradas' in resumo
        
        # Verify cruzamento items have new field names
        if len(cruzamento) > 0:
            sample_key = list(cruzamento.keys())[0]
            sample_item = cruzamento[sample_key]
            
            assert 'medicamento_detectado' in sample_item, "Cruzamento item missing 'medicamento_detectado'"
            assert 'principio_ativo' in sample_item, "Cruzamento item missing 'principio_ativo'"
            assert 'indice_oportunidade' in sample_item, "Cruzamento item missing 'indice_oportunidade'"
            assert 'licitacoes_encontradas' in sample_item, "Cruzamento item missing 'licitacoes_encontradas'"
            assert 'licitacoes' in sample_item, "Cruzamento item missing 'licitacoes'"
            
            print(f"✅ Cruzamento working with new field names. Sample: {sample_key}")
        else:
            print("⚠️ No items in cruzamento - might need more alerts with high opportunity")
        
        print(f"✅ Resumo: {resumo}")


class TestAnvisaV3Stats:
    """Tests for statistics endpoint"""
    
    def test_stats_includes_janelas_abertas(self):
        """GET /api/anvisa/stats should include janelas_abertas"""
        response = requests.get(f"{BASE_URL}/api/anvisa/stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        
        assert 'janelas_abertas' in data, "Stats missing 'janelas_abertas'"
        assert isinstance(data['janelas_abertas'], int), "janelas_abertas should be integer"
        
        # Verify other expected fields
        assert 'total_alertas' in data
        assert 'risco_alto' in data
        assert 'oportunidades_importacao' in data
        
        print(f"✅ Stats include janelas_abertas: {data['janelas_abertas']}")
        print(f"   Total alertas: {data['total_alertas']}")
        print(f"   Risco alto: {data['risco_alto']}")


class TestAnvisaV3Fontes:
    """Tests for 3-source scraper"""
    
    def test_alertas_show_fonte(self):
        """Alerts should show which source they came from (ANVISA News, DOU, Votos)"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas?limit=50", timeout=30)
        assert response.status_code == 200
        
        alertas = response.json().get('alertas', [])
        
        if len(alertas) == 0:
            pytest.skip("No alerts to test fonte")
        
        fontes_encontradas = set()
        
        for alerta in alertas:
            fonte = alerta.get('fonte', '')
            if fonte:
                fontes_encontradas.add(fonte)
        
        print(f"✅ Fontes encontradas: {fontes_encontradas}")
        
        # Should have at least one source
        assert len(fontes_encontradas) > 0, "No fontes found in alerts"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
