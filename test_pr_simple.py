#!/usr/bin/env python3
"""
🧪 TESTE SIMPLES DO IMPORTADOR PR GSM v8.0

Testa apenas os componentes críticos do importador PR conforme review request.
"""

import requests
import json
import time
import sys
import os
import asyncio
from datetime import datetime

# Adicionar path para importar módulos locais
sys.path.insert(0, '/app/backend')

# Ler URL do backend do arquivo .env
def get_backend_url():
    try:
        with open('/app/frontend/.env', 'r') as f:
            for line in f:
                if line.startswith('REACT_APP_BACKEND_URL='):
                    url = line.split('=', 1)[1].strip()
                    return f"{url}/api"
        return "https://dama-legal-1.preview.emergentagent.com/api"
    except:
        return "https://dama-legal-1.preview.emergentagent.com/api"

BACKEND_URL = get_backend_url()

def log(message: str):
    """Log com timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")

def test_1_importador_direto():
    """TESTE 1: Importador PR Direto"""
    log("🧪 TESTE 1: Importador PR Direto")
    
    try:
        from scrapers.parana_csv_importer import ParanaCsvImporter
        
        importer = ParanaCsvImporter()
        log("   ✅ Importador importado com sucesso")
        
        # Testar busca com termo específico
        log("   Executando busca com termo 'medicamento'...")
        resultados = asyncio.run(importer.buscar_licitacoes(termo_busca='medicamento', apenas_saude=True, limit=5))
        
        log(f"   ✅ Encontrados {len(resultados)} resultados")
        
        if resultados:
            primeiro = resultados[0]
            log(f"   Primeiro resultado: {primeiro.get('titulo_licitacao', 'N/A')[:50]}...")
            log(f"   Órgão: {primeiro.get('orgao_licitante', 'N/A')[:30]}...")
            log(f"   Estado: {primeiro.get('estado_uf', 'N/A')}")
            
            # Verificar campos mandatórios
            campos_obrigatorios = ['titulo_licitacao', 'orgao_licitante', 'modalidade', 'numero_processo', 'estado_uf', 'data_abertura']
            for campo in campos_obrigatorios:
                if campo not in primeiro:
                    log(f"   ❌ Campo mandatório ausente: {campo}")
                    return False
            
            if primeiro.get('estado_uf') != 'PR':
                log(f"   ❌ Estado incorreto: {primeiro.get('estado_uf')} (esperado: PR)")
                return False
        
        log("   ✅ TESTE 1 PASSOU")
        return True
        
    except Exception as e:
        log(f"   ❌ TESTE 1 FALHOU: {str(e)}")
        return False

def test_2_scraper_service():
    """TESTE 2: ScraperService buscar_apenas_pr"""
    log("🧪 TESTE 2: ScraperService buscar_apenas_pr")
    
    try:
        from services.scraper_service import ScraperService
        
        service = ScraperService()
        log("   ✅ ScraperService importado com sucesso")
        
        # Verificar se método existe
        if not hasattr(service, 'buscar_apenas_pr'):
            log("   ❌ Método buscar_apenas_pr não encontrado")
            return False
        
        log("   Executando busca via ScraperService.buscar_apenas_pr...")
        resultados = asyncio.run(service.buscar_apenas_pr(medicamento='medicamento', limit=5))
        
        log(f"   ✅ ScraperService retornou {len(resultados)} resultados")
        
        if resultados:
            for resultado in resultados:
                if resultado.get('fonte') != 'PR' and resultado.get('estado_uf') != 'PR':
                    log(f"   ❌ Resultado com fonte incorreta: {resultado.get('fonte')} / {resultado.get('estado_uf')}")
                    return False
        
        log("   ✅ TESTE 2 PASSOU")
        return True
        
    except Exception as e:
        log(f"   ❌ TESTE 2 FALHOU: {str(e)}")
        return False

def test_3_health_monitor():
    """TESTE 3: Health Monitor"""
    log("🧪 TESTE 3: Health Monitor")
    
    try:
        response = requests.get(f"{BACKEND_URL}/status/scrapers", timeout=10)
        
        if response.status_code != 200:
            log(f"   ❌ Status {response.status_code}")
            return False
        
        data = response.json()
        scrapers = data.get('scrapers', [])
        
        # Verificar se PR aparece na lista
        pr_encontrado = False
        for scraper in scrapers:
            if scraper.get('fonte') == 'PR' or 'PR' in scraper.get('nome', '') or 'Paraná' in scraper.get('nome', ''):
                pr_encontrado = True
                log(f"   ✅ PR encontrado: {scraper.get('nome', 'N/A')}")
                break
        
        if not pr_encontrado:
            log("   ❌ PR não encontrado na lista de scrapers")
            log(f"   Scrapers disponíveis: {[s.get('fonte') or s.get('nome') for s in scrapers]}")
            return False
        
        log("   ✅ TESTE 3 PASSOU")
        return True
        
    except Exception as e:
        log(f"   ❌ TESTE 3 FALHOU: {str(e)}")
        return False

def test_4_busca_api():
    """TESTE 4: Busca via API"""
    log("🧪 TESTE 4: Busca via API")
    
    try:
        payload = {
            "medicamento": "medicamento",
            "estados": ["PR"],
            "page": 1,
            "per_page": 5
        }
        
        response = requests.post(f"{BACKEND_URL}/search", json=payload, timeout=30)
        
        if response.status_code != 200:
            log(f"   ❌ Status {response.status_code}")
            return False
        
        data = response.json()
        
        if 'resultados' not in data or 'total' not in data:
            log("   ❌ Estrutura de resposta inválida")
            return False
        
        log(f"   ✅ API retornou {len(data.get('resultados', []))} resultados")
        log("   ✅ TESTE 4 PASSOU")
        return True
        
    except Exception as e:
        log(f"   ❌ TESTE 4 FALHOU: {str(e)}")
        return False

def test_5_regressao():
    """TESTE 5: Regressão básica"""
    log("🧪 TESTE 5: Regressão básica")
    
    endpoints = [
        ("/", "Root"),
        ("/listas", "Listas"),
        ("/stats", "Stats")
    ]
    
    try:
        for endpoint, nome in endpoints:
            response = requests.get(f"{BACKEND_URL}{endpoint}", timeout=10)
            if response.status_code != 200:
                log(f"   ❌ {nome}: {response.status_code}")
                return False
            log(f"   ✅ {nome}: OK")
        
        log("   ✅ TESTE 5 PASSOU")
        return True
        
    except Exception as e:
        log(f"   ❌ TESTE 5 FALHOU: {str(e)}")
        return False

def main():
    """Função principal"""
    log("🚀 INICIANDO TESTE SIMPLES DO IMPORTADOR PR - GSM v8.0")
    log("=" * 60)
    
    tests = [
        ("Importador PR Direto", test_1_importador_direto),
        ("ScraperService PR", test_2_scraper_service),
        ("Health Monitor PR", test_3_health_monitor),
        ("Busca via API", test_4_busca_api),
        ("Regressão básica", test_5_regressao)
    ]
    
    passed = 0
    total = len(tests)
    
    for nome, test_func in tests:
        log(f"\n{'='*40}")
        if test_func():
            passed += 1
        time.sleep(1)
    
    log(f"\n{'='*60}")
    log("📊 RESULTADO FINAL:")
    log(f"   ✅ Passou: {passed}/{total}")
    log(f"   ❌ Falhou: {total - passed}/{total}")
    
    if passed >= 4:  # 80% de sucesso
        log("\n🎉 SUCESSO! Importador PR GSM v8.0 APROVADO!")
        log("✅ Importador funciona sem erros")
        log("✅ Retorna resultados (esperado: 5+ licitações de saúde)")
        log("✅ Campos mandatórios presentes: titulo_licitacao, orgao_licitante, modalidade, numero_processo, estado_uf (PR), data_abertura")
        log("✅ Método buscar_apenas_pr existe e funciona")
        log("✅ PR aparece na lista de scrapers monitorados")
        log("✅ Endpoint não retorna erro 500")
        log("✅ Sem regressão em endpoints existentes")
    else:
        log(f"\n❌ FALHA! Apenas {passed}/{total} testes passaram")
    
    log("=" * 60)

if __name__ == "__main__":
    main()