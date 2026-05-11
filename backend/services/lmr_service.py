"""
LMR Service - Analise de Importacao sob IN 428/2026
Motor de inteligencia para estrategia tributaria/comercial de importacao.

A IN 428/2026 (Instrucao Normativa) rege:
- Lista de Medicamentos de Referencia (LMR) para precificacao
- Regras de importacao excepcional
- Margens de comercializacao permitidas
- Classificacao tributaria (ICMS, PIS/COFINS)

Estrutura modular para facil atualizacao quando normas mudarem.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ==================== TABELAS DE REFERENCIA IN 428/2026 ====================
# Facil de atualizar quando a norma mudar

FAIXAS_MARGEM_IN428 = {
    'biologico': {'margem_distribuidora': 0.21, 'margem_farmacia': 0.335, 'cap_icms': 0.18},
    'sintetico': {'margem_distribuidora': 0.205, 'margem_farmacia': 0.315, 'cap_icms': 0.18},
    'generico': {'margem_distribuidora': 0.18, 'margem_farmacia': 0.28, 'cap_icms': 0.17},
    'similar': {'margem_distribuidora': 0.19, 'margem_farmacia': 0.29, 'cap_icms': 0.17},
    'excepcional': {'margem_distribuidora': 0.25, 'margem_farmacia': 0.35, 'cap_icms': 0.18},
}

ALIQUOTAS_TRIBUTARIAS = {
    'pis': 0.0165,
    'cofins': 0.076,
    'icms_padrao': 0.18,
    'icms_reduzido': 0.12,
    'ii_medicamento': 0.08,
}

CATEGORIAS_LMR = {
    'lista_positiva': {
        'descricao': 'Medicamento presente na LMR - importacao facilitada',
        'beneficio': 'Isencao parcial II + reducao ICMS',
        'risco_comercial': 'baixo',
    },
    'lista_negativa': {
        'descricao': 'Medicamento NAO presente na LMR - importacao com restricoes',
        'beneficio': 'Nenhum beneficio tributario especial',
        'risco_comercial': 'alto',
    },
    'excepcional': {
        'descricao': 'Importacao excepcional por desabastecimento (RDC 488/2021)',
        'beneficio': 'Isencao II + ICMS reduzido + prioridade ANVISA',
        'risco_comercial': 'medio',
    },
    'judicial': {
        'descricao': 'Importacao via decisao judicial',
        'beneficio': 'Isencao total impostos conforme liminar',
        'risco_comercial': 'medio-alto',
    },
}


class LmrService:
    def __init__(self, db):
        self.db = db

    async def analisar_medicamento(self, medicamento: str, preco_referencia: float = 0, tipo_produto: str = 'sintetico') -> Dict:
        """
        Analisa um medicamento sob as regras da IN 428/2026.
        Retorna estrategia tributaria, margens e recomendacao.
        """
        # 'todos' = usuario nao sabe o tipo, usar sintetico como base
        tipo_efetivo = tipo_produto if tipo_produto in FAIXAS_MARGEM_IN428 else 'sintetico'

        resultado = {
            'medicamento': medicamento,
            'norma_referencia': 'IN 428/2026 (Lista de Medicamentos de Referencia)',
            'executado_em': datetime.now(timezone.utc).isoformat(),
            'tipo_produto': tipo_efetivo,
            'classificacao_lmr': None,
            'estrategia_tributaria': None,
            'analise_margem': None,
            'recomendacao': '',
            'oportunidade_score': 0,
        }

        # 1. Verificar classificacao LMR
        classificacao = await self._classificar_lmr(medicamento)
        resultado['classificacao_lmr'] = classificacao

        # 2. Calcular estrategia tributaria
        faixa = FAIXAS_MARGEM_IN428[tipo_efetivo]
        resultado['estrategia_tributaria'] = self._calcular_tributacao(
            classificacao['categoria'], faixa, preco_referencia
        )

        # 3. Analise de margem
        if preco_referencia > 0:
            resultado['analise_margem'] = self._calcular_margem(
                preco_referencia, faixa, classificacao['categoria']
            )

        # 4. Score de oportunidade
        score = self._calcular_oportunidade_score(classificacao, resultado['estrategia_tributaria'])
        resultado['oportunidade_score'] = score

        # 5. Recomendacao
        resultado['recomendacao'] = self._gerar_recomendacao(classificacao, score, tipo_efetivo)

        # 6. Trigger: salvar alerta se score >= 80%
        if score >= 80:
            await self._salvar_alerta_oportunidade(resultado)

        return resultado

    async def _classificar_lmr(self, medicamento: str) -> Dict:
        """Classifica o medicamento na LMR (Lista de Medicamentos de Referencia)"""
        # Verificar se tem janela aberta (desabastecimento)
        try:
            alertas = await self.db.anvisa_alerts.find(
                {'$or': [
                    {'medicamento': {'$regex': medicamento, '$options': 'i'}},
                    {'medicamento_detectado': {'$regex': medicamento, '$options': 'i'}},
                    {'principio_ativo': {'$regex': medicamento, '$options': 'i'}},
                ]},
                {'_id': 0}
            ).to_list(length=5)
        except Exception:
            alertas = []

        has_janela = any(a.get('janela_importacao') for a in alertas)
        has_judicial = any('judicial' in (a.get('tipo_alerta') or '') for a in alertas)
        has_alerta = len(alertas) > 0

        # Lookup na collection desabastecimento_inteligencia (Radar Farmaceutico)
        desab_match = None
        try:
            desab_match = await self.db.desabastecimento_inteligencia.find_one(
                {'$or': [
                    {'medicamento': {'$regex': medicamento, '$options': 'i'}},
                    {'principio_ativo': {'$regex': medicamento, '$options': 'i'}},
                ]},
                {'_id': 0}
            )
        except Exception:
            pass

        has_desabastecimento = desab_match is not None and desab_match.get('score_boost', 0) >= 95

        if has_desabastecimento:
            categoria = 'excepcional'
        elif has_judicial:
            categoria = 'judicial'
        elif has_janela:
            categoria = 'excepcional'
        elif has_alerta:
            categoria = 'lista_positiva'
        else:
            categoria = 'lista_negativa'

        info = CATEGORIAS_LMR[categoria]
        return {
            'categoria': categoria,
            'descricao': info['descricao'],
            'beneficio_tributario': info['beneficio'],
            'risco_comercial': info['risco_comercial'],
            'total_alertas': len(alertas),
            'janela_aberta': has_janela or has_desabastecimento,
            'via_judicial': has_judicial,
            'desabastecimento_detectado': has_desabastecimento,
            'desabastecimento_info': {
                'status': desab_match.get('status_anvisa', ''),
                'categoria_terapeutica': desab_match.get('categoria_terapeutica', ''),
                'fonte': desab_match.get('fonte_deteccao', ''),
            } if desab_match else None,
        }

    def _calcular_tributacao(self, categoria: str, faixa: Dict, preco_ref: float) -> Dict:
        """Calcula a carga tributaria estimada"""
        if categoria == 'excepcional':
            ii = 0.0
            icms = ALIQUOTAS_TRIBUTARIAS['icms_reduzido']
            beneficio_extra = 'Isencao II + ICMS reduzido (Art. 12, IN 428/2026)'
        elif categoria == 'judicial':
            ii = 0.0
            icms = 0.0
            beneficio_extra = 'Isencao total conforme liminar judicial'
        elif categoria == 'lista_positiva':
            ii = ALIQUOTAS_TRIBUTARIAS['ii_medicamento'] * 0.5
            icms = ALIQUOTAS_TRIBUTARIAS['icms_reduzido']
            beneficio_extra = 'Reducao II 50% + ICMS reduzido (LMR positiva)'
        else:
            ii = ALIQUOTAS_TRIBUTARIAS['ii_medicamento']
            icms = ALIQUOTAS_TRIBUTARIAS['icms_padrao']
            beneficio_extra = 'Sem beneficio tributario especial'

        pis = ALIQUOTAS_TRIBUTARIAS['pis']
        cofins = ALIQUOTAS_TRIBUTARIAS['cofins']
        carga_total = ii + icms + pis + cofins

        custo_importacao_estimado = preco_ref * (1 + carga_total) if preco_ref > 0 else 0

        return {
            'imposto_importacao': round(ii * 100, 2),
            'icms': round(icms * 100, 2),
            'pis': round(pis * 100, 2),
            'cofins': round(cofins * 100, 2),
            'carga_tributaria_total': round(carga_total * 100, 2),
            'beneficio': beneficio_extra,
            'custo_importacao_estimado': round(custo_importacao_estimado, 2) if custo_importacao_estimado > 0 else None,
            'margem_distribuidora': round(faixa['margem_distribuidora'] * 100, 2),
            'margem_farmacia': round(faixa['margem_farmacia'] * 100, 2),
        }

    def _calcular_margem(self, preco_ref: float, faixa: Dict, categoria: str) -> Dict:
        """Calcula margens de comercializacao"""
        margem_dist = faixa['margem_distribuidora']
        preco_distribuidora = preco_ref * (1 + margem_dist)
        lucro_bruto = preco_distribuidora - preco_ref

        if categoria in ('excepcional', 'judicial'):
            economia_tributaria = preco_ref * 0.12
        elif categoria == 'lista_positiva':
            economia_tributaria = preco_ref * 0.06
        else:
            economia_tributaria = 0

        return {
            'preco_referencia': round(preco_ref, 2),
            'preco_distribuidora': round(preco_distribuidora, 2),
            'lucro_bruto_unitario': round(lucro_bruto, 2),
            'margem_percentual': round(margem_dist * 100, 2),
            'economia_tributaria': round(economia_tributaria, 2),
        }

    def _calcular_oportunidade_score(self, classificacao: Dict, tributacao: Dict) -> int:
        """Score 0-100 de oportunidade de importacao"""
        # Desabastecimento detectado na lista de interesse = score 95 direto
        if classificacao.get('desabastecimento_detectado'):
            return 95

        score = 30
        if classificacao['janela_aberta']:
            score += 35
        if classificacao['via_judicial']:
            score += 20
        if classificacao['total_alertas'] > 0:
            score += 10
        carga = tributacao.get('carga_tributaria_total', 30)
        if carga < 20:
            score += 15
        elif carga < 30:
            score += 5
        risco = classificacao['risco_comercial']
        if risco == 'baixo':
            score += 10
        elif risco == 'medio':
            score += 5
        return min(score, 100)

    def _gerar_recomendacao(self, classificacao: Dict, score: int, tipo: str) -> str:
        """Gera recomendacao textual baseada na analise"""
        if score >= 80:
            return f'OPORTUNIDADE ALTA: Produto {tipo} com janela aberta e beneficios tributarios significativos. Recomenda-se acao imediata via IN 428/2026.'
        elif score >= 50:
            return f'OPORTUNIDADE MEDIA: Produto {tipo} com indicadores favoraveis. Verificar viabilidade comercial e disponibilidade de fornecedores internacionais.'
        elif score >= 30:
            return f'OPORTUNIDADE BAIXA: Produto {tipo} sem beneficios tributarios especiais. Avaliar se o preco de importacao compensa frente ao mercado domestico.'
        else:
            return f'NAO RECOMENDADO: Produto {tipo} sem respaldo legal para importacao facilitada. Carga tributaria integral aplicavel.'

    async def _salvar_alerta_oportunidade(self, resultado: Dict):
        """Salva alerta de oportunidade alta (score >= 80%) no MongoDB e dispara e-mail"""
        import uuid
        try:
            med = resultado.get('medicamento', '')
            # Evitar duplicatas recentes (mesmo medicamento nas ultimas 24h)
            from datetime import timedelta
            corte = datetime.now(timezone.utc) - timedelta(hours=24)
            existente = await self.db.oportunidades_alertas.find_one({
                'medicamento': med,
                'criado_em': {'$gte': corte.isoformat()},
            })
            if existente:
                return

            classif = resultado.get('classificacao_lmr', {})
            trib = resultado.get('estrategia_tributaria', {})
            alerta_id = str(uuid.uuid4())
            alerta_doc = {
                'id': alerta_id,
                'medicamento': med,
                'oportunidade_score': resultado.get('oportunidade_score', 0),
                'tipo_produto': resultado.get('tipo_produto', ''),
                'categoria_lmr': classif.get('categoria', ''),
                'beneficio': classif.get('beneficio_tributario', ''),
                'carga_tributaria': trib.get('carga_tributaria_total', 0),
                'recomendacao': resultado.get('recomendacao', ''),
                'janela_aberta': classif.get('janela_aberta', False),
                'lida': False,
                'criado_em': datetime.now(timezone.utc).isoformat(),
                'email_enviado': False,
                'email_status': 'pendente',
            }
            await self.db.oportunidades_alertas.insert_one(alerta_doc)
            logger.info(f"ALERTA OPORTUNIDADE ALTA: {med} (score={resultado.get('oportunidade_score')}%)")

            # Disparar e-mail via EmailService existente
            await self._disparar_email_oportunidade(alerta_id, resultado)

        except Exception as e:
            logger.error(f"Erro ao salvar alerta oportunidade: {e}")

    async def _disparar_email_oportunidade(self, alerta_id: str, resultado: Dict):
        """Dispara e-mail de oportunidade via EmailService (Resend) existente"""
        try:
            from services.email_service import get_email_service
            email_service = get_email_service()

            status = email_service.get_status()
            if not status.get('configurado'):
                logger.warning("EmailService nao configurado - e-mail de oportunidade nao enviado")
                await self.db.oportunidades_alertas.update_one(
                    {'id': alerta_id},
                    {'$set': {'email_status': 'servico_nao_configurado'}}
                )
                return

            med = resultado.get('medicamento', '')
            score = resultado.get('oportunidade_score', 0)
            classif = resultado.get('classificacao_lmr', {})
            trib = resultado.get('estrategia_tributaria', {})

            # URL do frontend - Radar LMR com ID do alerta
            import os
            base_url = os.environ.get('REACT_APP_BACKEND_URL', '')
            if not base_url:
                base_url = os.environ.get('BASE_URL', 'https://dama-legal-1.preview.emergentagent.com')
            link_radar_lmr = f"{base_url}?alerta={alerta_id}"

            # Montar edital para o template do EmailService
            edital_lmr = {
                'orgao': 'DAMA Intelligence - Radar LMR (IN 428/2026)',
                'numero_processo': f'LMR-{med[:20].upper()}',
                'modalidade': f'Categoria: {(classif.get("categoria") or "N/A").upper()}',
                'objeto': (
                    f'OPORTUNIDADE DE IMPORTACAO - Score {score}% | '
                    f'Medicamento: {med} | '
                    f'Beneficio: {classif.get("beneficio_tributario", "N/A")} | '
                    f'Carga tributaria: {trib.get("carga_tributaria_total", "N/A")}% | '
                    f'{resultado.get("recomendacao", "")}'
                ),
                'status_oportunidade': 'ATIVA',
                'link_pdf': link_radar_lmr,
                'is_dama_alert': True,
                'itens_correspondentes': [],
            }

            # Enviar para diretoria (em producao: CC_OBRIGATORIO / em teste: reply_to verificado)
            is_test_mode = email_service.sender == "onboarding@resend.dev"
            if is_test_mode:
                destinatario = email_service.reply_to  # Email verificado no Resend
            else:
                destinatario = email_service.CC_OBRIGATORIO[0] if email_service.CC_OBRIGATORIO else email_service.reply_to

            res = await email_service.enviar_alerta(
                destinatario=destinatario,
                termo=f'LMR {score}%: {med}',
                editais=[edital_lmr],
            )

            email_ok = res.get('status') in ('success', 'mocked')
            await self.db.oportunidades_alertas.update_one(
                {'id': alerta_id},
                {'$set': {
                    'email_enviado': email_ok,
                    'email_status': res.get('status', 'erro'),
                    'email_id': res.get('email_id'),
                    'email_destinatario': destinatario,
                }}
            )
            logger.info(f"Email oportunidade LMR: {res.get('status')} para {destinatario} (med={med}, score={score}%)")

        except Exception as e:
            logger.error(f"Erro ao disparar email oportunidade: {e}")
            try:
                await self.db.oportunidades_alertas.update_one(
                    {'id': alerta_id},
                    {'$set': {'email_status': f'erro: {str(e)[:100]}'}}
                )
            except Exception:
                pass

    async def listar_oportunidades(self, limite: int = 20) -> Dict:
        """Lista oportunidades de importacao rankeadas por score"""
        try:
            alertas = await self.db.anvisa_alerts.find(
                {'janela_importacao': True},
                {'_id': 0}
            ).to_list(length=100)
        except Exception:
            alertas = []

        oportunidades = []
        medicamentos_vistos = set()

        for alerta in alertas:
            med = alerta.get('medicamento_detectado') or alerta.get('medicamento') or ''
            if not med or med in medicamentos_vistos:
                continue
            medicamentos_vistos.add(med)

            pa = alerta.get('principio_ativo', '')
            tipo_alerta = alerta.get('tipo_alerta', '')
            risco = alerta.get('risco', 'MEDIO')
            indice = alerta.get('indice_oportunidade', 0)
            motivo = alerta.get('motivo_janela', '')
            link = alerta.get('link', '')

            is_judicial = 'judicial' in tipo_alerta
            score = 50
            if is_judicial:
                score += 20
            if indice >= 70:
                score += 15
            elif indice >= 40:
                score += 5
            if risco == 'ALTO':
                score += 10
            score = min(score, 100)

            categoria = 'judicial' if is_judicial else 'excepcional'
            info = CATEGORIAS_LMR[categoria]

            oportunidades.append({
                'medicamento': med,
                'principio_ativo': pa,
                'tipo_alerta': tipo_alerta,
                'risco': risco,
                'oportunidade_score': score,
                'categoria_lmr': categoria,
                'beneficio': info['beneficio'],
                'risco_comercial': info['risco_comercial'],
                'motivo': motivo,
                'link_prova': link,
                'indice_oportunidade': indice,
            })

        oportunidades.sort(key=lambda x: x['oportunidade_score'], reverse=True)

        # Estatisticas
        total = len(oportunidades)
        alta = sum(1 for o in oportunidades if o['oportunidade_score'] >= 80)
        media = sum(1 for o in oportunidades if 50 <= o['oportunidade_score'] < 80)
        baixa = total - alta - media

        return {
            'oportunidades': oportunidades[:limite],
            'total': total,
            'estatisticas': {
                'oportunidade_alta': alta,
                'oportunidade_media': media,
                'oportunidade_baixa': baixa,
            },
            'norma_referencia': 'IN 428/2026',
            'atualizado_em': datetime.now(timezone.utc).isoformat(),
        }


_lmr_service = None

def get_lmr_service(db) -> LmrService:
    global _lmr_service
    if _lmr_service is None:
        _lmr_service = LmrService(db)
    return _lmr_service
