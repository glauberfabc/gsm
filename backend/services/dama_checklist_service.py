"""
DAMA Checklist Service v2 - Verificacao automatizada de conformidade
Inclui Motor de Revogacao Cruzada (Cross-Reference)

Verifica:
1. Vigencia das normas citadas (com deteccao de revogacao)
2. Status do medicamento na lista de desabastecimento (Janela Aberta)
3. Publicacao oficial DOU/ANVISA
4. Analise LMR (IN 428/2026)
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ==================== TABELA DE REVOGACAO CRUZADA ====================
# Formato: norma_antiga -> {revogada_por, data_revogacao, observacao}
# Facil de atualizar: adicione novas entradas quando normas mudarem

REVOGACOES = {
    'rdc 327/2019': {
        'revogada_por': 'RDC 660/2022',
        'data': '2022-03-30',
        'obs': 'RDC 327/2019 foi integralmente revogada pela RDC 660/2022 que atualizou regras de produtos derivados de Cannabis.',
    },
    'rdc 327': {
        'revogada_por': 'RDC 660/2022',
        'data': '2022-03-30',
        'obs': 'RDC 327/2019 foi integralmente revogada pela RDC 660/2022.',
    },
    'rdc 17/2010': {
        'revogada_por': 'RDC 658/2022',
        'data': '2022-03-30',
        'obs': 'RDC 17/2010 (BPF) revogada pela RDC 658/2022 (nova BPF harmonizada).',
    },
    'rdc 17': {
        'revogada_por': 'RDC 658/2022',
        'data': '2022-03-30',
        'obs': 'RDC 17/2010 (BPF) revogada pela RDC 658/2022.',
    },
    'resolucao 02/2004': {
        'revogada_por': 'Resolucao 07/2022 CMED',
        'data': '2022-06-01',
        'obs': 'Resolucao CMED 02/2004 substituida pela Resolucao 07/2022 (novas regras de precificacao).',
    },
    'rdc 55/2005': {
        'revogada_por': 'RDC 751/2022',
        'data': '2022-09-29',
        'obs': 'RDC 55/2005 (registro simplificado) revogada pela RDC 751/2022.',
    },
    'in 11/2016': {
        'revogada_por': 'IN 428/2026',
        'data': '2026-01-15',
        'obs': 'IN 11/2016 (LMR anterior) substituida pela IN 428/2026 (nova Lista de Medicamentos de Referencia).',
    },
    'rdc 81/2008': {
        'revogada_por': 'RDC 488/2021',
        'data': '2021-07-23',
        'obs': 'RDC 81/2008 (importacao) atualizada pela RDC 488/2021 (importacao excepcional por desabastecimento).',
    },
    'rdc 185/2001': {
        'revogada_por': 'RDC 665/2022',
        'data': '2022-03-30',
        'obs': 'RDC 185/2001 (registro de dispositivos medicos) revogada pela RDC 665/2022.',
    },
}

# Normas vigentes de referencia (para sugestao)
NORMAS_VIGENTES_REF = {
    'importacao_excepcional': 'RDC 488/2021',
    'precificacao_cmed': 'Resolucao CMED 07/2022',
    'bpf': 'RDC 658/2022',
    'cannabis': 'RDC 660/2022',
    'lmr': 'IN 428/2026',
    'licitacao': 'Lei 14.133/2021',
    'registro_medicamento': 'RDC 751/2022',
}


class DamaChecklistService:
    def __init__(self, db):
        self.db = db

    async def executar_checklist(self, medicamento: str, normas: Optional[List[str]] = None) -> Dict:
        resultado = {
            'medicamento': medicamento,
            'executado_em': datetime.now(timezone.utc).isoformat(),
            'checks': [],
            'revogacoes_detectadas': [],
            'score_conformidade': 0,
            'recomendacao': '',
        }

        # Check 1: Vigencia normativa + Revogacao cruzada
        checks_vigencia, revogacoes = await self._check_vigencia_com_revogacao(normas or [])
        resultado['checks'].extend(checks_vigencia)
        resultado['revogacoes_detectadas'] = revogacoes

        # Check 2: Status desabastecimento (Janela Aberta)
        check_janela = await self._check_janela_aberta(medicamento)
        resultado['checks'].append(check_janela)

        # Check 3: Publicacao oficial DOU/ANVISA
        check_publicacao = await self._check_publicacao_oficial(medicamento)
        resultado['checks'].append(check_publicacao)

        # Check 4: Analise LMR (IN 428/2026)
        check_lmr = await self._check_lmr(medicamento)
        resultado['checks'].append(check_lmr)

        # Calcular score
        total = len(resultado['checks'])
        aprovados = sum(1 for c in resultado['checks'] if c['status'] == 'ok')
        alertas = sum(1 for c in resultado['checks'] if c['status'] == 'alerta')
        bloqueios = sum(1 for c in resultado['checks'] if c['status'] == 'bloqueio')

        if total > 0:
            resultado['score_conformidade'] = round((aprovados / total) * 100)

        if bloqueios > 0:
            resultado['recomendacao'] = 'BLOQUEIO: Existem normas caducas/revogadas ou ausencia de respaldo legal. Revise antes de prosseguir.'
        elif alertas > 0:
            resultado['recomendacao'] = 'ATENCAO: Alguns itens requerem verificacao manual. Revise os alertas antes de prosseguir.'
        else:
            resultado['recomendacao'] = 'APROVADO: Todos os checks passaram. O medicamento possui respaldo legal para oferta de produto importado.'

        resultado['resumo'] = {
            'total': total,
            'aprovados': aprovados,
            'alertas': alertas,
            'bloqueios': bloqueios,
        }

        # Normas vigentes de referencia
        resultado['normas_vigentes_referencia'] = NORMAS_VIGENTES_REF

        return resultado

    async def _check_vigencia_com_revogacao(self, normas: List[str]):
        """Verifica vigencia + detecta revogacoes cruzadas"""
        from services.vigencia_service import get_vigencia_service
        vigencia_svc = get_vigencia_service(self.db)

        checks = []
        revogacoes = []

        normas_padrao = [
            'Resolucao 07/2022',
            'RDC 488/2021',
        ]
        todas_normas = list(set(normas + normas_padrao))

        for norma in todas_normas:
            # --- REVOGACAO CRUZADA ---
            norma_lower = norma.lower().strip()
            revogacao = None
            for chave, info in REVOGACOES.items():
                if chave in norma_lower:
                    revogacao = info
                    break

            if revogacao:
                revogacoes.append({
                    'norma_obsoleta': norma,
                    'revogada_por': revogacao['revogada_por'],
                    'data_revogacao': revogacao['data'],
                    'observacao': revogacao['obs'],
                })
                checks.append({
                    'tipo': 'vigencia',
                    'item': f'Norma: {norma}',
                    'status': 'bloqueio',
                    'detalhe': f'REVOGADA por {revogacao["revogada_por"]} em {revogacao["data"]}.',
                    'status_norma': 'revogada',
                    'pode_usar': False,
                    'sugestao_substituicao': revogacao['revogada_por'],
                    'observacao_revogacao': revogacao['obs'],
                })
                continue

            # --- VERIFICACAO VIGENCIA NORMAL ---
            try:
                resultado = await vigencia_svc.verificar_vigencia(norma)
                if resultado.get('encontrada'):
                    status_norma = resultado.get('status', 'desconhecido')
                    pode_usar = resultado.get('pode_usar', False)
                    checks.append({
                        'tipo': 'vigencia',
                        'item': f'Norma: {norma}',
                        'status': 'ok' if pode_usar else 'bloqueio',
                        'detalhe': resultado.get('alerta', ''),
                        'status_norma': status_norma,
                        'pode_usar': pode_usar,
                        'sugestao_substituicao': None,
                    })
                else:
                    checks.append({
                        'tipo': 'vigencia',
                        'item': f'Norma: {norma}',
                        'status': 'alerta',
                        'detalhe': 'Norma nao encontrada na base CMED. Verifique manualmente.',
                        'status_norma': 'desconhecido',
                        'pode_usar': None,
                        'sugestao_substituicao': None,
                    })
            except Exception as e:
                logger.error(f"Erro ao verificar vigencia de {norma}: {e}")
                checks.append({
                    'tipo': 'vigencia',
                    'item': f'Norma: {norma}',
                    'status': 'alerta',
                    'detalhe': f'Erro na verificacao: {str(e)[:100]}',
                    'status_norma': 'erro',
                    'pode_usar': None,
                    'sugestao_substituicao': None,
                })

        return checks, revogacoes

    async def _check_janela_aberta(self, medicamento: str) -> Dict:
        from services.medicamento_search_service import get_medicamento_search_service
        try:
            search_svc = get_medicamento_search_service(self.db)
            resultado = await search_svc.buscar(medicamento)
            janela = resultado.get('janela_aberta', False)
            total = resultado.get('total', 0)
            dama = resultado.get('analise_dama', {})
            impacto = dama.get('impacto', 0)
            has_pub = dama.get('has_publicacao_oficial', False)

            if janela and has_pub:
                return {
                    'tipo': 'janela_aberta',
                    'item': f'Desabastecimento: {medicamento}',
                    'status': 'ok',
                    'detalhe': f'Janela Aberta confirmada. {impacto} publicacao(oes) oficial(is) de {total} resultados.',
                    'janela_aberta': True,
                    'total_resultados': total,
                }
            elif total > 0:
                return {
                    'tipo': 'janela_aberta',
                    'item': f'Desabastecimento: {medicamento}',
                    'status': 'alerta',
                    'detalhe': f'{total} resultado(s), porem sem publicacao oficial (DOU/ANVISA/CMED). PNCP nao constitui prova legal.',
                    'janela_aberta': False,
                    'total_resultados': total,
                }
            else:
                return {
                    'tipo': 'janela_aberta',
                    'item': f'Desabastecimento: {medicamento}',
                    'status': 'alerta',
                    'detalhe': 'Nenhum resultado encontrado. Verifique a grafia ou tente sinonimos.',
                    'janela_aberta': False,
                    'total_resultados': 0,
                }
        except Exception as e:
            logger.error(f"Erro janela aberta {medicamento}: {e}")
            return {
                'tipo': 'janela_aberta',
                'item': f'Desabastecimento: {medicamento}',
                'status': 'alerta',
                'detalhe': f'Erro: {str(e)[:100]}',
                'janela_aberta': False,
                'total_resultados': 0,
            }

    async def _check_publicacao_oficial(self, medicamento: str) -> Dict:
        try:
            alertas = await self.db.anvisa_alertas.find(
                {'$or': [
                    {'medicamento': {'$regex': medicamento, '$options': 'i'}},
                    {'medicamento_detectado': {'$regex': medicamento, '$options': 'i'}},
                    {'principio_ativo': {'$regex': medicamento, '$options': 'i'}},
                ]},
                {'_id': 0}
            ).to_list(length=10)

            if alertas:
                alerta_janela = [a for a in alertas if a.get('janela_importacao')]
                if alerta_janela:
                    return {
                        'tipo': 'publicacao_oficial',
                        'item': f'Publicacao ANVISA/DOU: {medicamento}',
                        'status': 'ok',
                        'detalhe': f'{len(alerta_janela)} alerta(s) com Janela de Importacao.',
                        'total_alertas': len(alertas),
                    }
                return {
                    'tipo': 'publicacao_oficial',
                    'item': f'Publicacao ANVISA/DOU: {medicamento}',
                    'status': 'alerta',
                    'detalhe': f'{len(alertas)} alerta(s), porem nenhum com janela de importacao.',
                    'total_alertas': len(alertas),
                }
            return {
                'tipo': 'publicacao_oficial',
                'item': f'Publicacao ANVISA/DOU: {medicamento}',
                'status': 'alerta',
                'detalhe': 'Nenhum alerta na base. Atualize na aba JANELA ANVISA.',
                'total_alertas': 0,
            }
        except Exception as e:
            return {
                'tipo': 'publicacao_oficial',
                'item': f'Publicacao ANVISA/DOU: {medicamento}',
                'status': 'alerta',
                'detalhe': f'Erro: {str(e)[:100]}',
                'total_alertas': 0,
            }

    async def _check_lmr(self, medicamento: str) -> Dict:
        """Verifica classificacao LMR (IN 428/2026)"""
        from services.lmr_service import get_lmr_service
        try:
            lmr_svc = get_lmr_service(self.db)
            analise = await lmr_svc.analisar_medicamento(medicamento)
            classif = analise.get('classificacao_lmr', {})
            categoria = classif.get('categoria', 'lista_negativa')
            score = analise.get('oportunidade_score', 0)

            if categoria in ('excepcional', 'judicial'):
                return {
                    'tipo': 'lmr_in428',
                    'item': f'LMR IN 428/2026: {medicamento}',
                    'status': 'ok',
                    'detalhe': f'Categoria: {categoria.upper()}. {classif.get("beneficio_tributario", "")}. Score oportunidade: {score}%.',
                    'categoria_lmr': categoria,
                    'oportunidade_score': score,
                }
            elif categoria == 'lista_positiva':
                return {
                    'tipo': 'lmr_in428',
                    'item': f'LMR IN 428/2026: {medicamento}',
                    'status': 'ok',
                    'detalhe': f'Lista Positiva. {classif.get("beneficio_tributario", "")}.',
                    'categoria_lmr': categoria,
                    'oportunidade_score': score,
                }
            else:
                return {
                    'tipo': 'lmr_in428',
                    'item': f'LMR IN 428/2026: {medicamento}',
                    'status': 'alerta',
                    'detalhe': f'Lista Negativa - sem beneficio tributario especial. Verificar viabilidade comercial.',
                    'categoria_lmr': categoria,
                    'oportunidade_score': score,
                }
        except Exception as e:
            logger.error(f"Erro LMR {medicamento}: {e}")
            return {
                'tipo': 'lmr_in428',
                'item': f'LMR IN 428/2026: {medicamento}',
                'status': 'alerta',
                'detalhe': f'Erro na analise LMR: {str(e)[:100]}',
                'categoria_lmr': 'erro',
                'oportunidade_score': 0,
            }


_checklist_service = None

def get_checklist_service(db) -> DamaChecklistService:
    global _checklist_service
    if _checklist_service is None:
        _checklist_service = DamaChecklistService(db)
    return _checklist_service
