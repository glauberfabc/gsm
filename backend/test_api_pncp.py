import requests
import json

def test():
    url = "https://pncp.gov.br/pncp-api/v1/consultas/compras"
    params = {
        'pagina': 1,
        'tamanhoPagina': 10,
        'termo': 'canabidiol',
        'tiposDocumento': '1'
    }
    r = requests.get(url, params=params)
    print(f"Status Compras: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"Total Compras: {data.get('totalRegistros')}")
        for item in data.get('data', []):
            print(f"- {item.get('objeto')[:100]}")

    url_item = "https://pncp.gov.br/pncp-api/v1/consultas/compras/itens"
    params_item = {
        'pagina': 1,
        'tamanhoPagina': 10,
        'termo': 'canabidiol'
    }
    r = requests.get(url_item, params=params_item)
    print(f"\nStatus Itens: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"Total Itens: {data.get('totalRegistros')}")
        for item in data.get('data', []):
            print(f"- {item.get('objeto')[:100]}")

if __name__ == "__main__":
    test()
