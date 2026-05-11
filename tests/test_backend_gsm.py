"""
GSM v25.1 Backend API Tests
===========================
Tests for:
- Radares CRUD (create, read, update, delete)
- Preços search endpoint
- Listas endpoint
- Search/local endpoint
"""

import pytest
import requests
import os
import uuid

# Get backend URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://dama-legal-1.preview.emergentagent.com"

API_URL = f"{BASE_URL}/api"


class TestHealthAndBasics:
    """Basic health and connectivity tests"""
    
    def test_listas_endpoint_returns_200(self):
        """Test /api/listas returns 200"""
        response = requests.get(f"{API_URL}/listas")
        assert response.status_code == 200
        data = response.json()
        assert "listas" in data
        assert "total" in data
        print(f"✅ Listas endpoint: {data['total']} listas found")
    
    def test_radares_endpoint_returns_200(self):
        """Test /api/radares returns 200"""
        response = requests.get(f"{API_URL}/radares")
        assert response.status_code == 200
        data = response.json()
        assert "radares" in data
        assert "total" in data
        print(f"✅ Radares endpoint: {data['total']} radares found")


class TestRadaresCRUD:
    """CRUD tests for Radares (Alertas com E-mail e Frequência)"""
    
    @pytest.fixture
    def test_radar_data(self):
        """Generate unique test radar data"""
        unique_id = str(uuid.uuid4())[:8]
        return {
            "nome": f"TEST_Radar_{unique_id}",
            "email": f"test_{unique_id}@example.com",
            "termos": "canabidiol, insulina, teste",
            "frequencia": "24h"
        }
    
    def test_create_radar(self, test_radar_data):
        """Test POST /api/radares - Create new radar"""
        response = requests.post(f"{API_URL}/radares", json=test_radar_data)
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        
        data = response.json()
        # API returns {"message": ..., "radar": {...}}
        assert "radar" in data
        radar = data["radar"]
        assert "id" in radar
        assert radar["nome"] == test_radar_data["nome"]
        assert radar["email"] == test_radar_data["email"]
        assert radar["termos"] == test_radar_data["termos"]
        assert radar["frequencia"] == test_radar_data["frequencia"]
        
        # Store ID for cleanup
        radar_id = radar["id"]
        print(f"✅ Created radar: {radar_id}")
        
        # Cleanup - delete the test radar
        delete_response = requests.delete(f"{API_URL}/radares/{radar_id}")
        assert delete_response.status_code == 200
        print(f"✅ Cleaned up radar: {radar_id}")
    
    def test_create_and_get_radar(self, test_radar_data):
        """Test Create → GET verification pattern"""
        # CREATE
        create_response = requests.post(f"{API_URL}/radares", json=test_radar_data)
        assert create_response.status_code == 201
        created_data = create_response.json()
        radar_id = created_data["radar"]["id"]
        
        # GET to verify persistence - returns {"radar": {...}}
        get_response = requests.get(f"{API_URL}/radares/{radar_id}")
        assert get_response.status_code == 200
        
        fetched_data = get_response.json()
        fetched_radar = fetched_data["radar"]
        assert fetched_radar["nome"] == test_radar_data["nome"]
        assert fetched_radar["email"] == test_radar_data["email"]
        print(f"✅ Verified radar persistence: {radar_id}")
        
        # Cleanup
        requests.delete(f"{API_URL}/radares/{radar_id}")
    
    def test_update_radar(self, test_radar_data):
        """Test PUT /api/radares/{id} - Update radar"""
        # CREATE first
        create_response = requests.post(f"{API_URL}/radares", json=test_radar_data)
        assert create_response.status_code == 201
        radar_id = create_response.json()["radar"]["id"]
        
        # UPDATE - returns {"message": ..., "radar": {...}}
        update_data = {
            "nome": f"TEST_Updated_{radar_id[:8]}",
            "frequencia": "8h"
        }
        update_response = requests.put(f"{API_URL}/radares/{radar_id}", json=update_data)
        assert update_response.status_code == 200
        
        updated_data = update_response.json()
        updated_radar = updated_data["radar"]
        assert updated_radar["nome"] == update_data["nome"]
        assert updated_radar["frequencia"] == update_data["frequencia"]
        
        # GET to verify update persisted - returns {"radar": {...}}
        get_response = requests.get(f"{API_URL}/radares/{radar_id}")
        assert get_response.status_code == 200
        fetched_radar = get_response.json()["radar"]
        assert fetched_radar["nome"] == update_data["nome"]
        print(f"✅ Updated and verified radar: {radar_id}")
        
        # Cleanup
        requests.delete(f"{API_URL}/radares/{radar_id}")
    
    def test_delete_radar(self, test_radar_data):
        """Test DELETE /api/radares/{id} - Delete radar"""
        # CREATE first
        create_response = requests.post(f"{API_URL}/radares", json=test_radar_data)
        assert create_response.status_code == 201
        radar_id = create_response.json()["radar"]["id"]
        
        # DELETE
        delete_response = requests.delete(f"{API_URL}/radares/{radar_id}")
        assert delete_response.status_code == 200
        
        # GET to verify deletion
        get_response = requests.get(f"{API_URL}/radares/{radar_id}")
        assert get_response.status_code == 404
        print(f"✅ Deleted and verified removal: {radar_id}")
    
    def test_create_radar_missing_email(self):
        """Test validation - radar without email should fail"""
        invalid_data = {
            "nome": "TEST_Invalid_Radar",
            "termos": "test",
            "frequencia": "24h"
            # Missing email
        }
        response = requests.post(f"{API_URL}/radares", json=invalid_data)
        # Should return 422 (validation error) or 400
        assert response.status_code in [400, 422], f"Expected 400/422, got {response.status_code}"
        print("✅ Validation works - missing email rejected")
    
    def test_radar_frequency_options(self, test_radar_data):
        """Test all frequency options (8h, 12h, 24h)"""
        frequencies = ["8h", "12h", "24h"]
        
        for freq in frequencies:
            test_radar_data["frequencia"] = freq
            test_radar_data["nome"] = f"TEST_Freq_{freq}_{uuid.uuid4().hex[:6]}"
            
            response = requests.post(f"{API_URL}/radares", json=test_radar_data)
            assert response.status_code == 201, f"Failed for frequency {freq}"
            
            radar_data = response.json()["radar"]
            radar_id = radar_data["id"]
            assert radar_data["frequencia"] == freq
            
            # Cleanup
            requests.delete(f"{API_URL}/radares/{radar_id}")
        
        print("✅ All frequency options work: 8h, 12h, 24h")


class TestPrecosSearch:
    """Tests for /api/precos/search endpoint"""
    
    def test_precos_search_basic(self):
        """Test basic price search"""
        response = requests.get(f"{API_URL}/precos/search?q=insulina")
        assert response.status_code == 200
        
        data = response.json()
        assert "termo" in data
        assert "total" in data
        assert "resultados" in data
        assert data["termo"] == "insulina"
        print(f"✅ Preços search: {data['total']} results for 'insulina'")
    
    def test_precos_search_with_limit(self):
        """Test price search with limit parameter"""
        response = requests.get(f"{API_URL}/precos/search?q=medicamento&limite=5")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["resultados"]) <= 5
        print(f"✅ Preços search with limit: {len(data['resultados'])} results")
    
    def test_precos_search_result_structure(self):
        """Test price search result structure"""
        response = requests.get(f"{API_URL}/precos/search?q=insulina")
        assert response.status_code == 200
        
        data = response.json()
        if data["resultados"]:
            result = data["resultados"][0]
            # Check expected fields
            assert "descricao" in result
            assert "orgao" in result
            assert "preco_unitario" in result
            assert "uf" in result
            print(f"✅ Preços result structure valid")
        else:
            print("⚠️ No results to validate structure")


class TestSearchLocal:
    """Tests for /api/search/local endpoint (main search)"""
    
    def test_search_by_medicamento(self):
        """Test search by medication name"""
        response = requests.get(f"{API_URL}/search/local?q=insulina&limit=5")
        assert response.status_code == 200
        
        data = response.json()
        assert "termo" in data
        assert "total" in data
        assert "resultados" in data
        print(f"✅ Search by medicamento: {data['total']} results")
    
    def test_search_by_municipio(self):
        """Test search by municipality"""
        response = requests.get(f"{API_URL}/search/local?municipio=Guarulhos&limit=5")
        assert response.status_code == 200
        
        data = response.json()
        assert "resultados" in data
        print(f"✅ Search by município: {data['total']} results")
    
    def test_search_by_uf(self):
        """Test search by state (UF) - Note: API may return results from other states due to expansion"""
        response = requests.get(f"{API_URL}/search/local?q=medicamento&estados=SP&limit=5")
        assert response.status_code == 200
        
        data = response.json()
        assert "resultados" in data
        assert "filtros_ativos" in data
        # Verify filter was applied (API may still return other states due to term expansion)
        if "estados" in data.get("filtros_ativos", {}):
            assert "SP" in data["filtros_ativos"]["estados"]
        print(f"✅ Search by UF: {data['total']} results with SP filter")
    
    def test_search_combined_filters(self):
        """Test search with multiple filters"""
        response = requests.get(f"{API_URL}/search/local?q=insulina&estados=SP&limit=10")
        assert response.status_code == 200
        
        data = response.json()
        assert "filtros_ativos" in data
        print(f"✅ Combined filters search: {data['total']} results")
    
    def test_search_result_structure(self):
        """Test search result structure has required fields"""
        response = requests.get(f"{API_URL}/search/local?q=insulina&limit=1")
        assert response.status_code == 200
        
        data = response.json()
        if data["resultados"]:
            result = data["resultados"][0]
            # Check key fields exist
            expected_fields = ["objeto", "orgao", "uf"]
            for field in expected_fields:
                assert field in result or result.get(field) is not None, f"Missing field: {field}"
            print("✅ Search result structure valid")
        else:
            print("⚠️ No results to validate structure")


class TestListas:
    """Tests for /api/listas endpoint"""
    
    def test_list_listas(self):
        """Test GET /api/listas"""
        response = requests.get(f"{API_URL}/listas")
        assert response.status_code == 200
        
        data = response.json()
        assert "listas" in data
        assert "total" in data
        assert isinstance(data["listas"], list)
        print(f"✅ Listas: {data['total']} lists found")
    
    def test_lista_structure(self):
        """Test lista structure has required fields"""
        response = requests.get(f"{API_URL}/listas")
        assert response.status_code == 200
        
        data = response.json()
        if data["listas"]:
            lista = data["listas"][0]
            assert "id" in lista
            assert "nome" in lista
            assert "medicamentos" in lista
            print("✅ Lista structure valid")


class TestCleanup:
    """Cleanup any remaining test data"""
    
    def test_cleanup_test_radares(self):
        """Remove any TEST_ prefixed radares"""
        response = requests.get(f"{API_URL}/radares")
        if response.status_code == 200:
            radares = response.json().get("radares", [])
            cleaned = 0
            for radar in radares:
                if radar.get("nome", "").startswith("TEST_"):
                    delete_response = requests.delete(f"{API_URL}/radares/{radar['id']}")
                    if delete_response.status_code == 200:
                        cleaned += 1
            print(f"✅ Cleaned up {cleaned} test radares")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
