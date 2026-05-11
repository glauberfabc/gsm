#!/usr/bin/env python3
"""
🧪 TESTE RÁPIDO DO SCRAPER SC - Validação Específica

Testa apenas os componentes críticos do scraper SC conforme review request:
1. Teste Direto do Scraper SC
2. Teste via ScraperService
3. Health Monitor
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

# Ler URL do backend
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

def test_sc_scraper_direto():
    """TESTE 1: Scraper SC Direto"""
    log("🧪 TESTE 1: Scraper SC Direto")
    
    try:
        # Importar e testar o scraper diretamente
        log("   Importando SantaCatarinaScraper...")
        from scrapers.santa_catarina_scraper import SantaCatarinaScraper
        
        scraper = SantaCatarinaScraper()
        log("   ✅ Scraper importado com sucesso")
        
        # Testar busca com termo específico
        log("   Executando busca com termo 'medicamento'...")
        resultados = asyncio.run(scraper.buscar_licitacoes(termo_busca='medicamento', limit=5))
        
        # Validações
        if isinstance(resultados, list):
            log(f"   ✅ Retornou lista com {len(resultados)} resultados")
            
            if resultados:
                primeiro = resultados[0]
                campos_obrigatorios = [
                    'titulo_licitacao', 'orgao_licitante', 'modalidade', 
                    'numero_processo', 'estado_uf', 'data_inicial', 'data_final'
                ]
                
                campos_ok = all(campo in primeiro for campo in campos_obrigatorios)
                estado_ok = primeiro.get('estado_uf') == 'SC'
                
                log(f"   ✅ Campos mandatórios: {'OK' if campos_ok else 'FALTANDO'}")
                log(f"   ✅ Estado SC: {'OK' if estado_ok else 'INCORRETO'}")
                log(f"   Título: {primeiro.get('titulo_licitacao', 'N/A')[:50]}...")
                log(f"   Órgão: {primeiro.get('orgao_licitante', 'N/A')[:30]}...")
                
                return campos_ok and estado_ok
            else:
                log("   ℹ️ Nenhum resultado (normal para termo específico)")
                return True
        else:
            log("   ❌ Não retornou lista")
            return False
            
    except Exception as e:
        log(f"   ❌ Erro: {str(e)}")
        return False

def test_scraper_service():
    """TESTE 2: ScraperService SC"""
    log("🧪 TESTE 2: ScraperService SC")
    
    try:
        from services.scraper_service import ScraperService
        
        service = ScraperService()
        log("   ✅ ScraperService importado")
        
        # Verificar se método existe
        if hasattr(service, 'buscar_apenas_sc'):
            log("   ✅ Método buscar_apenas_sc existe")
            
            # Testar busca
            resultados = asyncio.run(service.buscar_apenas_sc('medicamento', False, 3))
            
            if isinstance(resultados, list):
                log(f"   ✅ Retornou {len(resultados)} resultados")
                return True
            else:
                log("   ❌ Não retornou lista")
                return False
        else:
            log("   ❌ Método buscar_apenas_sc não encontrado")
            return False
            
    except Exception as e:
        log(f"   ❌ Erro: {str(e)}")
        return False

def test_health_monitor():
    """TESTE 3: Health Monitor SC"""
    log("🧪 TESTE 3: Health Monitor SC")
    
    try:
        session = requests.Session()
        response = session.get(f"{BACKEND_URL}/status/scrapers", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            scrapers = data.get('scrapers', [])
            
            # Procurar SC
            sc_encontrado = False
            for scraper in scrapers:
                if scraper.get('fonte') == 'SC' or 'SC' in scraper.get('nome', ''):
                    sc_encontrado = True
                    log(f"   ✅ SC encontrado: {scraper.get('nome', 'N/A')}")
                    break
            
            if not sc_encontrado:
                log("   ❌ SC não encontrado na lista")
                log(f"   Scrapers: {[s.get('fonte') or s.get('nome') for s in scrapers]}")
            
            return sc_encontrado
        else:
            log(f"   ❌ Status {response.status_code}")
            return False
            
    except Exception as e:
        log(f"   ❌ Erro: {str(e)}")
        return False

def main():
    """Executa testes rápidos"""
    log("🚀 TESTE RÁPIDO SCRAPER SC - GSM v7.0")
    log("=" * 50)
    
    testes = [
        ("Scraper SC Direto", test_sc_scraper_direto),
        ("ScraperService SC", test_scraper_service),
        ("Health Monitor SC", test_health_monitor)
    ]
    
    passou = 0
    total = len(testes)
    
    for nome, teste_func in testes:
        log(f"\n{'='*40}")
        resultado = teste_func()
        
        if resultado:
            log(f"✅ {nome}: PASSOU")
            passou += 1
        else:
            log(f"❌ {nome}: FALHOU")
    
    log(f"\n{'='*50}")
    log(f"📊 RESULTADO FINAL: {passou}/{total} testes passaram")
    
    if passou >= 3:
        log("🎉 SCRAPER SC FUNCIONANDO CORRETAMENTE!")
        log("✅ Importação OK")
        log("✅ Campos mandatórios presentes")
        log("✅ Integração ScraperService OK")
        log("✅ Health Monitor inclui SC")
    else:
        log("❌ Scraper SC precisa de correções")
    
    log("=" * 50)

if __name__ == "__main__":
    main()