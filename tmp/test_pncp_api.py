import requests
import json

def test_pncp():
    url = "https://pncp.gov.br/api/search/"
    # Testar se aceita tamanhoPagina para trazer mais de 10 por vez
    params = {
        'q': 'insulina',
        'tipos_documento': 'edital',
        'status': 'recebendo_proposta',
        'pagina': 1,
        'tamanhoPagina': 50 # Tentando 50 por página
    }
    
    r = requests.get(url, params=params)
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        items = data.get('items', [])
        total = data.get('total', 0)
        print(f"Total reportado: {total}")
        print(f"Items nesta pagina (com tamanhoPagina=50): {len(items)}")
        
        # Testar sem o parametro para ver o padrao
        params.pop('tamanhoPagina')
        r2 = requests.get(url, params=params)
        data2 = r2.json()
        print(f"Items nesta pagina (padrao): {len(data2.get('items', []))}")

if __name__ == "__main__":
    test_pncp()
