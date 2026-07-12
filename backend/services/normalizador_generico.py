"""
Normalizador Genérico - Multi-Fonte
====================================

Este serviço normaliza dados de QUALQUER fonte para o modelo canônico.
Extende a arquitetura existente (PNCP) para suportar múltiplas fontes.

Fontes suportadas:
- PNCP (Portal Nacional de Contratações Públicas)
- ComprasNet (Federal)
- TCE-SP (São Paulo - Tribunal de Contas)
- MG-CSV (Minas Gerais - Dados Abertos)
- PR-CSV (Paraná - Portal da Transparência)
- GO-CSV (Goiás - Dados Abertos)

Pipeline Multi-Fonte:
    Scraper → editais_sync (raw) → NormalizadorGenerico → editais_normalizados
                                          ↓
                                   hash_dedup (SHA256)
                                          ↓
                                   deduplicação cross-fonte

Características:
- Detecta automaticamente a fonte e aplica normalização correta
- Mantém compatibilidade com normalizador PNCP existente
- Suporta extensão fácil para novas fontes
- Logging detalhado para dashboard de monitoramento
"""

import logging
from typing import Dict, Optional, List, Any
from datetime import datetime, timezone
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


class NormalizadorGenerico:
    """
    Normaliza dados de múltiplas fontes para o modelo canônico
    
    Responsabilidades:
    - Detectar fonte de dados automaticamente
    - Mapear campos específicos de cada fonte → modelo canônico
    - Calcular hash de deduplicação cross-fonte
    - Detectar tags automáticas
    - Registrar métricas para dashboard
    """
    
    # Mapeamento de status genérico
    STATUS_MAP = {
        # Status abertos/ativos
        'aberto': StatusEdital.ABERTO,
        'ativo': StatusEdital.ABERTO,
        'ativa': StatusEdital.ABERTO,
        'em andamento': StatusEdital.EM_ANDAMENTO,
        'em proposta': StatusEdital.EM_ANDAMENTO,
        'em licitação': StatusEdital.EM_ANDAMENTO,
        'publicado': StatusEdital.PUBLICADO,
        'agendado': StatusEdital.PUBLICADO,
        'fase certame': StatusEdital.EM_ANDAMENTO,
        # Status encerrados
        'encerrado': StatusEdital.ENCERRADO,
        'encerrada': StatusEdital.ENCERRADO,
        'concluído': StatusEdital.ENCERRADO,
        'concluido': StatusEdital.ENCERRADO,
        # Outros
        'suspenso': StatusEdital.SUSPENSO,
        'cancelado': StatusEdital.CANCELADO,
        'deserto': StatusEdital.DESERTO,
        'fracassado': StatusEdital.DESERTO,
        'adjudicado': StatusEdital.ADJUDICADO,
        'homologado': StatusEdital.HOMOLOGADO,
        'revogado': StatusEdital.REVOGADO,
    }
    
    # Mapeamento de esfera
    ESFERA_MAP = {
        'federal': EsferaEdital.FEDERAL,
        'estadual': EsferaEdital.ESTADUAL,
        'municipal': EsferaEdital.MUNICIPAL,
        'distrital': EsferaEdital.DISTRITAL,
    }
    
    # Mapeamento de fonte por prefixo/identificador
    FONTE_MAP = {
        'pncp': FonteEdital.PNCP,
        'comprasnet': FonteEdital.COMPRASNET,
        'tce-sp': FonteEdital.ESTADUAL,
        'mg-csv': FonteEdital.ESTADUAL,
        'pr-csv': FonteEdital.ESTADUAL,
        'go-csv': FonteEdital.ESTADUAL,
    }
    
    def __init__(self, db: AsyncIOMotorDatabase):
        """
        Inicializa o normalizador genérico
        
        Args:
            db: Conexão com MongoDB
        """
        self.db = db
        self.raw_collection = db.editais_sync
        self.normalized_collection = db.editais_normalizados
        self.worker_logs = db.worker_logs  # Para dashboard
    
    async def registrar_execucao(self, worker: str, status: str, detalhes: Dict = None):
        """
        Registra execução de worker para o Dashboard de Monitoramento
        
        Args:
            worker: Nome do worker (ex: 'sync_comprasnet')
            status: 'inicio', 'sucesso', 'erro'
            detalhes: Detalhes adicionais (contadores, erros, etc)
        """
        try:
            await self.worker_logs.insert_one({
                'worker': worker,
                'status': status,
                'timestamp': datetime.now(timezone.utc),
                'detalhes': detalhes or {}
            })
        except Exception as e:
            logger.error(f"❌ Erro ao registrar execução: {str(e)}")
    
    def detectar_fonte(self, raw_doc: Dict) -> str:
        """
        Detecta a fonte de dados com base nos campos do documento
        
        Args:
            raw_doc: Documento raw
            
        Returns:
            str: Identificador da fonte
        """
        fonte = raw_doc.get('fonte', '').lower()
        fonte_id = raw_doc.get('fonte_id', '').lower()
        
        # Detectar por campo fonte
        if 'pncp' in fonte:
            return 'pncp'
        elif 'comprasnet' in fonte:
            return 'comprasnet'
        elif 'tce' in fonte and 'sp' in fonte:
            return 'tce-sp'
        elif 'mg' in fonte:
            return 'mg-csv'
        elif 'pr' in fonte:
            return 'pr-csv'
        elif 'go' in fonte:
            return 'go-csv'
        
        # Detectar por fonte_id
        if 'comprasnet' in fonte_id:
            return 'comprasnet'
        elif fonte_id.startswith('tce-sp'):
            return 'tce-sp'
        elif fonte_id.startswith('mg-'):
            return 'mg-csv'
        elif fonte_id.startswith('pr-'):
            return 'pr-csv'
        elif fonte_id.startswith('go-'):
            return 'go-csv'
        
        # Default: PNCP
        return 'pncp'
    
    def normalize(self, raw_doc: Dict) -> Optional[EditalNormalizado]:
        """
        Normaliza um documento raw de qualquer fonte para o modelo canônico
        
        Esta função é IDEMPOTENTE: pode ser chamada múltiplas vezes
        para o mesmo documento sem efeitos colaterais.
        
        Args:
            raw_doc: Documento raw da collection editais_sync
            
        Returns:
            EditalNormalizado ou None se dados inválidos
        """
        try:
            # Detectar fonte
            fonte_detectada = self.detectar_fonte(raw_doc)
            
            # Extrair objeto (campo principal de descrição)
            objeto = (
                raw_doc.get('objeto') or 
                raw_doc.get('titulo_licitacao') or 
                raw_doc.get('descricao_objeto') or
                ''
            ).strip()
            
            # Extrair órgão
            orgao = (
                raw_doc.get('orgao') or 
                raw_doc.get('orgao_licitante') or
                raw_doc.get('entidade') or
                raw_doc.get('nomeOrgao') or
                'Órgão não identificado'
            ).strip()
            
            # Validar campos obrigatórios
            if not objeto and not orgao:
                logger.warning("⚠️ [NORMALIZ] Documento sem objeto e orgao")
                return None
            
            # Mapear fonte
            fonte_enum = self.FONTE_MAP.get(fonte_detectada, FonteEdital.OUTRO)
            
            # Mapear status
            status_raw = (
                raw_doc.get('status') or 
                raw_doc.get('status_aquisicao') or 
                raw_doc.get('situacao') or
                ''
            ).lower()
            status = self._mapear_status(status_raw)
            
            # Mapear esfera
            esfera_raw = (raw_doc.get('esfera') or '').lower()
            esfera = self.ESFERA_MAP.get(esfera_raw)
            if not esfera:
                # Inferir esfera pela fonte
                if fonte_detectada == 'comprasnet':
                    esfera = EsferaEdital.FEDERAL
                elif fonte_detectada in ['tce-sp', 'mg-csv', 'pr-csv', 'go-csv']:
                    esfera = EsferaEdital.ESTADUAL
                elif fonte_detectada == 'pncp':
                    esfera = self._inferir_esfera_pncp(raw_doc)
            
            # Extrair UF
            uf = (
                raw_doc.get('estado') or 
                raw_doc.get('estado_uf') or
                raw_doc.get('uf') or
                self._extrair_uf_de_fonte(fonte_detectada) or
                'BR'
            ).upper()
            
            # Extrair município
            municipio = raw_doc.get('municipio') or self._extrair_municipio(raw_doc)
            
            # Parsear datas
            data_abertura = self._parse_datetime(
                raw_doc.get('data_abertura') or 
                raw_doc.get('data_inicial') or
                raw_doc.get('data_apresentacao')
            )
            data_publicacao = self._parse_datetime(
                raw_doc.get('data_publicacao') or 
                raw_doc.get('data_referencia')
            )
            
            # Extrair CNPJ
            cnpj_orgao = self._extrair_cnpj(
                raw_doc.get('link_origem') or 
                raw_doc.get('uasg')
            )
            
            # Extrair valor
            valor_estimado = self._parse_valor(
                raw_doc.get('valor_estimado') or
                raw_doc.get('valor_total') or
                raw_doc.get('valor_referencia') or
                raw_doc.get('valor_autorizado')
            )
            
            # Criar objeto de origem para auditoria
            origem = OrigemDados(
                url=raw_doc.get('link_origem'),
                raw_id=raw_doc.get('id') or raw_doc.get('fonte_id'),
                fonte_original=raw_doc.get('fonte_nome') or fonte_detectada.upper(),
                data_extracao=self._parse_datetime(raw_doc.get('sincronizado_em') or raw_doc.get('data_referencia'))
            )
            
            # Tags existentes ou detectar
            tags = raw_doc.get('tags', [])
            is_saude = raw_doc.get('is_saude', False)
            
            # 🔗 RESOLUÇÃO DE LINKS V2 (Padrão GSM - VALIDAÇÃO REAL)
            from services.link_resolver_service_v2 import get_link_resolver_v2
            link_resolver = get_link_resolver_v2()
            
            # Preparar dados para resolução de link
            edital_temp = {
                'fonte': raw_doc.get('fonte'),
                'link_origem': raw_doc.get('link_origem'),
                'link_documento': raw_doc.get('link_documento'),
                'numero_processo': raw_doc.get('numero_processo') or raw_doc.get('numero_pregao'),
                'cnpj_orgao': cnpj_orgao,
                'uasg': raw_doc.get('uasg'),
                'id_externo': raw_doc.get('id_externo') or raw_doc.get('fonte_id'),
                'orgao': orgao,
            }
            
            links_resolvidos = link_resolver.resolver_link(edital_temp)
            
            # Criar edital normalizado usando factory function
            edital = criar_edital_normalizado(
                id_externo=raw_doc.get('id_externo') or raw_doc.get('fonte_id') or raw_doc.get('numero_processo') or '',
                fonte=fonte_enum,
                municipio=municipio,
                uf=uf,
                esfera=esfera,
                orgao=orgao,
                cnpj_orgao=cnpj_orgao,
                objeto=objeto or f"Licitação {orgao}",
                valor_estimado=valor_estimado,
                modalidade=raw_doc.get('modalidade'),
                status=status,
                numero_processo=raw_doc.get('numero_processo') or raw_doc.get('numero_pregao'),
                data_abertura=data_abertura,
                data_publicacao=data_publicacao,
                # 🔗 Link resolvido pelo LinkResolverService (Prioridade: PNCP > Portal > PDF > Fallback)
                link_edital=links_resolvidos['link_principal'],
                link_anexos=[],
                tags=tags if isinstance(tags, list) else [],
                is_saude=is_saude,
                origem_dados=origem,
                created_at=self._parse_datetime(raw_doc.get('criado_em')) or datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            return edital
            
        except Exception as e:
            logger.error(f"❌ [NORMALIZ] Erro ao normalizar: {str(e)}")
            return None
    
    def _mapear_status(self, status_raw: str) -> StatusEdital:
        """Mapeia status com fallback inteligente"""
        if not status_raw:
            return StatusEdital.OUTRO
        
        for key, value in self.STATUS_MAP.items():
            if key in status_raw:
                return value
        
        return StatusEdital.OUTRO
    
    def _inferir_esfera_pncp(self, raw_doc: Dict) -> Optional[EsferaEdital]:
        """Infere esfera de documento PNCP"""
        esfera_raw = raw_doc.get('esfera', '').lower()
        
        if 'federal' in esfera_raw:
            return EsferaEdital.FEDERAL
        elif 'estadual' in esfera_raw:
            return EsferaEdital.ESTADUAL
        elif 'municipal' in esfera_raw:
            return EsferaEdital.MUNICIPAL
        
        return None
    
    def _extrair_uf_de_fonte(self, fonte: str) -> Optional[str]:
        """Extrai UF da fonte quando é estadual"""
        mapa = {
            'tce-sp': 'SP',
            'mg-csv': 'MG',
            'pr-csv': 'PR',
            'go-csv': 'GO',
        }
        return mapa.get(fonte)
    
    def _extrair_municipio(self, raw_doc: Dict) -> Optional[str]:
        """Tenta extrair nome do município"""
        import re
        
        objeto = raw_doc.get('objeto', '')
        orgao = raw_doc.get('orgao_licitante', '') or raw_doc.get('orgao', '')
        
        for texto in [objeto, orgao]:
            match = re.search(r'Munic[íi]pio de ([A-Za-zÀ-ÿ\s]+?)(?:\s*[-–]\s*[A-Z]{2})?[,.]', texto, re.IGNORECASE)
            if match:
                return match.group(1).strip()
            
            match = re.search(r'Prefeitura (?:Municipal )?de ([A-Za-zÀ-ÿ\s]+?)(?:\s*[-–]\s*[A-Z]{2})?[,.]', texto, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extrair_cnpj(self, valor: str) -> Optional[str]:
        """Extrai CNPJ de URL ou campo"""
        if not valor:
            return None
        
        import re
        
        # Procura por sequência de 14 dígitos
        match = re.search(r'(\d{14})', str(valor))
        if match:
            return match.group(1)
        
        # CNPJ formatado
        match = re.search(r'(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})', str(valor))
        if match:
            return re.sub(r'[^\d]', '', match.group(1))
        
        return None
    
    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        """Converte valor para datetime"""
        if not value:
            return None
        
        if isinstance(value, datetime):
            return value
        
        if isinstance(value, str):
            formatos = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d",
                "%d/%m/%Y %H:%M",
                "%d/%m/%Y"
            ]
            
            for fmt in formatos:
                try:
                    return datetime.strptime(value[:len(fmt)+3], fmt)
                except ValueError:
                    continue
        
        return None
    
    def _parse_valor(self, value: Any) -> Optional[float]:
        """Converte valor para float"""
        if value is None:
            return None
        
        try:
            if isinstance(value, (int, float)):
                return float(value)
            
            import re
            valor_str = str(value)
            valor_limpo = re.sub(r'[^\d,.]', '', valor_str)
            
            if ',' in valor_limpo and '.' in valor_limpo:
                valor_limpo = valor_limpo.replace('.', '').replace(',', '.')
            elif ',' in valor_limpo:
                valor_limpo = valor_limpo.replace(',', '.')
            
            return float(valor_limpo) if valor_limpo else None
        except (ValueError, AttributeError):
            return None
    
    async def normalizar_e_salvar(self, raw_doc: Dict) -> Dict[str, Any]:
        """
        Normaliza um documento e salva na collection (com deduplicação)
        
        Args:
            raw_doc: Documento raw
            
        Returns:
            Dict com status da operação
        """
        edital = self.normalize(raw_doc)
        
        if not edital:
            return {"status": "erro", "motivo": "Falha na normalização"}
        
        try:
            # Converter para dict
            edital_dict = edital.model_dump(exclude_none=True)
            
            # Upsert usando id_externo como chave primária (fallback para hash_dedup se não houver id_externo)
            query_match = {"id_externo": edital.id_externo} if edital.id_externo else {"hash_dedup": edital.hash_dedup}
            
            result = await self.normalized_collection.update_one(
                query_match,
                {"$set": edital_dict},
                upsert=True
            )
            
            if result.upserted_id:
                return {"status": "inserido", "hash": edital.hash_dedup, "fonte": str(edital.fonte)}
            elif result.modified_count > 0:
                return {"status": "atualizado", "hash": edital.hash_dedup, "fonte": str(edital.fonte)}
            else:
                return {"status": "duplicado", "hash": edital.hash_dedup, "fonte": str(edital.fonte)}
                
        except Exception as e:
            logger.error(f"❌ [NORMALIZ] Erro ao salvar: {str(e)}")
            return {"status": "erro", "motivo": str(e)}
    
    async def normalizar_lote(self, documentos: List[Dict], fonte: str = None) -> Dict[str, int]:
        """
        Normaliza um lote de documentos (usado pelos scrapers)
        
        Args:
            documentos: Lista de documentos raw
            fonte: Identificador da fonte (para logging)
            
        Returns:
            Dict com estatísticas
        """
        worker_name = f"normalizar_{fonte or 'lote'}"
        
        stats = {
            "processados": 0,
            "inseridos": 0,
            "atualizados": 0,
            "duplicados": 0,
            "erros": 0
        }
        
        # Registrar início
        await self.registrar_execucao(worker_name, 'inicio', {'total_docs': len(documentos)})
        
        try:
            for raw_doc in documentos:
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
            
            logger.info(f"✅ [NORMALIZ] Lote {fonte or 'genérico'}: {stats}")
            
            # Registrar sucesso
            await self.registrar_execucao(worker_name, 'sucesso', stats)
            
        except Exception as e:
            logger.error(f"❌ [NORMALIZ] Erro no lote: {str(e)}")
            stats["erros"] += 1
            await self.registrar_execucao(worker_name, 'erro', {'erro': str(e), **stats})
        
        return stats
    
    async def backfill_por_fonte(self, fonte: str = None, batch_size: int = 100) -> Dict[str, int]:
        """
        Processa documentos raw de uma fonte específica
        
        Args:
            fonte: Filtrar por fonte (None = todas)
            batch_size: Tamanho do batch
            
        Returns:
            Dict com estatísticas
        """
        logger.info(f"📥 [NORMALIZ] Backfill fonte={fonte or 'TODAS'}...")
        
        stats = {
            "processados": 0,
            "inseridos": 0,
            "atualizados": 0,
            "duplicados": 0,
            "erros": 0
        }
        
        try:
            # Filtro por fonte se especificado
            query = {}
            if fonte:
                query["fonte"] = {"$regex": fonte, "$options": "i"}
            
            cursor = self.raw_collection.find(query, {"_id": 0})
            
            batch = []
            async for raw_doc in cursor:
                batch.append(raw_doc)
                
                if len(batch) >= batch_size:
                    batch_stats = await self.normalizar_lote(batch, fonte)
                    self._merge_stats(stats, batch_stats)
                    batch = []
                    logger.info(f"📊 [NORMALIZ] Progresso: {stats['processados']} processados")
            
            # Processar batch final
            if batch:
                batch_stats = await self.normalizar_lote(batch, fonte)
                self._merge_stats(stats, batch_stats)
            
            logger.info(f"✅ [NORMALIZ] Backfill concluído: {stats}")
            
        except Exception as e:
            logger.error(f"❌ [NORMALIZ] Erro no backfill: {str(e)}")
            stats["erros"] += 1
        
        return stats
    
    def _merge_stats(self, total: Dict, batch: Dict):
        """Merge stats de batch no total"""
        for key in total:
            total[key] += batch.get(key, 0)
    
    async def get_stats_por_fonte(self) -> Dict[str, Any]:
        """Retorna estatísticas agrupadas por fonte"""
        try:
            pipeline = [
                {"$group": {"_id": "$fonte", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]
            
            por_fonte = {}
            async for doc in self.normalized_collection.aggregate(pipeline):
                por_fonte[doc["_id"]] = doc["count"]
            
            total = await self.normalized_collection.count_documents({})
            
            return {
                "total": total,
                "por_fonte": por_fonte
            }
        except Exception as e:
            logger.error(f"❌ [NORMALIZ] Erro ao obter stats: {str(e)}")
            return {"total": 0, "por_fonte": {}}


# Instância global
_normalizador_generico_instance = None


def get_normalizador_generico(db: AsyncIOMotorDatabase) -> NormalizadorGenerico:
    """Retorna instância do normalizador genérico (singleton)"""
    global _normalizador_generico_instance
    if _normalizador_generico_instance is None:
        _normalizador_generico_instance = NormalizadorGenerico(db)
    return _normalizador_generico_instance
