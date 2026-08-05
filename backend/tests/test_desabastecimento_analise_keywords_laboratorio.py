import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.desabastecimento_service import DesabastecimentoService

# _analise_keywords nao usa self.db, mas __init__ faz db[COLLECTION], entao
# db=None quebraria na construcao (TypeError: 'NoneType' object is not
# subscriptable). Um MagicMock() e subscritavel e nunca e efetivamente usado
# pelo metodo sob teste.
svc = DesabastecimentoService(db=MagicMock())


class TestAnaliseKeywordsLaboratorio:
    def test_transferencia_titularidade_classifica_como_laboratorio(self):
        alertas = [{
            'titulo': 'ANVISA aprova transferência de titularidade do medicamento X',
            'descricao': '',
            'link': 'https://in.gov.br/materia/1',
        }]

        resultado = svc._analise_keywords(alertas)

        assert resultado[0]['tipo_alerta'] == 'laboratorio'

    def test_atualizacao_de_bula_classifica_como_laboratorio(self):
        alertas = [{
            'titulo': 'Laboratório Y comunica atualização de bula',
            'descricao': '',
            'link': 'https://in.gov.br/materia/2',
        }]

        resultado = svc._analise_keywords(alertas)

        assert resultado[0]['tipo_alerta'] == 'laboratorio'

    def test_desabastecimento_continua_tendo_prioridade_sobre_laboratorio(self):
        # Um texto que mistura os dois - desabastecimento tem prioridade
        # porque e checado antes na cadeia if/elif.
        alertas = [{
            'titulo': 'Desabastecimento de medicamento X após transferência de titularidade',
            'descricao': '',
            'link': 'https://in.gov.br/materia/3',
        }]

        resultado = svc._analise_keywords(alertas)

        assert resultado[0]['tipo_alerta'] == 'desabastecimento'
