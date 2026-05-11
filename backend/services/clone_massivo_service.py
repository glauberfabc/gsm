"""
CLONE MASSIVO v55.0 - Ingestão de Dados em Volume

Este serviço faz MIRRORING (espelhamento) completo dos dados disponíveis
para a collection editais_gsm.

OBJETIVO: Igualar o volume de dados do parceiro.

FONTES DE INGESTÃO:
1. editais_normalizados (PNCP já sincronizado)
2. licitacoes (dados históricos)
3. API PNCP direta (novos editais)
"""

import os
import logging
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class CloneMassivoService:
    """
    Serviço de clonagem massiva de dados para editais_gsm.
    
    ESTRATÉGIA: Copiar TODOS os dados existentes para a collection própria,
    garantindo independência total.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection_destino = db.editais_gsm
        self.collection_origem1 = db.editais_normalizados
        self.collection_origem2 = db.licitacoes
        
    async def executar_clone_massivo(self, termos: List[str] = None) -> Dict:
        """
        Executa clonagem massiva de TODAS as fontes para editais_gsm.
        
        Args:
            termos: Lista de termos para filtrar (opcional). Se None, clona TUDO.
            
        Returns:
            Dict com estatísticas da clonagem
        """
        logger.info("🔄 [CLONE-MASSIVO] Iniciando espelhamento de dados...")
        
        stats = {
            "inicio": datetime.now(timezone.utc).isoformat(),
            "total_processados": 0,
            "novos_inseridos": 0,
            "atualizados": 0,
            "erros": 0,
            "fontes": []
        }
        
        # 1. Clonar de editais_normalizados
        stats_norm = await self._clonar_de_collection(
            collection_origem=self.collection_origem1,
            nome_fonte="editais_normalizados",
            termos=termos
        )
        stats["fontes"].append(stats_norm)
        stats["total_processados"] += stats_norm["processados"]
        stats["novos_inseridos"] += stats_norm["novos"]
        stats["atualizados"] += stats_norm["atualizados"]
        
        # 2. Clonar de licitacoes
        stats_lic = await self._clonar_de_collection(
            collection_origem=self.collection_origem2,
            nome_fonte="licitacoes",
            termos=termos
        )
        stats["fontes"].append(stats_lic)
        stats["total_processados"] += stats_lic["processados"]
        stats["novos_inseridos"] += stats_lic["novos"]
        stats["atualizados"] += stats_lic["atualizados"]
        
        stats["fim"] = datetime.now(timezone.utc).isoformat()
        
        # Contar total na collection destino
        stats["total_editais_gsm"] = await self.collection_destino.count_documents({})
        
        logger.info(f"✅ [CLONE-MASSIVO] Concluído: {stats['novos_inseridos']} novos, {stats['atualizados']} atualizados, total: {stats['total_editais_gsm']}")
        
        return stats
    
    async def _clonar_de_collection(
        self,
        collection_origem,
        nome_fonte: str,
        termos: List[str] = None,
        limite: int = 10000
    ) -> Dict:
        """
        Clona documentos de uma collection origem para editais_gsm.
        """
        logger.info(f"📥 [CLONE] Clonando de {nome_fonte}...")
        
        stats = {
            "fonte": nome_fonte,
            "processados": 0,
            "novos": 0,
            "atualizados": 0,
            "erros": 0
        }
        
        try:
            # Construir query
            if termos:
                query = {
                    "$or": [
                        {"objeto": {"$regex": "|".join(termos), "$options": "i"}},
                        {"medicamento": {"$regex": "|".join(termos), "$options": "i"}}
                    ]
                }
            else:
                query = {}  # Clonar TUDO
            
            # Buscar documentos
            cursor = collection_origem.find(query, {"_id": 0}).limit(limite)
            
            async for doc in cursor:
                stats["processados"] += 1
                
                try:
                    # Gerar ID GSM único
                    id_gsm = self._gerar_id_gsm(doc)
                    
                    # Transformar para schema GSM
                    doc_gsm = self._transformar_para_schema_gsm(doc, nome_fonte, id_gsm)
                    
                    # Upsert
                    result = await self.collection_destino.update_one(
                        {"id_gsm": id_gsm},
                        {"$set": doc_gsm},
                        upsert=True
                    )
                    
                    if result.upserted_id:
                        stats["novos"] += 1
                    elif result.modified_count > 0:
                        stats["atualizados"] += 1
                        
                except Exception as e:
                    stats["erros"] += 1
                    if stats["erros"] < 5:
                        logger.warning(f"⚠️ [CLONE] Erro ao processar: {e}")
            
            logger.info(f"📥 [{nome_fonte}] {stats['processados']} processados, {stats['novos']} novos, {stats['atualizados']} atualizados")
            
        except Exception as e:
            logger.error(f"❌ [CLONE] Erro ao clonar de {nome_fonte}: {e}")
            stats["erros"] += 1
        
        return stats
    
    def _gerar_id_gsm(self, doc: Dict) -> str:
        """Gera ID GSM único baseado nos dados do documento."""
        id_base = (
            doc.get('id_externo', '') or
            doc.get('numero_controle_pncp', '') or
            doc.get('id', '') or
            doc.get('hash_dedup', '') or
            str(doc.get('objeto', ''))[:100] + str(doc.get('orgao', ''))[:50]
        )
        return hashlib.md5(id_base.encode()).hexdigest()
    
    def _transformar_para_schema_gsm(self, doc: Dict, fonte: str, id_gsm: str) -> Dict:
        """Transforma documento para schema GSM padronizado."""
        
        # Extrair dados do órgão
        orgao = doc.get('orgao', '') or doc.get('orgao_licitante', '')
        cnpj = doc.get('cnpj_orgao', '') or doc.get('cnpj', '')
        uasg = doc.get('uasg', '') or cnpj.replace('.', '').replace('/', '').replace('-', '')[:14] if cnpj else ''
        
        return {
            # Identificadores GSM
            "id_gsm": id_gsm,
            "id_externo": doc.get('id_externo', '') or doc.get('id', '') or id_gsm,
            "numero_controle_pncp": doc.get('numero_controle_pncp', ''),
            "hash_dedup": doc.get('hash_dedup', ''),
            
            # Fonte de origem
            "fonte_origem": f"CLONE_{fonte.upper()}",
            "fonte": doc.get('fonte', fonte),
            "fonte_clone": fonte,
            
            # Dados do órgão (obrigatório para interface v10)
            "dados_orgao": {
                "uasg": uasg,
                "cnpj": cnpj,
                "nome": orgao,
                "uf": doc.get('estado', '') or doc.get('uf', ''),
                "municipio": doc.get('municipio', '')
            },
            
            # Campos principais
            "objeto": (doc.get('objeto', '') or doc.get('medicamento', '')).strip().upper(),
            "orgao": orgao,
            "estado": doc.get('estado', '') or doc.get('uf', ''),
            "uf": doc.get('estado', '') or doc.get('uf', ''),
            "municipio": doc.get('municipio', ''),
            "esfera": doc.get('esfera', ''),
            "modalidade": doc.get('modalidade', ''),
            "status": doc.get('status', 'ATIVA'),
            
            # Valores
            "valor_estimado": doc.get('valor_estimado'),
            "valor_referencia": doc.get('valor_referencia'),
            
            # Datas
            "data_publicacao": doc.get('data_publicacao'),
            "data_abertura": doc.get('data_abertura') or doc.get('data_final'),
            
            # Links
            "link_documento": doc.get('link_edital', '') or doc.get('link_origem', ''),
            "link_origem": doc.get('link_origem', ''),
            "link_portal": doc.get('link_portal', '') or doc.get('link_origem', ''),
            "link_edital": doc.get('link_edital', ''),
            
            # Identificação da licitação
            "numero_processo": doc.get('numero_processo', ''),
            "numero_licitacao": doc.get('numero_licitacao', ''),
            
            # Itens clonados
            "itens_clonados": doc.get('itens_edital', []) or doc.get('itens', []),
            
            # Metadados
            "clonado_em": datetime.now(timezone.utc),
            "atualizado_em": datetime.now(timezone.utc),
            "is_saude": doc.get('is_saude', False),
            "score_relevancia": doc.get('score_relevancia', 0),
            "tags": doc.get('tags', [])
        }
    
    async def get_stats(self) -> Dict:
        """Retorna estatísticas do banco local GSM."""
        total_gsm = await self.collection_destino.count_documents({})
        total_norm = await self.collection_origem1.count_documents({})
        total_lic = await self.collection_origem2.count_documents({})
        
        # Contar por fonte
        pipeline = [
            {"$group": {"_id": "$fonte_origem", "count": {"$sum": 1}}}
        ]
        por_fonte = await self.collection_destino.aggregate(pipeline).to_list(length=100)
        
        return {
            "editais_gsm": total_gsm,
            "editais_normalizados": total_norm,
            "licitacoes": total_lic,
            "por_fonte": {item["_id"]: item["count"] for item in por_fonte},
            "cobertura": f"{(total_gsm / max(total_norm, 1)) * 100:.1f}%"
        }


# Singleton
_clone_service = None

def get_clone_massivo_service(db: AsyncIOMotorDatabase) -> CloneMassivoService:
    global _clone_service
    if _clone_service is None:
        _clone_service = CloneMassivoService(db)
    return _clone_service
