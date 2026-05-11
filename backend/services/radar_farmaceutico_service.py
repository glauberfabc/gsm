"""
Radar Farmaceutico Service - Inteligencia de Desabastecimento
=============================================================
Modulo central para:
1. Lista de Interesse Estrategica (Oncologia, Doencas Raras, Peptideos)
2. Deteccao de desabastecimento via DOU/ANVISA
3. Cruzamento automatico: lista de interesse X desabastecimento
4. Trigger de alerta (score_boost=95) + Resend email
"""

import logging
import hashlib
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import uuid

logger = logging.getLogger(__name__)

COLLECTION_INTERESSE = 'lista_interesse_estrategica'
COLLECTION_DESABASTECIMENTO = 'desabastecimento_inteligencia'

# Termos de captura para DOU Secao 1
TERMOS_DESABASTECIMENTO = [
    'suspensão de fabricação',
    'suspensao de fabricacao',
    'interrupção definitiva',
    'interrupcao definitiva',
    'descontinuidade temporária',
    'descontinuidade temporaria',
    'reativação de fabricação',
    'reativacao de fabricacao',
    'interrupção de fabricação',
    'interrupcao de fabricacao',
    'interrupção temporária',
    'interrupcao temporaria',
    'descontinuação de medicamento',
    'descontinuacao de medicamento',
    'desabastecimento',
]

# Seeds iniciais da lista de interesse
SEEDS_LISTA_INTERESSE = [
    {
        'medicamento': 'Pembrolizumabe',
        'principio_ativo': 'Pembrolizumabe',
        'categoria': 'Oncologia',
        'prioridade': 'alta',
        'target_type': 'Importacao',
    },
    {
        'medicamento': 'Canabidiol',
        'principio_ativo': 'Canabidiol (CBD)',
        'categoria': 'Doencas Raras',
        'prioridade': 'alta',
        'target_type': 'Importacao',
    },
    {
        'medicamento': 'Semaglutida',
        'principio_ativo': 'Semaglutida',
        'categoria': 'Peptideos',
        'prioridade': 'alta',
        'target_type': 'Nacional',
    },
    {
        'medicamento': 'Eculizumabe',
        'principio_ativo': 'Eculizumabe',
        'categoria': 'Doencas Raras',
        'prioridade': 'alta',
        'target_type': 'Importacao',
    },
]


class RadarFarmaceuticoService:

    def __init__(self, db):
        self.db = db
        self.interesse = db[COLLECTION_INTERESSE]
        self.desabastecimento = db[COLLECTION_DESABASTECIMENTO]

    # ======================== SEED ========================

    async def seed_lista_interesse(self):
        """Insere seeds se a collection estiver vazia."""
        count = await self.interesse.count_documents({})
        if count > 0:
            return {'status': 'ja_existente', 'total': count}

        for item in SEEDS_LISTA_INTERESSE:
            item['id'] = str(uuid.uuid4())
            item['ativo'] = True
            item['criado_em'] = datetime.now(timezone.utc).isoformat()
            item['atualizado_em'] = datetime.now(timezone.utc).isoformat()
            await self.interesse.insert_one(item)

        return {'status': 'seeds_inseridos', 'total': len(SEEDS_LISTA_INTERESSE)}

    # ======================== CRUD LISTA INTERESSE ========================

    async def listar_interesse(self) -> List[Dict]:
        cursor = self.interesse.find({}, {'_id': 0}).sort('prioridade', 1)
        return await cursor.to_list(length=200)

    async def adicionar_interesse(self, data: Dict) -> Dict:
        doc = {
            'id': str(uuid.uuid4()),
            'medicamento': data['medicamento'].strip(),
            'principio_ativo': data.get('principio_ativo', data['medicamento']).strip(),
            'categoria': data.get('categoria', 'Oncologia'),
            'prioridade': data.get('prioridade', 'media'),
            'target_type': data.get('target_type', 'Importacao'),
            'ativo': True,
            'criado_em': datetime.now(timezone.utc).isoformat(),
            'atualizado_em': datetime.now(timezone.utc).isoformat(),
        }
        await self.interesse.insert_one(doc)
        doc.pop('_id', None)
        return doc

    async def remover_interesse(self, item_id: str) -> bool:
        result = await self.interesse.delete_one({'id': item_id})
        return result.deleted_count > 0

    async def atualizar_interesse(self, item_id: str, data: Dict) -> bool:
        update_fields = {}
        for key in ('medicamento', 'principio_ativo', 'categoria', 'prioridade', 'target_type', 'ativo'):
            if key in data:
                update_fields[key] = data[key]
        if not update_fields:
            return False
        update_fields['atualizado_em'] = datetime.now(timezone.utc).isoformat()
        result = await self.interesse.update_one({'id': item_id}, {'$set': update_fields})
        return result.modified_count > 0

    # ======================== SCAN DESABASTECIMENTO ========================

    async def executar_scan(self) -> Dict:
        """
        Executa scan completo:
        1. Coleta publicacoes DOU com termos de desabastecimento
        2. Cruza com alertas ANVISA existentes (anvisa_alertas)
        3. Cruza com lista de interesse
        4. Salva matches na collection desabastecimento_inteligencia
        5. Dispara alertas para matches com score_boost >= 95
        """
        logger.info("Radar Farmaceutico: iniciando scan de desabastecimento...")

        # 1. Buscar na lista de interesse
        interesse_list = await self.interesse.find(
            {'ativo': True}, {'_id': 0}
        ).to_list(length=200)

        if not interesse_list:
            return {'status': 'sem_lista_interesse', 'matches': 0}

        # 2. Buscar alertas ANVISA existentes (ja coletados pelo scraper)
        alertas_anvisa = await self.db.anvisa_alertas.find(
            {}, {'_id': 0}
        ).to_list(length=500)

        # 3. Coletar publicacoes DOU focadas em desabastecimento
        publicacoes_dou = await self._coletar_dou_desabastecimento()

        # 4. Cruzar com lista de interesse
        matches = []
        for item_interesse in interesse_list:
            med = item_interesse['medicamento'].lower()
            pa = item_interesse['principio_ativo'].lower()

            # Check ANVISA alertas
            for alerta in alertas_anvisa:
                alerta_med = (alerta.get('medicamento_detectado') or alerta.get('medicamento') or '').lower()
                alerta_pa = (alerta.get('principio_ativo') or '').lower()
                alerta_titulo = (alerta.get('titulo') or '').lower()
                alerta_desc = (alerta.get('descricao') or '').lower()

                texto_alerta = f"{alerta_med} {alerta_pa} {alerta_titulo} {alerta_desc}"
                if med in texto_alerta or pa in texto_alerta:
                    # Verificar se tem termos de desabastecimento
                    has_desab_term = any(t in texto_alerta for t in TERMOS_DESABASTECIMENTO)
                    if has_desab_term or alerta.get('janela_importacao'):
                        matches.append(self._criar_match(item_interesse, alerta, 'anvisa_alertas'))

            # Check publicacoes DOU novas
            for pub in publicacoes_dou:
                pub_texto = f"{pub.get('titulo', '')} {pub.get('descricao', '')}".lower()
                if med in pub_texto or pa in pub_texto:
                    matches.append(self._criar_match(item_interesse, pub, 'dou_scan'))

        # 5. Salvar matches e detectar novos para alerta
        novos = 0
        alertas_disparados = 0
        for match in matches:
            match_hash = hashlib.md5(
                f"{match['medicamento']}_{match['fonte_deteccao']}_{match.get('titulo_fonte', '')[:50]}".encode()
            ).hexdigest()

            existente = await self.desabastecimento.find_one({'_hash': match_hash})
            match['_hash'] = match_hash
            match['atualizado_em'] = datetime.now(timezone.utc).isoformat()

            if not existente:
                match['criado_em'] = datetime.now(timezone.utc).isoformat()
                await self.desabastecimento.insert_one(match)
                novos += 1

                # Trigger alerta se score_boost >= 95
                if match.get('score_boost', 0) >= 95:
                    await self._disparar_alerta_desabastecimento(match)
                    alertas_disparados += 1
            else:
                await self.desabastecimento.update_one(
                    {'_hash': match_hash}, {'$set': match}
                )

        stats = await self.estatisticas()
        logger.info(f"Radar Farmaceutico: {len(matches)} matches, {novos} novos, {alertas_disparados} alertas")

        return {
            'status': 'concluido',
            'total_interesse': len(interesse_list),
            'total_alertas_anvisa': len(alertas_anvisa),
            'total_publicacoes_dou': len(publicacoes_dou),
            'matches_encontrados': len(matches),
            'novos_registros': novos,
            'alertas_disparados': alertas_disparados,
            'estatisticas': stats,
        }

    def _criar_match(self, item_interesse: Dict, fonte: Dict, tipo_fonte: str) -> Dict:
        """Cria registro de match entre lista de interesse e fonte de desabastecimento."""
        titulo = fonte.get('titulo', '')
        descricao = fonte.get('descricao', '')
        texto = f"{titulo} {descricao}".lower()

        # Determinar status_anvisa
        status = 'desabastecimento_detectado'
        if 'reativação' in texto or 'reativacao' in texto:
            status = 'reativacao_fabricacao'
        elif 'interrupção definitiva' in texto or 'interrupcao definitiva' in texto:
            status = 'interrupcao_definitiva'
        elif 'suspensão' in texto or 'suspensao' in texto:
            status = 'suspensao_fabricacao'
        elif 'descontinuidade temporária' in texto or 'descontinuidade temporaria' in texto:
            status = 'descontinuidade_temporaria'

        # Tentar extrair data_interrupcao e previsao_retorno
        data_interrupcao = fonte.get('data_publicacao', '')
        previsao_retorno = ''
        retorno_match = re.search(r'previsão.*?(\d{2}/\d{2}/\d{4})', texto)
        if retorno_match:
            previsao_retorno = retorno_match.group(1)

        # Score boost: 95% se na lista de interesse + desabastecimento
        score_boost = 95 if status != 'reativacao_fabricacao' else 30

        return {
            'id': str(uuid.uuid4()),
            'medicamento': item_interesse['medicamento'],
            'principio_ativo': item_interesse['principio_ativo'],
            'categoria_terapeutica': item_interesse['categoria'],
            'prioridade': item_interesse['prioridade'],
            'target_type': item_interesse['target_type'],
            'na_lista_interesse': True,
            'status_anvisa': status,
            'data_interrupcao': data_interrupcao,
            'previsao_retorno': previsao_retorno,
            'score_boost': score_boost,
            'fonte_deteccao': tipo_fonte,
            'titulo_fonte': titulo[:200],
            'link_fonte': fonte.get('link', ''),
            'descricao_fonte': descricao[:500],
        }

    async def _coletar_dou_desabastecimento(self) -> List[Dict]:
        """Coleta publicacoes DOU focadas em desabastecimento/interrupcao."""
        import aiohttp

        queries = [
            'suspensão fabricação medicamento anvisa',
            'interrupção definitiva medicamento anvisa',
            'descontinuidade temporária medicamento anvisa',
            'reativação fabricação medicamento anvisa',
            'desabastecimento medicamento fabricação anvisa',
        ]

        resultados = []
        timeout = aiohttp.ClientTimeout(total=20)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }

        try:
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                for query in queries:
                    try:
                        items = await self._buscar_dou(session, query)
                        resultados.extend(items)
                    except Exception as e:
                        logger.error(f"DOU desabastecimento scan erro [{query[:30]}]: {e}")
        except Exception as e:
            logger.error(f"DOU session erro: {e}")

        # Dedup por titulo
        vistos = set()
        unicos = []
        for r in resultados:
            key = r.get('titulo', '')[:80]
            if key not in vistos:
                vistos.add(key)
                unicos.append(r)

        logger.info(f"DOU desabastecimento: {len(resultados)} coletados, {len(unicos)} unicos")
        return unicos

    async def _buscar_dou(self, session, query: str) -> List[Dict]:
        """Busca no DOU via jsonArray."""
        import urllib.parse
        import json

        encoded = urllib.parse.quote(query)
        url = f'https://www.in.gov.br/consulta/-/buscar/dou?q={encoded}&s=do1&exactDate=mes'

        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return []
                html = await resp.text()
        except Exception:
            return []

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

        resultados = []
        for item in arr[:15]:
            titulo = re.sub(r'<[^>]+>', '', item.get('title', '')).strip()
            content = re.sub(r'<[^>]+>', '', item.get('content', ''))
            pub_date = item.get('pubDate', '')
            url_title = item.get('urlTitle', '')
            link = f'https://www.in.gov.br/web/dou/-/{url_title}' if url_title else ''

            texto_lower = f'{titulo} {content}'.lower()

            # Filtrar: manter apenas se tem termos relevantes
            has_relevant = any(t in texto_lower for t in TERMOS_DESABASTECIMENTO)
            has_med = any(kw in texto_lower for kw in [
                'medicamento', 'farmac', 'principio ativo', 'princípio ativo',
                'laboratorio', 'laboratório', 'fabricante',
            ])

            if has_relevant and has_med:
                resultados.append({
                    'titulo': titulo,
                    'link': link,
                    'data_publicacao': pub_date,
                    'descricao': content[:1000],
                    'fonte': 'DOU Secao 1 - Desabastecimento',
                })

        return resultados

    # ======================== TRIGGER ALERTA ========================

    async def _disparar_alerta_desabastecimento(self, match: Dict):
        """Salva alerta de oportunidade + dispara email via Resend."""
        try:
            from services.lmr_service import get_lmr_service

            med = match['medicamento']
            lmr_svc = get_lmr_service(self.db)

            # Gerar analise LMR completa (forcar score 95 via desabastecimento)
            analise = await lmr_svc.analisar_medicamento(med, tipo_produto='biologico')

            # Forcar score para 95% (desabastecimento confirmado)
            alerta_id = str(uuid.uuid4())
            alerta_doc = {
                'id': alerta_id,
                'medicamento': med,
                'oportunidade_score': 95,
                'tipo_produto': analise.get('tipo_produto', 'biologico'),
                'categoria_lmr': 'excepcional',
                'beneficio': 'Desabastecimento detectado - Importacao excepcional (RDC 488/2021)',
                'carga_tributaria': analise.get('estrategia_tributaria', {}).get('carga_tributaria_total', 0),
                'recomendacao': f'DESABASTECIMENTO CRITICO: {med} ({match["categoria_terapeutica"]}) - {match["status_anvisa"]}. Acao imediata recomendada via IN 428/2026.',
                'janela_aberta': True,
                'lida': False,
                'criado_em': datetime.now(timezone.utc).isoformat(),
                'email_enviado': False,
                'email_status': 'pendente',
                'fonte_desabastecimento': True,
                'status_desabastecimento': match['status_anvisa'],
                'categoria_terapeutica': match['categoria_terapeutica'],
            }

            # Evitar duplicata (mesmo med nas ultimas 24h)
            corte = datetime.now(timezone.utc) - timedelta(hours=24)
            existente = await self.db.oportunidades_alertas.find_one({
                'medicamento': med,
                'fonte_desabastecimento': True,
                'criado_em': {'$gte': corte.isoformat()},
            })
            if existente:
                logger.info(f"Alerta desabastecimento duplicado (24h): {med}")
                return

            await self.db.oportunidades_alertas.insert_one(alerta_doc)

            # Disparar email
            await lmr_svc._disparar_email_oportunidade(alerta_id, {
                'medicamento': med,
                'oportunidade_score': 95,
                'tipo_produto': 'biologico',
                'classificacao_lmr': {
                    'categoria': 'excepcional',
                    'beneficio_tributario': 'Desabastecimento detectado - Importacao excepcional',
                },
                'estrategia_tributaria': analise.get('estrategia_tributaria', {}),
                'recomendacao': alerta_doc['recomendacao'],
            })

            logger.info(f"ALERTA DESABASTECIMENTO CRITICO: {med} - email disparado")

        except Exception as e:
            logger.error(f"Erro ao disparar alerta desabastecimento: {e}")

    # ======================== LISTAR DESABASTECIMENTO ========================

    async def listar_desabastecimento(self, limite: int = 50) -> List[Dict]:
        cursor = self.desabastecimento.find(
            {}, {'_id': 0, '_hash': 0}
        ).sort([('score_boost', -1), ('atualizado_em', -1)]).limit(limite)
        return await cursor.to_list(length=limite)

    async def estatisticas(self) -> Dict:
        total_interesse = await self.interesse.count_documents({'ativo': True})
        total_desab = await self.desabastecimento.count_documents({})
        criticos = await self.desabastecimento.count_documents({'score_boost': {'$gte': 95}})
        reativados = await self.desabastecimento.count_documents({'status_anvisa': 'reativacao_fabricacao'})

        # Por categoria terapeutica
        pipeline = [
            {'$group': {'_id': '$categoria_terapeutica', 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}},
        ]
        por_categoria = {}
        async for doc in self.desabastecimento.aggregate(pipeline):
            por_categoria[doc['_id']] = doc['count']

        # Por status
        pipeline_status = [
            {'$group': {'_id': '$status_anvisa', 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}},
        ]
        por_status = {}
        async for doc in self.desabastecimento.aggregate(pipeline_status):
            por_status[doc['_id']] = doc['count']

        return {
            'total_lista_interesse': total_interesse,
            'total_desabastecimento': total_desab,
            'criticos': criticos,
            'reativados': reativados,
            'por_categoria': por_categoria,
            'por_status': por_status,
        }


_radar_farmaceutico_service = None


def get_radar_farmaceutico_service(db) -> RadarFarmaceuticoService:
    global _radar_farmaceutico_service
    if _radar_farmaceutico_service is None:
        _radar_farmaceutico_service = RadarFarmaceuticoService(db)
    return _radar_farmaceutico_service
