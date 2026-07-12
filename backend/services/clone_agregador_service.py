"""
CLONE AGREGADOR v59.0 - Espelhamento Total da API Agregador
========================================================

OBJETIVO: Clonar TODOS os dados da API Agregador para o MongoDB local.
O sistema deve retornar 950+ resultados como o parceiro.

ESTRATÉGIA:
1. Login na API Agregador
2. Buscar TODAS as licitações disponíveis (sem filtros)
3. Salvar no editais_gsm com schema GSM v57.0
4. Repetir para múltiplas páginas até esgotar

SCHEMA GSM v57.0:
- UASG em destaque
- Portal de Origem
- Tabela de Itens (6 colunas)
- Links funcionais
"""

import aiohttp
import asyncio
import logging
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class CloneAgregadorService:
    """
    Serviço de clonagem da API Agregador para o MongoDB local.
    """
    
    BASE_URL = "https://gsm.gruposmartmedical.com.br"
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.editais_gsm
        self.token = None
        self.timeout = aiohttp.ClientTimeout(total=120)
        
        # Credenciais
        self.username = 'claudio@gruposmartmedical.com.br'
        self.password = 'Mj@08080808'
    
    async def _login(self, session: aiohttp.ClientSession) -> bool:
        """Realiza login no Agregador."""
        try:
            url = f"{self.BASE_URL}/users/login"
            payload = {
                "username": self.username,
                "password": self.password
            }
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "GSM-Clone/1.0"
            }
            
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("token"):
                        self.token = data.get("token")
                        logger.info(f"✅ [CLONE-AGREGADOR] Login OK")
                        return True
                logger.error(f"❌ [CLONE-AGREGADOR] Login falhou: HTTP {response.status}")
                return False
        except Exception as e:
            logger.error(f"❌ [CLONE-AGREGADOR] Erro no login: {e}")
            return False
    
    def _get_headers(self) -> Dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "GSM-Clone/1.0"
        }
    
    async def clonar_tudo(self, max_paginas: int = 50) -> Dict:
        """
        Clona TODOS os dados da API Agregador.
        
        Returns:
            Dict com estatísticas da clonagem
        """
        stats = {
            "inicio": datetime.now(timezone.utc).isoformat(),
            "total_clonados": 0,
            "total_atualizados": 0,
            "paginas_processadas": 0,
            "erros": 0
        }
        
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                # 1. Login
                if not await self._login(session):
                    stats["erro"] = "Falha no login"
                    return stats
                
                # 2. Buscar página por página
                pagina = 0
                total_records = None
                
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
                        "ordem": [
                            {"orderBy": "dataInicial"},
                            {"order": "asc"}
                        ],
                        "tipo": []
                    }
                    
                    try:
                        async with session.post(url, json=payload, headers=self._get_headers()) as response:
                            if response.status != 200:
                                logger.warning(f"⚠️ [CLONE] Página {pagina} HTTP {response.status}")
                                break
                            
                            data = await response.json()
                            
                            if total_records is None:
                                total_records = data.get('recordsTotal', 0)
                                logger.info(f"📊 [CLONE-AGREGADOR] Total no Agregador: {total_records}")
                            
                            avisos = data.get('data', [])
                            if not avisos:
                                logger.info(f"✅ [CLONE] Fim dos dados na página {pagina}")
                                break
                            
                            # Processar cada aviso
                            for aviso in avisos:
                                resultado = await self._salvar_aviso(aviso)
                                if resultado == "inserido":
                                    stats["total_clonados"] += 1
                                elif resultado == "atualizado":
                                    stats["total_atualizados"] += 1
                            
                            stats["paginas_processadas"] += 1
                            logger.info(f"📥 [CLONE] Página {pagina}: {len(avisos)} avisos ({stats['total_clonados']} clonados)")
                            
                            pagina += 1
                            
                            # Pequena pausa para não sobrecarregar
                            await asyncio.sleep(0.5)
                            
                    except Exception as e:
                        logger.error(f"❌ [CLONE] Erro na página {pagina}: {e}")
                        stats["erros"] += 1
                        pagina += 1
                        continue
                
        except Exception as e:
            logger.error(f"❌ [CLONE-AGREGADOR] Erro geral: {e}")
            stats["erro"] = str(e)
        
        stats["fim"] = datetime.now(timezone.utc).isoformat()
        stats["total_editais_gsm"] = await self.collection.count_documents({})
        
        logger.info(f"✅ [CLONE-AGREGADOR] Concluído: {stats['total_clonados']} clonados, {stats['total_editais_gsm']} total no banco")
        
        return stats
    
    async def _salvar_aviso(self, aviso: Dict) -> str:
        """
        Salva um aviso do Agregador no schema GSM v57.0.
        """
        try:
            aviso_id = str(aviso.get('id', ''))
            id_gsm = hashlib.md5(f"AGREGADOR-{aviso_id}".encode()).hexdigest()
            
            # Extrair dados
            objeto = aviso.get('objeto', '') or ''
            uasg = str(aviso.get('uasg', '') or '')
            uasg_nome = aviso.get('uasgNome', '') or ''
            portal_nome = aviso.get('portalNome', 'Agregador') or 'Agregador'
            uf_completo = aviso.get('uf', '') or ''
            pregao = aviso.get('pregao', '') or ''
            url = aviso.get('url', '') or ''
            
            # Converter UF
            uf_sigla = self._extrair_uf(uf_completo)
            
            # Extrair município do nome do órgão
            municipio = self._extrair_municipio(uasg_nome)
            
            # Datas
            data_inicial = self._parse_date(aviso.get('dataInicial'))
            data_final = self._parse_date(aviso.get('dataFinal'))
            data_pub = self._parse_date(aviso.get('dataPublicacao'))
            
            # Itens (se disponíveis)
            itens_raw = aviso.get('item', []) or []
            itens_formatados = []
            for idx, item in enumerate(itens_raw):
                itens_formatados.append({
                    "grupo": 1,
                    "item": idx + 1,
                    "descricao": item.get('descricao', item.get('objeto', objeto[:100])),
                    "me_epp": "Sim" if aviso.get('exclusivoMePp') else "Não",
                    "quantidade": item.get('quantidade', 1),
                    "unidade": item.get('unidade', 'UN'),
                    "valor_unitario": item.get('valor'),
                    "valor_total": item.get('valor')
                })
            
            # Se não há itens, criar um item com o objeto
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
            
            # Extrair link PDF dos anexos (campo crucial para download direto)
            link_pdf = self._extrair_link_pdf(aviso)
            
            # Documento no schema GSM v57.0
            doc = {
                "id_gsm": id_gsm,
                "id_externo": aviso_id,
                "numero_controle_pncp": "",
                
                # Fonte (PADRÃO AGREGADOR)
                "fonte_origem": "AGREGADOR",
                "fonte": portal_nome,
                "portal_captura": portal_nome,
                
                # Órgão (PADRÃO AGREGADOR)
                "dados_orgao": {
                    "uasg": uasg,
                    "cnpj": "",
                    "nome": uasg_nome,
                    "uf": uf_sigla,
                    "municipio": municipio
                },
                
                # Dados principais
                "objeto": objeto.upper(),
                "orgao": uasg_nome,
                "estado": uf_sigla,
                "uf": uf_sigla,
                "municipio": municipio,
                "uasg": uasg,
                
                # Classificação
                "modalidade": aviso.get('tipo', 'Pregão Eletrônico'),
                "status": "ABERTA",
                
                # Datas (PADRÃO AGREGADOR)
                "data_publicacao": data_pub.isoformat() if data_pub else None,
                "data_abertura": data_final.isoformat() if data_final else None,
                "data_inicial": data_inicial.isoformat() if data_inicial else None,
                "data_final": data_final.isoformat() if data_final else None,
                
                # Links (PADRÃO AGREGADOR - com PDF dos anexos)
                "link_documento": link_pdf or url,
                "link_pdf": link_pdf,
                "link_origem": url,
                "link_portal": url,
                
                # Anexos originais (para referência completa)
                "anexos": [
                    {"nome": a.get('nome', ''), "url": a.get('url', '')}
                    for a in (aviso.get('anexo', []) or [])
                    if a.get('url')
                ],
                
                # Identificação
                "numero_processo": pregao,
                "numero_licitacao": pregao,
                
                # TABELA DE ITENS (6 colunas - PADRÃO AGREGADOR)
                "itens_clonados": itens_formatados,
                
                # Metadados
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
            logger.debug(f"Erro ao salvar aviso: {e}")
            return "erro"
    
    def _extrair_uf(self, uf_completo: str) -> str:
        """Converte nome do estado para sigla UF."""
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
        
        uf_lower = uf_completo.lower().strip()
        return uf_map.get(uf_lower, uf_completo[:2].upper() if len(uf_completo) >= 2 else '')
    
    def _extrair_municipio(self, orgao_nome: str) -> str:
        """Tenta extrair município do nome do órgão."""
        if not orgao_nome:
            return ''
        
        # Padrões comuns
        prefixes = ['prefeitura municipal de ', 'prefeitura de ', 'município de ', 'fundo municipal de saude de ']
        orgao_lower = orgao_nome.lower()
        
        for prefix in prefixes:
            if prefix in orgao_lower:
                return orgao_nome.split(prefix)[-1].split(' - ')[0].strip().title()
        
        return ''
    
    def _parse_date(self, date_str) -> Optional[datetime]:
        """Converte string de data para datetime."""
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
            return None
        except:
            return None
    
    def _extrair_link_pdf(self, aviso: Dict) -> Optional[str]:
        """Extrai link direto para PDF do edital a partir dos anexos."""
        anexos = aviso.get('anexo', []) or []
        if not anexos:
            return None
        
        # Prioridade 1: Anexo com 'edital' no nome
        for anexo in anexos:
            nome = (anexo.get('nome', '') or '').lower()
            url_anexo = anexo.get('url', '')
            if url_anexo and ('edital' in nome):
                return url_anexo
        
        # Prioridade 2: Qualquer PDF
        for anexo in anexos:
            nome = (anexo.get('nome', '') or '').lower()
            url_anexo = anexo.get('url', '')
            if url_anexo and ('.pdf' in nome or '.zip' in nome):
                return url_anexo
        
        # Prioridade 3: Primeiro anexo disponível
        for anexo in anexos:
            url_anexo = anexo.get('url', '')
            if url_anexo:
                return url_anexo
        
        return None
    
    def _is_saude(self, objeto: str) -> bool:
        """Verifica se é edital de saúde."""
        if not objeto:
            return False
        
        objeto_lower = objeto.lower()
        keywords = ['medicament', 'farmac', 'hospital', 'saúde', 'saude', 'médic', 'medic',
                   'insulina', 'vacina', 'canabidiol', 'cannabis', 'cbd', 'oncolog']
        return any(kw in objeto_lower for kw in keywords)


# Singleton
_clone_service = None

def get_clone_agregador_service(db: AsyncIOMotorDatabase) -> CloneAgregadorService:
    global _clone_service
    if _clone_service is None:
        _clone_service = CloneAgregadorService(db)
    return _clone_service
