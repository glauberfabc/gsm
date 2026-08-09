import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import services.comprasgov_service as comprasgov_service_module
from services.comprasgov_service import ComprasGovService


class TestBuscarContratacoesPorObjeto:
    def test_chama_a_api_uma_vez_por_modalidade_relevante(self, monkeypatch):
        """A API do Compras.gov.br exige codigoModalidade (obrigatorio) -
        sem ele, toda chamada retorna 404 e a fonte comprasgov nunca
        contribui nenhum resultado. Esse teste garante que uma modalidade
        e sempre enviada, uma vez por modalidade relevante."""
        chamadas = []

        async def fake_consultar_contratacoes_pncp(**kwargs):
            chamadas.append(kwargs)
            return {'resultado': [], 'tempo_segundos': 0.1}

        monkeypatch.setattr(
            comprasgov_service_module.cgov,
            'consultar_contratacoes_pncp',
            fake_consultar_contratacoes_pncp,
        )

        svc = ComprasGovService()
        asyncio.run(svc.buscar_contratacoes_por_objeto(termo='insulina'))

        assert len(chamadas) >= 2, "deveria fazer pelo menos uma chamada por modalidade relevante"
        for kwargs in chamadas:
            assert kwargs.get('modalidade') is not None, (
                f"chamada sem 'modalidade' definido vai retornar 404 na API real: {kwargs}"
            )

    def test_agrega_resultados_de_todas_as_modalidades_e_filtra_pelo_termo(self, monkeypatch):
        async def fake_consultar_contratacoes_pncp(**kwargs):
            modalidade = kwargs.get('modalidade')
            if modalidade == 6:
                return {'resultado': [
                    {'objetoCompra': 'AQUISICAO DE INSULINA NPH', 'orgaoEntidadeCnpj': '1'},
                    {'objetoCompra': 'AQUISICAO DE SERINGAS', 'orgaoEntidadeCnpj': '1'},
                ]}
            if modalidade == 8:
                return {'resultado': [
                    {'objetoCompra': 'DISPENSA PARA COMPRA DE INSULINA REGULAR', 'orgaoEntidadeCnpj': '2'},
                ]}
            return {'resultado': []}

        monkeypatch.setattr(
            comprasgov_service_module.cgov,
            'consultar_contratacoes_pncp',
            fake_consultar_contratacoes_pncp,
        )

        svc = ComprasGovService()
        resultado = asyncio.run(svc.buscar_contratacoes_por_objeto(termo='insulina'))

        objetos = [c['objeto'] for c in resultado['com_termo']]
        assert 'AQUISICAO DE INSULINA NPH' in objetos
        assert 'DISPENSA PARA COMPRA DE INSULINA REGULAR' in objetos
        assert 'AQUISICAO DE SERINGAS' not in objetos
        assert resultado['total'] == len(resultado['com_termo'])

    def test_sem_resultado_em_nenhuma_modalidade_retorna_lista_vazia_sem_erro(self, monkeypatch):
        async def fake_consultar_contratacoes_pncp(**kwargs):
            return {'resultado': []}

        monkeypatch.setattr(
            comprasgov_service_module.cgov,
            'consultar_contratacoes_pncp',
            fake_consultar_contratacoes_pncp,
        )

        svc = ComprasGovService()
        resultado = asyncio.run(svc.buscar_contratacoes_por_objeto(termo='item inexistente'))

        assert resultado['com_termo'] == []
        assert resultado['total'] == 0
