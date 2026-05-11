import requests

def test():
    # Endpoints que o Portal PNCP usa na "Busca Avançada"
    base = "https://pncp.gov.br/api/consulta/v1"
    
    print("--- Testando Busca por Itens ---")
    url_itens = f"{base}/itens/compra"
    params = {
        'pagina': 1,
        'tamanhoPagina': 10,
        'termo': 'canabidiol'
    }
    r = requests.get(url_itens, params=params)
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"Total: {data.get('totalRegistros')}")
        for item in data.get('data', [])[:3]:
            print(f"- Item: {item.get('materialOuServicoNome')} | Compra: {item.get('numeroControlePNCP')}")

if __name__ == "__main__":
    test()
