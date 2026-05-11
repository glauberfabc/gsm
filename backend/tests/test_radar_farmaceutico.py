"""
Test Radar Farmaceutico - Inteligencia de Desabastecimento
==========================================================
Tests for Phase 1 & 2 of Radar Farmaceutico:
1. Lista de Interesse Estrategica CRUD
2. Desabastecimento detection
3. Stats endpoint
4. Scan trigger
5. Seed functionality
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Expected seeded items
EXPECTED_SEEDS = ['Pembrolizumabe', 'Canabidiol', 'Semaglutida', 'Eculizumabe']


class TestRadarFarmaceuticoListaInteresse:
    """Tests for Lista de Interesse Estrategica CRUD operations"""

    def test_get_lista_interesse_returns_seeded_items(self):
        """GET /api/radar-farmaceutico/lista-interesse should return seeded items"""
        response = requests.get(f"{BASE_URL}/api/radar-farmaceutico/lista-interesse")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert 'items' in data, "Response should have 'items' key"
        assert 'total' in data, "Response should have 'total' key"
        
        items = data['items']
        assert len(items) >= 4, f"Expected at least 4 seeded items, got {len(items)}"
        
        # Check that all expected seeds are present
        medicamentos = [item['medicamento'] for item in items]
        for seed in EXPECTED_SEEDS:
            assert seed in medicamentos, f"Expected seed '{seed}' not found in lista interesse"
        
        print(f"PASS: GET lista-interesse returns {len(items)} items including all 4 seeds")

    def test_lista_interesse_item_structure(self):
        """Verify structure of lista interesse items"""
        response = requests.get(f"{BASE_URL}/api/radar-farmaceutico/lista-interesse")
        assert response.status_code == 200
        
        data = response.json()
        items = data['items']
        assert len(items) > 0, "Should have at least one item"
        
        # Check first item structure
        item = items[0]
        required_fields = ['id', 'medicamento', 'principio_ativo', 'categoria', 'prioridade', 'target_type', 'ativo']
        for field in required_fields:
            assert field in item, f"Item missing required field: {field}"
        
        # Verify field values
        assert item['ativo'] == True, "Item should be active"
        assert item['categoria'] in ['Oncologia', 'Doencas Raras', 'Peptideos'], f"Invalid categoria: {item['categoria']}"
        assert item['prioridade'] in ['alta', 'media', 'baixa'], f"Invalid prioridade: {item['prioridade']}"
        assert item['target_type'] in ['Importacao', 'Nacional'], f"Invalid target_type: {item['target_type']}"
        
        print(f"PASS: Lista interesse item structure is correct")

    def test_post_add_new_interesse(self):
        """POST /api/radar-farmaceutico/lista-interesse should add new item"""
        test_item = {
            'medicamento': f'TEST_Medicamento_{int(time.time())}',
            'principio_ativo': 'Test Principio Ativo',
            'categoria': 'Oncologia',
            'prioridade': 'media',
            'target_type': 'Nacional'
        }
        
        response = requests.post(
            f"{BASE_URL}/api/radar-farmaceutico/lista-interesse",
            json=test_item
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert 'id' in data, "Response should have 'id'"
        assert data['medicamento'] == test_item['medicamento']
        assert data['principio_ativo'] == test_item['principio_ativo']
        assert data['categoria'] == test_item['categoria']
        assert data['ativo'] == True
        
        # Store ID for cleanup
        self.__class__.test_item_id = data['id']
        
        print(f"PASS: POST lista-interesse created item with id={data['id']}")

    def test_post_add_interesse_requires_medicamento(self):
        """POST without medicamento should return 400"""
        response = requests.post(
            f"{BASE_URL}/api/radar-farmaceutico/lista-interesse",
            json={'principio_ativo': 'Test'}
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("PASS: POST without medicamento returns 400")

    def test_delete_interesse(self):
        """DELETE /api/radar-farmaceutico/lista-interesse/{id} should remove item"""
        # First create an item to delete
        test_item = {
            'medicamento': f'TEST_ToDelete_{int(time.time())}',
            'principio_ativo': 'Delete Test',
            'categoria': 'Peptideos'
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/radar-farmaceutico/lista-interesse",
            json=test_item
        )
        assert create_response.status_code == 200
        item_id = create_response.json()['id']
        
        # Now delete it
        delete_response = requests.delete(
            f"{BASE_URL}/api/radar-farmaceutico/lista-interesse/{item_id}"
        )
        
        assert delete_response.status_code == 200, f"Expected 200, got {delete_response.status_code}"
        data = delete_response.json()
        assert data['message'] == 'Removido'
        assert data['id'] == item_id
        
        # Verify it's gone
        list_response = requests.get(f"{BASE_URL}/api/radar-farmaceutico/lista-interesse")
        items = list_response.json()['items']
        item_ids = [i['id'] for i in items]
        assert item_id not in item_ids, "Deleted item should not be in list"
        
        print(f"PASS: DELETE lista-interesse/{item_id} removed item successfully")

    def test_delete_nonexistent_returns_404(self):
        """DELETE with invalid ID should return 404"""
        response = requests.delete(
            f"{BASE_URL}/api/radar-farmaceutico/lista-interesse/nonexistent-id-12345"
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: DELETE nonexistent item returns 404")


class TestRadarFarmaceuticoStats:
    """Tests for stats endpoint"""

    def test_get_stats_returns_correct_structure(self):
        """GET /api/radar-farmaceutico/stats should return statistics"""
        response = requests.get(f"{BASE_URL}/api/radar-farmaceutico/stats")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        required_fields = ['total_lista_interesse', 'total_desabastecimento', 'criticos', 'reativados']
        for field in required_fields:
            assert field in data, f"Stats missing required field: {field}"
        
        # Verify values are integers
        assert isinstance(data['total_lista_interesse'], int)
        assert isinstance(data['total_desabastecimento'], int)
        assert isinstance(data['criticos'], int)
        assert isinstance(data['reativados'], int)
        
        # Should have at least 4 items in lista interesse (seeds)
        assert data['total_lista_interesse'] >= 4, f"Expected at least 4 in lista interesse, got {data['total_lista_interesse']}"
        
        print(f"PASS: GET stats returns correct structure with total_lista_interesse={data['total_lista_interesse']}")


class TestRadarFarmaceuticoScan:
    """Tests for scan endpoint"""

    def test_post_scan_triggers_background_scan(self):
        """POST /api/radar-farmaceutico/scan should trigger background scan"""
        response = requests.post(f"{BASE_URL}/api/radar-farmaceutico/scan")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data['status'] == 'processando', f"Expected status='processando', got {data['status']}"
        assert 'mensagem' in data, "Response should have 'mensagem'"
        
        print(f"PASS: POST scan returns status='processando'")


class TestRadarFarmaceuticoDesabastecimento:
    """Tests for desabastecimento endpoint"""

    def test_get_desabastecimento_returns_list(self):
        """GET /api/radar-farmaceutico/desabastecimento should return items list"""
        response = requests.get(f"{BASE_URL}/api/radar-farmaceutico/desabastecimento")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert 'items' in data, "Response should have 'items' key"
        assert 'total' in data, "Response should have 'total' key"
        assert 'estatisticas' in data, "Response should have 'estatisticas' key"
        
        # Items should be a list (may be empty if no desabastecimento detected)
        assert isinstance(data['items'], list)
        
        # Estatisticas should have required fields
        stats = data['estatisticas']
        assert 'total_lista_interesse' in stats
        assert 'total_desabastecimento' in stats
        
        print(f"PASS: GET desabastecimento returns {len(data['items'])} items with stats")


class TestRadarFarmaceuticoSeed:
    """Tests for seed endpoint"""

    def test_post_seed_returns_ja_existente(self):
        """POST /api/radar-farmaceutico/seed should return ja_existente when seeds already present"""
        response = requests.post(f"{BASE_URL}/api/radar-farmaceutico/seed")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Since seeds are already inserted, should return ja_existente
        assert data['status'] == 'ja_existente', f"Expected status='ja_existente', got {data['status']}"
        assert 'total' in data, "Response should have 'total'"
        assert data['total'] >= 4, f"Expected total >= 4, got {data['total']}"
        
        print(f"PASS: POST seed returns status='ja_existente' with total={data['total']}")


class TestLmrIntegrationWithDesabastecimento:
    """Tests for LMR service integration with desabastecimento_inteligencia"""

    def test_lmr_service_checks_desabastecimento(self):
        """LMR analysis should check desabastecimento_inteligencia collection"""
        # Analyze a seeded medicamento
        response = requests.post(
            f"{BASE_URL}/api/dama/lmr-analise-medicamento",
            json={
                'medicamento': 'Pembrolizumabe',
                'tipo_produto': 'biologico'
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert 'classificacao_lmr' in data, "Response should have classificacao_lmr"
        
        # The classificacao should indicate if desabastecimento was detected
        classificacao = data['classificacao_lmr']
        assert 'desabastecimento_detectado' in classificacao, "classificacao should have desabastecimento_detectado field"
        
        print(f"PASS: LMR analysis includes desabastecimento check (detected={classificacao['desabastecimento_detectado']})")


class TestCleanup:
    """Cleanup test data"""

    def test_cleanup_test_items(self):
        """Remove TEST_ prefixed items from lista interesse"""
        response = requests.get(f"{BASE_URL}/api/radar-farmaceutico/lista-interesse")
        if response.status_code == 200:
            items = response.json().get('items', [])
            for item in items:
                if item.get('medicamento', '').startswith('TEST_'):
                    requests.delete(f"{BASE_URL}/api/radar-farmaceutico/lista-interesse/{item['id']}")
                    print(f"Cleaned up test item: {item['medicamento']}")
        
        print("PASS: Cleanup completed")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
