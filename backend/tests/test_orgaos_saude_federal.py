import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.orgaos_saude_federal import bate_orgao_saude, ORGAOS_SAUDE_FEDERAL


class TestBateOrgaoSaude:
    def test_cnpj_exato_do_ministerio_bate(self):
        assert bate_orgao_saude('QUALQUER NOME', '00394544000185') is True

    def test_cnpj_fora_da_lista_nao_bate_sem_keyword(self):
        assert bate_orgao_saude('MUNICIPIO DE GOIANESIA', '01065846000172') is False

    def test_keyword_ministerio_da_saude_bate_por_nome(self):
        assert bate_orgao_saude('MINISTERIO DA SAUDE', None) is True

    def test_keyword_dlog_bate_por_nome(self):
        assert bate_orgao_saude('DEPARTAMENTO DE LOGISTICA EM SAUDE', '') is True

    def test_keyword_ignora_acentuacao_e_caixa(self):
        assert bate_orgao_saude('Instituto Nacional de Câncer', None) is True

    def test_nome_sem_relacao_nao_bate(self):
        assert bate_orgao_saude('SECRETARIA DE AGRICULTURA E ABASTECIMENTO', '46384400000149') is False

    def test_cnpj_none_e_nome_none_nao_bate(self):
        assert bate_orgao_saude(None, None) is False

    def test_lista_tem_pelo_menos_ministerio_da_saude(self):
        nomes = [o['nome'] for o in ORGAOS_SAUDE_FEDERAL]
        assert any('Ministério da Saúde' in n or 'Ministerio da Saude' in n for n in nomes)
