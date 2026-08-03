"""
Scheduler de Jobs Periódicos - GSM Buscador de Editais

Responsabilidades:
- Executar verificação de alertas periodicamente (a cada 30 min)
- Limpar notificações antigas (diariamente às 3h)
- Buscar novas licitações do PNCP-OFICIAL
- Sincronizar múltiplas fontes de dados (ComprasNet, TCE-SP, MG, PR, GO)
- Registrar logs de execução para Dashboard de Monitoramento

Usa APScheduler com BackgroundScheduler para execução assíncrona.
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta, timezone
from typing import Optional
import logging
import asyncio

logger = logging.getLogger(__name__)

# Instância global do scheduler
_scheduler: Optional[AsyncIOScheduler] = None
_db = None
_notificacao_service = None
_scraper_service = None
_sync_service = None
_multi_source_sync = None
_normalizador = None


def get_scheduler() -> Optional[AsyncIOScheduler]:
    """Retorna a instância do scheduler"""
    return _scheduler


async def job_verificar_alertas():
    """
    Job principal: Verifica alertas ativos e gera notificações
    Executa a cada 30 minutos
    Registra execução para Dashboard de Monitoramento
    """
    logger.info("🔔 [SCHEDULER] Iniciando verificação periódica de alertas...")
    
    try:
        await _registrar_worker_log('check_alerts', 'inicio', {})
        
        if _notificacao_service is None:
            logger.warning("⚠️ NotificacaoService não inicializado")
            await _registrar_worker_log('check_alerts', 'erro', {'motivo': 'NotificacaoService não inicializado'})
            return
        
        # Executar verificação
        resultado = await _notificacao_service.verificar_novas_licitacoes(forcar=False)
        
        logger.info(f"✅ [SCHEDULER] Verificação concluída: {resultado}")
        
        # Registrar sucesso
        await _registrar_worker_log('check_alerts', 'sucesso', resultado)
        
        # Se houver notificações novas, enviar emails
        if resultado.get('notificacoes_criadas', 0) > 0:
            await _enviar_emails_pendentes()
        
    except Exception as e:
        logger.error(f"❌ [SCHEDULER] Erro na verificação: {str(e)}")
        await _registrar_worker_log('check_alerts', 'erro', {'erro': str(e)})


async def job_sincronizar_pncp():
    """
    Job PRINCIPAL: Sincroniza editais do PNCP-OFICIAL com banco local
    Executa a cada 15 minutos
    
    Arquitetura Local-First:
    - Baixa todos os editais novos do PNCP
    - Salva no MongoDB com índices de texto
    - Permite buscas instantâneas (<1s) vs 45s na API externa
    - Registra execução para Dashboard de Monitoramento
    """
    logger.info("🔄 [SCHEDULER] Iniciando sincronização PNCP-OFICIAL...")
    
    try:
        # Registrar início para dashboard
        await _registrar_worker_log('sync_pncp', 'inicio', {})
        
        if _sync_service is None:
            logger.warning("⚠️ SyncService não inicializado")
            await _registrar_worker_log('sync_pncp', 'erro', {'motivo': 'SyncService não inicializado'})
            return
        
        # Executar sincronização
        stats = await _sync_service.sync_pncp()
        
        logger.info("✅ [SCHEDULER] Sincronização concluída:")
        logger.info(f"   📊 Novos: {stats.get('novos', 0)}")
        logger.info(f"   📊 Atualizados: {stats.get('atualizados', 0)}")
        logger.info(f"   ⏱️ Duração: {stats.get('duracao_segundos', 0):.1f}s")
        
        # Registrar sucesso para dashboard
        await _registrar_worker_log('sync_pncp', 'sucesso', stats)
        
    except Exception as e:
        logger.error(f"❌ [SCHEDULER] Erro na sincronização: {str(e)}")
        await _registrar_worker_log('sync_pncp', 'erro', {'erro': str(e)})


async def job_limpar_notificacoes_antigas():
    """
    Job de manutenção: Remove notificações arquivadas com mais de 30 dias
    Executa diariamente às 3h
    Registra execução para Dashboard de Monitoramento
    """
    logger.info("🧹 [SCHEDULER] Iniciando limpeza de notificações antigas...")
    
    try:
        await _registrar_worker_log('cleanup', 'inicio', {})
        
        if _db is None:
            logger.warning("⚠️ Database não inicializado")
            await _registrar_worker_log('cleanup', 'erro', {'motivo': 'Database não inicializado'})
            return
        
        # Calcular data limite (30 dias atrás)
        limite = datetime.now(timezone.utc) - timedelta(days=30)
        
        # Remover notificações arquivadas antigas
        result = await _db.notificacoes.delete_many({
            'status': 'arquivada',
            'criado_em': {'$lt': limite}
        })
        
        stats = {'notificacoes_removidas': result.deleted_count}
        
        if result.deleted_count > 0:
            logger.info(f"✅ [SCHEDULER] Limpeza: {result.deleted_count} notificações removidas")
        else:
            logger.info("ℹ️ [SCHEDULER] Limpeza: Nenhuma notificação antiga para remover")
        
        await _registrar_worker_log('cleanup', 'sucesso', stats)
        
    except Exception as e:
        logger.error(f"❌ [SCHEDULER] Erro na limpeza: {str(e)}")
        await _registrar_worker_log('cleanup', 'erro', {'erro': str(e)})


async def _registrar_worker_log(worker: str, status: str, detalhes: dict = None):
    """
    Registra log de execução de worker para Dashboard de Monitoramento
    
    Args:
        worker: Nome do worker (sync_pncp, check_alerts, matcher_v2, cleanup, sync_multi)
        status: 'inicio', 'sucesso', 'erro'
        detalhes: Informações adicionais (métricas, erros, etc)
    """
    try:
        if _db is None:
            return
        
        await _db.worker_logs.insert_one({
            'worker': worker,
            'status': status,
            'timestamp': datetime.now(timezone.utc),
            'detalhes': detalhes or {}
        })
    except Exception as e:
        logger.error(f"❌ [SCHEDULER] Erro ao registrar log: {str(e)}")


async def job_sincronizar_multi_fonte():
    """
    Job SECUNDÁRIO: Sincroniza fontes adicionais (ComprasNet, TCE-SP, MG, PR, GO)
    Executa a cada 1 hora
    
    Fontes sincronizadas:
    - ComprasNet (Federal)
    - TCE-SP (São Paulo)
    - MG-CSV (Minas Gerais)
    - PR-CSV (Paraná)
    - GO-CSV (Goiás)
    
    Registra execução para Dashboard de Monitoramento
    """
    logger.info("🌐 [SCHEDULER] Iniciando sincronização multi-fonte...")
    
    try:
        await _registrar_worker_log('sync_multi', 'inicio', {})
        
        if _multi_source_sync is None:
            logger.warning("⚠️ MultiSourceSync não inicializado")
            await _registrar_worker_log('sync_multi', 'erro', {'motivo': 'MultiSourceSync não inicializado'})
            return
        
        # Sincronizar todas as fontes
        stats = await _multi_source_sync.sync_all(limit_por_fonte=30)
        
        logger.info("✅ [SCHEDULER] Multi-fonte concluída:")
        logger.info(f"   📊 Fontes OK: {stats.get('fontes_processadas', 0)}")
        logger.info(f"   📊 Total raw: {stats.get('total_raw', 0)}")
        logger.info(f"   📊 Normalizados: {stats.get('total_normalizados', 0)}")
        logger.info(f"   ⏱️ Duração: {stats.get('duracao_total_segundos', 0):.1f}s")
        
        await _registrar_worker_log('sync_multi', 'sucesso', stats)
        
    except Exception as e:
        logger.error(f"❌ [SCHEDULER] Erro na sincronização multi-fonte: {str(e)}")
        await _registrar_worker_log('sync_multi', 'erro', {'erro': str(e)})


async def job_executar_matcher():
    """
    Job de processamento: Executa Matcher v2 sobre editais normalizados
    Executa a cada 30 minutos (após sincronização)
    
    Pipeline:
        editais_normalizados → matcher_v2 → matches → notificações
    
    Registra execução para Dashboard de Monitoramento
    """
    logger.info("🎯 [SCHEDULER] Iniciando Matcher v2...")
    
    try:
        await _registrar_worker_log('matcher_v2', 'inicio', {})
        
        if _db is None:
            logger.warning("⚠️ Database não inicializado")
            await _registrar_worker_log('matcher_v2', 'erro', {'motivo': 'Database não inicializado'})
            return
        
        from services.matcher_service import MatcherServiceV2
        matcher = MatcherServiceV2(_db)
        
        stats = await matcher.processar_todos_alertas()
        
        logger.info("✅ [SCHEDULER] Matcher v2 concluído:")
        logger.info(f"   📊 Alertas: {stats.get('alertas_processados', 0)}")
        logger.info(f"   📊 Matches: {stats.get('total_matches', 0)}")
        logger.info(f"   📊 Score médio: {stats.get('score_medio', 0):.1f}")
        
        await _registrar_worker_log('matcher_v2', 'sucesso', stats)
        
    except Exception as e:
        logger.error(f"❌ [SCHEDULER] Erro no Matcher v2: {str(e)}")
        await _registrar_worker_log('matcher_v2', 'erro', {'erro': str(e)})


async def _salvar_licitacoes_pncp(licitacoes: list):
    """Salva licitações do PNCP no banco local para processamento de alertas"""
    try:
        if _db is None:
            return
        
        salvos = 0
        for lic in licitacoes:
            # Verificar se já existe
            existe = await _db.licitacoes.find_one({'id': lic.get('id')})
            if not existe:
                lic['fonte_scheduler'] = 'PNCP-OFICIAL'
                lic['importado_em'] = datetime.now(timezone.utc)
                await _db.licitacoes.insert_one(lic)
                salvos += 1
        
        if salvos > 0:
            logger.info(f"💾 [SCHEDULER] {salvos} novas licitações salvas do PNCP")
            
    except Exception as e:
        logger.error(f"❌ [SCHEDULER] Erro ao salvar licitações: {str(e)}")


async def _enviar_emails_pendentes():
    """
    Envia emails para notificações pendentes via Resend.
    Cada alerta pode ter um email_notificacao diferente.
    
    Integração com Resend:
    - Se RESEND_API_KEY configurada: envia emails reais
    - Se não configurada: modo mock (apenas logs)
    """
    from services.email_service import get_email_service
    
    try:
        if _db is None:
            return
        
        email_service = get_email_service()
        
        # Buscar notificações não notificadas por email
        cursor = _db.notificacoes.find({
            'status': 'pendente',
            'email_enviado': {'$ne': True}
        }).limit(20)
        
        notificacoes = await cursor.to_list(length=20)
        
        emails_enviados = 0
        
        for notif in notificacoes:
            # Buscar o email específico e palavra-chave do alerta
            email_destino = None
            palavra_chave = "Licitação"
            nome_alerta = None
            alerta_id = notif.get('alerta_id')
            
            if alerta_id:
                alerta = await _db.alertas_notificacao.find_one(
                    {'id': alerta_id},
                    {'email_notificacao': 1, 'palavras_chave': 1, 'nome': 1, '_id': 0}
                )
                if alerta:
                    email_destino = alerta.get('email_notificacao')
                    palavras = alerta.get('palavras_chave', [])
                    palavra_chave = ", ".join(palavras) if palavras else "Licitação"
                    nome_alerta = alerta.get('nome')
            
            # Email padrão se não definido
            if not email_destino:
                email_destino = "claudio@gruposmartmedical.com.br"
            
            # Extrair licitações da notificação
            licitacoes = notif.get('licitacoes', [])
            if not licitacoes:
                licitacoes = [{
                    'objeto': notif.get('titulo', 'Licitação encontrada'),
                    'orgao': notif.get('orgao', 'N/A'),
                    'estado': notif.get('estado', 'BR'),
                    'link_origem': notif.get('link', '#')
                }]
            
            # Enviar email via EmailService (Resend ou Mock)
            resultado = await email_service.enviar_alerta_licitacoes(
                destinatario=email_destino,
                palavra_chave=palavra_chave,
                licitacoes=licitacoes,
                nome_alerta=nome_alerta
            )
            
            if resultado.get('status') in ['sent', 'mocked']:
                emails_enviados += 1
                
                # Marcar como enviado
                await _db.notificacoes.update_one(
                    {'id': notif['id']},
                    {'$set': {
                        'email_enviado': True, 
                        'email_enviado_em': datetime.now(timezone.utc),
                        'email_enviado_para': email_destino,
                        'email_status': resultado.get('status'),
                        'email_id': resultado.get('email_id')
                    }}
                )
        
        if emails_enviados > 0:
            status = email_service.get_status()
            modo = "Resend" if status.get('configurado') else "Mock"
            logger.info(f"📧 [SCHEDULER] {emails_enviados} emails enviados via {modo}")
            
    except Exception as e:
        logger.error(f"❌ [SCHEDULER] Erro ao enviar emails: {str(e)}")


async def job_processar_alertas_email_diario():
    """
    🔔 P5: Job para processar alertas de email DIÁRIOS
    Executa diariamente às 8h da manhã
    
    Pipeline:
    1. Busca todos alertas ativos com frequência 'diario'
    2. Para cada alerta, busca novas oportunidades ATIVAS (quality >= 70)
    3. Filtra editais já enviados (controle de duplicatas)
    4. Envia email se houver novidades
    5. Atualiza registro de envios
    """
    logger.info("🔔 [SCHEDULER/P5] Iniciando processamento de alertas DIÁRIOS...")
    
    try:
        await _registrar_worker_log('alertas_email_diario', 'inicio', {})
        
        if _db is None:
            logger.warning("⚠️ Database não inicializado para alertas P5")
            await _registrar_worker_log('alertas_email_diario', 'erro', {'motivo': 'Database não inicializado'})
            return
        
        from services.alerta_service import get_alerta_service
        
        alerta_service = get_alerta_service(_db)
        stats = await alerta_service.processar_todos_alertas(frequencia='diario')
        
        logger.info("✅ [SCHEDULER/P5] Alertas DIÁRIOS processados:")
        logger.info(f"   📊 Total: {stats.get('total_alertas', 0)}")
        logger.info(f"   📧 Enviados: {stats.get('enviados', 0)}")
        logger.info(f"   📭 Sem novidades: {stats.get('sem_novidades', 0)}")
        logger.info(f"   ❌ Erros: {stats.get('erros', 0)}")
        
        await _registrar_worker_log('alertas_email_diario', 'sucesso', stats)
        
    except Exception as e:
        logger.error(f"❌ [SCHEDULER/P5] Erro nos alertas diários: {str(e)}")
        await _registrar_worker_log('alertas_email_diario', 'erro', {'erro': str(e)})


async def job_processar_alertas_email_semanal():
    """
    🔔 P5: Job para processar alertas de email SEMANAIS
    Executa toda segunda-feira às 8h da manhã
    
    Mesma lógica do diário, mas apenas para alertas com frequência 'semanal'
    """
    logger.info("🔔 [SCHEDULER/P5] Iniciando processamento de alertas SEMANAIS...")
    
    try:
        await _registrar_worker_log('alertas_email_semanal', 'inicio', {})
        
        if _db is None:
            logger.warning("⚠️ Database não inicializado para alertas P5")
            await _registrar_worker_log('alertas_email_semanal', 'erro', {'motivo': 'Database não inicializado'})
            return
        
        from services.alerta_service import get_alerta_service
        
        alerta_service = get_alerta_service(_db)
        stats = await alerta_service.processar_todos_alertas(frequencia='semanal')
        
        logger.info("✅ [SCHEDULER/P5] Alertas SEMANAIS processados:")
        logger.info(f"   📊 Total: {stats.get('total_alertas', 0)}")
        logger.info(f"   📧 Enviados: {stats.get('enviados', 0)}")
        logger.info(f"   📭 Sem novidades: {stats.get('sem_novidades', 0)}")
        logger.info(f"   ❌ Erros: {stats.get('erros', 0)}")
        
        await _registrar_worker_log('alertas_email_semanal', 'sucesso', stats)
        
    except Exception as e:
        logger.error(f"❌ [SCHEDULER/P5] Erro nos alertas semanais: {str(e)}")
        await _registrar_worker_log('alertas_email_semanal', 'erro', {'erro': str(e)})


# ==================== JOBS DE RADARES (v41.0) ====================

async def job_processar_radares_8h():
    """
    🛰️ v41.0: Job para processar radares com frequência de 8 horas
    Executa às 8h, 16h e 0h
    
    Assunto do email: 🔔 [NOME DO RADAR]: Novo Edital para [TERMO]
    """
    logger.info("🛰️ [SCHEDULER/RADAR] Iniciando processamento de radares 8H...")
    
    try:
        await _registrar_worker_log('radares_8h', 'inicio', {})
        
        if _db is None:
            logger.warning("⚠️ Database não inicializado para radares")
            await _registrar_worker_log('radares_8h', 'erro', {'motivo': 'Database não inicializado'})
            return
        
        from services.radar_service import get_radar_service
        
        radar_service = get_radar_service(_db)
        stats = await radar_service.processar_todos_radares(frequencia='8h')
        
        logger.info("✅ [SCHEDULER/RADAR] Radares 8H processados:")
        logger.info(f"   📊 Total: {stats.get('total_radares', 0)}")
        logger.info(f"   📧 Enviados: {stats.get('emails_enviados', 0)}")
        logger.info(f"   📭 Sem novidades: {stats.get('sem_novidades', 0)}")
        logger.info(f"   ❌ Erros: {stats.get('erros', 0)}")
        
        await _registrar_worker_log('radares_8h', 'sucesso', stats)
        
    except Exception as e:
        logger.error(f"❌ [SCHEDULER/RADAR] Erro nos radares 8H: {str(e)}")
        await _registrar_worker_log('radares_8h', 'erro', {'erro': str(e)})


async def job_processar_radares_12h():
    """
    🛰️ v41.0: Job para processar radares com frequência de 12 horas
    Executa às 8h e 20h
    """
    logger.info("🛰️ [SCHEDULER/RADAR] Iniciando processamento de radares 12H...")
    
    try:
        await _registrar_worker_log('radares_12h', 'inicio', {})
        
        if _db is None:
            logger.warning("⚠️ Database não inicializado para radares")
            await _registrar_worker_log('radares_12h', 'erro', {'motivo': 'Database não inicializado'})
            return
        
        from services.radar_service import get_radar_service
        
        radar_service = get_radar_service(_db)
        stats = await radar_service.processar_todos_radares(frequencia='12h')
        
        logger.info("✅ [SCHEDULER/RADAR] Radares 12H processados:")
        logger.info(f"   📊 Total: {stats.get('total_radares', 0)}")
        logger.info(f"   📧 Enviados: {stats.get('emails_enviados', 0)}")
        
        await _registrar_worker_log('radares_12h', 'sucesso', stats)
        
    except Exception as e:
        logger.error(f"❌ [SCHEDULER/RADAR] Erro nos radares 12H: {str(e)}")
        await _registrar_worker_log('radares_12h', 'erro', {'erro': str(e)})


async def job_processar_radares_24h():
    """
    🛰️ v41.0: Job para processar radares com frequência de 24 horas (diário)
    Executa às 8h da manhã
    """
    logger.info("🛰️ [SCHEDULER/RADAR] Iniciando processamento de radares DIÁRIOS...")
    
    try:
        await _registrar_worker_log('radares_24h', 'inicio', {})
        
        if _db is None:
            logger.warning("⚠️ Database não inicializado para radares")
            await _registrar_worker_log('radares_24h', 'erro', {'motivo': 'Database não inicializado'})
            return
        
        from services.radar_service import get_radar_service
        
        radar_service = get_radar_service(_db)
        stats = await radar_service.processar_todos_radares(frequencia='24h')
        
        logger.info("✅ [SCHEDULER/RADAR] Radares DIÁRIOS processados:")
        logger.info(f"   📊 Total: {stats.get('total_radares', 0)}")
        logger.info(f"   📧 Enviados: {stats.get('emails_enviados', 0)}")
        
        await _registrar_worker_log('radares_24h', 'sucesso', stats)
        
    except Exception as e:
        logger.error(f"❌ [SCHEDULER/RADAR] Erro nos radares diários: {str(e)}")
        await _registrar_worker_log('radares_24h', 'erro', {'erro': str(e)})


async def job_sincronizar_agregador():
    """
    🔄 v59.0: Job de sincronização com API Agregador
    
    MOTOR DE ALIMENTAÇÃO CLONE DO AGREGADOR
    
    Executa a cada 15 minutos para buscar dados FRESCOS de:
    - ComprasNet Federal
    - PNCP
    - BNC (Bolsa Nacional de Compras)
    - BLL Compras
    - BBMNet
    - Licitar Digital
    - ComprasNet Bahia
    - E mais 15+ portais regionais
    
    Todos os dados são salvos na collection editais_gsm.
    """
    logger.info("🔄 [MOTOR-AGREGADOR] Iniciando sincronização com Agregador...")
    
    try:
        await _registrar_worker_log('sync_agregador', 'inicio', {})
        
        if _db is None:
            logger.warning("⚠️ Database não inicializado")
            await _registrar_worker_log('sync_agregador', 'erro', {'motivo': 'Database não inicializado'})
            return
        
        from services.motor_sincronizacao_gsm import get_motor_sincronizacao
        
        motor = get_motor_sincronizacao(_db)
        stats = await motor.sincronizar()
        
        logger.info(f"✅ [MOTOR-AGREGADOR] Sync concluída: {stats.get('novos', 0)} novos, {stats.get('total_banco', 0)} total")
        
        await _registrar_worker_log('sync_agregador', 'sucesso', {
            'novos': stats.get('novos', 0),
            'atualizados': stats.get('atualizados', 0),
            'total_banco': stats.get('total_banco', 0)
        })
        
    except Exception as e:
        logger.error(f"❌ [MOTOR-AGREGADOR] Erro na sincronização: {str(e)}")
        await _registrar_worker_log('sync_agregador', 'erro', {'erro': str(e)})


async def job_sincronizar_fontes_diretas():
    """
    🌐 v59.0: Job de sincronização com FONTES DIRETAS
    
    INDEPENDÊNCIA TOTAL - Acesso direto aos portais:
    - PNCP (pncp.gov.br)
    - ComprasNet (compras.dados.gov.br)
    - BNC (bnc.org.br)
    - BLL (bll.org.br)
    - Licitar Digital
    - Compras Públicas
    
    Executa a cada 30 minutos.
    """
    logger.info("🌐 [FONTES-DIRETAS] Iniciando sincronização direta...")
    
    try:
        await _registrar_worker_log('sync_fontes_diretas', 'inicio', {})
        
        if _db is None:
            logger.warning("⚠️ Database não inicializado")
            return
        
        from services.fontes_diretas_gsm import get_fontes_diretas
        
        fontes = get_fontes_diretas(_db)
        stats = await fontes.sincronizar_todas_fontes()
        
        logger.info(f"✅ [FONTES-DIRETAS] Sync: {stats.get('total_novos', 0)} novos")
        
        await _registrar_worker_log('sync_fontes_diretas', 'sucesso', stats)
        
    except Exception as e:
        logger.error(f"❌ [FONTES-DIRETAS] Erro: {str(e)}")
        await _registrar_worker_log('sync_fontes_diretas', 'erro', {'erro': str(e)})


async def job_sync_gsm_independente():
    """
    🏠 v53.0: Job de sincronização GSM INDEPENDENTE
    
    Executa a cada 15 minutos para manter o banco local atualizado.
    
    Sincroniza termos das listas e radares do cliente diretamente
    do PNCP para a collection editais_gsm.
    """
    logger.info("🏠 [SCHEDULER/GSM] Iniciando sincronização independente...")
    
    try:
        await _registrar_worker_log('sync_gsm', 'inicio', {})
        
        if _db is None:
            logger.warning("⚠️ Database não inicializado para sync GSM")
            await _registrar_worker_log('sync_gsm', 'erro', {'motivo': 'Database não inicializado'})
            return
        
        from services.pncp_sync_service import get_pncp_sync_service
        
        sync_service = get_pncp_sync_service(_db)
        
        # Buscar termos das listas e radares do cliente
        termos_sync = set()
        
        # Coletar termos das listas
        async for lista in _db.alertas.find({"tipo": {"$in": ["lista", "shortcut"]}}, {"medicamentos": 1, "_id": 0}):
            medicamentos = lista.get('medicamentos', [])
            if medicamentos:
                termos_sync.update(medicamentos)
        
        # Coletar termos dos radares
        async for radar in _db.radares.find({}, {"termos": 1, "_id": 0}):
            termos = radar.get('termos', '')
            if termos:
                termos_sync.update([t.strip() for t in termos.split(',') if t.strip()])
        
        # Termos padrão se não houver configurados
        if not termos_sync:
            termos_sync = {'insulina', 'canabidiol', 'prolia', 'denosumabe', 'medicamento'}
        
        logger.info(f"🏠 [GSM] Sincronizando {len(termos_sync)} termos: {list(termos_sync)[:5]}...")
        
        total_novos = 0
        total_atualizados = 0
        
        for termo in list(termos_sync)[:10]:  # Limitar a 10 termos por execução
            try:
                stats = await sync_service.sincronizar_termo(
                    termo=termo,
                    dias=30,
                    limite=50
                )
                total_novos += stats.get('novos_inseridos', 0)
                total_atualizados += stats.get('atualizados', 0)
            except Exception as e:
                logger.warning(f"⚠️ [GSM] Erro ao sincronizar '{termo}': {e}")
        
        logger.info(f"✅ [SCHEDULER/GSM] Sync independente concluído:")
        logger.info(f"   📊 Novos: {total_novos}")
        logger.info(f"   📊 Atualizados: {total_atualizados}")
        
        await _registrar_worker_log('sync_gsm', 'sucesso', {
            'termos_sincronizados': len(termos_sync),
            'novos': total_novos,
            'atualizados': total_atualizados
        })
        
    except Exception as e:
        logger.error(f"❌ [SCHEDULER/GSM] Erro na sincronização: {str(e)}")
        await _registrar_worker_log('sync_gsm', 'erro', {'erro': str(e)})


def init_scheduler(db, notificacao_service, scraper_service=None, sync_service=None, multi_source_sync=None, normalizador=None):
    """
    Inicializa o scheduler com os serviços necessários
    
    Args:
        db: Conexão com MongoDB
        notificacao_service: Instância do NotificacaoService
        scraper_service: Instância do ScraperService (opcional)
        sync_service: Instância do SyncService para sincronização local
        multi_source_sync: Instância do MultiSourceSync para fontes adicionais
        normalizador: Instância do NormalizadorGenerico
    """
    global _scheduler, _db, _notificacao_service, _scraper_service, _sync_service, _multi_source_sync, _normalizador
    
    _db = db
    _notificacao_service = notificacao_service
    _scraper_service = scraper_service
    _sync_service = sync_service
    _multi_source_sync = multi_source_sync
    _normalizador = normalizador
    
    try:
        # Criar scheduler assíncrono
        _scheduler = AsyncIOScheduler(timezone="America/Sao_Paulo")
        
        # =====================================================================
        # 🔄 v59.0: MOTOR AGREGADOR (PRIORIDADE MÁXIMA - a cada 15 min)
        # =====================================================================
        # Este job clona os dados da API Agregador para o banco local
        # Mantém o banco sempre atualizado com dados frescos
        _scheduler.add_job(
            job_sincronizar_agregador,
            trigger=IntervalTrigger(minutes=15),
            id="sync_agregador_motor",
            name="🔄 Motor Agregador → MongoDB Local",
            replace_existing=True,
            max_instances=1
        )
        
        # =====================================================================
        # 🏠 v53.0: SYNC GSM INDEPENDENTE (a cada 15 min)
        # =====================================================================
        # Este job mantém o banco local editais_gsm atualizado
        # Busca termos das listas/radares do cliente e sincroniza do PNCP
        _scheduler.add_job(
            job_sync_gsm_independente,
            trigger=IntervalTrigger(minutes=15),
            id="sync_gsm_independente",
            name="🏠 Sync GSM Independente → MongoDB Local",
            replace_existing=True,
            max_instances=1
        )
        
        # =====================================================================
        # 🌐 v59.0: FONTES DIRETAS (a cada 30 min)
        # =====================================================================
        # Acesso direto aos portais sem intermediário (PNCP, BNC, BLL, etc.)
        _scheduler.add_job(
            job_sincronizar_fontes_diretas,
            trigger=IntervalTrigger(minutes=30),
            id="sync_fontes_diretas",
            name="🌐 Fontes Diretas → MongoDB Local",
            replace_existing=True,
            max_instances=1
        )
        
        # Job 0: SINCRONIZAÇÃO PNCP (a cada 15 min) - LEGADO
        if sync_service:
            _scheduler.add_job(
                job_sincronizar_pncp,
                trigger=IntervalTrigger(minutes=15),
                id="sync_pncp",
                name="Sincronização PNCP → MongoDB",
                replace_existing=True,
                max_instances=1
            )
        
        # Job 1: Verificação de alertas (a cada 30 minutos)
        # Agora busca no banco LOCAL (instantâneo) ao invés da API externa
        _scheduler.add_job(
            job_verificar_alertas,
            trigger=IntervalTrigger(minutes=30),
            id="check_alerts",
            name="Verificação de Alertas (Local)",
            replace_existing=True,
            max_instances=1
        )
        
        # Job 2: Matcher v2 (a cada 30 minutos, offset de 5 min após verificação)
        _scheduler.add_job(
            job_executar_matcher,
            trigger=IntervalTrigger(minutes=30, start_date=datetime.now() + timedelta(minutes=5)),
            id="matcher_v2",
            name="Matcher v2 - Scoring de Relevância",
            replace_existing=True,
            max_instances=1
        )
        
        # Job 3: SINCRONIZAÇÃO MULTI-FONTE (a cada 1 hora)
        # ComprasNet, TCE-SP, MG, PR, GO
        if multi_source_sync:
            _scheduler.add_job(
                job_sincronizar_multi_fonte,
                trigger=IntervalTrigger(hours=1),
                id="sync_multi",
                name="Sincronização Multi-Fonte",
                replace_existing=True,
                max_instances=1
            )
        
        # Job 4: Limpeza diária (às 3h da manhã)
        _scheduler.add_job(
            job_limpar_notificacoes_antigas,
            trigger=CronTrigger(hour=3, minute=0),
            id="cleanup",
            name="Limpeza de Notificações Antigas",
            replace_existing=True,
            max_instances=1
        )
        
        # ==================== JOBS P5 - ALERTAS POR EMAIL ====================
        
        # Job 5: Alertas de email DIÁRIOS (às 8h da manhã)
        _scheduler.add_job(
            job_processar_alertas_email_diario,
            trigger=CronTrigger(hour=8, minute=0),
            id="alertas_email_diario",
            name="P5 - Alertas Email Diários",
            replace_existing=True,
            max_instances=1
        )
        
        # Job 6: Alertas de email SEMANAIS (Segunda-feira às 8h)
        _scheduler.add_job(
            job_processar_alertas_email_semanal,
            trigger=CronTrigger(day_of_week='mon', hour=8, minute=0),
            id="alertas_email_semanal",
            name="P5 - Alertas Email Semanais",
            replace_existing=True,
            max_instances=1
        )
        
        # ==================== JOBS DE RADARES v41.0 ====================
        
        # Job 7: Radares 8H (às 0h, 8h, 16h)
        _scheduler.add_job(
            job_processar_radares_8h,
            trigger=CronTrigger(hour='0,8,16', minute=0),
            id="radares_8h",
            name="v41.0 - Radares 8 em 8 horas",
            replace_existing=True,
            max_instances=1
        )
        
        # Job 8: Radares 12H (às 8h e 20h)
        _scheduler.add_job(
            job_processar_radares_12h,
            trigger=CronTrigger(hour='8,20', minute=0),
            id="radares_12h",
            name="v41.0 - Radares 12 em 12 horas",
            replace_existing=True,
            max_instances=1
        )
        
        # Job 9: Radares 24H/Diário (às 8h)
        _scheduler.add_job(
            job_processar_radares_24h,
            trigger=CronTrigger(hour=8, minute=0),
            id="radares_24h",
            name="v41.0 - Radares Diários",
            replace_existing=True,
            max_instances=1
        )
        
        # Job 10: Radar ANVISA - Desabastecimento (a cada 12h)
        async def job_anvisa_radar():
            try:
                from services.anvisa_scraper import AnvisaScraper
                from services.desabastecimento_service import DesabastecimentoService
                scraper = AnvisaScraper()
                alertas = await scraper.coletar_tudo()
                descont = await scraper.coletar_descontinuacao()
                alertas.extend(descont)
                svc = DesabastecimentoService(_db)
                await svc.processar_alertas(alertas)
                logger.info(f"ANVISA Radar: {len(alertas)} alertas coletados e processados")
            except Exception as e:
                logger.error(f"ANVISA Radar erro: {e}")
        
        _scheduler.add_job(
            job_anvisa_radar,
            trigger=CronTrigger(hour='7,19', minute=0),
            id="anvisa_radar",
            name="v78.0 - Radar ANVISA Desabastecimento",
            replace_existing=True,
            max_instances=1
        )

        # Job 10b: Registro ANVISA - dados abertos de medicamentos (1x/dia, o dataset muda pouco)
        async def job_anvisa_registro():
            try:
                from services.anvisa_registro_service import sincronizar_registro_medicamentos
                total = await sincronizar_registro_medicamentos(_db)
                logger.info(f"ANVISA Registro (dados abertos): {total} registros nao-ativos sincronizados")
            except Exception as e:
                logger.error(f"ANVISA Registro (dados abertos) erro: {e}")

        _scheduler.add_job(
            job_anvisa_registro,
            trigger=CronTrigger(hour=5, minute=30),
            id="anvisa_registro_dados_abertos",
            name="Registro ANVISA - Dados Abertos (situacao de registro)",
            replace_existing=True,
            max_instances=1
        )

        # Job 11: Radar Farmacêutico v3.1 - Inteligência de Desabastecimento (a cada 12h)
        async def job_radar_farmaceutico_v31():
            try:
                from services.radar_farmaceutico_service import get_radar_farmaceutico_service
                svc = get_radar_farmaceutico_service(_db)
                stats = await svc.executar_scan()
                logger.info(f"🛰️ Radar Farmacêutico v3.1: scan concluído. Matches: {stats.get('matches_encontrados', 0)}")
                await _registrar_worker_log('radar_farmaceutico_v31', 'sucesso', stats)
            except Exception as e:
                logger.error(f"❌ Radar Farmacêutico v3.1 erro: {e}")
                await _registrar_worker_log('radar_farmaceutico_v31', 'erro', {'erro': str(e)})

        _scheduler.add_job(
            job_radar_farmaceutico_v31,
            trigger=CronTrigger(hour='6,18', minute=30),  # 6:30 e 18:30 (fora do rush da ANVISA)
            id="radar_farma_v31",
            name="v78.0 - Radar Farmacêutico Inteligente",
            replace_existing=True,
            max_instances=1
        )
        
        # Iniciar scheduler
        _scheduler.start()
        
        logger.info("=" * 60)
        logger.info("✅ APScheduler inicializado com sucesso!")
        logger.info("📋 Jobs configurados:")
        if sync_service:
            logger.info("   0. 🔄 Sincronização PNCP → MongoDB - a cada 15 min")
        logger.info("   1. 🔔 Verificação de Alertas (Local) - a cada 30 min")
        logger.info("   2. 🎯 Matcher v2 - a cada 30 min (offset 5min)")
        if multi_source_sync:
            logger.info("   3. 🌐 Sincronização Multi-Fonte - a cada 1 hora")
        logger.info("   4. 🧹 Limpeza de Notificações - diário às 03:00")
        logger.info("   5. 📧 P5: Alertas Email Diários - diário às 08:00")
        logger.info("   6. 📧 P5: Alertas Email Semanais - segunda às 08:00")
        logger.info("   7. 🛰️ v41: Radares 8H - às 00:00, 08:00, 16:00")
        logger.info("   8. 🛰️ v41: Radares 12H - às 08:00, 20:00")
        logger.info("   9. 🛰️ v41: Radares Diários - às 08:00")
        logger.info("  10. 💊 v78: Radar ANVISA - às 07:00, 19:00")
        logger.info("  10b. 📋 Registro ANVISA (dados abertos) - às 05:30")
        logger.info("  11. 🛰️ v78: Radar Farmacêutico v3.1 - às 06:30, 18:30")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar scheduler: {str(e)}")
        return False


def shutdown_scheduler():
    """Encerra o scheduler de forma limpa"""
    global _scheduler
    
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("🛑 Scheduler encerrado")


async def executar_verificacao_manual():
    """Executa verificação manual (chamada via API)"""
    await job_verificar_alertas()
    if _sync_service:
        await job_sincronizar_pncp()
