from fastapi import FastAPI, APIRouter, HTTPException, Query
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import sys

# Adicionar path para importar m\u00f3dulos locais
sys.path.insert(0, str(Path(__file__).parent))

from models.licitacao import Licitacao, LicitacaoCreate, SearchQuery
from services.scraper_service import ScraperService
from services.mock_data_service import MockDataService

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI(title="BEM - Buscador Estadual de Medicamentos")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Inicializar servi\u00e7os
scraper_service = ScraperService()
mock_service = MockDataService()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== ROTAS BEM ====================

@api_router.get("/")
async def root():
    return {
        "message": "BEM - Buscador Estadual de Medicamentos API",
        "version": "1.0.0",
        "endpoints": {
            "search": "/api/search",
            "states": "/api/states",
            "refresh": "/api/refresh",
            "stats": "/api/stats"
        }
    }

@api_router.post("/search")
async def search_medicamentos(query: SearchQuery):
    """Busca medicamentos nas bases estaduais"""
    try:
        logger.info(f"Buscando medicamento: {query.medicamento}")
        
        resultados = []
        
        # Buscar nos scrapers reais (CE, ES, SP)
        dados_reais = await scraper_service.buscar_medicamento(query.medicamento)
        resultados.extend(dados_reais)
        
        # Se n\u00e3o for apenas_reais, adicionar dados mockados
        if not query.apenas_reais:
            dados_mock = mock_service.gerar_dados_mock(query.medicamento, quantidade=10)
            resultados.extend(dados_mock)
        
        # Filtrar por estado se especificado
        if query.estado:
            resultados = [r for r in resultados if r['estado'] == query.estado]
        
        # Filtrar por tags se especificado
        if query.tags:
            resultados = [r for r in resultados if any(tag in r['tags'] for tag in query.tags)]
        
        # Salvar no MongoDB
        for resultado in resultados:
            # Verificar se j\u00e1 existe
            existing = await db.licitacoes.find_one({
                'medicamento': resultado['medicamento'],
                'estado': resultado['estado'],
                'numero_processo': resultado['numero_processo']
            })
            
            if not existing:
                # Converter datetime para ISO string para MongoDB
                doc = resultado.copy()
                doc['data_referencia'] = doc['data_referencia'].isoformat()
                doc['created_at'] = datetime.now().isoformat()
                doc['updated_at'] = datetime.now().isoformat()
                doc['id'] = str(uuid.uuid4())
                await db.licitacoes.insert_one(doc)
        
        logger.info(f"Encontrados {len(resultados)} resultados para {query.medicamento}")
        
        return {
            "total": len(resultados),
            "medicamento": query.medicamento,
            "resultados": resultados
        }
        
    except Exception as e:
        logger.error(f"Erro na busca: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao buscar medicamento: {str(e)}")

@api_router.get("/states")
async def get_states():
    """Retorna lista de estados com indica\u00e7\u00e3o de quais t\u00eam scraping real"""
    estados_reais = ['CE', 'ES', 'SP']
    estados_mock = [
        'AC', 'AL', 'AP', 'AM', 'BA', 'DF', 'GO', 'MA', 'MT', 'MS', 
        'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 
        'RR', 'SC', 'SE', 'TO'
    ]
    
    estados = []
    for uf in estados_reais:
        estados.append({
            'uf': uf,
            'nome': _get_estado_nome(uf),
            'has_scraping': True,
            'is_mock': False
        })
    
    for uf in estados_mock:
        estados.append({
            'uf': uf,
            'nome': _get_estado_nome(uf),
            'has_scraping': False,
            'is_mock': True
        })
    
    return {"estados": sorted(estados, key=lambda x: x['uf'])}

@api_router.post("/refresh/{estado}")
async def refresh_estado(estado: str, medicamento: str = Query(...)):
    """For\u00e7a refresh de dados de um estado espec\u00edfico"""
    try:
        if estado not in ['CE', 'ES', 'SP']:
            raise HTTPException(status_code=400, detail="Refresh dispon\u00edvel apenas para CE, ES e SP")
        
        logger.info(f"Refresh manual para {estado} - medicamento: {medicamento}")
        
        dados = await scraper_service.refresh_estado(estado, medicamento)
        
        return {
            "estado": estado,
            "medicamento": medicamento,
            "total": len(dados),
            "resultados": dados
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro no refresh: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar dados: {str(e)}")

@api_router.get("/stats")
async def get_stats():
    """Retorna estat\u00edsticas gerais do sistema"""
    try:
        total_licitacoes = await db.licitacoes.count_documents({})
        total_reais = await db.licitacoes.count_documents({'is_mock': False})
        total_mock = await db.licitacoes.count_documents({'is_mock': True})
        
        # Contagem por estado
        pipeline = [
            {'$group': {'_id': '$estado', 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}}
        ]
        por_estado = await db.licitacoes.aggregate(pipeline).to_list(27)
        
        return {
            "total_licitacoes": total_licitacoes,
            "licitacoes_reais": total_reais,
            "licitacoes_mock": total_mock,
            "por_estado": [{'estado': item['_id'], 'total': item['count']} for item in por_estado],
            "estados_com_scraping": ['CE', 'ES', 'SP']
        }
        
    except Exception as e:
        logger.error(f"Erro ao buscar estat\u00edsticas: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao buscar estat\u00edsticas: {str(e)}")


def _get_estado_nome(uf: str) -> str:
    """Retorna nome completo do estado"""
    estados = {
        'AC': 'Acre', 'AL': 'Alagoas', 'AP': 'Amapá', 'AM': 'Amazonas',
        'BA': 'Bahia', 'CE': 'Ceará', 'DF': 'Distrito Federal', 'ES': 'Espírito Santo',
        'GO': 'Goiás', 'MA': 'Maranhão', 'MT': 'Mato Grosso', 'MS': 'Mato Grosso do Sul',
        'MG': 'Minas Gerais', 'PA': 'Pará', 'PB': 'Paraíba', 'PR': 'Paraná',
        'PE': 'Pernambuco', 'PI': 'Piauí', 'RJ': 'Rio de Janeiro', 'RN': 'Rio Grande do Norte',
        'RS': 'Rio Grande do Sul', 'RO': 'Rondônia', 'RR': 'Roraima', 'SC': 'Santa Catarina',
        'SP': 'São Paulo', 'SE': 'Sergipe', 'TO': 'Tocantins'
    }
    return estados.get(uf, uf)

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()