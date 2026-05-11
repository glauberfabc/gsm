"""
Serviço de Esclarecimento Técnico v2 - Revisado Juridicamente
Gera texto técnico-jurídico para informar órgão público sobre
desabastecimento de medicamento e oferta de produto importado.

Revisão Jurídica:
- Base legal atualizada (Lei 14.133/2021, RDC 753/2022, RDC 488/2021)
- Inclusão de solicitação de cópia do processo judicial
- Princípios constitucionais e administrativos corretos
- Menção à Resolução CMED vigente para precificação
- Estrutura de ofício formal padrão da Advocacia Pública
"""

import os
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

logger = logging.getLogger(__name__)

MESES_PT = [
    'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
    'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'
]


def _data_extenso():
    hoje = datetime.now()
    return f"{hoje.day} de {MESES_PT[hoje.month - 1]} de {hoje.year}"


SYSTEM_PROMPT = """Você é um advogado especialista em Direito Administrativo, Licitações Públicas e Regulação Farmacêutica brasileira, com ampla experiência em pregões eletrônicos e processos de contratação pública de medicamentos.

Sua tarefa é redigir um TEXTO DE ESCLARECIMENTO TÉCNICO formal para ser protocolado perante órgão público em processo licitatório.

CONTEXTO JURÍDICO:
O medicamento solicitado no edital encontra-se em situação de desabastecimento, descontinuação ou indisponibilidade no mercado nacional, conforme publicação oficial da ANVISA, DOU ou CMED. A empresa licitante pretende ofertar produto importado como alternativa legalmente válida.

DIRETRIZES JURÍDICAS OBRIGATÓRIAS:

1. BASE LEGAL PRINCIPAL:
   - Lei nº 14.133/2021 (Nova Lei de Licitações), especialmente:
     * Art. 9º, §1º (participação em licitações)
     * Art. 41 (princípio da competitividade)
     * Art. 75, IV, "a" e "b" (dispensa para desabastecimento/emergência)
   - RDC nº 488/2021-ANVISA (importação excepcional de medicamentos em desabastecimento)
   - RDC nº 753/2022-ANVISA (registro de medicamentos importados) - quando aplicável
   - RDC nº 203/2017-ANVISA (procedimentos de importação) - quando aplicável

2. REGRA CRÍTICA DE VIGÊNCIA NORMATIVA (DAMA):
   - Cite APENAS resoluções CMED/ANVISA que estejam VIGENTES
   - NUNCA cite normas com status "caduca" ou "revogada"
   - Se uma resolução estiver caduca/revogada, substitua pela equivalente vigente

3. EXIGÊNCIA DE PROCESSO JUDICIAL:
   - SEMPRE incluir um item/seção informando que, caso o órgão público ACEITE a participação com produto importado, será necessária a DISPONIBILIZAÇÃO DA CÓPIA INTEGRAL DO PROCESSO JUDICIAL que fundamentou a aquisição, quando houver decisão judicial envolvida
   - Fundamentar no princípio da publicidade (Art. 37, CF/88) e no dever de transparência (Art. 5º da Lei 14.133/2021)

4. ESTRUTURA OBRIGATÓRIA DO DOCUMENTO:
   a) Cabeçalho: dados da empresa (Razão Social, CNPJ, endereço)
   b) Data por extenso
   c) Destinatário: Pregoeiro/Comissão de Licitação / Órgão
   d) Referência ao edital (se disponível)
   e) Título: "ESCLARECIMENTO TÉCNICO"
   f) Seções numeradas:
      1. DO DESABASTECIMENTO - com citação da publicação oficial
      2. DA OFERTA DE PRODUTO IMPORTADO - com base legal
      3. DA BASE LEGAL - referências normativas vigentes
      4. DA DOCUMENTAÇÃO COMPROBATÓRIA - prova documental
      5. DA SOLICITAÇÃO DE CÓPIA DO PROCESSO JUDICIAL - quando aplicável
      6. DO REQUERIMENTO - pedido formal
   g) Fecho formal e assinatura

5. LINGUAGEM:
   - Formal, técnica e impessoal
   - Vocabulário jurídico-administrativo adequado
   - Sem abreviações informais
   - Tratamento: "Prezados Senhores" ou "Ilustríssimo(a) Senhor(a) Pregoeiro(a)"
   - Entre 400-600 palavras

6. PRINCÍPIOS A MENCIONAR:
   - Supremacia do interesse público
   - Continuidade do serviço público de saúde
   - Princípio da competitividade (Art. 5º, Lei 14.133/2021)
   - Princípio da economicidade
   - Direito à saúde (Art. 196, CF/88) - quando pertinente

Responda APENAS com o texto do esclarecimento, sem markdown, sem explicações adicionais."""


async def gerar_esclarecimento(
    medicamento: str,
    principio_ativo: str,
    situacao: str,
    link_prova: str,
    tipo_alerta: str,
    empresa: Dict,
    edital_info: Optional[Dict] = None,
    vigencia_context: Optional[str] = None,
) -> Dict:
    """Gera texto de esclarecimento técnico-jurídico revisado."""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        from dotenv import load_dotenv
        load_dotenv()

        api_key = os.environ.get('EMERGENT_LLM_KEY', '')
        if not api_key:
            return _gerar_template_fixo(
                medicamento, principio_ativo, situacao,
                link_prova, tipo_alerta, empresa, edital_info
            )

        chat = LlmChat(
            api_key=api_key,
            session_id=f"esclarecimento-{datetime.now().strftime('%Y%m%d%H%M')}",
            system_message=SYSTEM_PROMPT,
        ).with_model("gemini", "gemini-2.5-flash")

        empresa_nome = empresa.get('name', '[RAZÃO SOCIAL]')
        empresa_cnpj = empresa.get('cnpj', '[CNPJ]')
        empresa_endereco = empresa.get('address', '[ENDEREÇO]')
        empresa_phone = empresa.get('phone', '')
        empresa_email = empresa.get('email', '')

        edital_str = ''
        if edital_info:
            edital_str = f"""
DADOS DO EDITAL:
- Número: {edital_info.get('numero', 'N/A')}
- Órgão Licitante: {edital_info.get('orgao', 'N/A')}
- Objeto: {edital_info.get('objeto', 'N/A')}"""

        vigencia_str = ''
        if vigencia_context:
            vigencia_str = f"""

VIGÊNCIA NORMATIVA (DAMA - Lista atualizada de resoluções CMED):
{vigencia_context}
IMPORTANTE: Use APENAS as normas marcadas como "vigente" ou "vigente com alterações". NÃO cite normas marcadas como BLOQUEADA."""

        prompt = f"""Redija o Texto de Esclarecimento Técnico com os seguintes dados:

MEDICAMENTO EM DESABASTECIMENTO:
- Nome Comercial/Genérico: {medicamento}
- Princípio Ativo: {principio_ativo}
- Situação Oficial: {situacao}
- Tipo do Alerta ANVISA: {tipo_alerta}
- Link da Publicação Oficial (Prova Documental): {link_prova}

EMPRESA LICITANTE:
- Razão Social: {empresa_nome}
- CNPJ: {empresa_cnpj}
- Endereço: {empresa_endereco}
- Telefone: {empresa_phone}
- E-mail: {empresa_email}
{edital_str}{vigencia_str}

Data do documento: {_data_extenso()}

LEMBRE-SE: Incluir obrigatoriamente a seção sobre solicitação de cópia do processo judicial, caso a Administração Pública aceite a participação com produto importado e haja decisão judicial envolvida.

Redija o texto completo do esclarecimento técnico-jurídico."""

        response = await chat.send_message(UserMessage(text=prompt))

        return {
            'texto': response.strip(),
            'medicamento': medicamento,
            'principio_ativo': principio_ativo,
            'link_prova': link_prova,
            'empresa': empresa_nome,
            'empresa_cnpj': empresa_cnpj,
            'gerado_em': datetime.now(timezone.utc).isoformat(),
            'gerado_por': 'gemini',
        }

    except Exception as e:
        logger.error(f"Erro ao gerar esclarecimento com IA: {e}")
        return _gerar_template_fixo(
            medicamento, principio_ativo, situacao,
            link_prova, tipo_alerta, empresa, edital_info
        )


def _gerar_template_fixo(
    medicamento, principio_ativo, situacao, link_prova, tipo_alerta, empresa, edital_info
) -> Dict:
    """Template fixo revisado juridicamente - fallback quando Gemini não está disponível."""
    data_str = _data_extenso()

    empresa_nome = empresa.get('name', '[RAZÃO SOCIAL DA EMPRESA]')
    empresa_cnpj = empresa.get('cnpj', '[CNPJ]')
    empresa_endereco = empresa.get('address', '[ENDEREÇO COMPLETO]')
    empresa_phone = empresa.get('phone', '')
    empresa_email = empresa.get('email', '')

    edital_ref = ''
    orgao_dest = 'Ao Ilustríssimo(a) Senhor(a) Pregoeiro(a)\ne à Comissão Permanente de Licitação'
    if edital_info:
        if edital_info.get('orgao'):
            orgao_dest = f"Ao Ilustríssimo(a) Senhor(a) Pregoeiro(a)\n{edital_info['orgao']}"
        if edital_info.get('numero'):
            edital_ref = f"\nRef.: Pregão Eletrônico nº {edital_info['numero']}"

    texto = f"""{empresa_nome}
CNPJ: {empresa_cnpj}
{empresa_endereco}

{data_str}

{orgao_dest}{edital_ref}

ESCLARECIMENTO TÉCNICO - DESABASTECIMENTO DE {medicamento.upper()} ({principio_ativo.upper()})

Prezados Senhores,

A empresa {empresa_nome}, pessoa jurídica de direito privado, inscrita no CNPJ sob o nº {empresa_cnpj}, com sede em {empresa_endereco}, vem, respeitosamente, à presença de Vossas Senhorias, apresentar o presente ESCLARECIMENTO TÉCNICO acerca do medicamento {medicamento} (princípio ativo: {principio_ativo}), nos termos a seguir expostos.

1. DO DESABASTECIMENTO

Informamos que o medicamento {medicamento} ({principio_ativo}) encontra-se em situação de {situacao} no mercado nacional, conforme publicação oficial da Agência Nacional de Vigilância Sanitária (ANVISA), disponível para consulta no seguinte endereço eletrônico:

{link_prova}

A referida publicação configura prova documental inequívoca da indisponibilidade do produto de fabricação nacional, o que impacta diretamente o abastecimento do Sistema Único de Saúde (SUS) e a continuidade do atendimento à população.

2. DA OFERTA DE PRODUTO IMPORTADO

Diante da comprovada indisponibilidade do produto nacional, e com fundamento na legislação vigente, a empresa {empresa_nome} se propõe a fornecer produto importado equivalente, devidamente autorizado pelos órgãos reguladores competentes, assegurando a mesma qualidade, segurança e eficácia terapêutica.

3. DA BASE LEGAL

A oferta de produto importado em substituição ao nacional indisponível encontra amparo nos seguintes dispositivos legais e normativos:

a) Lei Federal nº 14.133, de 1º de abril de 2021 (Nova Lei de Licitações e Contratos Administrativos):
   - Art. 5º: princípios da legalidade, impessoalidade, publicidade, eficiência e competitividade;
   - Art. 41: garantia do caráter competitivo do processo licitatório;
   - Art. 75, inciso IV: hipóteses de dispensa de licitação em casos de emergência.

b) Resolução da Diretoria Colegiada (RDC) nº 488, de 6 de outubro de 2021 - ANVISA:
   - Regulamenta a importação excepcional de medicamentos em situação de desabastecimento no mercado nacional.

c) Constituição Federal de 1988:
   - Art. 196: direito à saúde como dever do Estado, garantido mediante políticas que visem à redução do risco de doença;
   - Art. 37, caput: princípios da Administração Pública, incluindo publicidade e eficiência.

4. DA DOCUMENTAÇÃO COMPROBATÓRIA

Segue como anexo a publicação oficial da ANVISA que comprova a situação de desabastecimento do medicamento em questão, servindo como prova documental para fins de habilitação e esclarecimento perante este órgão público.

5. DA SOLICITAÇÃO DE CÓPIA DO PROCESSO JUDICIAL

Caso esta Administração Pública venha a deferir a participação desta empresa com o produto importado, e havendo decisão judicial que fundamente a aquisição do referido medicamento, requer-se, com fulcro no princípio constitucional da publicidade (Art. 37, caput, CF/88), no dever de transparência (Art. 5º da Lei nº 14.133/2021) e no direito de acesso à informação (Lei nº 12.527/2011), a disponibilização da cópia integral do processo judicial correspondente, para fins de adequação da proposta comercial e cumprimento das obrigações contratuais.

6. DO REQUERIMENTO

Ante o exposto, a empresa {empresa_nome} requer:

a) O recebimento e a juntada do presente Esclarecimento Técnico aos autos do processo licitatório;
b) A aceitação da proposta com produto importado equivalente, em conformidade com a legislação vigente;
c) A disponibilização da cópia do processo judicial, caso existente, nos termos do item 5 supra.

Nestes termos, pede deferimento.

Atenciosamente,

____________________________________
{empresa_nome}
CNPJ: {empresa_cnpj}"""

    if empresa_phone:
        texto += f"\nTelefone: {empresa_phone}"
    if empresa_email:
        texto += f"\nE-mail: {empresa_email}"

    return {
        'texto': texto,
        'medicamento': medicamento,
        'principio_ativo': principio_ativo,
        'link_prova': link_prova,
        'empresa': empresa_nome,
        'empresa_cnpj': empresa_cnpj,
        'gerado_em': datetime.now(timezone.utc).isoformat(),
        'gerado_por': 'template',
    }
