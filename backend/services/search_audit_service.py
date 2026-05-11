"""
Search Audit Service - Log de Buscas Sem Resultados
====================================================

🎯 OBJETIVO: Registrar buscas que retornam zero resultados para
auditoria manual de fontes e identificação de gaps.

Requisito v4.1: "Dashboard Comparativo (Preparação)"
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class SearchAuditService:
    """
    Serviço de auditoria de buscas
    
    Registra:
    - Termos buscados
    - Número de resultados
    - Fontes consultadas
    - Timestamp
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.search_audit_logs
    
    async def setup_indexes(self):
        """Cria índices necessários"""
        try:
            # Índice por termo (para agrupamento)
            await self.collection.create_index("termo")
            
            # Índice por data (para limpeza)
            await self.collection.create_index("timestamp")
            
            # Índice composto para análise
            await self.collection.create_index([
                ("termo", 1),
                ("total_resultados", 1)
            ])
            
            logger.info("✅ [SearchAudit] Índices criados")
            
        except Exception as e:
            logger.debug(f"Índices já existem ou erro: {e}")
    
    async def registrar_busca(
        self,
        termo: str,
        total_resultados: int,
        fontes_consultadas: List[str],
        filtros: Optional[Dict] = None,
        tempo_ms: Optional[float] = None
    ):
        """
        Registra uma busca no log de auditoria
        
        Args:
            termo: Termo buscado
            total_resultados: Quantidade de resultados encontrados
            fontes_consultadas: Lista de fontes (PNCP, ComprasNet, BNC, etc)
            filtros: Filtros aplicados
            tempo_ms: Tempo de execução em ms
        """
        try:
            doc = {
                "termo": termo.lower().strip(),
                "total_resultados": total_resultados,
                "fontes_consultadas": fontes_consultadas,
                "filtros": filtros or {},
                "tempo_ms": tempo_ms,
                "timestamp": datetime.now(timezone.utc),
                "is_zero_results": total_resultados == 0
            }
            
            await self.collection.insert_one(doc)
            
            # Log especial para buscas sem resultado
            if total_resultados == 0:
                logger.warning(f"🔴 [AUDIT] Busca sem resultados: '{termo}' (fontes: {fontes_consultadas})")
            
        except Exception as e:
            logger.debug(f"Erro ao registrar busca: {e}")
    
    async def get_termos_sem_resultado(
        self,
        limite: int = 50,
        dias: int = 30
    ) -> List[Dict]:
        """
        Retorna termos que frequentemente retornam zero resultados
        
        Args:
            limite: Máximo de termos
            dias: Período em dias
            
        Returns:
            Lista de termos com contagem de buscas sem resultado
        """
        try:
            from datetime import timedelta
            
            pipeline = [
                # Filtrar por período
                {
                    "$match": {
                        "is_zero_results": True,
                        "timestamp": {
                            "$gte": datetime.now(timezone.utc) - timedelta(days=dias)
                        }
                    }
                },
                # Agrupar por termo
                {
                    "$group": {
                        "_id": "$termo",
                        "total_buscas": {"$sum": 1},
                        "ultima_busca": {"$max": "$timestamp"},
                        "fontes": {"$addToSet": "$fontes_consultadas"}
                    }
                },
                # Ordenar por frequência
                {"$sort": {"total_buscas": -1}},
                # Limitar
                {"$limit": limite}
            ]
            
            cursor = self.collection.aggregate(pipeline)
            resultados = await cursor.to_list(length=limite)
            
            return [
                {
                    "termo": r["_id"],
                    "total_buscas": r["total_buscas"],
                    "ultima_busca": r["ultima_busca"].isoformat() if r.get("ultima_busca") else None,
                    "fontes_consultadas": list(set(f for fontes in r.get("fontes", []) for f in fontes))
                }
                for r in resultados
            ]
            
        except Exception as e:
            logger.error(f"Erro ao buscar termos sem resultado: {e}")
            return []
    
    async def get_estatisticas(
        self,
        dias: int = 7
    ) -> Dict[str, Any]:
        """
        Retorna estatísticas de busca
        
        Args:
            dias: Período em dias
            
        Returns:
            Estatísticas agregadas
        """
        try:
            from datetime import timedelta
            
            filtro = {
                "timestamp": {
                    "$gte": datetime.now(timezone.utc) - timedelta(days=dias)
                }
            }
            
            # Total de buscas
            total_buscas = await self.collection.count_documents(filtro)
            
            # Buscas sem resultado
            total_zero = await self.collection.count_documents({
                **filtro,
                "is_zero_results": True
            })
            
            # Termos únicos
            termos_unicos = len(await self.collection.distinct("termo", filtro))
            
            # Top termos buscados
            pipeline = [
                {"$match": filtro},
                {"$group": {"_id": "$termo", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 10}
            ]
            
            top_termos = await self.collection.aggregate(pipeline).to_list(10)
            
            return {
                "periodo_dias": dias,
                "total_buscas": total_buscas,
                "total_sem_resultado": total_zero,
                "taxa_zero_resultados": round(total_zero / total_buscas * 100, 2) if total_buscas > 0 else 0,
                "termos_unicos": termos_unicos,
                "top_termos": [
                    {"termo": t["_id"], "buscas": t["count"]}
                    for t in top_termos
                ]
            }
            
        except Exception as e:
            logger.error(f"Erro ao calcular estatísticas: {e}")
            return {}


# Singleton com DB
_search_audit_instance = None

def get_search_audit(db: AsyncIOMotorDatabase) -> SearchAuditService:
    """Retorna instância do serviço"""
    global _search_audit_instance
    if _search_audit_instance is None:
        _search_audit_instance = SearchAuditService(db)
    return _search_audit_instance
