#!/usr/bin/env python3
"""
Detailed debug of temporal filter logic
"""

import requests
from datetime import datetime, timedelta

# Get backend URL
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

def debug_temporal_detailed():
    print("🔍 DETAILED DEBUG: Temporal Filter Logic")
    print("=" * 60)
    
    # Get results without history
    response = requests.get(f"{BACKEND_URL}/search/local", params={
        "q": "canabidiol",
        "limit": 30,
        "incluir_historico": False
    })
    
    if response.status_code != 200:
        print(f"❌ Error: {response.status_code}")
        return
    
    data = response.json()
    resultados = data.get('resultados', [])
    
    hoje = datetime.now()
    limite_90_dias = hoje - timedelta(days=90)
    
    print(f"Today: {hoje.strftime('%Y-%m-%d')}")
    print(f"90-day limit: {limite_90_dias.strftime('%Y-%m-%d')}")
    print(f"Total results: {len(resultados)}")
    print()
    
    should_be_included = 0
    should_be_excluded = 0
    
    for i, resultado in enumerate(resultados):
        pub_str = resultado.get('data_publicacao')
        ab_str = resultado.get('data_abertura')
        
        print(f"Result {i+1}:")
        print(f"  Object: {resultado.get('objeto', 'N/A')[:50]}...")
        print(f"  Pub date: {pub_str}")
        print(f"  Open date: {ab_str}")
        
        # Parse dates
        pub_date = None
        ab_date = None
        
        if pub_str:
            try:
                pub_date = datetime.fromisoformat(pub_str.replace('Z', '').split('T')[0])
            except:
                pass
        
        if ab_str:
            try:
                ab_date = datetime.fromisoformat(ab_str.replace('Z', '').split('T')[0])
            except:
                pass
        
        # Check criteria
        meets_pub_criteria = pub_date and pub_date >= limite_90_dias
        meets_open_criteria = ab_date and ab_date >= hoje
        
        print(f"  Pub criteria (>= {limite_90_dias.strftime('%Y-%m-%d')}): {meets_pub_criteria}")
        print(f"  Open criteria (>= {hoje.strftime('%Y-%m-%d')}): {meets_open_criteria}")
        
        should_include = meets_pub_criteria or meets_open_criteria
        print(f"  Should be included: {should_include}")
        
        if should_include:
            should_be_included += 1
        else:
            should_be_excluded += 1
            print(f"  ❌ THIS SHOULD BE EXCLUDED!")
        
        print()
    
    print(f"Summary:")
    print(f"  Should be included: {should_be_included}")
    print(f"  Should be excluded: {should_be_excluded}")
    
    if should_be_excluded > 0:
        print(f"❌ TEMPORAL FILTER IS NOT WORKING CORRECTLY!")
        print(f"   {should_be_excluded} processes should have been filtered out")
    else:
        print(f"✅ TEMPORAL FILTER IS WORKING CORRECTLY!")
        print(f"   All {should_be_included} processes meet the criteria")

if __name__ == "__main__":
    debug_temporal_detailed()