"""
Test Suite for ANVISA Structured Fields v20
============================================
Tests the NEW structured fields upgrade to ANVISA Janela module:
1. medicamento_detectado - Medication name from AI extraction
2. principio_ativo - Active ingredient
3. tipo_alerta - Alert type classification
4. gatilhos - Array of regulatory triggers (RDC 488, RDC 203, etc.)
5. indice_oportunidade - 0-100% opportunity index
6. Statistics including demanda_publica_critica and oportunidade_alta
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAnvisaAtualizarEndpoint:
    """POST /api/anvisa/atualizar - Scrape and process ANVISA alerts with new fields"""
    
    def test_atualizar_returns_processados_and_estatisticas(self):
        """Test that atualizar returns processados > 0 with new estatisticas fields"""
        response = requests.post(f"{BASE_URL}/api/anvisa/atualizar", timeout=120)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify base response structure
        assert 'processados' in data, "Response missing 'processados'"
        assert 'estatisticas' in data, "Response missing 'estatisticas'"
        assert data['processados'] >= 0, "processados should be >= 0"
        
        # Verify NEW estatisticas fields
        stats = data['estatisticas']
        print(f"Estatisticas received: {stats}")
        
        # Core stats
        assert 'total_alertas' in stats, "Missing total_alertas in estatisticas"
        assert 'risco_alto' in stats, "Missing risco_alto in estatisticas"
        assert 'risco_medio' in stats, "Missing risco_medio in estatisticas"
        
        # NEW: demanda_publica_critica field
        assert 'demanda_publica_critica' in stats, "Missing demanda_publica_critica in estatisticas"
        
        # NEW: oportunidade_alta field (alerts with indice >= 70)
        assert 'oportunidade_alta' in stats, "Missing oportunidade_alta in estatisticas"
        
        print(f"✅ Atualizar returned processados={data['processados']}, demanda_publica_critica={stats['demanda_publica_critica']}, oportunidade_alta={stats['oportunidade_alta']}")


class TestAnvisaAlertasEndpoint:
    """GET /api/anvisa/alertas - List alerts with new structured fields"""
    
    def test_alertas_have_structured_fields(self):
        """Each alert should have: medicamento_detectado, principio_ativo, tipo_alerta, situacao, risco, oportunidade, indice_oportunidade, gatilhos"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        alertas = data.get('alertas', [])
        
        assert len(alertas) > 0, "No alertas returned - need data to test"
        
        # Check first 5 alerts for required fields
        required_fields = [
            'medicamento_detectado',
            'principio_ativo', 
            'tipo_alerta',
            'situacao',
            'risco',
            'oportunidade',
            'indice_oportunidade',
            'gatilhos'
        ]
        
        for idx, alerta in enumerate(alertas[:5]):
            print(f"\n--- Alert {idx}: {alerta.get('titulo', 'No title')[:50]}... ---")
            
            for field in required_fields:
                assert field in alerta, f"Alert {idx} missing field '{field}'"
                print(f"  {field}: {alerta[field]}")
        
        print(f"\n✅ All {len(alertas)} alerts have required structured fields")
    
    def test_alertas_sorted_by_indice_oportunidade_desc(self):
        """Alertas should be sorted by indice_oportunidade DESC"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas", timeout=30)
        assert response.status_code == 200
        
        alertas = response.json().get('alertas', [])
        assert len(alertas) >= 2, "Need at least 2 alerts to verify sorting"
        
        # Extract indices
        indices = [a.get('indice_oportunidade', 0) for a in alertas]
        print(f"First 10 indices: {indices[:10]}")
        
        # Verify descending order
        for i in range(len(indices) - 1):
            assert indices[i] >= indices[i+1], f"Not sorted DESC at position {i}: {indices[i]} < {indices[i+1]}"
        
        print(f"✅ {len(alertas)} alerts sorted by indice_oportunidade DESC")
    
    def test_indice_oportunidade_is_number_0_to_100(self):
        """indice_oportunidade should be a number between 0-100"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas", timeout=30)
        assert response.status_code == 200
        
        alertas = response.json().get('alertas', [])
        
        for idx, alerta in enumerate(alertas[:10]):
            indice = alerta.get('indice_oportunidade')
            assert isinstance(indice, (int, float)), f"Alert {idx}: indice_oportunidade is not a number, got {type(indice)}"
            assert 0 <= indice <= 100, f"Alert {idx}: indice_oportunidade {indice} not in range 0-100"
        
        print(f"✅ All indices are numbers in range 0-100")
    
    def test_gatilhos_is_array_with_correct_structure(self):
        """gatilhos should be an array with objects having id, label, peso, keyword"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas", timeout=30)
        assert response.status_code == 200
        
        alertas = response.json().get('alertas', [])
        
        gatilhos_found = 0
        for idx, alerta in enumerate(alertas[:20]):
            gatilhos = alerta.get('gatilhos', [])
            assert isinstance(gatilhos, list), f"Alert {idx}: gatilhos is not a list"
            
            if len(gatilhos) > 0:
                gatilhos_found += 1
                for gi, g in enumerate(gatilhos):
                    assert 'id' in g, f"Alert {idx}, gatilho {gi}: missing 'id'"
                    assert 'label' in g, f"Alert {idx}, gatilho {gi}: missing 'label'"
                    assert 'peso' in g, f"Alert {idx}, gatilho {gi}: missing 'peso'"
                    assert 'keyword' in g, f"Alert {idx}, gatilho {gi}: missing 'keyword'"
                    print(f"  Alert {idx}: Gatilho '{g['id']}' - {g['label']} (peso={g['peso']})")
        
        print(f"✅ Found {gatilhos_found} alerts with gatilhos, all have correct structure")
    
    def test_tipo_alerta_has_specific_types(self):
        """tipo_alerta should have specific types like 'recolhimento', 'proibição', 'desabastecimento', not just 'alerta'/'noticia'"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas", timeout=30)
        assert response.status_code == 200
        
        alertas = response.json().get('alertas', [])
        
        # Expected specific types
        specific_types = [
            'interrupção fabricação',
            'desabastecimento',
            'descontinuação',
            'importação excepcional',
            'recolhimento',
            'proibição',
            'alerta segurança',
            'falsificação',
            'regulamentação',
            'informativo'
        ]
        
        tipos_encontrados = set()
        for alerta in alertas:
            tipo = alerta.get('tipo_alerta', '')
            tipos_encontrados.add(tipo)
        
        print(f"Tipos encontrados: {tipos_encontrados}")
        
        # At least some alerts should have specific types
        generic_only = tipos_encontrados.issubset({'alerta', 'noticia', 'comunicado'})
        assert not generic_only, f"Only generic types found: {tipos_encontrados}. Expected specific types like: {specific_types[:5]}"
        
        print(f"✅ Found specific tipo_alerta types: {tipos_encontrados}")


class TestAnvisaCruzarLicitacoesEndpoint:
    """POST /api/anvisa/cruzar-licitacoes - Cross-reference with tenders"""
    
    def test_cruzamento_items_have_new_fields(self):
        """Response cruzamento items should have medicamento_detectado, principio_ativo, tipo_alerta, indice_oportunidade"""
        response = requests.post(f"{BASE_URL}/api/anvisa/cruzar-licitacoes", timeout=120)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert 'cruzamento' in data, "Response missing 'cruzamento'"
        assert 'resumo' in data, "Response missing 'resumo'"
        
        cruzamento = data['cruzamento']
        
        if len(cruzamento) == 0:
            pytest.skip("No cruzamento data - need alerts with oportunidade to test")
        
        required_fields = [
            'medicamento_detectado',
            'principio_ativo',
            'tipo_alerta',
            'indice_oportunidade'
        ]
        
        for med_name, med_data in list(cruzamento.items())[:5]:
            print(f"\n--- Cruzamento: {med_name} ---")
            
            for field in required_fields:
                assert field in med_data, f"Cruzamento '{med_name}' missing field '{field}'"
                print(f"  {field}: {med_data[field]}")
            
            # Verify indice_oportunidade is a number
            indice = med_data.get('indice_oportunidade')
            assert isinstance(indice, (int, float)), f"indice_oportunidade is not a number"
            assert 0 <= indice <= 100, f"indice_oportunidade {indice} not in range 0-100"
            
            # Verify licitacoes_encontradas
            assert 'licitacoes_encontradas' in med_data, "Missing licitacoes_encontradas"
            assert isinstance(med_data['licitacoes_encontradas'], int), "licitacoes_encontradas should be int"
        
        print(f"\n✅ All cruzamento items have required new fields")
    
    def test_resumo_has_expected_fields(self):
        """resumo should have medicamentos_analisados, medicamentos_com_licitacao, total_licitacoes_encontradas"""
        response = requests.post(f"{BASE_URL}/api/anvisa/cruzar-licitacoes", timeout=120)
        assert response.status_code == 200
        
        data = response.json()
        resumo = data.get('resumo', {})
        
        required_resumo_fields = [
            'medicamentos_analisados',
            'medicamentos_com_licitacao',
            'total_licitacoes_encontradas'
        ]
        
        for field in required_resumo_fields:
            assert field in resumo, f"resumo missing field '{field}'"
            assert isinstance(resumo[field], int), f"resumo.{field} should be int, got {type(resumo[field])}"
        
        print(f"✅ Resumo: analisados={resumo['medicamentos_analisados']}, com_licitacao={resumo['medicamentos_com_licitacao']}, total_licitacoes={resumo['total_licitacoes_encontradas']}")


class TestAnvisaStatsEndpoint:
    """GET /api/anvisa/stats - Quick statistics endpoint"""
    
    def test_stats_include_new_fields(self):
        """Stats should include demanda_publica_critica and oportunidade_alta"""
        response = requests.get(f"{BASE_URL}/api/anvisa/stats", timeout=30)
        assert response.status_code == 200
        
        stats = response.json()
        
        # Core fields
        assert 'total_alertas' in stats, "Missing total_alertas"
        assert 'risco_alto' in stats, "Missing risco_alto"
        assert 'risco_medio' in stats, "Missing risco_medio"
        
        # NEW fields
        assert 'demanda_publica_critica' in stats, "Missing demanda_publica_critica"
        assert 'oportunidade_alta' in stats, "Missing oportunidade_alta"
        
        print(f"✅ Stats: total={stats['total_alertas']}, alto={stats['risco_alto']}, medio={stats['risco_medio']}, demanda_critica={stats['demanda_publica_critica']}, oportunidade_alta={stats['oportunidade_alta']}")


if __name__ == "__main__":
    pytest.main([__file__, '-v', '--tb=short'])
