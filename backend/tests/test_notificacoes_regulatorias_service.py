import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.notificacoes_regulatorias_service import (
    criar_a_partir_de_alertas_anvisa,
    criar_a_partir_de_novos_registros,
)


class _FakeCollection:
    def __init__(self):
        self.docs = []

    async def find_one(self, query):
        chave = query.get('chave_dedup')
        for d in self.docs:
            if d['chave_dedup'] == chave:
                return d
        return None

    async def insert_one(self, doc):
        self.docs.append(doc)


class _FakeDb:
    def __init__(self):
        self.notificacoes_regulatorias = _FakeCollection()


class TestCriarAPartirDeAlertasAnvisa:
    def test_mapeia_tipo_alerta_para_categoria_do_sino(self):
        db = _FakeDb()
        alertas = [
            {'tipo_alerta': 'desabastecimento', 'titulo': 'Falta de X', 'link': 'https://a.gov.br/1'},
            {'tipo_alerta': 'interrupção fabricação', 'titulo': 'Interrupção Y', 'link': 'https://a.gov.br/2'},
            {'tipo_alerta': 'descontinuação', 'titulo': 'Cancelamento Z', 'link': 'https://a.gov.br/3'},
            {'tipo_alerta': 'recolhimento', 'titulo': 'Recall W', 'link': 'https://a.gov.br/4'},
            {'tipo_alerta': 'proibição', 'titulo': 'Interdição V', 'link': 'https://a.gov.br/5'},
            {'tipo_alerta': 'laboratorio', 'titulo': 'Titularidade U', 'link': 'https://a.gov.br/6'},
        ]

        criadas = asyncio.run(criar_a_partir_de_alertas_anvisa(db, alertas))

        assert criadas == 6
        categorias = {d['titulo']: d['categoria'] for d in db.notificacoes_regulatorias.docs}
        assert categorias['Falta de X'] == 'desabastecimento'
        assert categorias['Interrupção Y'] == 'desabastecimento'
        assert categorias['Cancelamento Z'] == 'cancelamento_suspensao'
        assert categorias['Recall W'] == 'cancelamento_suspensao'
        assert categorias['Interdição V'] == 'cancelamento_suspensao'
        assert categorias['Titularidade U'] == 'laboratorio'

    def test_tipos_fora_de_escopo_nao_geram_notificacao(self):
        db = _FakeDb()
        alertas = [
            {'tipo_alerta': 'importação excepcional', 'titulo': 'A', 'link': 'https://a.gov.br/1'},
            {'tipo_alerta': 'decisão judicial', 'titulo': 'B', 'link': 'https://a.gov.br/2'},
            {'tipo_alerta': 'regulamentação', 'titulo': 'C', 'link': 'https://a.gov.br/3'},
            {'tipo_alerta': 'informativo', 'titulo': 'D', 'link': 'https://a.gov.br/4'},
        ]

        criadas = asyncio.run(criar_a_partir_de_alertas_anvisa(db, alertas))

        assert criadas == 0
        assert db.notificacoes_regulatorias.docs == []

    def test_dedup_por_link_nao_cria_duplicata(self):
        db = _FakeDb()
        alerta = {'tipo_alerta': 'desabastecimento', 'titulo': 'Falta de X', 'link': 'https://a.gov.br/1'}

        primeira = asyncio.run(criar_a_partir_de_alertas_anvisa(db, [alerta]))
        segunda = asyncio.run(criar_a_partir_de_alertas_anvisa(db, [alerta]))

        assert primeira == 1
        assert segunda == 0
        assert len(db.notificacoes_regulatorias.docs) == 1

    def test_campos_do_documento_criado(self):
        db = _FakeDb()
        alerta = {
            'tipo_alerta': 'desabastecimento',
            'titulo': 'Falta de Insulina',
            'descricao': 'Descrição completa',
            'link': 'https://in.gov.br/materia/123',
            'medicamento_detectado': 'Insulina Glargina',
            'data_publicacao': '2026-08-01',
        }

        asyncio.run(criar_a_partir_de_alertas_anvisa(db, [alerta]))

        doc = db.notificacoes_regulatorias.docs[0]
        assert doc['categoria'] == 'desabastecimento'
        assert doc['titulo'] == 'Falta de Insulina'
        assert doc['descricao'] == 'Descrição completa'
        assert doc['medicamento'] == 'Insulina Glargina'
        assert doc['url_fonte_oficial'] == 'https://in.gov.br/materia/123'
        assert doc['data_evento'] == '2026-08-01'
        assert doc['lida'] is False
        assert 'id' in doc
        assert 'criado_em' in doc


class TestCriarAPartirDeNovosRegistros:
    def test_cria_notificacao_para_cada_registro_novo(self):
        db = _FakeDb()
        novos = [
            {'numero_registro_produto': '123456', 'nome_produto': 'Nucala', 'empresa_detentora_registro': 'GSK',
             'data_finalizacao_processo': '2026-08-01'},
        ]

        criadas = asyncio.run(criar_a_partir_de_novos_registros(db, novos))

        assert criadas == 1
        doc = db.notificacoes_regulatorias.docs[0]
        assert doc['categoria'] == 'novo_registro'
        assert 'Nucala' in doc['titulo']
        assert doc['medicamento'] == 'Nucala'
        assert doc['url_fonte_oficial'] == ''
        assert doc['chave_dedup'] == '123456'

    def test_dedup_por_numero_registro_produto(self):
        db = _FakeDb()
        registro = {'numero_registro_produto': '123456', 'nome_produto': 'Nucala',
                     'empresa_detentora_registro': 'GSK', 'data_finalizacao_processo': '2026-08-01'}

        primeira = asyncio.run(criar_a_partir_de_novos_registros(db, [registro]))
        segunda = asyncio.run(criar_a_partir_de_novos_registros(db, [registro]))

        assert primeira == 1
        assert segunda == 0

    def test_ignora_registro_sem_numero(self):
        db = _FakeDb()
        registro = {'nome_produto': 'Sem numero', 'empresa_detentora_registro': 'X'}

        criadas = asyncio.run(criar_a_partir_de_novos_registros(db, [registro]))

        assert criadas == 0
