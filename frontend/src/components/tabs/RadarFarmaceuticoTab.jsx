import React, { useState, useEffect } from 'react';
import { Loader2, Search, Plus, Trash2, RefreshCw, AlertTriangle, CheckCircle, Target, Pill, Activity, ShieldAlert, ArrowRight, X, ChevronDown, ChevronUp } from 'lucide-react';

const CATEGORIAS = [
  { id: 'Oncologia', label: 'Oncologia', badgeCls: 'bg-rose-100 text-rose-700' },
  { id: 'Doencas Raras', label: 'Doencas Raras', badgeCls: 'bg-violet-100 text-violet-700' },
  { id: 'Peptideos', label: 'Peptideos', badgeCls: 'bg-cyan-100 text-cyan-700' },
];

const PRIORIDADES = [
  { id: 'alta', label: 'Alta', color: 'red' },
  { id: 'media', label: 'Media', color: 'amber' },
  { id: 'baixa', label: 'Baixa', color: 'slate' },
];

const TARGET_TYPES = [
  { id: 'Importacao', label: 'Importacao' },
  { id: 'Nacional', label: 'Nacional' },
];

const STATUS_CONFIG = {
  desabastecimento_detectado: { label: 'Desabastecimento', badgeCls: 'bg-red-100 text-red-700', iconCls: 'bg-red-100', iconColor: 'text-red-600', icon: ShieldAlert },
  interrupcao_definitiva: { label: 'Interrupcao Definitiva', badgeCls: 'bg-red-100 text-red-700', iconCls: 'bg-red-100', iconColor: 'text-red-600', icon: AlertTriangle },
  suspensao_fabricacao: { label: 'Suspensao Fabricacao', badgeCls: 'bg-amber-100 text-amber-700', iconCls: 'bg-amber-100', iconColor: 'text-amber-600', icon: AlertTriangle },
  descontinuidade_temporaria: { label: 'Descontinuidade Temp.', badgeCls: 'bg-amber-100 text-amber-700', iconCls: 'bg-amber-100', iconColor: 'text-amber-600', icon: Activity },
  reativacao_fabricacao: { label: 'Reativacao', badgeCls: 'bg-emerald-100 text-emerald-700', iconCls: 'bg-emerald-100', iconColor: 'text-emerald-600', icon: CheckCircle },
};

export function RadarFarmaceuticoTab({
  listaInteresse, desabastecimento, stats, loading, scanLoading, addLoading,
  carregarListaInteresse, carregarDesabastecimento, carregarStats,
  adicionarInteresse, removerInteresse, executarScan,
}) {
  const [showAddForm, setShowAddForm] = useState(false);
  const [newItem, setNewItem] = useState({ medicamento: '', principio_ativo: '', categoria: 'Oncologia', prioridade: 'alta', target_type: 'Importacao' });
  const [expandedDesab, setExpandedDesab] = useState(null);

  useEffect(() => {
    if (!listaInteresse) carregarListaInteresse();
    if (!desabastecimento) carregarDesabastecimento();
    if (!stats) carregarStats();
  }, [listaInteresse, desabastecimento, stats, carregarListaInteresse, carregarDesabastecimento, carregarStats]);

  const handleAdd = async () => {
    if (!newItem.medicamento.trim()) return;
    const ok = await adicionarInteresse({
      ...newItem,
      principio_ativo: newItem.principio_ativo || newItem.medicamento,
    });
    if (ok) {
      setNewItem({ medicamento: '', principio_ativo: '', categoria: 'Oncologia', prioridade: 'alta', target_type: 'Importacao' });
      setShowAddForm(false);
    }
  };

  const handleRemove = async (id) => {
    await removerInteresse(id);
  };

  const items = listaInteresse?.items || [];
  const desabItems = desabastecimento?.items || [];
  const estatisticas = stats || {};

  return (
    <div className="space-y-6" data-testid="radar-farmaceutico-tab">
      {/* Header */}
      <div className="bg-gradient-to-r from-slate-900 to-slate-800 rounded-2xl p-6 border border-slate-700 shadow-xl">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-black text-white flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-rose-600/20 flex items-center justify-center">
                <Activity size={22} className="text-rose-400"/>
              </div>
              Radar Farmaceutico
            </h2>
            <p className="text-slate-400 text-sm mt-1">Inteligencia de Desabastecimento ANVISA - Monitoramento Estrategico</p>
          </div>
          <button
            onClick={executarScan}
            disabled={scanLoading}
            data-testid="btn-scan-desabastecimento"
            className="flex items-center gap-2 px-5 py-3 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold text-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-rose-600/30"
          >
            <RefreshCw size={16} className={scanLoading ? 'animate-spin' : ''}/>
            {scanLoading ? 'Escaneando DOU...' : 'Escanear Desabastecimento'}
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Lista de Interesse" value={estatisticas.total_lista_interesse || 0} color="blue" icon={Target} testId="stat-interesse"/>
        <StatCard label="Desabastecimento" value={estatisticas.total_desabastecimento || 0} color="red" icon={ShieldAlert} testId="stat-desab"/>
        <StatCard label="Criticos (95%)" value={estatisticas.criticos || 0} color="rose" icon={AlertTriangle} testId="stat-criticos"/>
        <StatCard label="Reativados" value={estatisticas.reativados || 0} color="emerald" icon={CheckCircle} testId="stat-reativados"/>
      </div>

      {/* Lista de Interesse Estrategica */}
      <div className="bg-white rounded-2xl shadow-lg border border-slate-200 overflow-hidden">
        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 px-6 py-4 border-b border-slate-200 flex items-center justify-between">
          <h3 className="font-black text-slate-800 text-sm uppercase tracking-wider flex items-center gap-2">
            <Target size={18} className="text-blue-600"/>
            Lista de Interesse Estrategica
          </h3>
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            data-testid="btn-add-interesse"
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs transition-all shadow"
          >
            <Plus size={14}/> Adicionar
          </button>
        </div>

        {/* Add Form */}
        {showAddForm && (
          <div className="px-6 py-4 bg-blue-50/50 border-b border-blue-100" data-testid="form-add-interesse">
            <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
              <input
                data-testid="input-medicamento"
                placeholder="Medicamento"
                value={newItem.medicamento}
                onChange={e => setNewItem({...newItem, medicamento: e.target.value})}
                className="px-3 py-2 rounded-lg border border-slate-300 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
              />
              <input
                data-testid="input-principio-ativo"
                placeholder="Principio Ativo"
                value={newItem.principio_ativo}
                onChange={e => setNewItem({...newItem, principio_ativo: e.target.value})}
                className="px-3 py-2 rounded-lg border border-slate-300 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
              />
              <select
                data-testid="select-categoria"
                value={newItem.categoria}
                onChange={e => setNewItem({...newItem, categoria: e.target.value})}
                className="px-3 py-2 rounded-lg border border-slate-300 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none bg-white"
              >
                {CATEGORIAS.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
              </select>
              <select
                data-testid="select-target-type"
                value={newItem.target_type}
                onChange={e => setNewItem({...newItem, target_type: e.target.value})}
                className="px-3 py-2 rounded-lg border border-slate-300 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none bg-white"
              >
                {TARGET_TYPES.map(t => <option key={t.id} value={t.id}>{t.label}</option>)}
              </select>
              <div className="flex gap-2">
                <button
                  onClick={handleAdd}
                  disabled={addLoading || !newItem.medicamento.trim()}
                  data-testid="btn-confirmar-add"
                  className="flex-1 flex items-center justify-center gap-1 px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs transition-all disabled:opacity-50"
                >
                  {addLoading ? <Loader2 size={14} className="animate-spin"/> : <CheckCircle size={14}/>}
                  Salvar
                </button>
                <button
                  onClick={() => setShowAddForm(false)}
                  className="px-3 py-2 rounded-lg bg-slate-200 hover:bg-slate-300 text-slate-600 font-bold text-xs transition-all"
                >
                  <X size={14}/>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="tabela-interesse">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                <th className="text-left px-6 py-3 font-bold text-slate-600 text-xs uppercase">Medicamento</th>
                <th className="text-left px-4 py-3 font-bold text-slate-600 text-xs uppercase">Principio Ativo</th>
                <th className="text-center px-4 py-3 font-bold text-slate-600 text-xs uppercase">Categoria</th>
                <th className="text-center px-4 py-3 font-bold text-slate-600 text-xs uppercase">Prioridade</th>
                <th className="text-center px-4 py-3 font-bold text-slate-600 text-xs uppercase">Target</th>
                <th className="text-center px-4 py-3 font-bold text-slate-600 text-xs uppercase">Status</th>
                <th className="text-center px-4 py-3 font-bold text-slate-600 text-xs uppercase">Acao</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item, idx) => {
                const catConfig = CATEGORIAS.find(c => c.id === item.categoria) || CATEGORIAS[0];
                const desabMatch = desabItems.find(d => d.medicamento?.toLowerCase() === item.medicamento?.toLowerCase());
                const statusKey = desabMatch?.status_anvisa || '';
                const statusCfg = STATUS_CONFIG[statusKey];

                return (
                  <tr key={item.id || idx} className="border-b border-slate-100 hover:bg-slate-50 transition-colors" data-testid={`interesse-row-${idx}`}>
                    <td className="px-6 py-3 font-bold text-slate-800">{item.medicamento}</td>
                    <td className="px-4 py-3 text-slate-600">{item.principio_ativo}</td>
                    <td className="px-4 py-3 text-center">
                      <span className={`px-2.5 py-1 rounded-full text-xs font-bold ${catConfig.badgeCls}`}>
                        {catConfig.label}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase ${
                        item.prioridade === 'alta' ? 'bg-red-100 text-red-700' :
                        item.prioridade === 'media' ? 'bg-amber-100 text-amber-700' :
                        'bg-slate-100 text-slate-600'
                      }`}>
                        {item.prioridade}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={`text-xs font-bold ${item.target_type === 'Importacao' ? 'text-teal-600' : 'text-indigo-600'}`}>
                        {item.target_type}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      {desabMatch ? (
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-bold ${statusCfg?.badgeCls || 'bg-red-100 text-red-700'}`}>
                          {statusCfg?.icon && <statusCfg.icon size={12}/>}
                          {statusCfg?.label || statusKey}
                        </span>
                      ) : (
                        <span className="text-xs text-slate-400 font-medium">Monitorando</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <button
                        onClick={() => handleRemove(item.id)}
                        data-testid={`btn-remover-${idx}`}
                        className="p-1.5 rounded-lg hover:bg-red-50 text-slate-400 hover:text-red-500 transition-all"
                        title="Remover da lista"
                      >
                        <Trash2 size={15}/>
                      </button>
                    </td>
                  </tr>
                );
              })}
              {items.length === 0 && (
                <tr><td colSpan="7" className="px-6 py-8 text-center text-slate-400 font-medium">Nenhum medicamento na lista de interesse</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Desabastecimento Detectado */}
      <div className="bg-white rounded-2xl shadow-lg border border-slate-200 overflow-hidden">
        <div className="bg-gradient-to-r from-red-50 to-rose-50 px-6 py-4 border-b border-slate-200 flex items-center justify-between">
          <h3 className="font-black text-slate-800 text-sm uppercase tracking-wider flex items-center gap-2">
            <ShieldAlert size={18} className="text-red-600"/>
            Desabastecimento Detectado
            {desabItems.length > 0 && (
              <span className="ml-2 px-2 py-0.5 rounded-full bg-red-600 text-white text-xs font-bold">{desabItems.length}</span>
            )}
          </h3>
        </div>

        {loading ? (
          <div className="py-12 text-center">
            <Loader2 size={32} className="animate-spin text-red-500 mx-auto mb-3"/>
            <p className="text-slate-500 text-sm font-medium">Carregando dados de desabastecimento...</p>
          </div>
        ) : desabItems.length === 0 ? (
          <div className="py-12 text-center">
            <CheckCircle size={40} className="text-emerald-400 mx-auto mb-3"/>
            <p className="text-slate-600 font-bold text-sm">Nenhum desabastecimento detectado na lista de interesse</p>
            <p className="text-slate-400 text-xs mt-1">Execute o scan para verificar publicacoes recentes do DOU/ANVISA</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {desabItems.map((item, idx) => {
              const statusCfg = STATUS_CONFIG[item.status_anvisa] || STATUS_CONFIG.desabastecimento_detectado;
              const isExpanded = expandedDesab === idx;
              const StatusIcon = statusCfg.icon;

              return (
                <div key={item.id || idx} className="px-6 py-4 hover:bg-slate-50/50 transition-colors" data-testid={`desab-row-${idx}`}>
                  <div className="flex items-center justify-between cursor-pointer" onClick={() => setExpandedDesab(isExpanded ? null : idx)}>
                    <div className="flex items-center gap-4">
                      <div className={`w-10 h-10 rounded-xl ${statusCfg.iconCls} flex items-center justify-center`}>
                        <StatusIcon size={20} className={statusCfg.iconColor}/>
                      </div>
                      <div>
                        <p className="font-bold text-slate-800">{item.medicamento}</p>
                        <p className="text-xs text-slate-500">{item.principio_ativo} - {item.categoria_terapeutica}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <span className={`px-3 py-1 rounded-full text-xs font-bold ${statusCfg.badgeCls}`}>
                        {statusCfg.label}
                      </span>
                      <div className={`px-3 py-1.5 rounded-xl font-black text-sm ${
                        item.score_boost >= 95 ? 'bg-red-600 text-white shadow-lg shadow-red-600/30' :
                        'bg-slate-200 text-slate-600'
                      }`}>
                        {item.score_boost}%
                      </div>
                      {isExpanded ? <ChevronUp size={18} className="text-slate-400"/> : <ChevronDown size={18} className="text-slate-400"/>}
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="mt-4 ml-14 bg-slate-50 rounded-xl p-4 text-sm space-y-2 border border-slate-200">
                      <div className="grid grid-cols-2 gap-3">
                        <div><span className="font-bold text-slate-600">Fonte:</span> <span className="text-slate-500">{item.fonte_deteccao}</span></div>
                        <div><span className="font-bold text-slate-600">Target:</span> <span className="text-slate-500">{item.target_type}</span></div>
                        <div><span className="font-bold text-slate-600">Data Interrupcao:</span> <span className="text-slate-500">{item.data_interrupcao || 'N/A'}</span></div>
                        <div><span className="font-bold text-slate-600">Previsao Retorno:</span> <span className="text-slate-500">{item.previsao_retorno || 'N/A'}</span></div>
                      </div>
                      {item.titulo_fonte && (
                        <div className="mt-2 pt-2 border-t border-slate-200">
                          <p className="font-bold text-slate-600 text-xs">Publicacao:</p>
                          <p className="text-slate-500 text-xs mt-1">{item.titulo_fonte}</p>
                          {item.link_fonte && (
                            <a href={item.link_fonte} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline text-xs flex items-center gap-1 mt-1">
                              Ver no DOU <ArrowRight size={12}/>
                            </a>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Scan loading overlay */}
      {scanLoading && (
        <div className="fixed inset-0 bg-black/20 z-40 flex items-center justify-center backdrop-blur-sm" data-testid="scan-overlay">
          <div className="bg-white rounded-2xl p-8 shadow-2xl text-center max-w-sm">
            <RefreshCw size={40} className="animate-spin text-rose-500 mx-auto mb-4"/>
            <p className="font-bold text-slate-800 text-lg">Escaneando DOU/ANVISA</p>
            <p className="text-slate-500 text-sm mt-2">Buscando publicacoes de interrupcao, suspensao e descontinuidade. Cruzando com lista de interesse...</p>
            <p className="text-slate-400 text-xs mt-3">Isso pode levar ate 30 segundos</p>
          </div>
        </div>
      )}
    </div>
  );
}

const STAT_COLORS = {
  blue: { text: 'text-blue-600', iconBg: 'bg-blue-100', iconColor: 'text-blue-600' },
  red: { text: 'text-red-600', iconBg: 'bg-red-100', iconColor: 'text-red-600' },
  rose: { text: 'text-rose-600', iconBg: 'bg-rose-100', iconColor: 'text-rose-600' },
  emerald: { text: 'text-emerald-600', iconBg: 'bg-emerald-100', iconColor: 'text-emerald-600' },
};

function StatCard({ label, value, color, icon: Icon, testId }) {
  const c = STAT_COLORS[color] || STAT_COLORS.blue;
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm hover:shadow-md transition-all" data-testid={testId}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">{label}</p>
          <p className={`text-2xl font-black ${c.text} mt-1`}>{value}</p>
        </div>
        <div className={`w-10 h-10 rounded-xl ${c.iconBg} flex items-center justify-center`}>
          <Icon size={20} className={c.iconColor}/>
        </div>
      </div>
    </div>
  );
}
