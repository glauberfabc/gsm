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


from services.medicamento_query_parser import contem_concentracao


class TestContemConcentracao:
    def test_tolera_variacao_de_espaco(self):
        assert contem_concentracao("Frasco 100mg/ml pronto uso", "100 MG/ML") is True

    def test_tolera_espaco_ao_redor_da_barra(self):
        assert contem_concentracao("Frasco 100 MG / ML pronto uso", "100 MG/ML") is True

    def test_nao_bate_com_dose_diferente(self):
        assert contem_concentracao("Frasco 50 MG/ML", "100 MG/ML") is False


from services.medicamento_query_parser import parse_query


class TestParseQuery:
    def test_extrai_principio_ativo_concentracao_e_forma(self):
        q = parse_query("MEPOLIZUMABE 100 MG/ML CANETA APLICADORA")
        assert q["principio_ativo"] == "MEPOLIZUMABE"
        assert q["concentracao"] == "100 MG/ML"
        assert q["forma_farmaceutica"] == "CANETA APLICADORA"

    def test_extrai_concentracao_sem_forma(self):
        q = parse_query("MEPOLIZUMABE 100 MG/ML")
        assert q["principio_ativo"] == "MEPOLIZUMABE"
        assert q["concentracao"] == "100 MG/ML"
        assert q["forma_farmaceutica"] is None

    def test_busca_so_com_nome_mantem_termo_inteiro(self):
        q = parse_query("Mepolizumabe")
        assert q["principio_ativo"] == "Mepolizumabe"
        assert q["concentracao"] is None
        assert q["forma_farmaceutica"] is None

    def test_concentracao_simples_mg(self):
        q = parse_query("Somatropina 4mg")
        assert q["principio_ativo"] == "Somatropina"
        assert q["concentracao"] == "4mg"

    def test_forma_farmaceutica_com_acento_no_termo_original(self):
        q = parse_query("Ocitocina 5 UI Pó Liofilizado")
        assert q["principio_ativo"] == "Ocitocina"
        assert q["forma_farmaceutica"] == "Pó Liofilizado"

    def test_termo_original_preservado(self):
        q = parse_query("  Mepolizumabe 100 MG/ML  ")
        assert q["termo_original"] == "Mepolizumabe 100 MG/ML"

    def test_concentracao_nao_vaza_para_forma_farmaceutica_adjacente(self):
        q = parse_query("Aciclovir 5G/GEL")
        assert q["concentracao"] == "5G"
        assert q["forma_farmaceutica"] == "GEL"
        assert q["principio_ativo"] == "Aciclovir"

    def test_string_vazia_nao_quebra(self):
        q = parse_query("")
        assert q["principio_ativo"] == ""
        assert q["concentracao"] is None
        assert q["forma_farmaceutica"] is None


from services.medicamento_query_parser import dividir_termo, parse_termo_completo


class TestDividirTermo:
    def test_sem_barra_retorna_termo_unico(self):
        assert dividir_termo("Mepolizumabe") == ["Mepolizumabe"]

    def test_com_barra_divide_em_partes(self):
        partes = dividir_termo("Synvisc Classic 2ml / Hilano G-F 20")
        assert partes == ["Synvisc Classic 2ml", "Hilano G-F 20"]

    def test_barra_com_espacos_extras(self):
        assert dividir_termo("A /  B  / C") == ["A", "B", "C"]

    def test_barra_grudada_de_concentracao_nao_divide(self):
        # "100 MG/ML" tem barra sem espaço nos dois lados - é notação de
        # concentração, não separador de nome composto. Se dividisse aqui,
        # "ML" viraria uma segunda busca "fantasma" que bate em qualquer
        # texto contendo a palavra "ml" (comuníssima em texto farmacêutico),
        # o oposto do que este plano existe para resolver.
        assert dividir_termo("Mepolizumabe 100 MG/ML") == ["Mepolizumabe 100 MG/ML"]

    def test_barra_com_espaco_de_um_lado_apenas(self):
        assert dividir_termo("Synvisc Classic 2ml/ Hilano G-F 20") == ["Synvisc Classic 2ml", "Hilano G-F 20"]
        assert dividir_termo("Synvisc Classic 2ml /Hilano G-F 20") == ["Synvisc Classic 2ml", "Hilano G-F 20"]


class TestParseTermoCompleto:
    def test_termo_simples_gera_uma_query(self):
        queries = parse_termo_completo("Mepolizumabe 100 MG/ML")
        assert len(queries) == 1
        assert queries[0]["principio_ativo"] == "Mepolizumabe"

    def test_nome_composto_gera_duas_queries(self):
        queries = parse_termo_completo("Synvisc Classic 2ml / Hilano G-F 20")
        assert len(queries) == 2
        assert queries[0]["principio_ativo"] == "Synvisc Classic"
        assert queries[0]["concentracao"] == "2ml"
        assert queries[1]["principio_ativo"] == "Hilano G-F 20"
        assert queries[1]["concentracao"] is None


from services.medicamento_query_parser import resultado_relevante


class TestResultadoRelevante:
    def test_retorna_a_query_que_bateu(self):
        queries = parse_termo_completo("Synvisc Classic 2ml / Hilano G-F 20")
        match = resultado_relevante("Edital de Hilano G-F 20 para joelho", queries)
        assert match is not None
        assert match["principio_ativo"] == "Hilano G-F 20"

    def test_retorna_none_quando_nenhuma_parte_bate(self):
        queries = parse_termo_completo("Mepolizumabe 100 MG/ML")
        assert resultado_relevante("Edital de Omalizumabe 75mg", queries) is None

    def test_retorna_primeira_query_que_bater(self):
        queries = parse_termo_completo("Mepolizumabe 100 MG/ML")
        match = resultado_relevante("Bula de Mepolizumabe injetável", queries)
        assert match is not None
        assert match["principio_ativo"] == "Mepolizumabe"
