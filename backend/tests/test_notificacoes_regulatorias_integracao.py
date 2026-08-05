"""
Regressao de integracao para o feed regulatorio do sino
(GET /api/notificacoes/regulatorias). Bate no endpoint real, seguindo o
mesmo padrao dos demais testes de integracao deste diretorio.
"""
import os
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestNotificacoesRegulatorias:
    def test_endpoint_retorna_estrutura_esperada(self):
        response = requests.get(f"{BASE_URL}/api/notificacoes/regulatorias?limite=15")
        assert response.status_code == 200

        data = response.json()
        assert "alertas" in data
        assert "total" in data
        assert "nao_lidas" in data

        for item in data["alertas"]:
            for campo in ("id", "categoria", "titulo", "descricao", "medicamento",
                          "url_fonte_oficial", "data_evento", "lida", "criado_em"):
                assert campo in item, f"Notificacao sem campo {campo}"
            assert item["categoria"] in (
                "desabastecimento", "cancelamento_suspensao", "novo_registro", "laboratorio"
            ), f"Categoria fora do esperado: {item['categoria']}"
        print(f"✅ /notificacoes/regulatorias: {data['total']} notificacao(oes), estrutura ok")
