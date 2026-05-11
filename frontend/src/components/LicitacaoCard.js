import React, { useState } from 'react';
import { ChevronDown, ChevronUp, FileText, ExternalLink, Calendar, Building2, MapPin, Tag, Clock, Hash, Package, List, Download, AlertTriangle, ShieldCheck, CheckCircle } from 'lucide-react';

/**
 * 🎯 PADRÃO GSM - CARD DE LICITAÇÃO (v4.0 ELITE)
 * 
 * Especificação Técnica de Finalização GSM:
 * 
 * CAMPOS OBRIGATÓRIOS:
 * - Portal de Origem (PNCP, BNC, etc.)
 * - Número da UASG/Código da Unidade
 * - Número da Licitação/Processo
 * - Cidade e UF (Estado)
 * - Data de Publicação, Data Inicial (Abertura), Data Final
 * 
 * TABELA DE ITENS (Crucial - Padrão GSM):
 * - Nº do Item
 * - Descrição Detalhada
 * - Status ME/EPP
 * - Quantidade
 * - Valor Total Estimado
 * 
 * LÓGICA "SAFE REDIRECT":
 * - Prioridade 1: Link direto para arquivo (PDF/ZIP)
 * - Prioridade 2: URL da página de detalhes do PNCP
 * 
 * GRIFO VISUAL (v3.7):
 * - Destaca o termo buscado em amarelo no objeto e nos itens
 */

// 🖍️ COMPONENTE DE GRIFO VISUAL (HIGHLIGHT) - v3.7 ELITE
const Highlight = ({ text, highlight }) => {
  if (!text) return <span>-</span>;
  if (!highlight || !highlight.trim()) return <span>{text}</span>;
  
  try {
    // Escapar caracteres especiais de regex
    const escapedHighlight = highlight.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const regex = new RegExp(`(${escapedHighlight})`, 'gi');
    const parts = String(text).split(regex);
    
    return (
      <span>
        {parts.map((part, i) => 
          regex.test(part) ? (
            <mark key={i} className="bg-yellow-300 text-black font-black px-0.5 rounded">
              {part}
            </mark>
          ) : (
            <span key={i}>{part}</span>
          )
        )}
      </span>
    );
  } catch {
    return <span>{text}</span>;
  }
};

export default function LicitacaoCard({ licitacao, termoBusca = '' }) {
  const [expandido, setExpandido] = useState(false);
  const [mostrarTodosItens, setMostrarTodosItens] = useState(false);

  // 🛡️ PROTEÇÃO ANTI-TELA BRANCA: Validar dados de entrada
  if (!licitacao || typeof licitacao !== 'object') {
    return (
      <div className="bg-amber-50 border border-amber-300 rounded-lg p-4 mb-4">
        <span className="text-amber-800 text-sm">⚠️ Dados de licitação inválidos</span>
      </div>
    );
  }

  // 🎯 BADGE DE STATUS DE OPORTUNIDADE V3 (PADRÃO GSM)
  const getStatusOportunidadeBadge = () => {
    const status = licitacao.status_oportunidade || 'ENCERRADA';
    const badgeData = licitacao.badge_status || {};
    const isCredenciamento = licitacao.is_credenciamento || badgeData.is_credenciamento || false;
    
    const configs = {
      'ATIVA': {
        bg: isCredenciamento ? 'bg-blue-500' : 'bg-green-500',
        text: 'text-white',
        border: isCredenciamento ? 'border-blue-600' : 'border-green-600',
        icon: isCredenciamento ? '🔵' : '🟢',
        label: isCredenciamento ? 'ATIVA - Credenciamento' : 'ATIVA',
        subtexto: badgeData.subtexto || (licitacao.dias_ate_abertura !== null ? 
          (isCredenciamento ? `Vigente (${licitacao.dias_ate_abertura} dias)` : `Em ${licitacao.dias_ate_abertura} dias`) : ''),
        pulse: !isCredenciamento && licitacao.dias_ate_abertura !== null && licitacao.dias_ate_abertura <= 3
      },
      'FUTURA': {
        bg: 'bg-yellow-500',
        text: 'text-white',
        border: 'border-yellow-600',
        icon: '🟡',
        label: 'FUTURA',
        subtexto: badgeData.subtexto || '',
        pulse: false
      },
      'ENCERRADA': {
        bg: 'bg-gray-400',
        text: 'text-white',
        border: 'border-gray-500',
        icon: '🔴',
        label: 'ENCERRADA',
        subtexto: badgeData.subtexto || '',
        pulse: false
      }
    };

    const config = configs[status] || configs['ENCERRADA'];
    
    return (
      <div className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg ${config.bg} ${config.text} border ${config.border} font-bold shadow-md ${config.pulse ? 'animate-pulse' : ''}`}>
        <span className="text-sm">{config.icon}</span>
        <span className="text-sm">{config.label}</span>
        {config.subtexto && (
          <span className="text-xs opacity-90 ml-1">• {config.subtexto}</span>
        )}
      </div>
    );
  };

  // Extrair número do edital/processo
  const getNumeroEdital = () => {
    return licitacao.numero_edital || 
           licitacao.numero_processo || 
           licitacao.numero_pregao || 
           licitacao.numero_controle_pncp ||
           licitacao.id_externo || 
           'N/A';
  };

  // Extrair UASG/Código da Unidade (NOVO - v3.3)
  const getUASG = () => {
    return licitacao.uasg || 
           licitacao.codigo_unidade || 
           licitacao.unidade_orgao ||
           licitacao.codigo_orgao ||
           licitacao.orgao_cnpj ||  // CNPJ do órgão como fallback
           null;
  };

  // Extrair modalidade
  const getModalidade = () => {
    return licitacao.tipo_modalidade || 
           licitacao.modalidade || 
           'Não informada';
  };

  /**
   * 🔗 LÓGICA "DIRECT-FIRST" (v4.2 ELITE)
   * 
   * HIERARQUIA DE DOWNLOAD:
   * 
   * PRIORIDADE 1 (Direto): Link final do arquivo (.pdf, .zip, .doc) ou API de arquivos PNCP
   *    → Inicia download imediato
   * 
   * PRIORIDADE 2 (Fallback): Portal visual do PNCP/Órgão
   *    → Só se link direto não disponível
   * 
   * 🆕 v4.2: URLs /pncp-api/.../arquivos/N são LINKS DIRETOS válidos!
   */
  const getLinkEdital = (lic) => {
    // =====================================================================
    // 🆕 v4.2: VERIFICAR SE É LINK DE ARQUIVO PNCP (DOWNLOAD DIRETO)
    // URLs como /pncp-api/v1/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos/{n}
    // retornam o arquivo binário diretamente (não é redirect, é download)
    // =====================================================================
    const isLinkArquivoPNCP = (url) => {
      if (!url) return false;
      return url.match(/\/pncp-api\/v1\/orgaos\/\d+\/compras\/\d+\/\d+\/arquivos\/\d+/);
    };
    
    // =====================================================================
    // 🚫 LINKS BLOQUEADOS (NÃO USAR)
    // =====================================================================
    const isLinkBloqueado = (url) => {
      if (!url) return true;
      
      // 🆕 v4.2: Permitir links de arquivos PNCP (são downloads diretos!)
      if (isLinkArquivoPNCP(url)) {
        return false; // NÃO bloquear - é download direto
      }
      
      const blockedPatterns = [
        '/pncp-api/',           // API do PNCP genérica (exceto arquivos)
        '/api/',                // APIs em geral
        'dados.gov.br',         // Portal de dados abertos
        'conjunto-de-dados',    // URLs de datasets
      ];
      return blockedPatterns.some(pattern => url.includes(pattern));
    };
    
    // =====================================================================
    // ✅ PRIORIDADE 1 (DIRECT-FIRST): Links de arquivo direto
    // =====================================================================
    const isArquivoDireto = (url) => {
      if (!url) return false;
      // 🆕 v4.2: Incluir links de arquivos PNCP como "arquivo direto"
      if (isLinkArquivoPNCP(url)) return true;
      return url.match(/\.(pdf|zip|doc|docx|xls|xlsx|rar|7z)(\?|#|$)/i);
    };
    
    // 1.0 🆕 v4.2 PRIORIDADE MÁXIMA: Link de arquivo PNCP (navegação dupla)
    if (lic.link_edital && isLinkArquivoPNCP(lic.link_edital)) {
      return lic.link_edital;
    }
    
    if (lic.link_documento && isLinkArquivoPNCP(lic.link_documento)) {
      return lic.link_documento;
    }
    
    // 1.1 Verificar link_documento (normalmente é o PDF direto)
    if (lic.link_documento && lic.link_documento.startsWith('http')) {
      if (isArquivoDireto(lic.link_documento) && !isLinkBloqueado(lic.link_documento)) {
        return lic.link_documento;
      }
    }
    
    // 1.2 Verificar link_edital (pode ser PDF direto)
    if (lic.link_edital && lic.link_edital.startsWith('http')) {
      if (isArquivoDireto(lic.link_edital) && !isLinkBloqueado(lic.link_edital)) {
        return lic.link_edital;
      }
    }
    
    // 1.3 Verificar link_sistema_origem (alguns portais dão link direto)
    const urlOrigem = lic.link_sistema_origem || lic.link_origem || '';
    if (urlOrigem && urlOrigem.startsWith('http') && !isLinkBloqueado(urlOrigem)) {
      if (isArquivoDireto(urlOrigem)) {
        return urlOrigem;
      }
    }
    
    // =====================================================================
    // ✅ PRIORIDADE 2 (FALLBACK): Links de portais confiáveis
    // =====================================================================
    const portaisConfiaveis = [
      'comprasnet',
      'licitacoes-e',
      'portaldecompraspublicas',
      'bll.org.br',
      'bbmnetlicitacoes',
      'licitanet',
      'pregaobanrisul',
      'licitardigital',
      'bnccompras'
    ];
    
    // 2.1 Link de sistema origem (portal confiável)
    if (urlOrigem && urlOrigem.startsWith('http') && !isLinkBloqueado(urlOrigem)) {
      const isPortalConfiavel = portaisConfiaveis.some(p => urlOrigem.toLowerCase().includes(p));
      if (isPortalConfiavel) {
        return urlOrigem;
      }
    }
    
    // 2.2 Link edital (portal confiável)
    if (lic.link_edital && lic.link_edital.startsWith('http')) {
      const isPortalConfiavel = portaisConfiaveis.some(p => lic.link_edital.toLowerCase().includes(p));
      if (isPortalConfiavel && !isLinkBloqueado(lic.link_edital)) {
        return lic.link_edital;
      }
    }
    
    // 2.3 Link PNCP (portal visual /app/)
    if (lic.link_pncp && lic.link_pncp.startsWith('http')) {
      if (lic.link_pncp.includes('/app/') && !isLinkBloqueado(lic.link_pncp)) {
        return lic.link_pncp;
      }
    }
    
    // =====================================================================
    // ✅ PRIORIDADE 3: Construir link do Portal Visual PNCP
    // =====================================================================
    const cnpj = lic.orgao_cnpj || lic.cnpj_orgao || lic.cnpj || lic._pncp_cnpj;
    const ano = lic.ano || lic.ano_compra || lic._pncp_ano;
    const sequencial = lic.numero_sequencial || lic.sequencial_compra || lic._pncp_sequencial;
    
    if (cnpj && ano && sequencial) {
      const cnpjLimpo = String(cnpj).replace(/\D/g, '');
      return `https://pncp.gov.br/app/editais/${cnpjLimpo}/${ano}/${sequencial}`;
    }
    
    // =====================================================================
    // ✅ FALLBACK FINAL: Busca no portal PNCP
    // =====================================================================
    const query = lic.numero_controle_pncp || lic.numero_processo || lic.numero_edital || lic.fonte_id || '';
    if (query) {
      return `https://pncp.gov.br/app/editais?q=${encodeURIComponent(query)}`;
    }
    
    return 'https://pncp.gov.br/app/editais';
  };
  
  // 🆕 v4.2 ELITE: Detectar se é download direto ou portal
  const isDownloadDireto = (url) => {
    if (!url) return false;
    // Links de arquivos PNCP são downloads diretos
    if (url.match(/\/pncp-api\/v1\/orgaos\/\d+\/compras\/\d+\/\d+\/arquivos\/\d+/)) {
      return true;
    }
    return url.match(/\.(pdf|zip|doc|docx|xls|xlsx|rar|7z)(\?|#|$)/i);
  };

  // Verificar se link é direto para download (PDF/ZIP) ou portal externo
  const isLinkDownloadDireto = () => {
    const link = getLinkEdital(licitacao);
    // É download direto se termina em .pdf ou .zip
    return link.match(/\.(pdf|zip)(\?|$)/i) !== null;
  };

  // Formatar data
  const formatarData = (data) => {
    if (!data) return 'N/A';
    try {
      const date = new Date(data);
      if (isNaN(date.getTime())) return 'N/A';
      return date.toLocaleDateString('pt-BR', { 
        day: '2-digit', 
        month: '2-digit', 
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return 'N/A';
    }
  };

  // Formatar data curta (sem hora)
  const formatarDataCurta = (data) => {
    if (!data) return 'N/A';
    try {
      const date = new Date(data);
      if (isNaN(date.getTime())) return 'N/A';
      return date.toLocaleDateString('pt-BR', { 
        day: '2-digit', 
        month: '2-digit', 
        year: 'numeric'
      });
    } catch {
      return 'N/A';
    }
  };

  // Badge de fonte/portal (OBRIGATÓRIO v3.3)
  const getFonteBadge = (fonte) => {
    const f = (fonte || '').toLowerCase();
    let cor = 'bg-gray-500';
    let texto = fonte || 'Portal';
    
    if (f.includes('pncp')) { cor = 'bg-purple-600'; texto = 'PNCP'; }
    else if (f.includes('comprasnet')) { cor = 'bg-blue-600'; texto = 'ComprasNet'; }
    else if (f.includes('bnc')) { cor = 'bg-orange-600'; texto = 'BNC'; }
    else if (f.includes('licitanet')) { cor = 'bg-cyan-600'; texto = 'Licitanet'; }
    else if (f.includes('municipal')) { cor = 'bg-teal-600'; texto = 'Municipal'; }
    else if (f.includes('estadual')) { cor = 'bg-emerald-600'; texto = 'Estadual'; }
    
    return (
      <span className={`${cor} text-white text-xs px-2 py-0.5 rounded font-medium`}>
        {texto}
      </span>
    );
  };

  // Verificar se link é válido
  const isLinkValido = licitacao.link_status === 'VALIDO' || 
                       Boolean(licitacao.arquivos_disponiveis?.length) ||
                       (licitacao.link_edital && !licitacao.link_edital.includes('?q='));

  // Obter itens (prioridade: itens_correspondentes > itens_edital)
  // 🛡️ v3.3: Garantir fallback correto quando array está vazio
  const getItens = () => {
    const itensCorrespondentes = licitacao.itens_correspondentes;
    const itensEdital = licitacao.itens_edital;
    
    // Se itens_correspondentes existe e tem elementos, usar ele
    if (Array.isArray(itensCorrespondentes) && itensCorrespondentes.length > 0) {
      return itensCorrespondentes;
    }
    
    // Fallback para itens_edital
    if (Array.isArray(itensEdital) && itensEdital.length > 0) {
      return itensEdital;
    }
    
    return [];
  };

  const itens = getItens();
  const uasg = getUASG();
  
  // v4.0: Verificar se há itens com match confirmado
  const temItemConfirmado = itens.some(item => item.termo_match || item.match_encontrado);

  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-sm hover:shadow-md transition-shadow mb-4 overflow-hidden">
      {/* 🎯 BARRA SUPERIOR - STATUS DE OPORTUNIDADE V3 */}
      <div className={`px-4 py-2 flex items-center justify-between ${
        licitacao.status_oportunidade === 'ATIVA' && licitacao.is_credenciamento ? 'bg-blue-50 border-b border-blue-200' :
        licitacao.status_oportunidade === 'ATIVA' ? 'bg-green-50 border-b border-green-200' :
        licitacao.status_oportunidade === 'FUTURA' ? 'bg-yellow-50 border-b border-yellow-200' :
        'bg-gray-50 border-b border-gray-200'
      }`}>
        {/* Badge de status */}
        {getStatusOportunidadeBadge()}
        
        {/* Info adicional */}
        <div className="flex items-center gap-3 flex-wrap">
          {/* 🛡️ v4.0 ELITE: Badge "RESULTADO CONFIRMADO" quando tem item confirmado */}
          {temItemConfirmado && (
            <div className="flex items-center gap-1 text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-100 text-xs font-black uppercase">
              <CheckCircle size={14} />
              <span>RESULTADO CONFIRMADO</span>
            </div>
          )}
          
          {/* 🔒 P3: AVISO DE AUDITORIA */}
          {licitacao.audit_warning && (
            <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium ${
              licitacao.audit_warning.cor === 'yellow' 
                ? 'bg-amber-100 text-amber-800 border border-amber-300' 
                : licitacao.audit_warning.cor === 'blue'
                ? 'bg-blue-100 text-blue-800 border border-blue-300'
                : licitacao.audit_warning.cor === 'red'
                ? 'bg-red-100 text-red-800 border border-red-300'
                : 'bg-gray-100 text-gray-700 border border-gray-300'
            }`}>
              <span>{licitacao.audit_warning.emoji}</span>
              <span>{licitacao.audit_warning.texto}</span>
            </div>
          )}
          
          {/* 🔒 P3: QUALITY SCORE */}
          {licitacao.quality_score !== undefined && (
            <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg font-bold text-xs ${
              licitacao.quality_level === 'ALTA' 
                ? 'bg-emerald-500 text-white' 
                : licitacao.quality_level === 'MEDIA'
                ? 'bg-amber-400 text-amber-900'
                : 'bg-red-300 text-red-900'
            }`}>
              <span>🔒</span>
              <span>Q: {licitacao.quality_score}</span>
            </div>
          )}
          
          {/* Dias até abertura/vigência */}
          {licitacao.dias_ate_abertura !== null && licitacao.status_oportunidade !== 'ENCERRADA' && (
            <div className="flex items-center gap-1 text-sm text-gray-600">
              <Clock size={14} />
              <span className="font-medium">
                {licitacao.is_credenciamento ? (
                  licitacao.dias_ate_abertura > 0 ? `Vigente` : 'Último dia!'
                ) : (
                  licitacao.dias_ate_abertura === 0 ? 'Hoje!' :
                  licitacao.dias_ate_abertura === 1 ? 'Amanhã' :
                  `${licitacao.dias_ate_abertura} dias`
                )}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* CONTEÚDO PRINCIPAL */}
      <div 
        className="p-4 cursor-pointer"
        onClick={() => setExpandido(!expandido)}
      >
        <div className="flex items-start justify-between gap-4">
          {/* Coluna esquerda: Info principal */}
          <div className="flex-1 min-w-0">
            {/* 🎯 LINHA 1: IDENTIFICAÇÃO (Portal, UASG, Número) - v3.3 OBRIGATÓRIO */}
            <div className="flex items-center gap-2 mb-3 flex-wrap">
              {/* Portal de Origem */}
              {getFonteBadge(licitacao.fonte)}
              
              {/* UASG/Código da Unidade (v3.3) */}
              {uasg && (
                <div className="flex items-center gap-1 bg-gray-100 text-gray-700 px-2 py-1 rounded text-xs border border-gray-300">
                  <span className="font-medium">UASG:</span>
                  <span className="font-bold">{uasg}</span>
                </div>
              )}
              
              {/* Número do Edital/Processo */}
              <div className="flex items-center gap-1.5 bg-indigo-100 text-indigo-800 px-3 py-1.5 rounded-lg border border-indigo-200">
                <Hash size={14} className="text-indigo-600" />
                <span className="font-bold text-sm">{getNumeroEdital()}</span>
              </div>
              
              {/* Modalidade */}
              <div className="flex items-center gap-1.5 bg-blue-100 text-blue-800 px-2 py-1 rounded border border-blue-200">
                <FileText size={12} className="text-blue-600" />
                <span className="font-medium text-xs">{getModalidade()}</span>
              </div>

              {licitacao.esfera && (
                <span className="text-xs text-gray-600 bg-gray-100 px-2 py-1 rounded">
                  {licitacao.esfera}
                </span>
              )}
            </div>

            {/* 🎯 LINHA 2: LOCALIZAÇÃO (Cidade + UF) - v3.3 OBRIGATÓRIO */}
            <div className="flex items-center gap-2 mb-2 text-sm">
              <Building2 size={16} className="text-gray-500 flex-shrink-0" />
              <span className="font-semibold text-gray-900 truncate">
                {licitacao.orgao || licitacao.orgao_licitante || 'Órgão não informado'}
              </span>
              <span className="text-gray-400">|</span>
              <MapPin size={14} className="text-blue-500 flex-shrink-0" />
              <span className="font-bold text-blue-700">
                {licitacao.municipio && licitacao.uf 
                  ? `${licitacao.municipio}/${licitacao.uf}`
                  : licitacao.uf || licitacao.estado || 'N/A'}
              </span>
            </div>

            {/* Linha 3: Objeto (truncado) - 🖍️ COM GRIFO VISUAL v3.7 */}
            <div className="mb-3">
              <p className="text-sm text-gray-700 line-clamp-2 font-medium uppercase">
                <Highlight 
                  text={licitacao.objeto || licitacao.medicamento || 'Objeto não informado'} 
                  highlight={termoBusca} 
                />
              </p>
            </div>

            {/* 🎯 LINHA 4: CRONOGRAMA (Datas) - v3.3 OBRIGATÓRIO */}
            <div className="mb-3 p-3 bg-gradient-to-r from-amber-50 to-orange-50 border-l-4 border-amber-500 rounded-r-lg">
              <div className="flex items-start gap-4 flex-wrap">
                <Calendar size={18} className="text-amber-600 flex-shrink-0 mt-0.5" />
                <div className="flex flex-wrap gap-4 text-sm">
                  {/* Data de Publicação */}
                  <div className="flex flex-col">
                    <span className="text-xs text-gray-500 uppercase font-medium">Publicação</span>
                    <span className="font-semibold text-gray-800">{formatarDataCurta(licitacao.data_publicacao)}</span>
                  </div>
                  
                  {/* Data Inicial (Abertura) */}
                  <div className="flex flex-col">
                    <span className="text-xs text-amber-600 uppercase font-medium">Abertura</span>
                    <span className="font-bold text-amber-800">{formatarData(licitacao.data_abertura)}</span>
                  </div>
                  
                  {/* Data Final (Limite de Propostas) */}
                  {licitacao.data_fim_vigencia && (
                    <div className="flex flex-col">
                      <span className="text-xs text-red-500 uppercase font-medium">Limite</span>
                      <span className="font-semibold text-red-700">{formatarDataCurta(licitacao.data_fim_vigencia)}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
            
            {/* 📦 TABELA DE ITENS (Crucial - Padrão GSM) v3.3 */}
            {itens.length > 0 ? (
              <div className="mt-3 p-3 bg-blue-50 border-l-4 border-blue-500 rounded-r-lg">
                <div className="flex items-center gap-2 mb-2">
                  <Package size={16} className="text-blue-600" />
                  <span className="text-sm font-bold text-blue-800">
                    🎯 Itens que deram match ({itens.length})
                  </span>
                </div>
                <p className="text-xs text-blue-600 mb-2 italic">* Dados extraídos diretamente do edital oficial</p>
                
                {/* Tabela de itens */}
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="bg-blue-100 text-blue-800">
                        <th className="px-2 py-1 text-left font-bold">Nº</th>
                        <th className="px-2 py-1 text-left font-bold">Descrição</th>
                        <th className="px-2 py-1 text-center font-bold">ME/EPP</th>
                        <th className="px-2 py-1 text-right font-bold">Qtd</th>
                        <th className="px-2 py-1 text-right font-bold">Valor Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(mostrarTodosItens ? itens : itens.slice(0, 3)).map((item, idx) => {
                        const numItem = item.numero_item || 'NA';
                        const qtd = item.quantidade || 'NA';
                        const unidade = item.unidade || '';
                        const valorTotal = item.valor_total;
                        const statusMeEpp = item.status_me_epp || item.beneficio_me_epp || item.exclusivo_me_epp;
                        // 🎯 v3.6: Detectar se o item corresponde à busca
                        const isItemEncontrado = item.termo_match || item.match_encontrado;
                        
                        return (
                          <tr key={idx} className={`border-b border-blue-100 transition-colors ${
                            isItemEncontrado 
                              ? 'bg-yellow-50 hover:bg-yellow-100 border-l-8 border-yellow-400' 
                              : 'bg-white hover:bg-blue-50 opacity-60'
                          }`}>
                            <td className={`px-2 py-2 ${isItemEncontrado ? 'text-blue-800' : 'text-slate-400'}`}>
                              <span className={`px-2 py-0.5 rounded text-xs font-bold ${
                                numItem === 'NA' ? 'bg-red-500 text-white' : 'bg-blue-600 text-white'
                              }`}>
                                {numItem}
                              </span>
                            </td>
                            <td className="px-2 py-2">
                              <div className="flex items-center gap-2 flex-wrap">
                                {/* 🖍️ GRIFO VISUAL NA DESCRIÇÃO DO ITEM - v4.0 ELITE */}
                                <span className={`font-medium uppercase ${isItemEncontrado ? 'text-blue-900' : 'text-gray-800'}`}>
                                  <Highlight 
                                    text={(item.descricao || 'Descrição não disponível').substring(0, 120)} 
                                    highlight={termoBusca} 
                                  />
                                  {(item.descricao || '').length > 120 ? '...' : ''}
                                </span>
                                {/* 🏷️ BADGE "CONFIRMADO NO ITEM" v4.0 - Com animação pulse e borda */}
                                {isItemEncontrado && (
                                  <span className="bg-yellow-400 text-black px-2 py-0.5 rounded-full text-[8px] font-black uppercase tracking-wide whitespace-nowrap shadow-sm border border-yellow-500 animate-pulse">
                                    CONFIRMADO NO ITEM
                                  </span>
                                )}
                              </div>
                            </td>
                            <td className="px-2 py-2 text-center">
                              {statusMeEpp ? (
                                <span className="bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded text-xs font-medium">
                                  {typeof statusMeEpp === 'string' ? statusMeEpp : 'SIM'}
                                </span>
                              ) : (
                                <span className="text-gray-400">-</span>
                              )}
                            </td>
                            <td className="px-2 py-2 text-right">
                              <span className={qtd === 'NA' ? 'text-red-600 font-semibold' : 'text-gray-700'}>
                                {qtd === 'NA' ? 'NA' : `${qtd} ${unidade}`}
                              </span>
                            </td>
                            <td className="px-2 py-2 text-right">
                              <span className={!valorTotal || valorTotal === 'NA' ? 'text-red-600 font-semibold' : 'text-green-700 font-bold'}>
                                {!valorTotal || valorTotal === 'NA' 
                                  ? 'NA' 
                                  : `R$ ${parseFloat(valorTotal).toLocaleString('pt-BR', {minimumFractionDigits: 2})}`}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                
                {itens.length > 3 && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setMostrarTodosItens(!mostrarTodosItens);
                    }}
                    className="mt-2 text-xs text-blue-700 hover:text-blue-900 font-medium flex items-center gap-1"
                  >
                    <List size={12} />
                    {mostrarTodosItens 
                      ? 'Mostrar menos' 
                      : `Ver todos os ${itens.length} itens`}
                  </button>
                )}
              </div>
            ) : (
              <div className="mt-3 p-3 bg-amber-50 border-l-4 border-amber-500 rounded-r-lg">
                <div className="flex items-center gap-2">
                  <AlertTriangle size={16} className="text-amber-600" />
                  <span className="text-sm text-amber-800">
                    <strong>Itens não estruturados:</strong> Consulte o PDF do edital para detalhes.
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Coluna direita: Botão Download + Expandir */}
          <div className="flex flex-col items-end gap-2">
            {/* 📥 BOTÃO DOWNLOAD PRINCIPAL (v4.4 ELITE) */}
            {(() => {
              const link = getLinkEdital(licitacao);
              const isDireto = isDownloadDireto(link);
              
              return (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    if (isDireto) {
                      // Download direto
                      const a = document.createElement('a');
                      a.href = link;
                      a.target = '_blank';
                      a.rel = 'noopener noreferrer';
                      document.body.appendChild(a);
                      a.click();
                      document.body.removeChild(a);
                    } else {
                      // Abrir portal
                      window.open(link, '_blank');
                    }
                  }}
                  className={`flex items-center gap-2 px-5 py-3 ${
                    isDireto 
                      ? 'bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700' 
                      : 'bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700'
                  } text-white rounded-xl transition-all font-bold shadow-lg text-sm whitespace-nowrap uppercase tracking-wide`}
                >
                  {isDireto ? (
                    <>
                      <Download size={16} />
                      Baixar Edital
                    </>
                  ) : (
                    <>
                      <ExternalLink size={16} />
                      Ver no Portal
                    </>
                  )}
                </button>
              );
            })()}
            
            {/* 🆕 v4.4: MÚLTIPLOS ARQUIVOS (Edital, TR, ETP, etc.) */}
            {licitacao.arquivos_disponiveis && licitacao.arquivos_disponiveis.length > 1 && (
              <div className="flex flex-wrap gap-1 justify-end">
                {licitacao.arquivos_disponiveis.slice(0, 5).map((arq, idx) => {
                  const tipo = arq.tipo_documento || 'DOC';
                  const cores = {
                    'EDITAL': 'bg-emerald-100 text-emerald-700 border-emerald-300',
                    'TR': 'bg-blue-100 text-blue-700 border-blue-300',
                    'ETP': 'bg-purple-100 text-purple-700 border-purple-300',
                    'MINUTA': 'bg-amber-100 text-amber-700 border-amber-300',
                    'ATA': 'bg-pink-100 text-pink-700 border-pink-300',
                    'ANEXO': 'bg-gray-100 text-gray-600 border-gray-300',
                    'OUTROS': 'bg-slate-100 text-slate-600 border-slate-300'
                  };
                  
                  return (
                    <button
                      key={idx}
                      onClick={(e) => {
                        e.stopPropagation();
                        window.open(arq.url, '_blank');
                      }}
                      className={`px-2 py-1 text-xs font-medium rounded-lg border ${cores[tipo] || cores['OUTROS']} hover:opacity-80 transition-opacity flex items-center gap-1`}
                      title={arq.titulo_original || arq.titulo || tipo}
                    >
                      <Download size={10} />
                      {tipo}
                    </button>
                  );
                })}
                {licitacao.arquivos_disponiveis.length > 5 && (
                  <span className="px-2 py-1 text-xs text-gray-500">
                    +{licitacao.arquivos_disponiveis.length - 5}
                  </span>
                )}
              </div>
            )}

            {/* Badges adicionais */}
            <div className="flex gap-1 flex-wrap justify-end">
              {licitacao.is_saude && (
                <span className="inline-flex items-center px-2 py-0.5 bg-emerald-100 text-emerald-800 text-xs rounded-full border border-emerald-300">
                  🏥 Saúde
                </span>
              )}
              {licitacao.is_acionavel && (
                <span className="inline-flex items-center px-2 py-0.5 bg-green-100 text-green-800 text-xs rounded-full border border-green-300">
                  ✅ Acionável
                </span>
              )}
            </div>

            {/* Botão expandir/recolher */}
            <button
              className="p-2 hover:bg-gray-100 rounded-full transition-colors"
              onClick={(e) => {
                e.stopPropagation();
                setExpandido(!expandido);
              }}
            >
              {expandido ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
            </button>
          </div>
        </div>

        {/* Tags */}
        {(() => {
          const tags = Array.isArray(licitacao.tags) ? licitacao.tags : [];
          return tags.length > 0 && (
            <div className="flex gap-2 mt-3 flex-wrap">
              {tags.slice(0, 5).map((tag, idx) => (
                <span
                  key={idx}
                  className="inline-flex items-center gap-1 px-2 py-1 bg-indigo-50 text-indigo-700 text-xs rounded-full"
                >
                  <Tag size={10} />
                  {String(tag).replace('_', ' ')}
                </span>
              ))}
              {tags.length > 5 && (
                <span className="text-xs text-gray-400">+{tags.length - 5}</span>
              )}
            </div>
          );
        })()}
      </div>

      {/* DETALHES EXPANDIDOS */}
      {expandido && (
        <div className="border-t border-gray-200 bg-gray-50">
          <div className="p-4 space-y-4">
            {/* Seção: Informações Detalhadas */}
            <div className="bg-white rounded-lg p-4 border border-gray-200">
              <h4 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                <Building2 size={18} className="text-blue-600" />
                Informações Completas da Licitação
              </h4>
              
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 text-sm">
                <div className="bg-gray-50 p-2 rounded">
                  <span className="text-gray-500 text-xs block">Portal de Origem</span>
                  <span className="font-semibold text-gray-900">{licitacao.fonte || 'N/A'}</span>
                </div>
                
                {uasg && (
                  <div className="bg-gray-50 p-2 rounded">
                    <span className="text-gray-500 text-xs block">UASG/Código Unidade</span>
                    <span className="font-bold text-gray-900">{uasg}</span>
                  </div>
                )}
                
                <div className="bg-gray-50 p-2 rounded">
                  <span className="text-gray-500 text-xs block">Número do Processo</span>
                  <span className="font-bold text-gray-900">{getNumeroEdital()}</span>
                </div>
                
                <div className="bg-gray-50 p-2 rounded">
                  <span className="text-gray-500 text-xs block">Modalidade</span>
                  <span className="font-semibold text-gray-900">{getModalidade()}</span>
                </div>
                
                <div className="bg-gray-50 p-2 rounded">
                  <span className="text-gray-500 text-xs block">Status</span>
                  <span className={`font-semibold ${
                    licitacao.status_oportunidade === 'ATIVA' ? 'text-green-600' :
                    licitacao.status_oportunidade === 'FUTURA' ? 'text-yellow-600' :
                    'text-gray-600'
                  }`}>
                    {licitacao.status_oportunidade || 'N/A'}
                  </span>
                </div>
                
                <div className="bg-blue-50 p-2 rounded border border-blue-200">
                  <span className="text-blue-500 text-xs block">Localização</span>
                  <span className="font-bold text-blue-900">
                    {licitacao.municipio && licitacao.uf 
                      ? `${licitacao.municipio}/${licitacao.uf}`
                      : licitacao.uf || 'N/A'}
                  </span>
                </div>

                {licitacao.data_publicacao && (
                  <div className="bg-gray-50 p-2 rounded">
                    <span className="text-gray-500 text-xs block">Data de Publicação</span>
                    <span className="font-medium text-gray-900">{formatarData(licitacao.data_publicacao)}</span>
                  </div>
                )}

                {licitacao.data_abertura && (
                  <div className="bg-amber-50 p-2 rounded border border-amber-200">
                    <span className="text-amber-600 text-xs block">Data de Abertura</span>
                    <span className="font-bold text-amber-900">{formatarData(licitacao.data_abertura)}</span>
                  </div>
                )}
                
                {licitacao.data_fim_vigencia && (
                  <div className="bg-red-50 p-2 rounded border border-red-200">
                    <span className="text-red-500 text-xs block">Data Final/Limite</span>
                    <span className="font-semibold text-red-900">{formatarData(licitacao.data_fim_vigencia)}</span>
                  </div>
                )}
                
                {licitacao.cnpj_orgao && (
                  <div className="bg-gray-50 p-2 rounded">
                    <span className="text-gray-500 text-xs block">CNPJ Órgão</span>
                    <span className="font-medium text-gray-900">{licitacao.cnpj_orgao}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Seção: Objeto */}
            {licitacao.objeto && (
              <div className="bg-white rounded-lg p-4 border border-gray-200">
                <h4 className="font-semibold text-gray-900 mb-2">📄 Objeto da Licitação</h4>
                <p className="text-sm text-gray-700 leading-relaxed">
                  {licitacao.objeto}
                </p>
              </div>
            )}

            {/* Seção: Arquivos Disponíveis */}
            {licitacao.arquivos_disponiveis && licitacao.arquivos_disponiveis.length > 0 && (
              <div className="bg-white rounded-lg p-4 border border-gray-200">
                <h4 className="font-semibold text-gray-900 mb-3">📎 Arquivos Disponíveis ({licitacao.arquivos_disponiveis.length})</h4>
                <div className="space-y-2">
                  {licitacao.arquivos_disponiveis.map((arquivo, idx) => (
                    <a
                      key={idx}
                      href={arquivo.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-2 p-2 bg-gray-50 hover:bg-gray-100 rounded border border-gray-200 transition-colors"
                    >
                      <Download size={16} className="text-green-600" />
                      <span className="text-sm text-gray-800 flex-1">{arquivo.titulo || arquivo.nome || `Arquivo ${idx + 1}`}</span>
                      <ExternalLink size={14} className="text-gray-400" />
                    </a>
                  ))}
                </div>
              </div>
            )}

            {/* Seção: Ações (Botões) */}
            <div className="flex gap-3 flex-wrap">
              <button
                onClick={() => window.open(getLinkEdital(licitacao), '_blank')}
                className="flex-1 min-w-[200px] inline-flex items-center justify-center gap-2 px-4 py-4 bg-gradient-to-r from-emerald-600 to-green-600 text-white rounded-xl hover:from-emerald-700 hover:to-green-700 transition-colors font-bold shadow-lg uppercase text-sm"
              >
                <Download size={18} />
                Baixar Edital no Portal
              </button>
              
              <a
                href={getLinkEdital(licitacao)}
                target="_blank"
                rel="noopener noreferrer"
                className="flex-1 min-w-[200px] inline-flex items-center justify-center gap-2 px-4 py-4 bg-white text-slate-600 border-2 border-slate-200 rounded-xl hover:bg-slate-50 transition-colors font-bold uppercase text-sm"
              >
                <ExternalLink size={18} />
                Página do Processo
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
