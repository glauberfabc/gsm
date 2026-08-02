import React, { useState } from 'react';
import { Search, Loader2, Shield, RefreshCw, Pill, CheckCircle, AlertCircle, AlertTriangle, X, ExternalLink, FileText, FileDown, ClipboardCheck } from 'lucide-react';

export function AnvisaTab({
  anvisaAlertas, anvisaStats, anvisaLoading,
  anvisaAtualizando, atualizarAnvisa,
  anvisaBuscaTermo, setAnvisaBuscaTermo,
  anvisaBuscaResultados, setAnvisaBuscaResultados,
  anvisaBuscaLoading, buscarMedicamentoAnvisa,
  companies,
  openEsclarecimento,
  setSearchTerm, setActiveTab, executarBusca,
  damaChecklist,
}) {
  return (
    <div className="space-y-6">
      {/* Header + botoes */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-black text-slate-800 uppercase tracking-tight flex items-center gap-3">
            <Shield size={28} className="text-red-500"/> JANELA ANVISA
          </h2>
          <p className="text-slate-400 text-xs font-medium mt-1">Monitora desabastecimento e importacao excepcional | ANVISA + DOU</p>
        </div>
        <div className="flex gap-2">
          <button data-testid="anvisa-atualizar-btn" onClick={atualizarAnvisa} disabled={anvisaAtualizando}
            className="flex items-center gap-2 px-4 py-2.5 bg-red-600 text-white rounded-xl font-bold text-sm hover:bg-red-700 transition-all disabled:opacity-50">
            {anvisaAtualizando ? <Loader2 size={16} className="animate-spin"/> : <RefreshCw size={16}/>}
            {anvisaAtualizando ? 'Coletando...' : 'Atualizar'}
          </button>
        </div>
      </div>

      {/* Campo de Busca */}
      <div className="bg-white rounded-2xl shadow-lg border-2 border-red-100 p-4" data-testid="anvisa-busca-medicamento">
        <div className="flex items-center gap-2 mb-3">
          <Search size={18} className="text-red-500"/>
          <span className="text-sm font-black text-slate-700 uppercase tracking-wide">Buscar Medicamento</span>
          <span className="text-[10px] text-slate-400 font-medium ml-1">DOU + CMED + Noticias + Legislacao</span>
        </div>
        <div className="flex gap-2">
          <input type="text" data-testid="anvisa-busca-input"
            value={anvisaBuscaTermo} onChange={(e) => setAnvisaBuscaTermo(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && buscarMedicamentoAnvisa()}
            onFocus={() => { if (anvisaBuscaResultados) setAnvisaBuscaTermo(''); }}
            placeholder="Ex: Ravulizumabe, Epidiolex, Denosumabe..."
            className="flex-1 px-4 py-3 bg-slate-50 border-2 border-slate-200 rounded-xl text-sm font-semibold text-slate-700 placeholder:text-slate-300 focus:border-red-400 focus:ring-2 focus:ring-red-100 outline-none transition-all"
          />
          <button data-testid="anvisa-busca-btn" onClick={buscarMedicamentoAnvisa}
            disabled={anvisaBuscaLoading || !anvisaBuscaTermo.trim()}
            className="px-6 py-3 bg-red-600 text-white rounded-xl font-black text-sm uppercase hover:bg-red-700 disabled:opacity-50 transition-all flex items-center gap-2">
            {anvisaBuscaLoading ? <Loader2 size={16} className="animate-spin"/> : <Search size={16}/>}
            {anvisaBuscaLoading ? 'Buscando...' : 'Buscar'}
          </button>
        </div>
      </div>

      {/* Loading */}
      {anvisaBuscaLoading && (
        <div className="text-center py-10 bg-white rounded-2xl shadow border border-slate-100">
          <Loader2 size={36} className="animate-spin text-red-500 mx-auto mb-3"/>
          <p className="text-slate-500 font-bold text-sm">Consultando DOU, CMED, PNCP, Noticias ANVISA, Descontinuacao...</p>
          <p className="text-slate-400 text-xs mt-1">Buscando em 6 fontes oficiais simultaneamente</p>
        </div>
      )}

      {/* Resultados da Busca */}
      {anvisaBuscaResultados && !anvisaBuscaLoading && (
        <SearchResults
          data={anvisaBuscaResultados}
          setAnvisaBuscaResultados={setAnvisaBuscaResultados}
          companies={companies}
          openEsclarecimento={openEsclarecimento}
          damaChecklist={damaChecklist}
        />
      )}

      {/* Resumo compacto */}
      {anvisaStats && <StatsBar stats={anvisaStats} />}

      {/* Lista de Alertas */}
      {anvisaLoading ? (
        <div className="text-center py-16">
          <Loader2 size={40} className="animate-spin text-red-500 mx-auto mb-4"/>
          <p className="text-slate-500 font-bold">Coletando dados ANVISA + DOU...</p>
        </div>
      ) : anvisaAlertas.length > 0 ? (
        <AlertasList
          alertas={anvisaAlertas}
          companies={companies}
          openEsclarecimento={openEsclarecimento}
          setSearchTerm={setSearchTerm}
          setActiveTab={setActiveTab}
          executarBusca={executarBusca}
        />
      ) : (
        <div className="text-center py-16 bg-white rounded-2xl shadow border border-slate-200">
          <Pill size={48} className="text-slate-300 mx-auto mb-4"/>
          <p className="text-slate-500 font-bold text-lg">Nenhum alerta encontrado</p>
          <p className="text-slate-400 text-sm mt-2">Clique em "Atualizar" para coletar dados da ANVISA e DOU</p>
        </div>
      )}
    </div>
  );
}

function SearchResults({ data, setAnvisaBuscaResultados, companies, openEsclarecimento, damaChecklist }) {
  return (
    <div className="bg-white rounded-2xl shadow-lg border border-slate-200 overflow-hidden" data-testid="anvisa-busca-resultados">
      {/* JANELA ABERTA Alert */}
      {data.janela_aberta && (
        <div className="bg-red-600 px-5 py-3 flex items-center gap-3 animate-pulse" data-testid="janela-aberta-alert">
          <AlertTriangle size={20} className="text-white"/>
          <span className="text-white font-black text-sm uppercase">
            JANELA ABERTA DETECTADA - Publicacao oficial (DOU/ANVISA) confirma desabastecimento!
          </span>
        </div>
      )}

      {/* Header */}
      <div className="bg-gradient-to-r from-red-600 to-red-700 px-5 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2 text-white">
          <Pill size={18}/>
          <span className="font-black text-sm uppercase">{data.total} resultado(s) para "{data.medicamento_buscado}"</span>
          <span className="text-white/60 text-[10px] font-medium ml-2">filtro: {data.filtro_temporal || '>=2025'}</span>
        </div>
        <div className="flex items-center gap-2">
          {damaChecklist && (
            <button data-testid="checklist-btn"
              onClick={() => damaChecklist.executarChecklist(data.medicamento_buscado)}
              disabled={damaChecklist.checklistLoading}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-white/20 hover:bg-white/30 text-white rounded-lg text-[11px] font-bold transition-colors disabled:opacity-50">
              {damaChecklist.checklistLoading
                ? <Loader2 size={13} className="animate-spin"/>
                : <ClipboardCheck size={13}/>}
              Checklist DAMA
            </button>
          )}
          <button onClick={() => setAnvisaBuscaResultados(null)} className="text-white/70 hover:text-white transition-colors"><X size={18}/></button>
        </div>
      </div>

      {/* Checklist Panel */}
      {damaChecklist?.checklistResultado && damaChecklist.checklistMedicamento === data.medicamento_buscado && (
        <ChecklistPanel checklist={damaChecklist.checklistResultado} />
      )}

      {/* Fontes */}
      <div className="px-5 py-2 bg-slate-50 border-b border-slate-100 flex flex-wrap gap-2">
        {data.fontes_consultadas?.map((f, i) => (
          <span key={i} className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold ${
            f.status === 'ok' && f.total > 0 ? 'bg-emerald-100 text-emerald-700' :
            f.status === 'ok' ? 'bg-slate-100 text-slate-500' : 'bg-red-100 text-red-600'
          }`}>
            {f.status === 'ok' ? <CheckCircle size={10}/> : <AlertCircle size={10}/>} {f.nome}: {f.total}
          </span>
        ))}
      </div>

      {/* DAMA Analysis */}
      {data.analise_dama?.aviso && (
        <div data-testid="dama-analise-aviso" className={`px-5 py-2 border-b flex items-center gap-2 text-xs font-bold ${
          data.analise_dama.impacto > 0 ? 'bg-emerald-50 border-emerald-200 text-emerald-800' : 'bg-amber-50 border-amber-200 text-amber-800'
        }`}>
          {data.analise_dama.impacto > 0
            ? <CheckCircle size={14} className="text-emerald-600 flex-shrink-0"/>
            : <AlertCircle size={14} className="text-amber-600 flex-shrink-0"/>}
          <span>{data.analise_dama.aviso}</span>
        </div>
      )}

      {/* Results List */}
      {data.total > 0 ? (
        <div className="divide-y divide-slate-100 max-h-[500px] overflow-y-auto">
          {data.resultados.map((r, idx) => (
            <ResultRow key={idx} r={r} idx={idx} medicamentoBuscado={data.medicamento_buscado}
              companies={companies} openEsclarecimento={openEsclarecimento}
              damaChecklist={damaChecklist} />
          ))}
        </div>
      ) : (
        <div className="py-10 text-center">
          <Search size={32} className="text-slate-300 mx-auto mb-2"/>
          <p className="text-slate-500 font-bold">Nenhum resultado encontrado</p>
          <p className="text-slate-400 text-xs mt-1">Tente outro termo ou verifique a grafia</p>
        </div>
      )}
    </div>
  );
}

function ChecklistPanel({ checklist }) {
  if (!checklist) return null;
  const score = checklist.score_conformidade || 0;
  const scoreColor = score >= 75 ? 'emerald' : score >= 25 ? 'amber' : 'red';
  const revogacoes = checklist.revogacoes_detectadas || [];

  return (
    <div className="px-5 py-3 bg-slate-50 border-b-2 border-slate-200" data-testid="checklist-panel">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <ClipboardCheck size={16} className={`text-${scoreColor}-600`}/>
          <span className="text-sm font-black text-slate-700 uppercase">Checklist DAMA - {checklist.medicamento}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`px-3 py-1 rounded-full text-xs font-black bg-${scoreColor}-100 text-${scoreColor}-700`}>
            {score}% Conformidade
          </span>
          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
            score >= 75 ? 'bg-emerald-600 text-white' : score >= 25 ? 'bg-amber-600 text-white' : 'bg-red-600 text-white'
          }`}>
            {checklist.resumo?.aprovados || 0} OK / {checklist.resumo?.alertas || 0} ALERTA / {checklist.resumo?.bloqueios || 0} BLOQUEIO
          </span>
        </div>
      </div>

      {/* REVOGACAO CRUZADA - Alertas de normas obsoletas */}
      {revogacoes.length > 0 && (
        <div className="mb-3 space-y-1.5" data-testid="revogacoes-alert">
          {revogacoes.map((rev, ri) => (
            <div key={ri} data-testid={`revogacao-item-${ri}`}
              className="flex items-start gap-2 px-3 py-2.5 rounded-xl bg-red-100 border-2 border-red-300 text-red-900 text-xs animate-pulse-once">
              <AlertTriangle size={16} className="text-red-600 mt-0.5 flex-shrink-0"/>
              <div className="flex-1">
                <p className="font-black uppercase text-[11px] tracking-wide">
                  Norma Revogada! Utilize a <span className="bg-red-600 text-white px-1.5 py-0.5 rounded font-black">{rev.revogada_por}</span>
                </p>
                <p className="font-semibold mt-0.5 opacity-90">
                  {rev.norma_obsoleta} foi revogada em {rev.data_revogacao}.
                </p>
                {rev.observacao && <p className="text-[10px] mt-0.5 opacity-75">{rev.observacao}</p>}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="space-y-1">
        {checklist.checks?.map((c, i) => (
          <div key={i} data-testid={`checklist-item-${i}`} className={`flex items-start gap-2 px-3 py-1.5 rounded-lg text-xs ${
            c.status === 'ok' ? 'bg-emerald-50 text-emerald-800' :
            c.status === 'alerta' ? 'bg-amber-50 text-amber-800' :
            'bg-red-50 text-red-800'
          }`}>
            {c.status === 'ok' ? <CheckCircle size={14} className="text-emerald-600 mt-0.5 flex-shrink-0"/>
              : c.status === 'alerta' ? <AlertCircle size={14} className="text-amber-600 mt-0.5 flex-shrink-0"/>
              : <AlertTriangle size={14} className="text-red-600 mt-0.5 flex-shrink-0"/>}
            <div className="flex-1">
              <span className="font-bold">{c.item}</span>
              <p className="text-[11px] opacity-80 mt-0.5">{c.detalhe}</p>
              {/* Sugestao de Substituicao inline */}
              {c.sugestao_substituicao && (
                <p data-testid={`sugestao-substituicao-${i}`}
                  className="mt-1 text-[11px] font-black text-red-700 bg-red-200/50 px-2 py-1 rounded inline-block">
                  Substitua por: {c.sugestao_substituicao}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Normas vigentes de referencia */}
      {checklist.normas_vigentes_referencia && (
        <div className="mt-2 px-3 py-2 bg-blue-50 border border-blue-200 rounded-lg" data-testid="normas-vigentes-ref">
          <p className="text-[10px] font-bold text-blue-500 uppercase tracking-wide mb-1">Normas Vigentes de Referencia</p>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(checklist.normas_vigentes_referencia).map(([key, val]) => (
              <span key={key} className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-[10px] font-bold">{val}</span>
            ))}
          </div>
        </div>
      )}

      {checklist.recomendacao && (
        <p className={`mt-2 text-xs font-bold px-3 py-1.5 rounded-lg ${
          score >= 75 ? 'bg-emerald-100 text-emerald-800' : score >= 25 ? 'bg-amber-100 text-amber-800' : 'bg-red-100 text-red-800'
        }`}>{checklist.recomendacao}</p>
      )}
    </div>
  );
}

function ResultRow({ r, idx, medicamentoBuscado, companies, openEsclarecimento, damaChecklist }) {
  return (
    <div data-testid={`busca-resultado-${idx}`} className={`px-5 py-3 hover:bg-slate-50 transition-colors ${
      r.indicador_mercado ? 'bg-amber-50 border-l-4 border-amber-500' : ''
    }`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            {/* INDICADOR PNCP badge com tooltip */}
            {r.indicador_mercado && (
              <span className="relative group cursor-help">
                <span className="px-2 py-0.5 rounded text-[10px] font-black bg-amber-600 text-white" data-testid={`indicador-pncp-badge-${idx}`}>
                  INDICADOR PNCP
                </span>
                <span className="absolute bottom-full left-0 mb-2 w-72 p-2.5 rounded-lg bg-slate-900 text-white text-[11px] leading-relaxed font-medium shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50 pointer-events-none">
                  Indicador de mercado (PNCP). Nao constitui respaldo legal para justificar importacao. Apenas publicacoes oficiais do <strong className="text-amber-400">DOU</strong>, <strong className="text-amber-400">ANVISA</strong> ou <strong className="text-amber-400">CMED</strong> tem validade juridica para fundamentar pedidos de participacao com produtos importados.
                </span>
              </span>
            )}
            {r.tag_recente && <span className="px-2 py-0.5 rounded text-[10px] font-black bg-emerald-600 text-white">RECENTE</span>}
            {r.classificacao_dama === 'rotina' && <span className="px-2 py-0.5 rounded text-[10px] font-black bg-slate-400 text-white">ROTINA</span>}
            <span className={`px-2 py-0.5 rounded text-[10px] font-black uppercase ${
              r.risco === 'ALTO' ? 'bg-red-600 text-white' : r.risco === 'MEDIO' ? 'bg-amber-500 text-white' : 'bg-slate-200 text-slate-600'
            }`}>{r.risco}</span>
            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
              r.tipo_alerta === 'importacao excepcional' ? 'bg-purple-100 text-purple-700' :
              r.tipo_alerta === 'desabastecimento' ? 'bg-red-100 text-red-700' :
              r.tipo_alerta === 'decisao judicial' ? 'bg-blue-100 text-blue-700' :
              r.tipo_alerta === 'regulamentacao' ? 'bg-amber-100 text-amber-700' :
              r.tipo_alerta === 'janela aberta' ? 'bg-red-100 text-red-700' :
              r.tipo_alerta === 'dispensa' ? 'bg-orange-100 text-orange-700' :
              r.tipo_alerta === 'descontinuacao' ? 'bg-violet-100 text-violet-700' :
              r.tipo_alerta === 'indicador mercado' ? 'bg-amber-100 text-amber-700' :
              'bg-slate-100 text-slate-600'
            }`}>{r.tipo_alerta || 'informativo'}</span>
            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
              r.fonte_busca === 'DOU' ? 'bg-blue-100 text-blue-600' :
              r.fonte_busca === 'CMED' ? 'bg-red-100 text-red-600' :
              r.fonte_busca === 'Noticias ANVISA' ? 'bg-green-100 text-green-700' :
              r.fonte_busca?.includes('PNCP') ? 'bg-indigo-100 text-indigo-700' :
              r.fonte_busca?.includes('Descontinuacao') ? 'bg-violet-100 text-violet-700' :
              'bg-slate-100 text-slate-500'
            }`}>{r.fonte_busca || r.fonte || 'GSM'}</span>
            {r.data_publicacao && <span className="text-[10px] text-slate-400 font-medium">{r.data_publicacao}</span>}
          </div>
          <h4 className="text-sm font-bold text-slate-800 leading-snug">{r.titulo}</h4>
          {r.descricao && <p className="text-xs text-slate-500 mt-1 line-clamp-2">{r.descricao?.replace(/<[^>]+>/g, ' ')}</p>}
          {r.aviso_dama && <p className="text-[10px] text-amber-600 mt-1 font-semibold italic">{r.aviso_dama}</p>}
        </div>
        <div className="flex flex-col gap-1 flex-shrink-0">
          {r.link && (
            <a href={r.link} target="_blank" rel="noopener noreferrer" data-testid={`busca-link-${idx}`}
              className="inline-flex items-center gap-1 px-3 py-1.5 bg-blue-600 text-white rounded-lg text-[11px] font-bold hover:bg-blue-700 transition-colors">
              <ExternalLink size={12}/> Ver Documento
            </a>
          )}
          <button data-testid={`prova-documental-btn-${idx}`}
            onClick={() => damaChecklist?.gerarProvaDocumental({
              ...r,
              medicamento_detectado: r.medicamento_detectado || r.medicamento || medicamentoBuscado,
            }, companies.find(c => c.name)?.id || '')}
            className="inline-flex items-center gap-1 px-3 py-1.5 bg-amber-600 text-white rounded-lg text-[11px] font-bold hover:bg-amber-700 transition-colors">
            <FileDown size={12}/> Prova PDF
          </button>
          <button onClick={() => openEsclarecimento(r, medicamentoBuscado, companies)}
            className="inline-flex items-center gap-1 px-3 py-1.5 bg-purple-600 text-white rounded-lg text-[11px] font-bold hover:bg-purple-700 transition-colors">
            <FileText size={12}/> Esclarecimento
          </button>
        </div>
      </div>
    </div>
  );
}

function StatsBar({ stats }) {
  return (
    <div className="flex flex-wrap gap-3">
      <div className="bg-white px-4 py-2 rounded-xl shadow border border-slate-200 flex items-center gap-2">
        <span className="text-lg font-black text-slate-800">{stats.total_alertas}</span>
        <span className="text-[10px] font-bold text-slate-400 uppercase">Alertas</span>
      </div>
      <div className="bg-red-600 px-4 py-2 rounded-xl shadow flex items-center gap-2 text-white">
        <span className="text-lg font-black">{stats.janelas_abertas || 0}</span>
        <span className="text-[10px] font-bold uppercase opacity-90">Janelas Abertas</span>
      </div>
      <div className="bg-white px-4 py-2 rounded-xl shadow border border-red-200 flex items-center gap-2">
        <span className="text-lg font-black text-red-600">{stats.risco_alto}</span>
        <span className="text-[10px] font-bold text-red-400 uppercase">Risco Alto</span>
      </div>
      <div className="bg-white px-4 py-2 rounded-xl shadow border border-blue-200 flex items-center gap-2">
        <span className="text-lg font-black text-blue-600">{stats.oportunidades_importacao}</span>
        <span className="text-[10px] font-bold text-blue-400 uppercase">Importacao</span>
      </div>
    </div>
  );
}

function AlertasList({ alertas, companies, openEsclarecimento, setSearchTerm, setActiveTab, executarBusca }) {
  return (
    <div className="space-y-3" data-testid="anvisa-lista">
      <p className="text-xs text-slate-400 font-bold uppercase tracking-wider">{alertas.length} alertas | Ordenado por relevancia</p>
      {alertas.map((alerta, idx) => {
        const med = alerta.medicamento_detectado || alerta.medicamento || '';
        const pa = alerta.principio_ativo || '';
        const janela = alerta.janela_importacao;
        const indice = alerta.indice_oportunidade || 0;
        let nomeBusca = med.includes(',') ? med.split(',')[0].trim() : med;
        if (nomeBusca.length > 40 && pa && pa.length < nomeBusca.length && pa !== 'N/A') nomeBusca = pa;

        return (
          <div key={idx} data-testid={`anvisa-alerta-${idx}`}
            className={`bg-white rounded-2xl shadow-lg border-2 overflow-hidden transition-all hover:shadow-xl ${
              janela ? 'border-red-400 bg-red-50/20' : indice >= 50 ? 'border-amber-300' : 'border-slate-200'
            }`}>
            <div className="p-5">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 flex-wrap mb-2">
                    <h3 data-testid={`anvisa-med-nome-${idx}`} className="text-xl font-black text-slate-900 uppercase tracking-wide">{nomeBusca}</h3>
                    {janela && <span className="px-3 py-1 bg-red-600 text-white rounded-lg text-xs font-black animate-pulse shadow-md">JANELA ABERTA</span>}
                    {!janela && indice >= 50 && <span className="px-2 py-0.5 bg-amber-100 text-amber-700 rounded text-[10px] font-black">MONITORAR</span>}
                  </div>
                  {pa && pa !== med && pa !== nomeBusca && <p className="text-sm text-blue-700 font-semibold mb-1">Principio Ativo: {pa}</p>}
                  <p className="text-sm text-slate-600 mb-2">{alerta.situacao}</p>
                  {janela && alerta.motivo_janela && (
                    <p className="text-xs text-red-700 font-semibold bg-red-50 px-3 py-1.5 rounded-lg border border-red-200 mb-2">{alerta.motivo_janela}</p>
                  )}
                  <AlertaMetadata alerta={alerta} />
                  <AlertaTags alerta={alerta} indice={indice} />
                </div>
                <div className="flex flex-col gap-2 items-end flex-shrink-0">
                  <button data-testid={`anvisa-buscar-${idx}`}
                    onClick={() => { if (nomeBusca && nomeBusca !== 'N/A') { setSearchTerm(nomeBusca); setActiveTab('search'); executarBusca(nomeBusca, '', ''); } }}
                    className="px-5 py-3 bg-blue-600 text-white rounded-xl text-sm font-black hover:bg-blue-700 transition-all shadow-lg active:scale-95 flex items-center gap-2 whitespace-nowrap">
                    <Search size={16}/> Localizar Editais
                  </button>
                  {alerta.link && (
                    <a href={alerta.link} target="_blank" rel="noopener noreferrer" data-testid={`anvisa-prova-${idx}`}
                      className="px-4 py-2 bg-amber-500 text-white rounded-xl text-xs font-black hover:bg-amber-600 transition-all inline-flex items-center gap-1.5 shadow">
                      <ExternalLink size={14}/> Ver Prova Documental
                    </a>
                  )}
                  <button data-testid={`anvisa-esclarecimento-${idx}`}
                    onClick={() => openEsclarecimento(alerta, med, companies)}
                    className="px-4 py-2 bg-purple-600 text-white rounded-xl text-xs font-black hover:bg-purple-700 transition-all inline-flex items-center gap-1.5 shadow">
                    <FileText size={14}/> Gerar Esclarecimento
                  </button>
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function AlertaMetadata({ alerta }) {
  const re = alerta.numero_re && alerta.numero_re !== 'N/A' ? alerta.numero_re : '';
  const proc = alerta.numero_processo_judicial && alerta.numero_processo_judicial !== 'N/A' ? alerta.numero_processo_judicial : '';
  const org = alerta.orgao_destinatario && alerta.orgao_destinatario !== 'N/A' ? alerta.orgao_destinatario : '';
  const qtd = alerta.quantidade_autorizada && alerta.quantidade_autorizada !== 'N/A' ? alerta.quantidade_autorizada : '';
  if (!re && !proc && !org && !qtd) return null;
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 mb-2 text-xs">
      {re && <span className="text-blue-800 font-bold bg-blue-50 px-2 py-0.5 rounded border border-blue-200">RE n {re}</span>}
      {proc && <span className="text-purple-800 font-bold bg-purple-50 px-2 py-0.5 rounded border border-purple-200">Processo: {proc}</span>}
      {org && <span className="text-slate-700 font-semibold">Dest: {org}</span>}
      {qtd && <span className="text-emerald-700 font-semibold">Qtd: {qtd}</span>}
    </div>
  );
}

function AlertaTags({ alerta, indice }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
        alerta.tipo_alerta === 'importacao excepcional' || alerta.tipo_alerta === 'importacao_excepcional' ? 'bg-blue-500 text-white' :
        alerta.tipo_alerta === 'decisao judicial' || alerta.tipo_alerta === 'decisao_judicial' ? 'bg-purple-500 text-white' :
        alerta.tipo_alerta === 'desabastecimento' ? 'bg-red-100 text-red-700' :
        alerta.tipo_alerta === 'interrupcao fabricacao' ? 'bg-red-100 text-red-700' :
        alerta.tipo_alerta === 'recolhimento' ? 'bg-amber-100 text-amber-700' :
        alerta.tipo_alerta === 'proibicao' ? 'bg-red-100 text-red-700' :
        'bg-slate-100 text-slate-500'
      }`}>{alerta.tipo_alerta}</span>
      <span className={`px-2 py-0.5 rounded-full text-[10px] font-black ${
        alerta.risco === 'ALTO' ? 'bg-red-500 text-white' : alerta.risco === 'MEDIO' ? 'bg-amber-500 text-white' : 'bg-green-100 text-green-700'
      }`}>{alerta.risco}</span>
      <span className="px-2 py-0.5 bg-slate-100 text-slate-500 rounded text-[10px] font-bold">{alerta.fonte || 'ANVISA'}</span>
      {indice > 0 && (
        <span className={`px-2 py-0.5 rounded text-[10px] font-black ${indice >= 70 ? 'bg-red-100 text-red-600' : indice >= 40 ? 'bg-amber-100 text-amber-600' : 'bg-slate-100 text-slate-400'}`}>
          {indice}%
        </span>
      )}
    </div>
  );
}
