"""
Sincronizador Mestre - GSM Buscador de Editais

Responsabilidades:
- Baixar editais do PNCP-OFICIAL periodicamente (a cada 15 min)
- Salvar no MongoDB local com índices de texto
- Permitir buscas instantâneas (<1s) no banco local

Arquitetura Local-First:
- Sincronizador baixa dados → MongoDB
- Busca de alertas consulta MongoDB (não mais API externa)
- Resultado: 45s → <1s de tempo de resposta
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class SyncService:
    """
    Serviço de Sincronização de Editais
    
    Responsável por manter o banco de dados local atualizado
    com os editais do PNCP e outras fontes.
    """
    
    def __init__(self, db, pncp_client=None):
        """
        Inicializa o serviço de sincronização
        
        Args:
            db: Conexão com MongoDB
            pncp_client: Cliente PNCP API Oficial
        """
        self.db = db
        self.pncp_client = pncp_client
        # Collection raw (para sincronização)
        self.editais_sync = db.editais_sync if db is not None else None
        # Collection normalizada (para busca - com links resolvidos)
        self.editais_collection = db.editais_normalizados if db is not None else None
        
        # Configurações
        self.BATCH_SIZE = 500  # Máximo de editais por sincronização
        self.SYNC_INTERVAL_MINUTES = 15
        
    async def setup_indexes(self):
        """
        Configura índices do MongoDB para busca ultra-rápida
        
        Índices criados:
        - Texto completo no campo 'objeto' (Full Text Search)
        - Único no 'id_externo' (evita duplicatas)
        - Composto para filtros comuns
        """
        try:
            logger.info("🔧 [SYNC] Configurando índices do MongoDB...")
            
            # 1. Índice de texto para busca por palavras-chave
            await self.editais_collection.create_index(
                [("objeto", "text"), ("orgao", "text")],
                name="idx_busca_texto",
                default_language="portuguese"
            )
            
            # 2. Índice único para evitar duplicados
            await self.editais_collection.create_index(
                [("id_externo", 1)],
                unique=True,
                name="idx_id_externo"
            )
            
            # 3. Índice para filtros por data
            await self.editais_collection.create_index(
                [("data_abertura", -1)],
                name="idx_data_abertura"
            )
            
            # 4. Índice para filtros por estado
            await self.editais_collection.create_index(
                [("estado", 1)],
                name="idx_estado"
            )
            
            # 5. Índice composto para queries frequentes
            await self.editais_collection.create_index(
                [("fonte", 1), ("sincronizado_em", -1)],
                name="idx_fonte_sync"
            )
            
            logger.info("✅ [SYNC] Índices do MongoDB configurados com sucesso!")
            return True
            
        except Exception as e:
            logger.error(f"❌ [SYNC] Erro ao configurar índices: {str(e)}")
            return False
    
    async def sync_pncp(self) -> Dict[str, Any]:
        """
        Sincroniza editais do PNCP-OFICIAL com o banco local
        
        Returns:
            Dict com estatísticas da sincronização
        """
        logger.info("🚀 [SYNC] Iniciando sincronização PNCP-OFICIAL...")
        inicio = datetime.now(timezone.utc)
        
        stats = {
            'fonte': 'PNCP-OFICIAL',
            'inicio': inicio.isoformat(),
            'novos': 0,
            'atualizados': 0,
            'erros': 0,
            'total_processados': 0
        }
        
        try:
            if not self.pncp_client:
                logger.warning("⚠️ [SYNC] Cliente PNCP não configurado")
                return stats
            
            # Buscar editais com propostas abertas (sem filtro de termo)
            editais_raw = await self.pncp_client.buscar_licitacoes(
                termo_busca=None,
                apenas_futuras=True,
                apenas_saude=False,  # Pegar TODOS os editais
                limit=self.BATCH_SIZE
            )
            
            if not editais_raw:
                logger.info("ℹ️ [SYNC] Nenhum edital novo retornado pela API")
                return stats
            
            logger.info(f"📥 [SYNC] Recebidos {len(editais_raw)} editais da API")
            
            # Preparar operações de bulk write
            from pymongo import UpdateOne
            operacoes = []
            
            for edital in editais_raw:
                try:
                    # Criar ID único baseado nos dados do edital
                    id_externo = self._gerar_id_externo(edital)
                    
                    # Preparar documento para o banco
                    doc = self._preparar_documento(edital, id_externo)
                    
                    # Operação upsert (atualiza se existe, insere se não)
                    operacoes.append(
                        UpdateOne(
                            {"id_externo": id_externo},
                            {"$set": doc, "$setOnInsert": {"criado_em": datetime.now(timezone.utc)}},
                            upsert=True
                        )
                    )
                    
                except Exception as e:
                    logger.warning(f"⚠️ [SYNC] Erro ao processar edital: {str(e)}")
                    stats['erros'] += 1
            
            # Executar bulk write (salva em editais_sync - dados raw)
            if operacoes:
                result = await self.editais_sync.bulk_write(operacoes, ordered=False)
                stats['novos'] = result.upserted_count
                stats['atualizados'] = result.modified_count
                stats['total_processados'] = len(operacoes)
                
                logger.info(f"✨ [SYNC] Sincronização concluída:")
                logger.info(f"   📊 Novos: {stats['novos']}")
                logger.info(f"   📊 Atualizados: {stats['atualizados']}")
                logger.info(f"   📊 Erros: {stats['erros']}")
            
            # Registrar última sincronização
            await self._registrar_sync(stats)
            
        except Exception as e:
            logger.error(f"❌ [SYNC] Erro na sincronização: {str(e)}")
            stats['erro_geral'] = str(e)
        
        stats['fim'] = datetime.now(timezone.utc).isoformat()
        stats['duracao_segundos'] = (datetime.now(timezone.utc) - inicio).total_seconds()
        
        return stats
    
    def _gerar_id_externo(self, edital: Dict) -> str:
        """Gera ID único para o edital baseado nos dados disponíveis"""
        # Tentar diferentes combinações de campos para criar ID único
        partes = []
        
        if edital.get('numero_processo'):
            partes.append(edital['numero_processo'])
        if edital.get('cnpj'):
            partes.append(edital['cnpj'])
        if edital.get('ano'):
            partes.append(str(edital['ano']))
        if edital.get('sequencial'):
            partes.append(str(edital['sequencial']))
        
        if partes:
            return "-".join(partes)
        
        # Fallback: usar ID interno ou gerar UUID
        return edital.get('id', str(uuid4()))
    
    def _preparar_documento(self, edital: Dict, id_externo: str) -> Dict:
        """
        Prepara documento para inserção no MongoDB (Schema GSM v52.0)
        
        SCHEMA OBRIGATÓRIO:
        - id_gsm: hash único do processo
        - fonte_origem: PNCP_OFICIAL | SCRAPER_MG | SCRAPER_SP
        - dados_orgao: {uasg, cnpj, nome, uf, municipio}
        - objeto: string em caixa alta
        - itens_clonados: array de itens do edital
        - link_documento: URL direta do PDF
        """
        # Extrair UASG do CNPJ ou dados do órgão
        cnpj = edital.get('cnpj_orgao', '') or edital.get('cnpj', '')
        uasg = edital.get('uasg', '') or cnpj.replace('.', '').replace('/', '').replace('-', '')[:14] if cnpj else ''
        
        return {
            # Identificadores GSM
            "id_gsm": id_externo,  # v52.0: Campo renomeado
            "id_externo": id_externo,  # Mantido para compatibilidade
            "id_interno": edital.get('id', ''),
            
            # Fonte de origem (Sistema GSM)
            "fonte_origem": edital.get('fonte', 'PNCP_OFICIAL'),
            "fonte": edital.get('fonte', 'PNCP_OFICIAL'),
            
            # Dados do órgão (Obrigatório para interface v10)
            "dados_orgao": {
                "uasg": uasg,
                "cnpj": cnpj,
                "nome": edital.get('orgao_licitante', '') or edital.get('orgao', ''),
                "uf": edital.get('estado', ''),
                "municipio": edital.get('municipio', '')
            },
            
            # Campos legados (mantidos para compatibilidade)
            "objeto": (edital.get('objeto') or edital.get('medicamento', '')).strip().upper(),
            "orgao": edital.get('orgao_licitante', '') or edital.get('orgao', ''),
            "estado": edital.get('estado', ''),
            "uf": edital.get('estado', ''),  # Alias
            "municipio": edital.get('municipio', ''),
            "esfera": edital.get('esfera', ''),
            "modalidade": edital.get('modalidade', ''),
            "status": edital.get('status', 'ATIVA'),
            "valor_estimado": edital.get('valor_estimado'),
            "data_publicacao": edital.get('data_publicacao'),
            "data_abertura": edital.get('data_final') or edital.get('data_abertura'),
            
            # Links (Obrigatório para download)
            "link_documento": edital.get('link_edital', '') or edital.get('link_origem', ''),
            "link_origem": edital.get('link_origem', ''),
            "link_portal": edital.get('link_portal', '') or edital.get('link_origem', ''),
            
            # Identificação da licitação
            "numero_processo": edital.get('numero_processo', ''),
            "numero_licitacao": edital.get('numero_licitacao', '') or edital.get('numero_processo', ''),
            
            # Itens clonados (Schema GSM v52.0)
            "itens_clonados": edital.get('itens', []),
            
            # Metadados
            "sincronizado_em": datetime.now(timezone.utc),
            "is_saude": edital.get('is_saude', False),
            "score_relevancia": edital.get('score_relevancia', 0),
            "tags": edital.get('tags_display', [])
        }
    
    async def _registrar_sync(self, stats: Dict):
        """Registra estatísticas da sincronização"""
        try:
            await self.db.sync_logs.insert_one({
                "timestamp": datetime.now(timezone.utc),
                "fonte": stats.get('fonte'),
                "novos": stats.get('novos', 0),
                "atualizados": stats.get('atualizados', 0),
                "erros": stats.get('erros', 0)
            })
        except Exception as e:
            logger.warning(f"⚠️ [SYNC] Erro ao registrar log: {str(e)}")
    
    async def buscar_local(
        self, 
        termo_busca: str = None,
        keywords: List[str] = None,
        estados: List[str] = None,
        modalidade: str = None,
        esfera: str = None,
        apenas_saude: bool = False,
        limit: int = 50,
        skip: int = 0
    ) -> Dict:
        """
        Busca editais no banco local usando Full Text Search
        
        BUSCA HÍBRIDA: Combina termo digitado + palavras-chave das listas do usuário
        Lógica: Resultado = (Termo Pesquisado) OR (Termos da Lista)
        
        Tempo estimado: < 100ms (vs 45s na API externa)
        
        Args:
            termo_busca: Palavra-chave digitada no momento (opcional)
            keywords: Lista de palavras-chave das listas do usuário (opcional)
            estados: Lista de estados para filtrar (UF)
            modalidade: Filtro por modalidade (Pregão, Concorrência, etc)
            esfera: Filtro por esfera (Federal, Estadual, Municipal)
            apenas_saude: Se True, filtra apenas editais de saúde
            limit: Máximo de resultados
            skip: Pular N resultados (paginação)
            
        Returns:
            Dict com resultados, total e metadados
        """
        try:
            inicio = datetime.now()
            
            # Construir query
            query = {}
            
            # BUSCA HÍBRIDA: Combinar termo atual + keywords das listas
            termos_busca = []
            if termo_busca and termo_busca.strip():
                termos_busca.append(termo_busca.strip())
            if keywords:
                termos_busca.extend([k.strip() for k in keywords if k.strip()])
            
            # Full Text Search com todos os termos (operador OR implícito)
            if termos_busca:
                # MongoDB Full Text Search usa OR por padrão entre palavras
                query["$text"] = {"$search": " ".join(termos_busca)}
            
            # Filtro por estados (UF) - busca preferencialmente em 'uf', fallback para 'estado'
            if estados:
                estados_upper = [e.upper() for e in estados]
                # Usar 'uf' como campo principal (modelo canônico)
                query["uf"] = {"$in": estados_upper}
            
            # Filtro por modalidade
            if modalidade:
                # Busca case-insensitive usando regex
                query["modalidade"] = {"$regex": modalidade, "$options": "i"}
            
            # Filtro por esfera
            if esfera:
                query["esfera"] = {"$regex": esfera, "$options": "i"}
            
            # Filtro de saúde
            if apenas_saude:
                query["is_saude"] = True
            
            # Contar total antes de paginar
            total = await self.editais_collection.count_documents(query)
            
            # Executar busca com score de relevância
            # Executar busca com score de relevância se tiver termos
            if termos_busca:
                cursor = self.editais_collection.find(
                    query,
                    {"score": {"$meta": "textScore"}, "_id": 0}
                ).sort([("score", {"$meta": "textScore"})]).skip(skip).limit(limit)
            else:
                cursor = self.editais_collection.find(
                    query,
                    {"_id": 0}
                ).sort([("data_abertura", -1)]).skip(skip).limit(limit)
            
            resultados = await cursor.to_list(length=limit)
            
            tempo_ms = (datetime.now() - inicio).total_seconds() * 1000
            
            # Log detalhado dos filtros
            filtros_aplicados = []
            if termo_busca: filtros_aplicados.append(f"termo='{termo_busca}'")
            if keywords: filtros_aplicados.append(f"keywords={keywords[:3]}{'...' if len(keywords) > 3 else ''}")
            if estados: filtros_aplicados.append(f"estados={estados}")
            if modalidade: filtros_aplicados.append(f"modalidade='{modalidade}'")
            if esfera: filtros_aplicados.append(f"esfera='{esfera}'")
            if apenas_saude: filtros_aplicados.append("apenas_saude=True")
            
            busca_hibrida = bool(termo_busca and keywords)
            
            logger.info(f"🔍 [SYNC] Busca {'HÍBRIDA' if busca_hibrida else 'local'}: {', '.join(filtros_aplicados) or 'sem filtros'} → {len(resultados)}/{total} resultados em {tempo_ms:.1f}ms")
            
            return {
                "resultados": resultados,
                "total": total,
                "tempo_ms": tempo_ms,
                "busca_hibrida": busca_hibrida,
                "termos_combinados": termos_busca
            }
            
        except Exception as e:
            logger.error(f"❌ [SYNC] Erro na busca local: {str(e)}")
            return {"resultados": [], "total": 0, "tempo_ms": 0}
    
    async def buscar_para_alerta(self, alerta: Dict) -> List[Dict]:
        """
        Busca editais que correspondem a um alerta específico
        
        Args:
            alerta: Configuração do alerta (palavras_chave, estados, etc)
            
        Returns:
            Lista de editais que correspondem ao alerta
        """
        try:
            palavras = alerta.get('palavras_chave', [])
            estados = alerta.get('estados', [])
            
            # Combinar palavras-chave para busca
            termo_busca = " ".join(palavras) if palavras else None
            
            # Buscar no banco local
            resultados = await self.buscar_local(
                termo_busca=termo_busca,
                estados=estados if estados else None,
                apenas_saude=False,
                limit=100
            )
            
            # Filtrar por data (apenas editais novos desde última verificação)
            ultima_verificacao = alerta.get('ultima_verificacao')
            if ultima_verificacao:
                resultados = [
                    r for r in resultados
                    if r.get('sincronizado_em') and r['sincronizado_em'] > ultima_verificacao
                ]
            
            return resultados
            
        except Exception as e:
            logger.error(f"❌ [SYNC] Erro ao buscar para alerta: {str(e)}")
            return []
    
    async def get_stats(self) -> Dict:
        """Retorna estatísticas do banco de editais sincronizados"""
        try:
            total = await self.editais_collection.count_documents({})
            saude = await self.editais_collection.count_documents({"is_saude": True})
            
            # Última sincronização
            ultimo_log = await self.db.sync_logs.find_one(
                {},
                sort=[("timestamp", -1)]
            )
            
            # Editais por fonte
            pipeline = [
                {"$group": {"_id": "$fonte", "count": {"$sum": 1}}}
            ]
            por_fonte = {}
            async for doc in self.editais_collection.aggregate(pipeline):
                por_fonte[doc['_id']] = doc['count']
            
            return {
                "total_editais": total,
                "editais_saude": saude,
                "ultima_sincronizacao": ultimo_log.get('timestamp').isoformat() if ultimo_log else None,
                "por_fonte": por_fonte
            }
            
        except Exception as e:
            logger.error(f"❌ [SYNC] Erro ao obter stats: {str(e)}")
            return {}


# Instância global (será inicializada no server.py)
sync_service: Optional[SyncService] = None


def get_sync_service() -> Optional[SyncService]:
    """Retorna instância do serviço de sincronização"""
    return sync_service


def init_sync_service(db, pncp_client) -> SyncService:
    """Inicializa o serviço de sincronização"""
    global sync_service
    sync_service = SyncService(db, pncp_client)
    return sync_service
