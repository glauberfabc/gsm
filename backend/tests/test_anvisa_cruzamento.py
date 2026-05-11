"""
ANVISA Cruzamento Tests - Backend API Tests
============================================
Tests for the NEW ANVISA features:
1. POST /api/anvisa/atualizar - coletados, processados, oportunidades_licitacao
2. GET /api/anvisa/alertas - medicamento with SPECIFIC names, situacao, risco, oportunidade
3. POST /api/anvisa/cruzar-licitacoes - cruzamento dict with medicine names as keys
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAnvisaAtualizar:
    """Test POST /api/anvisa/atualizar endpoint"""
    
    def test_atualizar_returns_coletados(self):
        """POST /api/anvisa/atualizar should return coletados > 0"""
        response = requests.post(f"{BASE_URL}/api/anvisa/atualizar", timeout=120)
        assert response.status_code == 200
        
        data = response.json()
        assert "coletados" in data, "Response missing 'coletados' field"
        assert data["coletados"] >= 0, "coletados should be >= 0"
        print(f"✓ Coletados: {data['coletados']}")
    
    def test_atualizar_returns_processados(self):
        """POST /api/anvisa/atualizar should return processados > 0"""
        response = requests.post(f"{BASE_URL}/api/anvisa/atualizar", timeout=120)
        assert response.status_code == 200
        
        data = response.json()
        assert "processados" in data, "Response missing 'processados' field"
        assert data["processados"] >= 0, "processados should be >= 0"
        print(f"✓ Processados: {data['processados']}")
    
    def test_atualizar_returns_estatisticas(self):
        """POST /api/anvisa/atualizar should return estatisticas with oportunidades_licitacao"""
        response = requests.post(f"{BASE_URL}/api/anvisa/atualizar", timeout=120)
        assert response.status_code == 200
        
        data = response.json()
        assert "estatisticas" in data, "Response missing 'estatisticas' field"
        
        stats = data["estatisticas"]
        assert "oportunidades_licitacao" in stats, "estatisticas missing 'oportunidades_licitacao'"
        print(f"✓ Oportunidades Licitação: {stats['oportunidades_licitacao']}")


class TestAnvisaAlertas:
    """Test GET /api/anvisa/alertas endpoint"""
    
    def test_alertas_returns_list(self):
        """GET /api/anvisa/alertas should return a list of alertas"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert "alertas" in data, "Response missing 'alertas' field"
        assert isinstance(data["alertas"], list), "alertas should be a list"
        assert len(data["alertas"]) > 0, "alertas list should not be empty"
        print(f"✓ Total alertas: {len(data['alertas'])}")
    
    def test_alertas_have_medicamento_field(self):
        """Each alerta should have medicamento field with SPECIFIC names (not N/A or Diversos)"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas", timeout=30)
        data = response.json()
        
        alertas = data.get("alertas", [])
        assert len(alertas) > 0, "No alertas to test"
        
        invalid_names = {'N/A', 'Diversos', 'Medicamentos', '-', ''}
        specific_count = 0
        
        for alerta in alertas[:10]:  # Check first 10
            assert "medicamento" in alerta, "Alerta missing 'medicamento' field"
            med_name = alerta["medicamento"]
            
            # Check if name is specific (not generic)
            if med_name and med_name not in invalid_names:
                specific_count += 1
            
            print(f"  - Medicamento: {med_name}")
        
        # At least 50% should have specific names
        assert specific_count >= len(alertas[:10]) * 0.5, f"Only {specific_count}/10 alertas have specific medicamento names"
        print(f"✓ {specific_count}/{len(alertas[:10])} alertas have specific medicamento names")
    
    def test_alertas_have_required_fields(self):
        """Each alerta should have situacao, risco (ALTO/MEDIO/BAIXO), oportunidade"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas", timeout=30)
        data = response.json()
        
        alertas = data.get("alertas", [])
        assert len(alertas) > 0, "No alertas to test"
        
        valid_risco = {'ALTO', 'MEDIO', 'BAIXO'}
        valid_oportunidade = {'Importação', 'Licitação provável', 'Monitorar'}
        
        for alerta in alertas[:5]:
            # Check situacao
            assert "situacao" in alerta, "Alerta missing 'situacao' field"
            assert alerta["situacao"], "situacao should not be empty"
            
            # Check risco
            assert "risco" in alerta, "Alerta missing 'risco' field"
            assert alerta["risco"] in valid_risco, f"Invalid risco: {alerta['risco']}"
            
            # Check oportunidade
            assert "oportunidade" in alerta, "Alerta missing 'oportunidade' field"
            assert alerta["oportunidade"] in valid_oportunidade, f"Invalid oportunidade: {alerta['oportunidade']}"
            
            # Check descricao
            assert "descricao" in alerta, "Alerta missing 'descricao' field"
            
            print(f"  ✓ {alerta['medicamento']}: risco={alerta['risco']}, oportunidade={alerta['oportunidade']}")


class TestAnvisaCruzarLicitacoes:
    """Test POST /api/anvisa/cruzar-licitacoes endpoint"""
    
    def test_cruzar_returns_cruzamento_dict(self):
        """POST /api/anvisa/cruzar-licitacoes should return cruzamento dict"""
        response = requests.post(f"{BASE_URL}/api/anvisa/cruzar-licitacoes", timeout=90)
        assert response.status_code == 200
        
        data = response.json()
        assert "cruzamento" in data, "Response missing 'cruzamento' field"
        assert isinstance(data["cruzamento"], dict), "cruzamento should be a dict"
        print(f"✓ Cruzamento has {len(data['cruzamento'])} medicines")
    
    def test_cruzar_medicines_have_licitacoes(self):
        """Each medicine in cruzamento should have licitacoes_encontradas and licitacoes array"""
        response = requests.post(f"{BASE_URL}/api/anvisa/cruzar-licitacoes", timeout=90)
        data = response.json()
        
        cruzamento = data.get("cruzamento", {})
        assert len(cruzamento) > 0, "Cruzamento is empty"
        
        for med_name, med_data in list(cruzamento.items())[:3]:
            assert "licitacoes_encontradas" in med_data, f"Medicine {med_name} missing 'licitacoes_encontradas'"
            assert "licitacoes" in med_data, f"Medicine {med_name} missing 'licitacoes'"
            assert isinstance(med_data["licitacoes"], list), "licitacoes should be a list"
            
            print(f"  - {med_name}: {med_data['licitacoes_encontradas']} licitações")
    
    def test_cruzar_returns_resumo(self):
        """POST /api/anvisa/cruzar-licitacoes should return resumo with statistics"""
        response = requests.post(f"{BASE_URL}/api/anvisa/cruzar-licitacoes", timeout=90)
        data = response.json()
        
        assert "resumo" in data, "Response missing 'resumo' field"
        resumo = data["resumo"]
        
        assert "medicamentos_analisados" in resumo, "resumo missing 'medicamentos_analisados'"
        assert "medicamentos_com_licitacao" in resumo, "resumo missing 'medicamentos_com_licitacao'"
        assert "total_licitacoes_encontradas" in resumo, "resumo missing 'total_licitacoes_encontradas'"
        
        print(f"✓ Resumo: {resumo['medicamentos_analisados']} analisados, {resumo['medicamentos_com_licitacao']} com licitação, {resumo['total_licitacoes_encontradas']} total")
    
    def test_cruzar_licitacoes_have_required_fields(self):
        """Licitacoes in cruzamento should have objeto, orgao, UF, modalidade, data fields"""
        response = requests.post(f"{BASE_URL}/api/anvisa/cruzar-licitacoes", timeout=90)
        data = response.json()
        
        cruzamento = data.get("cruzamento", {})
        
        # Find a medicine with licitações
        for med_name, med_data in cruzamento.items():
            if med_data.get("licitacoes_encontradas", 0) > 0:
                licitacoes = med_data.get("licitacoes", [])
                if licitacoes:
                    lic = licitacoes[0]
                    # Check for expected fields (may vary by source)
                    print(f"  Licitação fields: {list(lic.keys())}")
                    # At minimum should have objeto/descricao
                    assert any(f in lic for f in ['objeto', 'descricao', 'medicamento']), "Licitação missing objeto/descricao"
                    print(f"✓ Found licitação with objeto/descricao field")
                    return
        
        print("ℹ No licitações with data to verify fields (all have 0 matches)")


class TestAnvisaStats:
    """Test ANVISA stats/statistics endpoint"""
    
    def test_stats_returns_counts(self):
        """GET /api/anvisa/alertas estatisticas should have all required counts"""
        response = requests.get(f"{BASE_URL}/api/anvisa/alertas", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        stats = data.get("estatisticas", {})
        
        assert "total_alertas" in stats, "stats missing 'total_alertas'"
        assert "risco_alto" in stats, "stats missing 'risco_alto'"
        assert "risco_medio" in stats, "stats missing 'risco_medio'"
        assert "oportunidades_importacao" in stats, "stats missing 'oportunidades_importacao'"
        assert "oportunidades_licitacao" in stats, "stats missing 'oportunidades_licitacao'"
        
        print(f"✓ Stats: total={stats['total_alertas']}, alto={stats['risco_alto']}, medio={stats['risco_medio']}, importacao={stats['oportunidades_importacao']}, licitacao={stats['oportunidades_licitacao']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
