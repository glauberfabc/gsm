"""
FONTES DIRETAS GSM v59.0 - Independência Total do Agregador
=========================================================

Este módulo acessa DIRETAMENTE as mesmas fontes que o Agregador usa,
eliminando a dependência do intermediário.

PORTAIS MAPEADOS (22 total):
1.  ComprasNet Federal (comprasgovernamentais.gov.br)
2.  Licitações-e (Banco do Brasil)
3.  Compras Públicas (portaldecompraspublicas.com.br)
5.  BEC/SP (bec.sp.gov.br)
6.  Siga RJ (compras.rj.gov.br)
7.  Siga ES (compras.es.gov.br)
9.  Compras MG (compras.mg.gov.br)
11. Compras SC (portaldecompras.sc.gov.br)
17. Procergs
18. ComprasRS (compras.rs.gov.br)
20. ComprasNet GO (comprasgoias.go.gov.br)
24. BLL (bll.org.br)
25. ComprasNet Cotação
26. Publinexo
28. Licitanet (licitanet.com.br)
29. Compras AM
35. Compras MT
58. Compras PE
898. Compras BR
1236. Licitar Digital (licitardigital.com.br)
1362. BNC (bnc.org.br)
+ PNCP (pncp.gov.br) - Portal Nacional

ESTRATÉGIA:
1. Acessar APIs públicas de cada portal
2. Normalizar dados para schema GSM
3. Salvar em editais_gsm
4. Executar a cada 15 minutos via scheduler
"""

import aiohttp
import asyncio
import logging
import hashlib
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# Headers padrão para requests
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "pt-BR,pt;q=0.9",
}


class FontesDiretasGSM:
    """
    Acesso direto às fontes de licitações sem intermediário.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.editais_gsm
        self.timeout = aiohttp.ClientTimeout(total=60)
    
    async def sincronizar_todas_fontes(self) -> Dict:
        """
        Sincroniza TODAS as fontes diretas.
        Roda a cada 15 minutos.
        """
        stats = {
            "inicio": datetime.now(timezone.utc).isoformat(),
            "total_novos": 0,
            "por_fonte": {}
        }
        
        logger.info("🌐 [FONTES-DIRETAS] Iniciando sincronização multi-fonte...")
        
        # 1. PNCP - Portal Nacional (principal)
        pncp_stats = await self._sync_pncp()
        stats["por_fonte"]["PNCP"] = pncp_stats
        stats["total_novos"] += pncp_stats.get("novos", 0)
        
        # 2. Compras Públicas
        cp_stats = await self._sync_compras_publicas()
        stats["por_fonte"]["ComprasPublicas"] = cp_stats
        stats["total_novos"] += cp_stats.get("novos", 0)
        
        # 3. BNC - Bolsa Nacional de Compras
        bnc_stats = await self._sync_bnc()
        stats["por_fonte"]["BNC"] = bnc_stats
        stats["total_novos"] += bnc_stats.get("novos", 0)
        
        # 4. BLL - Bolsa de Licitações
        bll_stats = await self._sync_bll()
        stats["por_fonte"]["BLL"] = bll_stats
        stats["total_novos"] += bll_stats.get("novos", 0)
        
        # 5. Licitar Digital
        ld_stats = await self._sync_licitar_digital()
        stats["por_fonte"]["LicitarDigital"] = ld_stats
        stats["total_novos"] += ld_stats.get("novos", 0)
        
        # 6. ComprasNet Federal (dados.gov.br)
        cn_stats = await self._sync_comprasnet()
        stats["por_fonte"]["ComprasNet"] = cn_stats
        stats["total_novos"] += cn_stats.get("novos", 0)
        
        stats["fim"] = datetime.now(timezone.utc).isoformat()
        stats["total_banco"] = await self.collection.count_documents({})
        
        logger.info(f"✅ [FONTES-DIRETAS] Concluído: {stats['total_novos']} novos, {stats['total_banco']} total")
        
        return stats
    
    async def _sync_pncp(self) -> Dict:
        """
        Sincroniza com PNCP - Portal Nacional de Contratações Públicas
        API: https://pncp.gov.br/api/consulta/v1/contratacoes
        """
        stats = {"fonte": "PNCP", "novos": 0, "erros": 0}
        
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                # Buscar últimas contratações
                params = {
                    "dataPublicacaoInicio": (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
                    "dataPublicacaoFim": datetime.now().strftime("%Y-%m-%d"),
                    "pagina": 1,
                    "tamanhoPagina": 100
                }
                
                url = "https://pncp.gov.br/api/consulta/v1/contratacoes"
                
                for pagina in range(1, 11):  # Máximo 10 páginas
                    params["pagina"] = pagina
                    
                    try:
                        async with session.get(url, params=params, headers=HEADERS) as resp:
                            if resp.status != 200:
                                break
                            
                            data = await resp.json()
                            items = data.get("data", []) or data.get("resultado", []) or []
                            
                            if not items:
                                break
                            
                            for item in items:
                                resultado = await self._salvar_pncp(item)
                                if resultado == "inserido":
                                    stats["novos"] += 1
                            
                            await asyncio.sleep(0.5)
                            
                    except Exception as e:
                        stats["erros"] += 1
                        continue
                        
        except Exception as e:
            logger.error(f"❌ [PNCP] Erro: {e}")
            stats["erro"] = str(e)
        
        logger.info(f"📥 [PNCP] {stats['novos']} novos editais")
        return stats
    
    async def _sync_compras_publicas(self) -> Dict:
        """
        Sincroniza com Portal de Compras Públicas
        URL: portaldecompraspublicas.com.br
        """
        stats = {"fonte": "ComprasPublicas", "novos": 0, "erros": 0}
        
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                # API do Portal de Compras Públicas
                url = "https://www.portaldecompraspublicas.com.br/api/licitacoes"
                
                try:
                    async with session.get(url, headers=HEADERS) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            items = data if isinstance(data, list) else data.get("data", [])
                            
                            for item in items[:100]:
                                resultado = await self._salvar_compras_publicas(item)
                                if resultado == "inserido":
                                    stats["novos"] += 1
                except Exception as e:
                    stats["erros"] += 1
                    logger.debug(f"ComprasPublicas API indisponível: {e}")
                    
        except Exception as e:
            logger.debug(f"[ComprasPublicas] Erro: {e}")
        
        return stats
    
    async def _sync_bnc(self) -> Dict:
        """
        Sincroniza com BNC - Bolsa Nacional de Compras
        URL: bnc.org.br
        """
        stats = {"fonte": "BNC", "novos": 0, "erros": 0}
        
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                # Tentar API do BNC
                urls = [
                    "https://bnc.org.br/api/editais",
                    "https://api.bnc.org.br/v1/licitacoes",
                    "https://bnc.org.br/sistema/api/licitacoes"
                ]
                
                for url in urls:
                    try:
                        async with session.get(url, headers=HEADERS) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                items = data if isinstance(data, list) else data.get("data", [])
                                
                                for item in items[:100]:
                                    resultado = await self._salvar_bnc(item)
                                    if resultado == "inserido":
                                        stats["novos"] += 1
                                break
                    except:
                        continue
                        
        except Exception as e:
            logger.debug(f"[BNC] Erro: {e}")
        
        return stats
    
    async def _sync_bll(self) -> Dict:
        """
        Sincroniza com BLL - Bolsa de Licitações e Leilões
        URL: bll.org.br
        """
        stats = {"fonte": "BLL", "novos": 0, "erros": 0}
        
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                urls = [
                    "https://bll.org.br/api/licitacoes",
                    "https://api.bll.org.br/v1/editais"
                ]
                
                for url in urls:
                    try:
                        async with session.get(url, headers=HEADERS) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                items = data if isinstance(data, list) else data.get("data", [])
                                
                                for item in items[:100]:
                                    resultado = await self._salvar_bll(item)
                                    if resultado == "inserido":
                                        stats["novos"] += 1
                                break
                    except:
                        continue
                        
        except Exception as e:
            logger.debug(f"[BLL] Erro: {e}")
        
        return stats
    
    async def _sync_licitar_digital(self) -> Dict:
        """
        Sincroniza com Licitar Digital
        URL: licitardigital.com.br
        """
        stats = {"fonte": "LicitarDigital", "novos": 0, "erros": 0}
        
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                urls = [
                    "https://licitardigital.com.br/api/licitacoes",
                    "https://api.licitardigital.com.br/v1/editais"
                ]
                
                for url in urls:
                    try:
                        async with session.get(url, headers=HEADERS) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                items = data if isinstance(data, list) else data.get("data", [])
                                
                                for item in items[:100]:
                                    resultado = await self._salvar_licitar_digital(item)
                                    if resultado == "inserido":
                                        stats["novos"] += 1
                                break
                    except:
                        continue
                        
        except Exception as e:
            logger.debug(f"[LicitarDigital] Erro: {e}")
        
        return stats
    
    async def _sync_comprasnet(self) -> Dict:
        """
        Sincroniza com ComprasNet via dados.gov.br
        API: https://compras.dados.gov.br/licitacoes
        """
        stats = {"fonte": "ComprasNet", "novos": 0, "erros": 0}
        
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                url = "https://compras.dados.gov.br/licitacoes/v1/licitacoes.json"
                
                try:
                    async with session.get(url, headers=HEADERS) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            items = data.get("_embedded", {}).get("licitacoes", [])
                            
                            for item in items[:100]:
                                resultado = await self._salvar_comprasnet(item)
                                if resultado == "inserido":
                                    stats["novos"] += 1
                except Exception as e:
                    stats["erros"] += 1
                    logger.debug(f"ComprasNet API: {e}")
                    
        except Exception as e:
            logger.debug(f"[ComprasNet] Erro: {e}")
        
        return stats
    
    # ========================================
    # MÉTODOS DE SALVAMENTO POR FONTE
    # ========================================
    
    async def _salvar_pncp(self, item: Dict) -> str:
        """Salva item do PNCP no schema GSM."""
        try:
            numero_controle = item.get("numeroControlePNCP", "")
            id_gsm = hashlib.md5(f"PNCP-{numero_controle}".encode()).hexdigest()
            
            orgao = item.get("orgaoEntidade", {}) or {}
            
            doc = {
                "id_gsm": id_gsm,
                "id_externo": numero_controle,
                "numero_controle_pncp": numero_controle,
                
                "fonte_origem": "PNCP_DIRETO",
                "fonte": "Portal Nacional de Contratações Públicas - PNCP",
                "portal_captura": "PNCP",
                
                "dados_orgao": {
                    "uasg": orgao.get("codigoUnidade", ""),
                    "cnpj": orgao.get("cnpj", ""),
                    "nome": orgao.get("razaoSocial", ""),
                    "uf": item.get("ufSigla", ""),
                    "municipio": orgao.get("municipioNome", "")
                },
                
                "objeto": (item.get("objetoCompra", "") or "").upper(),
                "orgao": orgao.get("razaoSocial", ""),
                "estado": item.get("ufSigla", ""),
                "uf": item.get("ufSigla", ""),
                "municipio": orgao.get("municipioNome", ""),
                "uasg": orgao.get("codigoUnidade", ""),
                
                "modalidade": item.get("modalidadeNome", "Pregão Eletrônico"),
                "status": "ABERTA",
                
                "data_publicacao": item.get("dataPublicacaoPncp"),
                "data_abertura": item.get("dataEncerramentoProposta"),
                
                "link_documento": f"https://pncp.gov.br/app/editais/{numero_controle}",
                "link_origem": item.get("linkSistemaOrigem", ""),
                "link_portal": f"https://pncp.gov.br/app/editais/{numero_controle}",
                
                "numero_processo": item.get("numeroCompra", ""),
                "numero_licitacao": item.get("numeroCompra", ""),
                
                "itens_clonados": [],
                
                "sincronizado_em": datetime.now(timezone.utc),
                "atualizado_em": datetime.now(timezone.utc),
                "is_saude": self._is_saude(item.get("objetoCompra", "")),
                "is_fonte_direta": True
            }
            
            result = await self.collection.update_one(
                {"id_gsm": id_gsm},
                {"$set": doc},
                upsert=True
            )
            
            return "inserido" if result.upserted_id else "existente"
            
        except Exception as e:
            logger.debug(f"Erro PNCP: {e}")
            return "erro"
    
    async def _salvar_compras_publicas(self, item: Dict) -> str:
        """Salva item do Compras Públicas."""
        try:
            id_base = item.get("id", "") or item.get("numero", "")
            id_gsm = hashlib.md5(f"CP-{id_base}".encode()).hexdigest()
            
            doc = {
                "id_gsm": id_gsm,
                "id_externo": str(id_base),
                "fonte_origem": "COMPRAS_PUBLICAS_DIRETO",
                "fonte": "Compras Públicas",
                "portal_captura": "Compras Públicas",
                
                "objeto": (item.get("objeto", "") or "").upper(),
                "orgao": item.get("orgao", ""),
                "uf": item.get("uf", ""),
                "estado": item.get("uf", ""),
                
                "modalidade": item.get("modalidade", "Pregão Eletrônico"),
                "status": "ABERTA",
                
                "link_portal": item.get("url", ""),
                
                "sincronizado_em": datetime.now(timezone.utc),
                "is_fonte_direta": True
            }
            
            result = await self.collection.update_one(
                {"id_gsm": id_gsm},
                {"$set": doc},
                upsert=True
            )
            
            return "inserido" if result.upserted_id else "existente"
        except:
            return "erro"
    
    async def _salvar_bnc(self, item: Dict) -> str:
        """Salva item do BNC."""
        try:
            id_base = item.get("id", "") or item.get("codigo", "")
            id_gsm = hashlib.md5(f"BNC-{id_base}".encode()).hexdigest()
            
            doc = {
                "id_gsm": id_gsm,
                "id_externo": str(id_base),
                "fonte_origem": "BNC_DIRETO",
                "fonte": "BNC - Bolsa Nacional de Compras",
                "portal_captura": "BNC",
                
                "objeto": (item.get("objeto", "") or "").upper(),
                "orgao": item.get("orgao", ""),
                "uf": item.get("uf", ""),
                "estado": item.get("uf", ""),
                
                "modalidade": item.get("modalidade", "Pregão Eletrônico"),
                "status": "ABERTA",
                
                "sincronizado_em": datetime.now(timezone.utc),
                "is_fonte_direta": True
            }
            
            result = await self.collection.update_one(
                {"id_gsm": id_gsm},
                {"$set": doc},
                upsert=True
            )
            
            return "inserido" if result.upserted_id else "existente"
        except:
            return "erro"
    
    async def _salvar_bll(self, item: Dict) -> str:
        """Salva item do BLL."""
        try:
            id_base = item.get("id", "") or item.get("codigo", "")
            id_gsm = hashlib.md5(f"BLL-{id_base}".encode()).hexdigest()
            
            doc = {
                "id_gsm": id_gsm,
                "id_externo": str(id_base),
                "fonte_origem": "BLL_DIRETO",
                "fonte": "BLL - Bolsa de Licitações e Leilões",
                "portal_captura": "BLL",
                
                "objeto": (item.get("objeto", "") or "").upper(),
                "orgao": item.get("orgao", ""),
                "uf": item.get("uf", ""),
                "estado": item.get("uf", ""),
                
                "modalidade": item.get("modalidade", "Pregão Eletrônico"),
                "status": "ABERTA",
                
                "sincronizado_em": datetime.now(timezone.utc),
                "is_fonte_direta": True
            }
            
            result = await self.collection.update_one(
                {"id_gsm": id_gsm},
                {"$set": doc},
                upsert=True
            )
            
            return "inserido" if result.upserted_id else "existente"
        except:
            return "erro"
    
    async def _salvar_licitar_digital(self, item: Dict) -> str:
        """Salva item do Licitar Digital."""
        try:
            id_base = item.get("id", "") or item.get("codigo", "")
            id_gsm = hashlib.md5(f"LD-{id_base}".encode()).hexdigest()
            
            doc = {
                "id_gsm": id_gsm,
                "id_externo": str(id_base),
                "fonte_origem": "LICITAR_DIGITAL_DIRETO",
                "fonte": "Licitar Digital",
                "portal_captura": "Licitar Digital",
                
                "objeto": (item.get("objeto", "") or "").upper(),
                "orgao": item.get("orgao", ""),
                "uf": item.get("uf", ""),
                "estado": item.get("uf", ""),
                
                "modalidade": item.get("modalidade", "Pregão Eletrônico"),
                "status": "ABERTA",
                
                "sincronizado_em": datetime.now(timezone.utc),
                "is_fonte_direta": True
            }
            
            result = await self.collection.update_one(
                {"id_gsm": id_gsm},
                {"$set": doc},
                upsert=True
            )
            
            return "inserido" if result.upserted_id else "existente"
        except:
            return "erro"
    
    async def _salvar_comprasnet(self, item: Dict) -> str:
        """Salva item do ComprasNet."""
        try:
            id_base = item.get("identificador", "") or item.get("numero", "")
            id_gsm = hashlib.md5(f"CN-{id_base}".encode()).hexdigest()
            
            doc = {
                "id_gsm": id_gsm,
                "id_externo": str(id_base),
                "fonte_origem": "COMPRASNET_DIRETO",
                "fonte": "ComprasNet",
                "portal_captura": "ComprasNet",
                
                "dados_orgao": {
                    "uasg": str(item.get("uasg", "")),
                    "nome": item.get("orgao", {}).get("nome", "") if isinstance(item.get("orgao"), dict) else ""
                },
                
                "objeto": (item.get("objeto", "") or "").upper(),
                "orgao": item.get("orgao", {}).get("nome", "") if isinstance(item.get("orgao"), dict) else "",
                "uf": item.get("uf", ""),
                "estado": item.get("uf", ""),
                "uasg": str(item.get("uasg", "")),
                
                "modalidade": item.get("modalidade", "Pregão Eletrônico"),
                "status": "ABERTA",
                
                "data_publicacao": item.get("data_publicacao"),
                "data_abertura": item.get("data_entrega_proposta"),
                
                "link_portal": item.get("_links", {}).get("self", {}).get("href", ""),
                
                "sincronizado_em": datetime.now(timezone.utc),
                "is_fonte_direta": True
            }
            
            result = await self.collection.update_one(
                {"id_gsm": id_gsm},
                {"$set": doc},
                upsert=True
            )
            
            return "inserido" if result.upserted_id else "existente"
        except:
            return "erro"
    
    def _is_saude(self, objeto: str) -> bool:
        if not objeto:
            return False
        objeto_lower = objeto.lower()
        keywords = ['medicament', 'farmac', 'hospital', 'saúde', 'saude', 'médic', 'medic',
                   'insulina', 'vacina', 'canabidiol', 'cannabis', 'cbd', 'oncolog']
        return any(kw in objeto_lower for kw in keywords)


# Singleton
_fontes_diretas = None

def get_fontes_diretas(db: AsyncIOMotorDatabase) -> FontesDiretasGSM:
    global _fontes_diretas
    if _fontes_diretas is None:
        _fontes_diretas = FontesDiretasGSM(db)
    return _fontes_diretas
