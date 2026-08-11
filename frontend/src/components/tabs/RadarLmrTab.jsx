import React, { useEffect } from 'react';
import { Loader2, Search, Building2, CheckCircle, Target, DollarSign, AlertTriangle, X, FileDown } from 'lucide-react';
import { BidCard } from '../common/BidCard';

const API_BASE = process.env.REACT_APP_BACKEND_URL;

export function RadarLmrTab({
  // Deep-link de e-mails antigos (alertas de oportunidade tributaria ja
  // enviados antes desta aba virar busca do Ministerio da Saude) - mantido
  // para nao quebrar links ja enviados.
  alertaAberto, alertaLoading, fecharAlerta,
  // Busca (mesma infraestrutura da aba Pesquisa)
  searchTerm, setSearchTerm, results, setResults, isLoading, totalResults, avisoFonte,
  expandedItens, setExpandedItens, getBidDownloadUrl,
  filtroMinisterioSaude, setFiltroMinisterioSaude, executarBusca,
}) {
  // Ao abrir a aba, ativa o escopo Ministerio da Saude e carrega tudo
  // automaticamente (mesmo sem termo digitado).
  useEffect(() => {
    if (!filtroMinisterioSaude) setFiltroMinisterioSaude(true);
    executarBusca('', '', '', false, 1, true);
  }, []);

  const handleBuscar = () => {
    executarBusca(searchTerm, '', '', false, 1, true);
  };

  return (
    <div className="space-y-6" data-testid="radar-lmr-tab">
      {/* Alerta do Email (deep-link antigo) */}
      {alertaLoading && (
        <div className="text-center py-10 bg-white rounded-2xl shadow-lg border-2 border-emerald-200">
          <Loader2 size={40} className="animate-spin text-emerald-500 mx-auto mb-3"/>
          <p className="text-slate-600 font-bold text-sm">Carregando analise da oportunidade...</p>
        </div>
      )}
      {alertaAberto && !alertaLoading && (
        <AlertaEmailPanel data={alertaAberto} onClose={fecharAlerta} />
      )}

      {/* Header */}
      <div>
        <h2 className="text-2xl font-black text-slate-800 uppercase tracking-tight flex items-center gap-3">
          <Building2 size={28} className="text-teal-600"/> MINISTÉRIO DA SAÚDE
        </h2>
        <p className="text-slate-400 text-xs font-medium mt-1">
          Licitações, pregões, dispensas e inexigibilidades do Ministério da Saúde e unidades vinculadas (DLOG, INCA, DSEIs/SESAI)
        </p>
      </div>

      {/* Busca */}
      <div className="bg-white rounded-2xl shadow-lg border-2 border-teal-100 p-4" data-testid="ministerio-saude-busca">
        <div className="flex gap-2 flex-wrap">
          <div className="relative flex-1 min-w-[240px]">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={18}/>
            <input type="text" data-testid="ministerio-saude-busca-input"
              value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleBuscar()}
              placeholder="Filtrar por medicamento/objeto (ex: insulina)..."
              className="w-full pl-11 pr-4 py-3 bg-slate-50 border-2 border-slate-200 rounded-xl text-sm font-semibold text-slate-700 placeholder:text-slate-300 focus:border-teal-400 focus:ring-2 focus:ring-teal-100 outline-none transition-all"
            />
          </div>
          <button data-testid="ministerio-saude-buscar-btn" onClick={handleBuscar} disabled={isLoading}
            className="px-6 py-3 bg-teal-600 text-white rounded-xl font-black text-sm uppercase hover:bg-teal-700 disabled:opacity-50 transition-all flex items-center gap-2">
            {isLoading ? <Loader2 size={16} className="animate-spin"/> : <Search size={16}/>}
            {isLoading ? 'Buscando...' : 'Pesquisar'}
          </button>
        </div>
      </div>

      {/* Aviso de instabilidade da fonte */}
      {avisoFonte && (
        <div className="flex items-center gap-3 bg-amber-50 border-2 border-amber-200 text-amber-800 px-5 py-4 rounded-2xl text-sm font-bold">
          <AlertTriangle size={20} className="shrink-0 text-amber-500"/>
          {avisoFonte}
        </div>
      )}

      {/* Contador */}
      {!isLoading && results.length > 0 && (
        <p className="text-sm font-bold text-slate-600 px-2">
          <CheckCircle size={16} className="inline mr-2 text-emerald-500"/>
          <span className="text-2xl font-black text-slate-800">{totalResults}</span> processo(s) encontrado(s)
        </p>
      )}

      {/* Resultados */}
      <div className="space-y-4">
        {isLoading ? (
          <div className="py-20 text-center">
            <Loader2 className="animate-spin mx-auto text-teal-500 mb-4" size={48}/>
            <p className="text-slate-400 font-bold uppercase tracking-wider">Buscando no Ministério da Saúde...</p>
            <p className="text-xs text-slate-300 mt-2">PNCP - Compras.gov.br</p>
          </div>
        ) : results.length > 0 ? (
          results.map(bid => (
            <BidCard
              key={bid.id} bid={bid} searchTerm={searchTerm}
              expandedItens={expandedItens} setExpandedItens={setExpandedItens}
              setResults={setResults} getBidDownloadUrl={getBidDownloadUrl}
            />
          ))
        ) : (
          <div className="py-20 text-center text-slate-300 border-2 border-dashed border-slate-200 rounded-3xl">
            <Building2 size={48} className="mx-auto mb-4 opacity-50"/>
            <p className="font-black uppercase tracking-wider text-sm">Nenhum processo encontrado</p>
            <p className="text-xs mt-2">Tente outro termo ou aguarde alguns instantes e tente de novo.</p>
          </div>
        )}
      </div>
    </div>
  );
}

function TributoBadge({ label, value, highlight }) {
  return (
    <div className={`rounded-lg px-3 py-2 border ${highlight ? 'bg-red-50 border-red-200' : 'bg-slate-50 border-slate-200'}`}>
      <p className={`text-[10px] font-bold uppercase ${highlight ? 'text-red-400' : 'text-slate-400'}`}>{label}</p>
      <p className={`text-sm font-black ${highlight ? 'text-red-700' : 'text-slate-700'}`}>{value}</p>
    </div>
  );
}

// Mantido para links de e-mail de oportunidade tributaria enviados antes
// desta aba virar a busca do Ministerio da Saude - so renderiza via
// deep-link (?alerta=ID), nao faz parte do fluxo novo.
function AlertaEmailPanel({ data, onClose }) {
  const alerta = data.alerta || {};
  const analise = data.analise_lmr;
  const pdfUrl = data.pdf_url ? `${API_BASE}${data.pdf_url}` : null;
  const score = alerta.oportunidade_score || analise?.oportunidade_score || 0;
  const classif = analise?.classificacao_lmr || {};
  const trib = analise?.estrategia_tributaria || {};
  const hasAnalise = !!analise && !alerta.erro;

  return (
    <div className="bg-white rounded-2xl shadow-2xl border-2 border-emerald-400 overflow-hidden" data-testid="alerta-email-panel">
      {/* Header dourado/verde */}
      <div className="bg-gradient-to-r from-amber-500 via-emerald-500 to-teal-500 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3 text-white">
          <div className="bg-white/20 p-2 rounded-xl">
            <Target size={24}/>
          </div>
          <div>
            <h3 className="font-black text-lg uppercase tracking-wide">{alerta.medicamento || 'Oportunidade LMR'}</h3>
            <p className="text-white/80 text-xs font-medium">Alerta de Oportunidade via E-mail (histórico)</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="bg-white/20 text-white px-4 py-1.5 rounded-full text-lg font-black">{score}%</span>
          <button onClick={onClose} data-testid="fechar-alerta-panel" className="text-white/70 hover:text-white transition-colors p-1">
            <X size={22}/>
          </button>
        </div>
      </div>

      <div className="p-6 space-y-5">
        {/* Dados do Alerta (fallback seguro) */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="bg-emerald-50 border border-emerald-200 rounded-xl px-4 py-3">
            <p className="text-[10px] font-bold text-emerald-400 uppercase">Score</p>
            <p className="text-2xl font-black text-emerald-700">{score}%</p>
          </div>
          <div className="bg-purple-50 border border-purple-200 rounded-xl px-4 py-3">
            <p className="text-[10px] font-bold text-purple-400 uppercase">Categoria LMR</p>
            <p className="text-sm font-black text-purple-700 uppercase">{alerta.categoria_lmr || classif.categoria || 'N/A'}</p>
          </div>
          <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3">
            <p className="text-[10px] font-bold text-red-400 uppercase">Carga Tributaria</p>
            <p className="text-sm font-black text-red-700">{alerta.carga_tributaria || trib.carga_tributaria_total || 'N/A'}%</p>
          </div>
          <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3">
            <p className="text-[10px] font-bold text-blue-400 uppercase">Beneficio</p>
            <p className="text-xs font-bold text-blue-700">{alerta.beneficio || classif.beneficio_tributario || 'N/A'}</p>
          </div>
        </div>

        {/* Analise LMR completa (se disponivel) */}
        {hasAnalise && (
          <>
            <div>
              <h4 className="text-xs font-black text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-2">
                <DollarSign size={14}/> Estrategia Tributaria Detalhada
              </h4>
              <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
                <TributoBadge label="II" value={`${trib.imposto_importacao || 0}%`} />
                <TributoBadge label="ICMS" value={`${trib.icms || 0}%`} />
                <TributoBadge label="PIS" value={`${trib.pis || 0}%`} />
                <TributoBadge label="COFINS" value={`${trib.cofins || 0}%`} />
                <TributoBadge label="Carga Total" value={`${trib.carga_tributaria_total || 0}%`} highlight />
                <TributoBadge label="Margem Dist." value={`${trib.margem_distribuidora || 0}%`} />
              </div>
              {trib.beneficio && (
                <p className="text-xs text-emerald-700 font-bold mt-2">{trib.beneficio}</p>
              )}
            </div>

            <div className="bg-slate-50 border border-slate-200 rounded-xl px-4 py-3">
              <p className="text-[10px] font-bold text-slate-400 uppercase mb-1">Classificacao</p>
              <p className="text-xs text-slate-600">{classif.descricao}</p>
            </div>
          </>
        )}

        {/* Recomendacao */}
        <div className={`rounded-xl px-4 py-3 border-2 ${
          score >= 80 ? 'bg-emerald-50 border-emerald-300' : score >= 50 ? 'bg-amber-50 border-amber-300' : 'bg-slate-50 border-slate-300'
        }`}>
          <p className={`text-sm font-bold ${
            score >= 80 ? 'text-emerald-800' : score >= 50 ? 'text-amber-800' : 'text-slate-600'
          }`}>{alerta.recomendacao || analise?.recomendacao || 'Analise indisponivel'}</p>
        </div>

        {/* Fallback: dados basicos se analise falhou */}
        {!hasAnalise && !alerta.erro && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3">
            <p className="text-xs text-amber-700 font-bold">Analise completa indisponivel. Dados exibidos sao do alerta salvo no sistema.</p>
          </div>
        )}
        {alerta.erro && (
          <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3">
            <p className="text-xs text-red-700 font-bold">Alerta nao encontrado ou expirado. Verifique se o link esta correto.</p>
          </div>
        )}

        {/* Botoes de acao */}
        <div className="flex gap-3 pt-2">
          {pdfUrl && (
            <a href={pdfUrl} target="_blank" rel="noopener noreferrer" data-testid="baixar-prova-pdf"
              className="flex items-center gap-2 px-5 py-3 bg-emerald-600 text-white rounded-xl font-black text-sm hover:bg-emerald-700 transition-all shadow-lg">
              <FileDown size={18}/> Baixar Prova Documental PDF
            </a>
          )}
          <button onClick={onClose}
            className="flex items-center gap-2 px-5 py-3 bg-slate-200 text-slate-700 rounded-xl font-bold text-sm hover:bg-slate-300 transition-all">
            Fechar
          </button>
        </div>
      </div>
    </div>
  );
}
