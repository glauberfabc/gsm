"""
ComprasNet Search Service - Busca em Tempo Real no Portal de Compras do Governo Federal
========================================================================================

🎯 OBJETIVO: Integrar dados do ComprasNet/SIASG para encontrar licitações como "Prolia"
que não estão disponíveis no PNCP.

FONTES:
1. API de Dados Abertos: https://dadosabertos.compras.gov.br
2. Portal CnetMobile (SERPRO): https://cnetmobile.estaleiro.serpro.gov.br

ENDPOINTS PRINCIPAIS:
- /modulo-compras/1_consultarCompras - Busca geral
- /modulo-compras/2_consultarDetalheCompra - Detalhes
- /modulo-materiais/1_consultarMaterial - Materiais por descrição
"""

import asyncio
import logging
import re
import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
import hashlib

logger = logging.getLogger(__name__)


class ComprasNetSearchService:
    """
    Serviço de busca em tempo real no ComprasNet (Portal de Compras Governamentais)
    """
    
    def __init__(self):
        self.base_url_dados_abertos = "https://dadosabertos.compras.gov.br"
        self.base_url_cnetmobile = "https://cnetmobile.estaleiro.serpro.gov.br"
        self.timeout = 30
        
        # Headers para requisições
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'pt-BR,pt;q=0.9',
        }
        
        # UASGs prioritários de saúde (Federal)
        self.uasgs_saude = [
            {'uasg': '250001', 'nome': 'Ministério da Saúde', 'uf': 'DF'},
            {'uasg': '250005', 'nome': 'Secretaria de Atenção à Saúde', 'uf': 'DF'},
            {'uasg': '153153', 'nome': 'Fiocruz - RJ', 'uf': 'RJ'},
            {'uasg': '153154', 'nome': 'Fiocruz - BA', 'uf': 'BA'},
            {'uasg': '153166', 'nome': 'Fiocruz - PE', 'uf': 'PE'},
            {'uasg': '153157', 'nome': 'Fiocruz - MG', 'uf': 'MG'},
            {'uasg': '989915', 'nome': 'Hospital das Clínicas - SP', 'uf': 'SP'},
            {'uasg': '153165', 'nome': 'Hospital Universitário - UFRJ', 'uf': 'RJ'},
            {'uasg': '982921', 'nome': 'Prefeitura Rio das Ostras', 'uf': 'RJ'},  # Prolia encontrado aqui!
        ]
    
    async def buscar_por_termo(
        self,
        termo: str,
        limite: int = 50,
        apenas_ativas: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Busca licitações no ComprasNet por termo
        
        Estratégia em 2 etapas:
        1. Buscar via API de dados abertos (materiais)
        2. Buscar via CnetMobile (compras recentes)
        
        Args:
            termo: Termo de busca (ex: "prolia", "denosumabe")
            limite: Número máximo de resultados
            apenas_ativas: Filtrar apenas licitações ativas
            
        Returns:
            Lista de editais normalizados
        """
        resultados = []
        
        logger.info(f"🔍 [ComprasNet] Iniciando busca por '{termo}'")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
                # ETAPA 1: Buscar via CnetMobile (mais rápido e atual)
                resultados_cnet = await self._buscar_cnetmobile(client, termo, limite)
                resultados.extend(resultados_cnet)
                
                # ETAPA 2: Buscar via dados abertos (complementar)
                if len(resultados) < limite:
                    resultados_dados = await self._buscar_dados_abertos(client, termo, limite - len(resultados))
                    resultados.extend(resultados_dados)
                
                # ETAPA 3: Buscar em UASGs de saúde específicos
                if len(resultados) < limite:
                    resultados_uasg = await self._buscar_em_uasgs_saude(client, termo, limite - len(resultados))
                    resultados.extend(resultados_uasg)
                
        except Exception as e:
            logger.error(f"❌ [ComprasNet] Erro geral: {e}")
        
        # Deduplicar
        resultados_unicos = self._deduplicar(resultados)
        
        # Filtrar apenas ativas se solicitado
        if apenas_ativas:
            resultados_unicos = [
                r for r in resultados_unicos
                if r.get('status_oportunidade') == 'ATIVA' or self._is_ativa(r)
            ]
        
        logger.info(f"✅ [ComprasNet] {len(resultados_unicos)} resultados para '{termo}'")
        
        return resultados_unicos[:limite]
    
    async def _buscar_cnetmobile(
        self,
        client: httpx.AsyncClient,
        termo: str,
        limite: int
    ) -> List[Dict]:
        """
        Busca via CnetMobile (Portal interativo SERPRO)
        
        URL: https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/public/compras
        """
        resultados = []
        
        try:
            # Endpoint de busca pública
            url = f"{self.base_url_cnetmobile}/comprasnet-web/public/api/v1/compras"
            
            # Parâmetros de busca
            params = {
                'descricao': termo,
                'pagina': 1,
                'tamanhoPagina': min(limite, 50)
            }
            
            logger.info(f"  📡 [CnetMobile] Buscando em {url}")
            
            response = await client.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                compras = data.get('compras', []) or data.get('resultado', []) or data.get('_embedded', {}).get('compras', [])
                
                for compra in compras:
                    edital = self._normalizar_compra_cnetmobile(compra, termo)
                    if edital:
                        resultados.append(edital)
                
                logger.info(f"  ✅ [CnetMobile] {len(resultados)} resultados")
            else:
                logger.warning(f"  ⚠️ [CnetMobile] Status {response.status_code}")
                
        except httpx.TimeoutException:
            logger.warning("  ⏱️ [CnetMobile] Timeout")
        except Exception as e:
            logger.debug(f"  ⚠️ [CnetMobile] Erro: {e}")
        
        return resultados
    
    async def _buscar_dados_abertos(
        self,
        client: httpx.AsyncClient,
        termo: str,
        limite: int
    ) -> List[Dict]:
        """
        Busca via API de Dados Abertos do ComprasNet
        
        Endpoints:
        - /modulo-materiais/1_consultarMaterial - Busca por descrição de material
        - /modulo-compras/1_consultarCompras - Busca geral
        """
        resultados = []
        
        try:
            # Buscar materiais relacionados ao termo
            url_materiais = f"{self.base_url_dados_abertos}/modulo-materiais/1_consultarMaterial"
            
            params = {
                'descricao': termo,
                'pagina': 1
            }
            
            logger.info(f"  📡 [DadosAbertos] Buscando materiais '{termo}'")
            
            response = await client.get(url_materiais, params=params)
            
            if response.status_code == 200:
                data = response.json()
                materiais = data.get('materiais', []) or data.get('resultado', [])
                
                # Para cada material, buscar compras associadas
                for material in materiais[:5]:  # Limitar para evitar muitas requisições
                    codigo_material = material.get('codigoItemCatalogo') or material.get('codigo')
                    
                    if codigo_material:
                        compras = await self._buscar_compras_por_material(client, codigo_material)
                        for compra in compras[:limite]:
                            edital = self._normalizar_compra_dados_abertos(compra, termo)
                            if edital:
                                resultados.append(edital)
                
                logger.info(f"  ✅ [DadosAbertos] {len(resultados)} resultados")
            else:
                logger.debug(f"  ⚠️ [DadosAbertos] Status {response.status_code}")
                
        except httpx.TimeoutException:
            logger.warning("  ⏱️ [DadosAbertos] Timeout")
        except Exception as e:
            logger.debug(f"  ⚠️ [DadosAbertos] Erro: {e}")
        
        return resultados
    
    async def _buscar_compras_por_material(
        self,
        client: httpx.AsyncClient,
        codigo_material: str
    ) -> List[Dict]:
        """Busca compras associadas a um código de material"""
        try:
            url = f"{self.base_url_dados_abertos}/modulo-compras/1_consultarCompras"
            
            params = {
                'codigoItemCatalogo': codigo_material,
                'ano': datetime.now().year,
                'pagina': 1
            }
            
            response = await client.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('compras', []) or []
        except Exception:
            pass
        
        return []
    
    async def _buscar_em_uasgs_saude(
        self,
        client: httpx.AsyncClient,
        termo: str,
        limite: int
    ) -> List[Dict]:
        """
        Busca em UASGs de saúde específicos
        
        Foca em órgãos que frequentemente licitam medicamentos como Prolia/Denosumabe
        """
        resultados = []
        ano_atual = datetime.now().year
        
        try:
            for uasg_info in self.uasgs_saude:
                if len(resultados) >= limite:
                    break
                
                uasg = uasg_info['uasg']
                
                url = f"{self.base_url_dados_abertos}/modulo-compras/1_consultarCompras"
                
                params = {
                    'ano': ano_atual,
                    'codigoUasg': uasg,
                    'pagina': 1
                }
                
                try:
                    response = await client.get(url, params=params, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        compras = data.get('compras', []) or data.get('resultado', [])
                        
                        for compra in compras:
                            objeto = (compra.get('objeto') or compra.get('descricao') or '').lower()
                            
                            # Verificar se o termo está presente
                            if termo.lower() in objeto:
                                edital = self._normalizar_compra_dados_abertos(compra, termo)
                                if edital:
                                    edital['orgao'] = uasg_info['nome']
                                    edital['uasg'] = uasg
                                    edital['uf'] = uasg_info['uf']
                                    resultados.append(edital)
                    
                    await asyncio.sleep(0.5)  # Rate limiting
                    
                except Exception as e:
                    logger.debug(f"  ⚠️ UASG {uasg}: {e}")
                
            logger.info(f"  ✅ [UASGs Saúde] {len(resultados)} resultados")
            
        except Exception as e:
            logger.debug(f"  ⚠️ [UASGs Saúde] Erro: {e}")
        
        return resultados
    
    def _normalizar_compra_cnetmobile(self, compra: Dict, termo: str) -> Optional[Dict]:
        """Normaliza dados do CnetMobile para formato padrão"""
        try:
            objeto = compra.get('objeto') or compra.get('descricao', '')
            
            # Gerar IDs
            uasg = str(compra.get('codigoUasg') or compra.get('uasg', ''))
            ano = compra.get('ano', datetime.now().year)
            sequencial = compra.get('sequencial') or compra.get('numeroCompra', '')
            
            id_externo = f"comprasnet-{uasg}-{ano}-{sequencial}"
            hash_dedup = hashlib.md5(id_externo.encode()).hexdigest()
            
            # Datas
            data_publicacao = self._parse_date(compra.get('dataPublicacao'))
            data_abertura = self._parse_date(compra.get('dataAbertura') or compra.get('dataAberturaProposta'))
            data_final = self._parse_date(compra.get('dataEncerramentoProposta') or compra.get('dataLimiteRecebimentoProposta'))
            
            # Links
            link_sistema = compra.get('linkSistemaOrigem') or compra.get('link')
            link_edital = self._construir_link_comprasnet(uasg, ano, sequencial)
            
            return {
                'id_externo': id_externo,
                'numero_controle_pncp': None,
                'hash_dedup': hash_dedup,
                'objeto': objeto,
                'orgao': compra.get('nomeOrgao') or compra.get('orgao', 'ComprasNet'),
                'orgao_cnpj': compra.get('cnpjOrgao'),
                'uasg': uasg,
                'uf': compra.get('uf', ''),
                'municipio': compra.get('municipio', ''),
                'esfera': 'Federal',
                'modalidade': compra.get('modalidade', 'Pregão Eletrônico'),
                'numero_processo': f"{ano}/{sequencial}",
                'data_publicacao': data_publicacao.isoformat() if data_publicacao else None,
                'data_abertura': data_abertura.isoformat() if data_abertura else None,
                'data_final': data_final.isoformat() if data_final else None,
                'link_edital': link_edital,
                'link_sistema_origem': link_sistema,
                'link_status': 'VALIDO' if link_edital else 'INVALIDO',
                'tipo_link': 'comprasnet',
                'fonte': 'ComprasNet',
                'status_oportunidade': self._classificar_status(data_final),
                'is_saude': True,
                'quality_score': 85,
                'itens_edital': [],
                '_termo_match': termo
            }
            
        except Exception as e:
            logger.debug(f"Erro ao normalizar CnetMobile: {e}")
            return None
    
    def _normalizar_compra_dados_abertos(self, compra: Dict, termo: str) -> Optional[Dict]:
        """Normaliza dados da API de Dados Abertos para formato padrão"""
        try:
            objeto = compra.get('objeto') or compra.get('descricao', '')
            
            uasg = str(compra.get('codigoUasg') or compra.get('uasg', ''))
            ano = compra.get('ano', datetime.now().year)
            sequencial = compra.get('sequencial') or compra.get('numeroCompra', '')
            
            id_externo = f"comprasnet-{uasg}-{ano}-{sequencial}"
            hash_dedup = hashlib.md5(id_externo.encode()).hexdigest()
            
            data_publicacao = self._parse_date(compra.get('dataPublicacao'))
            data_abertura = self._parse_date(compra.get('dataAbertura'))
            data_final = self._parse_date(compra.get('dataEncerramento') or compra.get('dataFim'))
            
            link_edital = self._construir_link_comprasnet(uasg, ano, sequencial)
            
            return {
                'id_externo': id_externo,
                'numero_controle_pncp': None,
                'hash_dedup': hash_dedup,
                'objeto': objeto,
                'orgao': compra.get('nomeOrgao', 'ComprasNet'),
                'orgao_cnpj': compra.get('cnpjOrgao'),
                'uasg': uasg,
                'uf': compra.get('uf', ''),
                'municipio': '',
                'esfera': 'Federal',
                'modalidade': compra.get('descricaoModalidade', 'Pregão Eletrônico'),
                'numero_processo': f"{ano}/{sequencial}",
                'data_publicacao': data_publicacao.isoformat() if data_publicacao else None,
                'data_abertura': data_abertura.isoformat() if data_abertura else None,
                'data_final': data_final.isoformat() if data_final else None,
                'link_edital': link_edital,
                'link_sistema_origem': None,
                'link_status': 'VALIDO' if link_edital else 'INVALIDO',
                'tipo_link': 'comprasnet',
                'fonte': 'ComprasNet',
                'status_oportunidade': self._classificar_status(data_final),
                'is_saude': True,
                'quality_score': 80,
                'itens_edital': [],
                '_termo_match': termo
            }
            
        except Exception as e:
            logger.debug(f"Erro ao normalizar DadosAbertos: {e}")
            return None
    
    def _construir_link_comprasnet(self, uasg: str, ano: int, sequencial: str) -> str:
        """Constrói link para o portal ComprasNet"""
        if uasg and sequencial:
            return f"https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/public/landing?codigoUasg={uasg}&numeroCompra={sequencial}&ano={ano}"
        return ""
    
    def _parse_date(self, date_str: Any) -> Optional[datetime]:
        """Converte string de data para datetime"""
        if not date_str:
            return None
        
        if isinstance(date_str, datetime):
            return date_str
        
        try:
            for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d/%m/%Y', '%d/%m/%Y %H:%M']:
                try:
                    return datetime.strptime(str(date_str), fmt)
                except ValueError:
                    continue
            return datetime.fromisoformat(str(date_str).replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            return None
    
    def _classificar_status(self, data_final: Optional[datetime]) -> str:
        """Classifica status da oportunidade"""
        if not data_final:
            return 'ATIVA'
        
        agora = datetime.now()
        if isinstance(data_final, str):
            data_final = self._parse_date(data_final)
        
        if data_final and data_final > agora:
            return 'ATIVA'
        return 'ENCERRADA'
    
    def _is_ativa(self, edital: Dict) -> bool:
        """Verifica se edital está ativo"""
        data_final = edital.get('data_final')
        if not data_final:
            return True
        
        if isinstance(data_final, str):
            data_final = self._parse_date(data_final)
        
        return data_final and data_final > datetime.now()
    
    def _deduplicar(self, resultados: List[Dict]) -> List[Dict]:
        """Remove duplicatas baseado em hash_dedup"""
        vistos = set()
        unicos = []
        
        for r in resultados:
            h = r.get('hash_dedup')
            if h and h not in vistos:
                vistos.add(h)
                unicos.append(r)
        
        return unicos


# Singleton
_comprasnet_search_instance = None

def get_comprasnet_search() -> ComprasNetSearchService:
    """Retorna instância singleton do serviço"""
    global _comprasnet_search_instance
    if _comprasnet_search_instance is None:
        _comprasnet_search_instance = ComprasNetSearchService()
    return _comprasnet_search_instance
