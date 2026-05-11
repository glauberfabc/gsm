import requests
import json
import time

def test_unified_search_insulina():
    url = "http://127.0.0.1:8000/api/search/unified"
    params = {
        'q': 'insulina',
        'limit': 500
    }
    
    print(f"Buscando '{params['q']}' no motor independente (backend)...")
    inicio = time.time()
    try:
        r = requests.get(url, params=params, timeout=60)
        duracao = time.time() - inicio
        print(f"Status: {r.status_code} ({duracao:.2f}s)")
        
        if r.status_code == 200:
            data = r.json()
            total = data.get('total', 0)
            resultados = data.get('resultados', [])
            print(f"Total encontrado pelo GSM: {total}")
            print(f"Total de itens na lista: {len(resultados)}")
            
            if total >= 374:
                print("✅ SUCESSO: GSM capturou todos os 374+ resultados!")
            else:
                print(f"❌ AVISO: GSM ainda está em {total}, abaixo dos 374 esperados.")
    except Exception as e:
        print(f"Erro: {e}")

if __name__ == "__main__":
    test_unified_search_insulina()
