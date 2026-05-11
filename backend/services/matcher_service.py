"""
Matcher Service v2 - GSM Buscador de Editais
=============================================

Matcher sobre o modelo canônico (editais_normalizados).

Responsabilidades:
- Cruzar alertas do usuário com editais normalizados
- Gerar matches com scoring de relevância
- Suportar múltiplas estratégias de matching
- Preparar para evolução (NCM, embeddings)

Pipeline:
    editais_normalizados → matcher_v2 → matches → notificações → email

Regras de Matching:
1. Texto (objeto, objeto_resumido) - Full-text search
2. Tags (saúde, TI, etc) - Exact match
3. UF / Município - Geográfico
4. Modalidade - Exact match
5. (Futuro) NCM - Código fiscal
6. (Futuro) Embeddings - Semântico
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase
import re

logger = logging.getLogger(__name__)


class MatchResult:
    """Resultado de um match com scoring"""
    
    def __init__(
        self,
        edital_id: str,
        alerta_id: str,
        score: float,
        motivos: List[str],
        edital_data: Dict
    ):
        self.edital_id = edital_id
        self.alerta_id = alerta_id
        self.score = score
        self.motivos = motivos
        self.edital_data = edital_data
        self.timestamp = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict:
        return {
            "edital_id": self.edital_id,
            "alerta_id": self.alerta_id,
            "score": self.score,
            "motivos": self.motivos,
            "timestamp": self.timestamp.isoformat()
        }


class MatcherServiceV2:
    """
    Matcher v2 - Opera exclusivamente sobre editais_normalizados
    
    Features:
    - Scoring de relevância (0-100)
    - Múltiplas estratégias de match
    - Suporte a tags auto-detectadas
    - Preparado para NCM e embeddings
    """
    
    # Pesos para scoring (soma = 100)
    PESO_TEXTO = 40       # Match em objeto/objeto_resumido
    PESO_TAGS = 25        # Match em tags
    PESO_GEOGRAFICO = 20  # Match em UF/município
    PESO_MODALIDADE = 10  # Match em modalidade
    PESO_RECENCIA = 5     # Bonus por editais recentes
    
    # Threshold mínimo para considerar match
    SCORE_MINIMO = 20
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.editais_collection = db.editais_normalizados
        self.alertas_collection = db.alertas_notificacao
        self.matches_collection = db.matches  # Nova collection para histórico
        self.listas_collection = db.listas_medicamentos
    
    async def setup_indexes(self):
        """Cria índices para a collection de matches"""
        try:
            await self.matches_collection.create_index(
                [("alerta_id", 1), ("edital_id", 1)],
                unique=True,
                name="idx_match_unique"
            )
            await self.matches_collection.create_index(
                [("timestamp", -1)],
                name="idx_match_timestamp"
            )
            await self.matches_collection.create_index(
                [("score", -1)],
                name="idx_match_score"
            )
            logger.info("✅ [MATCHER] Índices configurados")
        except Exception as e:
            logger.error(f"❌ [MATCHER] Erro ao criar índices: {str(e)}")
    
    async def processar_alerta(
        self,
        alerta: Dict,
        limite_horas: int = 48,
        limite_resultados: int = 50
    ) -> List[MatchResult]:
        """
        Processa um alerta e retorna matches com editais normalizados
        
        Args:
            alerta: Configuração do alerta
            limite_horas: Considerar editais das últimas N horas
            limite_resultados: Máximo de matches por alerta
            
        Returns:
            Lista de MatchResult ordenada por score
        """
        try:
            matches: List[MatchResult] = []
            
            # Extrair critérios do alerta
            palavras_chave = alerta.get('palavras_chave', [])
            estados = alerta.get('estados', [])
            modalidades = alerta.get('modalidades', [])
            lista_id = alerta.get('lista_customizada_id')
            
            # Se tem lista customizada, adicionar palavras
            if lista_id:
                lista = await self.listas_collection.find_one(
                    {'id': lista_id},
                    {'medicamentos': 1, '_id': 0}
                )
                if lista and lista.get('medicamentos'):
                    palavras_chave = list(set(palavras_chave + lista['medicamentos']))
            
            # Se não tem critérios, não há match possível
            if not palavras_chave and not estados and not modalidades:
                logger.warning(f"⚠️ [MATCHER] Alerta {alerta.get('id')} sem critérios")
                return []
            
            # Buscar editais já notificados para este alerta
            editais_notificados = await self.db.notificacoes.distinct(
                'licitacao_id',
                {'alerta_id': alerta.get('id')}
            )
            
            # Construir query base
            query = await self._construir_query(
                palavras_chave=palavras_chave,
                estados=estados,
                modalidades=modalidades,
                limite_horas=limite_horas
            )
            
            # Excluir já notificados
            if editais_notificados:
                query['hash_dedup'] = {'$nin': editais_notificados}
            
            # Buscar editais candidatos
            cursor = self.editais_collection.find(
                query,
                {'_id': 0}
            ).limit(limite_resultados * 2)  # Busca mais para filtrar por score
            
            editais = await cursor.to_list(length=limite_resultados * 2)
            
            # Calcular score para cada edital
            for edital in editais:
                score, motivos = self._calcular_score(
                    edital=edital,
                    palavras_chave=palavras_chave,
                    estados=estados,
                    modalidades=modalidades
                )
                
                if score >= self.SCORE_MINIMO:
                    match = MatchResult(
                        edital_id=edital.get('hash_dedup', edital.get('id_externo')),
                        alerta_id=alerta.get('id'),
                        score=score,
                        motivos=motivos,
                        edital_data=edital
                    )
                    matches.append(match)
            
            # Ordenar por score e limitar
            matches.sort(key=lambda m: m.score, reverse=True)
            matches = matches[:limite_resultados]
            
            logger.info(f"🎯 [MATCHER] Alerta {alerta.get('id')}: {len(matches)} matches (score >= {self.SCORE_MINIMO})")
            
            return matches
            
        except Exception as e:
            logger.error(f"❌ [MATCHER] Erro ao processar alerta: {str(e)}")
            return []
    
    async def _construir_query(
        self,
        palavras_chave: List[str],
        estados: List[str],
        modalidades: List[str],
        limite_horas: int
    ) -> Dict:
        """
        Constrói query MongoDB otimizada para editais_normalizados
        
        IMPORTANTE: $text não pode ser combinado com $or em sub-queries
        Por isso usamos apenas regex para máxima flexibilidade
        """
        query = {}
        conditions = []
        
        # Filtro temporal (editais recentes)
        limite_tempo = datetime.now(timezone.utc) - timedelta(hours=limite_horas)
        conditions.append({
            '$or': [
                {'data_abertura': {'$gte': limite_tempo}},
                {'data_publicacao': {'$gte': limite_tempo}},
                {'created_at': {'$gte': limite_tempo}}
            ]
        })
        
        # Filtro por palavras-chave (usando regex para flexibilidade)
        if palavras_chave:
            keyword_conditions = []
            
            for palavra in palavras_chave:
                # Case-insensitive regex
                regex = {'$regex': re.escape(palavra), '$options': 'i'}
                keyword_conditions.append({'objeto': regex})
                keyword_conditions.append({'objeto_resumido': regex})
                keyword_conditions.append({'orgao': regex})
                # Também buscar nas tags
                keyword_conditions.append({'tags': regex})
            
            # OR entre todas as condições de keyword
            conditions.append({'$or': keyword_conditions})
        
        # Filtro por estados (UF)
        if estados:
            estados_upper = [e.upper() for e in estados]
            conditions.append({'uf': {'$in': estados_upper}})
        
        # Filtro por modalidades
        if modalidades:
            modalidade_conditions = []
            for mod in modalidades:
                modalidade_conditions.append({
                    'modalidade': {'$regex': re.escape(mod), '$options': 'i'}
                })
            conditions.append({'$or': modalidade_conditions})
        
        # Combinar condições
        if conditions:
            query['$and'] = conditions
        
        return query
    
    def _calcular_score(
        self,
        edital: Dict,
        palavras_chave: List[str],
        estados: List[str],
        modalidades: List[str]
    ) -> tuple[float, List[str]]:
        """
        Calcula score de relevância (0-100) para um edital
        
        Returns:
            (score, motivos) - Score numérico e lista de motivos do match
        """
        score = 0.0
        motivos = []
        
        objeto = (edital.get('objeto', '') or '').lower()
        objeto_resumido = (edital.get('objeto_resumido', '') or '').lower()
        orgao = (edital.get('orgao', '') or '').lower()
        tags = edital.get('tags', [])
        uf = (edital.get('uf', '') or '').upper()
        municipio = (edital.get('municipio', '') or '').lower()
        modalidade = (edital.get('modalidade', '') or '').lower()
        
        texto_completo = f"{objeto} {objeto_resumido} {orgao}"
        
        # 1. Scoring de texto (PESO_TEXTO = 40)
        palavras_encontradas = []
        for palavra in palavras_chave:
            if palavra.lower() in texto_completo:
                palavras_encontradas.append(palavra)
        
        if palavras_encontradas:
            # Score proporcional ao número de palavras encontradas
            proporcao = len(palavras_encontradas) / len(palavras_chave)
            score += self.PESO_TEXTO * proporcao
            motivos.append(f"Palavras-chave: {', '.join(palavras_encontradas[:3])}")
        
        # 2. Scoring de tags (PESO_TAGS = 25)
        if tags and palavras_chave:
            # Verificar se alguma tag está relacionada às keywords
            tags_relacionadas = []
            for tag in tags:
                for palavra in palavras_chave:
                    if palavra.lower() in tag.lower() or tag.lower() in palavra.lower():
                        tags_relacionadas.append(tag)
                        break
            
            if tags_relacionadas:
                score += self.PESO_TAGS
                motivos.append(f"Tags: {', '.join(tags_relacionadas[:2])}")
            elif edital.get('is_saude') and any('saude' in p.lower() or 'medic' in p.lower() for p in palavras_chave):
                score += self.PESO_TAGS * 0.5
                motivos.append("Área: Saúde")
        
        # 3. Scoring geográfico (PESO_GEOGRAFICO = 20)
        if estados:
            if uf in [e.upper() for e in estados]:
                score += self.PESO_GEOGRAFICO
                motivos.append(f"Estado: {uf}")
        
        # 4. Scoring de modalidade (PESO_MODALIDADE = 10)
        if modalidades:
            for mod in modalidades:
                if mod.lower() in modalidade:
                    score += self.PESO_MODALIDADE
                    motivos.append(f"Modalidade: {edital.get('modalidade', 'N/A')}")
                    break
        
        # 5. Bonus por recência (PESO_RECENCIA = 5)
        data_abertura = edital.get('data_abertura')
        if data_abertura:
            if isinstance(data_abertura, str):
                try:
                    data_abertura = datetime.fromisoformat(data_abertura.replace('Z', '+00:00'))
                except:
                    data_abertura = None
            
            if data_abertura:
                dias_ate_abertura = (data_abertura.replace(tzinfo=None) - datetime.utcnow()).days
                if 0 <= dias_ate_abertura <= 7:
                    score += self.PESO_RECENCIA
                    motivos.append("Edital recente (7 dias)")
                elif 7 < dias_ate_abertura <= 30:
                    score += self.PESO_RECENCIA * 0.5
        
        return round(score, 2), motivos
    
    async def salvar_match(self, match: MatchResult) -> bool:
        """Salva um match na collection de histórico"""
        try:
            match_doc = {
                'edital_id': match.edital_id,
                'alerta_id': match.alerta_id,
                'score': match.score,
                'motivos': match.motivos,
                'timestamp': match.timestamp,
                'processado': False
            }
            
            await self.matches_collection.update_one(
                {'edital_id': match.edital_id, 'alerta_id': match.alerta_id},
                {'$set': match_doc},
                upsert=True
            )
            return True
            
        except Exception as e:
            logger.error(f"❌ [MATCHER] Erro ao salvar match: {str(e)}")
            return False
    
    async def processar_todos_alertas(self) -> Dict[str, Any]:
        """
        Processa todos os alertas ativos e gera matches
        
        Returns:
            Estatísticas do processamento
        """
        try:
            inicio = datetime.now(timezone.utc)
            
            # Buscar alertas ativos
            cursor = self.alertas_collection.find(
                {'ativo': True},
                {'_id': 0}
            )
            alertas = await cursor.to_list(length=100)
            
            stats = {
                'alertas_processados': 0,
                'total_matches': 0,
                'matches_por_alerta': {},
                'score_medio': 0,
                'duracao_segundos': 0
            }
            
            todos_scores = []
            
            for alerta in alertas:
                matches = await self.processar_alerta(alerta)
                stats['alertas_processados'] += 1
                stats['total_matches'] += len(matches)
                stats['matches_por_alerta'][alerta.get('id')] = len(matches)
                
                # Salvar matches
                for match in matches:
                    await self.salvar_match(match)
                    todos_scores.append(match.score)
            
            # Calcular score médio
            if todos_scores:
                stats['score_medio'] = round(sum(todos_scores) / len(todos_scores), 2)
            
            stats['duracao_segundos'] = (datetime.now(timezone.utc) - inicio).total_seconds()
            
            logger.info(f"🎯 [MATCHER] Processamento concluído: {stats}")
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ [MATCHER] Erro no processamento: {str(e)}")
            return {'erro': str(e)}
    
    async def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do matcher"""
        try:
            total_matches = await self.matches_collection.count_documents({})
            matches_nao_processados = await self.matches_collection.count_documents({'processado': False})
            
            # Score médio dos últimos matches
            pipeline = [
                {'$sort': {'timestamp': -1}},
                {'$limit': 100},
                {'$group': {'_id': None, 'avg_score': {'$avg': '$score'}}}
            ]
            result = await self.matches_collection.aggregate(pipeline).to_list(1)
            score_medio = result[0]['avg_score'] if result else 0
            
            return {
                'total_matches': total_matches,
                'matches_pendentes': matches_nao_processados,
                'score_medio_recente': round(score_medio, 2),
                'threshold_minimo': self.SCORE_MINIMO
            }
            
        except Exception as e:
            logger.error(f"❌ [MATCHER] Erro ao obter stats: {str(e)}")
            return {}


# Singleton
_matcher_instance = None

def get_matcher(db: AsyncIOMotorDatabase) -> MatcherServiceV2:
    """Retorna instância do matcher (singleton)"""
    global _matcher_instance
    if _matcher_instance is None:
        _matcher_instance = MatcherServiceV2(db)
    return _matcher_instance
