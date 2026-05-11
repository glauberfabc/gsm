"""
PNCP Search Client v74.0
=========================
Cliente de busca em tempo real no PNCP (Portal Nacional de Contratações Públicas)

Endpoint: https://pncp.gov.br/api/search/
- Busca full-text por palavra-chave no objeto
- Sem autenticação
- Retorna editais, atas, contratos
- Dados: órgão, UF, município, modalidade, datas, valores, links

Este é o motor principal de busca independente do GSM.
"""

import aiohttp
import logging
from typing import List, Dict, Optional
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)


class PNCPSearchClient:
    """
    Cliente de busca em tempo real no PNCP.
    Busca diretamente na API pública sem depender de nenhum intermediário.
    """
    
    SEARCH_URL = "https://pncp.gov.br/api/search/"
    PNCP_BASE = "https://pncp.gov.br/app"
    
    def __init__(self):
        self.timeout = aiohttp.ClientTimeout(total=30)
        self.headers = {
            'Accept': 'application/json',
            'User-Agent': 'GSM-Buscador-Editais/2.0'
        }
    
    async def buscar(
        self,
        termo: str,
        pagina: int = 1,
        tipos_documento: str = "edital",
        status: str = "recebendo_proposta",
        max_paginas: int = 5
    ) -> Dict:
        """
        Busca em tempo real no PNCP por palavra-chave.
        Pagina automaticamente para capturar mais resultados.
        
        Args:
            termo: Palavra-chave (ex: "insulina", "canabidiol")
            pagina: Página inicial
            tipos_documento: "edital", "ata", "contrato" ou "todos"
            status: "recebendo_proposta" (apenas ativos), "todos" (todos)
            max_paginas: Máximo de páginas para buscar (10 itens/página)
        """
        resultados = []
        total = 0
        
        try:
            params = {
                'q': termo,
                'pagina': pagina
            }
            if tipos_documento and tipos_documento != "todos":
                params['tipos_documento'] = tipos_documento
            if status and status != "todos":
                params['status'] = status
            
            async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as session:
                # Primeira página
                async with session.get(self.SEARCH_URL, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        items = data.get('items', [])
                        total = data.get('total', len(items))
                        
                        for item in items:
                            resultado = self._mapear_resultado(item, termo)
                            if resultado:
                                resultados.append(resultado)
                        
                        # Paginar para buscar mais resultados
                        total_paginas = min(max_paginas, (total // 10) + 1)
                        for pg in range(pagina + 1, pagina + total_paginas):
                            try:
                                params['pagina'] = pg
                                async with session.get(self.SEARCH_URL, params=params) as resp_pg:
                                    if resp_pg.status == 200:
                                        data_pg = await resp_pg.json()
                                        items_pg = data_pg.get('items', [])
                                        if not items_pg:
                                            break
                                        for item in items_pg:
                                            resultado = self._mapear_resultado(item, termo)
                                            if resultado:
                                                resultados.append(resultado)
                            except Exception:
                                break
                    else:
                        logger.error(f"PNCP search error: {resp.status}")
        
        except Exception as e:
            logger.error(f"PNCP search exception: {e}")
        
        return {
            'resultados': resultados,
            'total': total,
            'pagina': pagina,
            'fonte': 'PNCP_TEMPO_REAL'
        }
    
    def _mapear_resultado(self, item: Dict, termo: str) -> Optional[Dict]:
        """Mapeia resultado da API PNCP para o schema GSM."""
        try:
            item_url = item.get('item_url', '')
            # Fix: Converter /compras/ para /editais/ (página com PDFs para download)
            if item_url and '/compras/' in item_url:
                item_url = item_url.replace('/compras/', '/editais/')
            link_pncp = f"{self.PNCP_BASE}{item_url}" if item_url else ''
            
            objeto = item.get('description', '') or item.get('title', '')
            orgao = item.get('orgao_nome', '') or ''
            unidade = item.get('unidade_nome', '') or ''
            uf = item.get('uf', '') or ''
            municipio = item.get('municipio_nome', '') or ''
            
            # ID único baseado no numero_controle_pncp
            numero_pncp = item.get('numero_controle_pncp', '')
            id_gsm = hashlib.md5(f"PNCP-{numero_pncp}".encode()).hexdigest() if numero_pncp else ''
            
            # Datas
            data_pub = item.get('data_publicacao_pncp', '')
            data_inicio = item.get('data_inicio_vigencia', '')
            data_fim = item.get('data_fim_vigencia', '')
            
            # Portal de origem - PNCP é agregador nacional, mostrar esfera + UF
            esfera = item.get('esfera_nome', '') or ''
            portal_nome = f"PNCP ({uf})" if uf else 'PNCP'
            
            return {
                'id': id_gsm,
                'id_gsm': id_gsm,
                'id_externo': numero_pncp,
                'numero_controle_pncp': numero_pncp,
                'fonte': 'PNCP',
                'fonte_origem': 'PNCP_TEMPO_REAL',
                'portal_captura': portal_nome,
                'objeto': objeto.upper(),
                'orgao': unidade or orgao,
                'dados_orgao': {
                    'cnpj': item.get('orgao_cnpj', ''),
                    'nome': orgao,
                    'unidade': unidade,
                    'uf': uf,
                    'municipio': municipio
                },
                'estado': uf,
                'uf': uf,
                'municipio': municipio,
                'modalidade': item.get('modalidade_licitacao_nome', 'Pregão Eletrônico'),
                'status': 'ABERTA' if not item.get('cancelado', False) else 'CANCELADA',
                'situacao': item.get('situacao_nome', ''),
                'data_publicacao': data_pub,
                'data_abertura': data_inicio,
                'data_inicial': data_inicio,
                'data_final': data_fim,
                'link_documento': link_pncp,
                'link_portal': link_pncp,
                'link_origem': link_pncp,
                'link_edital': link_pncp,
                'numero_processo': item.get('numero', '') or '',
                'numero_licitacao': str(item.get('numero_sequencial', '')),
                'valor_total_estimado': item.get('valor_global'),
                'tem_resultado': item.get('tem_resultado', False),
                'esfera': item.get('esfera_nome', ''),
                'poder': item.get('poder_nome', ''),
                'tipo_documento': item.get('tipo_nome', ''),
                'is_saude': self._is_saude(objeto),
                'itens_clonados': [],
                'anexos': [],
                'link_status': 'VALIDO'
            }
        except Exception as e:
            logger.error(f"Erro mapeando resultado PNCP: {e}")
            return None
    
    def _is_saude(self, objeto: str) -> bool:
        """Detecta se o edital é da área de saúde."""
        termos = [
            'medicament', 'farmac', 'hospital', 'saude', 'saúde',
            'insulina', 'canabidiol', 'seringa', 'luva', 'injetável',
            'comprimido', 'cirurg', 'ortopéd', 'prótese', 'laborat',
            'diagnóst', 'vacina', 'hemodi', 'oncolog', 'quimio',
            'ambulância', 'upa ', 'ubs ', 'pronto socorro'
        ]
        obj_lower = objeto.lower()
        return any(t in obj_lower for t in termos)
    
    async def buscar_detalhes(self, cnpj: str, ano: int, sequencial: int) -> Optional[Dict]:
        """
        Busca detalhes completos de uma contratação no PNCP.
        Inclui itens, anexos/documentos.
        """
        try:
            url = f"{self.PNCP_BASE}/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}"
            
            async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as session:
                # Dados principais
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return None
                    dados = await resp.json()
                
                # Itens
                itens = []
                try:
                    async with session.get(f"{url}/itens?pagina=1&tamanhoPagina=50") as resp_itens:
                        if resp_itens.status == 200:
                            itens_data = await resp_itens.json()
                            for it in itens_data if isinstance(itens_data, list) else []:
                                itens.append({
                                    'numero': str(it.get('numeroItem', '')),
                                    'descricao': it.get('descricao', ''),
                                    'quantidade': str(it.get('quantidade', '')),
                                    'unidade': it.get('unidadeMedida', ''),
                                    'valor_unitario': it.get('valorUnitarioEstimado'),
                                    'valor_total': it.get('valorTotal')
                                })
                except Exception:
                    pass
                
                # Arquivos/Documentos
                arquivos = []
                try:
                    async with session.get(f"{url}/arquivos?pagina=1&tamanhoPagina=20") as resp_arq:
                        if resp_arq.status == 200:
                            arqs_data = await resp_arq.json()
                            for arq in arqs_data if isinstance(arqs_data, list) else []:
                                arquivos.append({
                                    'nome': arq.get('titulo', '') or arq.get('nomeArquivo', ''),
                                    'url': arq.get('url', '')
                                })
                except Exception:
                    pass
                
                return {
                    'dados': dados,
                    'itens': itens,
                    'arquivos': arquivos
                }
        
        except Exception as e:
            logger.error(f"Erro buscando detalhes PNCP: {e}")
            return None
