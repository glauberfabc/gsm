"""
Monitoring Service - GSM Buscador de Editais
=============================================

Serviço de monitoramento para o Dashboard operacional.

Métricas coletadas:
- Status dos workers (OK / ERRO / ATRASO)
- Última execução por fonte
- Quantidade de editais (raw vs normalizados)
- Quantidade de matches gerados
- Alertas disparados vs suprimidos

Este serviço fecha o ciclo:
Fonte → Normalização → Match → Alerta → Monitoramento
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase
from enum import Enum

logger = logging.getLogger(__name__)


class WorkerStatus(str, Enum):
    """Status possíveis de um worker"""
    OK = "OK"
    ERRO = "ERRO"
    ATRASO = "ATRASO"
    INATIVO = "INATIVO"
    DESCONHECIDO = "DESCONHECIDO"


class MonitoringService:
    """
    Serviço de monitoramento operacional
    
    Coleta e agrega métricas de:
    - Workers (scheduler jobs)
    - Fontes de dados (PNCP, scrapers)
    - Pipeline de dados (raw → normalizado → match)
    - Sistema de alertas
    """
    
    # Thresholds para determinar status
    THRESHOLD_ATRASO_MINUTOS = 30  # Worker em atraso se não executou há X minutos
    THRESHOLD_ERRO_CONSECUTIVOS = 3  # Fonte com erro se falhou X vezes seguidas
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
    
    async def get_dashboard_completo(self) -> Dict[str, Any]:
        """
        Retorna todas as métricas do dashboard em uma única chamada
        
        Returns:
            Dict com todas as métricas agregadas
        """
        try:
            inicio = datetime.now(timezone.utc)
            
            dashboard = {
                "timestamp": inicio.isoformat(),
                "workers": await self._get_workers_status(),
                "fontes": await self._get_fontes_status(),
                "pipeline": await self._get_pipeline_metrics(),
                "alertas": await self._get_alertas_metrics(),
                "saude_geral": await self._calcular_saude_geral()
            }
            
            dashboard["tempo_coleta_ms"] = (datetime.now(timezone.utc) - inicio).total_seconds() * 1000
            
            return dashboard
            
        except Exception as e:
            logger.error(f"❌ [MONITORING] Erro ao coletar métricas: {str(e)}")
            return {"erro": str(e)}
    
    async def _get_workers_status(self) -> Dict[str, Any]:
        """
        Retorna status dos workers do scheduler
        
        Workers monitorados:
        - sync_pncp: Sincronização PNCP → MongoDB
        - check_alerts: Verificação de alertas
        - cleanup: Limpeza de dados antigos
        - matcher: Processamento de matches
        """
        try:
            workers = {}
            
            # Buscar logs de execução dos workers (collection: worker_logs)
            logs_collection = self.db.worker_logs
            
            # Worker: Sincronização PNCP
            sync_log = await logs_collection.find_one(
                {"worker": "sync_pncp", "status": "sucesso"},
                sort=[("timestamp", -1)]
            )
            workers["sync_pncp"] = self._avaliar_worker_v2(
                sync_log,
                nome="Sincronização PNCP",
                intervalo_esperado_min=15
            )
            
            # Worker: Verificação de Alertas
            alertas_log = await logs_collection.find_one(
                {"worker": "check_alerts", "status": "sucesso"},
                sort=[("timestamp", -1)]
            )
            workers["check_alerts"] = self._avaliar_worker_v2(
                alertas_log,
                nome="Verificação de Alertas",
                intervalo_esperado_min=30
            )
            
            # Worker: Matcher v2
            matcher_log = await logs_collection.find_one(
                {"worker": "matcher_v2", "status": "sucesso"},
                sort=[("timestamp", -1)]
            )
            workers["matcher_v2"] = self._avaliar_worker_v2(
                matcher_log,
                nome="Matcher v2",
                intervalo_esperado_min=30
            )
            
            # Worker: Limpeza
            cleanup_log = await logs_collection.find_one(
                {"worker": "cleanup", "status": "sucesso"},
                sort=[("timestamp", -1)]
            )
            workers["cleanup"] = self._avaliar_worker_v2(
                cleanup_log,
                nome="Limpeza de Dados",
                intervalo_esperado_min=1440  # 24 horas
            )
            
            # Resumo
            total = len(workers)
            ok = sum(1 for w in workers.values() if w["status"] == WorkerStatus.OK)
            erro = sum(1 for w in workers.values() if w["status"] == WorkerStatus.ERRO)
            atraso = sum(1 for w in workers.values() if w["status"] == WorkerStatus.ATRASO)
            
            return {
                "workers": workers,
                "resumo": {
                    "total": total,
                    "ok": ok,
                    "erro": erro,
                    "atraso": atraso
                }
            }
            
        except Exception as e:
            logger.error(f"❌ [MONITORING] Erro ao buscar status dos workers: {str(e)}")
            return {"erro": str(e)}
    
    def _avaliar_worker(
        self,
        log: Optional[Dict],
        nome: str,
        intervalo_esperado_min: int
    ) -> Dict[str, Any]:
        """Avalia status de um worker baseado no último log (formato antigo)"""
        return self._avaliar_worker_v2(log, nome, intervalo_esperado_min)
    
    def _avaliar_worker_v2(
        self,
        log: Optional[Dict],
        nome: str,
        intervalo_esperado_min: int
    ) -> Dict[str, Any]:
        """
        Avalia status de um worker baseado no último log
        
        Formato esperado dos logs (collection worker_logs):
        {
            "worker": "sync_pncp",
            "status": "sucesso" | "erro" | "inicio",
            "timestamp": datetime,
            "detalhes": {...}
        }
        """
        if not log:
            return {
                "nome": nome,
                "status": WorkerStatus.DESCONHECIDO,
                "ultima_execucao": None,
                "mensagem": "Nenhum registro encontrado"
            }
        
        ultima_execucao = log.get("timestamp")
        status_log = log.get("status", "").lower()
        detalhes = log.get("detalhes", {})
        erro_msg = detalhes.get("erro") if isinstance(detalhes, dict) else None
        
        # Calcular tempo desde última execução
        if ultima_execucao:
            if isinstance(ultima_execucao, str):
                ultima_execucao = datetime.fromisoformat(ultima_execucao.replace('Z', '+00:00'))
            
            agora = datetime.now(timezone.utc)
            if hasattr(ultima_execucao, 'tzinfo') and ultima_execucao.tzinfo is None:
                ultima_execucao = ultima_execucao.replace(tzinfo=timezone.utc)
            minutos_desde = (agora - ultima_execucao).total_seconds() / 60
        else:
            minutos_desde = float('inf')
        
        # Determinar status baseado no log
        if status_log == "erro" or erro_msg:
            status = WorkerStatus.ERRO
            mensagem = erro_msg or "Última execução falhou"
        elif minutos_desde > intervalo_esperado_min * 2:
            status = WorkerStatus.ATRASO
            mensagem = f"Última execução há {int(minutos_desde)} minutos (esperado: {intervalo_esperado_min})"
        elif status_log == "sucesso":
            status = WorkerStatus.OK
            mensagem = f"Executado há {int(minutos_desde)} minutos"
        else:
            status = WorkerStatus.DESCONHECIDO
            mensagem = f"Status desconhecido: {status_log}"
        
        return {
            "nome": nome,
            "status": status,
            "ultima_execucao": ultima_execucao.isoformat() if ultima_execucao else None,
            "minutos_desde_execucao": int(minutos_desde) if minutos_desde != float('inf') else None,
            "intervalo_esperado_min": intervalo_esperado_min,
            "mensagem": mensagem,
            "detalhes": detalhes
        }
    
    async def _get_fontes_status(self) -> Dict[str, Any]:
        """
        Retorna status das fontes de dados
        
        Fontes monitoradas:
        - PNCP-OFICIAL (API pública)
        - Scrapers estaduais/municipais
        """
        try:
            fontes = {}
            
            # Buscar execuções de scrapers
            scraper_collection = self.db.scraper_executions
            
            # Agrupar por fonte
            pipeline = [
                {"$sort": {"timestamp": -1}},
                {"$group": {
                    "_id": "$fonte",
                    "ultima_execucao": {"$first": "$timestamp"},
                    "ultimo_status": {"$first": "$status"},
                    "ultimo_erro": {"$first": "$erro"},
                    "total_execucoes": {"$sum": 1},
                    "total_sucesso": {"$sum": {"$cond": [{"$eq": ["$status", "sucesso"]}, 1, 0]}},
                    "total_resultados": {"$sum": "$total_resultados"}
                }}
            ]
            
            async for doc in scraper_collection.aggregate(pipeline):
                fonte_id = doc["_id"]
                
                # Calcular taxa de sucesso
                taxa_sucesso = (doc["total_sucesso"] / doc["total_execucoes"] * 100) if doc["total_execucoes"] > 0 else 0
                
                # Determinar status
                if doc["ultimo_status"] == "sucesso":
                    status = WorkerStatus.OK
                elif doc["ultimo_status"] == "erro":
                    status = WorkerStatus.ERRO
                else:
                    status = WorkerStatus.DESCONHECIDO
                
                fontes[fonte_id] = {
                    "fonte": fonte_id,
                    "status": status,
                    "ultima_execucao": doc["ultima_execucao"].isoformat() if doc["ultima_execucao"] else None,
                    "ultimo_erro": doc["ultimo_erro"],
                    "total_execucoes": doc["total_execucoes"],
                    "taxa_sucesso": round(taxa_sucesso, 1),
                    "total_resultados": doc["total_resultados"]
                }
            
            # Adicionar PNCP-OFICIAL se não existir nos logs
            if "PNCP-OFICIAL" not in fontes:
                # Verificar pela collection editais_sync
                count = await self.db.editais_sync.count_documents({"fonte": "PNCP-OFICIAL"})
                fontes["PNCP-OFICIAL"] = {
                    "fonte": "PNCP-OFICIAL",
                    "status": WorkerStatus.OK if count > 0 else WorkerStatus.DESCONHECIDO,
                    "total_resultados": count,
                    "mensagem": "Fonte principal via API pública"
                }
            
            # Resumo
            total = len(fontes)
            ok = sum(1 for f in fontes.values() if f.get("status") == WorkerStatus.OK)
            erro = sum(1 for f in fontes.values() if f.get("status") == WorkerStatus.ERRO)
            
            return {
                "fontes": fontes,
                "resumo": {
                    "total": total,
                    "ok": ok,
                    "erro": erro
                }
            }
            
        except Exception as e:
            logger.error(f"❌ [MONITORING] Erro ao buscar status das fontes: {str(e)}")
            return {"erro": str(e)}
    
    async def _get_pipeline_metrics(self) -> Dict[str, Any]:
        """
        Retorna métricas do pipeline de dados
        
        Pipeline: Fonte → Raw → Normalizado → Match
        """
        try:
            # Contagem de editais raw
            raw_count = await self.db.editais_sync.count_documents({})
            
            # Contagem de editais normalizados
            normalized_count = await self.db.editais_normalizados.count_documents({})
            
            # Contagem de matches
            matches_count = await self.db.matches.count_documents({})
            matches_pendentes = await self.db.matches.count_documents({"processado": False})
            
            # Taxa de normalização
            taxa_normalizacao = (normalized_count / raw_count * 100) if raw_count > 0 else 0
            
            # Contagem por fonte (normalizados)
            pipeline_fonte = [
                {"$group": {"_id": "$fonte", "count": {"$sum": 1}}}
            ]
            por_fonte = {}
            async for doc in self.db.editais_normalizados.aggregate(pipeline_fonte):
                por_fonte[doc["_id"]] = doc["count"]
            
            # Contagem de saúde
            saude_count = await self.db.editais_normalizados.count_documents({"is_saude": True})
            
            # Editais nas últimas 24h
            limite_24h = datetime.now(timezone.utc) - timedelta(hours=24)
            novos_24h = await self.db.editais_normalizados.count_documents({
                "created_at": {"$gte": limite_24h}
            })
            
            return {
                "editais_raw": raw_count,
                "editais_normalizados": normalized_count,
                "taxa_normalizacao": round(taxa_normalizacao, 1),
                "por_fonte": por_fonte,
                "saude": {
                    "total": saude_count,
                    "percentual": round(saude_count / normalized_count * 100, 1) if normalized_count > 0 else 0
                },
                "matches": {
                    "total": matches_count,
                    "pendentes": matches_pendentes
                },
                "novos_24h": novos_24h
            }
            
        except Exception as e:
            logger.error(f"❌ [MONITORING] Erro ao buscar métricas do pipeline: {str(e)}")
            return {"erro": str(e)}
    
    async def _get_alertas_metrics(self) -> Dict[str, Any]:
        """
        Retorna métricas do sistema de alertas
        
        Métricas:
        - Alertas ativos vs inativos
        - Alertas disparados vs suprimidos (score < threshold)
        - Notificações enviadas
        """
        try:
            # Contagem de alertas
            alertas_total = await self.db.alertas_notificacao.count_documents({})
            alertas_ativos = await self.db.alertas_notificacao.count_documents({"ativo": True})
            
            # Matches por score (disparados vs suprimidos)
            # Score >= 20 = disparado, < 20 = suprimido
            threshold = 20
            matches_disparados = await self.db.matches.count_documents({"score": {"$gte": threshold}})
            matches_suprimidos = await self.db.matches.count_documents({"score": {"$lt": threshold}})
            
            # Score médio dos matches
            pipeline_score = [
                {"$group": {"_id": None, "avg_score": {"$avg": "$score"}}}
            ]
            result = await self.db.matches.aggregate(pipeline_score).to_list(1)
            score_medio = result[0]["avg_score"] if result else 0
            
            # Notificações enviadas
            notificacoes_total = await self.db.notificacoes.count_documents({})
            notificacoes_lidas = await self.db.notificacoes.count_documents({"lida": True})
            
            # Notificações nas últimas 24h
            limite_24h = datetime.now(timezone.utc) - timedelta(hours=24)
            notificacoes_24h = await self.db.notificacoes.count_documents({
                "criado_em": {"$gte": limite_24h}
            })
            
            return {
                "alertas": {
                    "total": alertas_total,
                    "ativos": alertas_ativos,
                    "inativos": alertas_total - alertas_ativos
                },
                "matches": {
                    "disparados": matches_disparados,
                    "suprimidos": matches_suprimidos,
                    "score_medio": round(score_medio, 2),
                    "threshold": threshold
                },
                "notificacoes": {
                    "total": notificacoes_total,
                    "lidas": notificacoes_lidas,
                    "nao_lidas": notificacoes_total - notificacoes_lidas,
                    "ultimas_24h": notificacoes_24h
                }
            }
            
        except Exception as e:
            logger.error(f"❌ [MONITORING] Erro ao buscar métricas de alertas: {str(e)}")
            return {"erro": str(e)}
    
    async def _calcular_saude_geral(self) -> Dict[str, Any]:
        """
        Calcula score de saúde geral do sistema (0-100)
        
        Componentes:
        - Workers operacionais (30%)
        - Fontes ativas (25%)
        - Pipeline funcionando (25%)
        - Alertas sendo processados (20%)
        """
        try:
            score = 0
            detalhes = []
            
            # Workers (30%)
            workers = await self._get_workers_status()
            if "resumo" in workers:
                taxa_workers = workers["resumo"]["ok"] / max(workers["resumo"]["total"], 1)
                score += taxa_workers * 30
                detalhes.append(f"Workers: {workers['resumo']['ok']}/{workers['resumo']['total']} OK")
            
            # Pipeline (25%)
            pipeline = await self._get_pipeline_metrics()
            if "taxa_normalizacao" in pipeline:
                score += (pipeline["taxa_normalizacao"] / 100) * 25
                detalhes.append(f"Normalização: {pipeline['taxa_normalizacao']}%")
            
            # Matches (25%)
            alertas = await self._get_alertas_metrics()
            if "matches" in alertas:
                total_matches = alertas["matches"]["disparados"] + alertas["matches"]["suprimidos"]
                if total_matches > 0:
                    taxa_matches = alertas["matches"]["disparados"] / total_matches
                    score += taxa_matches * 25
                    detalhes.append(f"Matches válidos: {int(taxa_matches * 100)}%")
                else:
                    score += 25  # Sem matches ainda = OK
                    detalhes.append("Matches: Aguardando dados")
            
            # Dados disponíveis (20%)
            if "editais_normalizados" in pipeline:
                if pipeline["editais_normalizados"] > 0:
                    score += 20
                    detalhes.append(f"Editais: {pipeline['editais_normalizados']} disponíveis")
                else:
                    detalhes.append("Editais: Nenhum dado")
            
            # Determinar status geral
            if score >= 80:
                status = "SAUDÁVEL"
                emoji = "🟢"
            elif score >= 50:
                status = "ATENÇÃO"
                emoji = "🟡"
            else:
                status = "CRÍTICO"
                emoji = "🔴"
            
            return {
                "score": round(score, 1),
                "status": status,
                "emoji": emoji,
                "detalhes": detalhes
            }
            
        except Exception as e:
            logger.error(f"❌ [MONITORING] Erro ao calcular saúde geral: {str(e)}")
            return {"score": 0, "status": "ERRO", "emoji": "🔴"}
    
    async def registrar_execucao_worker(
        self,
        tipo: str,
        sucesso: bool,
        detalhes: Dict = None,
        erro: str = None
    ) -> bool:
        """
        Registra execução de um worker para monitoramento
        
        Args:
            tipo: Tipo do worker (sync_pncp, check_alerts, matcher_v2, cleanup)
            sucesso: Se a execução foi bem sucedida
            detalhes: Detalhes adicionais da execução
            erro: Mensagem de erro se houve falha
        """
        try:
            log = {
                "tipo": tipo,
                "timestamp": datetime.now(timezone.utc),
                "sucesso": sucesso,
                "erro": erro,
                "detalhes": detalhes or {}
            }
            
            await self.db.sync_logs.insert_one(log)
            
            logger.info(f"📝 [MONITORING] Registrada execução do worker '{tipo}': {'✅' if sucesso else '❌'}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ [MONITORING] Erro ao registrar execução: {str(e)}")
            return False


# Singleton
_monitoring_instance = None

def get_monitoring_service(db: AsyncIOMotorDatabase) -> MonitoringService:
    """Retorna instância do serviço de monitoramento"""
    global _monitoring_instance
    if _monitoring_instance is None:
        _monitoring_instance = MonitoringService(db)
    return _monitoring_instance
