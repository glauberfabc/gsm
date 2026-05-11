"""
Normalizador PNCP → Modelo Canônico
====================================

Este serviço transforma dados raw do PNCP (editais_sync) 
para o modelo canônico (editais_normalizados).

Pipeline:
    PNCP API → editais_sync (raw) → normalizador_pncp → editais_normalizados
                                          ↓
                                   hash_dedup (SHA256)
                                          ↓
                                   deduplicação

Características:
- Recebe 1 raw por vez
- É idempotente (pode rodar múltiplas vezes)
- Nunca escreve direto no matcher
- Função típica: normalize(raw_pncp) → EditalNormalizado
"""

import logging
from typing import Dict, Optional, List, Any
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase

from models.edital_normalizado import (
    EditalNormalizado,
    FonteEdital,
    StatusEdital,
    EsferaEdital,
    OrigemDados,
    criar_edital_normalizado
)

logger = logging.getLogger(__name__)


class NormalizadorPNCP:
    """
    Normaliza dados raw do PNCP para o modelo canônico
    
    Responsabilidades:
    - Mapear campos raw → campos normalizados
    - Limpar e validar dados
    - Calcular hash de deduplicação
    - Detectar tags automáticas
    """
    
    # Mapeamento de status PNCP → StatusEdital
    STATUS_MAP = {
        'aberto': StatusEdital.ABERTO,
        'em andamento': StatusEdital.EM_ANDAMENTO,
        'em proposta': StatusEdital.EM_ANDAMENTO,
        'suspenso': StatusEdital.SUSPENSO,
        'encerrado': StatusEdital.ENCERRADO,
        'cancelado': StatusEdital.CANCELADO,
        'deserto': StatusEdital.DESERTO,
        'adjudicado': StatusEdital.ADJUDICADO,
        'homologado': StatusEdital.HOMOLOGADO,
        'publicado': StatusEdital.PUBLICADO,
        'revogado': StatusEdital.REVOGADO,
    }
    
    # Mapeamento de esfera PNCP → EsferaEdital
    ESFERA_MAP = {
        'federal': EsferaEdital.FEDERAL,
        'estadual': EsferaEdital.ESTADUAL,
        'municipal': EsferaEdital.MUNICIPAL,
        'distrital': EsferaEdital.DISTRITAL,
    }
    
    def __init__(self, db: AsyncIOMotorDatabase):
        """
        Inicializa o normalizador
        
        Args:
            db: Conexão com MongoDB
        """
        self.db = db
        self.raw_collection = db.editais_sync
        self.normalized_collection = db.editais_normalizados
    
    async def setup_indexes(self):
        """
        Cria índices necessários na collection de editais normalizados
        
        Índices:
        - hash_dedup: único para deduplicação
        - uf, municipio: busca geográfica
        - data_abertura: ordenação temporal
        - tags: busca por categoria
        - ncm_detectados: busca por NCM
        """
        logger.info("🔧 [NORMALIZADOR] Configurando índices...")
        
        try:
            # Índice único para deduplicação
            await self.normalized_collection.create_index(
                "hash_dedup",
                unique=True,
                name="idx_hash_dedup_unique"
            )
            
            # Índices para busca geográfica
            await self.normalized_collection.create_index(
                [("uf", 1), ("municipio", 1)],
                name="idx_uf_municipio"
            )
            
            # Índice para ordenação temporal
            await self.normalized_collection.create_index(
                [("data_abertura", -1)],
                name="idx_data_abertura"
            )
            
            # Índice para busca por tags
            await self.normalized_collection.create_index(
                "tags",
                name="idx_tags"
            )
            
            # Índice para busca por NCM
            await self.normalized_collection.create_index(
                "ncm_detectados",
                name="idx_ncm"
            )
            
            # Índice para busca por fonte
            await self.normalized_collection.create_index(
                "fonte",
                name="idx_fonte"
            )
            
            # Índice full-text para busca no objeto
            await self.normalized_collection.create_index(
                [("objeto", "text"), ("orgao", "text")],
                default_language="portuguese",
                name="idx_texto"
            )
            
            logger.info("✅ [NORMALIZADOR] Índices configurados com sucesso!")
            
        except Exception as e:
            logger.error(f"❌ [NORMALIZADOR] Erro ao criar índices: {str(e)}")
            raise
    
    def normalize(self, raw_pncp: Dict[str, Any]) -> Optional[EditalNormalizado]:
        """
        Normaliza um documento raw do PNCP para o modelo canônico
        
        Esta função é IDEMPOTENTE: pode ser chamada múltiplas vezes
        para o mesmo documento sem efeitos colaterais.
        
        Args:
            raw_pncp: Documento raw da collection editais_sync
            
        Returns:
            EditalNormalizado ou None se dados inválidos
        """
        try:
            # Validar campos obrigatórios
            if not raw_pncp.get('objeto') or not raw_pncp.get('orgao'):
                logger.warning(f"⚠️ [NORMALIZADOR] Documento sem objeto ou orgao: {raw_pncp.get('id_externo')}")
                return None
            
            # Mapear status
            status_raw = raw_pncp.get('status', '').lower()
            status = self.STATUS_MAP.get(status_raw, StatusEdital.OUTRO)
            
            # Mapear esfera
            esfera_raw = raw_pncp.get('esfera', '').lower()
            esfera = self.ESFERA_MAP.get(esfera_raw)
            
            # Extrair município do objeto se não disponível
            municipio = raw_pncp.get('municipio') or self._extrair_municipio(raw_pncp)
            
            # Parsear datas
            data_abertura = self._parse_datetime(raw_pncp.get('data_abertura'))
            data_publicacao = self._parse_datetime(raw_pncp.get('data_publicacao'))
            
            # Extrair CNPJ do link se disponível
            cnpj_orgao = self._extrair_cnpj(raw_pncp.get('link_origem'))
            
            # Criar objeto de origem para auditoria
            origem = OrigemDados(
                url=raw_pncp.get('link_origem'),
                raw_id=raw_pncp.get('id_interno'),
                fonte_original="PNCP-OFICIAL",
                data_extracao=self._parse_datetime(raw_pncp.get('sincronizado_em'))
            )
            
            # Criar edital normalizado usando factory function
            edital = criar_edital_normalizado(
                id_externo=raw_pncp.get('id_externo', ''),
                fonte=FonteEdital.PNCP,
                municipio=municipio,
                uf=raw_pncp.get('estado', 'BR'),
                esfera=esfera,
                orgao=raw_pncp.get('orgao', ''),
                cnpj_orgao=cnpj_orgao,
                objeto=raw_pncp.get('objeto', ''),
                valor_estimado=raw_pncp.get('valor_estimado'),
                modalidade=raw_pncp.get('modalidade'),
                status=status,
                numero_processo=raw_pncp.get('numero_processo'),
                data_abertura=data_abertura,
                data_publicacao=data_publicacao,
                link_edital=raw_pncp.get('link_origem'),
                link_anexos=[],
                tags=raw_pncp.get('tags', []),
                is_saude=raw_pncp.get('is_saude', False),
                origem_dados=origem,
                created_at=self._parse_datetime(raw_pncp.get('criado_em')) or datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            return edital
            
        except Exception as e:
            logger.error(f"❌ [NORMALIZADOR] Erro ao normalizar: {str(e)}")
            return None
    
    async def normalizar_e_salvar(self, raw_pncp: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normaliza um documento e salva na collection (com deduplicação)
        
        Args:
            raw_pncp: Documento raw
            
        Returns:
            Dict com status da operação
        """
        edital = self.normalize(raw_pncp)
        
        if not edital:
            return {"status": "erro", "motivo": "Falha na normalização"}
        
        try:
            # Converter para dict (excluindo None e campos vazios)
            edital_dict = edital.model_dump(exclude_none=True)
            
            # Upsert usando hash_dedup como chave
            result = await self.normalized_collection.update_one(
                {"hash_dedup": edital.hash_dedup},
                {"$set": edital_dict},
                upsert=True
            )
            
            if result.upserted_id:
                return {"status": "inserido", "hash": edital.hash_dedup}
            elif result.modified_count > 0:
                return {"status": "atualizado", "hash": edital.hash_dedup}
            else:
                return {"status": "duplicado", "hash": edital.hash_dedup}
                
        except Exception as e:
            logger.error(f"❌ [NORMALIZADOR] Erro ao salvar: {str(e)}")
            return {"status": "erro", "motivo": str(e)}
    
    async def backfill(self, batch_size: int = 100) -> Dict[str, int]:
        """
        Processa todos os documentos raw e normaliza
        
        Este método é IDEMPOTENTE: pode ser executado múltiplas vezes.
        Documentos já processados serão atualizados ou ignorados (deduplicação).
        
        Args:
            batch_size: Quantidade de documentos por batch
            
        Returns:
            Dict com estatísticas do processamento
        """
        logger.info("📥 [NORMALIZADOR] Iniciando backfill PNCP → editais_normalizados...")
        
        stats = {
            "processados": 0,
            "inseridos": 0,
            "atualizados": 0,
            "duplicados": 0,
            "erros": 0
        }
        
        try:
            # Buscar todos os documentos raw
            cursor = self.raw_collection.find({}, {"_id": 0})
            
            batch = []
            async for raw_doc in cursor:
                batch.append(raw_doc)
                
                if len(batch) >= batch_size:
                    batch_stats = await self._processar_batch(batch)
                    self._merge_stats(stats, batch_stats)
                    batch = []
                    
                    logger.info(f"📊 [NORMALIZADOR] Progresso: {stats['processados']} processados, {stats['inseridos']} inseridos, {stats['erros']} erros")
            
            # Processar batch final
            if batch:
                batch_stats = await self._processar_batch(batch)
                self._merge_stats(stats, batch_stats)
            
            logger.info(f"✅ [NORMALIZADOR] Backfill concluído: {stats}")
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ [NORMALIZADOR] Erro no backfill: {str(e)}")
            stats["erros"] += 1
            return stats
    
    async def _processar_batch(self, batch: List[Dict]) -> Dict[str, int]:
        """Processa um batch de documentos"""
        stats = {
            "processados": 0,
            "inseridos": 0,
            "atualizados": 0,
            "duplicados": 0,
            "erros": 0
        }
        
        for raw_doc in batch:
            result = await self.normalizar_e_salvar(raw_doc)
            stats["processados"] += 1
            
            if result["status"] == "inserido":
                stats["inseridos"] += 1
            elif result["status"] == "atualizado":
                stats["atualizados"] += 1
            elif result["status"] == "duplicado":
                stats["duplicados"] += 1
            else:
                stats["erros"] += 1
        
        return stats
    
    def _merge_stats(self, total: Dict, batch: Dict):
        """Merge stats de batch no total"""
        for key in total:
            total[key] += batch.get(key, 0)
    
    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        """Converte valor para datetime"""
        if not value:
            return None
        
        if isinstance(value, datetime):
            return value
        
        if isinstance(value, str):
            # Tentar vários formatos
            formatos = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d"
            ]
            
            for fmt in formatos:
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
        
        return None
    
    def _extrair_cnpj(self, url: str) -> Optional[str]:
        """Extrai CNPJ de URL do PNCP (ex: ?q=18314617000147)"""
        if not url:
            return None
        
        import re
        # Procura por sequência de 14 dígitos
        match = re.search(r'q=(\d{14})', url)
        if match:
            return match.group(1)
        
        return None
    
    def _extrair_municipio(self, raw_pncp: Dict) -> Optional[str]:
        """Tenta extrair nome do município do objeto ou órgão"""
        objeto = raw_pncp.get('objeto', '')
        orgao = raw_pncp.get('orgao', '')
        
        # Padrão comum: "Município de X" ou "Prefeitura de X"
        import re
        
        for texto in [objeto, orgao]:
            # "Município de X - UF"
            match = re.search(r'Munic[íi]pio de ([A-Za-zÀ-ÿ\s]+?)(?:\s*[-–]\s*[A-Z]{2})?[,.]', texto, re.IGNORECASE)
            if match:
                return match.group(1).strip()
            
            # "Prefeitura Municipal de X"
            match = re.search(r'Prefeitura (?:Municipal )?de ([A-Za-zÀ-ÿ\s]+?)(?:\s*[-–]\s*[A-Z]{2})?[,.]', texto, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    async def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas da collection normalizada"""
        total = await self.normalized_collection.count_documents({})
        
        # Contagem por fonte
        pipeline_fonte = [
            {"$group": {"_id": "$fonte", "count": {"$sum": 1}}}
        ]
        por_fonte = {}
        async for doc in self.normalized_collection.aggregate(pipeline_fonte):
            por_fonte[doc["_id"]] = doc["count"]
        
        # Contagem por UF
        pipeline_uf = [
            {"$group": {"_id": "$uf", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        por_uf = {}
        async for doc in self.normalized_collection.aggregate(pipeline_uf):
            por_uf[doc["_id"]] = doc["count"]
        
        # Contagem de saúde
        saude_count = await self.normalized_collection.count_documents({"is_saude": True})
        
        return {
            "total": total,
            "por_fonte": por_fonte,
            "top_10_uf": por_uf,
            "total_saude": saude_count,
            "percentual_saude": round(saude_count / total * 100, 2) if total > 0 else 0
        }


# Função de conveniência para uso global
_normalizador_instance = None

def get_normalizador(db: AsyncIOMotorDatabase) -> NormalizadorPNCP:
    """Retorna instância do normalizador (singleton)"""
    global _normalizador_instance
    if _normalizador_instance is None:
        _normalizador_instance = NormalizadorPNCP(db)
    return _normalizador_instance
