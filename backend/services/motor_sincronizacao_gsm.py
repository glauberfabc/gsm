"""
MOTOR DE SINCRONIZAÇÃO GSM v74.0
================================

Motor de Alimentação Automática de Dados via Agregador

Este serviço sincroniza dados de editais via API do Agregador:
1. Conecta na API do Agregador a cada 15 minutos
2. Busca TODOS os novos editais
3. Salva no MongoDB local (editais_gsm)
4. O sistema fica sempre atualizado com dados frescos

PORTAIS ALIMENTADOS VIA AGREGADOR:
- ComprasNet Federal
- PNCP (Portal Nacional de Contratações Públicas)
- BNC (Bolsa Nacional de Compras)
- BLL Compras
- BBMNet
- Licitar Digital
- ComprasNet Bahia
- E mais 15+ portais regionais

FREQUÊNCIA: A cada 15 minutos
"""

import aiohttp
import asyncio
import logging
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class MotorSincronizacaoGSM:
    """
    Motor de sincronização via API do Agregador.
    Roda automaticamente a cada 15 minutos via APScheduler.
    """
    
    BASE_URL = "https://gsm.gruposmartmedical.com.br"
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.editais_gsm
        self.token = None
        self.timeout = aiohttp.ClientTimeout(total=120)
        
        # Credenciais Agregador
        self.username = 'claudio@gruposmartmedical.com.br'
        self.password = 'Mj@08080808'
        
        # Controle de última sincronização
        self.ultima_sync = None
        self.total_sync_hoje = 0
    
    async def _login(self, session: aiohttp.ClientSession) -> bool:
        """Login na API do Agregador."""
        try:
            url = f"{self.BASE_URL}/users/login"
            payload = {"username": self.username, "password": self.password}
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "GSM-Motor-Sync/1.0"
            }
            
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("token"):
                        self.token = data.get("token")
                        return True
                return False
        except Exception as e:
            logger.error(f"❌ [MOTOR-GSM] Erro no login: {e}")
            return False
    
    def _get_headers(self) -> Dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "GSM-Motor-Sync/1.0"
        }
    
    async def sincronizar(self) -> Dict:
        """
        Executa sincronização com o Agregador.
        
        Este método deve ser chamado pelo APScheduler a cada 15 minutos.
        Busca todos os editais disponíveis e salva no banco local.
        """
        stats = {
            "inicio": datetime.now(timezone.utc).isoformat(),
            "novos": 0,
            "atualizados": 0,
            "paginas": 0,
            "erros": 0
        }
        
        logger.info("🔄 [MOTOR-GSM] Iniciando sincronização com o Agregador...")
        
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                # Login
                if not await self._login(session):
                    stats["erro"] = "Falha no login Agregador"
                    return stats
                
                # Buscar todas as páginas
                pagina = 0
                max_paginas = 100  # Limitar para não travar
                
                while pagina < max_paginas:
                    url = f"{self.BASE_URL}/aviso/minhas"
                    payload = {
                        "pagina": pagina,
                        "interesse": True,
                        "favorito": False,
                        "orgaoFavorito": False,
                        "distribuidores": False,
                        "id": "",
                        "deserto": False,
                        "ordem": [{"orderBy": "dataPublicacao"}, {"order": "desc"}],
                        "tipo": []
                    }
                    
                    try:
                        async with session.post(url, json=payload, headers=self._get_headers()) as response:
                            if response.status != 200:
                                break
                            
                            data = await response.json()
                            avisos = data.get('data', [])
                            
                            if not avisos:
                                break
                            
                            # Processar cada aviso
                            for aviso in avisos:
                                resultado = await self._salvar_aviso(aviso)
                                if resultado == "inserido":
                                    stats["novos"] += 1
                                elif resultado == "atualizado":
                                    stats["atualizados"] += 1
                            
                            stats["paginas"] += 1
                            pagina += 1
                            
                            # Pausa para não sobrecarregar
                            await asyncio.sleep(0.3)
                            
                    except Exception as e:
                        stats["erros"] += 1
                        pagina += 1
                        continue
                
        except Exception as e:
            logger.error(f"❌ [MOTOR-GSM] Erro na sincronização: {e}")
            stats["erro"] = str(e)
        
        stats["fim"] = datetime.now(timezone.utc).isoformat()
        stats["total_banco"] = await self.collection.count_documents({})
        
        self.ultima_sync = datetime.now(timezone.utc)
        self.total_sync_hoje += stats["novos"]
        
        logger.info(f"✅ [MOTOR-GSM] Sync concluída: {stats['novos']} novos, {stats['atualizados']} atualizados, {stats['total_banco']} total")
        
        return stats
    
    async def _salvar_aviso(self, aviso: Dict) -> str:
        """Salva um aviso do Agregador no schema GSM."""
        try:
            aviso_id = str(aviso.get('id', ''))
            id_gsm = hashlib.md5(f"AGREGADOR-{aviso_id}".encode()).hexdigest()
            
            # Verificar se já existe e é recente (não atualizar se < 1 hora)
            existente = await self.collection.find_one({"id_gsm": id_gsm}, {"atualizado_em": 1})
            if existente:
                atualizado = existente.get("atualizado_em")
                if atualizado and isinstance(atualizado, datetime):
                    if (datetime.now(timezone.utc) - atualizado.replace(tzinfo=timezone.utc)).total_seconds() < 3600:
                        return "existente"
            
            # Extrair dados
            objeto = aviso.get('objeto', '') or ''
            uasg = str(aviso.get('uasg', '') or '')
            uasg_nome = aviso.get('uasgNome', '') or ''
            portal_nome = aviso.get('portalNome', 'Agregador') or 'Agregador'
            uf_completo = aviso.get('uf', '') or ''
            pregao = aviso.get('pregao', '') or ''
            url = aviso.get('url', '') or ''
            
            # UF
            uf_sigla = self._extrair_uf(uf_completo)
            
            # Município
            municipio = self._extrair_municipio(uasg_nome)
            
            # Datas
            data_inicial = self._parse_date(aviso.get('dataInicial'))
            data_final = self._parse_date(aviso.get('dataFinal'))
            data_pub = self._parse_date(aviso.get('dataPublicacao'))
            
            # Itens
            itens_raw = aviso.get('item', []) or []
            itens_formatados = []
            for idx, item in enumerate(itens_raw):
                itens_formatados.append({
                    "grupo": item.get('grupo', 1),
                    "item": idx + 1,
                    "descricao": item.get('descricao', item.get('objeto', objeto[:200])),
                    "me_epp": "Sim" if aviso.get('exclusivoMePp') else "Não",
                    "quantidade": item.get('quantidade', 1),
                    "unidade": item.get('unidade', 'UN'),
                    "valor_unitario": item.get('valor'),
                    "valor_total": item.get('valorTotal') or item.get('valor')
                })
            
            if not itens_formatados and objeto:
                itens_formatados.append({
                    "grupo": 1,
                    "item": 1,
                    "descricao": objeto[:500],
                    "me_epp": "Sim" if aviso.get('exclusivoMePp') else "Não",
                    "quantidade": 1,
                    "unidade": "UN",
                    "valor_unitario": None,
                    "valor_total": None
                })
            
            doc = {
                "id_gsm": id_gsm,
                "id_externo": aviso_id,
                "numero_controle_pncp": "",
                
                "fonte_origem": "AGREGADOR",
                "fonte": portal_nome,
                "portal_captura": portal_nome,
                
                "dados_orgao": {
                    "uasg": uasg,
                    "cnpj": "",
                    "nome": uasg_nome,
                    "uf": uf_sigla,
                    "municipio": municipio
                },
                
                "objeto": objeto.upper(),
                "orgao": uasg_nome,
                "estado": uf_sigla,
                "uf": uf_sigla,
                "municipio": municipio,
                "uasg": uasg,
                
                "modalidade": aviso.get('tipo', 'Pregão Eletrônico'),
                "status": "ABERTA",
                
                "data_publicacao": data_pub.isoformat() if data_pub else None,
                "data_abertura": data_final.isoformat() if data_final else None,
                "data_inicial": data_inicial.isoformat() if data_inicial else None,
                "data_final": data_final.isoformat() if data_final else None,
                
                "link_documento": self._extrair_link_pdf(aviso) or url,
                "link_pdf": self._extrair_link_pdf(aviso),
                "link_origem": url,
                "link_portal": url,
                
                # Anexos originais
                "anexos": [
                    {"nome": a.get('nome', ''), "url": a.get('url', '')}
                    for a in (aviso.get('anexo', []) or [])
                    if a.get('url')
                ],
                
                "numero_processo": pregao,
                "numero_licitacao": pregao,
                
                "itens_clonados": itens_formatados,
                
                "sincronizado_em": datetime.now(timezone.utc),
                "atualizado_em": datetime.now(timezone.utc),
                "is_saude": self._is_saude(objeto),
                "is_clone_agregador": True
            }
            
            result = await self.collection.update_one(
                {"id_gsm": id_gsm},
                {"$set": doc},
                upsert=True
            )
            
            if result.upserted_id:
                return "inserido"
            elif result.modified_count > 0:
                return "atualizado"
            return "existente"
            
        except Exception as e:
            logger.debug(f"Erro ao salvar: {e}")
            return "erro"
    
    def _extrair_link_pdf(self, aviso: Dict) -> Optional[str]:
        """Extrai link direto para PDF do edital a partir dos anexos."""
        anexos = aviso.get('anexo', []) or []
        if not anexos:
            return None
        
        for anexo in anexos:
            nome = (anexo.get('nome', '') or '').lower()
            url_anexo = anexo.get('url', '')
            if url_anexo and ('edital' in nome):
                return url_anexo
        
        for anexo in anexos:
            nome = (anexo.get('nome', '') or '').lower()
            url_anexo = anexo.get('url', '')
            if url_anexo and ('.pdf' in nome or '.zip' in nome):
                return url_anexo
        
        for anexo in anexos:
            url_anexo = anexo.get('url', '')
            if url_anexo:
                return url_anexo
        
        return None
    
    def _extrair_uf(self, uf_completo: str) -> str:
        if not uf_completo:
            return ''
        uf_map = {
            'acre': 'AC', 'alagoas': 'AL', 'amapá': 'AP', 'amazonas': 'AM',
            'bahia': 'BA', 'ceará': 'CE', 'distrito federal': 'DF', 'espírito santo': 'ES',
            'goiás': 'GO', 'maranhão': 'MA', 'mato grosso': 'MT', 'mato grosso do sul': 'MS',
            'minas gerais': 'MG', 'pará': 'PA', 'paraíba': 'PB', 'paraná': 'PR',
            'pernambuco': 'PE', 'piauí': 'PI', 'rio de janeiro': 'RJ', 'rio grande do norte': 'RN',
            'rio grande do sul': 'RS', 'rondônia': 'RO', 'roraima': 'RR', 'santa catarina': 'SC',
            'são paulo': 'SP', 'sergipe': 'SE', 'tocantins': 'TO'
        }
        return uf_map.get(uf_completo.lower().strip(), uf_completo[:2].upper() if len(uf_completo) >= 2 else '')
    
    def _extrair_municipio(self, orgao_nome: str) -> str:
        if not orgao_nome:
            return ''
        prefixes = ['prefeitura municipal de ', 'prefeitura de ', 'município de ', 'fundo municipal de saude de ']
        orgao_lower = orgao_nome.lower()
        for prefix in prefixes:
            if prefix in orgao_lower:
                return orgao_nome.split(prefix)[-1].split(' - ')[0].strip().title()
        return ''
    
    def _parse_date(self, date_str) -> Optional[datetime]:
        if not date_str:
            return None
        try:
            date_str = str(date_str).strip()
            if 'T' in date_str:
                return datetime.fromisoformat(date_str.replace('Z', ''))
            elif '/' in date_str and ':' in date_str:
                return datetime.strptime(date_str, '%d/%m/%Y %H:%M:%S')
            elif '/' in date_str:
                return datetime.strptime(date_str, '%d/%m/%Y')
        except:
            pass
        return None
    
    def _is_saude(self, objeto: str) -> bool:
        if not objeto:
            return False
        objeto_lower = objeto.lower()
        keywords = ['medicament', 'farmac', 'hospital', 'saúde', 'saude', 'médic', 'medic',
                   'insulina', 'vacina', 'canabidiol', 'cannabis', 'cbd', 'oncolog']
        return any(kw in objeto_lower for kw in keywords)
    
    async def get_status(self) -> Dict:
        """Retorna status do motor de sincronização."""
        total = await self.collection.count_documents({})
        ultimas_24h = await self.collection.count_documents({
            "sincronizado_em": {"$gte": datetime.now(timezone.utc) - timedelta(hours=24)}
        })
        
        return {
            "total_editais": total,
            "novos_24h": ultimas_24h,
            "ultima_sync": self.ultima_sync.isoformat() if self.ultima_sync else None,
            "sync_hoje": self.total_sync_hoje
        }


# Singleton
_motor_gsm = None

def get_motor_sincronizacao(db: AsyncIOMotorDatabase) -> MotorSincronizacaoGSM:
    global _motor_gsm
    if _motor_gsm is None:
        _motor_gsm = MotorSincronizacaoGSM(db)
    return _motor_gsm
