"""
Serviço de Notificações - GSM Buscador de Editais

Responsabilidades:
- Gerenciar alertas de usuário
- Verificar novas licitações periodicamente
- Gerar notificações baseadas em critérios
- Fornecer estatísticas de notificações

Frequência: A cada 6 horas (configurável por alerta)
Canal: Dashboard interno (sem email nesta versão)
"""

from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from uuid import uuid4
import logging
import asyncio

from models.notificacao import (
    AlertaConfig, AlertaConfigCreate, AlertaConfigUpdate,
    Notificacao, NotificacaoCreate, NotificacaoStats,
    StatusNotificacao, TipoAlerta
)

logger = logging.getLogger(__name__)


class NotificacaoService:
    """
    Serviço de gerenciamento de notificações e alertas
    
    Features:
    - CRUD de alertas de licitação
    - Verificação automática de novas licitações
    - Geração de notificações por critério
    - Estatísticas e contadores
    """
    
    # Limites de configuração
    MAX_ALERTAS_POR_USUARIO = 10
    MAX_PALAVRAS_POR_ALERTA = 20
    FREQUENCIA_MINIMA_HORAS = 1
    FREQUENCIA_PADRAO_HORAS = 6
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.alertas_collection = db.alertas_notificacao
        self.notificacoes_collection = db.notificacoes
        self.licitacoes_collection = db.licitacoes
        
        # Estado interno
        self._ultima_verificacao_global: Optional[datetime] = None
        self._verificacao_em_andamento: bool = False
    
    # ==================== CRUD DE ALERTAS ====================
    
    async def criar_alerta(self, alerta_data: AlertaConfigCreate) -> AlertaConfig:
        """
        Cria um novo alerta de notificação
        
        Args:
            alerta_data: Dados do alerta
            
        Returns:
            AlertaConfig criado
            
        Raises:
            ValueError: Se limite de alertas atingido
        """
        try:
            # Verificar limite de alertas
            total_alertas = await self.alertas_collection.count_documents({})
            if total_alertas >= self.MAX_ALERTAS_POR_USUARIO:
                raise ValueError(f"Limite de {self.MAX_ALERTAS_POR_USUARIO} alertas atingido")
            
            # Validar palavras-chave
            if len(alerta_data.palavras_chave) > self.MAX_PALAVRAS_POR_ALERTA:
                raise ValueError(f"Máximo de {self.MAX_PALAVRAS_POR_ALERTA} palavras-chave por alerta")
            
            # Criar documento
            alerta_id = str(uuid4())
            agora = datetime.now(timezone.utc)
            
            alerta_doc = {
                'id': alerta_id,
                'nome': alerta_data.nome,
                'tipo': alerta_data.tipo.value,
                'ativo': alerta_data.ativo,
                'palavras_chave': [p.lower().strip() for p in alerta_data.palavras_chave],
                'lista_customizada_id': alerta_data.lista_customizada_id,
                'estados': [e.upper() for e in alerta_data.estados],
                'modalidades': alerta_data.modalidades,
                'frequencia_horas': alerta_data.frequencia_horas,
                'email_notificacao': alerta_data.email_notificacao,  # Email customizado por alerta
                'criado_em': agora,
                'atualizado_em': agora,
                'ultima_verificacao': None,
                'total_notificacoes': 0
            }
            
            await self.alertas_collection.insert_one(alerta_doc)
            
            logger.info(f"✅ Alerta criado: {alerta_data.nome} (ID: {alerta_id})")
            
            return AlertaConfig(**alerta_doc)
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"❌ Erro ao criar alerta: {str(e)}")
            raise
    
    async def listar_alertas(self, apenas_ativos: bool = False) -> List[AlertaConfig]:
        """Lista todos os alertas"""
        try:
            filtro = {'ativo': True} if apenas_ativos else {}
            
            cursor = self.alertas_collection.find(filtro, {'_id': 0})
            alertas = await cursor.to_list(length=100)
            
            return [AlertaConfig(**a) for a in alertas]
            
        except Exception as e:
            logger.error(f"❌ Erro ao listar alertas: {str(e)}")
            return []
    
    async def obter_alerta(self, alerta_id: str) -> Optional[AlertaConfig]:
        """Obtém um alerta específico"""
        try:
            alerta = await self.alertas_collection.find_one(
                {'id': alerta_id},
                {'_id': 0}
            )
            
            return AlertaConfig(**alerta) if alerta else None
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter alerta {alerta_id}: {str(e)}")
            return None
    
    async def atualizar_alerta(self, alerta_id: str, update_data: AlertaConfigUpdate) -> Optional[AlertaConfig]:
        """Atualiza um alerta existente"""
        try:
            # Preparar dados de atualização
            update_fields = {}
            
            if update_data.nome is not None:
                update_fields['nome'] = update_data.nome
            if update_data.ativo is not None:
                update_fields['ativo'] = update_data.ativo
            if update_data.palavras_chave is not None:
                update_fields['palavras_chave'] = [p.lower().strip() for p in update_data.palavras_chave]
            if update_data.lista_customizada_id is not None:
                update_fields['lista_customizada_id'] = update_data.lista_customizada_id
            if update_data.estados is not None:
                update_fields['estados'] = [e.upper() for e in update_data.estados]
            if update_data.modalidades is not None:
                update_fields['modalidades'] = update_data.modalidades
            if update_data.frequencia_horas is not None:
                update_fields['frequencia_horas'] = update_data.frequencia_horas
            if update_data.email_notificacao is not None:
                update_fields['email_notificacao'] = update_data.email_notificacao
            
            update_fields['atualizado_em'] = datetime.now(timezone.utc)
            
            # Executar atualização
            result = await self.alertas_collection.update_one(
                {'id': alerta_id},
                {'$set': update_fields}
            )
            
            if result.modified_count == 0:
                return None
            
            return await self.obter_alerta(alerta_id)
            
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar alerta {alerta_id}: {str(e)}")
            raise
    
    async def deletar_alerta(self, alerta_id: str) -> bool:
        """Deleta um alerta e suas notificações"""
        try:
            # Deletar notificações relacionadas
            await self.notificacoes_collection.delete_many({'alerta_id': alerta_id})
            
            # Deletar alerta
            result = await self.alertas_collection.delete_one({'id': alerta_id})
            
            if result.deleted_count > 0:
                logger.info(f"🗑️ Alerta deletado: {alerta_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Erro ao deletar alerta {alerta_id}: {str(e)}")
            return False
    
    # ==================== NOTIFICAÇÕES ====================
    
    async def listar_notificacoes(
        self,
        status: Optional[StatusNotificacao] = None,
        alerta_id: Optional[str] = None,
        limite: int = 50,
        pagina: int = 1
    ) -> Dict[str, Any]:
        """
        Lista notificações com filtros e paginação
        
        Args:
            status: Filtrar por status (pendente, lida, arquivada)
            alerta_id: Filtrar por alerta específico
            limite: Itens por página
            pagina: Número da página
            
        Returns:
            Dict com notificações e metadados
        """
        try:
            # Construir filtro
            filtro = {}
            if status:
                filtro['status'] = status.value
            if alerta_id:
                filtro['alerta_id'] = alerta_id
            
            # Contar total
            total = await self.notificacoes_collection.count_documents(filtro)
            pendentes = await self.notificacoes_collection.count_documents({'status': 'pendente'})
            
            # Buscar com paginação
            skip = (pagina - 1) * limite
            
            cursor = self.notificacoes_collection.find(
                filtro,
                {'_id': 0}
            ).sort('criado_em', -1).skip(skip).limit(limite)
            
            notificacoes = await cursor.to_list(length=limite)
            
            return {
                'notificacoes': [Notificacao(**n) for n in notificacoes],
                'total': total,
                'pendentes': pendentes,
                'pagina': pagina,
                'por_pagina': limite
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao listar notificações: {str(e)}")
            return {'notificacoes': [], 'total': 0, 'pendentes': 0, 'pagina': 1, 'por_pagina': limite}
    
    async def marcar_como_lida(self, notificacao_id: str) -> bool:
        """Marca uma notificação como lida"""
        try:
            result = await self.notificacoes_collection.update_one(
                {'id': notificacao_id},
                {
                    '$set': {
                        'status': 'lida',
                        'lido_em': datetime.now(timezone.utc)
                    }
                }
            )
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"❌ Erro ao marcar notificação como lida: {str(e)}")
            return False
    
    async def marcar_todas_como_lidas(self, alerta_id: Optional[str] = None) -> int:
        """Marca todas as notificações pendentes como lidas"""
        try:
            filtro = {'status': 'pendente'}
            if alerta_id:
                filtro['alerta_id'] = alerta_id
            
            result = await self.notificacoes_collection.update_many(
                filtro,
                {
                    '$set': {
                        'status': 'lida',
                        'lido_em': datetime.now(timezone.utc)
                    }
                }
            )
            return result.modified_count
            
        except Exception as e:
            logger.error(f"❌ Erro ao marcar notificações como lidas: {str(e)}")
            return 0
    
    async def arquivar_notificacao(self, notificacao_id: str) -> bool:
        """Arquiva uma notificação"""
        try:
            result = await self.notificacoes_collection.update_one(
                {'id': notificacao_id},
                {'$set': {'status': 'arquivada'}}
            )
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"❌ Erro ao arquivar notificação: {str(e)}")
            return False
    
    async def obter_estatisticas(self) -> NotificacaoStats:
        """Obtém estatísticas de notificações"""
        try:
            # Contar notificações por status
            pipeline = [
                {'$group': {'_id': '$status', 'count': {'$sum': 1}}}
            ]
            
            cursor = self.notificacoes_collection.aggregate(pipeline)
            stats_raw = await cursor.to_list(length=10)
            
            stats_dict = {s['_id']: s['count'] for s in stats_raw}
            
            # Contar alertas ativos
            total_alertas = await self.alertas_collection.count_documents({'ativo': True})
            
            # Calcular próxima verificação
            proxima = None
            if self._ultima_verificacao_global:
                proxima = self._ultima_verificacao_global + timedelta(hours=self.FREQUENCIA_PADRAO_HORAS)
            
            return NotificacaoStats(
                total_pendentes=stats_dict.get('pendente', 0),
                total_lidas=stats_dict.get('lida', 0),
                total_arquivadas=stats_dict.get('arquivada', 0),
                total_alertas_ativos=total_alertas,
                ultima_verificacao=self._ultima_verificacao_global,
                proxima_verificacao=proxima
            )
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter estatísticas: {str(e)}")
            return NotificacaoStats()
    
    # ==================== VERIFICAÇÃO AUTOMÁTICA ====================
    
    async def verificar_novas_licitacoes(self, forcar: bool = False) -> Dict[str, Any]:
        """
        Verifica novas licitações e gera notificações
        
        Args:
            forcar: Se True, ignora o intervalo de frequência
            
        Returns:
            Dict com resultados da verificação
        """
        if self._verificacao_em_andamento:
            return {'status': 'em_andamento', 'mensagem': 'Verificação já em andamento'}
        
        try:
            self._verificacao_em_andamento = True
            agora = datetime.now(timezone.utc)
            
            logger.info("🔔 Iniciando verificação de novas licitações para alertas...")
            
            # Buscar alertas ativos
            alertas = await self.listar_alertas(apenas_ativos=True)
            
            if not alertas:
                return {'status': 'ok', 'mensagem': 'Nenhum alerta ativo', 'notificacoes_criadas': 0}
            
            total_notificacoes = 0
            alertas_verificados = 0
            
            for alerta in alertas:
                # Verificar se deve processar este alerta
                if not forcar and alerta.ultima_verificacao:
                    tempo_desde_verificacao = agora - alerta.ultima_verificacao.replace(tzinfo=timezone.utc)
                    if tempo_desde_verificacao < timedelta(hours=alerta.frequencia_horas):
                        continue
                
                # Processar alerta
                novas = await self._processar_alerta(alerta)
                total_notificacoes += novas
                alertas_verificados += 1
                
                # Atualizar última verificação
                await self.alertas_collection.update_one(
                    {'id': alerta.id},
                    {'$set': {'ultima_verificacao': agora}}
                )
            
            self._ultima_verificacao_global = agora
            
            logger.info(f"✅ Verificação concluída: {alertas_verificados} alertas, {total_notificacoes} novas notificações")
            
            return {
                'status': 'ok',
                'alertas_verificados': alertas_verificados,
                'notificacoes_criadas': total_notificacoes,
                'timestamp': agora.isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Erro na verificação: {str(e)}")
            return {'status': 'erro', 'mensagem': str(e)}
            
        finally:
            self._verificacao_em_andamento = False
    
    async def _processar_alerta(self, alerta: AlertaConfig) -> int:
        """
        Processa um alerta específico e cria notificações
        
        Args:
            alerta: Configuração do alerta
            
        Returns:
            Número de notificações criadas
        """
        try:
            # Construir query para buscar licitações
            query = await self._construir_query_alerta(alerta)
            
            if not query:
                return 0
            
            # Buscar licitações que correspondem ao alerta
            # Apenas licitações não notificadas anteriormente
            licitacoes_notificadas = await self.notificacoes_collection.distinct(
                'licitacao_id',
                {'alerta_id': alerta.id}
            )
            
            query['id'] = {'$nin': licitacoes_notificadas}
            
            # Buscar licitações recentes (últimas 48h)
            limite_tempo = datetime.now(timezone.utc) - timedelta(hours=48)
            query['$or'] = [
                {'data_referencia': {'$gte': limite_tempo}},
                {'criado_em': {'$gte': limite_tempo}}
            ]
            
            cursor = self.licitacoes_collection.find(query, {'_id': 0}).limit(50)
            licitacoes = await cursor.to_list(length=50)
            
            # Criar notificações
            notificacoes_criadas = 0
            
            for lic in licitacoes:
                motivo = self._identificar_motivo_match(alerta, lic)
                
                notificacao = {
                    'id': str(uuid4()),
                    'alerta_id': alerta.id,
                    'licitacao_id': lic.get('id', ''),
                    'titulo': lic.get('titulo_licitacao', lic.get('objeto', 'Sem título'))[:200],
                    'orgao': lic.get('orgao_licitante', 'N/A')[:100],
                    'estado': lic.get('estado', lic.get('estado_uf', 'N/A')),
                    'modalidade': lic.get('modalidade', 'N/A'),
                    'data_limite': lic.get('data_final', lic.get('data_limite')),
                    'link_origem': lic.get('link_origem', ''),
                    'motivo_match': motivo,
                    'status': 'pendente',
                    'criado_em': datetime.now(timezone.utc),
                    'lido_em': None
                }
                
                await self.notificacoes_collection.insert_one(notificacao)
                notificacoes_criadas += 1
            
            # Atualizar contador no alerta
            if notificacoes_criadas > 0:
                await self.alertas_collection.update_one(
                    {'id': alerta.id},
                    {'$inc': {'total_notificacoes': notificacoes_criadas}}
                )
            
            return notificacoes_criadas
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar alerta {alerta.id}: {str(e)}")
            return 0
    
    async def _construir_query_alerta(self, alerta: AlertaConfig) -> Dict:
        """Constrói query MongoDB baseada nos critérios do alerta"""
        query = {}
        conditions = []
        
        # Filtro por palavras-chave (busca no título e objeto)
        if alerta.palavras_chave:
            keyword_conditions = []
            for palavra in alerta.palavras_chave:
                regex = {'$regex': palavra, '$options': 'i'}
                keyword_conditions.append({'titulo_licitacao': regex})
                keyword_conditions.append({'objeto': regex})
                keyword_conditions.append({'medicamento': regex})
            
            if keyword_conditions:
                conditions.append({'$or': keyword_conditions})
        
        # Filtro por lista customizada
        if alerta.lista_customizada_id:
            # Buscar palavras da lista
            lista = await self.db.listas_medicamentos.find_one(
                {'id': alerta.lista_customizada_id},
                {'_id': 0, 'medicamentos': 1}
            )
            
            if lista and lista.get('medicamentos'):
                lista_conditions = []
                for med in lista['medicamentos']:
                    regex = {'$regex': med, '$options': 'i'}
                    lista_conditions.append({'titulo_licitacao': regex})
                    lista_conditions.append({'objeto': regex})
                    lista_conditions.append({'medicamento': regex})
                
                if lista_conditions:
                    conditions.append({'$or': lista_conditions})
        
        # Filtro por estados
        if alerta.estados:
            conditions.append({
                '$or': [
                    {'estado': {'$in': alerta.estados}},
                    {'estado_uf': {'$in': alerta.estados}}
                ]
            })
        
        # Filtro por modalidades
        if alerta.modalidades:
            regex_modalidades = '|'.join(alerta.modalidades)
            conditions.append({'modalidade': {'$regex': regex_modalidades, '$options': 'i'}})
        
        # Combinar condições
        if conditions:
            query['$and'] = conditions
        
        return query
    
    def _identificar_motivo_match(self, alerta: AlertaConfig, licitacao: Dict) -> str:
        """Identifica qual critério do alerta gerou o match"""
        titulo = (licitacao.get('titulo_licitacao', '') + ' ' + licitacao.get('objeto', '')).lower()
        
        # Verificar palavras-chave
        for palavra in alerta.palavras_chave:
            if palavra.lower() in titulo:
                return f"Palavra-chave: {palavra}"
        
        # Verificar estado
        estado_lic = licitacao.get('estado', licitacao.get('estado_uf', ''))
        if estado_lic in alerta.estados:
            return f"Estado: {estado_lic}"
        
        # Verificar modalidade
        modalidade_lic = licitacao.get('modalidade', '').lower()
        for mod in alerta.modalidades:
            if mod.lower() in modalidade_lic:
                return f"Modalidade: {mod}"
        
        return "Critério geral"
