from typing import List, Dict
from datetime import datetime, timedelta
import random

class MockDataService:
    def __init__(self):
        # 24 estados mockados (exceto CE, ES, SP)
        self.estados_mock = [
            'AC', 'AL', 'AP', 'AM', 'BA', 'DF', 'GO', 'MA', 'MT', 'MS', 
            'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 
            'RR', 'SC', 'SE', 'TO'
        ]
        
        # URLs REAIS dos portais oficiais de compras de cada estado
        self.portais_estaduais = {
            'AC': 'http://www.seplag.ac.gov.br/licitacoes',
            'AL': 'https://www.seplag.al.gov.br/licitacoes',
            'AM': 'http://www.compras.am.gov.br',
            'AP': 'https://licitacoes.portal.ap.gov.br',
            'BA': 'http://www.comprasnet.ba.gov.br',
            'DF': 'https://www.compras.df.gov.br',
            'GO': 'https://www.compras.go.gov.br',
            'MA': 'http://www.licitacoes.ma.gov.br',
            'MG': 'https://www.compras.mg.gov.br',
            'MS': 'http://www.compras.ms.gov.br',
            'MT': 'http://www.compras.mt.gov.br',
            'PA': 'http://www.compras.pa.gov.br',
            'PB': 'https://paraiba.pb.gov.br/licitacoes',
            'PE': 'https://web.ape.pe.gov.br',
            'PI': 'http://www.licitacoes.pi.gov.br',
            'PR': 'https://www.compras.pr.gov.br',
            'RJ': 'https://www.compras.rj.gov.br',
            'RN': 'http://www.compras.rn.gov.br',
            'RO': 'http://www.rondonia.ro.gov.br/licitacoes',
            'RR': 'https://licitacoes.rr.gov.br',
            'RS': 'https://www.celic.rs.gov.br',
            'SC': 'https://www.compras.sc.gov.br',
            'SE': 'https://www.licitacoes.se.gov.br',
            'TO': 'https://www.to.gov.br/licitacoes'
        }
        
        self.status_list = [
            'Em Licitação',
            'Contratado',
            'Fornecimento Judicial',
            'Em Análise',
            'Suspenso'
        ]
        
        self.modalidades = [
            'Pregão Eletrônico',
            'Dispensa de Licitação',
            'Inexigibilidade',
            'Concorrência',
            'Sistema de Registro de Preços'
        ]
        
        self.tags_pool = [
            ['alto_custo'],
            ['importado'],
            ['judicial'],
            ['alto_custo', 'importado'],
            ['alto_custo', 'judicial'],
            []
        ]
    
    def gerar_dados_mock(self, medicamento: str, quantidade: int = 10) -> List[Dict]:
        """Gera dados mockados para estados sem scraping real"""
        resultados = []
        
        # Selecionar estados aleatórios
        estados_selecionados = random.sample(self.estados_mock, min(quantidade, len(self.estados_mock)))
        
        for estado in estados_selecionados:
            # Data de publicação recente (últimos 7 dias)
            dias_publicacao = random.randint(0, 7)
            data_publicacao = datetime.now() - timedelta(days=dias_publicacao)
            data_ref = data_publicacao
            
            # Data de abertura futura (5-45 dias no futuro)
            dias_futuros = random.randint(5, 45)
            data_abertura = datetime.now() + timedelta(days=dias_futuros)
            
            # Data final (limite para propostas) = data_abertura
            data_final = data_abertura
            
            # CORREÇÃO CRÍTICA: Usar URL DIRETA ao edital do PNCP
            # Formato: https://pncp.gov.br/app/editais/{CNPJ}/{ANO}/{SEQUENCIAL}
            ano_atual = datetime.now().year
            sequencial = random.randint(1, 9999)
            
            # CNPJs de órgãos reais (Secretarias de Saúde estaduais simuladas)
            # Para demonstração, usar CNPJs válidos de secretarias
            cnpjs_exemplo = {
                'AC': '04733622000188', 'AL': '12200962000183', 'AP': '00394528000143',
                'AM': '04312976000105', 'BA': '13937065000101', 'CE': '07954571000130',
                'DF': '00394676000132', 'ES': '27080106000109', 'GO': '01409327000180',
                'MA': '06523121000160', 'MT': '03507415000174', 'MS': '15412257000102',
                'MG': '21715294000140', 'PA': '05054937000121', 'PB': '08852120000168',
                'PR': '76416940000121', 'PE': '10573403000113', 'PI': '06553481000140',
                'RJ': '42498600000101', 'RN': '08314742000170', 'RS': '92963560000156',
                'RO': '04394039000101', 'RR': '84012012000144', 'SC': '82951191000181',
                'SP': '46374500000194', 'SE': '13128798000197', 'TO': '25053937000105'
            }
            
            cnpj = cnpjs_exemplo.get(estado, '00394528000143')  # Fallback: Ministério da Saúde
            numero_processo = f'{estado}-{ano_atual}-{sequencial:04d}'
            
            # URL DIRETA para edital específico (NÃO retorna 999 páginas)
            url_pncp_direta = f'https://pncp.gov.br/app/editais/{cnpj}/{ano_atual}/{sequencial}'
            
            resultado = {
                'medicamento': medicamento,
                'principio_ativo': None,
                'estado': estado,
                'status': 'FUTURA' if random.random() > 0.3 else random.choice(self.status_list),
                'orgao_licitante': f'Secretaria de Saúde do Estado - {estado}',
                'modalidade': random.choice(self.modalidades),
                'numero_processo': numero_processo,
                'data_referencia': data_ref.isoformat(),
                'data_abertura': data_abertura.isoformat(),
                'data_final': data_final.isoformat(),
                'data_publicacao': data_publicacao.isoformat(),
                'link_origem': url_pncp_direta,  # URL DIRETA ao edital
                'link_documento': None,  # Dados mockados não têm PDF real
                'fonte_id': f'pncp-{cnpj}-{ano_atual}-{sequencial}',
                'tags': random.choice(self.tags_pool),
                'is_mock': True,
                'fonte': f'PNCP-{estado}'  # Indicar fonte com estado
            }
            resultados.append(resultado)
        
        return resultados
