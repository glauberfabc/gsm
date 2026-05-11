"""
Serviço de Download de PDFs - 100% Independente
================================================
Baixa PDFs do Conlicitação usando nossa sessão autenticada,
armazena localmente e serve ao usuário sem dependência externa.
"""

import os
import logging
import aiohttp
import asyncio
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

EDITAIS_DIR = Path(__file__).parent.parent / "uploads" / "editais"
EDITAIS_DIR.mkdir(parents=True, exist_ok=True)

CONLICITACAO_BASE = "https://consultaonline.conlicitacao.com.br"
CONLICITACAO_FRONTEND = "https://consulteonline.conlicitacao.com.br"


class PdfDownloadService:
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.email = os.environ.get('CONLICITACAO_EMAIL', '')
        self.password = os.environ.get('CONLICITACAO_PASSWORD', '')
        self._jar = aiohttp.CookieJar()
        self._logged_in = False
    
    def _headers(self):
        return {
            'Accept': '*/*',
            'Cache': 'no-cache',
            'NewFront': 'true',
            'Origin': CONLICITACAO_FRONTEND,
            'Referer': f'{CONLICITACAO_FRONTEND}/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    async def _login(self):
        timeout = aiohttp.ClientTimeout(total=30)
        self._jar = aiohttp.CookieJar()
        try:
            async with aiohttp.ClientSession(timeout=timeout, headers={
                **self._headers(),
                'Content-Type': 'application/json'
            }, cookie_jar=self._jar) as session:
                await session.get(f'{CONLICITACAO_BASE}/users/login')
                async with session.post(f'{CONLICITACAO_BASE}/users/login.json',
                                         json={'login': self.email, 'senha': self.password, 'refresh': False}) as resp:
                    if resp.status == 200:
                        self._logged_in = True
                        logger.info("PdfDownload: login OK")
                    else:
                        logger.error(f"PdfDownload: login falhou ({resp.status})")
        except Exception as e:
            logger.error(f"PdfDownload: login timeout/erro: {e}")
    
    def _local_path(self, id_externo: str) -> Path:
        return EDITAIS_DIR / f"{id_externo}.zip"
    
    async def get_pdf(self, id_externo: str) -> dict:
        """Retorna o PDF local ou baixa do Conlicitação."""
        local = self._local_path(id_externo)
        
        # Se já temos local, retornar
        if local.exists() and local.stat().st_size > 100:
            return {'path': str(local), 'status': 'local'}
        
        # Buscar URL do PDF no banco
        doc = await self.db['editais_clone'].find_one(
            {'id_externo': id_externo},
            {'_id': 0, 'link_pdf': 1, 'link_portal': 1}
        )
        if not doc:
            return {'path': None, 'status': 'not_found'}
        
        link_pdf = doc.get('link_pdf', '')
        if not link_pdf or 'conlicitacao' not in link_pdf:
            # Não é do Conlicitação, usar link_portal
            return {'path': None, 'status': 'redirect', 'url': doc.get('link_portal', '')}
        
        # Baixar do Conlicitação via nossa sessão
        if not self._logged_in:
            await self._login()
        
        if not self._logged_in:
            return {'path': None, 'status': 'auth_failed', 'url': doc.get('link_portal', '')}
        
        try:
            timeout = aiohttp.ClientTimeout(total=60)
            async with aiohttp.ClientSession(
                timeout=timeout, headers=self._headers(), cookie_jar=self._jar
            ) as session:
                async with session.get(link_pdf) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        if len(content) > 100:
                            local.write_bytes(content)
                            # Atualizar banco com caminho local
                            await self.db['editais_clone'].update_one(
                                {'id_externo': id_externo},
                                {'$set': {'pdf_local': str(local), 'pdf_baixado': True}}
                            )
                            logger.info(f"PDF baixado: {id_externo} ({len(content)} bytes)")
                            return {'path': str(local), 'status': 'downloaded'}
                    
                    if resp.status in (401, 403, 302):
                        self._logged_in = False
                        await self._login()
                        # Tentar novamente
                        async with session.get(link_pdf) as resp2:
                            if resp2.status == 200:
                                content = await resp2.read()
                                if len(content) > 100:
                                    local.write_bytes(content)
                                    await self.db['editais_clone'].update_one(
                                        {'id_externo': id_externo},
                                        {'$set': {'pdf_local': str(local), 'pdf_baixado': True}}
                                    )
                                    return {'path': str(local), 'status': 'downloaded'}
        except Exception as e:
            logger.error(f"Erro ao baixar PDF {id_externo}: {e}")
        
        # Fallback para link do portal original
        return {'path': None, 'status': 'download_failed', 'url': doc.get('link_portal', '')}
    
    async def baixar_lote(self, limit: int = 100):
        """Baixa PDFs em lote (background job)."""
        if not self._logged_in:
            await self._login()
        
        if not self._logged_in:
            logger.error("PdfDownload: não conseguiu autenticar")
            return 0
        
        # Buscar editais que ainda não tem PDF local
        cursor = self.db['editais_clone'].find(
            {'link_pdf': {'$regex': 'conlicitacao'}, 'pdf_baixado': {'$ne': True}},
            {'_id': 0, 'id_externo': 1, 'link_pdf': 1}
        ).limit(limit)
        
        docs = await cursor.to_list(length=limit)
        baixados = 0
        
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(
            timeout=timeout, headers=self._headers(), cookie_jar=self._jar
        ) as session:
            for doc in docs:
                try:
                    id_ext = doc['id_externo']
                    local = self._local_path(id_ext)
                    
                    if local.exists():
                        await self.db['editais_clone'].update_one(
                            {'id_externo': id_ext},
                            {'$set': {'pdf_local': str(local), 'pdf_baixado': True}}
                        )
                        baixados += 1
                        continue
                    
                    async with session.get(doc['link_pdf']) as resp:
                        if resp.status == 200:
                            content = await resp.read()
                            if len(content) > 100:
                                local.write_bytes(content)
                                await self.db['editais_clone'].update_one(
                                    {'id_externo': id_ext},
                                    {'$set': {'pdf_local': str(local), 'pdf_baixado': True}}
                                )
                                baixados += 1
                        elif resp.status in (401, 403):
                            self._logged_in = False
                            await self._login()
                    
                    await asyncio.sleep(0.5)  # Rate limit
                    
                except Exception as e:
                    logger.error(f"Erro PDF lote {doc.get('id_externo')}: {e}")
        
        logger.info(f"PdfDownload lote: {baixados}/{len(docs)} baixados")
        return baixados
