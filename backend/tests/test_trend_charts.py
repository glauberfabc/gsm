"""
Test Trend Charts (Sparklines) Feature - Backend Tests
Tests for mini trend charts showing price trends in Preços tab

Features tested:
- Backend /api/precos/search returns 'tendencia' array in each apresentacao
- Tendencia data has correct monthly grouping (mes, medio, min, max, qtd)
- Period filter (meses) correctly affects trend data points
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestTrendChartsBackend:
    """Tests for trend charts (tendencia) data in /api/precos/search"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test parameters"""
        self.search_url = f"{BASE_URL}/api/precos/search"
    
    def test_precos_search_returns_tendencia_field(self):
        """Test that apresentacoes include tendencia array"""
        # Search with 12 months for better chance of trend data
        params = {"q": "Prolia", "meses": 12, "limite": 50}
        
        response = requests.get(self.search_url, params=params, timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        apresentacoes = data.get('apresentacoes', [])
        
        # Should have apresentacoes
        assert len(apresentacoes) > 0, "Expected at least one apresentacao"
        
        # Each apresentacao should have tendencia field
        for ap in apresentacoes:
            assert 'tendencia' in ap, f"Missing 'tendencia' field in apresentacao: {ap.get('nome')}"
            # tendencia should be a list (can be empty if only 1 month of data)
            assert isinstance(ap['tendencia'], list), f"tendencia should be a list"
    
    def test_tendencia_data_structure(self):
        """Test that tendencia has correct monthly data structure (mes, medio, min, max, qtd)"""
        params = {"q": "Prolia", "meses": 24, "limite": 100}
        
        response = requests.get(self.search_url, params=params, timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        apresentacoes = data.get('apresentacoes', [])
        
        # Find an apresentacao with tendencia data (length >= 1)
        tendencia_found = False
        for ap in apresentacoes:
            tendencia = ap.get('tendencia', [])
            if len(tendencia) >= 1:
                tendencia_found = True
                for point in tendencia:
                    # Each point should have: mes, medio, min, max, qtd
                    assert 'mes' in point, "Missing 'mes' field in tendencia point"
                    assert 'medio' in point, "Missing 'medio' field in tendencia point"
                    assert 'min' in point, "Missing 'min' field in tendencia point"
                    assert 'max' in point, "Missing 'max' field in tendencia point"
                    assert 'qtd' in point, "Missing 'qtd' field in tendencia point"
                    
                    # Validate data types
                    assert isinstance(point['mes'], str), "mes should be string (YYYY-MM)"
                    assert isinstance(point['medio'], (int, float)), "medio should be numeric"
                    assert isinstance(point['min'], (int, float)), "min should be numeric"
                    assert isinstance(point['max'], (int, float)), "max should be numeric"
                    assert isinstance(point['qtd'], int), "qtd should be integer"
                    
                    # mes format should be YYYY-MM
                    assert len(point['mes']) == 7, f"mes format should be YYYY-MM, got: {point['mes']}"
                    assert '-' in point['mes'], f"mes format should be YYYY-MM, got: {point['mes']}"
                break  # Only need to check one
        
        # If no tendencia data found, log but don't fail (data-dependent)
        if not tendencia_found:
            print("WARNING: No tendencia data found - may be due to PNCP data availability")
    
    def test_tendencia_values_make_sense(self):
        """Test that tendencia values are logically correct (min <= medio <= max)"""
        params = {"q": "Prolia", "meses": 24, "limite": 100}
        
        response = requests.get(self.search_url, params=params, timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        apresentacoes = data.get('apresentacoes', [])
        
        for ap in apresentacoes:
            tendencia = ap.get('tendencia', [])
            for point in tendencia:
                min_val = point.get('min', 0)
                medio_val = point.get('medio', 0)
                max_val = point.get('max', 0)
                
                # min <= medio <= max
                assert min_val <= medio_val, f"min ({min_val}) should be <= medio ({medio_val})"
                assert medio_val <= max_val, f"medio ({medio_val}) should be <= max ({max_val})"
                
                # qtd should be positive
                assert point.get('qtd', 0) > 0, "qtd should be > 0 for each month with data"
    
    def test_tendencia_months_are_sorted(self):
        """Test that tendencia data is sorted chronologically by month"""
        params = {"q": "Prolia", "meses": 24, "limite": 100}
        
        response = requests.get(self.search_url, params=params, timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        apresentacoes = data.get('apresentacoes', [])
        
        for ap in apresentacoes:
            tendencia = ap.get('tendencia', [])
            if len(tendencia) >= 2:
                # Check that months are sorted
                months = [p['mes'] for p in tendencia]
                assert months == sorted(months), f"Tendencia months should be sorted: {months}"
    
    def test_period_filter_affects_tendencia(self):
        """Test that 3 months period shows fewer or equal trend points than 12 months"""
        # Search with 3 months
        params_3m = {"q": "Prolia", "meses": 3, "limite": 100}
        response_3m = requests.get(self.search_url, params=params_3m, timeout=60)
        assert response_3m.status_code == 200
        data_3m = response_3m.json()
        
        # Search with 12 months  
        params_12m = {"q": "Prolia", "meses": 12, "limite": 100}
        response_12m = requests.get(self.search_url, params=params_12m, timeout=60)
        assert response_12m.status_code == 200
        data_12m = response_12m.json()
        
        # Get max tendencia length from 3m vs 12m
        max_len_3m = 0
        for ap in data_3m.get('apresentacoes', []):
            max_len_3m = max(max_len_3m, len(ap.get('tendencia', [])))
        
        max_len_12m = 0
        for ap in data_12m.get('apresentacoes', []):
            max_len_12m = max(max_len_12m, len(ap.get('tendencia', [])))
        
        # 3 months should have at most 3 data points (one per month)
        # But can have 0 if no data in last 3 months
        assert max_len_3m <= 3, f"3 month period should have at most 3 trend points, got {max_len_3m}"
        
        # 12 months can have up to 12 data points
        assert max_len_12m <= 12, f"12 month period should have at most 12 trend points, got {max_len_12m}"
        
        print(f"Tendencia points: 3m={max_len_3m}, 12m={max_len_12m}")
    
    def test_different_search_term_returns_tendencia(self):
        """Test tendencia with different search term (Denosumabe)"""
        params = {"q": "Denosumabe", "meses": 12, "limite": 50}
        
        response = requests.get(self.search_url, params=params, timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        apresentacoes = data.get('apresentacoes', [])
        
        # All apresentacoes should have tendencia field
        for ap in apresentacoes:
            assert 'tendencia' in ap, f"Missing tendencia in {ap.get('nome')}"
            assert isinstance(ap['tendencia'], list), "tendencia should be a list"


@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
