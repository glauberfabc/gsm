"""
Serviço de Desabastecimento - Janela de Importação v3
=====================================================
Processa alertas coletados do scraper (ANVISA + DOU + Votos),
usa Gemini para extrair nome do medicamento e detectar janelas
de importação.

Fluxo regulatório implementado:
1. Detecta descontinuidade/desabastecimento
2. Classifica o tipo de janela (RDC 488, RDC 203, etc.)
3. Atribui índice de oportunidade (0-100%)
4. Cruza com licitações no PNCP
"""

import os
import logging
import hashlib
from datetime import datetime, timezone
from typing import List, Dict
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

COLLECTION = 'anvisa_alertas'

# ============================================================
# GATILHOS REGULATÓRIOS
# ============================================================
GATILHOS = {
    'importacao_excepcional': {
        'keywords': ['rdc 488', 'importação excepcional', 'importação em caráter excepcional', 'importação temporária', 'importação sem registro', 'indisponibilidade no mercado'],
        'peso': 35,
        'label': 'Importação Excepcional (RDC 488)',
    },
    'emergencia_saude': {
        'keywords': ['emergência de saúde pública', 'rdc 203', 'programas públicos', 'crise sanitária'],
        'peso': 30,
        'label': 'Emergência Saúde Pública (RDC 203)',
    },
    'interrupcao_fabricacao': {
        'keywords': ['interrupção de fabricação', 'interrupção fabricação', 'suspensão de fabricação', 'parada de produção', 'fábrica interditada'],
        'peso': 30,
        'label': 'Interrupção de Fabricação',
    },
    'desabastecimento': {
        'keywords': ['desabastecimento', 'falta de medicamento', 'falta no mercado', 'ruptura de estoque', 'medicamento em falta'],
        'peso': 30,
        'label': 'Risco de Desabastecimento',
    },
    'descontinuacao': {
        'keywords': ['descontinuação', 'descontinuidade', 'descontinuado', 'cancelamento de registro', 'registro cancelado', 'saída do mercado'],
        'peso': 25,
        'label': 'Descontinuação / Cancelamento',
    },
    'recolhimento': {
        'keywords': ['recolhimento', 'recall', 'interdição', 'apreensão', 'proibição', 'proíbe'],
        'peso': 20,
        'label': 'Recolhimento / Interdição',
    },
    'judicializacao': {
        'keywords': ['stf', 'tema 500', 'judicialização', 'fornecimento pelo estado', 'mandado judicial', 'liminar'],
        'peso': 15,
        'label': 'Judicialização / Demanda Crescente',
    },
    'falsificacao': {
        'keywords': ['falsificação', 'falsificado', 'sem registro', 'irregular'],
        'peso': 20,
        'label': 'Produto Irregular / Falsificado',
    },
}


def detectar_gatilhos(texto: str) -> List[Dict]:
    texto_lower = texto.lower()
    encontrados = []
    for key, config in GATILHOS.items():
        for kw in config['keywords']:
            if kw in texto_lower:
                encontrados.append({
                    'id': key,
                    'label': config['label'],
                    'peso': config['peso'],
                    'keyword': kw,
                })
                break
    return encontrados


def calcular_indice(gatilhos, risco, oportunidade, licitacoes=0, janela_importacao=False, decisao_judicial=False, numero_re=''):
    score = 10
    for g in gatilhos:
        score += g['peso']
    if risco == 'ALTO':
        score += 10
    elif risco == 'MEDIO':
        score += 5
    if oportunidade == 'Importação':
        score += 10
    elif oportunidade == 'Licitação provável':
        score += 5
    elif oportunidade == 'Demanda pública crítica':
        score += 8
    if licitacoes > 0:
        score += min(licitacoes * 3, 15)
    # Boost para janela de importação confirmada
    if janela_importacao:
        score += 20
    # Boost para decisão judicial (importação sem registro)
    if decisao_judicial:
        score += 15
    # Boost para Resolução-RE (confirmação oficial)
    if numero_re:
        score += 15
    return min(score, 100)


class DesabastecimentoService:

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db[COLLECTION]

    async def processar_alertas(self, alertas_brutos: List[Dict]) -> List[Dict]:
        if not alertas_brutos:
            return []

        # Separate CMED items (pre-classified) from items that need Gemini analysis
        cmed_items = [a for a in alertas_brutos if a.get('is_cmed')]
        outros_items = [a for a in alertas_brutos if not a.get('is_cmed')]

        vistos = set()
        unicos = []
        for a in outros_items:
            key = hashlib.md5(a['titulo'].encode()).hexdigest()
            if key not in vistos:
                vistos.add(key)
                unicos.append(a)

        # Analyze non-CMED items with Gemini
        analisados = await self._analisar_com_ia(unicos)

        # Add CMED items directly (they come pre-classified with all fields)
        for item in cmed_items:
            # Calculate indice for CMED items
            texto = f"{item.get('titulo','')} {item.get('situacao','')}"
            item['gatilhos'] = detectar_gatilhos(texto)
            item['indice_oportunidade'] = calcular_indice(
                item['gatilhos'], 'ALTO', 'Importação',
                janela_importacao=True,
            )
            analisados.append(item)

        for item in analisados:
            texto = f"{item.get('titulo','')} {item.get('descricao','')} {item.get('situacao','')}"
            item['gatilhos'] = detectar_gatilhos(texto)
            item['indice_oportunidade'] = calcular_indice(
                item['gatilhos'], item.get('risco', 'BAIXO'), item.get('oportunidade', 'Monitorar'),
                janela_importacao=item.get('janela_importacao', False),
                decisao_judicial=item.get('decisao_judicial', False),
                numero_re=item.get('numero_re', ''),
            )

        salvos = 0
        for item in analisados:
            item_id = hashlib.md5(item['titulo'].encode()).hexdigest()
            item['_hash'] = item_id
            item['atualizado_em'] = datetime.now(timezone.utc).isoformat()
            await self.collection.update_one(
                {'_hash': item_id}, {'$set': item}, upsert=True
            )
            salvos += 1

        logger.info(f"Desabastecimento: {salvos} alertas salvos")
        return analisados

    async def _analisar_com_ia(self, alertas: List[Dict]) -> List[Dict]:
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            from dotenv import load_dotenv
            load_dotenv()

            api_key = os.environ.get('EMERGENT_LLM_KEY', '')
            if not api_key:
                return self._analise_keywords(alertas)

            chat = LlmChat(
                api_key=api_key,
                session_id=f"anvisa-{datetime.now().strftime('%Y%m%d%H%M')}",
                system_message="""Você é um especialista em regulação farmacêutica brasileira e importação de medicamentos.

CONTEXTO: Estamos monitorando ANVISA e DOU para detectar JANELAS DE IMPORTAÇÃO.
Uma janela se abre quando:
- ANVISA publica uma Resolução-RE autorizando importação
- Há cumprimento de decisão judicial para importação sem registro
- Há autorização excepcional (RDC 488/RDC 203)
- Desabastecimento confirmado sem substituto nacional

REGRAS para "medicamento_detectado":
- Retorne APENAS UM nome, curto e pesquisável (máx 40 chars)
- Exemplos CORRETOS: "Pembrolizumabe", "Canabidiol", "Enoxaparina", "Insulina Glargina"
- Se houver múltiplos, retorne APENAS o principal
- NUNCA retorne "N/A", "Diversos", "Vários"

Campos obrigatórios (JSON):
1. "medicamento_detectado": UM único nome (máx 40 chars)
2. "principio_ativo": princípio ativo/substância (máx 40 chars)
3. "tipo_alerta": "importação excepcional" | "decisão judicial" | "desabastecimento" | "descontinuação" | "interrupção fabricação" | "recolhimento" | "proibição" | "regulamentação" | "informativo"
4. "situacao": resumo curto (máx 20 palavras)
5. "risco": "ALTO" | "MEDIO" | "BAIXO"
6. "oportunidade": "Importação" | "Licitação provável" | "Demanda pública crítica" | "Monitorar"
7. "janela_importacao": true SOMENTE se:
   - Resolução-RE autorizando IMPORTAÇÃO DE MEDICAMENTO ESPECÍFICO (não AFE/autorização de empresa)
   - Decisão judicial autorizando importação de MEDICAMENTO sem registro
   - RDC 488 ou RDC 203 com autorização explícita para IMPORTAR medicamento
   - Desabastecimento confirmado de medicamento ESPECÍFICO + importação autorizada
   ATENÇÃO: Resolução-RE sobre AFE (Autorização de Funcionamento de Empresa) NÃO é janela de importação!
   NÃO marque true para: recolhimentos, proibições, alertas gerais, mudanças regulatórias genéricas
8. "motivo_janela": se true, explicar em 1 frase
9. "numero_re": número da Resolução-RE se presente (ex: "1234/2026")
10. "orgao_destinatario": nome do órgão público/secretaria de saúde se mencionado
11. "quantidade_autorizada": quantidade e unidade se mencionada (ex: "5000 comprimidos")

Responda APENAS em JSON array puro."""
            ).with_model("gemini", "gemini-2.5-flash")

            textos = []
            for i, a in enumerate(alertas[:30]):
                desc = a.get('descricao', '')
                fonte = a.get('fonte', '')
                cat = a.get('categoria', '')
                numero_re = a.get('numero_re', '')
                tipo_doc = a.get('tipo_documento', '')
                
                parts = [f'{i+1}. [{fonte}]']
                if cat:
                    parts.append(f'[{cat}]')
                if tipo_doc:
                    parts.append(f'[{tipo_doc}]')
                if numero_re:
                    parts.append(f'[RE nº {numero_re}]')
                parts.append(a['titulo'])
                if desc:
                    # Send more content for DOU items to help extract medicine name
                    max_desc = 500 if 'DOU' in fonte else 250
                    parts.append(f'| {desc[:max_desc]}')
                textos.append(' '.join(parts))

            prompt = f"Analise {len(textos)} publicações do DOU/ANVISA. Identifique MEDICAMENTO, se há JANELA DE IMPORTAÇÃO, número da RE, órgão destinatário:\n\n" + "\n".join(textos)

            response = await chat.send_message(UserMessage(text=prompt))

            import json
            json_match = response
            if '```json' in response:
                json_match = response.split('```json')[1].split('```')[0]
            elif '```' in response:
                json_match = response.split('```')[1].split('```')[0]
            start = json_match.find('[')
            end = json_match.rfind(']') + 1
            if start >= 0 and end > start:
                dados_ia = json.loads(json_match[start:end])
            else:
                return self._analise_keywords(alertas)

            resultado = []
            for i, alerta in enumerate(alertas[:30]):
                ia = dados_ia[i] if i < len(dados_ia) else {}

                med = ia.get('medicamento_detectado', '') or ''
                if not med or med in ('N/A', 'Diversos', 'Medicamentos', 'Medicamento', '-', 'Vários', 'Não identificado', 'Não especificado'):
                    med = self._extrair_medicamento(alerta['titulo'])
                if ',' in med:
                    med = med.split(',')[0].strip()
                med = med[:60]

                pa = ia.get('principio_ativo', '') or ''
                if not pa or pa in ('N/A', 'Diversos', '-'):
                    pa = med

                def clean_na(val):
                    """Remove N/A, None, empty values."""
                    if not val or str(val).strip() in ('N/A', 'n/a', 'None', '-', '', 'null'):
                        return ''
                    return str(val).strip()

                resultado.append({
                    'titulo': alerta['titulo'],
                    'link': alerta.get('link', ''),
                    'descricao': alerta.get('descricao', ''),
                    'data_publicacao': alerta.get('data_publicacao', ''),
                    'categoria': alerta.get('categoria', ''),
                    'fonte': alerta.get('fonte', ''),
                    'medicamento_detectado': med,
                    'principio_ativo': pa,
                    'tipo_alerta': ia.get('tipo_alerta', alerta.get('tipo_alerta', 'informativo')),
                    'situacao': clean_na(ia.get('situacao', '')) or alerta.get('palavra_chave', ''),
                    'risco': ia.get('risco', 'MEDIO'),
                    'oportunidade': ia.get('oportunidade', 'Monitorar'),
                    'janela_importacao': ia.get('janela_importacao', False),
                    'motivo_janela': clean_na(ia.get('motivo_janela', '')),
                    # Novos campos estruturados - limpar N/A
                    'numero_re': clean_na(ia.get('numero_re', '')) or clean_na(alerta.get('numero_re', '')),
                    'orgao_destinatario': clean_na(ia.get('orgao_destinatario', '')) or clean_na(alerta.get('orgao_destinatario', '')),
                    'quantidade_autorizada': clean_na(ia.get('quantidade_autorizada', '')) or clean_na(alerta.get('quantidade_autorizada', '')),
                    'numero_processo_judicial': clean_na(alerta.get('numero_processo_judicial', '')),
                    'decisao_judicial': ia.get('tipo_alerta') == 'decisão judicial' or alerta.get('decisao_judicial', False),
                    'tipo_documento': clean_na(alerta.get('tipo_documento', '')),
                    'empresa_importadora': clean_na(alerta.get('empresa_importadora', '')),
                    'medicamento': med,
                    'coletado_em': alerta.get('coletado_em', ''),
                })

            return resultado

        except Exception as e:
            logger.error(f"Gemini análise erro: {e}")
            return self._analise_keywords(alertas)

    def _analise_keywords(self, alertas: List[Dict]) -> List[Dict]:
        resultado = []
        for alerta in alertas:
            texto = f"{alerta['titulo'].lower()} {alerta.get('descricao','').lower()}"
            medicamento = self._extrair_medicamento(alerta['titulo'])

            is_import = any(kw in texto for kw in ['importação excepcional', 'rdc 488', 'rdc 203', 'importação sem registro', 'resolução-re'])
            is_judicial = any(kw in texto for kw in ['decisão judicial', 'ação judicial', 'processo judicial', 'cumprimento de decisão'])
            is_desab = any(kw in texto for kw in ['desabastecimento', 'falta', 'ruptura', 'indisponibilidade'])
            is_interr = any(kw in texto for kw in ['interrupção', 'suspensão fabricação', 'parada produção'])
            is_desc = any(kw in texto for kw in ['descontinuação', 'descontinuado', 'cancelamento registro'])
            is_recolh = any(kw in texto for kw in ['recolhimento', 'recall', 'proíbe', 'proibição', 'interdição', 'apreensão'])

            if is_import:
                tipo, sit, risco, oport = 'importação excepcional', 'importação excepcional autorizada', 'ALTO', 'Importação'
                janela, motivo = True, 'Autorização de importação excepcional detectada'
            elif is_judicial:
                tipo, sit, risco, oport = 'decisão judicial', 'cumprimento de decisão judicial', 'ALTO', 'Importação'
                janela, motivo = True, 'Decisão judicial autoriza importação sem registro'
            elif is_desab:
                tipo, sit, risco, oport = 'desabastecimento', 'falta de medicamento detectada', 'ALTO', 'Importação'
                janela, motivo = True, 'Desabastecimento confirmado pode gerar janela de importação'
            elif is_interr:
                tipo, sit, risco, oport = 'interrupção fabricação', 'interrupção temporária', 'ALTO', 'Importação'
                janela, motivo = True, 'Interrupção de fabricação pode gerar importação excepcional'
            elif is_desc:
                tipo, sit, risco, oport = 'descontinuação', 'saída do mercado', 'ALTO', 'Importação'
                janela, motivo = True, 'Descontinuação pode abrir janela de importação'
            elif is_recolh:
                tipo, sit, risco, oport = 'recolhimento', 'recolhimento em curso', 'ALTO', 'Licitação provável'
                janela, motivo = False, ''
            else:
                tipo, sit, risco, oport = 'informativo', alerta.get('palavra_chave', 'alerta'), 'BAIXO', 'Monitorar'
                janela, motivo = False, ''

            resultado.append({
                'titulo': alerta['titulo'],
                'link': alerta.get('link', ''),
                'descricao': alerta.get('descricao', ''),
                'data_publicacao': alerta.get('data_publicacao', ''),
                'categoria': alerta.get('categoria', ''),
                'fonte': alerta.get('fonte', ''),
                'medicamento_detectado': medicamento,
                'principio_ativo': medicamento,
                'tipo_alerta': tipo,
                'situacao': sit,
                'risco': risco,
                'oportunidade': oport,
                'janela_importacao': janela,
                'motivo_janela': motivo,
                # Novos campos do scraper
                'numero_re': alerta.get('numero_re', ''),
                'orgao_destinatario': alerta.get('orgao_destinatario', ''),
                'quantidade_autorizada': alerta.get('quantidade_autorizada', ''),
                'numero_processo_judicial': alerta.get('numero_processo_judicial', ''),
                'decisao_judicial': is_judicial or alerta.get('decisao_judicial', False),
                'tipo_documento': alerta.get('tipo_documento', ''),
                'empresa_importadora': alerta.get('empresa_importadora', ''),
                'medicamento': medicamento,
                'coletado_em': alerta.get('coletado_em', ''),
            })

        return resultado

    @staticmethod
    def _extrair_medicamento(titulo: str) -> str:
        import re
        # Patterns to extract specific medicine names from titles
        patterns = [
            r'(?:recolhimento|apreensão)\s+(?:de\s+)?(?:lote\s+(?:de|do)\s+)?(.+?)(?:\s*$)',
            r'[Dd]escontinuação[:\s]+(.+?)(?:\s*[-–]|\s*$)',
            r'falta de (.+?)(?:\s*[-–]|\s*no|\s*$)',
            r'interrupção.*?de (.+?)(?:\s*[-–]|\s*$)',
            r'(?:suspende|proíbe|interdita|recolhe|apreende)\s+(.+?)(?:\s*$)',
            r'(?:determina.*?recolhimento de)\s+(?:lote\s+(?:de|do)\s+)?(.+?)(?:\s*$)',
        ]
        for p in patterns:
            match = re.search(p, titulo, re.IGNORECASE)
            if match:
                result = match.group(1).strip()
                # Clean up prefixes
                for prefix in ['produtos e interdita ', 'produtos ', 'medidas contra ', 'suplementos alimentares da empresa ']:
                    if result.lower().startswith(prefix):
                        result = result[len(prefix):]
                # Take only the first product if comma-separated
                if ',' in result:
                    result = result.split(',')[0].strip()
                # Remove trailing articles/prepositions
                result = re.sub(r'\s+(de|da|do|e|em|por|para|sem|com)\s*$', '', result, flags=re.IGNORECASE)
                return result[:60]
        
        # Fallback: clean the title
        clean = re.sub(r'^(?:Anvisa|ANVISA)\s+\w+\s+', '', titulo)
        # Remove common prefixes
        clean = re.sub(r'^(?:Determinado\s+o?\s*|Determinada?\s+)', '', clean, flags=re.IGNORECASE)
        # Take first meaningful segment
        if ' - ' in clean:
            clean = clean.split(' - ')[0]
        return clean[:60]

    async def listar_alertas(self, limit: int = 50) -> List[Dict]:
        cursor = self.collection.find(
            {}, {'_id': 0, '_hash': 0}
        ).sort([('indice_oportunidade', -1), ('coletado_em', -1)]).limit(limit)
        return await cursor.to_list(length=limit)

    async def estatisticas(self) -> Dict:
        total = await self.collection.count_documents({})
        alto = await self.collection.count_documents({'risco': 'ALTO'})
        medio = await self.collection.count_documents({'risco': 'MEDIO'})
        importacao = await self.collection.count_documents({'oportunidade': 'Importação'})
        licitacao = await self.collection.count_documents({'oportunidade': 'Licitação provável'})
        demanda = await self.collection.count_documents({'oportunidade': 'Demanda pública crítica'})
        janelas = await self.collection.count_documents({'janela_importacao': True})
        oport_alta = await self.collection.count_documents({'indice_oportunidade': {'$gte': 70}})

        pipeline = [
            {'$group': {'_id': '$tipo_alerta', 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}}
        ]
        por_tipo = {r['_id']: r['count'] for r in await self.collection.aggregate(pipeline).to_list(20)}

        return {
            'total_alertas': total,
            'risco_alto': alto,
            'risco_medio': medio,
            'oportunidades_importacao': importacao,
            'oportunidades_licitacao': licitacao,
            'demanda_publica_critica': demanda,
            'janelas_abertas': janelas,
            'oportunidade_alta': oport_alta,
            'por_tipo': por_tipo,
        }
