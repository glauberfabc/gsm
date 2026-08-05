import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.medicamento_query_parser import normalizar, contem_termo_estrito


class TestNormalizar:
    def test_remove_acentos_e_minusculas(self):
        assert normalizar("Pó Liofilizado") == "po liofilizado"

    def test_colapsa_espacos(self):
        assert normalizar("  Mepolizumabe   100  ") == "mepolizumabe 100"

    def test_string_vazia(self):
        assert normalizar("") == ""


class TestContemTermoEstrito:
    def test_nao_confunde_aciclovir_com_valaciclovir(self):
        assert contem_termo_estrito("Bula de Valaciclovir 500mg", "Aciclovir") is False

    def test_aciclovir_bate_em_texto_com_aciclovir(self):
        assert contem_termo_estrito("Edital de Aciclovir comprimido", "Aciclovir") is True

    def test_exige_todas_as_palavras_do_termo_composto(self):
        assert contem_termo_estrito("Licitação de Ácido Fólico", "Acido Valproico") is False
        assert contem_termo_estrito("Licitação de Ácido Valproico 250mg", "Acido Valproico") is True

    def test_ignora_acentuacao_e_caixa(self):
        assert contem_termo_estrito("MEPOLIZUMABE injetável", "mepolizumabe") is True

    def test_ignora_palavras_curtas_do_termo(self):
        # "de" tem 2 letras e não entra na exigência de match
        assert contem_termo_estrito("Edital de Aciclovir", "Aciclovir de") is True
