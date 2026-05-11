import React from 'react';
import { FileText, X, ExternalLink, Shield, Building, Loader2, AlertCircle, CheckCircle, AlertTriangle, Zap, Copy } from 'lucide-react';
import { toast } from 'sonner';

export function EsclarecimentoModal({
  esclarecimentoModal, setEsclarecimentoModal,
  esclarecimentoAlerta,
  esclarecimentoEmpresa, setEsclarecimentoEmpresa,
  esclarecimentoTexto,
  esclarecimentoGerando,
  vigenciaValidacao, vigenciaLoading,
  vigenciaBloqueio,
  vigenciaForceGenerate, setVigenciaForceGenerate,
  gerarEsclarecimento,
  companies,
}) {
  if (!esclarecimentoModal || !esclarecimentoAlerta) return null;

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4" data-testid="esclarecimento-modal">
      <div className="bg-white rounded-3xl shadow-2xl w-full max-w-3xl max-h-[90vh] overflow-auto">
        <div className="p-8 space-y-6">
          {/* Header */}
          <div className="flex justify-between items-start">
            <div>
              <h2 className="text-xl font-black text-slate-800 uppercase flex items-center gap-3">
                <FileText size={24} className="text-purple-600"/> Gerar Esclarecimento
              </h2>
              <p className="text-sm text-slate-500 mt-1">Texto tecnico para informar orgao publico sobre desabastecimento</p>
            </div>
            <button onClick={() => setEsclarecimentoModal(false)} className="text-slate-400 hover:text-slate-600"><X size={28}/></button>
          </div>

          {/* Medicamento info */}
          <div className="bg-red-50 p-4 rounded-2xl border border-red-200">
            <p className="text-xs font-bold text-red-400 uppercase mb-1">Medicamento em Desabastecimento</p>
            <p className="text-lg font-black text-slate-800 uppercase">{esclarecimentoAlerta.medicamento_detectado || esclarecimentoAlerta.medicamento}</p>
            {esclarecimentoAlerta.principio_ativo && <p className="text-sm text-blue-700 font-semibold">PA: {esclarecimentoAlerta.principio_ativo}</p>}
            <p className="text-sm text-slate-600 mt-1">{esclarecimentoAlerta.situacao}</p>
            {esclarecimentoAlerta.link && (
              <a href={esclarecimentoAlerta.link} target="_blank" rel="noopener noreferrer"
                className="text-xs text-blue-600 hover:underline mt-1 inline-flex items-center gap-1">
                <ExternalLink size={12}/> Publicacao oficial
              </a>
            )}
          </div>

          {/* Empresa */}
          <div>
            <label className="text-sm font-black text-slate-500 uppercase flex items-center gap-2 mb-2"><Building size={16}/> Empresa Proponente</label>
            <select data-testid="esclarecimento-empresa-select" value={esclarecimentoEmpresa}
              onChange={(e) => setEsclarecimentoEmpresa(e.target.value)}
              className="w-full py-3 px-4 border-2 rounded-xl focus:border-purple-500 outline-none font-semibold">
              <option value="">Selecione uma empresa...</option>
              {companies.filter(c => c.name).map(c => <option key={c.id} value={c.id}>{c.name} - {c.cnpj}</option>)}
            </select>
          </div>

          {/* DAMA Vigencia Panel */}
          <VigenciaPanel
            vigenciaLoading={vigenciaLoading}
            vigenciaValidacao={vigenciaValidacao}
            vigenciaBloqueio={vigenciaBloqueio}
            vigenciaForceGenerate={vigenciaForceGenerate}
            setVigenciaForceGenerate={setVigenciaForceGenerate}
          />

          {/* Gerar button */}
          <button data-testid="esclarecimento-gerar-btn" onClick={gerarEsclarecimento}
            disabled={esclarecimentoGerando || !esclarecimentoEmpresa || vigenciaLoading || (vigenciaBloqueio && !vigenciaForceGenerate)}
            className={`w-full py-4 rounded-xl font-black uppercase flex items-center justify-center gap-3 transition-all ${
              vigenciaBloqueio && !vigenciaForceGenerate
                ? 'bg-red-200 text-red-500 cursor-not-allowed'
                : 'bg-purple-600 text-white hover:bg-purple-700 disabled:opacity-50'
            }`}>
            {esclarecimentoGerando ? (<><Loader2 size={20} className="animate-spin"/> Gerando com IA + DAMA...</>)
              : vigenciaBloqueio && !vigenciaForceGenerate ? (<><Shield size={20}/> Bloqueado - Marque a caixa para prosseguir</>)
              : (<><Zap size={20}/> Gerar Texto de Esclarecimento</>)
            }
          </button>

          {/* Texto gerado */}
          {esclarecimentoTexto && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-sm font-black text-emerald-600 uppercase flex items-center gap-2"><CheckCircle size={16}/> Esclarecimento Gerado</p>
                <button data-testid="esclarecimento-copiar-btn"
                  onClick={() => { navigator.clipboard.writeText(esclarecimentoTexto); toast.success('Texto copiado!'); }}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg text-xs font-bold hover:bg-blue-700 flex items-center gap-1">
                  <Copy size={14}/> Copiar Texto
                </button>
              </div>
              <div className="bg-slate-50 p-6 rounded-2xl border border-slate-200 max-h-96 overflow-auto">
                <pre className="text-sm text-slate-700 whitespace-pre-wrap font-sans leading-relaxed" data-testid="esclarecimento-texto">{esclarecimentoTexto}</pre>
              </div>
              {esclarecimentoAlerta.link && (
                <div className="bg-amber-50 p-4 rounded-xl border border-amber-200">
                  <p className="text-xs font-bold text-amber-700 uppercase mb-1">Prova Documental (anexar ao processo)</p>
                  <a href={esclarecimentoAlerta.link} target="_blank" rel="noopener noreferrer"
                    className="text-sm text-blue-700 hover:underline font-semibold flex items-center gap-1">
                    <ExternalLink size={14}/> {esclarecimentoAlerta.link}
                  </a>
                </div>
              )}
            </div>
          )}

          <button onClick={() => setEsclarecimentoModal(false)}
            className="w-full py-3 bg-slate-200 text-slate-600 rounded-xl font-bold uppercase hover:bg-slate-300">Fechar</button>
        </div>
      </div>
    </div>
  );
}

function VigenciaPanel({ vigenciaLoading, vigenciaValidacao, vigenciaBloqueio, vigenciaForceGenerate, setVigenciaForceGenerate }) {
  return (
    <div data-testid="dama-vigencia-panel" className="rounded-2xl border-2 overflow-hidden">
      <div className={`px-4 py-3 flex items-center justify-between ${
        vigenciaLoading ? 'bg-slate-50 border-slate-200' :
        vigenciaBloqueio ? 'bg-red-50 border-red-300' :
        vigenciaValidacao ? 'bg-emerald-50 border-emerald-300' : 'bg-slate-50 border-slate-200'
      }`}>
        <div className="flex items-center gap-2">
          <Shield size={18} className={vigenciaLoading ? 'text-slate-400 animate-pulse' : vigenciaBloqueio ? 'text-red-600' : vigenciaValidacao ? 'text-emerald-600' : 'text-slate-400'}/>
          <span className="text-sm font-black uppercase tracking-wide">DAMA - Validacao de Vigencia</span>
        </div>
        {vigenciaLoading && <Loader2 size={16} className="animate-spin text-slate-500"/>}
        {!vigenciaLoading && vigenciaValidacao && (
          <span className={`text-xs font-black px-2 py-0.5 rounded-full ${vigenciaBloqueio ? 'bg-red-600 text-white' : 'bg-emerald-600 text-white'}`}>
            {vigenciaBloqueio ? 'BLOQUEIO' : 'APROVADO'}
          </span>
        )}
      </div>

      {vigenciaLoading && <div className="p-4 bg-white text-center"><p className="text-xs text-slate-500">Verificando vigencia das resolucoes CMED...</p></div>}

      {!vigenciaLoading && vigenciaValidacao && (
        <div className="p-4 bg-white space-y-3">
          {vigenciaValidacao.stats && (
            <div className="flex flex-wrap gap-2">
              <span className="px-2 py-1 bg-emerald-100 text-emerald-700 rounded text-xs font-bold">{vigenciaValidacao.stats.vigentes || 0} Vigentes</span>
              <span className="px-2 py-1 bg-amber-100 text-amber-700 rounded text-xs font-bold">{vigenciaValidacao.stats.vigentes_com_alteracoes || 0} Com Alteracoes</span>
              <span className="px-2 py-1 bg-red-100 text-red-700 rounded text-xs font-bold">{vigenciaValidacao.stats.caducas || 0} Caducas</span>
              <span className="px-2 py-1 bg-slate-100 text-slate-600 rounded text-xs font-bold">{vigenciaValidacao.stats.revogadas || 0} Revogadas</span>
            </div>
          )}
          {vigenciaValidacao.validacao?.map((v, i) => (
            <div key={i} data-testid={`vigencia-check-${i}`} className={`flex items-start gap-2 p-2 rounded-lg text-xs ${
              !v.encontrada ? 'bg-slate-50 text-slate-500' : v.pode_usar ? 'bg-emerald-50 text-emerald-800' : 'bg-red-50 text-red-800'
            }`}>
              {!v.encontrada ? <AlertCircle size={14} className="text-slate-400 mt-0.5 flex-shrink-0"/>
                : v.pode_usar ? <CheckCircle size={14} className="text-emerald-600 mt-0.5 flex-shrink-0"/>
                : <AlertTriangle size={14} className="text-red-600 mt-0.5 flex-shrink-0"/>}
              <div>
                <span className="font-bold">{v.referencia_buscada}</span>
                <span className={`ml-2 px-1.5 py-0.5 rounded text-[10px] font-black ${
                  v.status === 'vigente' ? 'bg-emerald-200 text-emerald-800' :
                  v.status === 'vigente com alteracoes' ? 'bg-amber-200 text-amber-800' :
                  v.status === 'caduca' ? 'bg-red-200 text-red-800' :
                  v.status === 'revogada' ? 'bg-red-300 text-red-900' : 'bg-slate-200 text-slate-600'
                }`}>{v.status?.toUpperCase() || 'N/A'}</span>
                {v.alerta && <p className="mt-1 text-[11px] opacity-80">{v.alerta}</p>}
              </div>
            </div>
          ))}
          {vigenciaBloqueio && (
            <div className="bg-red-100 border border-red-300 p-3 rounded-xl space-y-2">
              <p className="text-xs font-bold text-red-800 flex items-center gap-1"><AlertTriangle size={14}/> Normas caducas/revogadas detectadas</p>
              <p className="text-[11px] text-red-700">O sistema identificou normas que nao estao mais vigentes. O texto gerado usara APENAS normas validas, mas recomendamos revisao.</p>
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" data-testid="vigencia-force-checkbox" checked={vigenciaForceGenerate}
                  onChange={(e) => setVigenciaForceGenerate(e.target.checked)}
                  className="w-4 h-4 rounded border-red-300 text-red-600 focus:ring-red-500"/>
                <span className="text-xs font-bold text-red-800">Estou ciente e desejo gerar mesmo assim</span>
              </label>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
