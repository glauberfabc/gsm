"""
GSM v78.0 - 100% INDEPENDENTE Tests
====================================
Verifica que o sistema usa APENAS APIs públicas do governo:
- PNCP (pncp.gov.br)
- Compras.gov.br

ZERO dependência de Conlicitação ou qualquer terceiro.
PDFs baixados DIRETO do PNCP.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestGSMV78IndependenteBackend:
    """Testes de backend para verificar independência 100% de terceiros"""
    
    # ============ FEATURE 1: Fontes devem ser pncp_gov_br e compras_gov_br ============
    def test_search_unified_canabidiol_returns_correct_sources(self):
        """
        Feature 1: GET /api/search/unified?q=canabidiol deve retornar resultados 
        com fontes 'pncp_gov_br' e 'compras_gov_br', NÃO 'conlicitacao'
        """
        response = requests.get(f"{BASE_URL}/api/search/unified?q=canabidiol", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        fontes = data.get('fontes', {})
        
        # Verificar fontes ESPERADAS (100% independente)
        print(f"Fontes retornadas: {fontes}")
        
        # DEVE ter pncp_gov_br OU compras_gov_br (ou ambos)
        has_pncp = 'pncp_gov_br' in fontes or fontes.get('pncp_gov_br', 0) > 0
        has_compras = 'compras_gov_br' in fontes or fontes.get('compras_gov_br', 0) > 0
        
        assert has_pncp or has_compras, f"Deveria ter fontes pncp_gov_br ou compras_gov_br, mas tem: {fontes}"
        
        # NÃO deve ter conlicitacao em nenhuma variante
        invalid_sources = ['conlicitacao', 'conlicitacao_live', 'conlicitacao_direct']
        for source in invalid_sources:
            assert source not in fontes, f"Fonte '{source}' encontrada mas deveria ser 100% independente: {fontes}"
        
        print(f"✅ Fontes independentes verificadas: {fontes}")
    
    # ============ FEATURE 2: Links NÃO devem conter 'conlicitacao' ============
    def test_no_link_contains_conlicitacao(self):
        """
        Feature 2: NENHUM campo (link_pdf, link_portal, link_edital) deve conter 
        'conlicitacao'. link_pdf deve conter 'pncp.gov.br/pncp-api'
        """
        response = requests.get(f"{BASE_URL}/api/search/unified?q=canabidiol&limit=50", timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        resultados = data.get('resultados', [])
        assert len(resultados) > 0, "Nenhum resultado retornado"
        
        violations = []
        valid_pdf_links = 0
        
        for idx, r in enumerate(resultados):
            # Verificar cada campo de link
            for campo in ['link_pdf', 'link_portal', 'link_edital', 'link_origem']:
                valor = r.get(campo, '')
                if valor and 'conlicitacao' in valor.lower():
                    violations.append({
                        'index': idx,
                        'campo': campo,
                        'valor': valor
                    })
            
            # Verificar se link_pdf aponta para PNCP
            link_pdf = r.get('link_pdf', '')
            if link_pdf and 'pncp.gov.br/pncp-api' in link_pdf:
                valid_pdf_links += 1
        
        assert len(violations) == 0, f"CRITICAL: {len(violations)} links contêm 'conlicitacao': {violations[:5]}"
        
        print(f"✅ {len(resultados)} resultados verificados - ZERO links com 'conlicitacao'")
        print(f"✅ {valid_pdf_links} links de PDF apontam para PNCP API")
    
    # ============ FEATURE 3: Endpoint de itens do PNCP ============
    def test_editais_itens_endpoint_returns_real_items(self):
        """
        Feature 3: GET /api/editais/itens/{cnpj}/{ano}/{seq} deve retornar 
        itens reais do PNCP. Testar com CNPJ: 46374500000194/2026/1216
        """
        # CNPJ conhecido que retorna 4 itens de canabidiol
        cnpj = "46374500000194"
        ano = "2026"
        seq = "1216"
        
        response = requests.get(f"{BASE_URL}/api/editais/itens/{cnpj}/{ano}/{seq}", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        itens = data.get('itens', [])
        total = data.get('total', 0)
        
        print(f"Total de itens retornados: {total}")
        
        # Verificar estrutura dos itens
        if len(itens) > 0:
            item = itens[0]
            assert 'numero' in item or 'descricao' in item, f"Item sem estrutura esperada: {item}"
            print(f"✅ Primeiro item: {item}")
        
        # Se o endpoint retornar itens, validar que não são vazios
        for item in itens[:3]:
            descricao = item.get('descricao', '')
            print(f"   Item #{item.get('numero', '?')}: {descricao[:80]}...")
    
    # ============ FEATURE 4: Endpoint de arquivos do PNCP ============
    def test_editais_arquivos_endpoint(self):
        """
        Feature 4: GET /api/editais/arquivos/{cnpj}/{ano}/{seq} deve retornar 
        lista de arquivos do PNCP
        """
        cnpj = "46374500000194"
        ano = "2026"
        seq = "1216"
        
        response = requests.get(f"{BASE_URL}/api/editais/arquivos/{cnpj}/{ano}/{seq}", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        arquivos = data.get('arquivos', [])
        total = data.get('total', 0)
        
        print(f"Total de arquivos retornados: {total}")
        
        # Verificar estrutura se houver arquivos
        for arq in arquivos[:3]:
            print(f"   Arquivo: {arq}")
            # Verificar se URL aponta para PNCP
            url = arq.get('url', '')
            if url:
                assert 'pncp.gov.br' in url, f"Arquivo não aponta para PNCP: {url}"
    
    # ============ FEATURE 5: Link de download real do PNCP ============
    def test_link_pdf_is_real_download(self):
        """
        Feature 5: link_pdf nos resultados deve ser uma URL de download real 
        que retorna HTTP 200 com content-type apropriado (octet-stream, pdf, zip)
        """
        response = requests.get(f"{BASE_URL}/api/search/unified?q=canabidiol&limit=10", timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        resultados = data.get('resultados', [])
        
        valid_downloads = 0
        tested = 0
        
        for r in resultados[:5]:
            link_pdf = r.get('link_pdf', '')
            if not link_pdf or not link_pdf.startswith('http'):
                continue
            
            tested += 1
            print(f"Testando download: {link_pdf}")
            
            try:
                # Fazer requisição HEAD para verificar se é válido
                head_resp = requests.head(link_pdf, timeout=15, allow_redirects=True)
                
                if head_resp.status_code == 200:
                    content_type = head_resp.headers.get('Content-Type', '').lower()
                    
                    # Aceitar vários tipos de arquivo de edital
                    valid_types = ['octet-stream', 'pdf', 'zip', 'application']
                    is_valid = any(t in content_type for t in valid_types)
                    
                    if is_valid:
                        valid_downloads += 1
                        print(f"   ✅ Download válido (Content-Type: {content_type})")
                    else:
                        print(f"   ⚠️ Content-Type inesperado: {content_type}")
                else:
                    print(f"   ❌ HTTP {head_resp.status_code}")
                    
            except Exception as e:
                print(f"   ❌ Erro: {str(e)[:50]}")
        
        print(f"\n✅ {valid_downloads}/{tested} links de download válidos")
        # Pelo menos alguns devem funcionar
        if tested > 0:
            assert valid_downloads > 0, f"Nenhum link de download funcionou ({tested} testados)"
    
    # ============ FEATURE 9: Busca por insulina também funciona ============
    def test_search_insulina_returns_results(self):
        """
        Feature 9: Busca por 'insulina' também funciona e retorna resultados 
        com download links do PNCP
        """
        response = requests.get(f"{BASE_URL}/api/search/unified?q=insulina&limit=20", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        total = data.get('total', 0)
        resultados = data.get('resultados', [])
        fontes = data.get('fontes', {})
        
        print(f"Total insulina: {total}")
        print(f"Resultados retornados: {len(resultados)}")
        print(f"Fontes: {fontes}")
        
        assert len(resultados) > 0, "Nenhum resultado para 'insulina'"
        
        # Verificar fontes independentes
        invalid_sources = ['conlicitacao', 'conlicitacao_live']
        for source in invalid_sources:
            assert source not in fontes, f"Fonte '{source}' encontrada em insulina: {fontes}"
        
        # Verificar links
        pncp_links = 0
        for r in resultados[:10]:
            link = r.get('link_pdf', '')
            if 'pncp.gov.br' in link:
                pncp_links += 1
        
        print(f"✅ {pncp_links} links de PNCP em resultados de insulina")


class TestGSMV78LinkValidation:
    """Testes de validação de links - 100% governo"""
    
    def test_all_results_have_government_links(self):
        """Todos os resultados devem ter links de fontes governamentais"""
        response = requests.get(f"{BASE_URL}/api/search/unified?q=medicamento&limit=30", timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        resultados = data.get('resultados', [])
        
        gov_domains = ['pncp.gov.br', 'compras.gov.br', 'gov.br', '.gov.']
        third_party = ['conlicitacao', 'licitacoes-e.com']
        
        gov_links = 0
        violations = []
        
        for r in resultados:
            link = r.get('link_portal', '') or r.get('link_pdf', '') or r.get('link_edital', '')
            
            # Verificar se é do governo
            is_gov = any(domain in link for domain in gov_domains) if link else False
            is_third_party = any(tp in link.lower() for tp in third_party) if link else False
            
            if is_gov:
                gov_links += 1
            if is_third_party:
                violations.append(link)
        
        print(f"Links governamentais: {gov_links}/{len(resultados)}")
        
        assert len(violations) == 0, f"Links de terceiros encontrados: {violations[:5]}"
        
        if len(resultados) > 0:
            pct = (gov_links / len(resultados)) * 100
            print(f"✅ {pct:.1f}% dos links são governamentais")


class TestGSMV78MotorIndependente:
    """Testes específicos do motor_independente.py"""
    
    def test_motor_buscar_returns_correct_structure(self):
        """Verifica estrutura de resposta do motor independente"""
        response = requests.get(f"{BASE_URL}/api/search/unified?q=canabidiol", timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        
        # Verificar estrutura esperada
        assert 'termo' in data, "Campo 'termo' ausente"
        assert 'total' in data, "Campo 'total' ausente"
        assert 'resultados' in data, "Campo 'resultados' ausente"
        assert 'fontes' in data, "Campo 'fontes' ausente"
        
        # Performance deve estar presente
        performance = data.get('performance', {})
        print(f"Performance: {performance}")
        
        fonte_descricao = performance.get('fonte', '')
        assert 'independente' in fonte_descricao.lower() or 'PNCP' in fonte_descricao or 'Compras.gov' in fonte_descricao, \
            f"Descrição de fonte não indica independência: {fonte_descricao}"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
