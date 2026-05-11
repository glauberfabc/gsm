"""
Clonador Conlicitação → MongoDB
=================================
Importa TODOS os editais do Conlicitação para nosso banco.
Após clonagem, o sistema funciona 100% independente.

Fluxo:
1. Login no Conlicitação (temporário, só para importação)
2. Busca paginada de TODOS os editais
3. Armazena no MongoDB (coleção 'editais_clone')
4. Cria índice de busca textual
5. Motor de busca consulta nosso MongoDB — zero dependência externa
"""

import os
import re
import logging
import aiohttp
import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)
HTML_TAG_RE = re.compile(r'<[^>]+>')


class ClonadorConlicitacao:
    
    BASE_URL = "https://consultaonline.conlicitacao.com.br"
    FRONTEND_URL = "https://consulteonline.conlicitacao.com.br"
    COLLECTION = "editais_clone"
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.email = os.environ.get('CONLICITACAO_EMAIL', '')
        self.password = os.environ.get('CONLICITACAO_PASSWORD', '')
        self._jar = aiohttp.CookieJar()
        self._company_id = None
        self._logged_in = False
    
    def _headers(self):
        return {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Cache': 'no-cache',
            'NewFront': 'true',
            'Origin': self.FRONTEND_URL,
            'Referer': f'{self.FRONTEND_URL}/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    async def _login(self):
        timeout = aiohttp.ClientTimeout(total=15)
        self._jar = aiohttp.CookieJar()
        async with aiohttp.ClientSession(timeout=timeout, headers=self._headers(), cookie_jar=self._jar) as session:
            await session.get(f'{self.BASE_URL}/users/login')
            async with session.post(f'{self.BASE_URL}/users/login.json',
                                     json={'login': self.email, 'senha': self.password, 'refresh': False}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self._company_id = data.get('user', {}).get('client_id')
                    self._logged_in = True
                    logger.info(f"Clonador: login OK (company={self._company_id})")
    
    async def criar_indices(self):
        """Cria índices no MongoDB para busca eficiente."""
        col = self.db[self.COLLECTION]
        await col.create_index([("objeto", "text"), ("itens", "text"), ("orgao", "text")],
                               name="busca_textual", default_language="portuguese")
        await col.create_index("id_externo", unique=True, sparse=True)
        await col.create_index("data_final")
        await col.create_index("portal_captura")
        await col.create_index("uf")
        logger.info("Clonador: índices MongoDB criados")
    
    async def importar_tudo(self, max_pages: int = 7300):
        """Importa TODOS os editais do Conlicitação → MongoDB."""
        if not self.email or not self.password:
            logger.warning("Clonador: credenciais não configuradas")
            return
        
        await self._login()
        if not self._logged_in:
            logger.error("Clonador: login falhou, abortando importação")
            return
        
        await self.criar_indices()
        
        col = self.db[self.COLLECTION]
        total_importados = 0
        total_existentes = 0
        page = 1
        
        timeout = aiohttp.ClientTimeout(total=20)
        
        logger.info(f"Clonador: iniciando importação (max {max_pages} páginas)...")
        
        async with aiohttp.ClientSession(timeout=timeout, headers=self._headers(), cookie_jar=self._jar) as session:
            while page <= max_pages:
                try:
                    params = {'page': page}
                    if self._company_id:
                        params['companyId'] = self._company_id
                    
                    async with session.get(f'{self.BASE_URL}/biddings.json', params=params) as resp:
                        if resp.status in (401, 403, 423):
                            logger.warning(f"Clonador: sessão expirada na página {page}, re-login...")
                            await self._login()
                            continue
                        
                        if resp.status != 200:
                            logger.error(f"Clonador: erro {resp.status} na página {page}")
                            break
                        
                        data = await resp.json()
                        biddings = data.get('biddings', [])
                        
                        if not biddings:
                            logger.info(f"Clonador: sem mais dados na página {page}")
                            break
                        
                        # Mapear e inserir em batch
                        docs = []
                        for bid in biddings:
                            doc = self._mapear(bid)
                            if doc:
                                docs.append(doc)
                        
                        if docs:
                            for doc in docs:
                                try:
                                    await col.update_one(
                                        {'id_externo': doc['id_externo']},
                                        {'$set': doc},
                                        upsert=True
                                    )
                                    total_importados += 1
                                except Exception:
                                    total_existentes += 1
                        
                        # Log progresso a cada 50 páginas
                        if page % 50 == 0:
                            total_pages = data.get('total_pages', '?')
                            logger.info(f"Clonador: página {page}/{total_pages} | {total_importados} importados")
                        
                        page += 1
                        
                        # Rate limit - não sobrecarregar o servidor
                        await asyncio.sleep(0.3)
                
                except aiohttp.ClientError as e:
                    logger.error(f"Clonador: erro rede página {page}: {e}")
                    await asyncio.sleep(2)
                    continue
                except Exception as e:
                    logger.error(f"Clonador: erro página {page}: {e}")
                    page += 1
                    continue
        
        logger.info(f"Clonador: CONCLUÍDO! {total_importados} editais importados, {total_existentes} já existiam")
    
    def _strip_html(self, text: str) -> str:
        if not text:
            return ''
        return HTML_TAG_RE.sub('', text).strip()
    
    def _detect_portal(self, bid: Dict) -> str:
        site = bid.get('edital_site') or ''
        if 'pncp.gov.br' in site: return 'PNCP'
        if 'comprasnet' in site or 'compras.gov.br' in site: return 'ComprasNet'
        if 'bll' in site: return 'BLL'
        if 'bnc' in site: return 'BNC'
        if 'bbmnet' in site: return 'BBMNet'
        if 'licitanet' in site: return 'Licitanet'
        if 'licitar.digital' in site or 'licitardigital' in site: return 'Licitar Digital'
        if 'portaldecompraspublicas' in site: return 'Compras Públicas'
        if 'bec.sp.gov.br' in site: return 'BEC SP'
        if 'licitacoes-e' in site: return 'Licitações-e'
        if 'comprasbr' in site: return 'ComprasBR'
        if 'licitamaisbrasil' in site: return 'Licitamais'
        if 'petronect' in site: return 'Petronect'
        if site and '//' in site:
            return site.split('//')[1].split('/')[0]
        return 'Conlicitação'
    
    def _mapear(self, bid: Dict) -> Optional[Dict]:
        try:
            bid_id = bid.get('id') or bid.get('bidding_id', '')
            objeto = self._strip_html(bid.get('objeto', ''))
            itens = self._strip_html(bid.get('itens', ''))
            
            orgao = ''
            if bid.get('public_body'):
                orgao = bid['public_body'].get('nome', '')
            
            cidade = bid.get('orgao_cidade', '')
            estado = bid.get('orgao_estado', '')
            modalidade = bid.get('modality', {}).get('nome', '') if bid.get('modality') else ''
            
            data_abertura = bid.get('datahora_abertura') or ''
            data_final = bid.get('data_validade') or bid.get('datahora_prazo') or data_abertura
            
            portal = self._detect_portal(bid)
            link_portal = bid.get('edital_site') or ''
            
            link_pdf = ''
            edicts = bid.get('edicts') or []
            if edicts:
                url_path = edicts[0].get('url', '')
                if url_path:
                    link_pdf = f"{self.BASE_URL}{url_path}"
            
            return {
                'id_externo': str(bid_id),
                'id_gsm': f"CON-{bid_id}",
                'fonte': 'CLONE_CONLICITACAO',
                'portal_captura': f"{portal} ({estado})" if estado else portal,
                'portal_base': portal,
                'objeto': objeto,
                'itens': itens,
                'orgao': orgao,
                'uf': estado,
                'municipio': cidade,
                'modalidade': modalidade,
                'numero_edital': bid.get('edital', ''),
                'data_publicacao': data_abertura,
                'data_abertura': data_abertura,
                'data_final': data_final,
                'valor_estimado': bid.get('valor_estimado') or 0,
                'link_portal': link_portal,
                'link_pdf': link_pdf,
                'observacao': bid.get('observacao', ''),
                'importado_em': datetime.now(timezone.utc).isoformat(),
                'ativo': True
            }
        except Exception as e:
            logger.error(f"Clonador mapeamento: {e}")
            return None
