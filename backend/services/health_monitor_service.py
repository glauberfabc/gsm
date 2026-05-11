"""
Serviço de monitoramento de saúde dos scrapers
"""

from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timedelta
from typing import List
import logging

from models.scraper_status import ScraperExecution, ScraperHealthStatus, SystemHealthStatus

logger = logging.getLogger(__name__)


class HealthMonitorService:
    """
    Gerencia o monitoramento de saúde dos scrapers
    
    Responsabilidades:
    - Registrar execuções de scrapers
    - Calcular métricas de saúde
    - Fornecer status em tempo real
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.scraper_executions
    
    async def registrar_execucao(
        self,
        fonte: str,
        status: str,
        resultados_count: int = 0,
        termo_busca: str = None,
        tempo_execucao_ms: int = None,
        erro_mensagem: str = None
    ):
        """
        Registra uma execução de scraper no banco
        
        Args:
            fonte: Nome da fonte (PNCP, ComprasNet, etc.)
            status: success, error, timeout
            resultados_count: Número de resultados obtidos
            termo_busca: Termo pesquisado (opcional)
            tempo_execucao_ms: Tempo de execução em milissegundos
            erro_mensagem: Mensagem de erro se aplicável
        """
        try:
            execucao = {
                'fonte': fonte,
                'timestamp': datetime.now(),
                'status': status,
                'resultados_count': resultados_count,
                'termo_busca': termo_busca,
                'tempo_execucao_ms': tempo_execucao_ms,
                'erro_mensagem': erro_mensagem
            }
            
            await self.collection.insert_one(execucao)
            logger.debug(f"✅ Execução registrada: {fonte} - {status}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao registrar execução: {str(e)}")
    
    async def get_scraper_health(self, fonte: str) -> ScraperHealthStatus:
        """
        Calcula status de saúde de um scraper específico
        
        Args:
            fonte: Nome da fonte
            
        Returns:
            ScraperHealthStatus com métricas das últimas 24h
        """
        try:
            # Buscar execuções das últimas 24h
            limite_24h = datetime.now() - timedelta(hours=24)
            
            execucoes = await self.collection.find({
                'fonte': fonte,
                'timestamp': {'$gte': limite_24h}
            }).to_list(1000)
            
            if not execucoes:
                return ScraperHealthStatus(
                    fonte=fonte,
                    status='UNKNOWN',
                    total_execucoes_24h=0,
                    total_sucessos_24h=0,
                    total_erros_24h=0,
                    total_resultados_24h=0,
                    taxa_sucesso_24h=0.0
                )
            
            # Calcular métricas
            total_execucoes = len(execucoes)
            sucessos = [e for e in execucoes if e['status'] == 'success']
            erros = [e for e in execucoes if e['status'] in ['error', 'timeout']]
            
            total_sucessos = len(sucessos)
            total_erros = len(erros)
            total_resultados = sum(e.get('resultados_count', 0) for e in execucoes)
            taxa_sucesso = (total_sucessos / total_execucoes * 100) if total_execucoes > 0 else 0.0
            
            # Última execução com sucesso
            ultima_sucesso = None
            if sucessos:
                ultima_sucesso = max(sucessos, key=lambda x: x['timestamp'])['timestamp']
            
            # Última execução com erro
            ultima_erro = None
            ultima_msg_erro = None
            if erros:
                ultimo_erro_doc = max(erros, key=lambda x: x['timestamp'])
                ultima_erro = ultimo_erro_doc['timestamp']
                ultima_msg_erro = ultimo_erro_doc.get('erro_mensagem')
            
            # Tempo médio de execução
            tempos = [e.get('tempo_execucao_ms') for e in execucoes if e.get('tempo_execucao_ms')]
            tempo_medio = int(sum(tempos) / len(tempos)) if tempos else None
            
            # Determinar status geral
            if taxa_sucesso >= 90:
                status_geral = 'UP'
            elif taxa_sucesso >= 50:
                status_geral = 'DEGRADED'
            else:
                status_geral = 'DOWN'
            
            # Se não há sucesso nas últimas 2 horas, considerar DOWN
            if ultima_sucesso:
                if datetime.now() - ultima_sucesso > timedelta(hours=2):
                    status_geral = 'DOWN'
            
            return ScraperHealthStatus(
                fonte=fonte,
                status=status_geral,
                ultima_execucao_sucesso=ultima_sucesso,
                ultima_execucao_erro=ultima_erro,
                total_execucoes_24h=total_execucoes,
                total_sucessos_24h=total_sucessos,
                total_erros_24h=total_erros,
                total_resultados_24h=total_resultados,
                taxa_sucesso_24h=round(taxa_sucesso, 1),
                tempo_medio_execucao_ms=tempo_medio,
                ultima_mensagem_erro=ultima_msg_erro
            )
            
        except Exception as e:
            logger.error(f"❌ Erro ao calcular saúde de {fonte}: {str(e)}")
            return ScraperHealthStatus(
                fonte=fonte,
                status='ERROR',
                total_execucoes_24h=0,
                total_sucessos_24h=0,
                total_erros_24h=0,
                total_resultados_24h=0,
                taxa_sucesso_24h=0.0
            )
    
    async def get_system_health(self) -> SystemHealthStatus:
        """
        Retorna status de saúde geral do sistema
        
        Returns:
            SystemHealthStatus com resumo de todas as fontes
        """
        try:
            # Listar todas as fontes conhecidas (incluindo RJ, RS, SC, PR, BA, PE, SP-TCE, MG, GO e ES)
            fontes = [
                'PNCP', 'PNCP-OFICIAL', 'ComprasNet', 'BEC/SP', 'AGREGADOR',
                'RJ', 'RS', 'SC', 'PR', 'BA', 'PE', 'SP-TCE', 'MG', 'GO', 'ES-CSV',
                'SCRAPER-CE', 'SCRAPER-SP'
            ]
            
            # Calcular saúde de cada fonte
            scrapers_health = []
            for fonte in fontes:
                health = await self.get_scraper_health(fonte)
                scrapers_health.append(health)
            
            # Calcular métricas gerais
            total_fontes = len(scrapers_health)
            fontes_up = sum(1 for s in scrapers_health if s.status == 'UP')
            fontes_down = sum(1 for s in scrapers_health if s.status == 'DOWN')
            fontes_degraded = sum(1 for s in scrapers_health if s.status == 'DEGRADED')
            
            # Determinar status geral do sistema
            if fontes_down == 0 and fontes_degraded == 0:
                status_geral = 'HEALTHY'
            elif fontes_down == 0:
                status_geral = 'DEGRADED'
            else:
                status_geral = 'DOWN'
            
            return SystemHealthStatus(
                timestamp=datetime.now(),
                status_geral=status_geral,
                total_fontes=total_fontes,
                fontes_up=fontes_up,
                fontes_down=fontes_down,
                fontes_degraded=fontes_degraded,
                scrapers=scrapers_health
            )
            
        except Exception as e:
            logger.error(f"❌ Erro ao calcular saúde do sistema: {str(e)}")
            return SystemHealthStatus(
                timestamp=datetime.now(),
                status_geral='ERROR',
                total_fontes=0,
                fontes_up=0,
                fontes_down=0,
                fontes_degraded=0,
                scrapers=[]
            )
    
    async def limpar_execucoes_antigas(self, dias: int = 7):
        """
        Remove registros de execuções antigas para economizar espaço
        
        Args:
            dias: Número de dias a manter (padrão: 7)
        """
        try:
            limite = datetime.now() - timedelta(days=dias)
            
            result = await self.collection.delete_many({
                'timestamp': {'$lt': limite}
            })
            
            logger.info(f"🗑️ Limpeza: {result.deleted_count} execuções antigas removidas")
            
        except Exception as e:
            logger.error(f"❌ Erro na limpeza: {str(e)}")
