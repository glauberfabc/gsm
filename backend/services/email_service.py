"""
Email Service - P5

Serviço de envio de emails usando Resend.
Inclui template HTML profissional para alertas de licitações.
"""

import os
import asyncio
import logging
import resend
from typing import List, Dict, Optional
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Configuração Resend
resend.api_key = os.environ.get('RESEND_API_KEY', '')

# Configuração de emails
# TODO: Alterar para licitacoes@gruposmartmedical.com.br após verificar domínio no Resend
SENDER_EMAIL = "onboarding@resend.dev"  # Temporário para testes
REPLY_TO_EMAIL = "claudio@gruposmartmedical.com.br"


class EmailService:
    """
    Serviço de envio de emails para alertas de licitações.
    
    Usa Resend API com template HTML profissional.
    """
    
    def __init__(self):
        self.sender = SENDER_EMAIL
        self.reply_to = REPLY_TO_EMAIL
    
    # 📧 CC OBRIGATÓRIO (REGRA FIXA E GLOBAL)
    CC_OBRIGATORIO = [
        "hudson@vipfarma.com.br",
        "claudio@gruposmartmedical.com.br"
    ]
    
    async def enviar_alerta(self, destinatario: str, termo: str, editais: List[Dict]) -> Dict:
        """
        Envia email de alerta com novas oportunidades.
        
        REGRA OBRIGATÓRIA:
        - CC sempre para hudson@vipfarma.com.br e claudio@gruposmartmedical.com.br
        
        NOTA: No modo de teste Resend (onboarding@resend.dev), o CC é limitado.
        O código está preparado para produção com domínio verificado.
        
        Args:
            destinatario: Email do destinatário
            termo: Termo de busca do alerta
            editais: Lista de editais para enviar
            
        Returns:
            Dict com status do envio
        """
        if not editais:
            return {"status": "skip", "message": "Nenhum edital para enviar"}
        
        # Gerar HTML do email
        html_content = self._gerar_template_alerta(termo, editais)
        
        # Assunto do email
        qtd = len(editais)
        subject = f"🔔 {qtd} nova{'s' if qtd > 1 else ''} oportunidade{'s' if qtd > 1 else ''} para '{termo}'"
        
        # Lista de destinatários (evitar duplicados no CC)
        destinatarios = [destinatario]
        cc_list = [email for email in self.CC_OBRIGATORIO if email != destinatario]
        
        # 📧 LIMITAÇÃO RESEND MODO TESTE:
        # No modo de teste (onboarding@resend.dev), só podemos enviar para emails verificados.
        # Removemos o CC temporariamente para garantir entrega no teste.
        # Em PRODUÇÃO com domínio verificado, o CC funcionará normalmente.
        is_test_mode = self.sender == "onboarding@resend.dev"
        cc_usado = []  # Sem CC no modo teste
        cc_nota = ""
        
        if is_test_mode:
            logger.warning("⚠️ [EMAIL] Modo teste Resend - CC desabilitado temporariamente")
            cc_nota = " (CC desabilitado no modo teste - funcionará em produção)"
        else:
            cc_usado = cc_list
        
        params = {
            "from": self.sender,
            "to": destinatarios,
            "reply_to": self.reply_to,
            "subject": subject,
            "html": html_content
        }
        
        # Só adiciona CC se não estiver vazio
        if cc_usado:
            params["cc"] = cc_usado
        
        try:
            # Run sync SDK in thread to keep FastAPI non-blocking
            email = await asyncio.to_thread(resend.Emails.send, params)
            
            logger.info(f"✅ [EMAIL] Enviado para {destinatario} (CC: {', '.join(cc_usado) if cc_usado else 'desabilitado'}): {qtd} editais de '{termo}'")
            
            return {
                "status": "success",
                "message": f"Email enviado para {destinatario}{cc_nota}",
                "email_id": email.get("id"),
                "editais_enviados": len(editais),
                "cc": cc_list,  # Retorna o CC configurado (para referência)
                "cc_ativo": cc_usado,  # Retorna o CC realmente usado
                "modo_teste": is_test_mode,
                "nota_cc": "⚠️ CC OBRIGATÓRIO configurado mas temporariamente desabilitado no Resend teste. Em produção com domínio verificado, os emails serão enviados para hudson@vipfarma.com.br e claudio@gruposmartmedical.com.br automaticamente." if is_test_mode else None
            }
            
        except Exception as e:
            logger.error(f"❌ [EMAIL] Erro ao enviar para {destinatario}: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    async def enviar_teste(self, destinatario: str) -> Dict:
        """
        Envia email de teste para verificar configuração.
        """
        html_content = self._gerar_template_teste()
        
        params = {
            "from": self.sender,
            "to": [destinatario],
            "reply_to": self.reply_to,
            "subject": "✅ Teste de Configuração - GSM Alertas",
            "html": html_content
        }
        
        try:
            email = await asyncio.to_thread(resend.Emails.send, params)
            
            logger.info(f"✅ [EMAIL] Teste enviado para {destinatario}")
            
            return {
                "status": "success",
                "message": f"Email de teste enviado para {destinatario}",
                "email_id": email.get("id")
            }
            
        except Exception as e:
            logger.error(f"❌ [EMAIL] Erro no teste para {destinatario}: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def _highlight_termo(self, texto: str, termo: str) -> str:
        """
        🆕 v4.6: Aplica highlight (fundo amarelo) ao termo no texto.
        
        O termo é destacado com:
        - background-color: #fde047 (amarelo)
        - font-weight: bold
        - padding: 2px 4px
        - border-radius: 2px
        """
        import re
        if not termo or not texto:
            return texto
        
        # Escapar caracteres especiais do termo para regex
        termo_escaped = re.escape(termo)
        
        # Criar padrão para match case-insensitive
        pattern = re.compile(f'({termo_escaped})', re.IGNORECASE)
        
        # Substituir com highlight
        highlighted = pattern.sub(
            r'<span style="background-color: #fde047; font-weight: bold; padding: 2px 4px; border-radius: 2px;">\1</span>',
            texto
        )
        
        return highlighted
    
    def _gerar_template_alerta(self, termo: str, editais: List[Dict]) -> str:
        """
        Gera template HTML profissional para o email de alerta.
        🆕 v4.6: Agora com highlighting do termo em amarelo.
        """
        # Gerar cards dos editais
        editais_html = ""
        for edital in editais:
            editais_html += self._gerar_card_edital(edital, termo)
        
        # Highlight do termo no header
        termo_highlighted = f'<span style="background-color: #fde047; color: #1e3a8a; font-weight: bold; padding: 4px 8px; border-radius: 4px;">{termo}</span>'
        
        return f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f5f5f5;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f5f5f5; padding: 20px 0;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%); padding: 30px; border-radius: 8px 8px 0 0;">
                            <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 600;">
                                🔔 Novas Oportunidades
                            </h1>
                            <p style="color: #bfdbfe; margin: 10px 0 0 0; font-size: 16px;">
                                Termo de busca: {termo_highlighted}
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Summary -->
                    <tr>
                        <td style="padding: 20px 30px; background-color: #eff6ff; border-bottom: 1px solid #dbeafe;">
                            <p style="margin: 0; color: #1e40af; font-size: 16px;">
                                📊 <strong>{len(editais)}</strong> nova{'s' if len(editais) > 1 else ''} oportunidade{'s' if len(editais) > 1 else ''} encontrada{'s' if len(editais) > 1 else ''}
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Editais -->
                    <tr>
                        <td style="padding: 20px 30px;">
                            {editais_html}
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 20px 30px; background-color: #f8fafc; border-top: 1px solid #e2e8f0; border-radius: 0 0 8px 8px;">
                            <p style="margin: 0; color: #64748b; font-size: 12px; text-align: center;">
                                Este email foi enviado automaticamente pelo sistema GSM - Buscador de Editais.<br>
                                Para cancelar este alerta, acesse o painel de configurações.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
        '''
    
    def _gerar_card_edital(self, edital: Dict, termo: str = "") -> str:
        """
        Gera HTML de um card de edital.
        
        🔗 PADRÃO GSM - INFORMAÇÕES OBRIGATÓRIAS EM DESTAQUE:
        1. ✅ NÚMERO DO PROCESSO/EDITAL - Em destaque no topo
        2. ✅ DATA DE ABERTURA/SESSÃO - Caixa destacada
        3. ✅ ITEM Nº CORRESPONDENTE - Cards individuais com número
        4. ✅ Link direto para o edital (PDF)
        """
        orgao = edital.get('orgao', 'Órgão não informado')[:60]
        
        # 📋 NÚMERO DO PROCESSO/EDITAL - DESTAQUE OBRIGATÓRIO
        numero_processo = edital.get('numero_processo') or edital.get('numero_edital') or edital.get('numero_controle_pncp') or edital.get('numero', 'N/A')
        
        modalidade = edital.get('modalidade', 'N/A')
        objeto = edital.get('objeto', 'N/A')[:200]
        status = edital.get('status_oportunidade', 'ATIVA')
        uf = edital.get('uf', '')
        municipio = edital.get('municipio', '')
        
        # Localização
        local = f"{municipio}/{uf}" if municipio and uf else (municipio or uf or '')
        
        # =====================================================================
        # 📅 DATA DE ABERTURA/SESSÃO - DESTAQUE OBRIGATÓRIO
        # =====================================================================
        data_abertura = edital.get('data_abertura') or edital.get('data_fim_vigencia') or edital.get('data_sessao') or edital.get('data_publicacao')
        data_html = ""
        data_formatada = "Não informada"
        
        if data_abertura:
            try:
                if isinstance(data_abertura, str):
                    if 'T' in data_abertura:
                        data_obj = datetime.fromisoformat(data_abertura.replace('Z', '+00:00'))
                        data_formatada = data_obj.strftime("%d/%m/%Y às %H:%M")
                    else:
                        data_formatada = data_abertura
                else:
                    data_formatada = str(data_abertura)
            except:
                data_formatada = str(data_abertura)
        
        data_html = f'''
        <tr>
            <td style="padding: 12px 16px; background-color: #fef3c7; border-left: 4px solid #f59e0b;">
                <table width="100%" cellpadding="0" cellspacing="0">
                    <tr>
                        <td style="width: 30px; vertical-align: top;">
                            <span style="font-size: 18px;">📅</span>
                        </td>
                        <td>
                            <span style="color: #92400e; font-size: 12px; text-transform: uppercase; font-weight: 600;">Data de Abertura/Sessão</span><br>
                            <span style="color: #78350f; font-size: 16px; font-weight: 700;">{data_formatada}</span>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
        '''
        
        # =====================================================================
        # 🎯 ITENS CORRESPONDENTES AO TERMO - DESTAQUE OBRIGATÓRIO
        # =====================================================================
        # Prioridade: itens_correspondentes > itens_edital
        itens = edital.get('itens_correspondentes', []) or edital.get('itens_edital', [])
        arquivos = edital.get('arquivos_disponiveis', [])
        
        itens_html = ""
        if itens and len(itens) > 0:
            itens_cards = ""
            for idx, item in enumerate(itens[:5], 1):
                desc = item.get('descricao', 'Descrição não disponível')[:100]
                # 🆕 v4.6: Aplicar highlight ao termo na descrição
                desc_highlighted = self._highlight_termo(desc, termo)
                
                num_item = item.get('numero_item', 'NA')
                qtd = item.get('quantidade', 'NA')
                unidade = item.get('unidade', '')
                valor_unitario = item.get('valor_unitario', 'NA')
                valor_total = item.get('valor_total', 'NA')
                fonte = item.get('fonte', 'N/A')
                
                # Formatar quantidade com indicador NA
                if qtd == 'NA' or qtd is None or qtd == '':
                    qtd_display = '<span style="color: #dc2626; font-weight: 600;">NA</span>'
                else:
                    qtd_display = f'{qtd} {unidade}'
                
                # Formatar valor unitário com indicador NA
                if valor_unitario == 'NA' or valor_unitario is None or valor_unitario == '':
                    valor_un_display = '<span style="color: #dc2626; font-size: 11px;">Valor unit.: NA</span>'
                else:
                    try:
                        valor_un_display = f'<span style="color: #059669; font-size: 11px;">Valor unit.: R$ {float(valor_unitario):,.2f}</span>'
                    except:
                        valor_un_display = f'<span style="color: #059669; font-size: 11px;">Valor unit.: {valor_unitario}</span>'
                
                # Formatar valor total com indicador NA
                if valor_total == 'NA' or valor_total is None or valor_total == '':
                    valor_total_display = '<span style="color: #dc2626; font-weight: 600;">Total: NA</span>'
                else:
                    try:
                        valor_total_display = f'<strong style="color: #059669;">Total: R$ {float(valor_total):,.2f}</strong>'
                    except:
                        valor_total_display = f'<strong style="color: #059669;">Total: {valor_total}</strong>'
                
                # Badge do número do item
                if num_item == 'NA':
                    num_badge = '<span style="display: inline-block; background-color: #dc2626; color: #ffffff; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: 700;">Item NA</span>'
                else:
                    num_badge = f'<span style="display: inline-block; background-color: #2563eb; color: #ffffff; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: 700;">Item {num_item}</span>'
                
                itens_cards += f'''
                <tr>
                    <td style="padding: 10px; background-color: #ffffff; border: 1px solid #dbeafe; border-radius: 4px; margin-bottom: 4px;">
                        <table width="100%" cellpadding="0" cellspacing="0">
                            <tr>
                                <td style="width: 70px; vertical-align: top;">
                                    {num_badge}
                                </td>
                                <td style="padding-left: 10px;">
                                    <span style="color: #1f2937; font-size: 13px; font-weight: 600;">{desc_highlighted}</span>
                                    <br>
                                    <span style="color: #6b7280; font-size: 12px;">
                                        Qtd: {qtd_display} | {valor_un_display} | {valor_total_display}
                                    </span>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
                <tr><td style="height: 6px;"></td></tr>
                '''
            
            # Determinar fonte dos dados
            fonte_texto = "Dados extraídos diretamente do edital oficial"
            if any(item.get('_item_nao_estruturado') for item in itens):
                fonte_texto = "⚠️ Alguns itens não puderam ser estruturados automaticamente"
            
            itens_html = f'''
            <tr>
                <td style="padding: 12px 16px; background-color: #eff6ff; border-left: 4px solid #3b82f6;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                        <tr>
                            <td style="padding-bottom: 10px;">
                                <span style="font-size: 18px;">🎯</span>
                                <span style="color: #1e40af; font-size: 14px; font-weight: 700; margin-left: 4px;">
                                    Itens correspondentes ao termo "{termo}" ({len(itens)})
                                </span>
                                <br>
                                <span style="color: #3b82f6; font-size: 11px; font-style: italic;">
                                    * {fonte_texto}
                                </span>
                            </td>
                        </tr>
                        {itens_cards}
                    </table>
                </td>
            </tr>
            '''
        else:
            # Aviso quando não há itens estruturados
            itens_html = f'''
            <tr>
                <td style="padding: 12px 16px; background-color: #fef3c7; border-left: 4px solid #f59e0b;">
                    <span style="color: #92400e; font-size: 13px;">
                        ⚠️ <strong>Itens não estruturados:</strong> Este edital não possui itens extraídos automaticamente. 
                        Consulte o PDF do edital para detalhes.
                    </span>
                </td>
            </tr>
            '''
        
        # =====================================================================
        # 🔗 LINK DO EDITAL - v75.1: Fix link None + priorizar PDF/portal
        # =====================================================================
        link_sistema = edital.get('link_sistema_origem') or ''
        link_edital = edital.get('link_edital') or ''
        link_portal = edital.get('link_portal') or ''
        link_pdf = edital.get('link_pdf') or ''
        is_dama_alert = edital.get('is_dama_alert', False)
        
        # Prioridade: PDF direto > link_portal > link_sistema > link_edital > fallback PNCP
        if link_pdf and link_pdf.startswith('http'):
            link = link_pdf
        elif link_portal and link_portal.startswith('http'):
            link = link_portal
            if 'pncp.gov.br/app/compras/' in link:
                link = link.replace('/app/compras/', '/app/editais/')
        elif link_sistema and link_sistema.startswith('http'):
            link = link_sistema
        elif link_edital and link_edital.startswith('http'):
            link = link_edital
        else:
            # Fallback: busca no PNCP com termo seguro
            termo_busca = numero_processo if numero_processo and numero_processo != 'None' else edital.get('objeto', '')[:40]
            link = f'https://pncp.gov.br/app/editais?q={termo_busca}'
        
        # Texto e cor do botao: DAMA vs edital convencional
        if is_dama_alert:
            botao_texto = '📋 Ver Analise no DAMA / Baixar Prova Documental'
            botao_cor = '#059669'  # emerald
        else:
            botao_texto = '📄 Ver Edital / Baixar PDF →'
            botao_cor = '#2563eb'  # blue
        
        # Cores baseadas no status
        status_color = "#22c55e" if status == "ATIVA" else "#f59e0b" if status == "FUTURA" else "#6b7280"
        status_bg = "#dcfce7" if status == "ATIVA" else "#fef3c7" if status == "FUTURA" else "#f3f4f6"
        
        return f'''
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 20px; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden;">
            <!-- HEADER: Status + Nº Processo -->
            <tr>
                <td style="padding: 16px; background-color: #f8fafc; border-bottom: 1px solid #e2e8f0;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                        <tr>
                            <td>
                                <!-- Status -->
                                <span style="display: inline-block; padding: 4px 10px; background-color: {status_bg}; color: {status_color}; font-size: 11px; font-weight: 600; border-radius: 4px; text-transform: uppercase; margin-right: 8px;">
                                    {status}
                                </span>
                                <!-- Modalidade -->
                                <span style="display: inline-block; padding: 4px 10px; background-color: #f3f4f6; color: #374151; font-size: 11px; border-radius: 4px;">
                                    {modalidade}
                                </span>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding-top: 12px;">
                                <!-- 📋 NÚMERO DO PROCESSO - DESTAQUE OBRIGATÓRIO -->
                                <div style="background-color: #1e40af; color: #ffffff; padding: 10px 14px; border-radius: 6px; display: inline-block;">
                                    <span style="font-size: 12px; opacity: 0.9;">Processo/Edital nº</span><br>
                                    <span style="font-size: 18px; font-weight: 700;">{numero_processo}</span>
                                </div>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
            
            <!-- ÓRGÃO + LOCAL -->
            <tr>
                <td style="padding: 16px; border-bottom: 1px solid #e2e8f0;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                        <tr>
                            <td>
                                <span style="font-size: 16px;">🏛️</span>
                                <span style="color: #1f2937; font-size: 15px; font-weight: 600; margin-left: 4px;">{orgao}</span>
                            </td>
                        </tr>
                        {f'<tr><td style="padding-top: 4px;"><span style="color: #6b7280; font-size: 13px;">📍 {local}</span></td></tr>' if local else ''}
                    </table>
                </td>
            </tr>
            
            <!-- 📅 DATA DE ABERTURA - DESTAQUE -->
            {data_html}
            
            <!-- OBJETO -->
            <tr>
                <td style="padding: 16px;">
                    <p style="margin: 0; color: #374151; font-size: 14px; line-height: 1.5;">
                        {objeto}...
                    </p>
                </td>
            </tr>
            
            <!-- 🎯 ITENS CORRESPONDENTES - DESTAQUE -->
            {itens_html}
            
            <!-- 🆕 v4.5: ARQUIVOS DISPONÍVEIS (Múltiplos tipos) -->
            {self._gerar_arquivos_html(edital)}
            
            <!-- BOTÃO VER EDITAL -->
            <tr>
                <td style="padding: 16px; background-color: #f8fafc; border-top: 1px solid #e2e8f0;">
                    <a href="{link}" target="_blank" style="display: inline-block; padding: 12px 24px; background-color: {botao_cor}; color: #ffffff; text-decoration: none; font-size: 14px; font-weight: 600; border-radius: 6px;">
                        {botao_texto}
                    </a>
                </td>
            </tr>
        </table>
        '''
    
    def _gerar_arquivos_html(self, edital: Dict) -> str:
        """
        🆕 v4.5: Gera seção de múltiplos arquivos (EDITAL, TR, ETP, etc.)
        
        Cada arquivo tem um botão específico por tipo com cor distinta.
        """
        arquivos = edital.get('arquivos_disponiveis', [])
        
        if not arquivos or len(arquivos) <= 1:
            return ""
        
        # Cores por tipo de documento
        cores = {
            'EDITAL': {'bg': '#dcfce7', 'border': '#22c55e', 'text': '#15803d'},
            'TR': {'bg': '#dbeafe', 'border': '#3b82f6', 'text': '#1d4ed8'},
            'ETP': {'bg': '#f3e8ff', 'border': '#a855f7', 'text': '#7e22ce'},
            'MINUTA': {'bg': '#fef3c7', 'border': '#f59e0b', 'text': '#b45309'},
            'ATA': {'bg': '#fce7f3', 'border': '#ec4899', 'text': '#be185d'},
            'ANEXO': {'bg': '#f3f4f6', 'border': '#9ca3af', 'text': '#4b5563'},
            'OUTROS': {'bg': '#f1f5f9', 'border': '#94a3b8', 'text': '#475569'}
        }
        
        botoes_html = ""
        for arq in arquivos[:6]:  # Limitar a 6 arquivos
            tipo = arq.get('tipo_documento', 'OUTROS')
            titulo = arq.get('titulo_original', tipo)[:25]
            url = arq.get('url', '')
            
            if not url:
                continue
            
            cor = cores.get(tipo, cores['OUTROS'])
            
            botoes_html += f'''
            <a href="{url}" target="_blank" style="
                display: inline-block; 
                margin: 4px;
                padding: 8px 14px; 
                background-color: {cor['bg']}; 
                border: 1px solid {cor['border']};
                color: {cor['text']}; 
                text-decoration: none; 
                font-size: 12px; 
                font-weight: 600; 
                border-radius: 6px;
            ">
                ⬇️ {tipo}
            </a>
            '''
        
        return f'''
        <tr>
            <td style="padding: 12px 16px; background-color: #f8fafc; border-left: 4px solid #6366f1;">
                <table width="100%" cellpadding="0" cellspacing="0">
                    <tr>
                        <td style="padding-bottom: 8px;">
                            <span style="font-size: 16px;">📁</span>
                            <span style="color: #4338ca; font-size: 13px; font-weight: 700; margin-left: 4px;">
                                Arquivos Disponíveis ({len(arquivos)})
                            </span>
                        </td>
                    </tr>
                    <tr>
                        <td>
                            {botoes_html}
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
        '''
    
    def _gerar_template_teste(self) -> str:
        """
        Gera template HTML para email de teste.
        """
        return f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f5f5f5;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f5f5f5; padding: 20px 0;">
        <tr>
            <td align="center">
                <table width="500" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    <tr>
                        <td style="background: linear-gradient(135deg, #059669 0%, #10b981 100%); padding: 30px; border-radius: 8px 8px 0 0; text-align: center;">
                            <h1 style="color: #ffffff; margin: 0; font-size: 24px;">
                                ✅ Configuração OK!
                            </h1>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 30px; text-align: center;">
                            <p style="margin: 0; color: #374151; font-size: 16px; line-height: 1.6;">
                                O sistema de alertas está configurado corretamente.<br><br>
                                Você receberá notificações de novas oportunidades<br>
                                baseadas nos seus termos de busca salvos.
                            </p>
                            <p style="margin: 20px 0 0 0; color: #6b7280; font-size: 14px;">
                                <strong>Data do teste:</strong> {datetime.now().strftime("%d/%m/%Y %H:%M")}
                            </p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 20px; background-color: #f8fafc; border-top: 1px solid #e2e8f0; border-radius: 0 0 8px 8px; text-align: center;">
                            <p style="margin: 0; color: #64748b; font-size: 12px;">
                                GSM - Buscador de Editais<br>
                                Grupo Smart Medical
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
        '''


    def get_status(self) -> Dict:
        """
        Retorna status da configuração do serviço de email.
        Compatibilidade com sistema de notificações existente.
        """
        api_key = os.environ.get('RESEND_API_KEY', '')
        configurado = bool(api_key and len(api_key) > 10)
        
        return {
            "configurado": configurado,
            "provider": "Resend",
            "sender": self.sender,
            "reply_to": self.reply_to,
            "api_key_status": "configurada" if configurado else "não configurada",
            "api_key_preview": f"{api_key[:8]}..." if configurado else "vazia"
        }
    
    async def enviar_alerta_radar(
        self,
        email: str,
        nome_radar: str,
        editais: List[Dict],
        termo_principal: str = None
    ) -> Dict:
        """
        🎯 v52.0: Envia email de alerta para um radar específico
        
        Assunto dinâmico: 🔔 [NOME DO RADAR]: Match para [TERMO]
        
        Args:
            email: Email do destinatário
            nome_radar: Nome do radar
            editais: Lista de editais encontrados
            termo_principal: Termo principal da busca (para o assunto)
            
        Returns:
            Dict com status do envio
        """
        if not editais:
            return {"status": "skip", "message": "Nenhum edital para enviar"}
        
        # Gerar HTML do email com estilo radar
        html_content = self._gerar_template_radar(nome_radar, editais)
        
        # Assunto do email v52.0 - Dinâmico com termo
        qtd = len(editais)
        if termo_principal:
            subject = f"🔔 [{nome_radar}]: Match para {termo_principal} ({qtd} edita{'is' if qtd > 1 else 'l'})"
        else:
            subject = f"🔔 [{nome_radar}]: {qtd} nova{'s' if qtd > 1 else ''} oportunidade{'s' if qtd > 1 else ''}"
        
        params = {
            "from": self.sender,
            "to": [email],
            "reply_to": self.reply_to,
            "subject": subject,
            "html": html_content
        }
        
        try:
            email_response = await asyncio.to_thread(resend.Emails.send, params)
            
            logger.info(f"✅ [RADAR EMAIL] Enviado para {email}: {qtd} editais do radar '{nome_radar}'")
            
            return {
                "status": "success",
                "message": f"Email do radar enviado para {email}",
                "email_id": email_response.get("id"),
                "editais_enviados": len(editais)
            }
            
        except Exception as e:
            logger.error(f"❌ [RADAR EMAIL] Erro ao enviar para {email}: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def _gerar_template_radar(self, nome_radar: str, editais: List[Dict]) -> str:
        """
        🎯 v25.1: Gera template HTML para emails de radar
        """
        # Gerar cards dos editais
        editais_html = ""
        for edital in editais:
            editais_html += self._gerar_card_edital_radar(edital)
        
        return f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f1f5f9; margin: 0; padding: 20px;">
    <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: 0 auto;">
        <tr>
            <td>
                <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #0f172a; border-radius: 16px 16px 0 0;">
                    <tr>
                        <td style="padding: 30px; text-align: center;">
                            <div style="font-size: 48px; margin-bottom: 10px;">🛰️</div>
                            <h1 style="color: #10b981; margin: 0; font-size: 24px; font-weight: 900; text-transform: uppercase;">
                                Radar: {nome_radar}
                            </h1>
                            <p style="color: #94a3b8; margin: 10px 0 0 0; font-size: 14px;">
                                {len(editais)} nova{'s' if len(editais) > 1 else ''} oportunidade{'s' if len(editais) > 1 else ''} detectada{'s' if len(editais) > 1 else ''}
                            </p>
                        </td>
                    </tr>
                </table>
                
                <table width="100%" cellpadding="0" cellspacing="0" style="background-color: white;">
                    <tr>
                        <td style="padding: 30px;">
                            {editais_html}
                        </td>
                    </tr>
                </table>
                
                <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f8fafc; border-radius: 0 0 16px 16px; border-top: 1px solid #e2e8f0;">
                    <tr>
                        <td style="padding: 20px; text-align: center;">
                            <p style="margin: 0; color: #64748b; font-size: 12px;">
                                GSM Buscador de Editais v25.1<br>
                                <strong>Grupo Smart Medical</strong>
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
        '''
    
    def _gerar_card_edital_radar(self, edital: Dict) -> str:
        """
        🎯 v25.1: Gera card HTML para edital de radar
        """
        orgao = edital.get('orgao', 'Órgão não informado')[:60]
        objeto = edital.get('objeto', 'Objeto não informado')[:150]
        link = edital.get('link_edital', '#')
        status = edital.get('status_oportunidade', 'ATIVA')
        
        status_color = '#10b981' if status == 'ATIVA' else '#f59e0b' if status == 'FUTURA' else '#ef4444'
        
        return f'''
            <div style="margin-bottom: 20px; padding: 20px; background-color: #f8fafc; border-radius: 12px; border-left: 4px solid {status_color};">
                <div style="margin-bottom: 8px;">
                    <span style="background-color: {status_color}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 10px; font-weight: bold; text-transform: uppercase;">
                        {status}
                    </span>
                </div>
                <p style="margin: 0 0 8px 0; font-weight: bold; color: #1e293b; font-size: 14px;">
                    {orgao}
                </p>
                <p style="margin: 0 0 12px 0; color: #64748b; font-size: 13px; line-height: 1.4;">
                    {objeto}...
                </p>
                <a href="{link}" target="_blank" style="display: inline-block; background-color: #0f172a; color: white; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-size: 12px; font-weight: bold;">
                    Ver Edital →
                </a>
            </div>
        '''
    
    async def enviar_alerta_licitacoes(
        self, 
        destinatario: str, 
        palavra_chave: str, 
        licitacoes: List[Dict],
        nome_alerta: str = None
    ) -> Dict:
        """
        Método de compatibilidade com sistema de notificações existente.
        Converte formato antigo para novo e envia email.
        
        Args:
            destinatario: Email do destinatário
            palavra_chave: Termo de busca (usado como termo)
            licitacoes: Lista de licitações no formato antigo
            nome_alerta: Nome do alerta (opcional)
            
        Returns:
            Dict com status do envio
        """
        # Converter licitações do formato antigo para o novo
        editais_convertidos = []
        for lic in licitacoes:
            editais_convertidos.append({
                "orgao": lic.get("orgao", "N/A"),
                "numero_processo": lic.get("numero_processo", "N/A"),
                "modalidade": lic.get("modalidade", "Pregão"),
                "objeto": lic.get("objeto", lic.get("titulo", "N/A")),
                "status_oportunidade": "ATIVA",
                "relevance_score": lic.get("relevance_score", 50),
                "quality_score": lic.get("quality_score", 70),
                "link_edital": lic.get("link_origem", lic.get("link_edital", "#")),
                "itens_correspondentes": lic.get("itens_correspondentes", [])
            })
        
        # Verificar se API está configurada
        api_key = os.environ.get('RESEND_API_KEY', '')
        if not api_key or len(api_key) < 10:
            # Modo mock - apenas log
            logger.info(f"📧 [MOCK] Email para {destinatario}: {len(editais_convertidos)} editais de '{palavra_chave}'")
            return {
                "status": "mocked",
                "message": f"Email mockado (sem API key) para {destinatario}",
                "editais_enviados": len(editais_convertidos)
            }
        
        # Enviar usando método principal
        return await self.enviar_alerta(destinatario, palavra_chave, editais_convertidos)


# Singleton
_email_service = None

def get_email_service() -> EmailService:
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
