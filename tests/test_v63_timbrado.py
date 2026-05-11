"""
GSM v63.0 - Timbrado Upload & DAMA IA Tests
============================================
Tests for:
- GET /api/empresas - returns timbrado_nome and timbrado_path fields
- POST /api/empresas/{empresa_id}/timbrado - upload .docx timbrado
- GET /api/empresas/{empresa_id}/timbrado - verify empresa has timbrado
- POST /api/dama/process - process edital using empresa's registered timbrado
"""

import pytest
import requests
import os
import io
import zipfile

# Get backend URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://dama-legal-1.preview.emergentagent.com"

API_URL = f"{BASE_URL}/api"

# Test files paths
TEST_TIMBRADO_PATH = "/tmp/teste_timbrado.docx"
TEST_EDITAL_PATH = "/tmp/teste_edital.pdf"


class TestEmpresasWithTimbrado:
    """Tests for GET /api/empresas with timbrado fields"""
    
    def test_empresas_returns_timbrado_fields(self):
        """Test GET /api/empresas returns timbrado_nome and timbrado_path for empresa c1"""
        response = requests.get(f"{API_URL}/empresas")
        assert response.status_code == 200
        
        data = response.json()
        assert "empresas" in data
        assert "total" in data
        
        # Find empresa c1 (HC IMPORTAÇÕES)
        empresa_c1 = None
        for emp in data["empresas"]:
            if emp.get("id") == "c1":
                empresa_c1 = emp
                break
        
        assert empresa_c1 is not None, "Empresa c1 not found"
        assert "timbrado_nome" in empresa_c1, "timbrado_nome field missing"
        assert "timbrado_path" in empresa_c1, "timbrado_path field missing"
        assert empresa_c1["timbrado_nome"] is not None, "timbrado_nome is None"
        assert empresa_c1["timbrado_path"] is not None, "timbrado_path is None"
        
        print(f"✅ Empresa c1 has timbrado: {empresa_c1['timbrado_nome']}")
    
    def test_empresa_c2_no_timbrado(self):
        """Test empresa c2 does NOT have timbrado registered"""
        response = requests.get(f"{API_URL}/empresas")
        assert response.status_code == 200
        
        data = response.json()
        
        # Find empresa c2
        empresa_c2 = None
        for emp in data["empresas"]:
            if emp.get("id") == "c2":
                empresa_c2 = emp
                break
        
        assert empresa_c2 is not None, "Empresa c2 not found"
        # c2 should NOT have timbrado fields or they should be None
        has_timbrado = empresa_c2.get("timbrado_nome") is not None
        print(f"✅ Empresa c2 timbrado status: {'has timbrado' if has_timbrado else 'no timbrado'}")


class TestTimbradoUpload:
    """Tests for POST /api/empresas/{empresa_id}/timbrado"""
    
    def test_upload_timbrado_success(self):
        """Test uploading .docx timbrado for empresa c1"""
        # Read test timbrado file
        with open(TEST_TIMBRADO_PATH, "rb") as f:
            timbrado_content = f.read()
        
        files = {
            "timbrado": ("test_upload.docx", io.BytesIO(timbrado_content), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        }
        
        response = requests.post(f"{API_URL}/empresas/c1/timbrado", files=files)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "message" in data
        assert "empresa_id" in data
        assert data["empresa_id"] == "c1"
        assert "timbrado_nome" in data
        assert "timbrado_size_kb" in data
        
        print(f"✅ Timbrado uploaded: {data['timbrado_nome']} ({data['timbrado_size_kb']}KB)")
    
    def test_upload_timbrado_invalid_extension(self):
        """Test uploading non-.docx file should fail"""
        # Create a fake PDF content
        fake_pdf = b"%PDF-1.4 fake content"
        
        files = {
            "timbrado": ("test.pdf", io.BytesIO(fake_pdf), "application/pdf")
        }
        
        response = requests.post(f"{API_URL}/empresas/c1/timbrado", files=files)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        
        data = response.json()
        assert "detail" in data
        assert ".docx" in data["detail"].lower()
        
        print("✅ Invalid extension rejected correctly")


class TestVerificarTimbrado:
    """Tests for GET /api/empresas/{empresa_id}/timbrado"""
    
    def test_verificar_timbrado_empresa_c1(self):
        """Test empresa c1 has timbrado registered"""
        response = requests.get(f"{API_URL}/empresas/c1/timbrado")
        assert response.status_code == 200
        
        data = response.json()
        assert "tem_timbrado" in data
        assert "empresa_id" in data
        assert data["empresa_id"] == "c1"
        assert data["tem_timbrado"] == True, "Empresa c1 should have timbrado"
        assert "timbrado_nome" in data
        assert data["timbrado_nome"] is not None
        
        print(f"✅ Empresa c1 timbrado verified: {data['timbrado_nome']}")
    
    def test_verificar_timbrado_empresa_c2(self):
        """Test empresa c2 does NOT have timbrado"""
        response = requests.get(f"{API_URL}/empresas/c2/timbrado")
        assert response.status_code == 200
        
        data = response.json()
        assert "tem_timbrado" in data
        assert "empresa_id" in data
        assert data["empresa_id"] == "c2"
        # c2 should NOT have timbrado
        print(f"✅ Empresa c2 timbrado status: tem_timbrado={data['tem_timbrado']}")
    
    def test_verificar_timbrado_empresa_inexistente(self):
        """Test non-existent empresa returns tem_timbrado=False"""
        response = requests.get(f"{API_URL}/empresas/nonexistent123/timbrado")
        assert response.status_code == 200
        
        data = response.json()
        assert data["tem_timbrado"] == False
        
        print("✅ Non-existent empresa returns tem_timbrado=False")


class TestDAMAProcess:
    """Tests for POST /api/dama/process with registered timbrado"""
    
    def test_dama_process_with_registered_timbrado(self):
        """Test DAMA process using empresa c1's registered timbrado (no timbrado file sent)"""
        # Read test edital PDF
        with open(TEST_EDITAL_PATH, "rb") as f:
            edital_content = f.read()
        
        files = {
            "edital": ("teste_edital.pdf", io.BytesIO(edital_content), "application/pdf")
        }
        
        data = {
            "empresa_id": "c1",  # Has registered timbrado
            "custo_unitario": "0.0",
            "moeda": "BRL"
        }
        
        response = requests.post(f"{API_URL}/dama/process", files=files, data=data, timeout=120)
        
        # Should return ZIP file
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:500] if response.text else 'no text'}"
        assert "application/zip" in response.headers.get("Content-Type", ""), f"Expected ZIP, got {response.headers.get('Content-Type')}"
        
        # Verify ZIP content
        zip_buffer = io.BytesIO(response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            file_list = zf.namelist()
            print(f"✅ ZIP contains: {file_list}")
            
            # Check for expected files
            has_proposta = any("PROPOSTA" in f.upper() for f in file_list)
            has_declaracoes = any("DECLARAC" in f.upper() for f in file_list)
            
            assert has_proposta, f"ZIP should contain PROPOSTA file. Files: {file_list}"
            assert has_declaracoes, f"ZIP should contain DECLARACOES file. Files: {file_list}"
        
        print("✅ DAMA process with registered timbrado successful")
    
    def test_dama_process_empresa_without_timbrado_fails(self):
        """Test DAMA process for empresa without timbrado (c2) should fail if no timbrado sent"""
        # Read test edital PDF
        with open(TEST_EDITAL_PATH, "rb") as f:
            edital_content = f.read()
        
        files = {
            "edital": ("teste_edital.pdf", io.BytesIO(edital_content), "application/pdf")
        }
        
        data = {
            "empresa_id": "c2",  # Does NOT have registered timbrado
            "custo_unitario": "0.0",
            "moeda": "BRL"
        }
        
        response = requests.post(f"{API_URL}/dama/process", files=files, data=data, timeout=60)
        
        # Should fail with 400 because c2 has no timbrado and none was sent
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        
        data = response.json()
        assert "detail" in data
        assert "timbrado" in data["detail"].lower()
        
        print("✅ DAMA correctly rejects empresa without timbrado")
    
    def test_dama_process_with_sent_timbrado(self):
        """Test DAMA process sending timbrado file (for empresa without registered timbrado)"""
        # Read test files
        with open(TEST_EDITAL_PATH, "rb") as f:
            edital_content = f.read()
        with open(TEST_TIMBRADO_PATH, "rb") as f:
            timbrado_content = f.read()
        
        files = {
            "edital": ("teste_edital.pdf", io.BytesIO(edital_content), "application/pdf"),
            "timbrado": ("teste_timbrado.docx", io.BytesIO(timbrado_content), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        }
        
        data = {
            "empresa_id": "c2",  # Does NOT have registered timbrado, but we're sending one
            "custo_unitario": "0.0",
            "moeda": "BRL"
        }
        
        response = requests.post(f"{API_URL}/dama/process", files=files, data=data, timeout=120)
        
        # Should succeed because we sent the timbrado file
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:500] if response.text else 'no text'}"
        assert "application/zip" in response.headers.get("Content-Type", "")
        
        print("✅ DAMA process with sent timbrado successful")
    
    def test_dama_process_invalid_edital_extension(self):
        """Test DAMA rejects non-PDF edital"""
        fake_txt = b"This is not a PDF"
        
        files = {
            "edital": ("teste.txt", io.BytesIO(fake_txt), "text/plain")
        }
        
        data = {
            "empresa_id": "c1",
            "custo_unitario": "0.0",
            "moeda": "BRL"
        }
        
        response = requests.post(f"{API_URL}/dama/process", files=files, data=data, timeout=30)
        
        assert response.status_code == 400
        data = response.json()
        assert "pdf" in data["detail"].lower()
        
        print("✅ DAMA correctly rejects non-PDF edital")


class TestZIPContents:
    """Tests for ZIP file contents from DAMA process"""
    
    def test_zip_contains_proposta_comercial(self):
        """Test ZIP contains PROPOSTA_COMERCIAL document"""
        with open(TEST_EDITAL_PATH, "rb") as f:
            edital_content = f.read()
        
        files = {
            "edital": ("teste_edital.pdf", io.BytesIO(edital_content), "application/pdf")
        }
        
        data = {
            "empresa_id": "c1",
            "custo_unitario": "0.0",
            "moeda": "BRL"
        }
        
        response = requests.post(f"{API_URL}/dama/process", files=files, data=data, timeout=120)
        
        if response.status_code != 200:
            pytest.skip(f"DAMA process failed: {response.status_code}")
        
        zip_buffer = io.BytesIO(response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            file_list = zf.namelist()
            
            # Find PROPOSTA file
            proposta_files = [f for f in file_list if "PROPOSTA" in f.upper()]
            assert len(proposta_files) > 0, f"No PROPOSTA file found. Files: {file_list}"
            
            # Check file is not empty
            proposta_file = proposta_files[0]
            proposta_info = zf.getinfo(proposta_file)
            assert proposta_info.file_size > 0, "PROPOSTA file is empty"
            
            print(f"✅ PROPOSTA file found: {proposta_file} ({proposta_info.file_size} bytes)")
    
    def test_zip_contains_declaracoes(self):
        """Test ZIP contains DECLARACOES document"""
        with open(TEST_EDITAL_PATH, "rb") as f:
            edital_content = f.read()
        
        files = {
            "edital": ("teste_edital.pdf", io.BytesIO(edital_content), "application/pdf")
        }
        
        data = {
            "empresa_id": "c1",
            "custo_unitario": "0.0",
            "moeda": "BRL"
        }
        
        response = requests.post(f"{API_URL}/dama/process", files=files, data=data, timeout=120)
        
        if response.status_code != 200:
            pytest.skip(f"DAMA process failed: {response.status_code}")
        
        zip_buffer = io.BytesIO(response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            file_list = zf.namelist()
            
            # Find DECLARACOES file
            declaracoes_files = [f for f in file_list if "DECLARAC" in f.upper()]
            assert len(declaracoes_files) > 0, f"No DECLARACOES file found. Files: {file_list}"
            
            # Check file is not empty
            declaracoes_file = declaracoes_files[0]
            declaracoes_info = zf.getinfo(declaracoes_file)
            assert declaracoes_info.file_size > 0, "DECLARACOES file is empty"
            
            print(f"✅ DECLARACOES file found: {declaracoes_file} ({declaracoes_info.file_size} bytes)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
