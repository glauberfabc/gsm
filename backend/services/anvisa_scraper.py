"""
ANVISA Janela de Importação - Scraper v5 (Aprimorado)
=====================================================
Fontes:
  1. Notícias ANVISA (gov.br/anvisa/noticias)
  2. DOU Seção 1 — Resolução-RE, Autorização Excepcional, Decisão Judicial
  3. DOU Genérico — desabastecimento, importação excepcional

Objetivo: Detectar medicamentos com JANELA DE IMPORTAÇÃO aberta.
Foco em:
  - Resolução-RE (autorização de importação pela ANVISA)
  - Cumprimento de Decisão Judicial (importação sem registro)
  - Autorização Excepcional de Importação (RDC 488/RDC 203)
  - Desabastecimento confirmado
"""

import logging
import re
import json
import aiohttp
from datetime import datetime, timezone
from typing import List, Dict
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ============================================================
# PALAVRAS-CHAVE DE GATILHO
# ============================================================
KW_IMPORTACAO = [
    'importação excepcional', 'importação em caráter excepcional',
    'importação temporária', 'importação sem registro',
    'rdc 203', 'rdc 488', 'autorização excepcional',
    'indisponibilidade no mercado', 'resolução-re',
    'autorização de importação', 'importação de medicamento',
]
KW_JUDICIAL = [
    'cumprimento de decisão judicial', 'decisão judicial',
    'ação judicial', 'processo judicial', 'mandado judicial',
    'liminar', 'tutela de urgência', 'dispensa de registro',
    'sem registro no brasil',
]
KW_DESABASTECIMENTO = [
    'desabastecimento', 'falta de medicamento', 'falta no mercado',
    'ruptura de estoque', 'indisponibilidade',
    'interrupção de fabricação', 'interrupção fabricação',
    'suspensão de fabricação', 'parada de produção',
    'descontinuação', 'descontinuidade',
    'registro cancelado', 'cancelamento de registro',
]
KW_SAUDE = [
    'medicamento', 'farmácia', 'princípio ativo',
    'suplemento', 'recolhimento', 'recall', 'interdição',
    'proibição', 'falsificação', 'farmacovigilância',
]
KW_LABORATORIO = [
    'transferência de titularidade',
    'alteração pós-registro',
    'atualização de bula',
    'alteração de rotulagem',
    'mudança de titularidade',
]

# URLs das fontes
URLS_NOTICIAS = [
    'https://www.gov.br/anvisa/pt-br/assuntos/noticias-anvisa',
    'https://www.gov.br/anvisa/pt-br/assuntos/noticias-anvisa?b_start:int=30',
]

# DOU - Buscas específicas para capturar Resolução-RE e importações
DOU_SEARCHES_SECAO1 = [
    # Foco em autorizações de importação - SEM aspas duplas (o DOU não suporta)
    'Resolução-RE anvisa medicamento importação',
    'importação excepcional anvisa medicamento',
    'cumprimento decisão judicial anvisa medicamento',
    'desabastecimento medicamento importação anvisa',
    'anvisa importação autorização medicamento',
    'RDC 488 RDC 203 anvisa importação',
    # Radar Farmaceutico: termos de interrupcao/descontinuacao
    'suspensão fabricação medicamento anvisa',
    'interrupção definitiva medicamento anvisa',
    'descontinuidade temporária medicamento anvisa',
    'reativação fabricação medicamento anvisa',
]

DOU_SEARCHES_GERAL = [
    'anvisa desabastecimento importação excepcional',
    'anvisa descontinuação medicamento fabricação',
    'anvisa interrupção fabricação descontinuação',
]


class AnvisaScraper:
    """Scraper v5 - Foco em Resolução-RE e Autorizações de Importação."""

    def __init__(self):
        self.timeout = aiohttp.ClientTimeout(total=30)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
        }

    async def coletar_tudo(self) -> List[Dict]:
        """Coleta de todas as fontes e retorna alertas relevantes."""
        todos = []
        async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as session:
            # Fonte 1: Notícias ANVISA
            for url in URLS_NOTICIAS:
                try:
                    items = await self._scrape_noticias(session, url)
                    todos.extend(items)
                    logger.info(f'ANVISA notícias [{url[-30:]}]: {len(items)} items')
                except Exception as e:
                    logger.error(f'ANVISA notícias erro: {e}')

            # Fonte 2: DOU Seção 1 — Resolução-RE e Autorizações
            for query in DOU_SEARCHES_SECAO1:
                try:
                    items = await self._scrape_dou(session, query, secao='do1')
                    todos.extend(items)
                    logger.info(f'DOU Seção 1 [{query[:40]}]: {len(items)} items')
                except Exception as e:
                    logger.error(f'DOU Seção 1 erro: {e}')

            # Fonte 3: DOU Geral (todas seções)
            for query in DOU_SEARCHES_GERAL:
                try:
                    items = await self._scrape_dou(session, query, secao='todos')
                    todos.extend(items)
                    logger.info(f'DOU Geral [{query[:40]}]: {len(items)} items')
                except Exception as e:
                    logger.error(f'DOU Geral erro: {e}')

            # Fonte 4: DOU full content crawler - segue links dos resultados mais relevantes
            items_with_links = [i for i in todos if i.get('link') and 'in.gov.br' in i.get('link', '')]
            crawled = 0
            for item in items_with_links[:8]:  # Limita a 8 artigos para não sobrecarregar
                try:
                    full_text = await self._crawl_dou_article(session, item['link'])
                    if full_text and len(full_text) > len(item.get('descricao', '')):
                        item['descricao'] = full_text[:3000]  # Full content for better analysis
                        # Re-extract structured data with full content
                        extras = self._extrair_dados_dou(item['titulo'], full_text)
                        item.update(extras)
                        crawled += 1
                except Exception as e:
                    logger.error(f'DOU crawl erro: {e}')
            if crawled:
                logger.info(f'DOU full content: crawled {crawled} articles')

        # Fonte 5: CMED - Medicamentos com desabastecimento confirmado
        try:
            cmed_items = await self.coletar_cmed()
            todos.extend(cmed_items)
            logger.info(f'CMED: {len(cmed_items)} medicamentos')
        except Exception as e:
            logger.error(f'CMED erro: {e}')

        # Filtrar relevantes e dedup
        alertas = self._filtrar_relevantes(todos)
        logger.info(f'Total coletado: {len(todos)} → {len(alertas)} alertas relevantes')
        return alertas

    # ===================== DOU FULL CONTENT CRAWLER =====================
    async def _crawl_dou_article(self, session, url: str) -> str:
        """Acessa o conteúdo completo de um artigo do DOU."""
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    return ''
                html = await resp.text()

            soup = BeautifulSoup(html, 'html.parser')
            # DOU uses 'texto-dou' class for article content
            article = soup.find('div', class_='texto-dou')
            if not article:
                article = soup.find('div', id='materia')
            if not article:
                for cls in ['texto-dou', 'materia', 'journal-content-article']:
                    article = soup.find('div', class_=cls)
                    if article:
                        break

            if article:
                return article.get_text(separator='\n', strip=True)
            return ''
        except Exception:
            return ''

    # ===================== FONTE 1: NOTÍCIAS ANVISA =====================
    async def _scrape_noticias(self, session, url: str) -> List[Dict]:
        resultados = []
        async with session.get(url) as resp:
            if resp.status != 200:
                return []
            html = await resp.text()

        soup = BeautifulSoup(html, 'html.parser')
        lista = soup.find('ul', class_='noticias')
        if not lista:
            return []

        for li in lista.find_all('li', recursive=False):
            try:
                conteudo = li.find('div', class_='conteudo')
                if not conteudo:
                    continue

                h2 = conteudo.find('h2', class_='titulo')
                if not h2:
                    continue
                link_tag = h2.find('a')
                if not link_tag:
                    continue

                titulo = link_tag.get_text(strip=True)
                link = link_tag.get('href', '')
                if link and not link.startswith('http'):
                    link = f'https://www.gov.br{link}'
                if not titulo or len(titulo) < 10:
                    continue

                cat_div = conteudo.find('div', class_='subtitulo-noticia')
                categoria = cat_div.get_text(strip=True) if cat_div else ''

                desc_span = conteudo.find('span', class_='descricao')
                data_pub, descricao = '', ''
                if desc_span:
                    data_span = desc_span.find('span', class_='data')
                    if data_span:
                        data_pub = data_span.get_text(strip=True)
                    desc_text = desc_span.get_text(strip=True)
                    if data_pub and desc_text.startswith(data_pub):
                        desc_text = desc_text[len(data_pub):].strip()
                    if desc_text.startswith('- '):
                        desc_text = desc_text[2:].strip()
                    descricao = desc_text

                resultados.append({
                    'titulo': titulo,
                    'link': link,
                    'data_publicacao': data_pub,
                    'descricao': descricao,
                    'categoria': categoria,
                    'fonte': 'Notícias ANVISA',
                    'coletado_em': datetime.now(timezone.utc).isoformat(),
                })
            except Exception:
                continue
        return resultados

    # ===================== FONTE 2: DOU (Seção 1 ou Geral) =====================
    async def _scrape_dou(self, session, query: str, secao: str = 'todos') -> List[Dict]:
        """Busca no DOU via jsonArray embarcado no HTML.
        
        Args:
            query: termo de busca
            secao: 'do1' para Seção 1, 'todos' para todas
        """
        import urllib.parse
        encoded = urllib.parse.quote(query)
        url = f'https://www.in.gov.br/consulta/-/buscar/dou?q={encoded}&s={secao}&exactDate=mes'

        resultados = []
        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return []
                html = await resp.text()
        except Exception:
            return []

        # Extrair jsonArray do HTML
        pos = html.find('jsonArray')
        if pos < 0:
            return []

        start = html.find('[', pos)
        if start < 0:
            return []

        depth, end = 0, start
        for i in range(start, min(start + 500000, len(html))):
            if html[i] == '[':
                depth += 1
            elif html[i] == ']':
                depth -= 1
            if depth == 0:
                end = i + 1
                break

        try:
            raw = html[start:end].replace('\\/', '/')
            arr = json.loads(raw)
        except Exception:
            return []

        for item in arr[:20]:
            titulo = item.get('title', '')
            # Clean HTML tags from title
            titulo = re.sub(r'<[^>]+>', '', titulo).strip()
            content = re.sub(r'<[^>]+>', '', item.get('content', ''))
            pub_date = item.get('pubDate', '')
            url_title = item.get('urlTitle', '')
            section = item.get('pubName', '')

            link = f'https://www.in.gov.br/web/dou/-/{url_title}' if url_title else ''

            # Filter: keep items related to ANVISA/pharmaceutical/health imports
            texto_lower = f'{titulo} {content}'.lower()
            has_anvisa = 'anvisa' in texto_lower
            has_pharma_import = any(kw in texto_lower for kw in [
                'medicamento', 'insumos farmacêuticos', 'insumos farmaceuticos',
                'produtos para saúde', 'produtos para saude',
                'autorização de funcionamento', 'autorizacao de funcionamento',
                'princípio ativo', 'principio ativo',
            ])
            has_re_resolution = 'resolução-re' in texto_lower or 'resolucao-re' in texto_lower
            has_import = any(kw in texto_lower for kw in [
                'importar', 'importação', 'importacao', 'importador',
            ])
            has_judicial_health = any(kw in texto_lower for kw in [
                'decisão judicial', 'decisao judicial', 'mandado judicial',
            ]) and any(kw in texto_lower for kw in ['medicamento', 'saúde', 'saude', 'farmac'])
            
            # Accept: ANVISA content, pharma imports, RE resolutions with import, health judicial decisions
            if not (has_anvisa or has_pharma_import or (has_re_resolution and has_import) or has_judicial_health):
                continue

            # Extrair dados estruturados do conteúdo
            dados_extras = self._extrair_dados_dou(titulo, content)

            resultados.append({
                'titulo': titulo,
                'link': link,
                'data_publicacao': pub_date,
                'descricao': content[:1000],
                'categoria': f'DOU {section}',
                'fonte': f'DOU - {section}',
                'secao_dou': secao,
                'coletado_em': datetime.now(timezone.utc).isoformat(),
                **dados_extras,
            })

        return resultados

    def _extrair_dados_dou(self, titulo: str, content: str) -> Dict:
        """Extrai dados estruturados de publicações do DOU.
        
        Busca: Número da RE, Ação Judicial, Órgão Destinatário, Quantidade,
        Medicamentos mencionados, Empresas importadoras.
        """
        dados = {}
        texto = f'{titulo} {content}'
        texto_lower = texto.lower()

        # Número da Resolução-RE
        re_match = re.search(r'Resolu[çc][aã]o[- ]RE\s*n[ºo°]?\s*(\d[\d./]*)', texto, re.IGNORECASE)
        if re_match:
            dados['numero_re'] = re_match.group(1).strip()

        # Ação Judicial / Processo
        judicial_match = re.search(r'(?:A[çc][aã]o Judicial|Processo Judicial|Processo)\s*n[ºo°]?\s*([\d./-]+)', texto, re.IGNORECASE)
        if judicial_match:
            dados['numero_processo_judicial'] = judicial_match.group(1).strip()

        # Detectar se é cumprimento de decisão judicial
        if any(kw in texto_lower for kw in KW_JUDICIAL):
            dados['decisao_judicial'] = True

        # Órgão Destinatário / Interessado
        orgao_match = re.search(r'(?:Secretaria\s+(?:de\s+)?(?:Estado\s+de\s+)?Sa[uú]de|SES|Secretaria\s+Municipal)\s+(?:de|do|da)?\s*(\w[\w\s]{0,40})', texto, re.IGNORECASE)
        if orgao_match:
            dados['orgao_destinatario'] = orgao_match.group(0).strip()[:80]

        # Empresa importadora - buscar razão social de empresas com atividade IMPORTAR
        # Pattern: "EMPRESA NOME / CNPJ" seguido de atividade "IMPORTAR"
        import_sections = re.findall(
            r'([A-Z][A-Z\s&.,/-]{5,60})\s*/\s*(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}).*?IMPORTAR',
            texto, re.DOTALL
        )
        if import_sections:
            empresas = [m[0].strip() for m in import_sections[:3]]
            dados['empresa_importadora'] = '; '.join(empresas)[:120]

        # Quantidade autorizada
        qtd_match = re.search(r'(\d[\d.,]*)\s*(?:unidades|comprimidos|frascos|ampolas|caixas|doses|mg|ml|UI|litros|kg)', texto, re.IGNORECASE)
        if qtd_match:
            dados['quantidade_autorizada'] = qtd_match.group(0).strip()

        # Extrair nomes de medicamentos do conteúdo completo
        # Busca por padrões comuns em publicações do DOU
        med_patterns = [
            r'(?:medicamento|produto)\s*:\s*([A-Z][A-Za-zÀ-ÿ\s]+?)(?:\s*[-,;.]|\s*\d)',
            r'(?:princípio ativo|principio ativo)\s*:\s*([A-Z][A-Za-zÀ-ÿ\s]+?)(?:\s*[-,;.]|\s*\d)',
            r'(?:IMPORTAR|DISTRIBUIR|FABRICAR)\s*:\s*(?:MEDICAMENTO[S]?\s*/?\s*)([A-Z][A-Za-zÀ-ÿ\s]+?)(?:\s*[-;]|\s*$)',
        ]
        for p in med_patterns:
            match = re.search(p, texto)
            if match:
                dados['medicamento_extraido'] = match.group(1).strip()[:60]
                break

        # Detectar tipo de documento
        if 'resolução-re' in texto_lower or 'resolucao-re' in texto_lower:
            dados['tipo_documento'] = 'Resolução-RE'
        elif any(kw in texto_lower for kw in ['autorização excepcional', 'importação excepcional']):
            dados['tipo_documento'] = 'Autorização Excepcional'
        elif dados.get('decisao_judicial'):
            dados['tipo_documento'] = 'Decisão Judicial'

        return dados

    # ===================== FILTRAGEM =====================
    def _filtrar_relevantes(self, items: List[Dict]) -> List[Dict]:
        """Filtra itens relevantes para desabastecimento/importação."""
        alertas = []
        vistos = set()

        for item in items:
            titulo_lower = item['titulo'].lower()
            desc_lower = item.get('descricao', '').lower()
            texto = f'{titulo_lower} {desc_lower}'

            # Dedup
            key = item['titulo'][:80]
            if key in vistos:
                continue

            # CMED items are always relevant (pre-classified)
            if item.get('is_cmed'):
                vistos.add(key)
                alertas.append(item)
                continue

            # Verificar relevância
            is_importacao = any(kw in texto for kw in KW_IMPORTACAO)
            is_judicial = any(kw in texto for kw in KW_JUDICIAL)
            is_desabastecimento = any(kw in texto for kw in KW_DESABASTECIMENTO)
            is_saude = any(kw in texto for kw in KW_SAUDE)
            is_laboratorio = any(kw in texto for kw in KW_LABORATORIO)
            has_re = bool(item.get('numero_re'))
            has_tipo_doc = bool(item.get('tipo_documento'))

            if not (is_importacao or is_judicial or is_desabastecimento or is_saude or is_laboratorio or has_re or has_tipo_doc):
                continue

            vistos.add(key)

            # Classificar tipo
            if has_re or is_importacao:
                tipo = 'importacao_excepcional'
            elif is_judicial:
                tipo = 'decisao_judicial'
            elif is_desabastecimento:
                tipo = 'desabastecimento'
            else:
                tipo = 'alerta'

            alertas.append({
                **item,
                'tipo_alerta': tipo,
                'is_importacao': is_importacao,
                'is_judicial': is_judicial,
                'is_desabastecimento': is_desabastecimento,
                'is_laboratorio': is_laboratorio,
                'palavra_chave': self._primeira_keyword(texto),
            })

        return alertas

    @staticmethod
    def _primeira_keyword(texto: str) -> str:
        for kw in KW_IMPORTACAO + KW_JUDICIAL + KW_DESABASTECIMENTO + KW_LABORATORIO:
            if kw in texto:
                return kw
        return ''

    async def coletar_descontinuacao(self) -> List[Dict]:
        return []

    # ===================== FONTE CMED - DESABASTECIMENTO CONFIRMADO =====================
    async def coletar_cmed(self) -> List[Dict]:
        """
        Scraper da página CMED - Medicamentos com risco de desabastecimento.
        URL: https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/cmed/risco-de-desabastecimento
        
        Extrai todos os medicamentos listados na página.
        Cada medicamento é um alerta com janela_importacao=true.
        """
        url = 'https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/cmed/risco-de-desabastecimento'
        resultados = []

        try:
            async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        logger.error(f'CMED page returned {resp.status}')
                        return []
                    html = await resp.text()

            soup = BeautifulSoup(html, 'html.parser')
            # Find the main content area
            content = soup.find('div', id='content-core') or soup.find('div', class_='documentDescription') or soup.find('article')
            if not content:
                content = soup

            text = content.get_text(separator='\n', strip=True)

            # Extract medicines using Roman numeral pattern: "I - NOME (DOSE)"
            # Pattern matches: "I - SULFATO DE AMICACINA (250 MG/ML SOL INJ);"
            med_pattern = re.compile(
                r'(?:^|\n)\s*(?:[IVXLC]+)\s*[-–]\s*(.+?)(?:\s*[;.]?\s*$|\s*(?:e\s*$))',
                re.MULTILINE
            )
            matches = med_pattern.findall(text)

            # Clean up matches
            cleaned = []
            seen = set()
            for m in matches:
                clean = m.strip().rstrip(';.,').strip()
                # Remove trailing "e" (from "X; e")
                if clean.endswith(' e') or clean.endswith(' E'):
                    clean = clean[:-2].strip()
                clean = clean.rstrip(';.,').strip()
                if not clean or len(clean) < 5:
                    continue
                if clean.upper().startswith(('A LIBERAÇÃO', 'PARA QUE', 'VALE RESSALTAR')):
                    continue
                # Dedup by first 20 chars uppercase
                dedup_key = clean.upper()[:20]
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)
                cleaned.append(clean)
            matches = cleaned

            # Also try bold patterns from HTML
            for tag in content.find_all(['strong', 'b']):
                tag_text = tag.get_text(strip=True)
                # Match patterns like "HEPARINA SÓDICA SUÍNA 5.000 UI"
                if re.match(r'^[A-ZÁÉÍÓÚÂÊÔÃÕÇ\s]+\d', tag_text) and len(tag_text) > 8:
                    clean = tag_text.strip().rstrip(';.,').strip()
                    if clean.endswith(' e') or clean.endswith(' E'):
                        clean = clean[:-2].strip()
                    dedup_key = clean.upper()[:25]
                    if dedup_key not in seen and clean not in matches:
                        seen.add(dedup_key)
                        matches.append(clean)

            # Determine which phase each medicine belongs to
            fases_text = text.lower()
            fases = []
            for i, match in enumerate(matches):
                clean = match.strip().rstrip(';.,')
                if not clean or len(clean) < 5:
                    continue
                if clean.upper().startswith(('A LIBERAÇÃO', 'PARA QUE', 'VALE RESSALTAR')):
                    continue

                # Extract medicine name and dose
                dose_match = re.match(r'(.+?)\s*\((.+?)\)', clean)
                if dose_match:
                    nome = dose_match.group(1).strip()
                    dose = dose_match.group(2).strip()
                else:
                    # Try to split name from dose at first number after space
                    name_dose = re.match(r'^([A-ZÁÉÍÓÚÂÊÔÃÕÇ\s]+?)\s+(\d.+)$', clean)
                    if name_dose:
                        nome = name_dose.group(1).strip()
                        dose = name_dose.group(2).strip()
                    else:
                        nome = clean
                        dose = ''

                # Determine phase based on position
                fase = self._detectar_fase(text, clean)

                resultados.append({
                    'titulo': f'{nome} - Desabastecimento CMED',
                    'medicamento_detectado': nome,
                    'principio_ativo': nome,
                    'dose': dose,
                    'tipo_alerta': 'desabastecimento',
                    'situacao': f'Risco de desabastecimento confirmado pela CMED (Resolução CM-CMED nº 07/2022) - {fase}',
                    'fonte': 'CMED/ANVISA',
                    'link': url,
                    'risco': 'ALTO',
                    'oportunidade': 'Importação',
                    'janela_importacao': True,
                    'motivo_janela': f'Medicamento com risco de desabastecimento confirmado oficialmente pela CMED. Liberação de preços para garantir abastecimento.',
                    'fase_cmed': fase,
                    'base_legal': 'Resolução CM-CMED nº 7, de 1º de junho de 2022',
                    'coletado_em': datetime.now(timezone.utc).isoformat(),
                    'tipo_documento': 'Resolução CMED',
                    'is_cmed': True,
                })

            logger.info(f'CMED: {len(resultados)} medicamentos extraídos')
            return resultados

        except Exception as e:
            logger.error(f'CMED scraper erro: {e}')
            return []

    @staticmethod
    def _detectar_fase(text: str, med_name: str) -> str:
        """Detecta a qual fase de liberação o medicamento pertence."""
        text_lower = text.lower()
        med_lower = med_name.lower()
        
        # Find position of medicine in text
        pos = text_lower.find(med_lower)
        if pos < 0:
            return 'CMED'

        # Find which phase section it's in
        fases_pos = []
        for marker in ['1ª fase', '2ª fase', '3ª fase', '4ª fase']:
            idx = text_lower.find(marker)
            if idx >= 0:
                fases_pos.append((idx, marker.upper()))

        fases_pos.sort()
        fase = 'CMED'
        for fase_idx, fase_name in fases_pos:
            if pos > fase_idx:
                fase = fase_name
        return fase

