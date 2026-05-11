"""
Test DAMA Checklist and Prova Documental PDF endpoints (P2 features)
Tests:
1. POST /api/dama/checklist - DAMA checklist automation
2. POST /api/dama/prova-documental - PDF generation for procurement
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestDamaChecklist:
    """Tests for POST /api/dama/checklist endpoint"""

    def test_checklist_insulina_basic(self):
        """Test checklist with basic medicamento 'insulina'"""
        response = requests.post(
            f"{BASE_URL}/api/dama/checklist",
            json={"medicamento": "insulina"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify required fields exist
        assert "medicamento" in data, "Missing 'medicamento' field"
        assert data["medicamento"] == "insulina"
        
        assert "checks" in data, "Missing 'checks' array"
        assert isinstance(data["checks"], list), "'checks' should be a list"
        assert len(data["checks"]) > 0, "'checks' should not be empty"
        
        assert "score_conformidade" in data, "Missing 'score_conformidade' field"
        assert isinstance(data["score_conformidade"], (int, float)), "'score_conformidade' should be numeric"
        
        assert "resumo" in data, "Missing 'resumo' field"
        assert "recomendacao" in data, "Missing 'recomendacao' field"
        
        # Verify resumo structure
        resumo = data["resumo"]
        assert "total" in resumo, "Missing 'total' in resumo"
        assert "aprovados" in resumo, "Missing 'aprovados' in resumo"
        assert "alertas" in resumo, "Missing 'alertas' in resumo"
        assert "bloqueios" in resumo, "Missing 'bloqueios' in resumo"
        
        print(f"✓ Checklist insulina: score={data['score_conformidade']}%, checks={len(data['checks'])}")

    def test_checklist_with_normas(self):
        """Test checklist with custom normas list"""
        response = requests.post(
            f"{BASE_URL}/api/dama/checklist",
            json={
                "medicamento": "amoxicilina",
                "normas": ["RDC 488/2021"]
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify medicamento
        assert data["medicamento"] == "amoxicilina"
        
        # Verify checks include the custom norma
        checks = data["checks"]
        vigencia_checks = [c for c in checks if c.get("tipo") == "vigencia"]
        assert len(vigencia_checks) > 0, "Should have vigencia checks"
        
        # Check that RDC 488/2021 is in the checks
        norma_items = [c.get("item", "") for c in vigencia_checks]
        has_rdc_488 = any("RDC 488/2021" in item for item in norma_items)
        assert has_rdc_488, f"RDC 488/2021 should be in checks. Found: {norma_items}"
        
        print(f"✓ Checklist amoxicilina with normas: {len(vigencia_checks)} vigencia checks")

    def test_checklist_check_structure(self):
        """Test that each check has required fields"""
        response = requests.post(
            f"{BASE_URL}/api/dama/checklist",
            json={"medicamento": "paracetamol"}
        )
        assert response.status_code == 200
        
        data = response.json()
        checks = data["checks"]
        
        for i, check in enumerate(checks):
            assert "tipo" in check, f"Check {i} missing 'tipo'"
            assert "item" in check, f"Check {i} missing 'item'"
            assert "status" in check, f"Check {i} missing 'status'"
            assert check["status"] in ["ok", "alerta", "bloqueio"], f"Check {i} has invalid status: {check['status']}"
            assert "detalhe" in check, f"Check {i} missing 'detalhe'"
        
        print(f"✓ All {len(checks)} checks have valid structure")

    def test_checklist_empty_medicamento(self):
        """Test checklist with empty medicamento returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/dama/checklist",
            json={"medicamento": ""}
        )
        assert response.status_code == 400, f"Expected 400 for empty medicamento, got {response.status_code}"
        print("✓ Empty medicamento returns 400")

    def test_checklist_missing_medicamento(self):
        """Test checklist without medicamento field returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/dama/checklist",
            json={}
        )
        assert response.status_code == 400, f"Expected 400 for missing medicamento, got {response.status_code}"
        print("✓ Missing medicamento returns 400")


class TestProvaDocumental:
    """Tests for POST /api/dama/prova-documental endpoint"""

    def test_prova_documental_returns_pdf(self):
        """Test that prova-documental returns a valid PDF"""
        response = requests.post(
            f"{BASE_URL}/api/dama/prova-documental",
            json={
                "medicamento": "insulina",
                "fonte": "ANVISA/DOU",
                "titulo": "Teste de Prova Documental",
                "descricao": "Descricao do alerta de teste",
                "data_publicacao": "2026-01-15",
                "link": "https://www.gov.br/anvisa/teste",
                "tipo_alerta": "desabastecimento",
                "risco": "ALTO"
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:500]}"
        
        # Verify content type is PDF
        content_type = response.headers.get("Content-Type", "")
        assert "application/pdf" in content_type, f"Expected application/pdf, got {content_type}"
        
        # Verify Content-Disposition header
        content_disp = response.headers.get("Content-Disposition", "")
        assert "attachment" in content_disp, f"Expected attachment in Content-Disposition, got {content_disp}"
        assert "prova_documental" in content_disp, f"Expected 'prova_documental' in filename, got {content_disp}"
        
        # Verify PDF magic bytes
        pdf_content = response.content
        assert pdf_content.startswith(b"%PDF"), "Response should start with PDF magic bytes"
        assert len(pdf_content) > 1000, f"PDF should be larger than 1KB, got {len(pdf_content)} bytes"
        
        print(f"✓ Prova Documental PDF generated: {len(pdf_content)} bytes")

    def test_prova_documental_minimal_data(self):
        """Test prova-documental with minimal data"""
        response = requests.post(
            f"{BASE_URL}/api/dama/prova-documental",
            json={
                "medicamento": "teste_minimal"
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert response.content.startswith(b"%PDF"), "Should return valid PDF even with minimal data"
        print("✓ Prova Documental works with minimal data")

    def test_prova_documental_with_classificacao_dama(self):
        """Test prova-documental with classificacao_dama field"""
        response = requests.post(
            f"{BASE_URL}/api/dama/prova-documental",
            json={
                "medicamento": "ravulizumabe",
                "fonte": "DOU",
                "titulo": "Importacao Excepcional",
                "descricao": "Autorizacao de importacao excepcional",
                "data_publicacao": "2026-01-10",
                "link": "https://www.in.gov.br/teste",
                "tipo_alerta": "importacao excepcional",
                "risco": "MEDIO",
                "classificacao_dama": "importacao"
            }
        )
        
        assert response.status_code == 200
        assert response.content.startswith(b"%PDF")
        print("✓ Prova Documental with classificacao_dama works")


class TestIntegration:
    """Integration tests combining checklist and prova documental"""

    def test_checklist_then_prova(self):
        """Test workflow: run checklist, then generate prova for a result"""
        # Step 1: Run checklist
        checklist_resp = requests.post(
            f"{BASE_URL}/api/dama/checklist",
            json={"medicamento": "denosumabe"}
        )
        assert checklist_resp.status_code == 200
        checklist_data = checklist_resp.json()
        
        # Step 2: Generate prova documental based on checklist
        prova_resp = requests.post(
            f"{BASE_URL}/api/dama/prova-documental",
            json={
                "medicamento": checklist_data["medicamento"],
                "fonte": "GSM Checklist",
                "titulo": f"Checklist DAMA - {checklist_data['medicamento']}",
                "descricao": checklist_data.get("recomendacao", ""),
                "data_publicacao": checklist_data.get("executado_em", "")[:10],
                "tipo_alerta": "checklist",
                "risco": "ALTO" if checklist_data["score_conformidade"] < 50 else "BAIXO"
            }
        )
        
        assert prova_resp.status_code == 200
        assert prova_resp.content.startswith(b"%PDF")
        print(f"✓ Integration: Checklist (score={checklist_data['score_conformidade']}%) → PDF generated")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
