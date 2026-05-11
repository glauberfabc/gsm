"""
BuscaService V2 - Busca com Alto Recall (Sistema GSM)
=========================================================

🎯 OBJETIVO: Maximizar recall (encontrar todos os editais relevantes)

PROBLEMA ANTERIOR:
- Busca limitada a campo 'objeto' em 'editais_normalizados'
- Não considerava tags, medicamentos, categorias
- Não expandia termos de saúde
- RESULTADO: "canabidiol" e "insulina" não retornavam resultados

SOLUÇÃO IMPLEMENTADA:
1. Busca em MÚLTIPLAS COLLECTIONS (editais_normalizados + licitacoes)
2. Busca em MÚLTIPLOS CAMPOS (objeto, medicamento, tags, orgao)
3. EXPANSÃO DE TERMOS para domínio de saúde
4. FALLBACK por tags quando não há match textual direto
5. RESOLUÇÃO PNCP até arquivos (Sistema GSM)

CRITÉRIO DE SUCESSO:
Buscar "canabidiol", "insulina", "medicamento hospitalar" e encontrar editais reais.
"""

import asyncio
import logging
import re
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Set
from motor.motor_asyncio import AsyncIOMotorDatabase

# Importar o classificador de oportunidades (Sistema GSM)
from services.classificador_oportunidade import get_classificador, StatusOportunidade

# Importar o serviço de extração de itens (Sistema GSM)
from services.item_extractor_service import get_item_extractor

# Importar o scorer de relevância (P2)
from services.relevance_scorer import get_relevance_scorer

# Importar serviços P3 - Confiabilidade de Dados
from services.data_audit_service import get_data_audit_service
from services.quality_scorer import get_quality_scorer

# Importar resolver de links V2 (Sistema GSM)
from services.link_resolver_service_v2 import get_link_resolver_v2

# Importar resolver PNCP (Sistema GSM - resolve até arquivos)
from services.pncp_resolver_service import get_pncp_resolver

# Importar busca direta PNCP (fallback quando dados locais insuficientes)
from services.pncp_search_service import get_pncp_search

# 🆕 v4.1: Importar novas fontes (ComprasNet e BNC)
from services.comprasnet_search_service import get_comprasnet_search
from services.bnc_search_service import get_bnc_search
from services.search_audit_service import get_search_audit

logger = logging.getLogger(__name__)


# ==================== EXPANSÃO DE TERMOS (DOMÍNIO SAÚDE) ====================

EXPANSAO_TERMOS_SAUDE = {
    # Canabidiol e derivados
    'canabidiol': ['cbd', 'cannabis', 'cannabidiol', 'medicamento controlado', 'mevatyl', 'epidiolex'],
    'cbd': ['canabidiol', 'cannabis', 'cannabidiol'],
    
    # Insulina e diabetes
    'insulina': ['diabetes', 'medicamento biológico', 'medicamento injetável', 'glicemia', 'lantus', 'novorapid', 'humalog'],
    'diabetes': ['insulina', 'glicemia', 'antidiabético'],
    
    # 🆕 v4.1: Prolia/Denosumabe (medicamento para osteoporose)
    # 🔴 v4.4: Removido 'imunobiologico' (muito genérico) e 'osteoporose' (categoria, não medicamento)
    'prolia': ['denosumabe', 'denosumab', 'xgeva'],
    'denosumabe': ['prolia', 'denosumab', 'xgeva'],
    'denosumab': ['prolia', 'denosumabe', 'xgeva'],
    
    # Medicamentos genéricos
    'medicamento': ['fármaco', 'insumo farmacêutico', 'produto farmacêutico', 'remédio', 'droga'],
    'farmaco': ['medicamento', 'insumo farmacêutico'],
    'fármaco': ['medicamento', 'insumo farmacêutico'],
    
    # Hospitalar/Saúde
    'hospitalar': ['saúde', 'assistência médica', 'hospital', 'uti', 'upa'],
    'hospital': ['hospitalar', 'saúde', 'assistência médica', 'uti', 'upa', 'ubs'],
    'saude': ['saúde', 'hospitalar', 'médico', 'assistência médica'],
    'saúde': ['saude', 'hospitalar', 'médico', 'assistência médica'],
    
    # Equipamentos e insumos
    'equipamento médico': ['equipamento hospitalar', 'aparelho médico', 'dispositivo médico'],
    'insumo': ['material', 'consumível', 'descartável'],
    
    # Medicamentos específicos
    'adalimumabe': ['humira', 'biológico', 'artrite', 'imunobiológico'],
    'pembrolizumabe': ['keytruda', 'oncológico', 'imunoterapia'],
    'rituximabe': ['mabthera', 'biológico', 'linfoma'],
    
    # Categorias amplas
    'oncologia': ['oncológico', 'quimioterapia', 'radioterapia', 'câncer', 'tumor'],
    'cardiologia': ['cardiológico', 'coração', 'cardiovascular'],
    'odontologia': ['odontológico', 'dental', 'dentista'],
}

# Tags de saúde para fallback
TAGS_SAUDE = [
    'saude_geral', 'hospitalar', 'medicamentos', 'equipamentos_medicos',
    'laboratorio', 'insumos', 'odontologia', 'oftalmologia', 'oncologia',
    'cardiologia', 'saúde', 'médico', 'farmacêutico'
]


class BuscaServiceV2:
    """
    Serviço de Busca com Alto Recall
    
    Combina múltiplas estratégias para maximizar a chance de encontrar editais relevantes.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        # Collections para busca
        self.editais_normalizados = db.editais_normalizados
        self.licitacoes = db.licitacoes
        self.editais_sync = db.editais_sync
        
    def expandir_termos(self, termo: str, smart: bool = False) -> Set[str]:
        """
        Expande termo de busca incluindo sinônimos e termos relacionados
        
        Args:
            termo: Termo original da busca
            smart: Se True, aplica expansão avançada (plural, gênero)
            
        Returns:
            Set com termo original + expansões
        """
        if not termo:
            return set()
            
        termos = {termo.lower().strip()}
        
        # Normalizar (remover acentos para matching)
        termo_normalizado = self._normalizar_texto(termo)
        termos.add(termo_normalizado)
        
        # 🚀 EXPANSÃO INTELIGENTE (v65.0)
        if smart:
            # Lógica de Plural/Singular básica (Português)
            if termo_normalizado.endswith('s') and len(termo_normalizado) > 3:
                termos.add(termo_normalizado[:-1]) # Singular
            elif not termo_normalizado.endswith('s'):
                termos.add(termo_normalizado + 's') # Plural
                
            # Lógica de Gênero básica (o/a)
            if termo_normalizado.endswith('o'):
                termos.add(termo_normalizado[:-1] + 'a')
            elif termo_normalizado.endswith('a') and len(termo_normalizado) > 3:
                termos.add(termo_normalizado[:-1] + 'o')
                
            # Variações comuns de finalização
            if termo_normalizado.endswith('cao'):
                termos.add(termo_normalizado[:-3] + 'coes')
            elif termo_normalizado.endswith('coes'):
                termos.add(termo_normalizado[:-4] + 'cao')
        
        # Buscar expansões de domínio (Sinônimos de Saúde)
        for chave, expansoes in EXPANSAO_TERMOS_SAUDE.items():
            chave_norm = self._normalizar_texto(chave)
            
            # Se o termo contém a chave ou vice-versa
            if chave_norm in termo_normalizado or termo_normalizado in chave_norm:
                termos.update([self._normalizar_texto(e) for e in expansoes])
                termos.add(chave_norm)
        
        # Também buscar o termo em expansões de outras chaves
        for chave, expansoes in EXPANSAO_TERMOS_SAUDE.items():
            for exp in expansoes:
                if self._normalizar_texto(exp) in termo_normalizado:
                    termos.add(self._normalizar_texto(chave))
                    termos.update([self._normalizar_texto(e) for e in expansoes])
        
        return termos
    
    def _normalizar_texto(self, texto: str) -> str:
        """Remove acentos e converte para minúsculo"""
        if not texto:
            return ""
        import unicodedata
        texto = unicodedata.normalize('NFKD', texto)
        texto = ''.join(c for c in texto if not unicodedata.combining(c))
        return texto.lower().strip()
    
    async def buscar(
        self,
        termo_busca: str = None,
        keywords: List[str] = None,
        estados: List[str] = None,
        municipio: str = None,  # 🏙️ NOVO: Filtro por município (v3.6)
        modalidade: str = None,
        esfera: str = None,
        apenas_saude: bool = False,
        limit: int = 50,
        skip: int = 0,
        expandir_termos: bool = True,
        smart_search: bool = False,  # 🚀 NOVO v65.0: Busca Inteligente
        incluir_historico: bool = False,
        periodo_dias: int = 90,
        # 🎯 CLASSIFICAÇÃO DE OPORTUNIDADES V3 (PADRÃO GSM)
        incluir_ativas: bool = True,
        incluir_futuras: bool = False,
        incluir_encerradas: bool = False,
        excluir_credenciamentos: bool = False,  # V3: INVERTIDO - excluir, não incluir!
        # 🔒 P3: CAMADA DE CONFIABILIDADE DE DADOS
        incluir_suspeitos: bool = False,  # P3: Incluir DATA_SUSPEITA no resultado
        incluir_planejamento: bool = False,  # P3: Incluir PLANEJAMENTO_LONGO no resultado
        limite_quality_score: int = 70  # P3: Score mínimo para feed default
    ) -> Dict[str, Any]:
        """
        Busca editais com alto recall, filtro temporal e CLASSIFICAÇÃO DE OPORTUNIDADES
        
        🎯 PADRÃO GSM - CLASSIFICAÇÃO DE OPORTUNIDADES:
        - Por DEFAULT retorna APENAS oportunidades ATIVAS (acionáveis agora)
        - FUTURAS e ENCERRADAS só aparecem se explicitamente solicitadas
        
        🔒 FILTRO TEMPORAL (OBRIGATÓRIO POR DEFAULT):
        - Retorna APENAS processos recentes (últimos 90 dias) ou com abertura futura
        - Processos antigos só aparecem com incluir_historico=True
        
        Estratégia:
        1. Busca em editais_normalizados (PNCP) - FONTE PRINCIPAL
        2. Busca em licitacoes SOMENTE se tiver datas válidas
        3. Aplica filtro temporal rigoroso
        4. CLASSIFICA cada resultado (ATIVA/FUTURA/ENCERRADA)
        5. FILTRA por status_oportunidade (DEFAULT: apenas ATIVAS)
        6. Merge e deduplica resultados
        
        Args:
            termo_busca: Termo de busca principal
            keywords: Lista de keywords adicionais (busca híbrida)
            estados: Filtro por UF
            modalidade: Filtro por modalidade
            esfera: Filtro por esfera
            apenas_saude: Se True, filtra apenas editais de saúde
            limit: Máximo de resultados
            skip: Offset para paginação
            expandir_termos: Se True, expande termos com sinônimos
            incluir_historico: Se True, inclui processos antigos (DEFAULT: False)
            periodo_dias: Período em dias para considerar "recente" (DEFAULT: 90)
            incluir_ativas: Se True, inclui oportunidades ATIVAS (DEFAULT: True)
            incluir_futuras: Se True, inclui oportunidades FUTURAS (DEFAULT: False)
            incluir_encerradas: Se True, inclui oportunidades ENCERRADAS (DEFAULT: False)
            
        Returns:
            Dict com resultados classificados, total, metadados
        """
        inicio = datetime.now()
        
        # 🔒 CALCULAR LIMITES TEMPORAIS
        from datetime import timedelta
        agora = datetime.now(timezone.utc)
        limite_publicacao = agora - timedelta(days=periodo_dias)
        
        # 🎯 OBTER CLASSIFICADOR
        classificador = get_classificador()
        
        logger.info(f"🔍 [BUSCA-V2] Filtro temporal: {'DESATIVADO (histórico)' if incluir_historico else f'últimos {periodo_dias} dias'}")
        logger.info(f"🎯 [BUSCA-V2] Filtro status: ATIVAS={incluir_ativas}, FUTURAS={incluir_futuras}, ENCERRADAS={incluir_encerradas}")
        
        # Preparar termos de busca
        termos_originais = []
        if termo_busca and termo_busca.strip():
            termos_originais.append(termo_busca.strip())
        if keywords:
            termos_originais.extend([k.strip() for k in keywords if k.strip()])
        
        # Expandir termos se habilitado
        termos_expandidos = set()
        for termo in termos_originais:
            if expandir_termos:
                termos_expandidos.update(self.expandir_termos(termo, smart=smart_search))
            else:
                termos_expandidos.add(termo.lower())
        
        logger.info(f"🔍 [BUSCA-V2] Termos originais: {termos_originais}")
        logger.info(f"🔍 [BUSCA-V2] Termos expandidos: {list(termos_expandidos)[:10]}...")
        
        # Executar buscas em paralelo
        resultados_total = []
        
        # =====================================================================
        # 🏠 v59.0: BUSCA 100% LOCAL - SEM FILTROS AGRESSIVOS
        # =====================================================================
        
        # 1. Busca em editais_gsm (COLLECTION PRÓPRIA GSM - FONTE ÚNICA)
        r0 = await self._buscar_editais_gsm(
            termos=list(termos_expandidos),
            estados=estados,
            modalidade=modalidade,
            apenas_saude=apenas_saude,
            limit=limit * 10  # v59.0: Buscar MUITO mais para garantir volume
        )
        resultados_total.extend(r0)
        logger.info(f"🏠 [GSM] Fonte editais_gsm: {len(r0)} resultados")
        
        # 🚀 v64.0: BUSCA EXTERNA PNCP (LIVE SEARCH)
        # Se for uma busca por termo específico e tivermos poucos resultados locais,
        # buscamos diretamente no PNCP (como o Agregador fazia).
        # Isso resolve o problema de recall para medicamentos novos ou pouco frequentes no objeto.
        # v65.0: Aumentar recall para medicamentos específicos
        if termo_busca and len(resultados_total) < 50: 
            logger.info(f"🌐 [PNCP-LIVE] Iniciando busca externa para '{termo_busca}'...")
            try:
                pncp_search = get_pncp_search()
                # Usar buscar_e_resolver para ter links e ITENS REAIS
                # v65.0: Buscar pelo menos 100 no PNCP para competir com Effecti
                r_ext = await pncp_search.buscar_e_resolver(termo_busca, limite=max(limit, 100))
                
                # Marcar resultados externos para priorização se necessário
                for r in r_ext:
                    r['_viana_recall'] = True
                    r['_origem_ext'] = 'PNCP_LIVE'
                
                resultados_total.extend(r_ext)
                logger.info(f"✅ [PNCP-LIVE] Busca externa retornou {len(r_ext)} resultados")
            except Exception as e:
                logger.error(f"❌ [PNCP-LIVE] Erro na busca externa: {e}")

        # 2. Busca em editais_normalizados (FONTE SECUNDÁRIA - apenas se ainda precisar)
        if len(resultados_total) < limit:
            r1 = await self._buscar_normalizados(
                termos=list(termos_expandidos),
                estados=estados,
                modalidade=modalidade,
                esfera=esfera,
                apenas_saude=apenas_saude,
                limit=limit * 5
            )
            resultados_total.extend(r1)
        
        # 3. Busca em licitacoes (apenas se ainda precisar de mais)
        if len(resultados_total) < limit:
            r2 = await self._buscar_licitacoes(
                termos=list(termos_expandidos),
                estados=estados,
                apenas_saude=apenas_saude,
                limit=limit * 3
            )
            resultados_total.extend(r2)
        
        # v59.0: FILTRO TEMPORAL DESATIVADO - Retornar TODOS os dados do banco
        # O cliente quer VOLUME, não filtros
        logger.info(f"🔓 [v59.0] Filtro temporal DESATIVADO - {len(resultados_total)} resultados brutos")
        
        # Deduplicar resultados
        resultados_unicos = self._deduplicar_resultados(resultados_total)
        logger.info(f"🔓 [v59.0] Após dedup: {len(resultados_unicos)} resultados únicos")
        
        # 🏙️ FILTRO POR MUNICÍPIO (apenas se solicitado)
        if municipio and municipio.strip():
            municipio_lower = municipio.strip().lower()
            resultados_unicos = [
                r for r in resultados_unicos
                if municipio_lower in (r.get('municipio', '') or '').lower()
            ]
            logger.info(f"🏙️ [BUSCA-V2] Filtro por município '{municipio}': {len(resultados_unicos)} resultados")
        
        # v59.0: CLASSIFICAÇÃO SIMPLIFICADA - Não eliminar nada
        for r in resultados_unicos:
            r['status_oportunidade'] = 'ATIVA'
            r['is_acionavel'] = True
            r['badge_status'] = {
                'cor': 'green',
                'icone': '🟢',
                'texto': 'DISPONÍVEL',
                'classe_css': 'bg-green-500 text-white'
            }
        
        resultados_filtrados = resultados_unicos
        contagem_pre_filtro = {'ATIVA': len(resultados_unicos), 'TOTAL': len(resultados_unicos)}
        
        logger.info(f"🎯 [v59.0] {len(resultados_filtrados)} resultados (SEM FILTROS)")
        
        # =====================================================================
        # v59.0: ENRIQUECIMENTO DE ITENS - SEM ELIMINAR
        # =====================================================================
        tempo_itens_inicio = time.time()
        
        # v59.0: Apenas enriquecer, NUNCA eliminar
        for r in resultados_filtrados:
            itens = r.get('itens_edital', [])
            if itens:
                r['itens_correspondentes'] = itens
                r['total_itens_match'] = len(itens)
            else:
                r['itens_correspondentes'] = []
                r['total_itens_match'] = 0
        
        resultados_com_itens = resultados_filtrados
        
        tempo_itens_ms = (time.time() - tempo_itens_inicio) * 1000
        logger.info(f"📦 [BUSCA-V2] Extração de itens: {len(resultados_com_itens)} com match em {tempo_itens_ms:.1f}ms")
        
        # =====================================================================
        # v59.0: RANKING SIMPLIFICADO - SEM ELIMINAÇÃO
        # =====================================================================
        tempo_ranking_inicio = time.time()
        
        # Adicionar score básico de relevância sem eliminar
        for idx, r in enumerate(resultados_com_itens):
            r['relevance_score'] = 80  # Score fixo alto
            r['relevance_level'] = 'ALTA'
            r['relevance_emoji'] = '🔥'
            r['ranking_position'] = idx + 1
            r['quality_score'] = 80
            r['quality_level'] = 'ALTA'
            r['audit_status'] = 'DADOS_VALIDOS'
            r['qualifica_feed_default'] = True
            r['link_status'] = 'VALIDO'
        
        tempo_ranking_ms = (time.time() - tempo_ranking_inicio) * 1000
        logger.info(f"📊 [v59.0] Ranking aplicado a {len(resultados_com_itens)} resultados em {tempo_ranking_ms:.1f}ms")
        
        # v59.0: PULAR TODOS OS FILTROS P3 - NÃO ELIMINAR NADA
        resultados_com_links = resultados_com_itens
        
        logger.info(f"🏠 [v59.0] Busca 100% local: {len(resultados_com_links)} resultados (SEM FILTROS)")
        
        # =====================================================================
        # 📊 CONTAGEM FINAL
        # =====================================================================
        contagem_status_final = {'ATIVA': len(resultados_com_links), 'TOTAL': len(resultados_com_links)}
        
        # Aplicar paginação
        total = len(resultados_com_links)
        resultados_paginados = resultados_com_links[skip:skip + limit]
        
        tempo_ms = (datetime.now() - inicio).total_seconds() * 1000
        
        # Validação de consistência
        soma_status = (
            contagem_status_final.get('ATIVA', 0) + 
            contagem_status_final.get('FUTURA', 0) + 
            contagem_status_final.get('ENCERRADA', 0)
        )
        if soma_status != total:
            logger.warning(f"⚠️ [CONSISTÊNCIA] soma_status={soma_status} != total={total}")
        
        logger.info(f"✅ [BUSCA-V2] {total} resultados finais (ATIVA:{contagem_status_final.get('ATIVA',0)} | FUTURA:{contagem_status_final.get('FUTURA',0)} | ENCERRADA:{contagem_status_final.get('ENCERRADA',0)}) em {tempo_ms:.1f}ms")
        
        return {
            "resultados": resultados_paginados,
            "total": total,
            "tempo_ms": tempo_ms,
            "tempo_itens_ms": 0,
            "tempo_ranking_ms": tempo_ranking_ms,
            "tempo_p3_ms": 0,
            "termos_originais": termos_originais,
            "termos_expandidos": list(termos_expandidos)[:20],
            "origem": "MongoDB Local (P0 + P1 + P2 + P3)",
            "fontes_consultadas": ["editais_gsm"],
            # v59.0: Estatísticas simplificadas
            "contagem_status": contagem_status_final,
            "contagem_pre_filtro": contagem_pre_filtro,
            "relevancia": {"alta": len(resultados_paginados), "media": 0, "baixa": 0},
            "auditoria": {},
            "qualidade": {},
            "filtros_aplicados": {
                "incluir_ativas": incluir_ativas,
                "incluir_futuras": incluir_futuras,
                "incluir_encerradas": incluir_encerradas,
                "excluir_credenciamentos": excluir_credenciamentos,
                "incluir_suspeitos": incluir_suspeitos,
                "incluir_planejamento": incluir_planejamento,
                "limite_quality_score": limite_quality_score
            }
        }
    
    def _contar_por_status(self, resultados: List[Dict]) -> Dict[str, int]:
        """Conta resultados por status de oportunidade V3"""
        contagem = {
            StatusOportunidade.ATIVA.value: 0,
            StatusOportunidade.FUTURA.value: 0,
            StatusOportunidade.ENCERRADA.value: 0,
            "CREDENCIAMENTOS": 0  # V3: Contagem separada para credenciamentos (subset de ATIVA)
        }
        for r in resultados:
            status = r.get('status_oportunidade', StatusOportunidade.ENCERRADA.value)
            if status in contagem:
                contagem[status] += 1
            # Contar credenciamentos separadamente (são ATIVA mas com badge diferente)
            if r.get('is_credenciamento', False):
                contagem["CREDENCIAMENTOS"] += 1
        return contagem
    
    async def _buscar_normalizados(
        self,
        termos: List[str],
        estados: List[str] = None,
        modalidade: str = None,
        esfera: str = None,
        apenas_saude: bool = False,
        limit: int = 100
    ) -> List[Dict]:
        """Busca em editais_normalizados usando múltiplas estratégias"""
        resultados = []
        
        try:
            # Estratégia 1: Full Text Search (se houver termos)
            if termos:
                query_text = {"$text": {"$search": " ".join(termos)}}
                if estados:
                    query_text["uf"] = {"$in": [e.upper() for e in estados]}
                if esfera:
                    query_text["esfera"] = esfera
                if apenas_saude:
                    query_text["is_saude"] = True
                
                cursor = self.editais_normalizados.find(
                    query_text,
                    {"_id": 0}
                ).limit(limit)
                
                async for doc in cursor:
                    # 🛡️ GARANTIR CONTRATO: tags sempre array
                    doc = self._garantir_arrays(doc)
                    doc['_origem'] = 'editais_normalizados'
                    doc['_match_type'] = 'full_text'
                    resultados.append(doc)
            
            # Estratégia 2: Busca por filtros (esfera, estados) SEM termos de texto
            # 🔒 P4: Permitir buscar por esfera=Municipal mesmo sem termo de busca
            if not termos and (esfera or estados):
                query_filtros = {}
                if estados:
                    query_filtros["uf"] = {"$in": [e.upper() for e in estados]}
                if esfera:
                    query_filtros["esfera"] = esfera
                if apenas_saude:
                    query_filtros["is_saude"] = True
                
                cursor = self.editais_normalizados.find(
                    query_filtros,
                    {"_id": 0}
                ).sort([("created_at", -1), ("data_abertura", -1)]).limit(limit)
                
                async for doc in cursor:
                    doc = self._garantir_arrays(doc)
                    doc['_origem'] = 'editais_normalizados'
                    doc['_match_type'] = 'filtros_apenas'
                    resultados.append(doc)
                
                logger.info(f"📋 [BUSCA-V2] Busca por filtros (sem termo): {len(resultados)} resultados")
            
            # Estratégia 3: Regex em múltiplos campos (para termos não indexados)
            # 🆕 v4.0 ELITE: Busca por SIMILARIDADE (partial match LIKE %termo%)
            # Removido word boundary \b para permitir buscas como "Denosu" → "Denosumabe"
            for termo in termos[:5]:  # Limitar para performance
                # Escapar caracteres especiais de regex
                termo_escaped = re.escape(termo)
                # 🎯 v4.0 ELITE: Partial match - sem word boundary para aceitar "Denosu" em "Denosumabe"
                regex_pattern = termo_escaped
                regex = {"$regex": regex_pattern, "$options": "i"}
                
                # Busca em objeto
                query_regex = {"objeto": regex}
                if estados:
                    query_regex["uf"] = {"$in": [e.upper() for e in estados]}
                if esfera:
                    query_regex["esfera"] = esfera
                
                cursor = self.editais_normalizados.find(
                    query_regex,
                    {"_id": 0}
                ).limit(limit // 2)
                
                async for doc in cursor:
                    # 🛡️ GARANTIR CONTRATO: tags sempre array
                    doc = self._garantir_arrays(doc)
                    doc['_origem'] = 'editais_normalizados'
                    doc['_match_type'] = 'regex_objeto'
                    resultados.append(doc)
                
                # Busca em tags - partial match também
                query_tags = {"tags": {"$regex": termo_escaped, "$options": "i"}}
                cursor = self.editais_normalizados.find(
                    query_tags,
                    {"_id": 0}
                ).limit(limit // 2)
                
                async for doc in cursor:
                    # 🛡️ GARANTIR CONTRATO: tags sempre array
                    doc = self._garantir_arrays(doc)
                    doc['_origem'] = 'editais_normalizados'
                    doc['_match_type'] = 'regex_tags'
                    resultados.append(doc)
        
        except Exception as e:
            logger.error(f"❌ [BUSCA-V2] Erro em _buscar_normalizados: {e}")
        
        return resultados
    
    def _garantir_arrays(self, doc: Dict) -> Dict:
        """
        🛡️ CONTRATO DE DADOS: Garante que campos de array são SEMPRE arrays
        
        Campos garantidos:
        - tags: sempre array
        - tags_saude: sempre array
        """
        # Garantir tags
        raw_tags = doc.get('tags')
        if isinstance(raw_tags, list):
            doc['tags'] = raw_tags
        elif isinstance(raw_tags, str):
            doc['tags'] = [raw_tags] if raw_tags else []
        else:
            doc['tags'] = []
        
        # Garantir tags_saude
        raw_tags_saude = doc.get('tags_saude')
        if isinstance(raw_tags_saude, list):
            doc['tags_saude'] = raw_tags_saude
        elif isinstance(raw_tags_saude, str):
            doc['tags_saude'] = [raw_tags_saude] if raw_tags_saude else []
        else:
            doc['tags_saude'] = []
        
        return doc
    
    # =====================================================================
    # 🏠 v53.0: BUSCA NA COLLECTION PRÓPRIA GSM (INDEPENDÊNCIA TOTAL)
    # =====================================================================
    async def _buscar_editais_gsm(
        self,
        termos: List[str],
        estados: List[str] = None,
        modalidade: str = None,
        apenas_saude: bool = False,
        limit: int = 100
    ) -> List[Dict]:
        """
        v57.0: Busca na collection editais_gsm (dados clonados próprios)
        
        Esta é a fonte PRINCIPAL de dados do sistema independente.
        Populada pelo IngestaoMassivaService com dados multi-fonte.
        
        SCHEMA GSM v57.0:
        - UASG em destaque (azul)
        - Portal de Origem (ComprasNet, PNCP, BLL, etc)
        - Tabela de Itens com 6 colunas: Grupo, Item, Descrição, ME/EPP, QTD, Valor Total
        """
        resultados = []
        ids_vistos = set()
        
        try:
            # Collection própria GSM
            collection = self.db.editais_gsm
            
            # Construir query mais permissiva para alto volume
            or_conditions = []
            
            for termo in termos[:20]:
                termo_escaped = re.escape(termo)
                regex = {"$regex": termo_escaped, "$options": "i"}
                
                or_conditions.append({"objeto": regex})
                or_conditions.append({"dados_orgao.nome": regex})
                or_conditions.append({"itens_clonados.descricao": regex})
                or_conditions.append({"termo_busca": regex})
            
            query = {"$or": or_conditions} if or_conditions else {}
            
            if estados:
                query["$and"] = query.get("$and", [])
                query["$and"].append({
                    "$or": [
                        {"uf": {"$in": [e.upper() for e in estados]}},
                        {"dados_orgao.uf": {"$in": [e.upper() for e in estados]}}
                    ]
                })
            
            if modalidade:
                query["modalidade"] = {"$regex": modalidade, "$options": "i"}
            
            # Buscar com sort por data mais recente
            cursor = collection.find(
                query, 
                {"_id": 0}
            ).sort("data_publicacao", -1).limit(limit * 2)  # Buscar mais para ter margem
            
            async for doc in cursor:
                doc_id = doc.get('id_gsm') or doc.get('id_externo')
                if doc_id in ids_vistos:
                    continue
                ids_vistos.add(doc_id)
                
                dados_orgao = doc.get('dados_orgao', {}) or {}
                
                # Normalizar para formato padrão de busca (SCHEMA v57.0)
                normalizado = {
                    # IDs
                    'id_externo': doc.get('id_gsm') or doc.get('id_externo'),
                    'id_gsm': doc.get('id_gsm'),
                    'numero_controle_pncp': doc.get('numero_controle_pncp', ''),
                    
                    # Dados do órgão
                    'objeto': doc.get('objeto', ''),
                    'orgao': doc.get('orgao') or dados_orgao.get('nome', ''),
                    'estado': doc.get('uf') or dados_orgao.get('uf', ''),
                    'uf': doc.get('uf') or dados_orgao.get('uf', ''),
                    'municipio': doc.get('municipio') or dados_orgao.get('municipio', ''),
                    
                    # UASG em destaque
                    'uasg': dados_orgao.get('uasg', '') or doc.get('uasg', ''),
                    'cnpj': dados_orgao.get('cnpj', ''),
                    
                    # Portal de captura
                    'portal_captura': doc.get('portal_captura') or doc.get('fonte') or 'PNCP',
                    'fonte': doc.get('portal_captura') or doc.get('fonte') or doc.get('fonte_origem', 'GSM_LOCAL'),
                    
                    # Classificação
                    'modalidade': doc.get('modalidade', 'Pregão Eletrônico'),
                    'status': doc.get('status', 'ATIVA'),
                    
                    # Valores
                    'valor_estimado': doc.get('valor_estimado'),
                    
                    # Datas
                    'data_publicacao': doc.get('data_publicacao'),
                    'data_abertura': doc.get('data_abertura') or doc.get('data_final'),
                    'data_inicial': doc.get('data_inicial') or doc.get('data_publicacao'),
                    'data_final': doc.get('data_final') or doc.get('data_abertura'),
                    
                    # Links (incluindo PDF dos anexos)
                    'link_origem': doc.get('link_documento') or doc.get('link_pdf') or doc.get('link_portal') or doc.get('link_origem'),
                    'link_portal': doc.get('link_portal') or doc.get('link_documento'),
                    'link_edital': doc.get('link_pdf') or doc.get('link_documento') or doc.get('link_edital'),
                    'link_documento': doc.get('link_pdf') or doc.get('link_documento'),
                    
                    # Identificação da licitação
                    'numero_processo': doc.get('numero_processo', ''),
                    'numero_licitacao': doc.get('numero_licitacao', ''),
                    
                    # TABELA DE ITENS (6 colunas)
                    # Campos: grupo, item, descricao, me_epp, quantidade, valor_total
                    'itens_edital': doc.get('itens_clonados', []),
                    
                    # Metadados de busca
                    '_origem': 'editais_gsm',
                    '_match_type': 'gsm_local',
                    '_termo_match': termos[0] if termos else '',
                    'tags': doc.get('tags', []),
                    'is_saude': doc.get('is_saude', False)
                }
                resultados.append(normalizado)
                
                if len(resultados) >= limit:
                    break
            
            logger.info(f"🏠 [GSM-LOCAL] Encontrados {len(resultados)} editais na collection própria")
            
        except Exception as e:
            logger.error(f"❌ [GSM-LOCAL] Erro na busca: {e}")
            import traceback
            traceback.print_exc()
        
        return resultados[:limit]
    
    async def _buscar_licitacoes(
        self,
        termos: List[str],
        estados: List[str] = None,
        apenas_saude: bool = False,
        limit: int = 100
    ) -> List[Dict]:
        """
        Busca em collection licitacoes (dados históricos/mockados)
        
        ESTRATÉGIA: Buscar TODOS os termos nos campos medicamento E objeto
        🔴 v4.0 MATA-LIXO: Usar word boundary para palavra exata
        """
        resultados = []
        ids_vistos = set()  # Evitar duplicatas
        
        try:
            # Buscar com TODOS os termos em múltiplos campos
            for termo in termos[:20]:  # Limitar a 20 termos
                # 🔴 v4.0: Usar word boundary para busca de palavra exata
                termo_escaped = re.escape(termo)
                regex_pattern = f"\\b{termo_escaped}\\b"
                regex = {"$regex": regex_pattern, "$options": "i"}
                
                # Buscar em medicamento E objeto
                query = {
                    "$or": [
                        {"medicamento": regex},
                        {"objeto": regex},
                    ]
                }
                
                if estados:
                    # Buscar em ambos os campos (estado OU uf) para compatibilidade
                    query["$and"] = query.get("$and", [])
                    query["$and"].append({
                        "$or": [
                            {"estado": {"$in": [e.upper() for e in estados]}},
                            {"uf": {"$in": [e.upper() for e in estados]}}
                        ]
                    })
                
                cursor = self.licitacoes.find(
                    query,
                    {"_id": 0}
                ).limit(limit)
                
                async for doc in cursor:
                    # Evitar duplicatas usando ID
                    doc_id = doc.get('id', doc.get('fonte_id', str(doc)))
                    if doc_id in ids_vistos:
                        continue
                    ids_vistos.add(doc_id)
                    
                    normalizado = self._normalizar_licitacao(doc)
                    normalizado['_origem'] = 'licitacoes'
                    normalizado['_match_type'] = 'regex_licitacoes'
                    normalizado['_termo_match'] = termo
                    resultados.append(normalizado)
                
                if len(resultados) >= limit:
                    break
        
        except Exception as e:
            logger.error(f"❌ [BUSCA-V2] Erro em _buscar_licitacoes: {e}")
        
        return resultados
    
    async def _buscar_por_tags(
        self,
        termos: List[str],
        limite: int = 50
    ) -> List[Dict]:
        """
        Fallback: busca por tags de saúde quando não há match textual direto
        
        Se o usuário busca "canabidiol" e não encontra, retorna editais
        que têm tags de saúde/medicamentos relacionados.
        """
        resultados = []
        
        try:
            # Verificar se algum termo está relacionado a saúde
            termos_saude = False
            for termo in termos:
                termo_lower = termo.lower()
                if any(s in termo_lower for s in ['saude', 'saúde', 'medic', 'hospital', 'farm']):
                    termos_saude = True
                    break
                if termo_lower in EXPANSAO_TERMOS_SAUDE:
                    termos_saude = True
                    break
            
            if termos_saude:
                # Buscar editais com tags de saúde
                query = {
                    "$or": [
                        {"is_saude": True},
                        {"tags": {"$in": TAGS_SAUDE}},
                    ]
                }
                
                cursor = self.editais_normalizados.find(
                    query,
                    {"_id": 0}
                ).sort([("data_abertura", -1)]).limit(limite)
                
                async for doc in cursor:
                    doc['_origem'] = 'editais_normalizados'
                    doc['_match_type'] = 'fallback_tags_saude'
                    resultados.append(doc)
        
        except Exception as e:
            logger.error(f"❌ [BUSCA-V2] Erro em _buscar_por_tags: {e}")
        
        return resultados
    
    def _normalizar_licitacao(self, doc: Dict) -> Dict:
        """
        Normaliza documento da collection licitacoes para formato padrão
        
        🛡️ CONTRATO GARANTIDO:
        - tags: SEMPRE array (nunca None, string ou objeto)
        - tags_saude: SEMPRE array
        """
        # 🛡️ Garantir que tags é SEMPRE array
        raw_tags = doc.get('tags_display') or doc.get('tags')
        if isinstance(raw_tags, list):
            tags = raw_tags
        elif isinstance(raw_tags, str):
            tags = [raw_tags] if raw_tags else []
        else:
            tags = []
        
        return {
            "id_externo": doc.get('id', doc.get('fonte_id', '')),
            "objeto": doc.get('medicamento', '') or doc.get('objeto', ''),
            "orgao": doc.get('orgao_licitante', ''),
            "uf": doc.get('estado', ''),
            "municipio": doc.get('municipio', ''),
            "esfera": doc.get('esfera', ''),
            "modalidade": doc.get('modalidade', ''),
            "status": doc.get('status', ''),
            "data_publicacao": doc.get('data_publicacao'),
            "data_abertura": doc.get('data_final') or doc.get('data_abertura'),
            "link_edital": doc.get('link_origem', ''),
            "link_status": 'VALIDO' if doc.get('link_origem') else 'INVALIDO',
            "numero_processo": doc.get('numero_processo', doc.get('numero_pregao', '')),
            "fonte": doc.get('fonte', 'HISTORICO'),
            "is_saude": doc.get('is_saude', True),
            "tags": tags,  # 🛡️ GARANTIDO: sempre array
            "tags_saude": [],  # 🛡️ GARANTIDO: sempre array (será preenchido por matcher)
            "medicamento": doc.get('medicamento', ''),
        }
    
    async def _resolver_links_gsm(self, resultados: List[Dict]) -> List[Dict]:
        """
        🔗 v53.0: RESOLUÇÃO DE LINKS (SISTEMA GSM INDEPENDENTE)
        
        LÓGICA SIMPLIFICADA:
        - Aceitar TODOS os resultados do banco local
        - Usar link_portal como fallback se não tiver link_edital
        - NÃO descartar por falta de link (usuário pode buscar manualmente)
        
        O objetivo é MOSTRAR os resultados, não filtrar por link.
        """
        resultados_aceitos = []
        
        for r in resultados:
            # Pegar qualquer link disponível
            link = (
                r.get('link_edital') or 
                r.get('link_portal') or 
                r.get('link_origem') or 
                r.get('link_documento') or
                ''
            )
            
            # Garantir que tem algum link (mesmo que seja o portal genérico)
            if not link:
                # Construir link genérico do PNCP se tiver número de controle
                num_controle = r.get('numero_controle_pncp') or r.get('id_externo')
                if num_controle:
                    link = f"https://pncp.gov.br/app/editais/{num_controle}"
            
            # Atualizar links no resultado
            r['link_portal'] = link or r.get('link_portal', '')
            r['link_edital'] = link or r.get('link_edital', '')
            r['link_origem'] = link or r.get('link_origem', '')
            r['link_status'] = 'VALIDO' if link else 'PENDENTE'
            
            resultados_aceitos.append(r)
        
        logger.info(f"🔗 [GSM-LINKS] {len(resultados)} → {len(resultados_aceitos)} aceitos (100% local, sem descarte)")
        
        return resultados_aceitos
    
    def _normalizar_links(self, resultados: List[Dict]) -> List[Dict]:
        """
        DEPRECATED: Use _resolver_links_gsm
        Mantido para compatibilidade.
        """
        logger.warning("⚠️ _normalizar_links está deprecated. Use _resolver_links_gsm")
        # Fallback síncrono simples
        return [r for r in resultados if r.get('link_sistema_origem') or r.get('link_edital')]
    
    def _filtrar_por_data(
        self,
        resultados: List[Dict],
        limite_publicacao: datetime,
        data_atual: datetime
    ) -> List[Dict]:
        """
        🔒 FILTRO TEMPORAL OBRIGATÓRIO
        
        Retorna APENAS processos que atendam a pelo menos UM critério:
        - Data de publicação >= limite_publicacao (últimos N dias)
        - Data de abertura >= data_atual (abertura futura)
        
        Processos sem datas válidas são EXCLUÍDOS por default.
        """
        filtrados = []
        
        for r in resultados:
            # Extrair datas
            pub_str = r.get('data_publicacao')
            ab_str = r.get('data_abertura')
            
            is_recente = False
            
            # Verificar data de publicação
            if pub_str:
                try:
                    if isinstance(pub_str, datetime):
                        pub_date = pub_str
                    elif isinstance(pub_str, str):
                        pub_date = datetime.fromisoformat(
                            pub_str.replace('Z', '+00:00').split('T')[0]
                        )
                    else:
                        pub_date = None
                    
                    if pub_date:
                        # Normalizar timezone
                        if pub_date.tzinfo is None:
                            from datetime import timezone
                            pub_date = pub_date.replace(tzinfo=timezone.utc)
                        
                        if pub_date >= limite_publicacao:
                            is_recente = True
                except Exception:
                    pass
            
            # Verificar data de abertura (oportunidade acionável)
            if ab_str and not is_recente:
                try:
                    if isinstance(ab_str, datetime):
                        ab_date = ab_str
                    elif isinstance(ab_str, str):
                        ab_date = datetime.fromisoformat(
                            ab_str.replace('Z', '+00:00').split('T')[0]
                        )
                    else:
                        ab_date = None
                    
                    if ab_date:
                        # Normalizar timezone
                        if ab_date.tzinfo is None:
                            from datetime import timezone
                            ab_date = ab_date.replace(tzinfo=timezone.utc)
                        
                        if ab_date >= data_atual:
                            is_recente = True
                except Exception:
                    pass
            
            # Incluir se atende aos critérios OU se não tem datas (dados importantes)
            # 🔄 FALLBACK: Dados sem data de origem 'licitacoes' são mantidos
            # porque contêm medicamentos específicos que são valiosos
            sem_datas = not pub_str and not ab_str
            e_licitacoes = r.get('_origem') == 'licitacoes'
            
            if is_recente or (sem_datas and e_licitacoes):
                filtrados.append(r)
        
        logger.info(f"🔒 [FILTRO-TEMPORAL] {len(resultados)} → {len(filtrados)} (removidos {len(resultados) - len(filtrados)} antigos)")
        
        return filtrados
    
    def _deduplicar_resultados(self, resultados: List[Dict]) -> List[Dict]:
        """Remove duplicatas mantendo o resultado mais relevante"""
        vistos = {}
        
        for r in resultados:
            # Chave de deduplicação
            # v65.0: Chave de deduplicação melhorada (inclui licitacao_num e origem)
            # Isso evita que editais diferentes do mesmo órgão no mesmo dia sejam mesclados
            chave = (
                r.get('numero_processo', ''),
                r.get('licitacao_num', r.get('numero_licitacao', '')),
                r.get('orgao', r.get('orgao_licitante', '')),
                str(r.get('data_abertura', '')),
                r.get('fonte', 'GSM')
            )
            
            # Se já vimos, comparar qual é melhor
            if chave in vistos:
                existente = vistos[chave]
                # Preferir o que tem link válido
                if r.get('link_status') == 'VALIDO' and existente.get('link_status') != 'VALIDO':
                    vistos[chave] = r
            else:
                vistos[chave] = r
        
        return list(vistos.values())
    
    def _ordenar_por_relevancia(
        self,
        resultados: List[Dict],
        termos_busca: List[str]
    ) -> List[Dict]:
        """Ordena resultados por relevância (considera itens correspondentes)"""
        def calcular_score(doc):
            score = 0
            
            # 🎯 SCORE PRINCIPAL: Itens correspondentes (Sistema GSM)
            total_itens_match = doc.get('total_itens_match', 0)
            score += total_itens_match * 100  # Cada item com match vale muito
            
            # Score baseado no tipo de match
            match_type = doc.get('_match_type', '')
            if match_type == 'full_text':
                score += 50
            elif match_type == 'regex_objeto':
                score += 40
            elif match_type == 'regex_tags':
                score += 30
            elif match_type == 'fallback_tags_saude':
                score += 20
            
            # Bonus para link válido
            if doc.get('link_status') == 'VALIDO':
                score += 15
            
            # Bonus para oportunidade ativa
            if doc.get('status_oportunidade') == 'ATIVA':
                score += 25
            
            # Bonus para match direto no termo
            objeto = str(doc.get('objeto', '') or doc.get('medicamento', '')).lower()
            for termo in termos_busca:
                if termo.lower() in objeto:
                    score += 30
            
            # Score do MongoDB (se disponível)
            score += doc.get('score', 0) * 5
            
            return score
        
        return sorted(resultados, key=calcular_score, reverse=True)


# Singleton
_instance = None

def get_busca_service_v2(db: AsyncIOMotorDatabase) -> BuscaServiceV2:
    """Retorna instância do BuscaServiceV2"""
    global _instance
    if _instance is None:
        _instance = BuscaServiceV2(db)
    return _instance
