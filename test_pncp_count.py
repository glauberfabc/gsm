"""
Teste da correcao do motor_independente.py
Simula o fluxo de busca com status=recebendo_proposta + paginacao
"""
import requests
from datetime import datetime, timedelta

print("=" * 60)
print("TESTE: Simulando busca corrigida (status=recebendo_proposta + paginacao)")
print("=" * 60)

# Busca com status=recebendo_proposta e paginacao
all_items = []
total = 0

for pg in range(1, 11):
    r = requests.get('https://pncp.gov.br/api/search/', params={
        'q': 'canabidiol',
        'tipos_documento': 'edital',
        'status': 'recebendo_proposta',
        'ordenacao': '-data',
        'pagina': pg
    }, timeout=30)
    data = r.json()
    items = data.get('items', [])
    total = data.get('total', 0)
    if not items:
        break
    all_items.extend(items)
    print(f"  Pagina {pg}: {len(items)} items")

print(f"\nTotal reportado pela API: {total}")
print(f"Total capturado com paginacao: {len(all_items)}")

# Simular filtro de datas do _map_pncp
agora = datetime.now()
sobreviventes = 0
eliminados = 0
for it in all_items:
    data_fim = it.get('data_fim_vigencia', '')
    data_pub = it.get('data_publicacao_pncp', '')
    eliminar = False
    
    if data_fim:
        try:
            fim = datetime.fromisoformat(data_fim.replace('Z', '+00:00'))
            if fim.replace(tzinfo=None) < agora - timedelta(days=1):
                eliminar = True
        except:
            pass
    elif data_pub:
        try:
            pub = datetime.fromisoformat(data_pub.replace('Z', '+00:00'))
            if pub.replace(tzinfo=None) < agora - timedelta(days=90):
                eliminar = True
        except:
            pass
    
    if eliminar:
        eliminados += 1
    else:
        sobreviventes += 1

print(f"\nApos filtro de datas:")
print(f"  Sobreviventes (ativos): {sobreviventes}")
print(f"  Eliminados (vencidos): {eliminados}")

print()
print("=" * 60)
print("COMPARACAO:")
print(f"  Portal PNCP mostra: 30 (informado pelo usuario)")
print(f"  Motor ANTIGO (sem status, 1 pagina): ~9 resultados")
print(f"  Motor NOVO (com status, paginacao): {sobreviventes} resultados")
print("=" * 60)
