"""
ComprasGov Service — Serviço de integração com a API Dados Abertos do Compras.gov.br
=====================================================================================

Orquestra o cliente comprasgov_client.py e expõe funcionalidades de alto nível:
  - Busca por palavra-chave (ingestão + busca local)
  - Sincronização incremental por data
  - Pesquisa de preço histórico
  - Consulta de fornecedores
  - Consulta de contratos e atas

Integra com o motor_independente.py como fonte complementar de dados.
"""

import asyncio
import logging
import hashlib
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from backend.scrapers import comprasgov_client as cgov

logger = logging.getLogger(__name__)


class ComprasGovService:
    """
    Serviço de alto nível para a API de Dados Abertos do Compras.gov.br.
    
    Funcionalidades:
    1. buscar_contratacoes_por_periodo — Sincronização incremental
    2. buscar_contratacoes_por_objeto — Busca por palavra-chave no objeto
    3. buscar_itens_contratacao — Itens de uma contratação específica
    4. pesquisar_preco_material — Histórico de preços
    5. consultar_fornecedor — Dados de fornecedor
    6. buscar_contratos — Contratos ativos
    7. buscar_arp — Atas de registro de preço
    8. buscar_licitacoes_legado — Módulo legado (pré-PNCP)
    """

    def __init__(self, db=None):
        self.db = db
        self._initialized = False

    async def _ensure_indexes(self):
        """Cria índices para busca eficiente no MongoDB."""
        if self.db is None or self._initialized:
            return
        try:
            # Índice único para evitar duplicados da API
            await self.db.comprasgov_v3.create_index("numero_controle_pncp", unique=True)
            # Índice de texto para busca por objeto
            await self.db.comprasgov_v3.create_index([("objeto", "text"), ("orgao_nome", "text")])
            # Índice para filtros comuns
            await self.db.comprasgov_v3.create_index([("uf", 1), ("data_publicacao", -1)])
            self._initialized = True
            logger.info("✅ [ComprasGov] Índices do MongoDB verificados/criados.")
        except Exception as e:
            logger.error(f"Erro ao criar índices ComprasGov: {e}")

    # ─── Contratações PNCP ────────────────────────────────

    async def buscar_contratacoes_por_periodo(
        self,
        data_inicial: str,
        data_final: str,
        uf: Optional[str] = None,
        max_pages: int = 100,
        modalidade: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Busca contratações PNCP publicadas em um período.
        
        Use para sincronização incremental:
            data_inicial = ontem, data_final = hoje
        
        Args:
            data_inicial: Data inicial (YYYY-MM-DD)
            data_final: Data final (YYYY-MM-DD)
            uf: Filtrar por UF (opcional)
            max_pages: Máximo de páginas a percorrer
        
        Returns:
            {"contratacoes": [...], "total": int, "normalizadas": [...]}
        """
        logger.info(
            f"📡 [ComprasGov] Buscando contratações de {data_inicial} a {data_final}"
            + (f" UF={uf}" if uf else "")
        )

        result = await cgov.consultar_contratacoes_pncp(
            data_publicacao_inicial=data_inicial,
            data_publicacao_final=data_final,
            uf=uf,
            max_pages=max_pages,
            modalidade=modalidade,
        )

        raw = result.get("resultado", [])
        normalizadas = [cgov.normalizar_contratacao_pncp(r) for r in raw]

        logger.info(
            f"✅ [ComprasGov] {len(normalizadas)} contratações encontradas "
            f"({result.get('tempo_segundos', 0)}s)"
        )

        return {
            "contratacoes": raw,
            "normalizadas": normalizadas,
            "total": result.get("totalRegistros", len(raw)),
            "paginas_lidas": result.get("paginas_lidas", 1),
            "tempo_segundos": result.get("tempo_segundos", 0),
            "erros": result.get("erros", []),
        }

    # codigoModalidade e obrigatorio na API do Compras.gov.br (nao ha opcao
    # "todas as modalidades" numa unica chamada - confirmado via OpenAPI
    # spec ao vivo: sem esse parametro a API retorna 404). Cobrimos as
    # modalidades mais comuns para medicamentos/insumos (mesmo conjunto ja
    # usado na busca por escopo Ministerio da Saude): Concorrencia
    # Eletronica, Pregao Eletronico, Dispensa de Licitacao, Inexigibilidade.
    MODALIDADES_BUSCA_GERAL = [4, 6, 8, 9]

    async def buscar_contratacoes_por_objeto(
        self,
        termo: str,
        dias_atras: int = 30,
        uf: Optional[str] = None,
        max_pages: int = 20,
        modalidade: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Busca contratações que contenham o termo no objeto.

        Estratégia:
        1. Buscar contratações publicadas nos últimos N dias (uma chamada
           por modalidade relevante, em paralelo - a API não aceita
           "todas as modalidades" numa única chamada)
        2. Filtrar localmente pelo termo no campo objeto
        3. Buscar itens das contratações relevantes

        Args:
            termo: Palavra-chave (ex: "canabidiol", "insulina")
            dias_atras: Buscar publicações dos últimos N dias
            uf: Filtrar por UF
            max_pages: Máximo de páginas POR modalidade consultada
            modalidade: Se informado, consulta só essa modalidade em vez
                das modalidades padrão de busca geral

        Returns:
            {"contratacoes_total": int, "com_termo": [...], "total": int}
        """
        hoje = datetime.now().strftime("%Y-%m-%d")
        data_inicial = (datetime.now() - timedelta(days=dias_atras)).strftime("%Y-%m-%d")

        modalidades = [modalidade] if modalidade is not None else self.MODALIDADES_BUSCA_GERAL

        logger.info(
            f"🔍 [ComprasGov] Buscando '{termo}' nas contratações de {data_inicial} a {hoje} "
            f"(modalidades: {modalidades})"
        )

        resultados_por_modalidade = await asyncio.gather(
            *[
                cgov.consultar_contratacoes_pncp(
                    data_publicacao_inicial=data_inicial,
                    data_publicacao_final=hoje,
                    uf=uf,
                    max_pages=max_pages,
                    modalidade=mod,
                )
                for mod in modalidades
            ],
            return_exceptions=True,
        )

        raw = []
        tempo_total = 0.0
        for r in resultados_por_modalidade:
            if isinstance(r, Exception):
                logger.error(f"Erro consultando modalidade no ComprasGov: {r}")
                continue
            raw.extend(r.get("resultado", []))
            tempo_total += r.get("tempo_segundos", 0)

        termo_lower = termo.lower()

        # Filtrar pelo termo no objeto
        com_termo = []
        for r in raw:
            objeto = (r.get("objetoCompra") or "").lower()
            info_comp = (r.get("informacaoComplementar") or "").lower()
            if termo_lower in objeto or termo_lower in info_comp:
                com_termo.append(cgov.normalizar_contratacao_pncp(r))

        logger.info(
            f"✅ [ComprasGov] {len(com_termo)}/{len(raw)} contratações contêm '{termo}'"
        )

        return {
            "contratacoes_total": len(raw),
            "com_termo": com_termo,
            "total": len(com_termo),
            "tempo_segundos": round(tempo_total, 2),
        }

    async def buscar_itens_contratacao(
        self,
        id_compra: str,
    ) -> List[Dict]:
        """
        Busca itens de uma contratação específica.
        
        Args:
            id_compra: ID da compra (campo idCompra)
        
        Returns:
            Lista de itens normalizados
        """
        result = await cgov.consultar_itens_contratacoes_pncp(id_compra=id_compra)
        raw = result.get("resultado", [])
        return [cgov.normalizar_item_contratacao(r) for r in raw]

    async def buscar_resultado_itens(
        self,
        id_compra: str,
    ) -> List[Dict]:
        """
        Busca resultado dos itens (vencedores).
        
        Args:
            id_compra: ID da compra
        
        Returns:
            Lista de resultados
        """
        result = await cgov.consultar_resultado_itens_pncp(id_compra=id_compra)
        return result.get("resultado", [])

    # ─── Pesquisa de Preço ────────────────────────────────

    async def pesquisar_preco_material(
        self,
        descricao: str,
        max_pages: int = 10,
    ) -> Dict[str, Any]:
        """
        Pesquisa histórico de preços de material.
        
        Args:
            descricao: Descrição do item (ex: "CANABIDIOL")
            max_pages: Máximo de páginas
        
        Returns:
            {"precos": [...], "total": int, "estatisticas": {...}}
        """
        logger.info(f"💰 [ComprasGov] Pesquisando preço de '{descricao}'")

        result = await cgov.consultar_preco_material(
            descricao_item=descricao,
            max_pages=max_pages,
        )

        raw = result.get("resultado", [])

        # Calcular estatísticas
        precos = [
            r.get("precoUnitario") or r.get("valorUnitario") or 0
            for r in raw
            if (r.get("precoUnitario") or r.get("valorUnitario"))
        ]

        estatisticas = {}
        if precos:
            precos_validos = [p for p in precos if p > 0]
            if precos_validos:
                estatisticas = {
                    "menor_preco": min(precos_validos),
                    "maior_preco": max(precos_validos),
                    "media": round(sum(precos_validos) / len(precos_validos), 2),
                    "mediana": sorted(precos_validos)[len(precos_validos) // 2],
                    "total_registros": len(precos_validos),
                }

        logger.info(
            f"✅ [ComprasGov] {len(raw)} registros de preço para '{descricao}'"
        )

        return {
            "precos": raw,
            "total": len(raw),
            "estatisticas": estatisticas,
            "tempo_segundos": result.get("tempo_segundos", 0),
        }

    async def pesquisar_preco_servico(
        self,
        descricao: str,
        max_pages: int = 10,
    ) -> Dict[str, Any]:
        """Pesquisa histórico de preços de serviço."""
        result = await cgov.consultar_preco_servico(
            descricao_item=descricao,
            max_pages=max_pages,
        )
        return {
            "precos": result.get("resultado", []),
            "total": result.get("totalRegistros", 0),
            "tempo_segundos": result.get("tempo_segundos", 0),
        }

    # ─── Fornecedores ──────────────────────────────────────

    async def consultar_fornecedor(
        self,
        cnpj: Optional[str] = None,
        cpf: Optional[str] = None,
    ) -> List[Dict]:
        """
        Consulta dados de fornecedor.
        
        Args:
            cnpj: CNPJ do fornecedor
            cpf: CPF do fornecedor (pessoa física)
        
        Returns:
            Lista de fornecedores normalizados
        """
        result = await cgov.consultar_fornecedor(cnpj=cnpj, cpf=cpf)
        raw = result.get("resultado", [])
        return [cgov.normalizar_fornecedor(r) for r in raw]

    # ─── Contratos ─────────────────────────────────────────

    async def buscar_contratos(
        self,
        codigo_orgao: Optional[str] = None,
        max_pages: int = 20,
        **extra_params,
    ) -> Dict[str, Any]:
        """
        Busca contratos.
        
        Args:
            codigo_orgao: Código do órgão
            max_pages: Máximo de páginas
        
        Returns:
            {"contratos": [...], "total": int}
        """
        result = await cgov.consultar_contratos(
            codigo_orgao=codigo_orgao,
            max_pages=max_pages,
            **extra_params,
        )
        raw = result.get("resultado", [])
        normalizados = [cgov.normalizar_contrato(r) for r in raw]

        return {
            "contratos": normalizados,
            "total": len(normalizados),
            "tempo_segundos": result.get("tempo_segundos", 0),
        }

    # ─── ARP ───────────────────────────────────────────────

    async def buscar_arp(
        self,
        max_pages: int = 20,
        **extra_params,
    ) -> Dict[str, Any]:
        """
        Busca Atas de Registro de Preços.
        
        Returns:
            {"atas": [...], "total": int}
        """
        result = await cgov.consultar_arp(
            max_pages=max_pages,
            **extra_params,
        )
        raw = result.get("resultado", [])
        normalizadas = [cgov.normalizar_arp(r) for r in raw]

        return {
            "atas": normalizadas,
            "total": len(normalizadas),
            "tempo_segundos": result.get("tempo_segundos", 0),
        }

    # ─── Legado ────────────────────────────────────────────

    async def buscar_licitacoes_legado(
        self,
        modalidade: Optional[int] = None,
        uasg: Optional[str] = None,
        max_pages: int = 20,
        **extra_params,
    ) -> Dict[str, Any]:
        """
        Busca licitações do módulo legado (pré-PNCP).
        
        Args:
            modalidade: Código da modalidade (ex: 5 = Pregão Eletrônico)
            uasg: Código da UASG
        
        Returns:
            {"licitacoes": [...], "total": int}
        """
        result = await cgov.consultar_licitacao_legado(
            modalidade=modalidade,
            uasg=uasg,
            max_pages=max_pages,
            **extra_params,
        )
        raw = result.get("resultado", [])
        normalizadas = [cgov.normalizar_licitacao_legado(r) for r in raw]

        return {
            "licitacoes": normalizadas,
            "total": len(normalizadas),
            "tempo_segundos": result.get("tempo_segundos", 0),
        }

    # ─── UASG / Órgãos ────────────────────────────────────

    async def consultar_uasg(
        self,
        codigo_uasg: Optional[str] = None,
    ) -> List[Dict]:
        """Consulta UASGs."""
        result = await cgov.consultar_uasg(codigo_uasg=codigo_uasg)
        return result.get("resultado", [])

    async def consultar_orgao(
        self,
        codigo_orgao: Optional[str] = None,
    ) -> List[Dict]:
        """Consulta órgãos."""
        result = await cgov.consultar_orgao(codigo_orgao=codigo_orgao)
        return result.get("resultado", [])

    # ─── Sincronização incremental ─────────────────────────

    async def sync_incremental(
        self,
        dias_atras: int = 1,
        uf: Optional[str] = None,
        max_pages: int = 10,
    ) -> Dict[str, Any]:
        """
        Job de sincronização incremental com persistência no MongoDB.
        """
        if self.db is not None:
            await self._ensure_indexes()

        hoje = datetime.now().strftime("%Y-%m-%d")
        data_inicial = (datetime.now() - timedelta(days=dias_atras)).strftime("%Y-%m-%d")

        logger.info(f"🔄 [ComprasGov-Sync] Sincronização incremental {data_inicial} → {hoje}")

        contratacoes_totais = []
        
        # Modalidades principais: 5 (Pregão), 6 (Dispensa), 7 (Inexigibilidade), 1 (Leilão), 4 (Concorrência)
        modalidades = [5, 6, 7, 4, 1]
        
        for mod in modalidades:
            logger.info(f"📡 [ComprasGov-Sync] Sincronizando Modalidade {mod}...")
            result = await self.buscar_contratacoes_por_periodo(
                data_inicial=data_inicial,
                data_final=hoje,
                uf=uf,
                max_pages=max_pages // len(modalidades) or 5,
                modalidade=mod
            )
            contratacoes_totais.extend(result.get("normalizadas", []))
            # Pequeno delay para não estressar a API
            await asyncio.sleep(0.5)

        if not contratacoes_totais:
            return {"message": "Nenhuma contratação nova encontrada.", "total": 0}

        # 2. Persistir no MongoDB (Upsert)
        saved_count = 0
        if self.db is not None:
            from pymongo import UpdateOne
            operations = []
            for c in contratacoes_totais:
                # Usar numero_controle_pncp como ID único de negócio
                key = {"numero_controle_pncp": c.get("numero_controle_pncp")}
                if not key["numero_controle_pncp"]:
                    continue
                
                c["last_sync_at"] = datetime.utcnow()
                operations.append(UpdateOne(key, {"$set": c}, upsert=True))
            
            if operations:
                db_result = await self.db.comprasgov_v3.bulk_write(operations)
                saved_count = db_result.upserted_count + db_result.modified_count

        logger.info(
            f"✅ [ComprasGov-Sync] {len(contratacoes_totais)} processadas, "
            f"{saved_count} salvas/atualizadas no DB."
        )

        return {
            "total_processado": len(contratacoes_totais),
            "total_salvo_db": saved_count,
            "periodo": f"{data_inicial} → {hoje}",
            "tempo_segundos": 0, # TODO: Somar tempos das calls
        }


# ─── Singleton ────────────────────────────────────────────
_instance: Optional[ComprasGovService] = None


def get_comprasgov_service(db=None) -> ComprasGovService:
    """Retorna instância singleton do serviço."""
    global _instance
    if _instance is None:
        _instance = ComprasGovService(db=db)
    elif db is not None and _instance.db is None:
        _instance.db = db
    return _instance
