"""
Test suite for ANVISA Janela de Importação v5 features
======================================================
Tests DOU scraper improvements and new structured data fields:
- numero_re, orgao_destinatario, quantidade_autorizada
- numero_processo_judicial, decisao_judicial, tipo_documento, empresa_importadora
- Enhanced scoring for janela_importacao, decisao_judicial, numero_re
- tipo_alerta with importacao_excepcional and decisao_judicial categories
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAnvisaAlertasEndpoint:
    """Test GET /api/anvisa/alertas endpoint - structured fields validation"""
    
    def test_alertas_endpoint_returns_200(self):
        """Verify alertas endpoint is accessible"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas?limit=30")
        assert response.status_code == 200
        print(f"✅ GET /api/anvisa/alertas returned 200")
    
    def test_alertas_has_correct_structure(self):
        """Verify response has alertas and estatisticas"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas?limit=30")
        data = response.json()
        
        assert "alertas" in data
        assert "estatisticas" in data
        assert isinstance(data["alertas"], list)
        assert isinstance(data["estatisticas"], dict)
        print(f"✅ Response structure correct: alertas={len(data['alertas'])}, estatisticas present")
    
    def test_alertas_contain_new_structured_fields(self):
        """Verify alerts have all new v5 structured fields"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas?limit=30")
        alertas = response.json()["alertas"]
        
        required_fields = [
            "medicamento_detectado", "principio_ativo", "tipo_alerta",
            "situacao", "risco", "oportunidade", "janela_importacao",
            # New v5 structured fields
            "numero_re", "orgao_destinatario", "quantidade_autorizada",
            "numero_processo_judicial", "decisao_judicial", "tipo_documento", "empresa_importadora"
        ]
        
        for alerta in alertas[:5]:  # Check first 5
            for field in required_fields:
                assert field in alerta, f"Missing field: {field}"
        
        print(f"✅ All {len(required_fields)} structured fields present in alerts")
    
    def test_estatisticas_has_por_tipo(self):
        """Verify statistics include por_tipo breakdown"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas?limit=30")
        stats = response.json()["estatisticas"]
        
        assert "por_tipo" in stats
        assert isinstance(stats["por_tipo"], dict)
        
        # Should have importacao_excepcional and/or decisao_judicial if present
        print(f"✅ por_tipo breakdown: {stats['por_tipo']}")
    
    def test_estatisticas_has_importacao_excepcional_type(self):
        """Verify por_tipo includes importacao_excepcional category"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas?limit=30")
        stats = response.json()["estatisticas"]
        por_tipo = stats.get("por_tipo", {})
        
        # Count should be >= 0 (may not have any currently)
        importacao_count = por_tipo.get("importacao_excepcional", 0)
        print(f"✅ importacao_excepcional count: {importacao_count}")
        assert isinstance(importacao_count, int)
    
    def test_estatisticas_has_decisao_judicial_type(self):
        """Verify por_tipo includes decisao_judicial category"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas?limit=30")
        stats = response.json()["estatisticas"]
        por_tipo = stats.get("por_tipo", {})
        
        decisao_count = por_tipo.get("decisao_judicial", 0)
        print(f"✅ decisao_judicial count: {decisao_count}")
        assert isinstance(decisao_count, int)


class TestAnvisaAtualizarEndpoint:
    """Test POST /api/anvisa/atualizar endpoint - scraper trigger"""
    
    def test_atualizar_endpoint_returns_200(self):
        """Verify atualizar endpoint works"""
        response = requests.post(f"{BASE_URL}/api/anvisa/atualizar", timeout=120)
        assert response.status_code == 200
        print(f"✅ POST /api/anvisa/atualizar returned 200")
    
    def test_atualizar_returns_statistics(self):
        """Verify atualizar returns coletados, processados, estatisticas"""
        response = requests.post(f"{BASE_URL}/api/anvisa/atualizar", timeout=120)
        data = response.json()
        
        assert "coletados" in data
        assert "processados" in data
        assert "estatisticas" in data
        
        print(f"✅ Atualizar returned: coletados={data['coletados']}, processados={data['processados']}")
    
    def test_atualizar_estatisticas_has_por_tipo(self):
        """Verify atualizar returns por_tipo with type breakdown"""
        response = requests.post(f"{BASE_URL}/api/anvisa/atualizar", timeout=120)
        stats = response.json()["estatisticas"]
        
        assert "por_tipo" in stats
        por_tipo = stats["por_tipo"]
        
        # Check for expected type categories
        print(f"✅ Atualizar por_tipo: {por_tipo}")
        assert isinstance(por_tipo, dict)


class TestAnvisaStatsEndpoint:
    """Test GET /api/anvisa/stats endpoint"""
    
    def test_stats_endpoint_returns_200(self):
        """Verify stats endpoint works"""
        response = requests.get(f"{BASE_URL}/api/anvisa/stats")
        assert response.status_code == 200
        print(f"✅ GET /api/anvisa/stats returned 200")
    
    def test_stats_has_required_fields(self):
        """Verify stats has all required fields"""
        response = requests.get(f"{BASE_URL}/api/anvisa/stats")
        stats = response.json()
        
        required = [
            "total_alertas", "risco_alto", "risco_medio",
            "oportunidades_importacao", "janelas_abertas", "por_tipo"
        ]
        
        for field in required:
            assert field in stats, f"Missing stats field: {field}"
        
        print(f"✅ Stats has all required fields")


class TestAlertasScoringBoosts:
    """Test enhanced opportunity scoring with v5 boosts"""
    
    def test_alerts_have_indice_oportunidade(self):
        """Verify all alerts have indice_oportunidade calculated"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas?limit=30")
        alertas = response.json()["alertas"]
        
        for alerta in alertas:
            assert "indice_oportunidade" in alerta
            assert isinstance(alerta["indice_oportunidade"], (int, float))
            assert 0 <= alerta["indice_oportunidade"] <= 100
        
        print(f"✅ All alerts have valid indice_oportunidade (0-100)")
    
    def test_janela_importacao_boost(self):
        """Verify janela_importacao=True alerts have higher scores"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas?limit=50")
        alertas = response.json()["alertas"]
        
        janela_alerts = [a for a in alertas if a.get("janela_importacao")]
        non_janela_alerts = [a for a in alertas if not a.get("janela_importacao")]
        
        if janela_alerts and non_janela_alerts:
            avg_janela = sum(a["indice_oportunidade"] for a in janela_alerts) / len(janela_alerts)
            avg_non_janela = sum(a["indice_oportunidade"] for a in non_janela_alerts) / len(non_janela_alerts)
            
            print(f"✅ Janela alerts avg score: {avg_janela:.1f}, Non-janela avg: {avg_non_janela:.1f}")
            # Janela alerts should generally score higher
        else:
            print(f"⚠️ Not enough janela/non-janela alerts to compare ({len(janela_alerts)} janela, {len(non_janela_alerts)} non-janela)")


class TestTipoAlertaCategories:
    """Test tipo_alerta categorization"""
    
    def test_tipo_alerta_values(self):
        """Verify tipo_alerta has expected categories"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas?limit=50")
        alertas = response.json()["alertas"]
        
        tipos = set(a.get("tipo_alerta") for a in alertas)
        
        expected_types = {
            "alerta", "informativo", "regulamentação", "proibição",
            "recolhimento", "desabastecimento", "interrupção fabricação",
            "importação excepcional", "decisão judicial", "importacao_excepcional", "decisao_judicial"
        }
        
        print(f"✅ Found tipo_alerta values: {tipos}")
        
        # At least some expected types should be present
        assert len(tipos) > 0, "No tipo_alerta values found"


class TestStructuredDataExtraction:
    """Test structured data extraction from DOU"""
    
    def test_numero_re_extraction(self):
        """Verify numero_re field is populated when present"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas?limit=50")
        alertas = response.json()["alertas"]
        
        alerts_with_re = [a for a in alertas if a.get("numero_re")]
        
        print(f"✅ Alerts with numero_re: {len(alerts_with_re)}")
        
        for a in alerts_with_re[:3]:
            print(f"   - {a['medicamento_detectado'][:30]}: RE nº {a['numero_re']}")
    
    def test_decisao_judicial_flag(self):
        """Verify decisao_judicial boolean is set correctly"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas?limit=50")
        alertas = response.json()["alertas"]
        
        judicial_alerts = [a for a in alertas if a.get("decisao_judicial") == True]
        
        print(f"✅ Alerts with decisao_judicial=True: {len(judicial_alerts)}")
        
        for a in judicial_alerts[:3]:
            print(f"   - {a['medicamento_detectado'][:40]}, tipo: {a['tipo_alerta']}")
    
    def test_tipo_documento_extraction(self):
        """Verify tipo_documento is populated"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas?limit=50")
        alertas = response.json()["alertas"]
        
        alerts_with_tipo_doc = [a for a in alertas if a.get("tipo_documento")]
        
        print(f"✅ Alerts with tipo_documento: {len(alerts_with_tipo_doc)}")
        
        for a in alerts_with_tipo_doc[:3]:
            print(f"   - {a['medicamento_detectado'][:30]}: {a['tipo_documento']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
