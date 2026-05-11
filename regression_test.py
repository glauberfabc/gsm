#!/usr/bin/env python3
"""
🧪 TESTE DE REGRESSÃO - Endpoints Existentes

Verifica se endpoints críticos continuam funcionando após implementação do SC
"""

import requests
import json
import time
from datetime import datetime

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

def test_endpoints():
    """Testa endpoints críticos"""
    log("🧪 TESTE DE REGRESSÃO - Endpoints Existentes")
    
    session = requests.Session()
    session.headers.update({
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    })
    
    endpoints = [
        ("/", "GET", "Root endpoint"),
        ("/listas", "GET", "Listar listas"),
        ("/alertas", "GET", "Listar alertas"),
        ("/status/scrapers", "GET", "Status scrapers"),
        ("/stats", "GET", "Estatísticas"),
        ("/states", "GET", "Estados disponíveis")
    ]
    
    passou = 0
    total = len(endpoints)
    
    for endpoint, method, descricao in endpoints:
        try:
            log(f"   Testando {method} {endpoint}...")
            
            if method == "GET":
                resp = session.get(f"{BACKEND_URL}{endpoint}", timeout=10)
            else:
                resp = session.request(method, f"{BACKEND_URL}{endpoint}", timeout=10)
            
            if resp.status_code == 200:
                log(f"     ✅ {descricao}: OK")
                passou += 1
            else:
                log(f"     ❌ {descricao}: {resp.status_code}")
                
        except Exception as e:
            log(f"     ❌ {descricao}: Erro - {str(e)}")
    
    log(f"\n📊 RESULTADO: {passou}/{total} endpoints funcionando ({(passou/total)*100:.1f}%)")
    
    if passou >= total * 0.8:  # 80% devem funcionar
        log("✅ REGRESSÃO PASSOU - Endpoints críticos funcionando")
        return True
    else:
        log("❌ REGRESSÃO FALHOU - Muitos endpoints com problema")
        return False

def main():
    """Executa teste de regressão"""
    log("🚀 INICIANDO TESTE DE REGRESSÃO")
    log("=" * 50)
    
    resultado = test_endpoints()
    
    log("=" * 50)
    if resultado:
        log("🎉 TESTE DE REGRESSÃO APROVADO!")
    else:
        log("❌ TESTE DE REGRESSÃO REPROVADO!")

if __name__ == "__main__":
    main()