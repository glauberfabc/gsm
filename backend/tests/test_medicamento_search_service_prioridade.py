import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.medicamento_search_service import MedicamentoSearchService

svc = MedicamentoSearchService(db=None)  # _calcular_prioridade nao usa self.db
NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


class TestCalcularPrioridadePenalidadeConcentracao:
    def test_impacto_recente_com_concentracao_nao_confirmada_soma_penalidade(self):
        item_confirmada = {
            'classificacao_dama': 'impacto', '_parsed_date': NOW, 'tag_recente': False,
            '_obsoleto': False, 'concentracao_confirmada': True,
        }
        item_nao_confirmada = dict(item_confirmada, concentracao_confirmada=False)

        assert svc._calcular_prioridade(item_confirmada, NOW) == 1
        assert svc._calcular_prioridade(item_nao_confirmada, NOW) == 2

    def test_pncp_deserto_com_concentracao_nao_confirmada_soma_penalidade(self):
        item_confirmada = {
            'classificacao_dama': 'indicio', '_obsoleto': False, 'tag_recente': False,
            'indicador_mercado': True, 'situacao_licitacao': 'DESERTO/FRACASSADO',
            'concentracao_confirmada': True,
        }
        item_nao_confirmada = dict(item_confirmada, concentracao_confirmada=False)

        assert svc._calcular_prioridade(item_confirmada, NOW) == 1
        assert svc._calcular_prioridade(item_nao_confirmada, NOW) == 2

    def test_rotina_ignora_penalidade_mesmo_com_concentracao_nao_confirmada(self):
        item = {
            'classificacao_dama': 'rotina', '_obsoleto': False,
            'concentracao_confirmada': False,
        }
        assert svc._calcular_prioridade(item, NOW) == 5

    def test_obsoleto_ignora_penalidade_mesmo_com_concentracao_nao_confirmada(self):
        item = {
            'classificacao_dama': 'indicio', '_obsoleto': True,
            'concentracao_confirmada': False,
        }
        assert svc._calcular_prioridade(item, NOW) == 6

    def test_concentracao_confirmada_ausente_nao_penaliza(self):
        # item sem a chave 'concentracao_confirmada' (ex: fonte que nao a
        # define) nao deve ser penalizado - .get(...) retorna None, e
        # None is False == False.
        item = {
            'classificacao_dama': 'indicio', '_obsoleto': False, 'tag_recente': False,
        }
        assert svc._calcular_prioridade(item, NOW) == 4


class TestDedupResultados:
    def test_duplicata_mantem_versao_com_concentracao_confirmada(self):
        # mesmo titulo (ex.: mesma materia do DOU retornada por 2 buscas
        # distintas), uma com concentracao confirmada e outra sem - o
        # resultado confirmado deve prevalecer, independente da ordem.
        nao_confirmado = {'titulo': 'Portaria X - Mepolizumabe', 'concentracao_confirmada': False}
        confirmado = {'titulo': 'Portaria X - Mepolizumabe', 'concentracao_confirmada': True}

        deduped = MedicamentoSearchService._dedup_resultados([nao_confirmado, confirmado])
        assert len(deduped) == 1
        assert deduped[0]['concentracao_confirmada'] is True

    def test_duplicata_confirmada_primeiro_permanece_confirmada(self):
        confirmado = {'titulo': 'Portaria X - Mepolizumabe', 'concentracao_confirmada': True}
        nao_confirmado = {'titulo': 'Portaria X - Mepolizumabe', 'concentracao_confirmada': False}

        deduped = MedicamentoSearchService._dedup_resultados([confirmado, nao_confirmado])
        assert len(deduped) == 1
        assert deduped[0]['concentracao_confirmada'] is True

    def test_sem_duplicata_mantem_ambos(self):
        item_a = {'titulo': 'Portaria A', 'concentracao_confirmada': True}
        item_b = {'titulo': 'Portaria B', 'concentracao_confirmada': False}

        deduped = MedicamentoSearchService._dedup_resultados([item_a, item_b])
        assert len(deduped) == 2

    def test_titulo_vazio_e_descartado(self):
        deduped = MedicamentoSearchService._dedup_resultados([{'titulo': ''}, {'titulo': 'X'}])
        assert len(deduped) == 1
        assert deduped[0]['titulo'] == 'X'
