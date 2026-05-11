"""
Effecti Proxy Service v74.2
=============================
Proxy de busca em tempo real via API do Effecti.

Enquanto temos acesso à API, usamos ela como fonte principal.
Quando o operador busca "canabidiol", o GSM:
1. Faz login na API Effecti
2. Busca TODOS os avisos do perfil
3. Filtra por keyword localmente
4. Retorna resultados com links corretos (url do portal)

Este proxy será substituído por scrapers independentes no futuro.
"""

import asyncio
import aiohttp
import logging
import hashlib
from typing import List, Dict, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class EffectiProxyService:
    
    BASE_URL = "https://mdw.minha.effecti.com.br"
    USERNAME = "claudio@gruposmartmedical.com.br"
    PASSWORD = "Mj@08080808"
    
    def __init__(self):
        self.token = None
        self.timeout = aiohttp.ClientTimeout(total=30)
        self._cache_avisos = []
        self._cache_timestamp = None
        self._cache_ttl = 900  # 15 minutos
        self._loading = False
        self._load_task = None
    
    async def inicializar(self):
        """Inicia carregamento em background na inicialização do servidor."""
        if not self._loading:
            self._loading = True
            self._load_task = asyncio.create_task(self._carregar_background())
    
    async def _carregar_background(self):
        """Carrega todos os avisos em background."""
        try:
            avisos = await self._buscar_todos_avisos()
            if avisos:
                self._cache_avisos = avisos
                self._cache_timestamp = datetime.now(timezone.utc)
                logger.info(f"Effecti proxy: cache carregado com {len(avisos)} avisos em background")
        except Exception as e:
            logger.error(f"Effecti proxy background load error: {e}")
        finally:
            self._loading = False
    
    async def _login(self, session: aiohttp.ClientSession) -> bool:
        """Login na API Effecti."""
        try:
            resp = await session.post(
                f"{self.BASE_URL}/users/login",
                json={"username": self.USERNAME, "password": self.PASSWORD},
                headers={"Content-Type": "application/json"}
            )
            if resp.status == 200:
                data = await resp.json()
                self.token = data.get("token")
                return bool(self.token)
        except Exception as e:
            logger.error(f"Effecti login error: {e}")
        return False
    
    async def buscar(self, termo: str, limit: int = 50) -> Dict:
        """
        Busca em tempo real via API Effecti.
        Filtra por keyword e retorna apenas editais com data futura.
        """
        try:
            avisos = await self._obter_avisos_cache()
            
            if not avisos:
                return {'resultados': [], 'total': 0, 'fonte': 'EFFECTI_PROXY'}
            
            # Filtrar por keyword(s)
            termos = [t.strip().lower() for t in termo.split(',') if t.strip()]
            
            filtrados = []
            for aviso in avisos:
                objeto = (aviso.get('objeto', '') or '').lower()
                # Verificar se item descriptions contém o termo também
                itens_text = ' '.join(
                    (item.get('descricao', '') or '').lower() 
                    for item in (aviso.get('item', []) or [])
                )
                texto_completo = f"{objeto} {itens_text}"
                
                if any(t in texto_completo for t in termos):
                    resultado = self._mapear_aviso(aviso)
                    if resultado:
                        filtrados.append(resultado)
            
            # Filtrar apenas data futura
            hoje = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M')
            ativos = []
            for r in filtrados:
                data_final = r.get('data_final', '')
                if not data_final:
                    ativos.append(r)
                elif str(data_final) >= hoje[:10]:
                    ativos.append(r)
            
            # Ordenar por data (mais próximas primeiro)
            ativos.sort(key=lambda x: x.get('data_final', '') or '9999', reverse=False)
            
            return {
                'resultados': ativos[:limit],
                'total': len(ativos),
                'fonte': 'EFFECTI_PROXY'
            }
        
        except Exception as e:
            logger.error(f"Effecti proxy buscar error: {e}")
            return {'resultados': [], 'total': 0, 'fonte': 'EFFECTI_PROXY'}
    
    async def _obter_avisos_cache(self) -> List[Dict]:
        """Obtém avisos do cache. Retorna vazio se cache não estiver pronto."""
        if self._cache_avisos:
            return self._cache_avisos
        # Cache não pronto (carregando em background) - retorna vazio
        return []
    
    async def _buscar_todos_avisos(self) -> List[Dict]:
        """Busca TODOS os avisos da API Effecti (todas as páginas)."""
        todos = []
        
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                if not await self._login(session):
                    logger.error("Effecti login failed")
                    return []
                
                headers = {
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json"
                }
                
                # Buscar primeira página para saber o total
                payload = {
                    "pagina": 0,
                    "interesse": True,
                    "favorito": False,
                    "orgaoFavorito": False,
                    "distribuidores": False,
                    "id": "",
                    "deserto": False,
                    "ordem": [{"orderBy": "dataFinal"}, {"order": "desc"}],
                    "tipo": []
                }
                
                resp = await session.post(
                    f"{self.BASE_URL}/aviso/minhas",
                    json=payload, headers=headers
                )
                
                if resp.status != 200:
                    return []
                
                data = await resp.json()
                total = data.get('recordsTotal', 0)
                avisos_page = data.get('data', [])
                todos.extend(avisos_page)
                
                # Calcular total de páginas (15 por página)
                total_pages = (total // 15) + 1
                
                # Carregar TODAS as páginas (clone completo do Effecti)
                max_pages = total_pages
                logger.info(f"Effecti proxy: carregando {max_pages} paginas ({total} avisos)...")
                
                for pg in range(1, max_pages):
                    try:
                        payload["pagina"] = pg
                        resp = await session.post(
                            f"{self.BASE_URL}/aviso/minhas",
                            json=payload, headers=headers
                        )
                        if resp.status == 200:
                            data = await resp.json()
                            avisos_page = data.get('data', [])
                            if not avisos_page:
                                break
                            todos.extend(avisos_page)
                    except Exception:
                        continue
                
                logger.info(f"Effecti proxy: {len(todos)} avisos carregados de {total} total")
        
        except Exception as e:
            logger.error(f"Effecti proxy fetch error: {e}")
        
        return todos
    
    def _mapear_aviso(self, aviso: Dict) -> Optional[Dict]:
        """Mapeia aviso Effecti para formato GSM."""
        try:
            aviso_id = str(aviso.get('id', ''))
            id_gsm = hashlib.md5(f"EFFECTI-{aviso_id}".encode()).hexdigest()
            
            portal = aviso.get('portalNome', '') or ''
            uasg_nome = aviso.get('uasgNome', '') or ''
            uasg = str(aviso.get('uasg', ''))
            uf = aviso.get('uf', '') or ''
            objeto = (aviso.get('objeto', '') or '').upper()
            pregao = aviso.get('pregao', '') or ''
            
            # URL DO PORTAL (a regra do Effecti - é isso que o botão "Edital" usa)
            url_portal = aviso.get('url', '') or ''
            # Fix: Converter /compras/ para /editais/ em URLs PNCP (página com PDFs)
            if 'pncp.gov.br/app/compras/' in url_portal:
                url_portal = url_portal.replace('/app/compras/', '/app/editais/')
            
            # Extrair link PDF dos anexos (para download direto, se disponível)
            link_pdf = None
            for anexo in (aviso.get('anexo', []) or []):
                nome = (anexo.get('nome', '') or '').lower()
                a_url = anexo.get('url', '')
                if a_url and ('edital' in nome or '.pdf' in nome):
                    link_pdf = a_url
                    break
            if not link_pdf:
                for anexo in (aviso.get('anexo', []) or []):
                    if anexo.get('url'):
                        link_pdf = anexo['url']
                        break
            
            # Formatar datas (Effecti usa formato "DD/MM/YYYY HH:MM:SS")
            data_inicial = aviso.get('dataInicial', '') or ''
            data_final = aviso.get('dataFinal', '') or ''
            data_pub = aviso.get('dataPublicacao', '') or ''
            
            # Converter DD/MM/YYYY para YYYY-MM-DD para ordenação
            def normalizar_data(d):
                if not d:
                    return ''
                try:
                    if '/' in str(d):
                        parts = str(d).split(' ')[0].split('/')
                        if len(parts) == 3:
                            return f"{parts[2]}-{parts[1]}-{parts[0]}T{str(d).split(' ')[1] if ' ' in str(d) else '00:00:00'}"
                    return str(d)
                except:
                    return str(d)
            
            # Formatar itens
            itens = []
            for item in (aviso.get('item', []) or []):
                itens.append({
                    "grupo": str(item.get('grupo', '')),
                    "numero": str(item.get('numero', '')) if item.get('numero') else '',
                    "descricao": item.get('descricao', ''),
                    "exclusivo_me_epp": item.get('exclusivoMeEpp', -1),
                    "quantidade": str(item.get('quantidade', '')),
                    "unidade": item.get('unidade', ''),
                    "valor_total": item.get('valorTotal'),
                    "valor_unitario": item.get('valorUnitario')
                })
            
            # Anexos
            anexos = [
                {"nome": a.get('nome', ''), "url": a.get('url', '')}
                for a in (aviso.get('anexo', []) or []) if a.get('url')
            ]
            
            return {
                'id': id_gsm,
                'id_gsm': id_gsm,
                'id_externo': aviso_id,
                'fonte': portal,
                'fonte_origem': 'EFFECTI_PROXY',
                'portal_captura': portal,
                'objeto': objeto,
                'orgao': uasg_nome,
                'dados_orgao': {
                    'uasg': uasg,
                    'nome': uasg_nome,
                    'uf': uf
                },
                'estado': uf,
                'uf': uf,
                'municipio': '',
                'uasg': uasg,
                'modalidade': aviso.get('tipo', 'Pregão Eletrônico'),
                'status': 'ABERTA',
                'data_publicacao': normalizar_data(data_pub),
                'data_abertura': normalizar_data(data_final),
                'data_inicial': normalizar_data(data_inicial),
                'data_final': normalizar_data(data_final),
                # LINK DO PORTAL (como o Effecti faz)
                'link_documento': url_portal,
                'link_portal': url_portal,
                'link_origem': url_portal,
                'link_edital': url_portal,
                'link_pdf': link_pdf,
                'numero_processo': pregao,
                'numero_licitacao': pregao,
                'itens_clonados': itens,
                'anexos': anexos,
                'valor_total_estimado': aviso.get('valorTotalEstimado'),
                'is_saude': True,  # Veio do perfil de saúde
                'link_status': 'VALIDO'
            }
        
        except Exception as e:
            logger.error(f"Erro mapeando aviso Effecti: {e}")
            return None
