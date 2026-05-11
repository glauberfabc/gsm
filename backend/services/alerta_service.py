"""
Alerta Service - P5

Serviço para gerenciamento de alertas e envio de notificações.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import uuid4
from motor.motor_asyncio import AsyncIOMotorDatabase

from models.alerta import AlertaCreate, AlertaUpdate, FrequenciaAlerta
from services.email_service import get_email_service
from services.busca_service_v2 import get_busca_service_v2

logger = logging.getLogger(__name__)


class AlertaService:
    """
    Serviço para gerenciamento de alertas de licitações.
    
    Responsabilidades:
    - CRUD de alertas
    - Processamento de alertas (busca + envio)
    - Controle de duplicados
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.alertas = db.alertas
        self.email_service = get_email_service()
    
    async def criar_alerta(self, alerta: AlertaCreate) -> Dict:
        """
        Cria um novo alerta.
        """
        alerta_doc = {
            "id": str(uuid4()),
            "email": alerta.email,
            "termo": alerta.termo.lower().strip(),
            "frequencia": alerta.frequencia.value,
            "ativo": True,
            "filtros": alerta.filtros.dict() if alerta.filtros else {},
            "ultimo_envio": None,
            "editais_enviados": [],
            "total_enviados": 0,
            "created_at": datetime.now(timezone.utc),
            "updated_at": None
        }
        
        await self.alertas.insert_one(alerta_doc)
        
        logger.info(f"✅ [ALERTA] Criado: '{alerta.termo}' para {alerta.email}")
        
        return {
            "id": alerta_doc["id"],
            "email": alerta_doc["email"],
            "termo": alerta_doc["termo"],
            "frequencia": alerta_doc["frequencia"],
            "ativo": alerta_doc["ativo"],
            "created_at": alerta_doc["created_at"].isoformat()
        }
    
    async def listar_alertas(self, email: Optional[str] = None) -> List[Dict]:
        """
        Lista alertas, opcionalmente filtrados por email.
        """
        query = {}
        if email:
            query["email"] = email
        
        cursor = self.alertas.find(query, {"_id": 0})
        alertas = await cursor.to_list(1000)
        
        return [
            {
                "id": a["id"],
                "email": a["email"],
                "termo": a["termo"],
                "frequencia": a["frequencia"],
                "ativo": a["ativo"],
                "filtros": a.get("filtros", {}),
                "ultimo_envio": a["ultimo_envio"].isoformat() if a.get("ultimo_envio") else None,
                "total_enviados": a.get("total_enviados", 0),
                "created_at": a["created_at"].isoformat() if a.get("created_at") else None
            }
            for a in alertas
        ]
    
    async def obter_alerta(self, alerta_id: str) -> Optional[Dict]:
        """
        Obtém um alerta pelo ID.
        """
        alerta = await self.alertas.find_one({"id": alerta_id}, {"_id": 0})
        return alerta
    
    async def atualizar_alerta(self, alerta_id: str, update: AlertaUpdate) -> Optional[Dict]:
        """
        Atualiza um alerta existente.
        """
        update_data = {k: v for k, v in update.dict().items() if v is not None}
        
        if "frequencia" in update_data:
            update_data["frequencia"] = update_data["frequencia"].value
        
        if "filtros" in update_data and update_data["filtros"]:
            update_data["filtros"] = update_data["filtros"].dict()
        
        update_data["updated_at"] = datetime.now(timezone.utc)
        
        result = await self.alertas.update_one(
            {"id": alerta_id},
            {"$set": update_data}
        )
        
        if result.modified_count > 0:
            return await self.obter_alerta(alerta_id)
        return None
    
    async def deletar_alerta(self, alerta_id: str) -> bool:
        """
        Remove um alerta.
        """
        result = await self.alertas.delete_one({"id": alerta_id})
        return result.deleted_count > 0
    
    async def processar_alerta(self, alerta_id: str) -> Dict:
        """
        Processa um alerta específico:
        1. Busca novas oportunidades (P0→P1→P2→P3)
        2. Filtra duplicados já enviados
        3. Envia email se houver novidades
        4. Atualiza registro
        
        Returns:
            Dict com resultado do processamento
        """
        alerta = await self.obter_alerta(alerta_id)
        if not alerta:
            return {"status": "error", "message": "Alerta não encontrado"}
        
        if not alerta.get("ativo", False):
            return {"status": "skip", "message": "Alerta inativo"}
        
        termo = alerta["termo"]
        email = alerta["email"]
        filtros = alerta.get("filtros", {})
        editais_ja_enviados = set(alerta.get("editais_enviados", []))
        
        # Buscar oportunidades usando o pipeline completo (P0→P1→P2→P3)
        busca_service = get_busca_service_v2(self.db)
        
        resultado = await busca_service.buscar(
            termo_busca=termo,
            estados=filtros.get("estados"),
            esfera=filtros.get("esfera"),
            apenas_saude=filtros.get("apenas_saude", True),
            incluir_ativas=True,
            incluir_futuras=False,  # Apenas ATIVAS
            incluir_encerradas=False,
            excluir_credenciamentos=filtros.get("excluir_credenciamentos", False),
            limite_quality_score=70,  # Regra obrigatória: >= 70
            limit=50
        )
        
        editais = resultado.get("resultados", [])
        
        # =====================================================================
        # 🔒 FILTRO RIGOROSO (PADRÃO GSM) - SEM EXCEÇÕES
        # =====================================================================
        # REGRA: Somente editais com linkSistemaOrigem funcional
        # Links PNCP SPA, genéricos ou que exijam navegação manual são EXCLUÍDOS
        # Preferir 2 editais funcionais do que 39 problemáticos
        editais_funcionais = self._filtrar_links_funcionais_rigoroso(editais)
        
        logger.info(f"🔒 [ALERTA] Filtro rigoroso: {len(editais)} → {len(editais_funcionais)} com link funcional")
        
        # Filtrar duplicados (nunca reenviar)
        editais_novos = []
        for edital in editais_funcionais:
            edital_id = edital.get("id_externo") or edital.get("id") or edital.get("numero_processo")
            if edital_id and edital_id not in editais_ja_enviados:
                editais_novos.append(edital)
        
        if not editais_novos:
            logger.info(f"📭 [ALERTA] '{termo}': Nenhuma oportunidade nova")
            return {
                "status": "no_new",
                "message": "Nenhuma oportunidade nova",
                "termo": termo,
                "total_encontrados": len(editais),
                "total_novos": 0
            }
        
        # Enviar email
        envio = await self.email_service.enviar_alerta(email, termo, editais_novos)
        
        if envio["status"] == "success":
            # Atualizar registro
            novos_ids = [
                e.get("id_externo") or e.get("id") or e.get("numero_processo")
                for e in editais_novos
            ]
            
            await self.alertas.update_one(
                {"id": alerta_id},
                {
                    "$set": {
                        "ultimo_envio": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc)
                    },
                    "$push": {
                        "editais_enviados": {"$each": novos_ids}
                    },
                    "$inc": {
                        "total_enviados": len(editais_novos)
                    }
                }
            )
            
            logger.info(f"✅ [ALERTA] '{termo}': {len(editais_novos)} editais enviados para {email}")
        
        return {
            "status": envio["status"],
            "message": envio.get("message"),
            "termo": termo,
            "email": email,
            "total_encontrados": len(editais),
            "total_novos": len(editais_novos),
            "email_id": envio.get("email_id")
        }
    
    def _filtrar_links_funcionais_rigoroso(self, editais: List[Dict]) -> List[Dict]:
        """
        🔒 FILTRO RIGOROSO (PADRÃO GSM) - SEM EXCEÇÕES
        
        REGRA ABSOLUTA:
        - Somente editais com link_sistema_origem funcional são aceitos
        - Link deve permitir acesso DIRETO ao portal do órgão e documentos
        - PNCP SPA, links genéricos ou que exijam navegação são EXCLUÍDOS
        
        ACEITOS (link funcional direto):
        - ComprasNet (cnetmobile.estaleiro.serpro.gov.br)
        - Licitações-e Banco do Brasil (licitacoes-e.com.br, licitacoes-e2.bb.com.br)
        - Portal de Compras Públicas (portaldecompraspublicas.com.br)
        - BLL (bll.org.br)
        - BBMNet (bbmnetlicitacoes.com.br)
        - Pregão Banrisul (pregaobanrisul.com.br)
        - Licitar Digital (licitardigital.com.br)
        - Links diretos para PDF
        
        EXCLUÍDOS (sem exceções):
        - PNCP SPA (/app/editais/, pncp.gov.br)
        - Portais estaduais genéricos (compras.XX.gov.br)
        - Links de datasets
        - Qualquer link que exija navegação manual
        """
        # =====================================================================
        # 🚫 LISTA DE BLOQUEIO EXPLÍCITA (VERIFICADA PRIMEIRO)
        # Links que NUNCA são aceitos, independente de qualquer outra regra
        # 🆕 v4.5: Exceção para links de arquivos PNCP (/pncp-api/.../arquivos/)
        # =====================================================================
        links_bloqueados = [
            '/app/editais',          # PNCP SPA específico
            '/app/pncp',             # PNCP SPA variante
            'dados.gov.br',          # Portal de dados abertos
            'compras.dados.gov.br',  # Portal de dados de compras
        ]
        
        # 🆕 v4.5: Links de arquivos PNCP são ACEITOS (download direto)
        links_pncp_funcionais = [
            '/pncp-api/v1/orgaos/',  # API de arquivos PNCP (download direto)
            '/arquivos/',             # Padrão de arquivos
        ]
        
        # =====================================================================
        # ✅ LISTA DE APROVAÇÃO (LINKS FUNCIONAIS VERIFICADOS)
        # Apenas estes padrões são aceitos como link funcional
        # =====================================================================
        links_funcionais = [
            'cnetmobile.estaleiro.serpro.gov.br',  # ComprasNet Mobile
            'comprasnet-web/public/landing',       # ComprasNet Web
            'licitacoes-e.com.br',                 # Licitações-e BB
            'licitacoes-e2.bb.com.br',             # Licitações-e2 BB
            'portaldecompraspublicas.com.br',      # Portal de Compras Públicas
            'bll.org.br',                          # BLL
            'bbmnetlicitacoes.com.br',             # BBMNet
            'pregaobanrisul.com.br',               # Pregão Banrisul
            'licitardigital.com.br',               # Licitar Digital
            'licitanet.com.br',                    # Licitanet
            'compras.fortaleza.ce.gov.br',         # Compras Fortaleza
            'bnccompras.com',                      # BNC
            '.pdf',                                # PDF direto
            '.zip',                                # ZIP direto
            '/pncp-api/v1/orgaos/',                # 🆕 v4.5: Arquivos PNCP
        ]
        
        editais_filtrados = []
        
        for edital in editais:
            # ÚNICA FONTE ACEITA: link_sistema_origem
            link_sistema = edital.get('link_sistema_origem', '') or ''
            
            # Também verificar link_edital como fallback
            if not link_sistema.strip():
                link_sistema = edital.get('link_edital', '') or ''
            
            if not link_sistema.strip():
                logger.debug(f"❌ Edital sem link: {edital.get('objeto', '?')[:40]}")
                continue  # Sem link = EXCLUÍDO
            
            link_lower = link_sistema.lower()
            
            # 🚫 VERIFICAÇÃO 1: Está na lista de bloqueio?
            is_bloqueado = False
            for pattern in links_bloqueados:
                if pattern.lower() in link_lower:
                    is_bloqueado = True
                    logger.debug(f"🚫 Link BLOQUEADO ({pattern}): {link_sistema[:60]}")
                    break
            
            if is_bloqueado:
                continue  # BLOQUEADO = EXCLUÍDO, sem exceções
            
            # ✅ VERIFICAÇÃO 2: Está na lista de aprovação?
            is_funcional = False
            for pattern in links_funcionais:
                if pattern.lower() in link_lower:
                    is_funcional = True
                    break
            
            if is_funcional:
                # Garantir formato correto do link
                edital['link_edital'] = link_sistema if link_sistema.startswith('http') else f'https://{link_sistema}'
                editais_filtrados.append(edital)
                logger.debug(f"✅ Link FUNCIONAL: {link_sistema[:60]}")
            else:
                logger.debug(f"⚠️ Link NÃO RECONHECIDO (ignorado): {link_sistema[:60]}")
        
        logger.info(f"🔒 [FILTRO RIGOROSO] {len(editais)} → {len(editais_filtrados)} (bloqueados/não-funcionais removidos)")
        
        return editais_filtrados
    
    async def processar_todos_alertas(self, frequencia: Optional[str] = None) -> Dict:
        """
        Processa todos os alertas ativos.
        
        Args:
            frequencia: Filtrar por frequência ('diario' ou 'semanal')
            
        Returns:
            Dict com estatísticas do processamento
        """
        query = {"ativo": True}
        if frequencia:
            query["frequencia"] = frequencia
        
        cursor = self.alertas.find(query, {"_id": 0, "id": 1})
        alertas = await cursor.to_list(1000)
        
        stats = {
            "total_alertas": len(alertas),
            "enviados": 0,
            "sem_novidades": 0,
            "erros": 0,
            "detalhes": []
        }
        
        for alerta in alertas:
            try:
                resultado = await self.processar_alerta(alerta["id"])
                
                if resultado["status"] == "success":
                    stats["enviados"] += 1
                elif resultado["status"] == "no_new":
                    stats["sem_novidades"] += 1
                else:
                    stats["erros"] += 1
                
                stats["detalhes"].append(resultado)
                
            except Exception as e:
                logger.error(f"❌ [ALERTA] Erro ao processar {alerta['id']}: {e}")
                stats["erros"] += 1
        
        logger.info(f"📊 [ALERTAS] Processados: {stats['total_alertas']} | Enviados: {stats['enviados']} | Sem novidades: {stats['sem_novidades']} | Erros: {stats['erros']}")
        
        return stats


# Singleton
_alerta_service = None

def get_alerta_service(db: AsyncIOMotorDatabase) -> AlertaService:
    global _alerta_service
    if _alerta_service is None:
        _alerta_service = AlertaService(db)
    return _alerta_service
