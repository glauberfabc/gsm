import asyncio
import logging
import sys
import os

# Adicionar o diretório backend ao path
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), 'backend')))

from services.motor_independente import MotorBuscaIndependente

async def test_search():
    logging.basicConfig(level=logging.ERROR) # Use ERROR for cleaner output
    motor = MotorBuscaIndependente()
    
    print("Buscando 'canabidiol' no Motor Independente...")
    try:
        result = await motor.buscar("canabidiol", limit=50)
        print(f"Total encontrado: {result['total']}")
        for i, r in enumerate(result['resultados'][:10]):
            print(f"{i+1}. {r['objeto'][:100]}... ({r['fonte']})")
    except Exception as e:
        print(f"ERRO NA BUSCA: {e}")

if __name__ == "__main__":
    asyncio.run(test_search())
