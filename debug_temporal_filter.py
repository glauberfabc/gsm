#!/usr/bin/env python3
"""
Debug script to understand temporal filter behavior
"""

import requests
import json
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

def debug_temporal_filter():
    print("🔍 DEBUG: Temporal Filter Analysis")
    print("=" * 50)
    
    # Test search without history
    print("\n1. Testing search WITHOUT history (should apply temporal filter)")
    response = requests.get(f"{BACKEND_URL}/search/local", params={
        "q": "canabidiol",
        "limit": 10,
        "incluir_historico": False
    })
    
    if response.status_code == 200:
        data = response.json()
        print(f"   Results: {len(data.get('resultados', []))}")
        print(f"   Total: {data.get('total', 0)}")
        print(f"   incluir_historico: {data.get('filtros_ativos', {}).get('incluir_historico')}")
        print(f"   periodo_dias: {data.get('filtros_ativos', {}).get('periodo_dias')}")
        
        # Analyze dates in results
        hoje = datetime.now()
        limite_90_dias = hoje - timedelta(days=90)
        
        print(f"\n   Date analysis (today: {hoje.strftime('%Y-%m-%d')}, limit: {limite_90_dias.strftime('%Y-%m-%d')}):")
        
        for i, resultado in enumerate(data.get('resultados', [])[:5]):
            pub_str = resultado.get('data_publicacao', 'N/A')
            ab_str = resultado.get('data_abertura', 'N/A')
            
            print(f"   Result {i+1}:")
            print(f"     Object: {resultado.get('objeto', 'N/A')[:50]}...")
            print(f"     Pub date: {pub_str}")
            print(f"     Open date: {ab_str}")
            
            # Check if meets criteria
            meets_pub_criteria = False
            meets_open_criteria = False
            
            if pub_str and pub_str != 'N/A':
                try:
                    pub_date = datetime.fromisoformat(pub_str.replace('Z', '').split('T')[0])
                    meets_pub_criteria = pub_date >= limite_90_dias.replace(tzinfo=None)
                    print(f"     Pub criteria: {meets_pub_criteria} (date: {pub_date.strftime('%Y-%m-%d')})")
                except:
                    print(f"     Pub criteria: ERROR parsing date")
            
            if ab_str and ab_str != 'N/A':
                try:
                    ab_date = datetime.fromisoformat(ab_str.replace('Z', '').split('T')[0])
                    meets_open_criteria = ab_date >= hoje.replace(tzinfo=None)
                    print(f"     Open criteria: {meets_open_criteria} (date: {ab_date.strftime('%Y-%m-%d')})")
                except:
                    print(f"     Open criteria: ERROR parsing date")
            
            should_be_included = meets_pub_criteria or meets_open_criteria
            print(f"     Should be included: {should_be_included}")
            print()
    
    # Test search WITH history
    print("\n2. Testing search WITH history (should NOT apply temporal filter)")
    response = requests.get(f"{BACKEND_URL}/search/local", params={
        "q": "canabidiol",
        "limit": 10,
        "incluir_historico": True
    })
    
    if response.status_code == 200:
        data = response.json()
        print(f"   Results: {len(data.get('resultados', []))}")
        print(f"   Total: {data.get('total', 0)}")
        print(f"   incluir_historico: {data.get('filtros_ativos', {}).get('incluir_historico')}")

if __name__ == "__main__":
    debug_temporal_filter()