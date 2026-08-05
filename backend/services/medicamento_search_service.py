"""
Serviço de busca inteligente de medicamento na Janela ANVISA v4.
DAMA Intelligence com Análise Semântica:

FILTRO DE SEMÂNTICA NEGATIVA:
- Documentos de rotina (CBPF, certificações, registro) são REBAIXADOS
- Não comprovam desabastecimento → marcados como 'rotina'

GATILHO "JANELA ABERTA" (Prova Legal):
- SOMENTE publicações oficiais (DOU/ANVISA/CMED) ativam Janela Aberta
- PNCP Deserto/Fracassado/Dispensa = INDICADOR DE MERCADO (não prova legal)
- DOU: "Interrupção de fabricação", "Redução de oferta" = prova FORTE
- CBPF, Regimento Interno, Insumos Farmacêuticos = rotina (REBAIXAR)

HIERARQUIA DE PROVA:
  1. DOU Desabastecimento/Descontinuação (prova oficial → ATIVA Janela Aberta)
  2. ANVISA Descontinuação (prova oficial → ATIVA Janela Aberta)
  3. CMED Risco (prova administrativa → ATIVA Janela Aberta)
  4. PNCP Deserto/Fracassado (indicador de mercado → NÃO ativa Janela Aberta)
  5. Notícias ANVISA (indício)
  6. Rotina (REBAIXAR - certificações, CBPF, registros)

Fontes:
1. DOU (Diário Oficial da União)
2. CMED risco de desabastecimento
3. Alertas ANVISA (Base GSM)
4. Notícias ANVISA
5. PNCP - Indicadores de Mercado (Deserto/Fracassado/Dispensa)
6. ANVISA Descontinuação
7. Registro ANVISA - dados abertos (registros cancelados/inativos, indicador de mercado)
"""
import re
import json
import logging
import asyncio
import urllib.parse
import aiohttp
from datetime import datetime, timezone, timedelta
from typing import Dict, List
from bs4 import BeautifulSoup

from services.medicamento_query_parser import (
    QueryEstruturada, dividir_termo, parse_termo_completo,
    contem_termo_estrito, contem_concentracao, resultado_relevante,
)

logger = logging.getLogger(__name__)

# Keywords de prioridade dinâmica (impacto real)
KW_IMPACTO = [
    'desabastecimento', 'indisponibilidade', 'excepcionalidade',
    'importação excepcional', 'falta de medicamento', 'descontinuação',
    'ruptura de estoque', 'deserto', 'fracassado', 'dispensa emergencial',
    'dispensa de licitação', 'decisão judicial', 'tutela',
    'interrupção de fabricação', 'redução de oferta',
    'descontinuidade temporária', 'descontinuidade definitiva',
    'item fracassado', 'licitação deserta', 'pregão deserto',
    'contratação direta', 'situação de emergência',
]

# Semântica negativa - documentos de ROTINA (não comprovam desabastecimento)
KW_ROTINA = [
    'certificação de boas práticas',
    'certificado de boas práticas',
    'boas práticas de fabricação',
    'boas praticas de fabricacao',
    'cbpf',
    'conceder à empresa',
    'conceder a empresa',
    'concessão de certificado',
    'insumos farmacêuticos ativos',
    'regimento interno art. 140',
    'regimento interno art.140',
    'registro de medicamento',
    'renovação de registro',
    'alteração pós-registro',
    'alteração pos-registro',
    'inclusão de local de fabricação',
    'petição de alteração',
    'petição de renovação',
    'cancelamento a pedido',
    'transferência de titularidade',
]

# Gatilhos que CONFIRMAM impacto real
KW_PROVA_FORTE = [
    'interrupção de fabricação', 'redução de oferta',
    'descontinuidade temporária', 'descontinuidade definitiva',
    'desabastecimento', 'indisponibilidade no mercado',
    'ruptura de estoque', 'falta de medicamento',
]

CUTOFF_DATE = datetime(2025, 1, 1, tzinfo=timezone.utc)
RECENTE_CUTOFF = datetime(2026, 1, 1, tzinfo=timezone.utc)
OBSOLETE_MONTHS = 6


class MedicamentoSearchService:
    def __init__(self, db):
        self.db = db
        self.timeout = aiohttp.ClientTimeout(total=25)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
        }

    async def _buscar_fonte(self, nome: str, coro) -> tuple:
        """Executa a busca de uma fonte isolando falhas (usado com asyncio.gather)."""
        try:
            items = await coro
            return nome, items, "ok"
        except Exception as e:
            logger.error(f"Erro busca {nome}: {e}")
            return nome, [], "erro"

    async def buscar(self, medicamento: str) -> Dict:
        """Busca completa com priorização dinâmica DAMA."""
        termo = medicamento.strip()
        if not termo:
            return {"resultados": [], "total": 0, "fontes_consultadas": []}

        resultados = []
        fontes = []

        async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as session:
            # As 6 fontes são consultadas em paralelo via asyncio.gather() - cada uma
            # com seu próprio try/except isolado, para que uma fonte lenta ou com erro
            # não atrase nem derrube as demais.
            tasks = [
                self._buscar_fonte("DOU - Diário Oficial da União", self._buscar_dou(session, termo)),
                self._buscar_fonte("Base de Alertas GSM", self._buscar_alertas_db(termo)),
                self._buscar_fonte("CMED - Risco de Desabastecimento", self._buscar_cmed_db(termo)),
                self._buscar_fonte("Notícias ANVISA", self._buscar_noticias_anvisa(session, termo)),
                self._buscar_fonte("PNCP - Licitações Desertas/Fracassadas", self._buscar_pncp_deserto(session, termo)),
                self._buscar_fonte("ANVISA - Descontinuação", self._buscar_descontinuacao(session, termo)),
                self._buscar_fonte("Registro ANVISA (Cancelados/Inativos)", self._buscar_registro_cancelado(termo)),
            ]
            for nome, items, status in await asyncio.gather(*tasks):
                resultados.extend(items)
                fontes.append({"nome": nome, "total": len(items), "status": status})

        # Dedup
        seen = set()
        deduped = []
        for r in resultados:
            key = r.get('titulo', '')[:60].upper()
            if key and key not in seen:
                seen.add(key)
                deduped.append(r)

        # ========== REFINAMENTO: Verificar conteúdo real dos DOU ambíguos ==========
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5), headers=self.headers) as refine_session:
                await self._refinar_dou_conteudo(refine_session, deduped)
        except Exception as e:
            logger.debug(f"Refinamento DOU falhou: {e}")

        # ========== ANÁLISE SEMÂNTICA DAMA v3 ==========
        now = datetime.now(timezone.utc)
        processed = []
        rotina_count = 0
        impacto_count = 0
        has_publicacao_oficial = False

        for r in deduped:
            parsed_date = self._parse_date(r.get('data_publicacao', ''))
            r['_parsed_date'] = parsed_date

            # Regra de corte temporal: ocultar pre-2025
            if parsed_date and parsed_date < CUTOFF_DATE:
                continue

            # Tag RECENTE para 2026+
            r['tag_recente'] = bool(parsed_date and parsed_date >= RECENTE_CUTOFF)

            # Obsolescência: >6 meses
            if parsed_date:
                r['_obsoleto'] = (now - parsed_date).days / 30 > OBSOLETE_MONTHS
            else:
                r['_obsoleto'] = False

            # ---- ANÁLISE DE CONTEÚDO (não apenas keywords) ----
            classificacao = self._classificar_conteudo(r)
            r['classificacao_dama'] = classificacao

            if classificacao == 'rotina':
                rotina_count += 1
                r['aviso_dama'] = 'Documento de rotina (certificação/registro) - não comprova desabastecimento'
            elif classificacao == 'impacto':
                impacto_count += 1
                # Janela Aberta: APENAS publicações oficiais com PROVA FORTE
                # Dispensas genéricas no DOU NÃO são suficientes
                fonte_busca = r.get('fonte_busca', '').lower()
                is_fonte_oficial = any(f in fonte_busca for f in ['dou', 'anvisa', 'cmed', 'descontinuação'])
                if is_fonte_oficial:
                    texto_completo = (r.get('titulo', '') + ' ' + r.get('descricao', '')).lower()
                    has_prova_forte = any(kw in texto_completo for kw in KW_PROVA_FORTE)
                    tipo = r.get('tipo_alerta', '')
                    is_tipo_relevante = tipo in ['desabastecimento', 'descontinuação', 'importação excepcional']
                    if has_prova_forte or is_tipo_relevante or 'descontinuação' in fonte_busca:
                        has_publicacao_oficial = True

            # Classificar risco COM análise semântica
            r['risco'] = self._classificar_risco(r)

            # Prioridade dinâmica COM penalização de rotina
            r['_prioridade'] = self._calcular_prioridade(r, now)

            processed.append(r)

        # Ordenar: prioridade (menor = melhor) → data desc
        processed.sort(key=lambda x: (
            x.get('_prioridade', 99),
            -(x.get('_parsed_date') or datetime.min.replace(tzinfo=timezone.utc)).timestamp(),
        ))

        # JANELA ABERTA: APENAS com publicação oficial (DOU/ANVISA/CMED)
        # PNCP é indicador de mercado, mas NÃO constitui respaldo legal
        janela_aberta = has_publicacao_oficial

        # Aviso de fallback quando só encontra rotina
        aviso_analise = None
        if rotina_count > 0 and impacto_count == 0:
            aviso_analise = (
                f"DAMA encontrou {rotina_count} documento(s) de rotina (certificações, registros), "
                f"mas nenhuma prova de desabastecimento. Continuando busca por editais desertos..."
            )
        elif rotina_count > 0 and impacto_count > 0:
            aviso_analise = (
                f"{impacto_count} documento(s) com impacto real identificado(s). "
                f"{rotina_count} documento(s) de rotina rebaixados."
            )

        # Limpar campos internos
        for r in processed:
            r.pop('_parsed_date', None)
            r.pop('_prioridade', None)
            r.pop('_obsoleto', None)

        return {
            "medicamento_buscado": termo,
            "resultados": processed,
            "total": len(processed),
            "fontes_consultadas": fontes,
            "janela_aberta": janela_aberta,
            "filtro_temporal": ">=2025",
            "analise_dama": {
                "impacto": impacto_count,
                "rotina": rotina_count,
                "aviso": aviso_analise,
                "has_publicacao_oficial": has_publicacao_oficial,
            },
        }

    # ===================== FONTE 1: DOU =====================
    async def _buscar_dou(self, session, termo: str) -> List[Dict]:
        """Busca no DOU com frases exatas estratégicas."""
        resultados = []
        queries = [
            termo,
            f'{termo} desabastecimento',
            f'{termo} dispensa de licitação',
        ]

        # Termos significativos (>3 chars) extraídos do nome para filtro de relevância.
        # Evita aceitar resultados do DOU que batem apenas em tokens genéricos como "20" ou "G-F".
        termos_sig = [
            t.lower() for t in re.split(r'[\s/\-,;]+', termo)
            if len(t) > 3
        ]

        for query in queries:
            try:
                encoded = urllib.parse.quote(query)
                url = f'https://www.in.gov.br/consulta/-/buscar/dou?q={encoded}&s=todos&exactDate=ano'
                async with session.get(url) as resp:
                    if resp.status != 200:
                        continue
                    html = await resp.text()

                items = self._extract_dou_json(html)
                for item in items[:12]:
                    titulo = item.get('title', '').strip()
                    if not titulo or len(titulo) < 10:
                        continue

                    # O DOU retorna o trecho relevante no campo 'content' (com o termo
                    # buscado destacado em <span class='highlight'>), não em 'abstract'.
                    # 'abstract' não existe mais no formato atual da API; mantido como
                    # fallback caso volte a aparecer em formatos antigos.
                    abstract_raw = item.get('abstract') or item.get('content') or ''
                    abstract = re.sub(r'<[^>]+>', ' ', abstract_raw)
                    abstract = re.sub(r'\s+', ' ', abstract).strip()

                    # Filtro de relevância: o título ou abstract deve conter ao menos
                    # um termo significativo do medicamento buscado.
                    if termos_sig:
                        texto_item = (titulo + ' ' + abstract).lower()
                        if not any(t in texto_item for t in termos_sig):
                            continue

                    href = item.get('urlTitle', '')
                    link = f"https://www.in.gov.br/web/dou/-/{href}" if href else ''

                    resultados.append({
                        'titulo': titulo,
                        'descricao': abstract[:300] if abstract else '',
                        'link': link,
                        'data_publicacao': item.get('pubDate', ''),
                        'fonte': 'DOU',
                        'fonte_busca': 'DOU',
                        'tipo_documento': item.get('artType', 'Publicação DOU'),
                        'secao': item.get('pubName', ''),
                        'tipo_alerta': self._detectar_tipo_alerta(titulo + ' ' + abstract),
                    })
            except Exception as e:
                logger.error(f"DOU search error for '{query}': {e}")

        return resultados

    def _extract_dou_json(self, html: str) -> list:
        """Extrai JSON de resultados do DOU (suporta formato antigo e novo)."""
        # Formato antigo: var jsonArray = [...]
        match = re.search(r'var\s+jsonArray\s*=\s*(\[.+?\]);\s*\n', html, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass

        # Formato novo: array JSON em script tags
        scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
        for s in scripts:
            arr_match = re.search(r'\[\s*\{.*?"title".*?"urlTitle".*?\}\s*\]', s, re.DOTALL)
            if arr_match:
                try:
                    return json.loads(arr_match.group(0))
                except Exception:
                    continue
        return []

    # ===================== FONTE 2: DB ALERTAS =====================
    async def _buscar_alertas_db(self, queries_estruturadas: List[QueryEstruturada]) -> List[Dict]:
        or_conditions = []
        for q in queries_estruturadas:
            r = re.compile(re.escape(q['principio_ativo']), re.IGNORECASE)
            or_conditions.extend([
                {"medicamento_detectado": r},
                {"principio_ativo": r},
                {"titulo": r},
                {"medicamento": r},
            ])

        cursor = self.db.anvisa_alertas.find(
            {"$or": or_conditions},
            {"_id": 0}
        ).sort("coletado_em", -1).limit(20)
        candidatos = await cursor.to_list(length=20)

        resultados = []
        for r in candidatos:
            texto = ' '.join(str(r.get(campo, '')) for campo in
                              ('medicamento_detectado', 'principio_ativo', 'titulo', 'medicamento'))
            match = resultado_relevante(texto, queries_estruturadas)
            if not match:
                continue
            r['fonte_busca'] = 'Base GSM'
            r['concentracao_confirmada'] = (
                contem_concentracao(texto, match['concentracao']) if match['concentracao'] else None
            )
            resultados.append(r)
        return resultados

    # ===================== FONTE 3: CMED DB =====================
    async def _buscar_cmed_db(self, queries_estruturadas: List[QueryEstruturada]) -> List[Dict]:
        or_conditions = []
        for q in queries_estruturadas:
            r = re.compile(re.escape(q['principio_ativo']), re.IGNORECASE)
            or_conditions.extend([
                {"medicamento_detectado": r},
                {"principio_ativo": r},
                {"titulo": r},
            ])
        cursor = self.db.anvisa_alertas.find(
            {"$and": [
                {"is_cmed": True},
                {"$or": or_conditions},
            ]},
            {"_id": 0}
        ).limit(10)
        candidatos = await cursor.to_list(length=10)

        resultados = []
        for r in candidatos:
            texto = ' '.join(str(r.get(campo, '')) for campo in
                              ('medicamento_detectado', 'principio_ativo', 'titulo'))
            match = resultado_relevante(texto, queries_estruturadas)
            if not match:
                continue
            r['fonte_busca'] = 'CMED'
            r['concentracao_confirmada'] = (
                contem_concentracao(texto, match['concentracao']) if match['concentracao'] else None
            )
            resultados.append(r)
        return resultados

    # ===================== FONTE 4: NOTÍCIAS ANVISA =====================
    async def _buscar_noticias_anvisa(self, session, termo: str) -> List[Dict]:
        resultados = []
        encoded = urllib.parse.quote(termo)
        url = f'https://www.gov.br/anvisa/pt-br/assuntos/noticias-anvisa?SearchableText={encoded}'

        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return []
                html = await resp.text()

            soup = BeautifulSoup(html, 'html.parser')
            lista = soup.find('ul', class_='noticias')
            if not lista:
                return []

            words = [w.lower() for w in termo.split() if len(w) >= 3]
            for li in lista.find_all('li', recursive=False)[:10]:
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

                    full = (titulo + ' ' + descricao).lower()
                    if words and not any(w in full for w in words):
                        continue

                    resultados.append({
                        'titulo': titulo,
                        'link': link,
                        'data_publicacao': data_pub,
                        'descricao': descricao,
                        'fonte': 'Notícias ANVISA',
                        'fonte_busca': 'Notícias ANVISA',
                        'tipo_alerta': self._detectar_tipo_alerta(titulo + ' ' + descricao),
                    })
                except Exception:
                    continue
        except Exception as e:
            logger.error(f"ANVISA notícias search: {e}")

        return resultados

    # ===================== FONTE 5: PNCP DESERTO/FRACASSADO =====================
    async def _buscar_pncp_deserto(self, session, termo: str) -> List[Dict]:
        """
        Busca licitações no PNCP como INDICADORES DE MERCADO:
        - Contratação Direta / Dispensa / Deserto / Fracassado
        - NÃO ativa 'Janela Aberta' (precisa de publicação oficial DOU/ANVISA)
        """
        resultados = []
        encoded = urllib.parse.quote(termo)
        url = f'https://pncp.gov.br/api/search/?q={encoded}&tipos_documento=edital&pagina=1&tam_pagina=30'

        try:
            headers = {**self.headers, 'Accept': 'application/json'}
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()

            items = data.get('items', [])

            for item in items[:30]:
                title = item.get('title', '')
                desc = item.get('description', '')
                full = (title + ' ' + desc).lower()
                created = item.get('createdAt', '')[:10]

                # Verificar relevância do medicamento
                if termo.lower()[:4] not in full:
                    continue

                # Detect patterns indicating JANELA ABERTA
                is_contratacao_direta = 'contratação direta' in full or 'contratacao direta' in full
                is_dispensa = 'dispensa' in full
                is_deserto = 'deserto' in full or 'desert' in full
                is_fracassado = 'fracassado' in full or 'fracass' in full
                is_emergencial = 'emergencial' in full or 'emergência' in full or 'emergencia' in full

                if not any([is_contratacao_direta, is_dispensa, is_deserto, is_fracassado, is_emergencial]):
                    continue

                # Build PNCP link
                orgao_cnpj = item.get('orgao_cnpj', '')
                ano = item.get('ano', '')
                seq = item.get('numero_sequencial', '')
                link_pncp = ''
                if orgao_cnpj and ano and seq:
                    link_pncp = f'https://pncp.gov.br/app/editais/{orgao_cnpj}/{ano}/{seq}'
                elif item.get('item_url'):
                    link_pncp = item['item_url']
                    if not link_pncp.startswith('http'):
                        link_pncp = f'https://pncp.gov.br{link_pncp}'

                # Classify - PNCP é indicador de mercado, NÃO prova legal
                if is_deserto or is_fracassado:
                    status_text = 'DESERTO/FRACASSADO'
                    tipo_alerta = 'indicador mercado'
                elif is_emergencial:
                    status_text = 'DISPENSA EMERGENCIAL'
                    tipo_alerta = 'indicador mercado'
                elif is_contratacao_direta:
                    status_text = 'CONTRATAÇÃO DIRETA'
                    tipo_alerta = 'indicador mercado'
                else:
                    status_text = 'DISPENSA'
                    tipo_alerta = 'indicador mercado'

                resultados.append({
                    'titulo': f'{status_text} - {title[:80]}',
                    'descricao': desc[:250],
                    'link': link_pncp,
                    'data_publicacao': created,
                    'fonte': 'PNCP',
                    'fonte_busca': f'PNCP {status_text}',
                    'tipo_alerta': tipo_alerta,
                    'tipo_documento': f'Licitação {status_text}',
                    'indicador_mercado': True,
                    'situacao_licitacao': status_text,
                })

        except Exception as e:
            logger.error(f"PNCP deserto search: {e}")

        return resultados

    # ===================== FONTE 6: ANVISA DESCONTINUAÇÃO =====================
    async def _buscar_descontinuacao(self, session, termo: str) -> List[Dict]:
        """Busca na página ANVISA de descontinuação de medicamentos."""
        resultados = []
        url = 'https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/descontinuacao-de-medicamentos'

        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return []
                html = await resp.text()

            soup = BeautifulSoup(html, 'html.parser')
            content = soup.find('div', id='content-core') or soup.find('article') or soup
            text = content.get_text(separator='\n', strip=True)

            if termo.lower() in text.lower():
                # Extract relevant paragraph
                lines = text.split('\n')
                relevant = []
                for line in lines:
                    if termo.lower() in line.lower():
                        relevant.append(line.strip())

                if relevant:
                    resultados.append({
                        'titulo': f'{termo} - Descontinuação ANVISA detectada',
                        'descricao': ' | '.join(relevant[:3])[:300],
                        'link': url,
                        'fonte': 'ANVISA',
                        'fonte_busca': 'ANVISA Descontinuação',
                        'tipo_alerta': 'descontinuação',
                        'risco': 'ALTO',
                    })
        except Exception as e:
            logger.error(f"ANVISA descontinuação search: {e}")

        return resultados

    # ===================== FONTE 7: REGISTRO ANVISA (DADOS ABERTOS) =====================
    async def _buscar_registro_cancelado(self, queries_estruturadas: List[QueryEstruturada]) -> List[Dict]:
        """
        Busca registros de medicamentos cancelados/inativos/vencidos no dataset
        aberto da ANVISA (sincronizado periodicamente por job, ver
        services/anvisa_registro_service.py). Registro ativo não é indício de
        nada, por isso a coleção só guarda os não-ativos.

        Classificado como indicador de mercado (mesma categoria do PNCP), não
        como prova legal - um registro cancelado não comprova sozinho que o
        medicamento está em falta (pode haver outros produtos com o mesmo
        princípio ativo ainda ativos no mercado).
        """
        or_conditions = []
        for q in queries_estruturadas:
            r = re.compile(re.escape(q['principio_ativo']), re.IGNORECASE)
            or_conditions.extend([
                {"nome_produto": r},
                {"principio_ativo": r},
            ])

        cursor = self.db.anvisa_registro_medicamentos.find(
            {"$or": or_conditions}, {"_id": 0}
        ).sort("data_finalizacao_processo", -1).limit(15)
        candidatos = await cursor.to_list(length=15)

        resultados = []
        for d in candidatos:
            texto = f"{d.get('nome_produto', '')} {d.get('principio_ativo', '')}"
            match = resultado_relevante(texto, queries_estruturadas)
            if not match:
                continue

            situacao = d.get('situacao_registro', '')
            nome = d.get('nome_produto', '')
            empresa = d.get('empresa_detentora_registro', '')
            resultados.append({
                'titulo': f'Registro {situacao.upper()} - {nome}',
                'descricao': (
                    f"Princípio ativo: {d.get('principio_ativo', '')} | "
                    f"Empresa: {empresa} | Situação: {situacao}"
                )[:300],
                'link': '',
                'data_publicacao': d.get('data_finalizacao_processo', ''),
                'fonte': 'ANVISA Registro',
                'fonte_busca': 'Registro ANVISA (dados abertos)',
                'tipo_alerta': 'indicador mercado',
                'tipo_documento': 'Situação de registro',
                'indicador_mercado': True,
                'situacao_licitacao': f'REGISTRO {situacao.upper()}',
                'concentracao_confirmada': (
                    contem_concentracao(texto, match['concentracao']) if match['concentracao'] else None
                ),
            })
        return resultados

    # ===================== HELPERS =====================
    async def _refinar_dou_conteudo(self, session, resultados: List[Dict]):
        """
        Busca o conteúdo real dos DOU results ambíguos para classificar
        como rotina (CBPF, certificação) vs impacto real.
        Verifica no máximo 5 resultados DOU para não impactar performance.
        """
        dou_para_refinar = [
            r for r in resultados
            if r.get('fonte_busca') == 'DOU'
            and r.get('link')
            and (not r.get('descricao') or r.get('descricao', '').startswith('Publicação DOU sobre'))
        ][:3]

        if not dou_para_refinar:
            return

        async def _fetch_content(r):
            try:
                async with session.get(r['link']) as resp:
                    if resp.status != 200:
                        return
                    html = await resp.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    # Extract main content
                    content_div = soup.find('div', class_='texto-dou') or soup.find('div', class_='materia') or soup.find('article')
                    if not content_div:
                        return

                    texto = content_div.get_text(separator=' ', strip=True).lower()

                    # Update description if empty
                    if not r.get('descricao') or r['descricao'].startswith('Publicação DOU sobre'):
                        clean_text = content_div.get_text(separator=' ', strip=True)[:250]
                        r['descricao'] = clean_text

                    # Check for rotina keywords in actual content
                    if self._is_rotina(texto):
                        r['_conteudo_rotina'] = True
                        r['tipo_alerta'] = 'rotina'

                    # Check for impacto keywords
                    if self._has_impacto(texto):
                        r['_conteudo_impacto'] = True

            except Exception as e:
                logger.debug(f"DOU content fetch error: {e}")

        tasks = [_fetch_content(r) for r in dou_para_refinar]
        await asyncio.gather(*tasks, return_exceptions=True)


    def _parse_date(self, date_str: str):
        """Parse date from various formats."""
        if not date_str:
            return None
        # Try common formats
        for fmt in [
            '%d/%m/%Y', '%Y-%m-%d', '%d/%m/%Y %H:%M',
            '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f',
            '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%S.%f%z',
        ]:
            try:
                dt = datetime.strptime(date_str[:len(date_str)], fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except (ValueError, TypeError):
                continue

        # Try extract year
        year_match = re.search(r'(20\d{2})', date_str)
        if year_match:
            try:
                return datetime(int(year_match.group(1)), 6, 15, tzinfo=timezone.utc)
            except Exception:
                pass
        return None

    def _detectar_tipo_alerta(self, texto: str) -> str:
        texto_lower = texto.lower()
        # Primeiro: verificar se é rotina
        if self._is_rotina(texto_lower):
            return 'rotina'
        if any(kw in texto_lower for kw in ['importação excepcional', 'importação de medicamento', 'autorização de importação']):
            return 'importação excepcional'
        if any(kw in texto_lower for kw in ['decisão judicial', 'cumprimento de decisão', 'tutela']):
            return 'decisão judicial'
        if any(kw in texto_lower for kw in ['desabastecimento', 'falta de medicamento', 'ruptura']):
            return 'desabastecimento'
        if any(kw in texto_lower for kw in ['descontinuação', 'descontinuado', 'interrupção de fabricação']):
            return 'descontinuação'
        if any(kw in texto_lower for kw in ['deserto', 'fracassado']):
            return 'janela aberta'
        if any(kw in texto_lower for kw in ['dispensa', 'emergencial', 'contratação direta']):
            return 'dispensa'
        if any(kw in texto_lower for kw in ['resolução-re', 'resolucao-re', 'rdc', 'instrução normativa']):
            return 'regulamentação'
        return 'informativo'

    def _is_rotina(self, texto_lower: str) -> bool:
        """Verifica se o texto indica documento de rotina (CBPF, registro, certificação)."""
        return any(kw in texto_lower for kw in KW_ROTINA)

    def _has_impacto(self, texto_lower: str) -> bool:
        """Verifica se o texto tem termos de impacto real (desabastecimento, ruptura)."""
        return any(kw in texto_lower for kw in KW_IMPACTO)

    def _classificar_conteudo(self, item: Dict) -> str:
        """
        Análise semântica de conteúdo DAMA v3.
        Classifica cada documento como:
        - 'impacto': Comprova desabastecimento/risco real
        - 'indicio': Indica possível risco (regulamentação, notícia)
        - 'rotina': Documento burocrático sem prova de desabastecimento
        """
        texto = (item.get('titulo', '') + ' ' + item.get('descricao', '')).lower()
        fonte = item.get('fonte_busca', '').lower()

        # PNCP = indicador de mercado (prioridade média, não prova legal)
        if item.get('indicador_mercado'):
            situacao = item.get('situacao_licitacao', '').upper()
            if 'DESERTO' in situacao or 'FRACASSADO' in situacao:
                return 'impacto'
            return 'indicio'

        # Se o refinamento de conteúdo já classificou
        if item.get('_conteudo_rotina') and not item.get('_conteudo_impacto'):
            return 'rotina'
        if item.get('_conteudo_impacto'):
            return 'impacto'

        # Documentos de rotina MESMO que contenham o nome do medicamento
        is_rotina = self._is_rotina(texto)
        has_impacto_kw = self._has_impacto(texto)

        # Se tem keywords de impacto E rotina, verificar qual prevalece
        if is_rotina and not has_impacto_kw:
            return 'rotina'

        # Se tem prova forte de impacto
        if has_impacto_kw:
            return 'impacto'

        # Fontes que já indicam impacto
        if 'cmed' in fonte or 'descontinuação' in fonte:
            return 'impacto'

        # DOU com tipo regulamentação pode ser rotina ou impacto
        if 'dou' in fonte:
            if is_rotina:
                return 'rotina'
            if any(kw in texto for kw in ['resolução-re', 'resolucao-re']):
                return 'indicio'

        return 'indicio'

    def _classificar_risco(self, item: Dict) -> str:
        texto = (item.get('titulo', '') + ' ' + item.get('descricao', '')).lower()
        classificacao = item.get('classificacao_dama', 'indicio')

        # Rotina = SEMPRE baixo, independente de keywords
        if classificacao == 'rotina':
            return 'BAIXO'

        # PNCP deserto/fracassado = indicador forte de mercado
        if item.get('indicador_mercado'):
            situacao = item.get('situacao_licitacao', '').upper()
            if 'DESERTO' in situacao or 'FRACASSADO' in situacao:
                return 'ALTO'
            return 'MÉDIO'

        # Impacto confirmado
        if classificacao == 'impacto':
            if any(kw in texto for kw in KW_PROVA_FORTE):
                return 'ALTO'
            return 'ALTO'

        # Indício
        if any(kw in texto for kw in ['resolução-re', 'resolucao-re', 'voto', 'dispensa']):
            return 'MÉDIO'

        return 'BAIXO'

    def _calcular_prioridade(self, item: Dict, now: datetime) -> int:
        """
        Prioridade dinâmica com penalização de rotina:
        0 = PNCP deserto/fracassado (prova material)
        1 = Impacto confirmado + recente (90 dias)
        2 = Impacto + 2025/2026
        3 = Indício recente
        4 = Indício normal
        5 = Rotina (SEMPRE rebaixado)
        6 = Obsoleto
        """
        classificacao = item.get('classificacao_dama', 'indicio')
        parsed = item.get('_parsed_date')
        is_recente = item.get('tag_recente', False)
        is_obsoleto = item.get('_obsoleto', False)

        # Rotina = SEMPRE rebaixado (antes de obsoleto)
        if classificacao == 'rotina':
            return 5

        # Obsoleto perde tudo
        if is_obsoleto:
            return 6

        # PNCP deserto/fracassado = indicador de mercado (prioridade alta, mas não máxima)
        if item.get('indicador_mercado'):
            situacao = item.get('situacao_licitacao', '').upper()
            if 'DESERTO' in situacao or 'FRACASSADO' in situacao:
                return 1
            return 2

        # Impacto confirmado
        if classificacao == 'impacto':
            if parsed:
                days_ago = (now - parsed).days
                if days_ago <= 90:
                    return 1
            return 2 if is_recente else 3

        # Indício
        if is_recente:
            return 3
        return 4


_service = None

def get_medicamento_search_service(db):
    global _service
    if _service is None:
        _service = MedicamentoSearchService(db)
    return _service
