"""
Sincronizador Multi-Fonte - GSM Buscador de Editais
=====================================================

Orquestra a sincronização de múltiplas fontes de dados com o pipeline canônico.

Fontes suportadas (ordem de prioridade):
1. PNCP-OFICIAL (já ativo)
2. ComprasNet (Federal)
3. TCE-SP (São Paulo)
4. MG-CSV (Minas Gerais)
5. PR-CSV (Paraná)  
6. GO-CSV (Goiás)

Arquitetura:
    MultiSourceSync.sync_all()
        → Scraper.buscar_licitacoes()
        → editais_sync (raw)
        → NormalizadorGenerico.normalizar_lote()
        → editais_normalizados

Características:
- Execução paralela opcional de scrapers independentes
- Logging detalhado para Dashboard de Monitoramento
- Fallback gracioso se uma fonte falhar
- Métricas por fonte para análise de ROI
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


class MultiSourceSync:
    """
    Orquestrador de sincronização multi-fonte
    
    Responsabilidades:
    - Gerenciar scrapers de múltiplas fontes
    - Normalizar dados para formato canônico
    - Registrar métricas para dashboard
    - Tratar falhas de forma resiliente
    """
    
    def __init__(self, db, normalizador):
        """
        Inicializa o sincronizador multi-fonte
        
        Args:
            db: Conexão com MongoDB
            normalizador: Instância do NormalizadorGenerico
        """
        self.db = db
        self.normalizador = normalizador
        self.editais_sync = db.editais_sync
        self.worker_logs = db.worker_logs
        self.sync_stats = db.sync_stats
        
        # Scrapers disponíveis (serão inicializados sob demanda)
        self._scrapers = {}
        
    async def registrar_worker(self, worker: str, status: str, detalhes: Dict = None):
        """
        Registra execução de worker para Dashboard de Monitoramento
        
        Args:
            worker: Nome do worker (ex: 'sync_comprasnet')
            status: 'inicio', 'sucesso', 'erro'
            detalhes: Métricas e informações adicionais
        """
        try:
            await self.worker_logs.insert_one({
                'worker': worker,
                'status': status,
                'timestamp': datetime.now(timezone.utc),
                'detalhes': detalhes or {}
            })
        except Exception as e:
            logger.error(f"❌ Erro ao registrar worker: {str(e)}")
    
    def _get_scraper(self, fonte: str):
        """
        Obtém instância do scraper para uma fonte
        Lazy loading para evitar imports desnecessários
        """
        if fonte not in self._scrapers:
            if fonte == 'comprasnet':
                from scrapers.comprasnet_client import ComprasNetClient
                self._scrapers[fonte] = ComprasNetClient()
            elif fonte == 'tce-sp':
                from scrapers.sao_paulo_tce_importer import SaoPauloTceCsvImporter
                self._scrapers[fonte] = SaoPauloTceCsvImporter()
            elif fonte == 'mg-csv':
                from scrapers.minas_gerais_csv_importer import MinasGeraisCsvImporter
                self._scrapers[fonte] = MinasGeraisCsvImporter()
            elif fonte == 'pr-csv':
                from scrapers.parana_csv_importer import ParanaCsvImporter
                self._scrapers[fonte] = ParanaCsvImporter()
            elif fonte == 'go-csv':
                from scrapers.goias_csv_importer import GoiasCsvImporter
                self._scrapers[fonte] = GoiasCsvImporter()
        
        return self._scrapers.get(fonte)
    
    async def sync_fonte(self, fonte: str, limit: int = 50, apenas_saude: bool = False) -> Dict[str, Any]:
        """
        Sincroniza uma fonte específica
        
        Args:
            fonte: Identificador da fonte (comprasnet, tce-sp, mg-csv, pr-csv, go-csv)
            limit: Máximo de registros a buscar
            apenas_saude: Se True, filtra apenas editais de saúde
            
        Returns:
            Dict com estatísticas da sincronização
        """
        worker_name = f"sync_{fonte}"
        inicio = datetime.now(timezone.utc)
        
        stats = {
            'fonte': fonte,
            'inicio': inicio.isoformat(),
            'status': 'iniciando',
            'raw_encontrados': 0,
            'novos': 0,
            'atualizados': 0,
            'normalizados': 0,
            'erros': 0
        }
        
        try:
            # Registrar início
            await self.registrar_worker(worker_name, 'inicio', {'fonte': fonte})
            
            logger.info(f"🚀 [MULTI-SYNC] Iniciando sincronização: {fonte}")
            
            # Obter scraper
            scraper = self._get_scraper(fonte)
            if not scraper:
                raise ValueError(f"Scraper não encontrado para fonte: {fonte}")
            
            # Buscar licitações
            logger.info(f"  📥 Buscando dados de {fonte}...")
            
            # Diferentes scrapers têm diferentes assinaturas
            if fonte == 'comprasnet':
                # ComprasNet é síncrono
                licitacoes = scraper.buscar_licitacoes(
                    termo_busca=None,
                    apenas_futuras=True,
                    limit=limit
                )
            elif fonte == 'tce-sp':
                # TCE-SP tem assinatura específica
                licitacoes = await scraper.buscar_licitacoes(
                    termo_busca=None,
                    limit=limit
                )
            else:
                # Demais são assíncronos com parâmetros padrão
                try:
                    licitacoes = await scraper.buscar_licitacoes(
                        termo_busca=None,
                        apenas_saude=apenas_saude,
                        apenas_futuras=True,
                        limit=limit
                    )
                except TypeError:
                    # Fallback para scrapers com assinatura simples
                    licitacoes = await scraper.buscar_licitacoes(
                        termo_busca=None,
                        limit=limit
                    )
            
            stats['raw_encontrados'] = len(licitacoes)
            logger.info(f"  ✅ {fonte}: {len(licitacoes)} licitações encontradas")
            
            if not licitacoes:
                stats['status'] = 'sem_dados'
                await self.registrar_worker(worker_name, 'sucesso', stats)
                return stats
            
            # Salvar no banco raw (editais_sync)
            from pymongo import UpdateOne
            operacoes = []
            
            for lic in licitacoes:
                try:
                    # Gerar ID único
                    fonte_id = lic.get('fonte_id') or f"{fonte}-{lic.get('numero_processo', '')}-{lic.get('id', '')}"
                    
                    # Preparar documento
                    doc = {
                        **lic,
                        'fonte_id': fonte_id,
                        'fonte': fonte.upper(),
                        'sincronizado_em': datetime.now(timezone.utc)
                    }
                    
                    # Upsert por fonte_id
                    operacoes.append(
                        UpdateOne(
                            {'fonte_id': fonte_id},
                            {'$set': doc, '$setOnInsert': {'criado_em': datetime.now(timezone.utc)}},
                            upsert=True
                        )
                    )
                except Exception as e:
                    logger.warning(f"  ⚠️ Erro ao preparar doc: {str(e)}")
                    stats['erros'] += 1
            
            # Executar bulk write
            if operacoes:
                result = await self.editais_sync.bulk_write(operacoes, ordered=False)
                stats['novos'] = result.upserted_count
                stats['atualizados'] = result.modified_count
                
                logger.info(f"  💾 {fonte}: {stats['novos']} novos, {stats['atualizados']} atualizados")
            
            # Normalizar para formato canônico
            logger.info(f"  🔄 Normalizando dados de {fonte}...")
            norm_stats = await self.normalizador.normalizar_lote(licitacoes, fonte)
            stats['normalizados'] = norm_stats.get('inseridos', 0) + norm_stats.get('atualizados', 0)
            
            logger.info(f"  ✅ {fonte}: {stats['normalizados']} normalizados")
            
            stats['status'] = 'sucesso'
            stats['fim'] = datetime.now(timezone.utc).isoformat()
            stats['duracao_segundos'] = (datetime.now(timezone.utc) - inicio).total_seconds()
            
            # Registrar sucesso (criar cópia para evitar problemas de serialização)
            stats_log = {k: v for k, v in stats.items() if k not in ['_id']}
            await self.registrar_worker(worker_name, 'sucesso', stats_log)
            
            # Salvar estatísticas
            await self.sync_stats.insert_one({**stats_log, 'timestamp': datetime.now(timezone.utc)})
            
            logger.info(f"✅ [MULTI-SYNC] {fonte} concluído em {stats['duracao_segundos']:.1f}s")
            
        except Exception as e:
            logger.error(f"❌ [MULTI-SYNC] Erro em {fonte}: {str(e)}")
            import traceback
            logger.debug(traceback.format_exc())
            
            stats['status'] = 'erro'
            stats['erro'] = str(e)
            stats['fim'] = datetime.now(timezone.utc).isoformat()
            stats['duracao_segundos'] = (datetime.now(timezone.utc) - inicio).total_seconds()
            
            # Registrar erro
            await self.registrar_worker(worker_name, 'erro', stats)
        
        # Retornar stats sem _id (serialização segura)
        return {k: v for k, v in stats.items() if k not in ['_id']}
    
    async def sync_all(self, fontes: List[str] = None, limit_por_fonte: int = 50) -> Dict[str, Any]:
        """
        Sincroniza todas as fontes configuradas
        
        Args:
            fontes: Lista de fontes (default: todas disponíveis)
            limit_por_fonte: Máximo de registros por fonte
            
        Returns:
            Dict com estatísticas consolidadas
        """
        if fontes is None:
            fontes = ['comprasnet', 'tce-sp', 'mg-csv', 'pr-csv', 'go-csv']
        
        inicio = datetime.now(timezone.utc)
        
        stats_consolidado = {
            'inicio': inicio.isoformat(),
            'fontes_processadas': 0,
            'fontes_com_erro': 0,
            'total_raw': 0,
            'total_novos': 0,
            'total_normalizados': 0,
            'detalhes_por_fonte': {}
        }
        
        logger.info(f"🚀 [MULTI-SYNC] Iniciando sincronização de {len(fontes)} fontes...")
        
        for fonte in fontes:
            try:
                stats = await self.sync_fonte(fonte, limit=limit_por_fonte)
                stats_consolidado['detalhes_por_fonte'][fonte] = stats
                
                if stats.get('status') == 'sucesso':
                    stats_consolidado['fontes_processadas'] += 1
                    stats_consolidado['total_raw'] += stats.get('raw_encontrados', 0)
                    stats_consolidado['total_novos'] += stats.get('novos', 0)
                    stats_consolidado['total_normalizados'] += stats.get('normalizados', 0)
                else:
                    stats_consolidado['fontes_com_erro'] += 1
                    
            except Exception as e:
                logger.error(f"❌ Erro em {fonte}: {str(e)}")
                stats_consolidado['fontes_com_erro'] += 1
                stats_consolidado['detalhes_por_fonte'][fonte] = {'status': 'erro', 'erro': str(e)}
        
        stats_consolidado['fim'] = datetime.now(timezone.utc).isoformat()
        stats_consolidado['duracao_total_segundos'] = (datetime.now(timezone.utc) - inicio).total_seconds()
        
        logger.info("✅ [MULTI-SYNC] Sincronização completa:")
        logger.info(f"   📊 Fontes OK: {stats_consolidado['fontes_processadas']}/{len(fontes)}")
        logger.info(f"   📥 Total raw: {stats_consolidado['total_raw']}")
        logger.info(f"   🆕 Novos: {stats_consolidado['total_novos']}")
        logger.info(f"   ✅ Normalizados: {stats_consolidado['total_normalizados']}")
        logger.info(f"   ⏱️ Duração: {stats_consolidado['duracao_total_segundos']:.1f}s")
        
        return stats_consolidado
    
    async def get_status_fontes(self) -> List[Dict]:
        """
        Retorna status de todas as fontes para o Dashboard
        
        Returns:
            Lista com status de cada fonte
        """
        fontes = ['pncp', 'comprasnet', 'tce-sp', 'mg-csv', 'pr-csv', 'go-csv']
        status_list = []
        
        for fonte in fontes:
            try:
                # Buscar última execução
                ultima_exec = await self.worker_logs.find_one(
                    {'worker': f'sync_{fonte}'},
                    sort=[('timestamp', -1)]
                )
                
                # Buscar total de registros
                total = await self.editais_sync.count_documents({'fonte': fonte.upper()})
                
                # Determinar status
                if ultima_exec:
                    status = ultima_exec.get('status', 'DESCONHECIDO')
                    ultima_ts = ultima_exec.get('timestamp')
                    
                    # Verificar se está atrasado (>1 hora desde última execução bem-sucedida)
                    if status == 'sucesso' and ultima_ts:
                        if datetime.now(timezone.utc) - ultima_ts > timedelta(hours=1):
                            status = 'ATRASO'
                        else:
                            status = 'OK'
                    elif status == 'erro':
                        status = 'ERRO'
                    else:
                        status = status.upper()
                else:
                    status = 'DESCONHECIDO'
                    ultima_ts = None
                
                status_list.append({
                    'fonte': fonte,
                    'status': status,
                    'ultima_execucao': ultima_ts.isoformat() if ultima_ts else None,
                    'total_registros': total,
                    'detalhes': ultima_exec.get('detalhes', {}) if ultima_exec else {}
                })
                
            except Exception as e:
                status_list.append({
                    'fonte': fonte,
                    'status': 'ERRO',
                    'erro': str(e)
                })
        
        return status_list


# Instância global
_multi_source_sync_instance = None


def get_multi_source_sync(db, normalizador) -> MultiSourceSync:
    """Retorna instância do sincronizador multi-fonte (singleton)"""
    global _multi_source_sync_instance
    if _multi_source_sync_instance is None:
        _multi_source_sync_instance = MultiSourceSync(db, normalizador)
    return _multi_source_sync_instance
