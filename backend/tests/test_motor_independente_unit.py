import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.motor_independente import MotorBuscaIndependente


class TestEscolherDocumentoEdital:
    def test_prefere_documento_marcado_como_edital(self):
        arquivos = [
            {'seq': 1, 'titulo': 'Aviso.pdf', 'tipo': 'Aviso de Contratação'},
            {'seq': 2, 'titulo': 'Edital.pdf', 'tipo': 'Edital'},
            {'seq': 3, 'titulo': 'Anexo_I.pdf', 'tipo': 'Outros Documentos'},
        ]
        assert MotorBuscaIndependente.escolher_documento_edital(arquivos) == 2

    def test_case_insensitive_no_tipo(self):
        arquivos = [
            {'seq': 5, 'titulo': 'edital.pdf', 'tipo': 'EDITAL'},
        ]
        assert MotorBuscaIndependente.escolher_documento_edital(arquivos) == 5

    def test_sem_documento_marcado_usa_o_primeiro_da_lista(self):
        arquivos = [
            {'seq': 7, 'titulo': 'Termo_Referencia.pdf', 'tipo': 'Outros Documentos'},
            {'seq': 8, 'titulo': 'Planilha.xlsx', 'tipo': 'Outros Documentos'},
        ]
        assert MotorBuscaIndependente.escolher_documento_edital(arquivos) == 7

    def test_lista_vazia_cai_no_sequencial_1(self):
        assert MotorBuscaIndependente.escolher_documento_edital([]) == 1

    def test_tipo_ausente_nao_quebra(self):
        arquivos = [{'seq': 3, 'titulo': 'Sem_tipo.pdf'}]
        assert MotorBuscaIndependente.escolher_documento_edital(arquivos) == 3
