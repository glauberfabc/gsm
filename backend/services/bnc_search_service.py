"""
BNC Search Service - Busca em Tempo Real na Bolsa Nacional de Compras
======================================================================

🎯 OBJETIVO: Integrar dados da BNC (Bolsa Nacional de Compras) para expandir
a cobertura de licitações municipais e estaduais.

FONTE:
- Portal: https://bnccompras.com
- Busca Pública: https://bnccompras.com/Process/ProcessSearchPublic

A BNC é uma plataforma privada de pregões eletrônicos muito utilizada
por prefeituras e órgãos estaduais.
"""

import asyncio
import logging
import re
import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
import hashlib
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class BNCSearchService:
    """
    Serviço de busca em tempo real na BNC (Bolsa Nacional de Compras)
    
    Implementa scraping da página pública de busca de processos.
    """
    
    def __init__(self):
        self.base_url = "https://bnccompras.com"
        self.search_url = f"{self.base_url}/Process/ProcessSearchPublic"
        self.timeout = 30
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://bnccompras.com/',
        }
    
    async def buscar_por_termo(
        self,
        termo: str,
        limite: int = 50,
        apenas_ativas: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Busca licitações na BNC por termo
        
        Args:
            termo: Termo de busca (ex: "prolia", "denosumabe")
            limite: Número máximo de resultados
            apenas_ativas: Filtrar apenas licitações ativas
            
        Returns:
            Lista de editais normalizados
        """
        resultados = []
        
        logger.info(f"🔍 [BNC] Iniciando busca por '{termo}'")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers, follow_redirects=True) as client:
                # Buscar página de processos públicos
                resultados = await self._buscar_processos(client, termo, limite, apenas_ativas)
                
        except Exception as e:
            logger.error(f"❌ [BNC] Erro geral: {e}")
        
        logger.info(f"✅ [BNC] {len(resultados)} resultados para '{termo}'")
        
        return resultados[:limite]
    
    async def _buscar_processos(
        self,
        client: httpx.AsyncClient,
        termo: str,
        limite: int,
        apenas_ativas: bool
    ) -> List[Dict]:
        """
        Busca processos na página pública da BNC
        """
        resultados = []
        
        try:
            # Parâmetros da busca
            params = {
                'param1': '0',  # Todos os processos
                'searchText': termo,
            }
            
            logger.info(f"  📡 [BNC] Buscando em {self.search_url}")
            
            response = await client.get(self.search_url, params=params)
            
            if response.status_code == 200:
                # Parse HTML
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Encontrar tabela de processos
                processos = self._extrair_processos_html(soup, termo)
                
                for processo in processos[:limite]:
                    if apenas_ativas:
                        status = processo.get('status_oportunidade', '')
                        if status == 'ENCERRADA':
                            continue
                    resultados.append(processo)
                
                logger.info(f"  ✅ [BNC] Extraídos {len(resultados)} processos")
            else:
                logger.warning(f"  ⚠️ [BNC] Status {response.status_code}")
                
        except httpx.TimeoutException:
            logger.warning("  ⏱️ [BNC] Timeout")
        except Exception as e:
            logger.debug(f"  ⚠️ [BNC] Erro: {e}")
        
        return resultados
    
    def _extrair_processos_html(self, soup: BeautifulSoup, termo: str) -> List[Dict]:
        """
        Extrai processos do HTML da BNC
        """
        processos = []
        
        try:
            # Buscar cards ou linhas de processos
            # A BNC usa estrutura de cards com classe 'process-card' ou similar
            cards = soup.find_all('div', class_=re.compile(r'process|licitacao|card|item'))
            
            # Se não encontrar cards, tentar tabela
            if not cards:
                rows = soup.find_all('tr')
                for row in rows:
                    processo = self._extrair_de_linha_tabela(row, termo)
                    if processo:
                        processos.append(processo)
            else:
                for card in cards:
                    processo = self._extrair_de_card(card, termo)
                    if processo:
                        processos.append(processo)
            
            # Fallback: buscar qualquer link que contenha 'Process' ou 'Edital'
            if not processos:
                links = soup.find_all('a', href=re.compile(r'Process|Edital|Detail'))
                for link in links[:50]:
                    processo = self._extrair_de_link(link, termo)
                    if processo:
                        processos.append(processo)
            
        except Exception as e:
            logger.debug(f"Erro ao extrair processos HTML: {e}")
        
        return processos
    
    def _extrair_de_card(self, card, termo: str) -> Optional[Dict]:
        """Extrai dados de um card de processo"""
        try:
            # Extrair texto do card
            texto = card.get_text(separator=' ', strip=True)
            
            # Verificar se contém o termo buscado
            if termo.lower() not in texto.lower():
                return None
            
            # Extrair número do processo (padrão: XXX/20XX)
            numero_match = re.search(r'(\d+[/-]\d{4})', texto)
            numero_processo = numero_match.group(1) if numero_match else ''
            
            # Extrair órgão/município
            orgao_match = re.search(r'(PREFEITURA|MUNICÍPIO|CÂMARA|SECRETARIA)[^,\n]+', texto, re.IGNORECASE)
            orgao = orgao_match.group(0).strip() if orgao_match else 'BNC'
            
            # Extrair datas
            data_match = re.search(r'(\d{2}[/-]\d{2}[/-]\d{4})', texto)
            data_str = data_match.group(1) if data_match else None
            
            # Extrair link
            link_tag = card.find('a')
            link = ''
            if link_tag and link_tag.get('href'):
                href = link_tag.get('href')
                if not href.startswith('http'):
                    href = f"{self.base_url}{href}"
                link = href
            
            # Gerar ID
            id_externo = f"bnc-{numero_processo.replace('/', '-').replace(' ', '')}"
            hash_dedup = hashlib.md5(id_externo.encode()).hexdigest()
            
            # Classificar status
            status = 'ATIVA'
            if any(s in texto.lower() for s in ['encerrad', 'finaliz', 'concluíd', 'homolog']):
                status = 'ENCERRADA'
            elif any(s in texto.lower() for s in ['publicad', 'recepção', 'proposta']):
                status = 'ATIVA'
            
            return {
                'id_externo': id_externo,
                'numero_controle_pncp': None,
                'hash_dedup': hash_dedup,
                'objeto': texto[:500],  # Primeiros 500 caracteres como objeto
                'orgao': orgao,
                'orgao_cnpj': None,
                'uasg': None,
                'uf': self._extrair_uf(texto),
                'municipio': self._extrair_municipio(texto),
                'esfera': 'Municipal',
                'modalidade': self._extrair_modalidade(texto),
                'numero_processo': numero_processo,
                'data_publicacao': None,
                'data_abertura': self._parse_date(data_str).isoformat() if data_str else None,
                'data_final': None,
                'link_edital': link,
                'link_sistema_origem': link,
                'link_status': 'VALIDO' if link else 'INVALIDO',
                'tipo_link': 'bnc',
                'fonte': 'BNC',
                'status_oportunidade': status,
                'is_saude': True,
                'quality_score': 75,
                'itens_edital': [],
                '_termo_match': termo
            }
            
        except Exception as e:
            logger.debug(f"Erro ao extrair card: {e}")
            return None
    
    def _extrair_de_linha_tabela(self, row, termo: str) -> Optional[Dict]:
        """Extrai dados de uma linha de tabela"""
        try:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 3:
                return None
            
            texto = ' '.join([c.get_text(strip=True) for c in cells])
            
            if termo.lower() not in texto.lower():
                return None
            
            # Similar ao card, mas usa células
            numero_match = re.search(r'(\d+[/-]\d{4})', texto)
            numero_processo = numero_match.group(1) if numero_match else ''
            
            link_tag = row.find('a')
            link = ''
            if link_tag and link_tag.get('href'):
                href = link_tag.get('href')
                if not href.startswith('http'):
                    href = f"{self.base_url}{href}"
                link = href
            
            id_externo = f"bnc-{numero_processo.replace('/', '-').replace(' ', '')}"
            hash_dedup = hashlib.md5(id_externo.encode()).hexdigest()
            
            return {
                'id_externo': id_externo,
                'numero_controle_pncp': None,
                'hash_dedup': hash_dedup,
                'objeto': texto[:500],
                'orgao': 'BNC',
                'orgao_cnpj': None,
                'uasg': None,
                'uf': self._extrair_uf(texto),
                'municipio': self._extrair_municipio(texto),
                'esfera': 'Municipal',
                'modalidade': self._extrair_modalidade(texto),
                'numero_processo': numero_processo,
                'data_publicacao': None,
                'data_abertura': None,
                'data_final': None,
                'link_edital': link,
                'link_sistema_origem': link,
                'link_status': 'VALIDO' if link else 'INVALIDO',
                'tipo_link': 'bnc',
                'fonte': 'BNC',
                'status_oportunidade': 'ATIVA',
                'is_saude': True,
                'quality_score': 75,
                'itens_edital': [],
                '_termo_match': termo
            }
            
        except Exception:
            return None
    
    def _extrair_de_link(self, link_tag, termo: str) -> Optional[Dict]:
        """Extrai dados de um link de processo"""
        try:
            texto = link_tag.get_text(strip=True)
            href = link_tag.get('href', '')
            
            if termo.lower() not in texto.lower():
                return None
            
            if not href.startswith('http'):
                href = f"{self.base_url}{href}"
            
            numero_match = re.search(r'(\d+[/-]\d{4})', texto)
            numero_processo = numero_match.group(1) if numero_match else texto[:20]
            
            id_externo = f"bnc-{numero_processo.replace('/', '-').replace(' ', '-')}"
            hash_dedup = hashlib.md5(id_externo.encode()).hexdigest()
            
            return {
                'id_externo': id_externo,
                'numero_controle_pncp': None,
                'hash_dedup': hash_dedup,
                'objeto': texto,
                'orgao': 'BNC',
                'orgao_cnpj': None,
                'uasg': None,
                'uf': '',
                'municipio': '',
                'esfera': 'Municipal',
                'modalidade': 'Pregão Eletrônico',
                'numero_processo': numero_processo,
                'data_publicacao': None,
                'data_abertura': None,
                'data_final': None,
                'link_edital': href,
                'link_sistema_origem': href,
                'link_status': 'VALIDO',
                'tipo_link': 'bnc',
                'fonte': 'BNC',
                'status_oportunidade': 'ATIVA',
                'is_saude': True,
                'quality_score': 70,
                'itens_edital': [],
                '_termo_match': termo
            }
            
        except Exception:
            return None
    
    def _extrair_uf(self, texto: str) -> str:
        """Extrai UF do texto"""
        ufs = ['AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 
               'MT', 'MS', 'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 
               'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO']
        
        # Padrão: CIDADE/UF ou CIDADE-UF
        match = re.search(r'[/-]\s*([A-Z]{2})\b', texto.upper())
        if match and match.group(1) in ufs:
            return match.group(1)
        
        # Buscar UF isolada
        for uf in ufs:
            if f' {uf} ' in texto.upper() or texto.upper().endswith(f' {uf}'):
                return uf
        
        return ''
    
    def _extrair_municipio(self, texto: str) -> str:
        """Extrai município do texto"""
        # Padrão: MUNICÍPIO DE XXXXX
        match = re.search(r'MUNICÍPIO\s+DE\s+([^\s,/]+)', texto, re.IGNORECASE)
        if match:
            return match.group(1).strip().title()
        
        # Padrão: PREFEITURA DE XXXXX
        match = re.search(r'PREFEITURA\s+(DE\s+)?([^\s,/]+)', texto, re.IGNORECASE)
        if match:
            return match.group(2).strip().title()
        
        return ''
    
    def _extrair_modalidade(self, texto: str) -> str:
        """Extrai modalidade do texto"""
        texto_lower = texto.lower()
        
        if 'pregão eletrônico' in texto_lower or 'pregao eletronico' in texto_lower:
            return 'Pregão Eletrônico'
        elif 'pregão presencial' in texto_lower:
            return 'Pregão Presencial'
        elif 'concorrência' in texto_lower or 'concorrencia' in texto_lower:
            return 'Concorrência'
        elif 'tomada de preço' in texto_lower:
            return 'Tomada de Preços'
        elif 'convite' in texto_lower:
            return 'Convite'
        elif 'dispensa' in texto_lower:
            return 'Dispensa'
        elif 'inexigibilidade' in texto_lower:
            return 'Inexigibilidade'
        elif 'credenciamento' in texto_lower:
            return 'Credenciamento'
        
        return 'Pregão Eletrônico'  # Default
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Converte string de data para datetime"""
        if not date_str:
            return None
        
        try:
            for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d']:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
        except Exception:
            pass
        
        return None


# Singleton
_bnc_search_instance = None

def get_bnc_search() -> BNCSearchService:
    """Retorna instância singleton do serviço"""
    global _bnc_search_instance
    if _bnc_search_instance is None:
        _bnc_search_instance = BNCSearchService()
    return _bnc_search_instance
