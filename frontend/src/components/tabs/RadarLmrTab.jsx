import React, { useState, useEffect } from 'react';
import { Loader2, Search, TrendingUp, TrendingDown, AlertTriangle, CheckCircle, ChevronDown, ChevronUp, Target, Zap, ShieldCheck, DollarSign, ArrowRight, RefreshCw, Package, Filter, FileDown, X } from 'lucide-react';

const API_BASE = process.env.REACT_APP_BACKEND_URL;

const CATEGORIAS = [
  { id: 'todos', label: 'Todos', color: 'slate' },
  { id: 'sintetico', label: 'Sintetico', color: 'blue' },
  { id: 'biologico', label: 'Biologico', color: 'purple' },
  { id: 'generico', label: 'Generico', color: 'teal' },
  { id: 'similar', label: 'Similar', color: 'amber' },
  { id: 'excepcional', label: 'Excepcional', color: 'red' },
];

export function RadarLmrTab({ oportunidades, loading, analiseDetalhe, analiseLoading, carregarOportunidades, analisarMedicamento, setAnaliseDetalhe, alertaAberto, alertaLoading, fecharAlerta }) {
  const [buscaMed, setBuscaMed] = useState('');
  const [precoRef, setPrecoRef] = useState('');
  const [tipoProduto, setTipoProduto] = useState('todos');
  const [categoriaAtiva, setCategoriaAtiva] = useState('todos');
  const [expandedIdx, setExpandedIdx] = useState(null);
  const [soCriticas, setSoCriticas] = useState(false);

  useEffect(() => {
    if (!oportunidades) carregarOportunidades();
  }, [oportunidades, carregarOportunidades]);

  const handleAnalise = () => {
    if (buscaMed.trim()) {
      analisarMedicamento(buscaMed.trim(), parseFloat(precoRef) || 0, tipoProduto);
    }
  };

  // Sync tipoProduto with categoriaAtiva
  const handleCategoriaChange = (catId) => {
    setCategoriaAtiva(catId);
    setExpandedIdx(null);
    if (catId !== 'todos') setTipoProduto(catId);
  };

  const stats = oportunidades?.estatisticas || {};

  // Aplicar filtros: categoria + criticas
  let listaFiltrada = oportunidades?.oportunidades || [];
  if (soCriticas) {
    listaFiltrada = listaFiltrada.filter(o => o.oportunidade_score >= 80);
  }

  return (
    <div className="space-y-6" data-testid="radar-lmr-tab">
      {/* Alerta do Email (deep-link) */}
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
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-black text-slate-800 uppercase tracking-tight flex items-center gap-3">
            <Target size={28} className="text-emerald-500"/> RADAR DE IMPORTACAO
          </h2>
          <p className="text-slate-400 text-xs font-medium mt-1">Analise estrategica sob IN 428/2026 | Oportunidades de importacao com beneficio tributario</p>
        </div>
        <button data-testid="lmr-refresh-btn" onClick={carregarOportunidades} disabled={loading}
          className="flex items-center gap-2 px-4 py-2.5 bg-emerald-600 text-white rounded-xl font-bold text-sm hover:bg-emerald-700 transition-all disabled:opacity-50">
          {loading ? <Loader2 size={16} className="animate-spin"/> : <RefreshCw size={16}/>}
          {loading ? 'Atualizando...' : 'Atualizar Radar'}
        </button>
      </div>

      {/* Stats Cards */}
      {oportunidades && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="lmr-stats">
          <StatCard icon={Package} label="Total Oportunidades" value={oportunidades.total || 0} color="slate" />
          <StatCard icon={Zap} label="Oportunidade Alta" value={stats.oportunidade_alta || 0} color="emerald" highlight />
          <StatCard icon={TrendingUp} label="Oportunidade Media" value={stats.oportunidade_media || 0} color="amber" />
          <StatCard icon={TrendingDown} label="Oportunidade Baixa" value={stats.oportunidade_baixa || 0} color="slate" />
        </div>
      )}

      {/* Category Tabs */}
      <div className="bg-white rounded-2xl shadow-lg border border-slate-200 p-1.5" data-testid="lmr-categorias">
        <div className="flex gap-1 overflow-x-auto">
          {CATEGORIAS.map(cat => (
            <button
              key={cat.id}
              data-testid={`categoria-${cat.id}`}
              onClick={() => handleCategoriaChange(cat.id)}
              className={`px-4 py-2.5 rounded-xl text-xs font-black uppercase whitespace-nowrap transition-all ${
                categoriaAtiva === cat.id
                  ? `bg-${cat.color}-600 text-white shadow-lg`
                  : 'text-slate-400 hover:text-slate-700 hover:bg-slate-50'
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>
        {categoriaAtiva !== 'todos' && (
          <p className="text-[10px] text-slate-400 font-medium mt-1.5 px-2" data-testid="categoria-info">
            Analises individuais usarao aliquotas de <strong className="text-slate-600">{CATEGORIAS.find(c => c.id === categoriaAtiva)?.label}</strong> (IN 428/2026)
          </p>
        )}
      </div>

      {/* Busca individual */}
      <div className="bg-white rounded-2xl shadow-lg border-2 border-emerald-100 p-4" data-testid="lmr-busca-individual">
        <div className="flex items-center gap-2 mb-3">
          <Search size={18} className="text-emerald-500"/>
          <span className="text-sm font-black text-slate-700 uppercase tracking-wide">Analise Individual LMR</span>
          <span className="text-[10px] text-slate-400 font-medium ml-1">Consulte a estrategia tributaria de um medicamento</span>
        </div>
        <div className="flex gap-2 flex-wrap">
          <input type="text" data-testid="lmr-busca-input"
            value={buscaMed} onChange={(e) => setBuscaMed(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAnalise()}
            placeholder="Nome do medicamento..."
            className="flex-1 min-w-[200px] px-4 py-3 bg-slate-50 border-2 border-slate-200 rounded-xl text-sm font-semibold text-slate-700 placeholder:text-slate-300 focus:border-emerald-400 focus:ring-2 focus:ring-emerald-100 outline-none transition-all"
          />
          <input type="number" data-testid="lmr-preco-input"
            value={precoRef} onChange={(e) => setPrecoRef(e.target.value)}
            placeholder="Preco ref. (R$)"
            className="w-36 px-4 py-3 bg-slate-50 border-2 border-slate-200 rounded-xl text-sm font-semibold text-slate-700 placeholder:text-slate-300 focus:border-emerald-400 outline-none transition-all"
          />
          <select data-testid="lmr-tipo-select" value={tipoProduto} onChange={(e) => { setTipoProduto(e.target.value); setCategoriaAtiva(e.target.value); }}
            className="px-3 py-3 bg-slate-50 border-2 border-slate-200 rounded-xl text-sm font-semibold text-slate-700 outline-none">
            <option value="todos">Todos os tipos</option>
            <option value="sintetico">Sintetico</option>
            <option value="biologico">Biologico</option>
            <option value="generico">Generico</option>
            <option value="similar">Similar</option>
            <option value="excepcional">Excepcional</option>
          </select>
          <button data-testid="lmr-analisar-btn" onClick={handleAnalise}
            disabled={analiseLoading || !buscaMed.trim()}
            className="px-6 py-3 bg-emerald-600 text-white rounded-xl font-black text-sm uppercase hover:bg-emerald-700 disabled:opacity-50 transition-all flex items-center gap-2">
            {analiseLoading ? <Loader2 size={16} className="animate-spin"/> : <Target size={16}/>}
            {analiseLoading ? 'Analisando...' : 'Analisar'}
          </button>
        </div>
      </div>

      {/* Resultado da analise individual */}
      {analiseDetalhe && <AnaliseDetalheCard data={analiseDetalhe} onClose={() => setAnaliseDetalhe(null)} />}

      {/* Loading */}
      {loading && !oportunidades && (
        <div className="text-center py-16 bg-white rounded-2xl shadow border border-slate-100">
          <Loader2 size={40} className="animate-spin text-emerald-500 mx-auto mb-4"/>
          <p className="text-slate-500 font-bold">Carregando Radar de Importacao...</p>
        </div>
      )}

      {/* Critical Filter Toggle - only shows when total > 0 */}
      {oportunidades && oportunidades.total > 0 && (
        <div className="flex items-center gap-3 bg-white rounded-xl shadow border border-slate-200 px-4 py-3">
          <Filter size={16} className="text-emerald-500"/>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              data-testid="toggle-so-criticas"
              checked={soCriticas}
              onChange={(e) => setSoCriticas(e.target.checked)}
              className="w-4 h-4 text-emerald-600 rounded border-slate-300 focus:ring-emerald-500"
            />
            <span className="text-sm font-bold text-slate-700">Somente Oportunidades Criticas</span>
            <span className="text-xs text-slate-400">(score >= 80%)</span>
          </label>
        </div>
      )}

      {/* Lista de Oportunidades */}
      {oportunidades && listaFiltrada.length > 0 && (
        <div className="space-y-2" data-testid="lmr-lista-oportunidades">
          <p className="text-xs text-slate-400 font-bold uppercase tracking-wider flex items-center gap-2">
            <ShieldCheck size={14}/> {listaFiltrada.length} oportunidade(s){soCriticas ? ' critica(s)' : ''} | Ordenado por score | Ref: {oportunidades.norma_referencia}
          </p>
          {listaFiltrada.map((op, idx) => (
            <OportunidadeCard key={idx} op={op} idx={idx}
              expanded={expandedIdx === idx}
              onToggle={() => setExpandedIdx(expandedIdx === idx ? null : idx)}
              onAnalise={() => { setBuscaMed(op.medicamento); analisarMedicamento(op.medicamento, 0, categoriaAtiva !== 'todos' ? categoriaAtiva : 'sintetico'); }}
            />
          ))}
        </div>
      )}

      {oportunidades && oportunidades.total === 0 && (
        <div className="text-center py-16 bg-white rounded-2xl shadow border border-slate-200">
          <Package size={48} className="text-slate-300 mx-auto mb-4"/>
          <p className="text-slate-500 font-bold text-lg">Nenhuma oportunidade identificada</p>
          <p className="text-slate-400 text-sm mt-2">Atualize a base ANVISA na aba "Janela ANVISA" para que o Radar encontre medicamentos com janela aberta.</p>
        </div>
      )}
    </div>
  );
}

function StatCard({ icon: Icon, label, value, color, highlight }) {
  return (
    <div className={`rounded-2xl shadow-lg border-2 p-4 transition-all ${
      highlight && value > 0 ? `bg-${color}-50 border-${color}-300` : 'bg-white border-slate-200'
    }`}>
      <div className="flex items-center gap-3">
        <div className={`p-2.5 rounded-xl ${highlight && value > 0 ? `bg-${color}-100` : 'bg-slate-100'}`}>
          <Icon size={20} className={highlight && value > 0 ? `text-${color}-600` : 'text-slate-400'}/>
        </div>
        <div>
          <p className="text-2xl font-black text-slate-800">{value}</p>
          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wide">{label}</p>
        </div>
      </div>
    </div>
  );
}

function ScoreBadge({ score }) {
  const bg = score >= 80 ? 'bg-emerald-600' : score >= 50 ? 'bg-amber-500' : 'bg-slate-400';
  return (
    <span className={`${bg} text-white px-3 py-1 rounded-full text-xs font-black`} data-testid="score-badge">
      {score}%
    </span>
  );
}

function OportunidadeCard({ op, idx, expanded, onToggle, onAnalise }) {
  const scoreColor = op.oportunidade_score >= 80 ? 'emerald' : op.oportunidade_score >= 50 ? 'amber' : 'slate';

  return (
    <div data-testid={`lmr-oportunidade-${idx}`}
      className={`bg-white rounded-2xl shadow-lg border-2 overflow-hidden transition-all hover:shadow-xl ${
        op.oportunidade_score >= 80 ? 'border-emerald-300' : op.oportunidade_score >= 50 ? 'border-amber-300' : 'border-slate-200'
      }`}>
      <div className="p-4 cursor-pointer" onClick={onToggle}>
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 flex-1 min-w-0">
            <ScoreBadge score={op.oportunidade_score} />
            <div className="min-w-0">
              <h3 className="text-base font-black text-slate-800 uppercase tracking-wide truncate">{op.medicamento}</h3>
              {op.principio_ativo && op.principio_ativo !== op.medicamento && (
                <p className="text-xs text-blue-600 font-semibold truncate">{op.principio_ativo}</p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <span className={`px-2 py-0.5 rounded text-[10px] font-black uppercase ${
              op.categoria_lmr === 'excepcional' ? 'bg-purple-100 text-purple-700' :
              op.categoria_lmr === 'judicial' ? 'bg-blue-100 text-blue-700' :
              'bg-slate-100 text-slate-600'
            }`}>{op.categoria_lmr}</span>
            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
              op.risco === 'ALTO' ? 'bg-red-100 text-red-600' : op.risco === 'MEDIO' ? 'bg-amber-100 text-amber-600' : 'bg-emerald-100 text-emerald-600'
            }`}>{op.risco}</span>
            <span className={`px-2 py-0.5 rounded text-[10px] font-bold bg-${scoreColor}-100 text-${scoreColor}-700`}>
              Risco: {op.risco_comercial}
            </span>
            {expanded ? <ChevronUp size={18} className="text-slate-400"/> : <ChevronDown size={18} className="text-slate-400"/>}
          </div>
        </div>
      </div>

      {expanded && (
        <div className="px-4 pb-4 border-t border-slate-100 pt-3 space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <InfoBlock label="Beneficio Tributario" value={op.beneficio} icon={DollarSign} color="emerald" />
            <InfoBlock label="Tipo Alerta" value={op.tipo_alerta || 'N/A'} icon={AlertTriangle} color="amber" />
          </div>
          {op.motivo && (
            <div className="bg-emerald-50 border border-emerald-200 rounded-xl px-4 py-2">
              <p className="text-xs text-emerald-800 font-semibold">{op.motivo}</p>
            </div>
          )}
          {op.link_prova && (
            <a href={op.link_prova} target="_blank" rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-xs font-bold text-blue-600 hover:text-blue-800 transition-colors">
              <ArrowRight size={12}/> Ver Prova Documental
            </a>
          )}
          <button data-testid={`lmr-detalhe-btn-${idx}`} onClick={onAnalise}
            className="flex items-center gap-2 px-4 py-2 bg-emerald-600 text-white rounded-xl text-xs font-bold hover:bg-emerald-700 transition-all">
            <Target size={14}/> Analise Tributaria Completa
          </button>
        </div>
      )}
    </div>
  );
}

function InfoBlock({ label, value, icon: Icon, color }) {
  return (
    <div className={`bg-${color}-50 border border-${color}-200 rounded-xl px-3 py-2 flex items-start gap-2`}>
      <Icon size={14} className={`text-${color}-600 mt-0.5 flex-shrink-0`}/>
      <div>
        <p className={`text-[10px] font-bold text-${color}-400 uppercase`}>{label}</p>
        <p className={`text-xs font-semibold text-${color}-800`}>{value}</p>
      </div>
    </div>
  );
}

function AnaliseDetalheCard({ data, onClose }) {
  const classif = data.classificacao_lmr || {};
  const trib = data.estrategia_tributaria || {};
  const margem = data.analise_margem;
  const score = data.oportunidade_score || 0;
  const scoreColor = score >= 80 ? 'emerald' : score >= 50 ? 'amber' : 'slate';

  return (
    <div className="bg-white rounded-2xl shadow-2xl border-2 border-emerald-200 overflow-hidden" data-testid="lmr-analise-detalhe">
      {/* Header */}
      <div className={`bg-gradient-to-r from-${scoreColor}-600 to-${scoreColor}-700 px-5 py-3 flex items-center justify-between`}>
        <div className="flex items-center gap-3 text-white">
          <Target size={20}/>
          <div>
            <span className="font-black text-sm uppercase">{data.medicamento}</span>
            <p className="text-[10px] font-medium opacity-80">{data.norma_referencia}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <ScoreBadge score={score} />
          <button onClick={onClose} className="text-white/70 hover:text-white transition-colors text-lg font-bold ml-2">X</button>
        </div>
      </div>

      <div className="p-5 space-y-4">
        {/* Classificacao */}
        <div>
          <h4 className="text-xs font-black text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-2">
            <ShieldCheck size={14}/> Classificacao LMR
          </h4>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <MiniStat label="Categoria" value={classif.categoria?.toUpperCase() || 'N/A'}
              color={classif.categoria === 'excepcional' ? 'purple' : classif.categoria === 'judicial' ? 'blue' : classif.categoria === 'lista_positiva' ? 'emerald' : 'slate'} />
            <MiniStat label="Risco Comercial" value={classif.risco_comercial || 'N/A'} color="amber" />
            <MiniStat label="Alertas ANVISA" value={classif.total_alertas || 0} color="red" />
            <MiniStat label="Janela Aberta" value={classif.janela_aberta ? 'SIM' : 'NAO'}
              color={classif.janela_aberta ? 'emerald' : 'slate'} />
          </div>
          <p className="text-xs text-slate-500 mt-2">{classif.descricao}</p>
          <p className="text-xs font-bold text-emerald-700 mt-1">{classif.beneficio_tributario}</p>
        </div>

        {/* Tributacao */}
        <div>
          <h4 className="text-xs font-black text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-2">
            <DollarSign size={14}/> Estrategia Tributaria
          </h4>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            <TributoBadge label="II" value={`${trib.imposto_importacao || 0}%`} />
            <TributoBadge label="ICMS" value={`${trib.icms || 0}%`} />
            <TributoBadge label="PIS" value={`${trib.pis || 0}%`} />
            <TributoBadge label="COFINS" value={`${trib.cofins || 0}%`} />
            <TributoBadge label="Carga Total" value={`${trib.carga_tributaria_total || 0}%`} highlight />
            <TributoBadge label="Margem Distrib." value={`${trib.margem_distribuidora || 0}%`} />
          </div>
          <p className="text-xs text-emerald-700 font-bold mt-2">{trib.beneficio}</p>
          {trib.custo_importacao_estimado && (
            <p className="text-xs text-slate-600 mt-1">Custo Importacao Estimado: <strong>R$ {trib.custo_importacao_estimado.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</strong></p>
          )}
        </div>

        {/* Margem */}
        {margem && (
          <div>
            <h4 className="text-xs font-black text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-2">
              <TrendingUp size={14}/> Analise de Margem
            </h4>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
              <MiniStat label="Preco Referencia" value={`R$ ${margem.preco_referencia?.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`} color="slate" />
              <MiniStat label="Preco Distribuidora" value={`R$ ${margem.preco_distribuidora?.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`} color="blue" />
              <MiniStat label="Lucro Bruto Unit." value={`R$ ${margem.lucro_bruto_unitario?.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`} color="emerald" />
              <MiniStat label="Margem %" value={`${margem.margem_percentual}%`} color="amber" />
              <MiniStat label="Economia Tributaria" value={`R$ ${margem.economia_tributaria?.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`} color="emerald" />
            </div>
          </div>
        )}

        {/* Recomendacao */}
        <div className={`rounded-xl px-4 py-3 border ${
          score >= 80 ? 'bg-emerald-50 border-emerald-300' : score >= 50 ? 'bg-amber-50 border-amber-300' : 'bg-slate-50 border-slate-300'
        }`}>
          <p className={`text-xs font-bold ${
            score >= 80 ? 'text-emerald-800' : score >= 50 ? 'text-amber-800' : 'text-slate-600'
          }`}>{data.recomendacao}</p>
        </div>
      </div>
    </div>
  );
}

function MiniStat({ label, value, color }) {
  return (
    <div className={`bg-${color}-50 border border-${color}-200 rounded-lg px-3 py-2`}>
      <p className={`text-[10px] font-bold text-${color}-400 uppercase`}>{label}</p>
      <p className={`text-sm font-black text-${color}-700`}>{value}</p>
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
            <p className="text-white/80 text-xs font-medium">Alerta de Oportunidade via E-mail | IN 428/2026</p>
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
            <p className="text-xs text-amber-700 font-bold">Analise LMR completa indisponivel. Dados exibidos sao do alerta salvo no sistema.</p>
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

