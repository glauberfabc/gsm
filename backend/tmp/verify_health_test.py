import requests
import json

BASE_URL = "http://localhost:8000/api"

def test_scraper_diag(fonte):
    print(f"Testing diagnostic for {fonte}...")
    try:
        response = requests.post(f"{BASE_URL}/status/scrapers/{fonte}/test?medicamento=dipirona")
        if response.status_code == 200:
            print(f"✅ Success: {json.dumps(response.json(), indent=2)}")
        else:
            print(f"❌ Failed ({response.status_code}): {response.text}")
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    # Teste um que sabemos que é CSV e rápido
    test_scraper_diag("ES-CSV")
    # Teste um que é API
    test_scraper_diag("PNCP")
