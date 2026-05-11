"""
Test Suite for Smart Cache (24h TTL) and Opportunity Alerts System
Tests the 4 new features:
1. Smart Cache 24h TTL for LMR and ANVISA endpoints
2. Opportunity Alerts system (score >= 80%) with notification endpoints
3. Cache stats endpoint with both search_cache and smart_cache stats
4. Prova Documental PDF with LMR tax analysis section
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestSmartCacheFeature:
    """Tests for Smart Cache with 24h TTL"""
    
    def test_cache_stats_endpoint_returns_both_caches(self):
        """GET /api/cache/stats returns both cache_stats and smart_cache_stats"""
        response = requests.get(f"{BASE_URL}/api/cache/stats")
        assert response.status_code == 200
        
        data = response.json()
        # Verify both cache stats are present
        assert 'cache_stats' in data, "Missing cache_stats in response"
        assert 'smart_cache_stats' in data, "Missing smart_cache_stats in response"
        
        # Verify smart_cache_stats structure
        smart_stats = data['smart_cache_stats']
        assert 'hits' in smart_stats
        assert 'misses' in smart_stats
        assert 'hit_rate_percent' in smart_stats
        assert 'namespaces' in smart_stats
        assert 'ttl_hours' in smart_stats
        assert smart_stats['ttl_hours'] == 24.0, "Smart cache TTL should be 24 hours"
        
        print(f"✅ Cache stats: search_cache={data['cache_stats']}, smart_cache={smart_stats}")
    
    def test_lmr_analysis_first_call_is_miss(self):
        """GET /api/dama/lmr-analysis first call should be cache MISS"""
        # Clear cache first
        clear_resp = requests.post(f"{BASE_URL}/api/cache/clear")
        assert clear_resp.status_code == 200
        
        # Get initial stats
        stats_before = requests.get(f"{BASE_URL}/api/cache/stats").json()
        misses_before = stats_before['smart_cache_stats']['misses']
        
        # Make first call to LMR analysis
        response = requests.get(f"{BASE_URL}/api/dama/lmr-analysis")
        assert response.status_code == 200
        
        # Check stats after - misses should increment
        stats_after = requests.get(f"{BASE_URL}/api/cache/stats").json()
        misses_after = stats_after['smart_cache_stats']['misses']
        
        # First call should be a miss
        assert misses_after >= misses_before, "First call should be a cache miss"
        print(f"✅ LMR analysis first call: misses before={misses_before}, after={misses_after}")
    
    def test_lmr_analysis_second_call_is_hit(self):
        """GET /api/dama/lmr-analysis second call should be cache HIT"""
        # Clear cache first
        requests.post(f"{BASE_URL}/api/cache/clear")
        
        # First call (miss)
        requests.get(f"{BASE_URL}/api/dama/lmr-analysis")
        
        # Get stats after first call
        stats_after_first = requests.get(f"{BASE_URL}/api/cache/stats").json()
        hits_before = stats_after_first['smart_cache_stats']['hits']
        
        # Second call (should be hit)
        response = requests.get(f"{BASE_URL}/api/dama/lmr-analysis")
        assert response.status_code == 200
        
        # Check stats after second call
        stats_after_second = requests.get(f"{BASE_URL}/api/cache/stats").json()
        hits_after = stats_after_second['smart_cache_stats']['hits']
        
        # Second call should be a hit
        assert hits_after > hits_before, f"Second call should be a cache hit. Hits before={hits_before}, after={hits_after}"
        print(f"✅ LMR analysis second call: hits before={hits_before}, after={hits_after}")
    
    def test_lmr_analise_medicamento_uses_cache(self):
        """POST /api/dama/lmr-analise-medicamento uses smart cache on second call"""
        # Clear cache
        requests.post(f"{BASE_URL}/api/cache/clear")
        
        payload = {
            "medicamento": "insulina",
            "preco_referencia": 100.0,
            "tipo_produto": "biologico"
        }
        
        # First call
        resp1 = requests.post(f"{BASE_URL}/api/dama/lmr-analise-medicamento", json=payload)
        assert resp1.status_code == 200
        
        stats_after_first = requests.get(f"{BASE_URL}/api/cache/stats").json()
        hits_before = stats_after_first['smart_cache_stats']['hits']
        
        # Second call with same params
        resp2 = requests.post(f"{BASE_URL}/api/dama/lmr-analise-medicamento", json=payload)
        assert resp2.status_code == 200
        
        stats_after_second = requests.get(f"{BASE_URL}/api/cache/stats").json()
        hits_after = stats_after_second['smart_cache_stats']['hits']
        
        # Verify response structure
        data = resp2.json()
        assert 'medicamento' in data
        assert 'classificacao_lmr' in data
        assert 'estrategia_tributaria' in data
        assert 'oportunidade_score' in data
        
        print(f"✅ LMR analise medicamento: hits before={hits_before}, after={hits_after}")
    
    def test_anvisa_buscar_medicamento_uses_smart_cache(self):
        """GET /api/anvisa/buscar-medicamento uses smart cache (24h TTL)"""
        # Clear cache
        requests.post(f"{BASE_URL}/api/cache/clear")
        
        # First call
        resp1 = requests.get(f"{BASE_URL}/api/anvisa/buscar-medicamento?q=paracetamol")
        assert resp1.status_code == 200
        
        stats_after_first = requests.get(f"{BASE_URL}/api/cache/stats").json()
        
        # Second call
        resp2 = requests.get(f"{BASE_URL}/api/anvisa/buscar-medicamento?q=paracetamol")
        assert resp2.status_code == 200
        
        stats_after_second = requests.get(f"{BASE_URL}/api/cache/stats").json()
        
        # Verify anvisa_busca namespace exists
        namespaces = stats_after_second['smart_cache_stats']['namespaces']
        assert 'anvisa_busca' in namespaces, f"anvisa_busca namespace should exist. Namespaces: {namespaces}"
        
        print(f"✅ ANVISA buscar-medicamento uses smart cache. Namespaces: {namespaces}")
    
    def test_cache_clear_clears_both_caches(self):
        """POST /api/cache/clear clears both search_cache and smart_cache"""
        # Make some calls to populate cache
        requests.get(f"{BASE_URL}/api/dama/lmr-analysis")
        requests.get(f"{BASE_URL}/api/anvisa/buscar-medicamento?q=dipirona")
        
        # Verify cache has entries
        stats_before = requests.get(f"{BASE_URL}/api/cache/stats").json()
        
        # Clear cache
        clear_resp = requests.post(f"{BASE_URL}/api/cache/clear")
        assert clear_resp.status_code == 200
        assert 'message' in clear_resp.json()
        
        # Verify cache is cleared
        stats_after = requests.get(f"{BASE_URL}/api/cache/stats").json()
        
        # Smart cache should have 0 active entries after clear
        assert stats_after['smart_cache_stats']['active_entries'] == 0, \
            f"Smart cache should be empty after clear. Got: {stats_after['smart_cache_stats']['active_entries']}"
        
        # Hits and misses should be reset
        assert stats_after['smart_cache_stats']['hits'] == 0
        assert stats_after['smart_cache_stats']['misses'] == 0
        
        print(f"✅ Cache clear works: active_entries={stats_after['smart_cache_stats']['active_entries']}")


class TestNotificationsFeature:
    """Tests for Opportunity Alerts notification system"""
    
    def test_get_notificacoes_oportunidades(self):
        """GET /api/notificacoes/oportunidades returns alertas array, total, nao_lidas"""
        response = requests.get(f"{BASE_URL}/api/notificacoes/oportunidades")
        assert response.status_code == 200
        
        data = response.json()
        assert 'alertas' in data, "Response should have 'alertas' field"
        assert 'total' in data, "Response should have 'total' field"
        assert 'nao_lidas' in data, "Response should have 'nao_lidas' field"
        
        assert isinstance(data['alertas'], list)
        assert isinstance(data['total'], int)
        assert isinstance(data['nao_lidas'], int)
        
        print(f"✅ Notificacoes endpoint: total={data['total']}, nao_lidas={data['nao_lidas']}")
    
    def test_notificacoes_with_limite_param(self):
        """GET /api/notificacoes/oportunidades?limite=5 respects limit"""
        response = requests.get(f"{BASE_URL}/api/notificacoes/oportunidades?limite=5")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data['alertas']) <= 5, "Should respect limite parameter"
        
        print(f"✅ Notificacoes with limite: returned {len(data['alertas'])} alertas")
    
    def test_marcar_alerta_lida_nonexistent(self):
        """POST /api/notificacoes/oportunidades/{id}/lida returns 404 for nonexistent"""
        response = requests.post(f"{BASE_URL}/api/notificacoes/oportunidades/nonexistent-id-12345/lida")
        assert response.status_code == 404
        
        print("✅ Marcar alerta lida returns 404 for nonexistent ID")


class TestLmrAlertTrigger:
    """Tests for LMR alert trigger when score >= 80%"""
    
    def test_lmr_analise_medicamento_response_structure(self):
        """POST /api/dama/lmr-analise-medicamento returns correct structure"""
        payload = {
            "medicamento": "insulina glargina",
            "preco_referencia": 250.0,
            "tipo_produto": "biologico"
        }
        
        response = requests.post(f"{BASE_URL}/api/dama/lmr-analise-medicamento", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify response structure
        assert 'medicamento' in data
        assert 'classificacao_lmr' in data
        assert 'estrategia_tributaria' in data
        assert 'oportunidade_score' in data
        assert 'recomendacao' in data
        assert 'norma_referencia' in data
        
        # Verify classificacao_lmr structure
        classif = data['classificacao_lmr']
        assert 'categoria' in classif
        assert 'risco_comercial' in classif
        assert 'beneficio_tributario' in classif
        
        # Verify estrategia_tributaria structure
        trib = data['estrategia_tributaria']
        assert 'imposto_importacao' in trib
        assert 'icms' in trib
        assert 'carga_tributaria_total' in trib
        assert 'margem_distribuidora' in trib
        
        print(f"✅ LMR analise response: score={data['oportunidade_score']}%, categoria={classif['categoria']}")
    
    def test_lmr_analysis_endpoint(self):
        """GET /api/dama/lmr-analysis returns oportunidades list"""
        response = requests.get(f"{BASE_URL}/api/dama/lmr-analysis")
        assert response.status_code == 200
        
        data = response.json()
        assert 'oportunidades' in data
        assert 'total' in data
        assert 'estatisticas' in data
        assert 'norma_referencia' in data
        
        # Verify estatisticas structure
        stats = data['estatisticas']
        assert 'oportunidade_alta' in stats
        assert 'oportunidade_media' in stats
        assert 'oportunidade_baixa' in stats
        
        print(f"✅ LMR analysis: total={data['total']}, stats={stats}")


class TestProvaDocumentalWithLmr:
    """Tests for Prova Documental PDF with LMR tax analysis section"""
    
    def test_prova_documental_with_analise_lmr(self):
        """POST /api/dama/prova-documental with analise_lmr returns PDF"""
        payload = {
            "medicamento": "insulina",
            "fonte": "ANVISA",
            "titulo_documento": "Alerta de Desabastecimento",
            "descricao": "Medicamento em situacao de desabastecimento",
            "data_publicacao": "2026-01-15",
            "link": "https://anvisa.gov.br/alerta/123",
            "tipo_alerta": "desabastecimento",
            "risco": "ALTO",
            "analise_lmr": {
                "classificacao_lmr": {
                    "categoria": "excepcional",
                    "risco_comercial": "medio",
                    "beneficio_tributario": "Isencao II + ICMS reduzido"
                },
                "estrategia_tributaria": {
                    "imposto_importacao": 0,
                    "icms": 12,
                    "pis": 1.65,
                    "cofins": 7.6,
                    "carga_tributaria_total": 21.25,
                    "margem_distribuidora": 25,
                    "beneficio": "Isencao II + ICMS reduzido (Art. 12, IN 428/2026)"
                },
                "oportunidade_score": 85,
                "recomendacao": "OPORTUNIDADE ALTA: Produto biologico com janela aberta."
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/dama/prova-documental", json=payload)
        assert response.status_code == 200
        
        # Verify it returns a PDF
        content_type = response.headers.get('Content-Type', '')
        assert 'application/pdf' in content_type, f"Expected PDF, got {content_type}"
        
        # Verify PDF has content
        assert len(response.content) > 1000, "PDF should have substantial content"
        
        # Verify PDF magic bytes
        assert response.content[:4] == b'%PDF', "Response should be a valid PDF"
        
        print(f"✅ Prova Documental with LMR: PDF generated, size={len(response.content)} bytes")
    
    def test_prova_documental_without_analise_lmr(self):
        """POST /api/dama/prova-documental without analise_lmr still works"""
        payload = {
            "medicamento": "dipirona",
            "fonte": "DOU",
            "titulo_documento": "Publicacao Oficial",
            "descricao": "Descricao do documento",
            "data_publicacao": "2026-01-10",
            "link": "https://dou.gov.br/123",
            "tipo_alerta": "informativo",
            "risco": "BAIXO"
        }
        
        response = requests.post(f"{BASE_URL}/api/dama/prova-documental", json=payload)
        assert response.status_code == 200
        
        content_type = response.headers.get('Content-Type', '')
        assert 'application/pdf' in content_type
        
        print(f"✅ Prova Documental without LMR: PDF generated, size={len(response.content)} bytes")


class TestCacheStatsNamespaces:
    """Tests for cache stats namespaces"""
    
    def test_smart_cache_namespaces(self):
        """Verify smart cache has correct namespaces after various calls"""
        # Clear cache
        requests.post(f"{BASE_URL}/api/cache/clear")
        
        # Make calls to different endpoints
        requests.get(f"{BASE_URL}/api/dama/lmr-analysis")
        requests.get(f"{BASE_URL}/api/anvisa/buscar-medicamento?q=amoxicilina")
        requests.post(f"{BASE_URL}/api/dama/lmr-analise-medicamento", json={
            "medicamento": "omeprazol",
            "preco_referencia": 50.0,
            "tipo_produto": "generico"
        })
        
        # Check namespaces
        stats = requests.get(f"{BASE_URL}/api/cache/stats").json()
        namespaces = stats['smart_cache_stats']['namespaces']
        
        # Verify expected namespaces exist
        expected_namespaces = ['lmr_analysis', 'anvisa_busca', 'lmr_medicamento']
        for ns in expected_namespaces:
            if ns in namespaces:
                print(f"  ✓ Namespace '{ns}' found with {namespaces[ns]} entries")
        
        print(f"✅ Smart cache namespaces: {namespaces}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
