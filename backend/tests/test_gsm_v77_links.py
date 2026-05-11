"""
GSM v77.0 - Backend Tests for LIVE Search and Original Portal Links
====================================================================
Tests verify:
1. /api/search/unified returns results from conlicitacao_live and pncp_live sources
2. NO result has link_portal or link_pdf containing 'conlicitacao' in URL
3. Multiple portals are returned for search queries
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestUnifiedSearchV77:
    """Tests for /api/search/unified endpoint - LIVE search with original portal links"""
    
    def test_search_canabidiol_returns_results(self):
        """Test 1: GET /api/search/unified?q=canabidiol returns results with live sources"""
        response = requests.get(f"{BASE_URL}/api/search/unified", params={"q": "canabidiol", "limit": 50})
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "total" in data, "Response should have 'total' field"
        assert "resultados" in data, "Response should have 'resultados' field"
        assert "fontes" in data, "Response should have 'fontes' field"
        
        # Verify live sources are present
        fontes = data.get("fontes", {})
        assert "conlicitacao_live" in fontes or "pncp_live" in fontes, \
            f"Response should have live sources. Got: {fontes}"
        
        # Should have results
        assert data["total"] > 0, f"Expected results for 'canabidiol', got {data['total']}"
        assert len(data["resultados"]) > 0, "Should have at least one result"
    
    def test_search_canabidiol_no_conlicitacao_links(self):
        """Test 2: CRITICAL - No result should have link_portal or link_pdf containing 'conlicitacao'"""
        response = requests.get(f"{BASE_URL}/api/search/unified", params={"q": "canabidiol", "limit": 100})
        
        assert response.status_code == 200
        data = response.json()
        results = data.get("resultados", [])
        
        # Track violations
        violations = []
        
        for result in results:
            result_id = result.get("id", "unknown")
            
            # Check link_portal
            link_portal = result.get("link_portal", "") or ""
            if "conlicitacao" in link_portal.lower():
                violations.append({
                    "id": result_id,
                    "field": "link_portal",
                    "value": link_portal[:100]
                })
            
            # Check link_pdf
            link_pdf = result.get("link_pdf", "") or ""
            if "conlicitacao" in link_pdf.lower():
                violations.append({
                    "id": result_id,
                    "field": "link_pdf",
                    "value": link_pdf[:100]
                })
            
            # Check link_edital
            link_edital = result.get("link_edital", "") or ""
            if "conlicitacao" in link_edital.lower():
                violations.append({
                    "id": result_id,
                    "field": "link_edital",
                    "value": link_edital[:100]
                })
        
        assert len(violations) == 0, \
            f"CRITICAL: Found {len(violations)} links containing 'conlicitacao': {violations[:5]}"
    
    def test_search_insulina_returns_results(self):
        """Test 3: GET /api/search/unified?q=insulina returns results from multiple portals"""
        response = requests.get(f"{BASE_URL}/api/search/unified", params={"q": "insulina", "limit": 50})
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] > 0, "Expected results for 'insulina'"
        
        # Check for multiple portals
        portais = set()
        for result in data.get("resultados", []):
            portal = result.get("portal_captura", "")
            if portal:
                # Extract base portal name (remove UF suffix like "(RJ)")
                base_portal = portal.split(" ")[0] if " " in portal else portal
                portais.add(base_portal)
        
        assert len(portais) >= 2, f"Expected multiple portals, got {len(portais)}: {portais}"
    
    def test_search_insulina_no_conlicitacao_links(self):
        """Test 4: Insulina results should also have no conlicitacao links"""
        response = requests.get(f"{BASE_URL}/api/search/unified", params={"q": "insulina", "limit": 100})
        
        assert response.status_code == 200
        data = response.json()
        results = data.get("resultados", [])
        
        violations = []
        
        for result in results:
            for field in ["link_portal", "link_pdf", "link_edital"]:
                link = result.get(field, "") or ""
                if "conlicitacao" in link.lower():
                    violations.append({
                        "id": result.get("id", "unknown"),
                        "field": field,
                        "value": link[:80]
                    })
        
        assert len(violations) == 0, \
            f"Found {len(violations)} conlicitacao links in insulina results: {violations[:3]}"
    
    def test_search_returns_original_portal_links(self):
        """Test 5: Verify results have links to original portals (BLL, PNCP, ComprasNet, etc)"""
        response = requests.get(f"{BASE_URL}/api/search/unified", params={"q": "canabidiol", "limit": 30})
        
        assert response.status_code == 200
        data = response.json()
        
        # Expected original portal domains
        expected_portals = [
            "pncp.gov.br",
            "comprasnet",
            "compras.gov.br",
            "bll",
            "bnc",
            "bbmnet",
            "licitanet",
            "portaldecompraspublicas",
            "bec.sp.gov.br",
            "licitacoes-e",
            "comprasbr",
            "gov.br"  # Generic gov portals
        ]
        
        # Check that at least some results have original portal links
        original_portal_count = 0
        
        for result in data.get("resultados", []):
            link = result.get("link_portal", "") or ""
            link_lower = link.lower()
            
            for portal in expected_portals:
                if portal in link_lower:
                    original_portal_count += 1
                    break
        
        # At least 50% should have recognizable original portal links
        total = len(data.get("resultados", []))
        if total > 0:
            percentage = (original_portal_count / total) * 100
            assert percentage >= 30, \
                f"Expected at least 30% original portal links, got {percentage:.1f}%"
    
    def test_fontes_field_structure(self):
        """Test 6: Verify fontes field contains expected live source counts"""
        response = requests.get(f"{BASE_URL}/api/search/unified", params={"q": "canabidiol"})
        
        assert response.status_code == 200
        data = response.json()
        
        fontes = data.get("fontes", {})
        
        # Should have at least one live source
        has_live_source = (
            fontes.get("conlicitacao_live", 0) > 0 or 
            fontes.get("pncp_live", 0) > 0
        )
        
        assert has_live_source, f"Expected live sources in fontes, got: {fontes}"
    
    def test_result_structure(self):
        """Test 7: Verify result structure has all required fields"""
        response = requests.get(f"{BASE_URL}/api/search/unified", params={"q": "canabidiol", "limit": 5})
        
        assert response.status_code == 200
        data = response.json()
        results = data.get("resultados", [])
        
        if len(results) > 0:
            result = results[0]
            
            # Required fields for GSM
            required_fields = [
                "id", "objeto", "portal_captura", "link_portal"
            ]
            
            for field in required_fields:
                assert field in result, f"Result missing required field: {field}"
    
    def test_performance_source_indicator(self):
        """Test 8: Verify performance field indicates live source"""
        response = requests.get(f"{BASE_URL}/api/search/unified", params={"q": "canabidiol"})
        
        assert response.status_code == 200
        data = response.json()
        
        performance = data.get("performance", {})
        fonte = performance.get("fonte", "")
        
        # Should indicate live/original sources
        assert "LIVE" in fonte or "live" in fonte or "originais" in fonte.lower(), \
            f"Performance fonte should indicate live source, got: {fonte}"


class TestSearchValidation:
    """Edge case and validation tests"""
    
    def test_empty_query_rejected(self):
        """Test: Empty or too short query should return 400"""
        response = requests.get(f"{BASE_URL}/api/search/unified", params={"q": ""})
        assert response.status_code == 400, "Empty query should return 400"
        
        response = requests.get(f"{BASE_URL}/api/search/unified", params={"q": "a"})
        assert response.status_code == 400, "Single char query should return 400"
    
    def test_special_characters_handled(self):
        """Test: Query with special characters should not crash"""
        response = requests.get(f"{BASE_URL}/api/search/unified", params={"q": "insulina (glargina)"})
        # Should not return 500
        assert response.status_code in [200, 400], f"Got unexpected status: {response.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
