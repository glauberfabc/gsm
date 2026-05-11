"""
DAMA P0 - Vigência Normativa Feature Tests

Tests the DAMA P0 feature that scrapes CMED/ANVISA legislation portal to check
if legal resolutions are 'vigente' (valid), 'caduca' (expired), or 'revogada' (revoked).

Key Endpoints:
- GET /api/dama/vigencia/stats - Returns stats with total, vigentes, caducas, revogadas counts
- GET /api/dama/vigencia/check?referencia=Resolução 07/2022 - Check resolution status
- GET /api/dama/vigencia/resolucoes - List resolutions with status info
- POST /api/dama/vigencia/sync - Rescrape and return total count
- POST /api/dama/vigencia/validar-esclarecimento - Validate norms for esclarecimento
- POST /api/anvisa/esclarecimento - Generate esclarecimento with vigencia validation
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://dama-legal-1.preview.emergentagent.com')


class TestDamaVigenciaStats:
    """Test GET /api/dama/vigencia/stats - Returns statistics of CMED resolutions"""
    
    def test_stats_returns_200(self):
        """Stats endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/dama/vigencia/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_stats_has_required_fields(self):
        """Stats should have total, vigentes, caducas, revogadas counts"""
        response = requests.get(f"{BASE_URL}/api/dama/vigencia/stats")
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields
        required_fields = ['total', 'vigentes', 'caducas', 'revogadas']
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        # Values should be integers >= 0
        assert isinstance(data['total'], int), "total should be integer"
        assert data['total'] >= 0, "total should be non-negative"
        assert isinstance(data['vigentes'], int), "vigentes should be integer"
        assert isinstance(data['caducas'], int), "caducas should be integer"
        assert isinstance(data['revogadas'], int), "revogadas should be integer"
    
    def test_stats_has_vigentes_com_alteracoes(self):
        """Stats should also have vigentes_com_alteracoes count"""
        response = requests.get(f"{BASE_URL}/api/dama/vigencia/stats")
        assert response.status_code == 200
        data = response.json()
        
        assert 'vigentes_com_alteracoes' in data, "Missing vigentes_com_alteracoes field"
        assert isinstance(data['vigentes_com_alteracoes'], int)


class TestDamaVigenciaCheck:
    """Test GET /api/dama/vigencia/check - Check specific resolution status"""
    
    def test_check_resolucao_07_2022_caduca(self):
        """Resolução 07/2022 should be CADUCA with pode_usar=false"""
        response = requests.get(
            f"{BASE_URL}/api/dama/vigencia/check",
            params={"referencia": "Resolução 07/2022"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # This is the KEY business requirement
        assert data.get('encontrada') == True, "Resolução 07/2022 should be found"
        assert data.get('status') == 'caduca', f"Expected 'caduca', got '{data.get('status')}'"
        assert data.get('pode_usar') == False, "pode_usar should be False for caduca"
    
    def test_check_resolucao_02_2004_vigente(self):
        """Resolução 02/2004 should be VIGENTE COM ALTERAÇÕES with pode_usar=true"""
        response = requests.get(
            f"{BASE_URL}/api/dama/vigencia/check",
            params={"referencia": "Resolução 02/2004"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('encontrada') == True, "Resolução 02/2004 should be found"
        # Can be 'vigente' or 'vigente com alterações'
        assert data.get('status') in ['vigente', 'vigente com alterações'], \
            f"Expected vigente or vigente com alterações, got '{data.get('status')}'"
        assert data.get('pode_usar') == True, "pode_usar should be True for vigente"
    
    def test_check_returns_alerta_message(self):
        """Check endpoint should return alerta message explaining the status"""
        response = requests.get(
            f"{BASE_URL}/api/dama/vigencia/check",
            params={"referencia": "Resolução 07/2022"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert 'alerta' in data, "Should have alerta field"
        assert len(data['alerta']) > 10, "alerta should be a descriptive message"
        # For caduca resolutions, alerta should warn about not using
        if data.get('status') == 'caduca':
            assert 'CADUCA' in data['alerta'] or 'caduca' in data['alerta'].lower()
    
    def test_check_returns_referencia_buscada(self):
        """Check endpoint should echo back the searched reference"""
        ref = "Resolução 07/2022"
        response = requests.get(
            f"{BASE_URL}/api/dama/vigencia/check",
            params={"referencia": ref}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('referencia_buscada') == ref
    
    def test_check_unknown_resolution(self):
        """Check for unknown resolution should return encontrada=False"""
        response = requests.get(
            f"{BASE_URL}/api/dama/vigencia/check",
            params={"referencia": "Resolução 99/1999"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('encontrada') == False


class TestDamaVigenciaResolucoes:
    """Test GET /api/dama/vigencia/resolucoes - List all resolutions"""
    
    def test_resolucoes_returns_200(self):
        """Resolucoes endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/dama/vigencia/resolucoes")
        assert response.status_code == 200
    
    def test_resolucoes_returns_list(self):
        """Should return list of resolutions"""
        response = requests.get(f"{BASE_URL}/api/dama/vigencia/resolucoes")
        assert response.status_code == 200
        data = response.json()
        
        assert 'resolucoes' in data, "Missing resolucoes field"
        assert isinstance(data['resolucoes'], list)
        assert 'total' in data
    
    def test_resolucoes_have_required_fields(self):
        """Each resolution should have titulo, numero, ano, status"""
        response = requests.get(f"{BASE_URL}/api/dama/vigencia/resolucoes")
        assert response.status_code == 200
        data = response.json()
        
        if len(data['resolucoes']) > 0:
            resolution = data['resolucoes'][0]
            required = ['titulo', 'numero', 'ano', 'status']
            for field in required:
                assert field in resolution, f"Resolution missing field: {field}"


class TestDamaVigenciaSync:
    """Test POST /api/dama/vigencia/sync - Rescrape CMED legislation"""
    
    def test_sync_returns_200(self):
        """Sync endpoint should return 200"""
        response = requests.post(f"{BASE_URL}/api/dama/vigencia/sync")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_sync_returns_total(self):
        """Sync should return total count of scraped resolutions"""
        response = requests.post(f"{BASE_URL}/api/dama/vigencia/sync")
        assert response.status_code == 200
        data = response.json()
        
        assert 'total' in data, "Missing total field"
        assert isinstance(data['total'], int)
        # After sync, should have at least some resolutions (the CMED page has ~30+)
        assert data['total'] >= 5, f"Expected at least 5 resolutions, got {data['total']}"


class TestDamaVigenciaValidarEsclarecimento:
    """Test POST /api/dama/vigencia/validar-esclarecimento"""
    
    def test_validar_returns_200(self):
        """Validar endpoint should return 200"""
        response = requests.post(f"{BASE_URL}/api/dama/vigencia/validar-esclarecimento")
        assert response.status_code == 200
    
    def test_validar_returns_bloqueios(self):
        """Should return bloqueios array for caduca/revogada norms"""
        response = requests.post(f"{BASE_URL}/api/dama/vigencia/validar-esclarecimento")
        assert response.status_code == 200
        data = response.json()
        
        # Should have these fields
        assert 'validacao' in data, "Missing validacao field"
        assert 'bloqueios' in data, "Missing bloqueios field"
        assert 'tem_bloqueio' in data, "Missing tem_bloqueio field"
        assert isinstance(data['bloqueios'], list)
        assert isinstance(data['tem_bloqueio'], bool)
    
    def test_validar_checks_key_norms(self):
        """Should validate key norms: 07/2022, 13/2022, 02/2004, 01/2003"""
        response = requests.post(f"{BASE_URL}/api/dama/vigencia/validar-esclarecimento")
        assert response.status_code == 200
        data = response.json()
        
        validacao = data.get('validacao', [])
        referencias = [v.get('referencia_buscada', '') for v in validacao]
        
        # Should check these key norms
        expected_norms = ["Resolução 07/2022", "Resolução 02/2004"]
        for norm in expected_norms:
            assert any(norm in ref for ref in referencias), f"Missing check for {norm}"
    
    def test_validar_identifies_07_2022_as_bloqueio(self):
        """Resolução 07/2022 (caduca) should appear in bloqueios"""
        response = requests.post(f"{BASE_URL}/api/dama/vigencia/validar-esclarecimento")
        assert response.status_code == 200
        data = response.json()
        
        bloqueios = data.get('bloqueios', [])
        # Find 07/2022 in bloqueios
        found_07_2022 = False
        for b in bloqueios:
            ref = b.get('referencia_buscada', '')
            if '07/2022' in ref or '7/2022' in ref:
                found_07_2022 = True
                assert b.get('status') == 'caduca', "07/2022 should be caduca"
                assert b.get('pode_usar') == False
                break
        
        assert found_07_2022, "Resolução 07/2022 should be in bloqueios as it is caduca"
        assert data.get('tem_bloqueio') == True, "tem_bloqueio should be True"


class TestEsclarecimentoWithVigencia:
    """Test POST /api/anvisa/esclarecimento - with vigencia validation"""
    
    def test_esclarecimento_without_force_returns_bloqueado(self):
        """Without force_generate, should return bloqueado=true for caduca normas"""
        response = requests.post(
            f"{BASE_URL}/api/anvisa/esclarecimento",
            json={
                "medicamento": "Test Medicamento",
                "principio_ativo": "Test PA",
                "situacao": "Desabastecimento",
                "link_prova": "https://example.com",
                "tipo_alerta": "desabastecimento",
                "empresa_id": "c1",
                # force_generate defaults to False
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Should be blocked due to caduca normas (07/2022)
        assert data.get('bloqueado') == True, "Should be blocked when force_generate is false"
        assert 'vigencia_alertas' in data, "Should include vigencia_alertas"
        assert len(data['vigencia_alertas']) > 0, "Should have at least one vigencia alert"
    
    def test_esclarecimento_with_force_generates_text(self):
        """With force_generate=true, should generate text despite caduca normas"""
        response = requests.post(
            f"{BASE_URL}/api/anvisa/esclarecimento",
            json={
                "medicamento": "Canabidiol",
                "principio_ativo": "CBD",
                "situacao": "Desabastecimento temporário",
                "link_prova": "https://www.gov.br/anvisa/test",
                "tipo_alerta": "desabastecimento",
                "empresa_id": "c1",
                "force_generate": True
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Should generate text even with caduca normas
        assert 'bloqueado' not in data or data.get('bloqueado') == False, \
            "Should not be blocked when force_generate=true"
        assert 'texto' in data, "Should have generated texto"
        assert len(data.get('texto', '')) > 100, "texto should be substantial"
        assert data.get('vigencia_validada') == True, "Should mark vigencia as validated"
    
    def test_esclarecimento_required_field_medicamento(self):
        """Should return 400 if medicamento is missing"""
        response = requests.post(
            f"{BASE_URL}/api/anvisa/esclarecimento",
            json={
                "principio_ativo": "Test PA",
                "situacao": "Test",
                "force_generate": True
            }
        )
        # Should return 400 for missing required field
        assert response.status_code == 400


class TestVigenciaStatusValues:
    """Test that vigencia service correctly identifies status values"""
    
    def test_caduca_status_value(self):
        """caduca status should be exactly 'caduca'"""
        response = requests.get(
            f"{BASE_URL}/api/dama/vigencia/check",
            params={"referencia": "Resolução 07/2022"}
        )
        assert response.status_code == 200
        data = response.json()
        
        if data.get('encontrada'):
            assert data.get('status') == 'caduca'
    
    def test_vigente_status_values(self):
        """vigente can be 'vigente' or 'vigente com alterações'"""
        response = requests.get(
            f"{BASE_URL}/api/dama/vigencia/check",
            params={"referencia": "Resolução 02/2004"}
        )
        assert response.status_code == 200
        data = response.json()
        
        if data.get('encontrada'):
            assert data.get('status') in ['vigente', 'vigente com alterações']
            assert data.get('pode_usar') == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
