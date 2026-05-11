"""
DAMA - Validador de Vigência Normativa
Serviço para verificar status de vigência de resoluções CMED/ANVISA.

Scrapa a página oficial de legislação CMED e extrai:
- Número e ano da resolução
- Descrição/ementa
- Status (vigente, caduca, revogada, vigente com alterações)
- Link para PDF
- Norma que revogou/alterou (se aplicável)

Fonte: https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/cmed/legislacao/resolucoes
"""

import logging
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

CMED_RESOLUCOES_URL = "https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/cmed/legislacao/resolucoes"

# Status normalizados
STATUS_VIGENTE = "vigente"
STATUS_VIGENTE_ALTERACOES = "vigente com alterações"
STATUS_CADUCA = "caduca"
STATUS_REVOGADA = "revogada"
STATUS_VIGENCIA_FUTURA = "vigência futura"
STATUS_DESCONHECIDO = "desconhecido"


class VigenciaService:
    """Serviço DAMA para verificação de vigência normativa"""
    
    def __init__(self, db):
        self.db = db
        self.collection = db.cmed_resolucoes
    
    def _normalizar_status(self, status_raw: str) -> str:
        """Normaliza o status extraído do HTML"""
        s = status_raw.lower().strip()
        s = re.sub(r'^status:\s*', '', s)
        s = s.strip('_ ')
        
        if 'caduca' in s:
            return STATUS_CADUCA
        elif 'revogada' in s:
            return STATUS_REVOGADA
        elif 'vigência a partir' in s or 'vigencia a partir' in s:
            return STATUS_VIGENCIA_FUTURA
        elif 'vigente com alteraç' in s or 'vigente com alterac' in s:
            return STATUS_VIGENTE_ALTERACOES
        elif 'vigente' in s:
            return STATUS_VIGENTE
        return STATUS_DESCONHECIDO
    
    def _extrair_numero_ano(self, titulo: str) -> tuple:
        """Extrai número e ano de um título de resolução"""
        # "Resolução CM-CMED nº 7, de 1º de junho de 2022"
        # "Resolução nº 13, de 27 de dezembro de 2022"
        match = re.search(r'n[ºo°]\s*(\d+)', titulo, re.IGNORECASE)
        numero = int(match.group(1)) if match else 0
        
        match_ano = re.search(r'de\s+(\d{4})', titulo)
        ano = int(match_ano.group(1)) if match_ano else 0
        
        return numero, ano
    
    async def scrape_resolucoes(self) -> List[Dict]:
        """Scrapa a página de resoluções CMED e extrai status de vigência"""
        logger.info("[DAMA] Iniciando scraping de resoluções CMED...")
        
        try:
            resp = requests.get(CMED_RESOLUCOES_URL, timeout=30, headers={
                'User-Agent': 'Mozilla/5.0 (GSM-DAMA/1.0)'
            })
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            resolucoes = []
            
            # Cada resolução está em uma célula de tabela
            for td in soup.find_all('td'):
                text = td.get_text(' ', strip=True)
                
                # Verificar se contém "Resolução"
                if 'Resolução' not in text and 'resolução' not in text:
                    continue
                
                # Extrair link do PDF
                link_pdf = ''
                first_link = td.find('a')
                if first_link and first_link.get('href'):
                    link_pdf = first_link['href']
                    if link_pdf.startswith('/'):
                        link_pdf = 'https://www.gov.br' + link_pdf
                
                # Extrair título (primeiro link)
                titulo = first_link.get_text(strip=True) if first_link else ''
                if not titulo:
                    continue
                
                # Extrair status
                status_raw = ''
                # Procurar em itálico (tag <em>) que contém "Status:"
                for em in td.find_all('em'):
                    em_text = em.get_text(strip=True)
                    if 'status' in em_text.lower():
                        status_raw = em_text
                        break
                
                if not status_raw:
                    # Fallback: buscar no texto
                    status_match = re.search(r'Status:\s*([^\n]+)', text, re.IGNORECASE)
                    if status_match:
                        status_raw = status_match.group(1).strip()
                
                status = self._normalizar_status(status_raw) if status_raw else STATUS_DESCONHECIDO
                
                # Extrair número e ano
                numero, ano = self._extrair_numero_ano(titulo)
                
                # Extrair descrição (texto após o título, antes do Status)
                descricao = ''
                parts = text.split('Status:')
                if len(parts) > 0:
                    desc_text = parts[0]
                    # Remover o título do início
                    desc_text = desc_text.replace(titulo, '', 1).strip()
                    # Remover "Publicada no DOU..."
                    desc_text = re.split(r'Publicada no DOU', desc_text)[0].strip()
                    descricao = desc_text[:500]
                
                # Extrair norma que revogou/alterou
                revogada_por = ''
                alterada_por = ''
                if 'Revogada pela' in text or 'Revogada por' in text:
                    match_rev = re.search(r'Revogada pel[ao]\s+(.+?)(?:\n|$)', text)
                    if match_rev:
                        revogada_por = match_rev.group(1).strip()[:200]
                if 'Alterada pela' in text or 'Alterada por' in text:
                    match_alt = re.search(r'Alterada pel[ao][:\s]+(.+?)(?:\n|$)', text)
                    if match_alt:
                        alterada_por = match_alt.group(1).strip()[:200]
                
                resolucao = {
                    'titulo': titulo,
                    'numero': numero,
                    'ano': ano,
                    'descricao': descricao,
                    'status': status,
                    'status_raw': status_raw,
                    'link_pdf': link_pdf,
                    'revogada_por': revogada_por,
                    'alterada_por': alterada_por,
                    'fonte': CMED_RESOLUCOES_URL,
                    'atualizado_em': datetime.now(timezone.utc).isoformat()
                }
                
                resolucoes.append(resolucao)
            
            logger.info(f"[DAMA] Extraídas {len(resolucoes)} resoluções CMED")
            
            # Salvar no MongoDB
            if resolucoes:
                await self.collection.delete_many({})
                await self.collection.insert_many(resolucoes)
                logger.info(f"[DAMA] {len(resolucoes)} resoluções salvas no MongoDB")
            
            # Estatísticas
            stats = {}
            for r in resolucoes:
                s = r['status']
                stats[s] = stats.get(s, 0) + 1
            logger.info(f"[DAMA] Estatísticas: {stats}")
            
            return resolucoes
            
        except Exception as e:
            logger.error(f"[DAMA] Erro ao scraping resoluções: {e}")
            return []
    
    async def verificar_vigencia(self, referencia: str) -> Dict:
        """
        Verifica a vigência de uma norma específica.
        
        Args:
            referencia: Ex: "Resolução 07/2022", "CMED 7 2022", "Res 13/2022"
            
        Returns:
            Dict com status, alerta, e detalhes da norma
        """
        # Extrair número e ano da referência
        numero, ano = 0, 0
        match = re.search(r'(\d+)[/\s-]+(\d{4})', referencia)
        if match:
            numero = int(match.group(1))
            ano = int(match.group(2))
        else:
            # Tentar extrair apenas número
            match_num = re.search(r'n[ºo°]?\s*(\d+)', referencia, re.IGNORECASE)
            if match_num:
                numero = int(match_num.group(1))
            match_ano = re.search(r'(\d{4})', referencia)
            if match_ano:
                ano = int(match_ano.group(1))
        
        if not numero or not ano:
            return {
                'encontrada': False,
                'status': STATUS_DESCONHECIDO,
                'alerta': 'Não foi possível identificar a resolução na referência fornecida.',
                'pode_usar': False,
                'referencia_buscada': referencia
            }
        
        # Buscar no MongoDB
        resolucao = await self.collection.find_one(
            {'numero': numero, 'ano': ano},
            {'_id': 0}
        )
        
        if not resolucao:
            # Tentar buscar com scraping fresco
            await self.scrape_resolucoes()
            resolucao = await self.collection.find_one(
                {'numero': numero, 'ano': ano},
                {'_id': 0}
            )
        
        if not resolucao:
            return {
                'encontrada': False,
                'status': STATUS_DESCONHECIDO,
                'alerta': f'Resolução nº {numero}/{ano} não encontrada na base CMED.',
                'pode_usar': False,
                'referencia_buscada': referencia
            }
        
        # Determinar se pode ser usada
        pode_usar = resolucao['status'] in [STATUS_VIGENTE, STATUS_VIGENTE_ALTERACOES]
        
        # Gerar alerta contextual
        alerta = ''
        if resolucao['status'] == STATUS_CADUCA:
            alerta = (
                f"ATENÇÃO: A Resolução CM-CMED nº {numero}/{ano} está CADUCA. "
                f"Esta norma não está mais vigente e NÃO deve ser utilizada como base para "
                f"esclarecimentos em processos licitatórios. "
                f"Verifique se existe norma substituta vigente."
            )
        elif resolucao['status'] == STATUS_REVOGADA:
            msg_extra = ''
            if resolucao.get('revogada_por'):
                msg_extra = f" Revogada por: {resolucao['revogada_por']}."
            alerta = (
                f"ATENÇÃO: A Resolução CM-CMED nº {numero}/{ano} foi REVOGADA. "
                f"Esta norma NÃO deve ser utilizada.{msg_extra}"
            )
        elif resolucao['status'] == STATUS_VIGENCIA_FUTURA:
            alerta = (
                f"A Resolução CM-CMED nº {numero}/{ano} ainda não entrou em vigor. "
                f"Status: {resolucao.get('status_raw', '')}."
            )
        elif resolucao['status'] == STATUS_VIGENTE_ALTERACOES:
            msg_extra = ''
            if resolucao.get('alterada_por'):
                msg_extra = f" Alterada por: {resolucao['alterada_por']}."
            alerta = (
                f"A Resolução CM-CMED nº {numero}/{ano} está VIGENTE, porém com alterações. "
                f"Verifique a versão consolidada.{msg_extra}"
            )
        elif resolucao['status'] == STATUS_VIGENTE:
            alerta = f"A Resolução CM-CMED nº {numero}/{ano} está VIGENTE."
        
        return {
            'encontrada': True,
            'status': resolucao['status'],
            'alerta': alerta,
            'pode_usar': pode_usar,
            'referencia_buscada': referencia,
            'resolucao': resolucao
        }
    
    async def get_resolucoes_vigentes(self) -> List[Dict]:
        """Retorna apenas as resoluções vigentes"""
        cursor = self.collection.find(
            {'status': {'$in': [STATUS_VIGENTE, STATUS_VIGENTE_ALTERACOES]}},
            {'_id': 0}
        ).sort('ano', -1)
        return await cursor.to_list(length=100)
    
    async def get_stats(self) -> Dict:
        """Retorna estatísticas de vigência"""
        total = await self.collection.count_documents({})
        if total == 0:
            await self.scrape_resolucoes()
            total = await self.collection.count_documents({})
        
        vigentes = await self.collection.count_documents({'status': STATUS_VIGENTE})
        vigentes_alt = await self.collection.count_documents({'status': STATUS_VIGENTE_ALTERACOES})
        caducas = await self.collection.count_documents({'status': STATUS_CADUCA})
        revogadas = await self.collection.count_documents({'status': STATUS_REVOGADA})
        
        return {
            'total': total,
            'vigentes': vigentes,
            'vigentes_com_alteracoes': vigentes_alt,
            'caducas': caducas,
            'revogadas': revogadas,
            'ultima_atualizacao': datetime.now(timezone.utc).isoformat()
        }


# Singleton
_vigencia_service = None

def get_vigencia_service(db) -> VigenciaService:
    global _vigencia_service
    if _vigencia_service is None:
        _vigencia_service = VigenciaService(db)
    return _vigencia_service
