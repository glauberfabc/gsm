#!/usr/bin/env python3
"""
Script para criar índices no MongoDB

Otimiza performance de queries nas coleções principais.
Executa automaticamente no startup do backend.
"""

import asyncio
import os
import sys
from motor.motor_asyncio import AsyncIOMotorClient
import logging

# Adicionar path do backend
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_indexes():
    """
    Cria índices otimizados no MongoDB
    
    Índices criados:
    1. medicamento (texto) - busca principal
    2. estado (single) - filtro por UF
    3. status (single) - filtro por status
    4. data_final (single) - ordenação por urgência
    5. medicamento + estado (composto) - busca combinada
    6. fonte + is_mock (composto) - filtro de dados reais
    """
    try:
        # Conectar ao MongoDB
        mongo_url = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
        client = AsyncIOMotorClient(mongo_url)
        db = client['bem_db']
        
        logger.info("🗄️ Conectado ao MongoDB")
        logger.info("📊 Criando índices otimizados...")
        
        # Coleção de licitações
        collection = db.licitacoes
        
        # 1. Índice de texto em medicamento (busca full-text)
        logger.info("  📝 Criando índice de texto em 'medicamento'...")
        await collection.create_index(
            [("medicamento", "text"), ("objeto", "text")],
            name="idx_medicamento_text",
            default_language="portuguese"
        )
        
        # 2. Índice em estado (filtro comum)
        logger.info("  📍 Criando índice em 'estado'...")
        await collection.create_index(
            "estado",
            name="idx_estado"
        )
        
        # 3. Índice em status (filtro comum)
        logger.info("  🏷️ Criando índice em 'status'...")
        await collection.create_index(
            "status",
            name="idx_status"
        )
        
        # 4. Índice em data_final (ordenação por urgência)
        logger.info("  📅 Criando índice em 'data_final'...")
        await collection.create_index(
            "data_final",
            name="idx_data_final"
        )
        
        # 5. Índice em modalidade (filtro)
        logger.info("  📋 Criando índice em 'modalidade'...")
        await collection.create_index(
            "modalidade",
            name="idx_modalidade"
        )
        
        # 6. Índice em esfera (filtro)
        logger.info("  🌐 Criando índice em 'esfera'...")
        await collection.create_index(
            "esfera",
            name="idx_esfera"
        )
        
        # 7. Índice composto: medicamento + estado (query combinada)
        logger.info("  🔗 Criando índice composto 'medicamento + estado'...")
        await collection.create_index(
            [("medicamento", 1), ("estado", 1)],
            name="idx_medicamento_estado"
        )
        
        # 8. Índice composto: fonte + is_mock (filtro de dados reais)
        logger.info("  🔗 Criando índice composto 'fonte + is_mock'...")
        await collection.create_index(
            [("fonte", 1), ("is_mock", 1)],
            name="idx_fonte_mock"
        )
        
        # 9. Índice em id (busca por ID único)
        logger.info("  🆔 Criando índice em 'id'...")
        await collection.create_index(
            "id",
            name="idx_id",
            unique=True
        )
        
        # Listar índices criados
        logger.info("\n✅ Índices criados com sucesso!")
        logger.info("\n📋 Lista de índices ativos:")
        
        indexes = await collection.index_information()
        for idx_name, idx_info in indexes.items():
            keys = idx_info.get('key', [])
            logger.info(f"  • {idx_name}: {keys}")
        
        logger.info("\n🎯 Otimização concluída!")
        
        # Estatísticas
        stats = await db.command("collStats", "licitacoes")
        count = stats.get('count', 0)
        size_mb = stats.get('size', 0) / (1024 * 1024)
        
        logger.info(f"\n📊 Estatísticas da coleção:")
        logger.info(f"  Documentos: {count}")
        logger.info(f"  Tamanho: {size_mb:.2f} MB")
        logger.info(f"  Índices: {len(indexes)}")
        
    except Exception as e:
        logger.error(f"❌ Erro ao criar índices: {str(e)}")
        raise
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(create_indexes())
