"""
Preços Service - GSM Buscador de Editais v44.0

Serviço para consulta de preços históricos do PNCP (24 meses).

Funcionalidades:
- Integração com API PNCP de itens homologados
- Agregação: Menor, Maior, Média
- Cache MongoDB com validade de 15 dias
- Dashboard de inteligência de preços
- Filtragem por relevância (sinônimos de medicamentos)
- Agrupamento por apresentação (dosagem/mg)

Endpoint PNCP: https://pncp.gov.br/api/consulta/v1/contratacoes/item
"""

import os
import logging
import httpx
import asyncio
import unicodedata
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
import statistics
import re

logger = logging.getLogger(__name__)

# Configuração PNCP
PNCP_BASE_URL = "https://pncp.gov.br/api/consulta/v1"
PNCP_ITENS_URL = f"{PNCP_BASE_URL}/contratacoes/itens"
CACHE_VALIDADE_DIAS = 15

# Importar mapeamento de sinônimos da busca
from services.busca_service_v2 import EXPANSAO_TERMOS_SAUDE


@dataclass
class PrecoItem:
    """Item de preço individual"""
    orgao: str
    uf: str
    municipio: str
    descricao: str
    quantidade: float
    unidade: str
    valor_unitario: float
    valor_total: float
    data_homologacao: str
    modalidade: str
    numero_processo: str
    fonte: str = "PNCP"


@dataclass 
class ResumoPrecos:
    """Resumo agregado de preços"""
    termo_pesquisado: str
    total_registros: int
    preco_minimo: float
    preco_maximo: float
    preco_medio: float
    preco_mediana: float
    desvio_padrao: float
    data_mais_antiga: str
    data_mais_recente: str
    itens: List[PrecoItem]


@dataclass
class ApresentacaoPrecos:
    """Grupo de preços por apresentação (dosagem)"""
    apresentacao: str  # ex: "DENOSUMABE 60MG", "DENOSUMABE 120MG"
    total_registros: int
    preco_minimo: float
    preco_maximo: float
    preco_medio: float
    preco_mediana: float
    itens: List[PrecoItem]
    tendencia: List[Dict] = field(default_factory=list)  # [{mes: "2025-01", medio: 800, min: 700, max: 900, qtd: 5}]


class PrecosService:
    """
    Serviço de consulta de preços históricos.
    
    Integra com PNCP e mantém cache local no MongoDB.
    v44: Filtragem por relevância + agrupamento por apresentação.
    """
    
    def __init__(self, db):
        self.db = db
        self.cache_collection = db.precos_cache
        self.http_client = None
    
    async def _get_http_client(self):
        """Retorna cliente HTTP reutilizável"""
        if self.http_client is None:
            self.http_client = httpx.AsyncClient(timeout=60.0)
        return self.http_client
    
    def _normalizar_texto(self, texto: str) -> str:
        """Remove acentos, tags HTML e converte para minúsculo"""
        if not texto:
            return ""
        # Remover tags HTML
        texto = re.sub(r'<[^>]+>', ' ', texto)
        texto = re.sub(r'&[a-z]+;', ' ', texto)
        texto = unicodedata.normalize('NFKD', texto)
        texto = ''.join(c for c in texto if not unicodedata.combining(c))
        return texto.lower().strip()
    
    def _expandir_termos(self, termo: str) -> Set[str]:
        """Expande termo usando sinônimos do domínio saúde"""
        termos = set()
        termo_norm = self._normalizar_texto(termo)
        termos.add(termo_norm)
        
        # Buscar cada palavra do termo
        palavras = termo_norm.split()
        for palavra in palavras:
            termos.add(palavra)
        
        # Buscar sinônimos
        for chave, expansoes in EXPANSAO_TERMOS_SAUDE.items():
            chave_norm = self._normalizar_texto(chave)
            if chave_norm in termo_norm or termo_norm in chave_norm:
                termos.add(chave_norm)
                for exp in expansoes:
                    termos.add(self._normalizar_texto(exp))
        
        # Buscar também se o termo está nas expansões
        for chave, expansoes in EXPANSAO_TERMOS_SAUDE.items():
            for exp in expansoes:
                if self._normalizar_texto(exp) in termo_norm or termo_norm in self._normalizar_texto(exp):
                    termos.add(self._normalizar_texto(chave))
                    for e in expansoes:
                        termos.add(self._normalizar_texto(e))
        
        # Remover termos muito genéricos
        termos.discard('')
        logger.info(f"[PREÇOS] Termos expandidos para '{termo}': {termos}")
        return termos
    
    def _item_relevante(self, descricao: str, termos_expandidos: Set[str]) -> bool:
        """Verifica se a descrição do item é relevante para os termos buscados"""
        desc_norm = self._normalizar_texto(descricao)
        if not desc_norm:
            return False
        
        for termo in termos_expandidos:
            if len(termo) >= 3 and termo in desc_norm:
                return True
        return False
    
    def _extrair_apresentacao(self, descricao: str) -> str:
        """
        Extrai a apresentação (dosagem/concentração) da descrição.
        Normaliza variantes comuns para agrupar corretamente.
        """
        desc_norm = self._normalizar_texto(descricao)
        
        # Padrões de dosagem comuns - ordem importa (mais específico primeiro)
        padroes = [
            r'(\d+[\.,]?\d*)\s*mg/ml',     # 60mg/ml
            r'(\d+[\.,]?\d*)\s*ui/ml',      # 5000ui/ml
            r'(\d+[\.,]?\d*)\s*mcg/ml',     # 100mcg/ml
            r'(\d+[\.,]?\d*)\s*mg',          # 60mg
            r'(\d+[\.,]?\d*)\s*mcg',         # 120mcg
            r'(\d+[\.,]?\d*)\s*ui',          # 5000ui
            r'(\d+[\.,]?\d*)\s*g\b',         # 5g
        ]
        
        for padrao in padroes:
            match = re.search(padrao, desc_norm)
            if match:
                valor = match.group(1).replace(',', '.')
                # Determinar unidade
                if 'mg/ml' in desc_norm[match.start():match.end()+5]:
                    return f"{valor}MG/ML"
                elif 'ui/ml' in desc_norm[match.start():match.end()+5]:
                    return f"{valor}UI/ML"
                elif 'mcg/ml' in desc_norm[match.start():match.end()+6]:
                    return f"{valor}MCG/ML"
                elif 'mcg' in desc_norm[match.start():match.end()+4]:
                    return f"{valor}MCG"
                elif 'ui' in desc_norm[match.start():match.end()+3]:
                    return f"{valor}UI"
                elif 'g' == desc_norm[match.end():match.end()+1]:
                    return f"{valor}G"
                else:
                    return f"{valor}MG"
        
        return "SEM DOSAGEM"
    
    def _identificar_principio_ativo(self, descricao: str, termos_expandidos: Set[str]) -> str:
        """Identifica o princípio ativo do item a partir da descrição"""
        desc_norm = self._normalizar_texto(descricao)
        
        # Verificar qual sinônimo aparece na descrição
        for termo in termos_expandidos:
            if len(termo) >= 4 and termo in desc_norm:
                return termo.upper()
        
        # Fallback: primeira palavra significativa
        palavras = desc_norm.split()
        for p in palavras:
            if len(p) >= 4:
                return p.upper()
        return "OUTROS"
    
    def agrupar_por_apresentacao(self, itens: List[PrecoItem], termos_expandidos: Set[str]) -> List[ApresentacaoPrecos]:
        """Agrupa itens por apresentação (dosagem) e calcula estatísticas.
        Filtra outliers extremos que distorcem médias."""
        grupos = {}
        
        for item in itens:
            principio = self._identificar_principio_ativo(item.descricao, termos_expandidos)
            dosagem = self._extrair_apresentacao(item.descricao)
            chave = f"{principio} {dosagem}"
            
            if chave not in grupos:
                grupos[chave] = []
            grupos[chave].append(item)
        
        apresentacoes = []
        for nome, itens_grupo in sorted(grupos.items()):
            valores = [it.valor_unitario for it in itens_grupo if it.valor_unitario > 0]
            if not valores:
                continue
            
            # Filtrar outliers: remover valores > 10x a mediana (provável valor total do contrato)
            if len(valores) >= 3:
                mediana = statistics.median(valores)
                if mediana > 0:
                    valores_filtrados = [v for v in valores if v <= mediana * 10]
                    itens_filtrados = [it for it in itens_grupo if it.valor_unitario <= mediana * 10]
                    if valores_filtrados:
                        valores = valores_filtrados
                        itens_grupo = itens_filtrados
            
            # Calcular tendência mensal
            tendencia = self._calcular_tendencia_mensal(itens_grupo)
            
            apresentacoes.append(ApresentacaoPrecos(
                apresentacao=nome,
                total_registros=len(itens_grupo),
                preco_minimo=round(min(valores), 2),
                preco_maximo=round(max(valores), 2),
                preco_medio=round(statistics.mean(valores), 2),
                preco_mediana=round(statistics.median(valores), 2),
                itens=sorted(itens_grupo, key=lambda x: x.valor_unitario),
                tendencia=tendencia
            ))
        
        # Ordenar por número de registros (mais relevantes primeiro)
        apresentacoes.sort(key=lambda x: x.total_registros, reverse=True)
        
        return apresentacoes
    
    def _calcular_tendencia_mensal(self, itens: List[PrecoItem]) -> List[Dict]:
        """Agrupa preços por mês e calcula média/min/max mensal para gráfico de tendência"""
        meses_data = {}
        
        for item in itens:
            data = (item.data_homologacao or '')[:7]  # "2025-01"
            if len(data) < 7:
                continue
            
            if data not in meses_data:
                meses_data[data] = []
            meses_data[data].append(item.valor_unitario)
        
        tendencia = []
        for mes in sorted(meses_data.keys()):
            valores = meses_data[mes]
            tendencia.append({
                "mes": mes,
                "medio": round(statistics.mean(valores), 2),
                "min": round(min(valores), 2),
                "max": round(max(valores), 2),
                "qtd": len(valores)
            })
        
        return tendencia
    
    async def buscar_precos(
        self, 
        termo: str, 
        uf: str = None,
        limit: int = 100,
        use_cache: bool = True,
        meses: int = 24
    ) -> Tuple[ResumoPrecos, List[ApresentacaoPrecos]]:
        """
        Busca preços históricos para um termo.
        
        v45: Filtro por período em meses.
        """
        termo_normalizado = termo.strip().lower()
        
        # Expandir termos com sinônimos
        termos_expandidos = self._expandir_termos(termo)
        
        logger.info(f"[PRECOS] Buscando precos PNCP para: {termo} | Meses: {meses} | Sinonimos: {termos_expandidos}")
        
        # 1. Buscar na API PNCP com TODOS os sinônimos
        itens_pncp = await self._buscar_pncp_multi(termos_expandidos, uf, limit)
        
        # 2. Buscar também no MongoDB local
        itens_local = await self._buscar_local(termo, uf, limit)
        
        # 3. Filtrar resultados locais por relevância
        itens_local_filtrados = [
            it for it in itens_local
            if self._item_relevante(it.descricao, termos_expandidos)
        ]
        
        logger.info(f"[PRECOS] Local: {len(itens_local)} total → {len(itens_local_filtrados)} relevantes")
        
        # 4. Combinar resultados
        todos_itens = itens_pncp + itens_local_filtrados
        
        # 5. Remover duplicatas
        itens_unicos = self._remover_duplicatas(todos_itens)
        
        # 6. Filtrar por período (meses)
        if meses < 24:
            data_limite = (datetime.now(timezone.utc) - timedelta(days=meses * 30)).isoformat()[:10]
            itens_filtrados = []
            for it in itens_unicos:
                data_item = (it.data_homologacao or '')[:10]
                if data_item >= data_limite:
                    itens_filtrados.append(it)
            logger.info(f"[PRECOS] Filtro período {meses}m: {len(itens_unicos)} → {len(itens_filtrados)} itens")
            itens_unicos = itens_filtrados
        
        # 7. Calcular agregações gerais
        resumo = self._calcular_agregacoes(termo, itens_unicos)
        
        # 8. Agrupar por apresentação
        apresentacoes = self.agrupar_por_apresentacao(itens_unicos, termos_expandidos)
        
        logger.info(f"[PRECOS] Total: {resumo.total_registros} itens em {len(apresentacoes)} apresentacoes")
        
        return resumo, apresentacoes
    
    async def _buscar_cache(self, cache_key: str) -> Optional[ResumoPrecos]:
        """Busca resultado em cache se ainda válido"""
        try:
            cached = await self.cache_collection.find_one(
                {'cache_key': cache_key},
                {'_id': 0}
            )
            
            if not cached:
                return None
            
            # Verificar validade (15 dias)
            criado_em = cached.get('criado_em')
            if criado_em:
                if isinstance(criado_em, str):
                    criado_em = datetime.fromisoformat(criado_em.replace('Z', '+00:00'))
                
                validade = criado_em + timedelta(days=CACHE_VALIDADE_DIAS)
                if datetime.now(timezone.utc) > validade:
                    logger.info(f"⏰ [PREÇOS] Cache expirado para: {cache_key}")
                    return None
            
            # Reconstruir objeto
            dados = cached.get('dados', {})
            itens = [PrecoItem(**it) for it in dados.get('itens', [])]
            
            return ResumoPrecos(
                termo_pesquisado=dados.get('termo_pesquisado', ''),
                total_registros=dados.get('total_registros', 0),
                preco_minimo=dados.get('preco_minimo', 0),
                preco_maximo=dados.get('preco_maximo', 0),
                preco_medio=dados.get('preco_medio', 0),
                preco_mediana=dados.get('preco_mediana', 0),
                desvio_padrao=dados.get('desvio_padrao', 0),
                data_mais_antiga=dados.get('data_mais_antiga', ''),
                data_mais_recente=dados.get('data_mais_recente', ''),
                itens=itens
            )
            
        except Exception as e:
            logger.error(f"❌ [PREÇOS] Erro ao buscar cache: {str(e)}")
            return None
    
    async def _salvar_cache(self, cache_key: str, resumo: ResumoPrecos):
        """Salva resultado no cache"""
        try:
            dados = {
                'termo_pesquisado': resumo.termo_pesquisado,
                'total_registros': resumo.total_registros,
                'preco_minimo': resumo.preco_minimo,
                'preco_maximo': resumo.preco_maximo,
                'preco_medio': resumo.preco_medio,
                'preco_mediana': resumo.preco_mediana,
                'desvio_padrao': resumo.desvio_padrao,
                'data_mais_antiga': resumo.data_mais_antiga,
                'data_mais_recente': resumo.data_mais_recente,
                'itens': [
                    {
                        'orgao': it.orgao,
                        'uf': it.uf,
                        'municipio': it.municipio,
                        'descricao': it.descricao,
                        'quantidade': it.quantidade,
                        'unidade': it.unidade,
                        'valor_unitario': it.valor_unitario,
                        'valor_total': it.valor_total,
                        'data_homologacao': it.data_homologacao,
                        'modalidade': it.modalidade,
                        'numero_processo': it.numero_processo,
                        'fonte': it.fonte
                    }
                    for it in resumo.itens[:100]  # Limitar itens no cache
                ]
            }
            
            await self.cache_collection.update_one(
                {'cache_key': cache_key},
                {
                    '$set': {
                        'cache_key': cache_key,
                        'dados': dados,
                        'criado_em': datetime.now(timezone.utc).isoformat()
                    }
                },
                upsert=True
            )
            
            logger.info(f"💾 [PREÇOS] Cache salvo para: {cache_key}")
            
        except Exception as e:
            logger.error(f"❌ [PREÇOS] Erro ao salvar cache: {str(e)}")
    
    async def _buscar_pncp_multi(
        self,
        termos_expandidos: Set[str],
        uf: str = None,
        limit: int = 100
    ) -> List[PrecoItem]:
        """
        Busca itens no PNCP usando a Search API + resolução de itens por edital.
        Estratégia:
          1. Buscar editais via PNCP Search API (funciona corretamente)
          2. Para cada edital, extrair CNPJ/Ano/Sequencial
          3. Buscar itens e resultados homologados de cada edital
          4. Filtrar por relevância usando sinônimos
        """
        import aiohttp
        
        PNCP_SEARCH_URL = "https://pncp.gov.br/api/search/"
        PNCP_ITEMS_BASE = "https://pncp.gov.br/api/pncp/v1"
        
        itens_totais = []
        editais_processados = set()
        termos_buscados = set()
        
        # Priorizar termos mais específicos
        termos_ordenados = sorted(termos_expandidos, key=len, reverse=True)
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
            for termo in termos_ordenados[:3]:
                if len(termo) < 3:
                    continue
                skip = False
                for tb in termos_buscados:
                    if termo in tb or tb in termo:
                        skip = True
                        break
                if skip:
                    continue
                termos_buscados.add(termo)
                
                for pagina in range(1, 4):
                    sucesso_pagina = False
                    for tentativa in range(3):
                        try:
                            params = {
                                "q": termo,
                                "tipos_documento": "edital",
                                "ordenacao": "-data",
                                "pagina": pagina,
                                "tam_pagina": 100
                            }
                            
                            async with session.get(PNCP_SEARCH_URL, params=params) as resp:
                                if resp.status == 429:
                                    wait_time = 2 * (tentativa + 1)
                                    logger.info(f"[PRECOS] Rate limit 429, aguardando {wait_time}s...")
                                    await asyncio.sleep(wait_time)
                                    continue
                                
                                if resp.status != 200:
                                    logger.warning(f"[PRECOS] PNCP Search status {resp.status} para '{termo}' pag {pagina}")
                                    break
                                
                                data = await resp.json()
                                items = data.get('items', [])
                                total = data.get('total', 0)
                                
                                logger.info(f"[PRECOS] PNCP Search '{termo}' pag {pagina}: {len(items)} itens (total: {total})")
                                sucesso_pagina = True
                                
                                if not items:
                                    break
                            
                            # Coletar editais para processar em paralelo
                            editais_para_processar = []
                            for item in items:
                                item_url = item.get('item_url', '')
                                match = re.match(r'/compras/(\d+)/(\d+)/(\d+)', item_url)
                                if not match:
                                    continue
                                
                                cnpj = match.group(1)
                                ano = match.group(2)
                                seq = match.group(3)
                                edital_key = f"{cnpj}/{ano}/{seq}"
                                
                                if edital_key in editais_processados:
                                    continue
                                editais_processados.add(edital_key)
                                
                                edital_uf = item.get('uf', '')
                                if uf and edital_uf and edital_uf.upper() != uf.upper():
                                    continue
                                
                                editais_para_processar.append({
                                    'cnpj': cnpj, 'ano': ano, 'seq': seq,
                                    'orgao': item.get('orgao_nome', 'N/A'),
                                    'uf': edital_uf,
                                    'municipio': item.get('municipio_nome', ''),
                                    'data_pub': item.get('data_publicacao_pncp', ''),
                                    'modalidade': item.get('modalidade_licitacao_nome', ''),
                                    'edital_key': edital_key,
                                })
                            
                            # Processar editais em paralelo (max 15 simultâneos)
                            semaforo = asyncio.Semaphore(15)
                            
                            async def processar_edital(ed):
                                async with semaforo:
                                    return await self._buscar_itens_edital(
                                        session, PNCP_ITEMS_BASE,
                                        ed['cnpj'], ed['ano'], ed['seq'],
                                        ed['orgao'], ed['uf'], ed['municipio'],
                                        ed['data_pub'], ed['modalidade'],
                                        ed['edital_key'], termos_expandidos
                                    )
                            
                            resultados = await asyncio.gather(
                                *[processar_edital(ed) for ed in editais_para_processar],
                                return_exceptions=True
                            )
                            
                            for res in resultados:
                                if isinstance(res, list):
                                    itens_totais.extend(res)
                            
                            # Se poucos resultados no total, não pedir mais páginas
                            if total <= pagina * 100:
                                break
                        except Exception as e:
                            logger.error(f"[PRECOS] Erro PNCP Search '{termo}': {e}")
                            break
                        break  # Saiu do retry loop com sucesso
                    
                    if not sucesso_pagina:
                        break  # Sair do loop de páginas se falhou
                    
                    # Delay entre páginas para evitar rate limit
                    await asyncio.sleep(1)
                
                # Se já temos bastante resultados, parar
                if len(itens_totais) >= limit:
                    break
        
        logger.info(f"[PRECOS] PNCP multi-busca: {len(termos_buscados)} termos, {len(editais_processados)} editais → {len(itens_totais)} itens relevantes")
        return itens_totais
    
    async def _buscar_itens_edital(
        self,
        session,
        base_url: str,
        cnpj: str, ano: str, seq: str,
        orgao: str, uf: str, municipio: str, data_pub: str,
        modalidade: str, edital_key: str,
        termos_expandidos: Set[str]
    ) -> List[PrecoItem]:
        """Busca e filtra itens de um edital específico no PNCP"""
        itens = []
        url_itens = f"{base_url}/orgaos/{cnpj}/compras/{ano}/{seq}/itens"
        
        try:
            async with session.get(url_itens) as resp:
                if resp.status != 200:
                    return []
                
                itens_api = await resp.json()
                
                # Coletar itens relevantes primeiro
                itens_relevantes = []
                for item_data in itens_api:
                    descricao = item_data.get('descricao', '')
                    if self._item_relevante(descricao, termos_expandidos):
                        itens_relevantes.append(item_data)
                
                if not itens_relevantes:
                    return []
                
                # Tentar buscar resultados homologados em paralelo (max 5 por edital)
                async def buscar_resultado(item_data):
                    numero_item = item_data.get('numeroItem', 0)
                    if not numero_item:
                        return item_data, None
                    valor = await self._buscar_resultado_item(
                        session, base_url, cnpj, ano, seq, numero_item
                    )
                    return item_data, valor
                
                resultados = await asyncio.gather(
                    *[buscar_resultado(it) for it in itens_relevantes[:10]],
                    return_exceptions=True
                )
                
                for res in resultados:
                    if isinstance(res, Exception):
                        continue
                    item_data, valor_homologado = res
                    
                    descricao = item_data.get('descricao', '')
                    valor_unitario = float(item_data.get('valorUnitarioEstimado', 0) or 0)
                    valor_total = float(item_data.get('valorTotal', 0) or 0)
                    quantidade = float(item_data.get('quantidade', 0) or 0)
                    
                    if valor_homologado and valor_homologado > 0:
                        valor_unitario = valor_homologado
                    
                    if valor_unitario <= 0:
                        if valor_total > 0 and quantidade > 0:
                            valor_unitario = valor_total / quantidade
                    
                    if valor_unitario <= 0:
                        continue
                    
                    itens.append(PrecoItem(
                        orgao=orgao,
                        uf=uf,
                        municipio=municipio,
                        descricao=descricao,
                        quantidade=quantidade,
                        unidade=item_data.get('unidadeMedida', 'UN'),
                        valor_unitario=round(valor_unitario, 2),
                        valor_total=round(valor_total, 2) if valor_total > 0 else round(valor_unitario * quantidade, 2),
                        data_homologacao=data_pub,
                        modalidade=modalidade,
                        numero_processo=edital_key,
                        fonte='PNCP'
                    ))
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            logger.debug(f"[PRECOS] Erro itens {edital_key}: {e}")
        
        return itens
    
    async def _buscar_resultado_item(
        self, session, base_url: str,
        cnpj: str, ano: str, seq: str, numero_item: int
    ) -> Optional[float]:
        """Tenta buscar o preço homologado de um item específico"""
        if not numero_item:
            return None
        
        url = f"{base_url}/orgaos/{cnpj}/compras/{ano}/{seq}/itens/{numero_item}/resultados"
        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                
                # Pode ser lista de resultados - pegar o primeiro (vencedor)
                if isinstance(data, list) and data:
                    return float(data[0].get('valorUnitarioHomologado', 0) or 0)
                elif isinstance(data, dict):
                    return float(data.get('valorUnitarioHomologado', 0) or 0)
        except:
            pass
        return None
    
    async def _buscar_local(
        self, 
        termo: str, 
        uf: str = None, 
        limit: int = 100
    ) -> List[PrecoItem]:
        """
        Busca itens usando a mesma lógica do busca_service_v2.
        
        Como os editais locais não têm valores de preço armazenados,
        vamos buscar na API PNCP via o serviço de busca existente.
        """
        itens = []
        
        try:
            from services.busca_service_v2 import get_busca_service_v2
            
            busca_service = get_busca_service_v2(self.db)
            
            # Usar o mesmo serviço de busca - CORREÇÃO: termo_busca ao invés de termos
            resultado = await busca_service.buscar(
                termo_busca=termo,
                estados=[uf] if uf else None,
                municipio=None,
                limit=limit,
                incluir_historico=True,  # Buscar histórico para preços
                periodo_dias=730,  # 24 meses
                incluir_ativas=True,
                incluir_futuras=True,
                incluir_encerradas=True  # Incluir todas para ter preços históricos
            )
            
            # Extrair resultados do dicionário retornado
            resultados = resultado.get('resultados', [])
            
            logger.info(f"📊 [PREÇOS] Busca multi-fonte retornou {len(resultados)} resultados")
            
            for edital in resultados:
                # Processar itens do edital
                itens_edital = edital.get('itens_correspondentes', []) or edital.get('itens', [])
                
                # Se tem itens, usar eles
                if itens_edital:
                    for it in itens_edital:
                        try:
                            descricao = it.get('descricao', '') or it.get('nome', '') or ''
                            
                            valor_unitario = float(it.get('valor_unitario', 0) or 0)
                            valor_total = float(it.get('valor_total', 0) or 0)
                            
                            if valor_unitario <= 0 and valor_total > 0:
                                qtd = float(it.get('quantidade', 1) or 1)
                                valor_unitario = valor_total / qtd if qtd > 0 else valor_total
                            
                            if valor_unitario <= 0:
                                continue
                            
                            item = PrecoItem(
                                orgao=edital.get('orgao', 'N/A'),
                                uf=edital.get('uf', ''),
                                municipio=edital.get('municipio', ''),
                                descricao=descricao[:200] if descricao else edital.get('objeto', '')[:200],
                                quantidade=float(it.get('quantidade', 1) or 1),
                                unidade=it.get('unidade', 'UN'),
                                valor_unitario=valor_unitario,
                                valor_total=valor_total if valor_total > 0 else valor_unitario,
                                data_homologacao=edital.get('data_publicacao', '') or edital.get('data_abertura', ''),
                                modalidade=edital.get('modalidade', 'Pregão'),
                                numero_processo=edital.get('numero_processo', ''),
                                fonte=edital.get('fonte', 'LOCAL')
                            )
                            
                            itens.append(item)
                            
                        except Exception as e:
                            continue
                else:
                    # Usar valor total do edital se disponível
                    try:
                        valor = float(edital.get('valor_total', 0) or 0)
                        if valor <= 0:
                            continue
                        
                        item = PrecoItem(
                            orgao=edital.get('orgao', 'N/A'),
                            uf=edital.get('uf', ''),
                            municipio=edital.get('municipio', ''),
                            descricao=edital.get('objeto', '')[:200] or edital.get('medicamento', '')[:200],
                            quantidade=1,
                            unidade='UN',
                            valor_unitario=valor,
                            valor_total=valor,
                            data_homologacao=edital.get('data_publicacao', '') or edital.get('data_abertura', ''),
                            modalidade=edital.get('modalidade', 'Pregão'),
                            numero_processo=edital.get('numero_processo', ''),
                            fonte=edital.get('fonte', 'LOCAL')
                        )
                        
                        itens.append(item)
                        
                    except Exception as e:
                        continue
                
                if len(itens) >= limit:
                    break
            
            logger.info(f"✅ [PREÇOS] Extraídos {len(itens)} itens com preços")
            
        except Exception as e:
            logger.error(f"❌ [PREÇOS] Erro ao buscar local: {str(e)}")
            import traceback
            traceback.print_exc()
        
        return itens[:limit]
    
    def _remover_duplicatas(self, itens: List[PrecoItem]) -> List[PrecoItem]:
        """Remove itens duplicados por hash"""
        vistos = set()
        unicos = []
        
        for item in itens:
            # Gerar hash baseado em campos únicos
            hash_key = f"{item.numero_processo}_{item.descricao[:50]}_{item.valor_unitario}"
            
            if hash_key not in vistos:
                vistos.add(hash_key)
                unicos.append(item)
        
        return unicos
    
    def _calcular_agregacoes(self, termo: str, itens: List[PrecoItem]) -> ResumoPrecos:
        """Calcula estatísticas agregadas dos preços, removendo outliers extremos"""
        if not itens:
            return ResumoPrecos(
                termo_pesquisado=termo,
                total_registros=0,
                preco_minimo=0,
                preco_maximo=0,
                preco_medio=0,
                preco_mediana=0,
                desvio_padrao=0,
                data_mais_antiga='',
                data_mais_recente='',
                itens=[]
            )
        
        # Extrair valores
        valores = [it.valor_unitario for it in itens if it.valor_unitario > 0]
        
        if not valores:
            valores = [0]
        
        # Filtrar outliers extremos: remover valores > 10x a mediana
        if len(valores) >= 5:
            mediana_raw = statistics.median(valores)
            if mediana_raw > 0:
                limite_superior = mediana_raw * 10
                itens = [it for it in itens if it.valor_unitario <= limite_superior]
                valores = [it.valor_unitario for it in itens if it.valor_unitario > 0]
                if not valores:
                    valores = [0]
        
        # Calcular estatísticas
        preco_minimo = min(valores)
        preco_maximo = max(valores)
        preco_medio = statistics.mean(valores)
        preco_mediana = statistics.median(valores)
        desvio_padrao = statistics.stdev(valores) if len(valores) > 1 else 0
        
        # Datas
        datas = [it.data_homologacao for it in itens if it.data_homologacao]
        datas_validas = sorted([d for d in datas if d])
        
        return ResumoPrecos(
            termo_pesquisado=termo,
            total_registros=len(itens),
            preco_minimo=round(preco_minimo, 2),
            preco_maximo=round(preco_maximo, 2),
            preco_medio=round(preco_medio, 2),
            preco_mediana=round(preco_mediana, 2),
            desvio_padrao=round(desvio_padrao, 2),
            data_mais_antiga=datas_validas[0] if datas_validas else '',
            data_mais_recente=datas_validas[-1] if datas_validas else '',
            itens=sorted(itens, key=lambda x: x.valor_unitario)  # Ordenar por preço
        )


# Singleton
_precos_service = None

def get_precos_service(db) -> PrecosService:
    global _precos_service
    if _precos_service is None:
        _precos_service = PrecosService(db)
    return _precos_service
