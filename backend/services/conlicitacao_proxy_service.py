"""
Conlicitação Proxy Service v2.0
================================
Fonte independente com 145.000+ editais via consultaonline.conlicitacao.com.br.

Login: GET /users/login (session) → POST /users/login.json (auth_token + cookies)
Busca: GET /biddings.json?objeto=KEYWORD&page=N
Dados: objeto, orgão, cidade, UF, edital, datas, itens com highlight, PDF download
"""

import os
import re
import logging
import aiohttp
from typing import Dict, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Strip HTML tags helper
HTML_TAG_RE = re.compile(r'<[^>]+>')


class ConlicitacaoProxyService:
    """Proxy para Conlicitação: login automático + busca de editais."""
    
    BASE_URL = "https://consultaonline.conlicitacao.com.br"
    FRONTEND_URL = "https://consulteonline.conlicitacao.com.br"
    
    def __init__(self):
        self.email = os.environ.get('CONLICITACAO_EMAIL', '')
        self.password = os.environ.get('CONLICITACAO_PASSWORD', '')
        self._jar = aiohttp.CookieJar()
        self._logged_in = False
        self._company_id = None
    
    async def inicializar(self):
        """Login no Conlicitação em background."""
        if not self.email or not self.password:
            logger.warning("Conlicitação: credenciais não configuradas")
            return
        try:
            await self._login()
        except Exception as e:
            logger.error(f"Conlicitação: erro no login: {e}")
    
    def _headers(self) -> Dict:
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
        """GET session → POST login.json → cookies."""
        timeout = aiohttp.ClientTimeout(total=15)
        self._jar = aiohttp.CookieJar()
        
        async with aiohttp.ClientSession(timeout=timeout, headers=self._headers(), cookie_jar=self._jar) as session:
            # 1. GET login page for session cookie
            await session.get(f'{self.BASE_URL}/users/login')
            
            # 2. POST login
            payload = {'login': self.email, 'senha': self.password, 'refresh': False}
            async with session.post(f'{self.BASE_URL}/users/login.json', json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self._company_id = data.get('user', {}).get('client_id')
                    self._logged_in = True
                    logger.info(f"Conlicitação: login OK (company={self._company_id})")
                else:
                    logger.error(f"Conlicitação: login falhou ({resp.status})")
    
    async def buscar(self, termo: str, limit: int = 50) -> Dict:
        """Busca editais por palavra-chave."""
        if not self._logged_in:
            await self.inicializar()
        if not self._logged_in:
            return {'resultados': [], 'total': 0}
        
        resultados = []
        total = 0
        
        try:
            timeout = aiohttp.ClientTimeout(total=20)
            
            # Para multi-termo, buscar os 3 primeiros termos
            termos = [t.strip() for t in termo.split(',') if t.strip()][:3]
            
            async with aiohttp.ClientSession(timeout=timeout, headers=self._headers(), cookie_jar=self._jar) as session:
                for t in termos:
                    params = {'objeto': t, 'page': 1}
                    if self._company_id:
                        params['companyId'] = self._company_id
                    
                    try:
                        async with session.get(f'{self.BASE_URL}/biddings.json', params=params) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                total += data.get('total_entries', 0)
                                for bid in data.get('biddings', []):
                                    mapped = self._mapear(bid)
                                    if mapped:
                                        resultados.append(mapped)
                                
                                # Page 2 se precisar
                                if data.get('total_pages', 1) > 1 and len(resultados) < limit:
                                    params['page'] = 2
                                    async with session.get(f'{self.BASE_URL}/biddings.json', params=params) as resp2:
                                        if resp2.status == 200:
                                            data2 = await resp2.json()
                                            for bid in data2.get('biddings', []):
                                                mapped = self._mapear(bid)
                                                if mapped:
                                                    resultados.append(mapped)
                            elif resp.status in (401, 403, 423):
                                logger.warning("Conlicitação: sessão expirada, re-login...")
                                self._logged_in = False
                                await self._login()
                    except Exception as e:
                        logger.error(f"Conlicitação busca '{t}': {e}")
        
        except Exception as e:
            logger.error(f"Conlicitação buscar erro: {e}")
        
        return {
            'resultados': resultados[:limit],
            'total': total,
            'fonte': 'CONLICITACAO'
        }
    
    def _strip_html(self, text: str) -> str:
        """Remove tags HTML mas mantém texto."""
        if not text:
            return ''
        return HTML_TAG_RE.sub('', text).strip()
    
    def _detect_portal(self, bid: Dict) -> str:
        """Detecta o portal de origem pelo edital_site ou fonte_id."""
        site = bid.get('edital_site') or ''
        if 'pncp.gov.br' in site:
            return 'PNCP'
        if 'comprasnet' in site or 'compras.gov.br' in site:
            return 'ComprasNet'
        if 'bll' in site:
            return 'BLL'
        if 'bnc' in site:
            return 'BNC'
        if 'bbmnet' in site:
            return 'BBMNet'
        if 'licitanet' in site:
            return 'Licitanet'
        if 'licitar.digital' in site or 'licitardigital' in site:
            return 'Licitar Digital'
        if 'portaldecompraspublicas' in site:
            return 'Compras Públicas'
        if 'bec.sp.gov.br' in site:
            return 'BEC SP'
        if 'licitacoes-e' in site:
            return 'Licitações-e'
        if site:
            # Extrair domínio
            domain = site.split('//')[1].split('/')[0] if '//' in site else site
            return domain
        return 'Conlicitação'
    
    def _mapear(self, bid: Dict) -> Optional[Dict]:
        """Mapeia bidding Conlicitação → formato GSM."""
        try:
            bid_id = bid.get('id') or bid.get('bidding_id', '')
            objeto_raw = bid.get('objeto', '')
            objeto = self._strip_html(objeto_raw)
            itens_raw = bid.get('itens', '')
            itens_text = self._strip_html(itens_raw)
            
            orgao = ''
            if bid.get('public_body'):
                orgao = bid['public_body'].get('nome', '')
            if not orgao:
                orgao = bid.get('observacao', '').split('Órgão:')[-1].strip()[:100] if 'Órgão:' in bid.get('observacao', '') else ''
            
            cidade = bid.get('orgao_cidade', '')
            estado = bid.get('orgao_estado', '')
            edital_num = bid.get('edital', '')
            modalidade = ''
            if bid.get('modality'):
                modalidade = bid['modality'].get('nome', '')
            
            data_abertura = bid.get('datahora_abertura') or bid.get('datahora_documento', '')
            data_final = bid.get('data_validade') or bid.get('datahora_prazo') or data_abertura
            valor = bid.get('valor_estimado') or 0
            
            # Portal de origem
            portal = self._detect_portal(bid)
            portal_nome = f"{portal} ({estado})" if estado else portal
            
            # Link do portal
            link_portal = bid.get('edital_site') or ''
            if not link_portal:
                link_portal = f"https://consulteonline.conlicitacao.com.br/licitacao/{bid_id}"
            
            # PDF download
            link_pdf = ''
            edicts = bid.get('edicts') or []
            if edicts:
                first = edicts[0]
                url_path = first.get('url', '')
                if url_path:
                    link_pdf = f"{self.BASE_URL}{url_path}"
            
            id_gsm = f"CON-{bid_id}"
            
            return {
                'id': id_gsm,
                'id_gsm': id_gsm,
                'id_externo': str(bid_id),
                'numero_controle_pncp': edital_num,
                'fonte': 'CONLICITACAO',
                'fonte_origem': 'CONLICITACAO',
                'portal_captura': portal_nome,
                'objeto': objeto,
                'descricao': objeto,
                'orgao': orgao,
                'orgao_nome': orgao,
                'uf': estado,
                'municipio': cidade,
                'modalidade': modalidade,
                'numero_edital': edital_num,
                'data_publicacao': data_abertura,
                'data_abertura': data_abertura,
                'data_final': data_final,
                'valor_estimado': valor,
                'link_portal': link_portal,
                'link_pdf': link_pdf,
                'itens': itens_text,
                'itens_correspondentes': [i.strip() for i in itens_text.split('\n') if i.strip()][:10],
                'is_saude': True,
                'ativo': True
            }
        except Exception as e:
            logger.error(f"Conlicitação mapeamento: {e}")
            return None
