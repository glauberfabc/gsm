import requests

def test():
    url = "https://pncp.gov.br/api/search/"
    
    print("--- Testando tipos_documento=edital ---")
    params = {'q': 'canabidiol', 'tipos_documento': 'edital', 'pagina': 1}
    r = requests.get(url, params=params)
    if r.status_code == 200:
        print(f"Total Editais: {r.json().get('total')}")
    
    print("\n--- Testando tipos_documento=item ---")
    params = {'q': 'canabidiol', 'tipos_documento': 'item', 'pagina': 1}
    r = requests.get(url, params=params)
    if r.status_code == 200:
        data = r.json()
        print(f"Total Itens: {data.get('total')}")
        for item in data.get('items', [])[:3]:
            print(f"- Item de: {item.get('orgao_nome')}")

if __name__ == "__main__":
    test()
