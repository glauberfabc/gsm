import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.anvisa_scraper import AnvisaScraper

scraper = AnvisaScraper()


class TestFiltrarRelevantesLaboratorio:
    def test_item_com_transferencia_titularidade_passa_no_filtro(self):
        # Titulo deliberadamente SEM nenhuma palavra de KW_SAUDE (ex: "medicamento",
        # "farmácia") para provar que e o KW_LABORATORIO novo que faz o item passar,
        # nao uma coincidencia com uma keyword ja existente.
        items = [{
            'titulo': 'ANVISA publica resolução sobre transferência de titularidade de registro sanitário',
            'descricao': '',
            'link': 'https://in.gov.br/materia/1',
        }]

        resultado = scraper._filtrar_relevantes(items)

        assert len(resultado) == 1

    def test_item_sem_nenhum_gatilho_nao_passa(self):
        items = [{
            'titulo': 'Notícia qualquer sem relação com o setor',
            'descricao': 'Texto genérico sem nenhuma palavra-chave relevante',
            'link': 'https://in.gov.br/materia/2',
        }]

        resultado = scraper._filtrar_relevantes(items)

        assert len(resultado) == 0

    def test_item_com_atualizacao_de_bula_passa(self):
        # Idem: sem "medicamento"/"farmácia"/etc., so o novo gatilho de bula.
        items = [{
            'titulo': 'Laboratório Beta comunica atualização de bula do produto',
            'descricao': '',
            'link': 'https://in.gov.br/materia/3',
        }]

        resultado = scraper._filtrar_relevantes(items)

        assert len(resultado) == 1
