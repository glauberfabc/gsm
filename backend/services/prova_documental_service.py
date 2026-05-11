"""
Servico de Geracao de Prova Documental em PDF
Gera documento formal para apresentar em processos de licitacao.

Estrutura do PDF:
1. Cabecalho com dados da empresa
2. Data/hora da consulta
3. Conteudo da publicacao oficial (DOU/ANVISA/CMED)
4. Rodape com informacoes de autenticidade
"""

import io
import logging
from datetime import datetime
from typing import Dict, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Frame, PageTemplate
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT

logger = logging.getLogger(__name__)

MESES_PT = [
    'janeiro', 'fevereiro', 'marco', 'abril', 'maio', 'junho',
    'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'
]

# Cores corporativas
COR_PRIMARIA = colors.HexColor('#0F172A')
COR_ACCENT = colors.HexColor('#1E40AF')
COR_CINZA = colors.HexColor('#64748B')
COR_BG_CLARO = colors.HexColor('#F8FAFC')
COR_BORDA = colors.HexColor('#CBD5E1')


def _data_extenso():
    hoje = datetime.now()
    return f"{hoje.day} de {MESES_PT[hoje.month - 1]} de {hoje.year}"


def _criar_estilos():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        'DocTitulo', parent=styles['Title'],
        fontName='Helvetica-Bold', fontSize=14, leading=18,
        textColor=COR_PRIMARIA, alignment=TA_CENTER,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        'DocSubtitulo', parent=styles['Normal'],
        fontName='Helvetica', fontSize=9, leading=12,
        textColor=COR_CINZA, alignment=TA_CENTER,
        spaceAfter=12,
    ))
    styles.add(ParagraphStyle(
        'SecaoTitulo', parent=styles['Heading2'],
        fontName='Helvetica-Bold', fontSize=11, leading=14,
        textColor=COR_ACCENT, spaceAfter=6, spaceBefore=12,
    ))
    styles.add(ParagraphStyle(
        'CorpoTexto', parent=styles['Normal'],
        fontName='Helvetica', fontSize=10, leading=14,
        textColor=COR_PRIMARIA, alignment=TA_JUSTIFY,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        'CorpoNegrito', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=10, leading=14,
        textColor=COR_PRIMARIA, spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        'EmpresaInfo', parent=styles['Normal'],
        fontName='Helvetica', fontSize=9, leading=12,
        textColor=COR_CINZA, alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        'Rodape', parent=styles['Normal'],
        fontName='Helvetica', fontSize=7, leading=9,
        textColor=COR_CINZA, alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        'Citacao', parent=styles['Normal'],
        fontName='Helvetica-Oblique', fontSize=9, leading=13,
        textColor=colors.HexColor('#374151'),
        leftIndent=20, rightIndent=20,
        spaceAfter=8, spaceBefore=4,
        borderColor=COR_BORDA, borderWidth=0,
        backColor=COR_BG_CLARO,
        borderPadding=8,
    ))
    return styles


def gerar_prova_documental_pdf(
    medicamento: str,
    fonte: str,
    titulo_documento: str,
    descricao: str,
    data_publicacao: str,
    link: str,
    tipo_alerta: str,
    risco: str,
    empresa: Optional[Dict] = None,
    classificacao_dama: Optional[str] = None,
    analise_lmr: Optional[Dict] = None,
) -> bytes:
    """Gera PDF de Prova Documental formatado profissionalmente."""

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2.2*cm, rightMargin=2.2*cm,
        topMargin=2*cm, bottomMargin=2.5*cm,
    )

    styles = _criar_estilos()
    story = []

    # ---- CABECALHO EMPRESA ----
    empresa_nome = (empresa or {}).get('name', 'GRUPO SMART MEDICAL')
    empresa_cnpj = (empresa or {}).get('cnpj', '')
    empresa_end = (empresa or {}).get('address', '')
    empresa_tel = (empresa or {}).get('phone', '')
    empresa_email = (empresa or {}).get('email', '')

    story.append(Paragraph(empresa_nome, styles['DocTitulo']))
    info_parts = []
    if empresa_cnpj:
        info_parts.append(f'CNPJ: {empresa_cnpj}')
    if empresa_end:
        info_parts.append(empresa_end)
    contacts = []
    if empresa_tel:
        contacts.append(f'Tel: {empresa_tel}')
    if empresa_email:
        contacts.append(empresa_email)
    if contacts:
        info_parts.append(' | '.join(contacts))
    if info_parts:
        story.append(Paragraph('<br/>'.join(info_parts), styles['EmpresaInfo']))

    story.append(Spacer(1, 6*mm))
    story.append(HRFlowable(width='100%', thickness=1.5, color=COR_ACCENT))
    story.append(Spacer(1, 8*mm))

    # ---- TITULO DO DOCUMENTO ----
    story.append(Paragraph('PROVA DOCUMENTAL', styles['DocTitulo']))
    story.append(Paragraph(
        f'Consulta realizada em {_data_extenso()} as {datetime.now().strftime("%H:%M:%S")} (horario de Brasilia)',
        styles['DocSubtitulo']
    ))
    story.append(Spacer(1, 4*mm))

    # ---- DADOS DA CONSULTA (tabela) ----
    dados_tabela = [
        ['Medicamento:', medicamento.upper()],
        ['Fonte Oficial:', fonte],
        ['Tipo de Alerta:', tipo_alerta or 'informativo'],
        ['Classificacao DAMA:', classificacao_dama or 'N/A'],
        ['Nivel de Risco:', risco or 'N/A'],
        ['Data da Publicacao:', data_publicacao or 'N/A'],
    ]
    if link:
        dados_tabela.append(['Link da Publicacao:', link[:90] + ('...' if len(link) > 90 else '')])

    t = Table(dados_tabela, colWidths=[4.5*cm, 12*cm])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (0, -1), COR_ACCENT),
        ('TEXTCOLOR', (1, 0), (1, -1), COR_PRIMARIA),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LINEBELOW', (0, 0), (-1, -2), 0.5, COR_BORDA),
        ('BACKGROUND', (0, 0), (-1, 0), COR_BG_CLARO),
    ]))
    story.append(t)
    story.append(Spacer(1, 6*mm))

    # ---- CONTEUDO DA PUBLICACAO ----
    story.append(Paragraph('1. DOCUMENTO OFICIAL', styles['SecaoTitulo']))
    story.append(Paragraph(
        f'<b>{titulo_documento}</b>',
        styles['CorpoNegrito']
    ))

    # Limpar HTML do descricao
    desc_limpa = (descricao or '').replace('<', '&lt;').replace('>', '&gt;')
    if desc_limpa:
        story.append(Spacer(1, 2*mm))
        story.append(Paragraph(desc_limpa, styles['Citacao']))

    story.append(Spacer(1, 4*mm))

    # ---- FUNDAMENTACAO LEGAL ----
    story.append(Paragraph('2. FUNDAMENTACAO LEGAL', styles['SecaoTitulo']))
    story.append(Paragraph(
        'O presente documento serve como prova documental de consulta oficial, '
        'fundamentada nos seguintes dispositivos legais:',
        styles['CorpoTexto']
    ))
    leis = [
        'Lei no 14.133/2021 (Nova Lei de Licitacoes), Art. 5o - principio da transparencia e publicidade;',
        'RDC no 488/2021-ANVISA - importacao excepcional de medicamentos em desabastecimento;',
        'Lei no 12.527/2011 (Lei de Acesso a Informacao) - direito de acesso a informacao publica;',
        'Art. 37, caput, CF/88 - principios da publicidade e eficiencia.',
    ]
    for lei in leis:
        story.append(Paragraph(f'&bull; {lei}', styles['CorpoTexto']))

    story.append(Spacer(1, 4*mm))

    # ---- ANALISE TRIBUTARIA LMR (IN 428/2026) ----
    if analise_lmr:
        classif = analise_lmr.get('classificacao_lmr', {})
        trib = analise_lmr.get('estrategia_tributaria', {})
        score_lmr = analise_lmr.get('oportunidade_score', 0)

        story.append(Paragraph('3. ANALISE TRIBUTARIA LMR (IN 428/2026)', styles['SecaoTitulo']))
        story.append(Paragraph(
            'Analise de viabilidade de importacao conforme Instrucao Normativa 428/2026 '
            '(Lista de Medicamentos de Referencia):',
            styles['CorpoTexto']
        ))

        lmr_dados = [
            ['Categoria LMR:', (classif.get('categoria', 'N/A') or 'N/A').upper()],
            ['Risco Comercial:', classif.get('risco_comercial', 'N/A')],
            ['Beneficio Tributario:', classif.get('beneficio_tributario', 'N/A')],
            ['Carga Tributaria Total:', f"{trib.get('carga_tributaria_total', 'N/A')}%"],
            ['II:', f"{trib.get('imposto_importacao', 'N/A')}%"],
            ['ICMS:', f"{trib.get('icms', 'N/A')}%"],
            ['PIS/COFINS:', f"{trib.get('pis', 0)}% + {trib.get('cofins', 0)}%"],
            ['Margem Distribuidora:', f"{trib.get('margem_distribuidora', 'N/A')}%"],
            ['Score de Oportunidade:', f"{score_lmr}%"],
        ]
        if trib.get('custo_importacao_estimado'):
            lmr_dados.append(['Custo Importacao Est.:', f"R$ {trib['custo_importacao_estimado']:,.2f}"])

        t_lmr = Table(lmr_dados, colWidths=[5*cm, 11.5*cm])
        t_lmr.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TEXTCOLOR', (0, 0), (0, -1), COR_ACCENT),
            ('TEXTCOLOR', (1, 0), (1, -1), COR_PRIMARIA),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LINEBELOW', (0, 0), (-1, -2), 0.5, COR_BORDA),
            ('BACKGROUND', (0, 0), (-1, 0), COR_BG_CLARO),
        ]))
        story.append(t_lmr)

        if trib.get('beneficio'):
            story.append(Spacer(1, 2*mm))
            story.append(Paragraph(f'<b>Beneficio Fiscal:</b> {trib["beneficio"]}', styles['CorpoTexto']))

        recomendacao_lmr = analise_lmr.get('recomendacao', '')
        if recomendacao_lmr:
            story.append(Spacer(1, 2*mm))
            story.append(Paragraph(recomendacao_lmr, styles['Citacao']))

        story.append(Spacer(1, 4*mm))
        secao_num = 4
    else:
        secao_num = 3

    # ---- DECLARACAO DE AUTENTICIDADE ----
    story.append(Paragraph(f'{secao_num}. DECLARACAO DE AUTENTICIDADE', styles['SecaoTitulo']))
    story.append(Paragraph(
        f'Declaro, para os devidos fins, que a presente consulta foi realizada '
        f'diretamente na fonte oficial ({fonte}) em {_data_extenso()}, '
        f'as {datetime.now().strftime("%H:%M:%S")} (horario de Brasilia), '
        f'e que os dados aqui reproduzidos sao fieis ao conteudo publicado na data e hora indicados.',
        styles['CorpoTexto']
    ))

    if link:
        story.append(Spacer(1, 2*mm))
        story.append(Paragraph(
            f'<b>URL de verificacao:</b> {link}',
            styles['CorpoTexto']
        ))

    story.append(Spacer(1, 8*mm))

    # ---- ASSINATURA ----
    story.append(HRFlowable(width='40%', thickness=0.5, color=COR_CINZA))
    story.append(Paragraph(empresa_nome, styles['CorpoNegrito']))
    if empresa_cnpj:
        story.append(Paragraph(f'CNPJ: {empresa_cnpj}', styles['EmpresaInfo']))

    story.append(Spacer(1, 10*mm))

    # ---- RODAPE ----
    story.append(HRFlowable(width='100%', thickness=0.5, color=COR_BORDA))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(
        f'Documento gerado automaticamente pelo Sistema GSM Intelligence - DAMA v73.1 | '
        f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} | '
        f'Este documento nao substitui a consulta direta a fonte oficial.',
        styles['Rodape']
    ))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
