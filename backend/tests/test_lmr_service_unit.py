import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.lmr_service import LmrService, FAIXAS_MARGEM_IN428

svc = LmrService(db=None)  # _calcular_tributacao nao usa self.db


class TestCalcularTributacaoCascata:
    def test_carga_tributaria_total_maior_que_soma_simples_das_aliquotas(self):
        faixa = FAIXAS_MARGEM_IN428['sintetico']
        trib = svc._calcular_tributacao('lista_negativa', faixa, preco_ref=1000)

        soma_simples = trib['imposto_importacao'] + trib['icms'] + trib['pis'] + trib['cofins']
        assert trib['carga_tributaria_total'] > soma_simples

    def test_lista_negativa_valores_esperados(self):
        faixa = FAIXAS_MARGEM_IN428['sintetico']
        trib = svc._calcular_tributacao('lista_negativa', faixa, preco_ref=1000)

        # aliquotas nominais inalteradas
        assert trib['imposto_importacao'] == 8.0
        assert trib['icms'] == 18.0
        assert trib['pis'] == 1.65
        assert trib['cofins'] == 7.6

        # cascata: II=80, PIS=16.5, COFINS=76
        # base ICMS "por dentro" = (1000+80+16.5+76) / (1-0.18) = 1429.878048780488
        # ICMS = 1429.878048780488 * 0.18 = 257.37804878048783
        # carga = (80+16.5+76+257.37804878048783) / 1000 * 100 = 42.98780487804878 -> round(2) = 42.99
        # custo = (1000+80+16.5+76) + 257.37804878048783 = 1429.8780487804878 -> round(2) = 1429.88
        assert trib['carga_tributaria_total'] == 42.99
        assert trib['custo_importacao_estimado'] == 1429.88

    def test_judicial_sem_ii_nem_icms_mas_com_pis_cofins(self):
        faixa = FAIXAS_MARGEM_IN428['sintetico']
        trib = svc._calcular_tributacao('judicial', faixa, preco_ref=1000)

        assert trib['imposto_importacao'] == 0.0
        assert trib['icms'] == 0.0
        assert trib['custo_importacao_estimado'] == 1092.5  # CIF + PIS(16.5) + COFINS(76)

    def test_sem_preco_referencia_nao_calcula_custo(self):
        faixa = FAIXAS_MARGEM_IN428['sintetico']
        trib = svc._calcular_tributacao('lista_negativa', faixa, preco_ref=0)

        assert trib['custo_importacao_estimado'] is None

    def test_margem_distribuidora_e_farmacia_inalteradas(self):
        faixa = FAIXAS_MARGEM_IN428['biologico']
        trib = svc._calcular_tributacao('lista_positiva', faixa, preco_ref=1000)

        assert trib['margem_distribuidora'] == 21.0
        assert trib['margem_farmacia'] == 33.5
