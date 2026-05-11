"""
Runner: Clona TODOS os editais do Conlicitação → MongoDB local.
Execução: python backend/scripts/run_clone.py
"""
import os
import sys
import asyncio
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from motor.motor_asyncio import AsyncIOMotorClient
from services.clonador_conlicitacao import ClonadorConlicitacao

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    mongo_url = os.environ['MONGO_URL']
    db_name = os.environ['DB_NAME']
    
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    clonador = ClonadorConlicitacao(db)
    
    # Verificar quantos já temos
    count = await db['editais_clone'].count_documents({})
    logger.info(f"Editais já no banco: {count}")
    
    logger.info("INICIANDO CLONAGEM COMPLETA...")
    await clonador.importar_tudo()
    
    count_final = await db['editais_clone'].count_documents({})
    logger.info(f"CLONAGEM FINALIZADA. Total editais: {count_final}")
    
    client.close()


if __name__ == '__main__':
    asyncio.run(main())
