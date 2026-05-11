"""
Test: Preços Period Filter (meses parameter) v45.0
Tests the NEW period filter feature on /api/precos/search and /api/precos/export-excel
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestPrecosPeriodFilter:
    """Tests for the period filter (meses parameter) on Preços endpoints"""
    
    def test_precos_search_default_12_months(self):
        """Test default meses=12 returns results and includes 'periodo' field"""
        params = {
            'q': 'Prolia',
            'use_cache': 'false'
        }
        # Default should be 24 months based on server code ge=3, le=24
        response = requests.get(f"{BASE_URL}/api/precos/search", params=params, timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Should have periodo field
        assert 'periodo' in data, "Response should include 'periodo' field"
        assert 'meses' in data['periodo'], "Periodo should contain 'meses' word"
        
        # Should have results
        assert 'total' in data, "Response should include 'total' field"
        print(f"Default search returned {data['total']} results with periodo: {data['periodo']}")
    
    def test_precos_search_3_months_vs_24_months(self):
        """Key assertion: 3 months should return FEWER results than 24 months"""
        search_term = 'Prolia'
        
        # Search with 3 months
        params_3m = {'q': search_term, 'meses': 3, 'use_cache': 'false'}
        response_3m = requests.get(f"{BASE_URL}/api/precos/search", params=params_3m, timeout=90)
        assert response_3m.status_code == 200, f"3m search failed: {response_3m.status_code}"
        data_3m = response_3m.json()
        total_3m = data_3m.get('total', 0)
        periodo_3m = data_3m.get('periodo', '')
        
        print(f"3 months: {total_3m} results, periodo: {periodo_3m}")
        
        # Small delay to avoid rate limiting
        time.sleep(2)
        
        # Search with 24 months
        params_24m = {'q': search_term, 'meses': 24, 'use_cache': 'false'}
        response_24m = requests.get(f"{BASE_URL}/api/precos/search", params=params_24m, timeout=90)
        assert response_24m.status_code == 200, f"24m search failed: {response_24m.status_code}"
        data_24m = response_24m.json()
        total_24m = data_24m.get('total', 0)
        periodo_24m = data_24m.get('periodo', '')
        
        print(f"24 months: {total_24m} results, periodo: {periodo_24m}")
        
        # Key assertion: 3m should have FEWER results than 24m
        assert total_3m <= total_24m, f"3 months ({total_3m}) should have <= results than 24 months ({total_24m})"
        
        # Verify periodo field shows correct period
        assert '3 meses' in periodo_3m, f"Expected '3 meses' in periodo, got: {periodo_3m}"
        assert '24 meses' in periodo_24m, f"Expected '24 meses' in periodo, got: {periodo_24m}"
        
        print(f"PASS: 3m ({total_3m}) <= 24m ({total_24m})")
    
    def test_precos_search_6_months(self):
        """Test meses=6 returns results with correct periodo"""
        params = {'q': 'Prolia', 'meses': 6, 'use_cache': 'false'}
        response = requests.get(f"{BASE_URL}/api/precos/search", params=params, timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        assert 'periodo' in data
        assert '6 meses' in data['periodo'], f"Expected '6 meses', got: {data['periodo']}"
        print(f"6 months: {data['total']} results, periodo: {data['periodo']}")
    
    def test_precos_search_all_valid_periods(self):
        """Test all valid meses values: 3, 6, 9, 12, 18, 24"""
        valid_periods = [3, 6, 9, 12, 18, 24]
        results = {}
        
        for meses in valid_periods:
            params = {'q': 'insulina', 'meses': meses, 'use_cache': 'false', 'limite': 10}
            response = requests.get(f"{BASE_URL}/api/precos/search", params=params, timeout=60)
            assert response.status_code == 200, f"meses={meses} failed: {response.status_code}"
            
            data = response.json()
            results[meses] = data.get('total', 0)
            assert f'{meses} meses' in data.get('periodo', ''), f"Periodo should show '{meses} meses'"
            time.sleep(1)  # Rate limit
        
        print(f"Results by period: {results}")
        
        # Verify results are generally increasing with period
        for i in range(len(valid_periods) - 1):
            p1, p2 = valid_periods[i], valid_periods[i+1]
            assert results[p1] <= results[p2], f"{p1}m ({results[p1]}) should be <= {p2}m ({results[p2]})"
    
    def test_precos_export_excel_with_meses(self):
        """Test export-excel endpoint accepts meses parameter"""
        params = {
            'q': 'Prolia',
            'meses': 6,
            'limite': 50
        }
        response = requests.get(f"{BASE_URL}/api/precos/export-excel", params=params, timeout=120)
        
        # Should return 200 with Excel content
        assert response.status_code == 200, f"Export failed: {response.status_code}"
        
        # Verify content type is Excel
        content_type = response.headers.get('content-type', '')
        assert 'spreadsheet' in content_type or 'excel' in content_type or 'octet-stream' in content_type, \
            f"Expected Excel content type, got: {content_type}"
        
        # Verify file has content
        assert len(response.content) > 1000, f"Excel file too small: {len(response.content)} bytes"
        
        print(f"Export with meses=6: {len(response.content)} bytes, content-type: {content_type}")
    
    def test_precos_export_excel_24_months(self):
        """Test export-excel with 24 months period"""
        params = {'q': 'Prolia', 'meses': 24, 'limite': 50}
        response = requests.get(f"{BASE_URL}/api/precos/export-excel", params=params, timeout=120)
        
        assert response.status_code == 200
        assert len(response.content) > 1000
        
        print(f"Export with meses=24: {len(response.content)} bytes")
    
    def test_precos_search_invalid_meses_rejected(self):
        """Test that invalid meses values are rejected (e.g., meses=1, meses=30)"""
        # meses=1 should be rejected (minimum is 3)
        params = {'q': 'Prolia', 'meses': 1}
        response = requests.get(f"{BASE_URL}/api/precos/search", params=params, timeout=30)
        # FastAPI validation should reject with 422 Unprocessable Entity
        assert response.status_code == 422, f"meses=1 should be rejected, got: {response.status_code}"
        
        # meses=30 should be rejected (maximum is 24)
        params = {'q': 'Prolia', 'meses': 30}
        response = requests.get(f"{BASE_URL}/api/precos/search", params=params, timeout=30)
        assert response.status_code == 422, f"meses=30 should be rejected, got: {response.status_code}"
        
        print("PASS: Invalid meses values correctly rejected with 422")


@pytest.fixture(scope="module", autouse=True)
def setup_base_url():
    """Ensure BASE_URL is set"""
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL not set")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
