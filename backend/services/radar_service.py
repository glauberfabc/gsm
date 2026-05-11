"""
Radar Service - GSM Buscador de Editais v41.0

Serviço para processamento automático de Radares (Alertas por Email).
Cada radar pode ter frequência de 8h, 12h ou 24h.

Funcionalidades:
- Busca editais baseados nos termos do radar
- Envia emails via Resend com assunto dinâmico
- Controle de editais já enviados (evita duplicatas)
- Log de execução para monitoramento
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
import hashlib

logger = logging.getLogger(__name__)


class RadarService:
    """
    Serviço para processamento automático de Radares.
    
    Um Radar é um alerta configurado pelo usuário com:
    - Nome (identificador)
    - Termos de busca (palavras-chave)
    - Email de destino
    - Frequência (8h, 12h, 24h)
    """
    
    def __init__(self, db):
        self.db = db
        self.collection = db.radares
        self.editais_enviados = db.radares_editais_enviados
    
    async def processar_todos_radares(self, frequencia: str = None) -> Dict:
        """
        Processa todos os radares ativos.
        
        Args:
            frequencia: Filtrar por frequência específica ('8h', '12h', '24h')
            
        Returns:
            Estatísticas de processamento
        """
        stats = {
            'total_radares': 0,
            'processados': 0,
            'emails_enviados': 0,
            'sem_novidades': 0,
            'erros': 0,
            'detalhes': []
        }
        
        try:
            # Buscar radares
            query = {}
            if frequencia:
                query['frequencia'] = frequencia
            
            radares = await self.collection.find(query, {'_id': 0}).to_list(100)
            stats['total_radares'] = len(radares)
            
            if not radares:
                logger.info(f"📡 [RADAR] Nenhum radar encontrado para frequência: {frequencia or 'todas'}")
                return stats
            
            logger.info(f"📡 [RADAR] Processando {len(radares)} radares (frequência: {frequencia or 'todas'})...")
            
            for radar in radares:
                try:
                    resultado = await self.processar_radar(radar)
                    stats['processados'] += 1
                    
                    if resultado.get('status') == 'enviado':
                        stats['emails_enviados'] += 1
                    elif resultado.get('status') == 'sem_novidades':
                        stats['sem_novidades'] += 1
                    
                    stats['detalhes'].append({
                        'radar_id': radar.get('id'),
                        'nome': radar.get('nome'),
                        'resultado': resultado.get('status'),
                        'editais': resultado.get('editais_encontrados', 0)
                    })
                    
                except Exception as e:
                    logger.error(f"❌ [RADAR] Erro ao processar radar {radar.get('nome')}: {str(e)}")
                    stats['erros'] += 1
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ [RADAR] Erro geral: {str(e)}")
            stats['erros'] += 1
            return stats
    
    async def processar_radar(self, radar: Dict) -> Dict:
        """
        Processa um radar específico.
        
        Pipeline:
        1. Busca editais baseados nos termos
        2. Filtra editais já enviados
        3. Se houver novos, envia email
        4. Registra editais enviados
        
        Args:
            radar: Documento do radar
            
        Returns:
            Resultado do processamento
        """
        radar_id = radar.get('id')
        nome = radar.get('nome', 'Radar')
        termos = radar.get('termos', '')
        email = radar.get('email', '')
        
        if not termos or not email:
            return {'status': 'erro', 'message': 'Termos ou email não configurados'}
        
        logger.info(f"📡 [RADAR] Processando: {nome} (termos: {termos[:50]}...)")
        
        try:
            # 1. Buscar editais
            editais = await self._buscar_editais(termos)
            
            if not editais:
                logger.info(f"📡 [RADAR] {nome}: Nenhum edital encontrado")
                return {'status': 'sem_novidades', 'editais_encontrados': 0}
            
            # 2. Filtrar já enviados
            editais_novos = await self._filtrar_ja_enviados(radar_id, editais)
            
            if not editais_novos:
                logger.info(f"📡 [RADAR] {nome}: Todos editais já foram enviados anteriormente")
                return {'status': 'sem_novidades', 'editais_encontrados': len(editais), 'novos': 0}
            
            logger.info(f"📡 [RADAR] {nome}: {len(editais_novos)} novos editais de {len(editais)} encontrados")
            
            # 3. Enviar email
            from services.email_service import get_email_service
            email_service = get_email_service()
            
            # Preparar editais no formato esperado pelo email service
            editais_formatados = self._formatar_editais_para_email(editais_novos, termos)
            
            # Assunto dinâmico v52.0: 🔔 [NOME DO RADAR]: Match para [TERMO]
            termo_principal = termos.split(',')[0].strip() if ',' in termos else termos
            
            resultado_email = await email_service.enviar_alerta_radar(
                email=email,
                nome_radar=nome,
                editais=editais_formatados,
                termo_principal=termo_principal
            )
            
            if resultado_email.get('status') == 'success':
                # 4. Registrar editais enviados
                await self._registrar_enviados(radar_id, editais_novos)
                
                # Atualizar última execução do radar
                await self.collection.update_one(
                    {'id': radar_id},
                    {'$set': {
                        'ultima_execucao': datetime.now(timezone.utc).isoformat(),
                        'ultimo_envio': datetime.now(timezone.utc).isoformat(),
                        'editais_ultimo_envio': len(editais_novos)
                    }}
                )
                
                return {
                    'status': 'enviado',
                    'editais_encontrados': len(editais),
                    'editais_novos': len(editais_novos),
                    'email_id': resultado_email.get('email_id')
                }
            else:
                return {
                    'status': 'erro_email',
                    'message': resultado_email.get('message'),
                    'editais_encontrados': len(editais)
                }
            
        except Exception as e:
            logger.error(f"❌ [RADAR] Erro ao processar {nome}: {str(e)}")
            return {'status': 'erro', 'message': str(e)}
    
    async def _buscar_editais(self, termos: str, limit: int = 50) -> List[Dict]:
        """
        Busca editais baseados nos termos do radar.
        
        Usa busca por texto com expansão de termos.
        """
        try:
            # Separar termos por vírgula
            lista_termos = [t.strip().lower() for t in termos.split(',') if t.strip()]
            
            if not lista_termos:
                return []
            
            # Construir query de busca
            # Busca por texto em objeto, medicamento, descricao
            or_conditions = []
            for termo in lista_termos:
                or_conditions.extend([
                    {'objeto': {'$regex': termo, '$options': 'i'}},
                    {'medicamento': {'$regex': termo, '$options': 'i'}},
                    {'descricao': {'$regex': termo, '$options': 'i'}},
                ])
            
            # Buscar apenas editais ATIVOS (dos últimos 90 dias)
            data_limite = datetime.now(timezone.utc) - timedelta(days=90)
            
            query = {
                '$or': or_conditions,
                'status_oportunidade': {'$in': ['ATIVA', 'FUTURA', None]},
                '$or': [
                    {'data_publicacao': {'$gte': data_limite.isoformat()}},
                    {'created_at': {'$gte': data_limite}}
                ]
            }
            
            # Projeção para evitar _id
            projection = {'_id': 0}
            
            editais = await self.db.editais_normalizados.find(
                query, 
                projection
            ).sort('data_publicacao', -1).limit(limit).to_list(limit)
            
            return editais
            
        except Exception as e:
            logger.error(f"❌ [RADAR] Erro na busca: {str(e)}")
            return []
    
    async def _filtrar_ja_enviados(self, radar_id: str, editais: List[Dict]) -> List[Dict]:
        """
        Filtra editais que já foram enviados para este radar.
        """
        editais_novos = []
        
        for edital in editais:
            # Gerar hash único do edital
            hash_edital = self._gerar_hash_edital(edital)
            
            # Verificar se já foi enviado
            existe = await self.editais_enviados.find_one({
                'radar_id': radar_id,
                'hash_edital': hash_edital
            })
            
            if not existe:
                editais_novos.append(edital)
        
        return editais_novos
    
    def _gerar_hash_edital(self, edital: Dict) -> str:
        """
        Gera hash único para identificar um edital.
        """
        # Usar campos estáveis para hash
        conteudo = f"{edital.get('id_externo', '')}-{edital.get('numero_processo', '')}-{edital.get('orgao', '')}"
        return hashlib.md5(conteudo.encode()).hexdigest()
    
    async def _registrar_enviados(self, radar_id: str, editais: List[Dict]):
        """
        Registra editais enviados para evitar duplicatas futuras.
        """
        for edital in editais:
            hash_edital = self._gerar_hash_edital(edital)
            
            await self.editais_enviados.update_one(
                {'radar_id': radar_id, 'hash_edital': hash_edital},
                {'$set': {
                    'radar_id': radar_id,
                    'hash_edital': hash_edital,
                    'edital_id': edital.get('id_externo') or edital.get('hash_dedup'),
                    'enviado_em': datetime.now(timezone.utc).isoformat()
                }},
                upsert=True
            )
    
    def _formatar_editais_para_email(self, editais: List[Dict], termos: str) -> List[Dict]:
        """
        Formata editais para o template de email.
        """
        formatados = []
        
        for edital in editais:
            formatados.append({
                'orgao': edital.get('orgao', 'Órgão não informado'),
                'objeto': edital.get('objeto', edital.get('descricao', 'N/A')),
                'numero_processo': edital.get('numero_processo', 'N/A'),
                'modalidade': edital.get('modalidade', 'Pregão'),
                'status_oportunidade': edital.get('status_oportunidade', 'ATIVA'),
                'uf': edital.get('uf', ''),
                'municipio': edital.get('municipio', ''),
                'data_abertura': edital.get('data_abertura'),
                'data_publicacao': edital.get('data_publicacao'),
                'valor_total': edital.get('valor_total'),
                'link_edital': edital.get('link_edital') or edital.get('link_pncp', '#'),
                'itens_correspondentes': edital.get('itens_correspondentes', [])
            })
        
        return formatados


# Singleton
_radar_service = None

def get_radar_service(db) -> RadarService:
    global _radar_service
    if _radar_service is None:
        _radar_service = RadarService(db)
    return _radar_service
