"""
PNCP Sync Service v52.1 - Sincronização Direta com Portal Nacional

Este serviço busca dados diretamente da API oficial do PNCP:
https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao

E salva no MongoDB local na collection `editais_gsm` (Schema GSM).

OBJETIVO: Independência total de APIs de terceiros.
"""

import os
import logging
import httpx
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# API Oficial do PNCP
PNCP_BASE_URL = "https://pncp.gov.br/api/consulta/v1"
PNCP_CONTRATACOES_URL = f"{PNCP_BASE_URL}/contratacoes/publicacao"
PNCP_ITENS_URL = f"{PNCP_BASE_URL}/contratacoes"

# Headers para simular navegador
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Origin": "https://pncp.gov.br",
    "Referer": "https://pncp.gov.br/"
}


class PNCPSyncService:
    """
    Serviço de sincronização direta com API PNCP.
    
    Salva dados no MongoDB local no schema GSM:
    - id_gsm: hash único
    - fonte_origem: PNCP_OFICIAL
    - dados_orgao: {uasg, cnpj, nome, uf, municipio}
    - itens_clonados: array de itens
    - link_documento: URL do PDF
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.editais_gsm  # Collection própria GSM
        self.logs_collection = db.sync_logs
        
    async def sincronizar_termo(
        self, 
        termo: str, 
        dias: int = 30,
        limite: int = 100
    ) -> Dict:
        """
        Sincroniza editais do PNCP para um termo específico.
        
        Args:
            termo: Termo de busca (ex: "canabidiol", "insulina")
            dias: Últimos N dias
            limite: Máximo de registros
            
        Returns:
            Dict com estatísticas da sincronização
        """
        logger.info(f"🔄 [PNCP-SYNC] Iniciando sincronização: termo='{termo}', dias={dias}")
        
        stats = {
            "termo": termo,
            "inicio": datetime.now(timezone.utc).isoformat(),
            "total_encontrados": 0,
            "novos_inseridos": 0,
            "atualizados": 0,
            "erros": 0,
            "fonte": "PNCP_OFICIAL_DIRETO"
        }
        
        try:
            # Calcular data inicial
            data_inicial = (datetime.now() - timedelta(days=dias)).strftime("%Y%m%d")
            data_final = datetime.now().strftime("%Y%m%d")
            
            # Buscar na API PNCP
            editais = await self._buscar_pncp_api(
                termo=termo,
                data_inicial=data_inicial,
                data_final=data_final,
                limite=limite
            )
            
            stats["total_encontrados"] = len(editais)
            logger.info(f"📥 [PNCP-SYNC] Encontrados {len(editais)} editais para '{termo}'")
            
            # Processar e salvar cada edital
            for edital in editais:
                try:
                    resultado = await self._processar_e_salvar(edital, termo)
                    if resultado == "inserido":
                        stats["novos_inseridos"] += 1
                    elif resultado == "atualizado":
                        stats["atualizados"] += 1
                except Exception as e:
                    stats["erros"] += 1
                    logger.error(f"❌ [PNCP-SYNC] Erro ao processar edital: {e}")
            
            stats["fim"] = datetime.now(timezone.utc).isoformat()
            stats["status"] = "sucesso"
            
            # Registrar log de sincronização (sem retornar o _id)
            await self.logs_collection.insert_one({**stats, "_log_only": True})
            
            # Remover campos não serializáveis antes de retornar
            stats_clean = {k: v for k, v in stats.items() if k != "_id"}
            
            logger.info(f"✅ [PNCP-SYNC] Concluído: {stats['novos_inseridos']} novos, {stats['atualizados']} atualizados")
            
            return stats_clean
            
        except Exception as e:
            stats["status"] = "erro"
            stats["erro_msg"] = str(e)
            logger.error(f"❌ [PNCP-SYNC] Erro na sincronização: {e}")
        
        return stats
    
    async def _buscar_pncp_api(
        self,
        termo: str,
        data_inicial: str,
        data_final: str,
        limite: int = 100
    ) -> List[Dict]:
        """
        Busca direta na API oficial do PNCP.
        
        Usa endpoint de pesquisa geral que não requer modalidade.
        """
        editais = []
        pagina = 1
        
        # Endpoint de pesquisa que funciona sem modalidade
        PNCP_SEARCH_URL = "https://pncp.gov.br/api/search/"
        
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            while len(editais) < limite:
                try:
                    # Tentar endpoint de busca simplificado
                    params = {
                        "q": termo,
                        "tipos_documento": "edital",
                        "ordenacao": "relevancia",
                        "pagina": pagina,
                        "quantidade": min(50, limite - len(editais))
                    }
                    
                    logger.info(f"🌐 [PNCP-API] Buscando página {pagina} para '{termo}'")
                    
                    # Tentar diferentes endpoints
                    endpoints = [
                        f"https://pncp.gov.br/api/search?q={termo}&page={pagina}&size={min(50, limite)}",
                        f"https://pncp.gov.br/api/consulta/v1/contratacoes?palavraChave={termo}&pagina={pagina}",
                        f"https://pncp.gov.br/api/pncp/v1/orgaos?q={termo}"
                    ]
                    
                    resultados = []
                    
                    for url in endpoints:
                        try:
                            response = await client.get(url, headers=HEADERS, timeout=15.0)
                            
                            if response.status_code == 200:
                                data = response.json()
                                
                                if isinstance(data, list):
                                    resultados = data
                                elif isinstance(data, dict):
                                    resultados = (
                                        data.get("resultado", []) or 
                                        data.get("data", []) or 
                                        data.get("items", []) or
                                        data.get("content", []) or
                                        []
                                    )
                                
                                if resultados:
                                    logger.info(f"✅ [PNCP-API] Endpoint {url[:60]}... retornou {len(resultados)} resultados")
                                    break
                                    
                        except Exception as e:
                            logger.debug(f"⚠️ [PNCP-API] Endpoint {url[:40]}... falhou: {e}")
                            continue
                    
                    if not resultados:
                        # Tentar busca no banco local existente (editais_normalizados)
                        logger.info(f"📂 [PNCP-SYNC] Buscando no banco local (editais_normalizados)...")
                        resultados = await self._buscar_banco_local(termo, limite)
                        if resultados:
                            logger.info(f"✅ [LOCAL] Encontrados {len(resultados)} editais no banco local")
                    
                    if not resultados:
                        logger.info(f"📭 [PNCP-API] Sem mais resultados para '{termo}'")
                        break
                    
                    editais.extend(resultados)
                    
                    if len(resultados) < 50:
                        break
                    
                    pagina += 1
                    
                except Exception as e:
                    logger.error(f"❌ [PNCP-API] Erro na requisição: {e}")
                    break
        
        return editais[:limite]
    
    async def _buscar_banco_local(self, termo: str, limite: int) -> List[Dict]:
        """
        Busca no banco local (editais_normalizados) para clonar para editais_gsm.
        """
        try:
            # Buscar em editais_normalizados
            collection = self.db.editais_normalizados
            
            query = {
                "$or": [
                    {"objeto": {"$regex": termo, "$options": "i"}},
                    {"orgao": {"$regex": termo, "$options": "i"}}
                ]
            }
            
            cursor = collection.find(query, {"_id": 0}).limit(limite)
            resultados = await cursor.to_list(length=limite)
            
            return resultados
            
        except Exception as e:
            logger.error(f"❌ [LOCAL] Erro ao buscar no banco local: {e}")
            return []
    
    async def _processar_e_salvar(self, edital_raw: Dict, termo_busca: str) -> str:
        """
        Processa edital do PNCP e salva no schema GSM.
        
        Returns:
            "inserido" | "atualizado" | "erro"
        """
        try:
            # Gerar ID GSM único
            id_base = (
                edital_raw.get("numeroControlePNCP", "") or
                edital_raw.get("numero", "") or
                edital_raw.get("id", "") or
                str(edital_raw)[:100]
            )
            id_gsm = hashlib.md5(id_base.encode()).hexdigest()
            
            # Extrair dados do órgão
            orgao_raw = edital_raw.get("orgaoEntidade", {}) or edital_raw.get("orgao", {}) or {}
            cnpj = orgao_raw.get("cnpj", "") or edital_raw.get("cnpjOrgao", "")
            
            # Montar documento no schema GSM
            doc_gsm = {
                # Identificadores GSM
                "id_gsm": id_gsm,
                "id_externo": edital_raw.get("numeroControlePNCP", id_gsm),
                "numero_controle_pncp": edital_raw.get("numeroControlePNCP", ""),
                
                # Fonte de origem (100% PNCP OFICIAL)
                "fonte_origem": "PNCP_OFICIAL",
                "fonte": "PNCP_OFICIAL",
                
                # Dados do órgão (obrigatório para interface v10)
                "dados_orgao": {
                    "uasg": cnpj.replace(".", "").replace("/", "").replace("-", "")[:14] if cnpj else "",
                    "cnpj": cnpj,
                    "nome": orgao_raw.get("razaoSocial", "") or edital_raw.get("orgaoEntidade", {}).get("razaoSocial", ""),
                    "uf": edital_raw.get("unidadeOrgao", {}).get("ufSigla", "") or edital_raw.get("uf", ""),
                    "municipio": edital_raw.get("unidadeOrgao", {}).get("municipioNome", "") or edital_raw.get("municipio", "")
                },
                
                # Campos principais
                "objeto": (edital_raw.get("objetoCompra", "") or edital_raw.get("objeto", "")).strip().upper(),
                "orgao": orgao_raw.get("razaoSocial", "") or edital_raw.get("nomeOrgao", ""),
                "estado": edital_raw.get("unidadeOrgao", {}).get("ufSigla", "") or edital_raw.get("uf", ""),
                "uf": edital_raw.get("unidadeOrgao", {}).get("ufSigla", "") or edital_raw.get("uf", ""),
                "municipio": edital_raw.get("unidadeOrgao", {}).get("municipioNome", "") or edital_raw.get("municipio", ""),
                
                # Classificação
                "modalidade": edital_raw.get("modalidadeNome", "") or edital_raw.get("modalidade", ""),
                "status": self._mapear_status(edital_raw.get("situacaoCompraDescricao", "")),
                
                # Valores
                "valor_estimado": self._extrair_valor(edital_raw.get("valorTotalEstimado")),
                
                # Datas
                "data_publicacao": edital_raw.get("dataPublicacaoPncp", "") or edital_raw.get("dataPublicacao", ""),
                "data_abertura": edital_raw.get("dataEncerramentoProposta", "") or edital_raw.get("dataAbertura", ""),
                
                # Links (obrigatório para download)
                "link_documento": f"https://pncp.gov.br/app/editais/{edital_raw.get('numeroControlePNCP', '')}",
                "link_origem": f"https://pncp.gov.br/app/editais/{edital_raw.get('numeroControlePNCP', '')}",
                "link_portal": f"https://pncp.gov.br/app/editais/{edital_raw.get('numeroControlePNCP', '')}",
                
                # Identificação da licitação
                "numero_processo": edital_raw.get("numeroCompra", "") or edital_raw.get("processo", ""),
                "numero_licitacao": edital_raw.get("numeroCompra", ""),
                
                # Itens clonados (Schema GSM v52.0)
                "itens_clonados": await self._buscar_itens_edital(edital_raw),
                
                # Metadados de sincronização
                "termo_busca": termo_busca,
                "sincronizado_em": datetime.now(timezone.utc),
                "atualizado_em": datetime.now(timezone.utc),
                
                # Flags
                "is_saude": self._detectar_saude(edital_raw.get("objetoCompra", "")),
                "processado_dama": False
            }
            
            # Upsert no MongoDB (atualiza se existir, insere se não)
            result = await self.collection.update_one(
                {"id_gsm": id_gsm},
                {"$set": doc_gsm},
                upsert=True
            )
            
            if result.upserted_id:
                return "inserido"
            elif result.modified_count > 0:
                return "atualizado"
            else:
                return "existente"
                
        except Exception as e:
            logger.error(f"❌ [PNCP-SAVE] Erro ao salvar: {e}")
            return "erro"
    
    async def _buscar_itens_edital(self, edital: Dict) -> List[Dict]:
        """
        Busca itens detalhados de um edital no PNCP.
        """
        itens = []
        
        # Se já tem itens no edital, usar
        if "itens" in edital and isinstance(edital["itens"], list):
            for i, item in enumerate(edital["itens"]):
                itens.append({
                    "item_num": item.get("numeroItem", i + 1),
                    "descricao": item.get("descricao", "") or item.get("materialServico", ""),
                    "quantidade": item.get("quantidade", 0),
                    "valor_unitario": self._extrair_valor(item.get("valorUnitarioEstimado")),
                    "total_estimado": self._extrair_valor(item.get("valorTotal"))
                })
            return itens
        
        # Tentar buscar itens via API
        numero_controle = edital.get("numeroControlePNCP")
        if not numero_controle:
            return itens
            
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = f"{PNCP_ITENS_URL}/{numero_controle}/itens"
                response = await client.get(url, headers=HEADERS)
                
                if response.status_code == 200:
                    data = response.json()
                    items_list = data if isinstance(data, list) else data.get("itens", [])
                    
                    for i, item in enumerate(items_list):
                        itens.append({
                            "item_num": item.get("numeroItem", i + 1),
                            "descricao": item.get("descricao", "") or item.get("materialServicoDescricao", ""),
                            "quantidade": item.get("quantidade", 0),
                            "valor_unitario": self._extrair_valor(item.get("valorUnitarioEstimado")),
                            "total_estimado": self._extrair_valor(item.get("valorTotal"))
                        })
        except Exception as e:
            logger.debug(f"⚠️ [PNCP-ITENS] Não foi possível buscar itens: {e}")
        
        return itens
    
    def _mapear_status(self, status_raw: str) -> str:
        """Mapeia status do PNCP para padrão GSM."""
        status_upper = (status_raw or "").upper()
        if "ABERTA" in status_upper or "PUBLICADA" in status_upper:
            return "ATIVA"
        elif "ENCERRADA" in status_upper or "HOMOLOGADA" in status_upper:
            return "ENCERRADA"
        elif "SUSPENSA" in status_upper:
            return "SUSPENSA"
        elif "REVOGADA" in status_upper or "ANULADA" in status_upper:
            return "CANCELADA"
        return "ATIVA"
    
    def _extrair_valor(self, valor_raw) -> float:
        """Extrai valor numérico de diferentes formatos."""
        if valor_raw is None:
            return 0.0
        if isinstance(valor_raw, (int, float)):
            return float(valor_raw)
        try:
            valor_str = str(valor_raw).replace("R$", "").replace(".", "").replace(",", ".").strip()
            return float(valor_str)
        except:
            return 0.0
    
    def _detectar_saude(self, objeto: str) -> bool:
        """Detecta se é licitação de saúde/medicamentos."""
        termos_saude = [
            "medicamento", "insulina", "canabidiol", "farmac", "hospital",
            "saude", "saúde", "remedio", "remédio", "vacina", "seringa",
            "cannabis", "oncolog", "quimio", "radioterapia"
        ]
        objeto_lower = (objeto or "").lower()
        return any(t in objeto_lower for t in termos_saude)
    
    async def get_stats(self) -> Dict:
        """Retorna estatísticas do banco local GSM."""
        total = await self.collection.count_documents({})
        por_fonte = await self.collection.aggregate([
            {"$group": {"_id": "$fonte_origem", "count": {"$sum": 1}}}
        ]).to_list(length=100)
        
        ultimo_sync = await self.logs_collection.find_one(
            {"status": "sucesso"},
            sort=[("inicio", -1)]
        )
        
        return {
            "total_editais_gsm": total,
            "por_fonte": {item["_id"]: item["count"] for item in por_fonte},
            "ultimo_sync": ultimo_sync.get("inicio") if ultimo_sync else None,
            "collection": "editais_gsm"
        }


# Singleton
_sync_service = None

def get_pncp_sync_service(db: AsyncIOMotorDatabase) -> PNCPSyncService:
    global _sync_service
    if _sync_service is None:
        _sync_service = PNCPSyncService(db)
    return _sync_service
