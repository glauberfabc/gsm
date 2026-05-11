import React from 'react';
import { Search, Loader2, TrendingUp, TrendingDown, ChevronDown, CheckCircle, ExternalLink, FileDown } from 'lucide-react';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip } from 'recharts';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export function PrecosTab({
  precosTermo, setPrecosTermo, precosUF, setPrecosUF,
  precosMeses, setPrecosMeses, loadingPrecos, buscarPrecos,
  precosAgregacoes, precosTotalResultados, precosResultados,
  precosApresentacoes, precosApresentacaoAberta, setPrecosApresentacaoAberta,
}) {
  return (
    <div className="space-y-8">
      <div className="text-center mb-8">
        <h2 className="text-4xl font-black text-slate-800 uppercase tracking-tight">Central de Precos</h2>
        <p className="text-slate-500 text-lg font-medium uppercase tracking-wider">Inteligencia de Mercado</p>
      </div>
      
      {/* Barra de Pesquisa */}
      <div className="bg-white p-6 rounded-3xl shadow-xl border border-slate-200">
        <div className="flex gap-4">
          <div className="flex-grow relative">
            <TrendingUp className="absolute left-4 top-1/2 -translate-y-1/2 text-emerald-500" size={24} />
            <input type="text" data-testid="precos-search-input"
              placeholder="Pesquisar preco historico de medicamento..."
              className="w-full pl-14 pr-4 py-5 bg-slate-50 border-2 border-slate-200 rounded-xl text-lg font-semibold outline-none focus:border-emerald-500"
              value={precosTermo} onChange={(e) => setPrecosTermo(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && buscarPrecos()}
            />
          </div>
          <select data-testid="precos-uf-select" className="py-4 px-3 bg-slate-50 border-2 border-slate-200 rounded-xl font-semibold text-base focus:border-emerald-500 outline-none cursor-pointer" style={{ minWidth: '110px' }}
            value={precosUF} onChange={(e) => setPrecosUF(e.target.value)}>
            <option value="">Todos UF</option>
            {['SP','RJ','MG','ES','SC','PR','RS','BA','CE','GO','DF'].map(uf => <option key={uf} value={uf}>{uf}</option>)}
          </select>
          <select data-testid="precos-meses-select" className="py-4 px-3 bg-slate-50 border-2 border-slate-200 rounded-xl font-semibold text-base focus:border-emerald-500 outline-none cursor-pointer" style={{ minWidth: '130px' }}
            value={precosMeses} onChange={(e) => setPrecosMeses(Number(e.target.value))}>
            {[3,6,9,12,18,24].map(m => <option key={m} value={m}>{m} meses</option>)}
          </select>
          <button data-testid="precos-search-btn" onClick={buscarPrecos} disabled={loadingPrecos || !precosTermo.trim()}
            className="bg-emerald-600 text-white px-10 rounded-xl font-black uppercase text-sm shadow-lg hover:bg-emerald-700 disabled:opacity-50 flex items-center gap-2">
            {loadingPrecos ? <Loader2 className="animate-spin" size={20}/> : <Search size={20}/>} Pesquisar
          </button>
        </div>
      </div>
      
      {/* Big Numbers */}
      {precosAgregacoes && precosAgregacoes.minimo > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[
            { label: 'Menor Preco', value: precosAgregacoes.minimo, color: 'emerald', testId: 'precos-minimo' },
            { label: 'Preco Medio', value: precosAgregacoes.medio, color: 'blue', testId: 'precos-medio' },
            { label: 'Maior Preco', value: precosAgregacoes.maximo, color: 'red', testId: 'precos-maximo' },
          ].map(({ label, value, color, testId }) => (
            <div key={testId} className={`bg-${color}-50 p-8 rounded-3xl border-2 border-${color}-200 text-center`}>
              <p className={`text-sm font-black text-${color}-500 uppercase tracking-wider mb-2`}>{label}</p>
              <p className={`text-4xl font-black text-${color}-700`} data-testid={testId}>
                R$ {value?.toLocaleString('pt-BR', { minimumFractionDigits: 2 }) || '0,00'}
              </p>
            </div>
          ))}
        </div>
      )}
      
      {/* Info */}
      {precosTotalResultados > 0 && (
        <div className="flex items-center justify-between px-2">
          <p className="text-sm font-bold text-slate-600">
            <CheckCircle size={16} className="inline mr-2 text-emerald-500"/>
            <span className="text-2xl font-black text-slate-800" data-testid="precos-total">{precosTotalResultados}</span> registros encontrados para &ldquo;{precosTermo}&rdquo;
            {precosApresentacoes.length > 1 && (
              <span className="ml-3 text-xs bg-amber-100 text-amber-700 px-3 py-1 rounded-full font-black">{precosApresentacoes.length} APRESENTACOES DISTINTAS</span>
            )}
          </p>
          <div className="flex items-center gap-3">
            <p className="text-xs text-slate-400">Fontes: PNCP + Base Local</p>
            <button data-testid="precos-export-excel-btn"
              onClick={() => {
                const params = new URLSearchParams();
                params.append('q', precosTermo);
                if (precosUF) params.append('uf', precosUF);
                params.append('limite', '200');
                params.append('meses', precosMeses.toString());
                window.open(`${API}/precos/export-excel?${params.toString()}`, '_blank');
              }}
              className="flex items-center gap-2 bg-emerald-600 text-white px-4 py-2 rounded-lg font-bold text-xs uppercase hover:bg-emerald-700 transition-colors shadow-md">
              <FileDown size={16}/> Exportar Excel
            </button>
          </div>
        </div>
      )}
      
      {/* Loading */}
      {loadingPrecos && (
        <div className="py-20 text-center">
          <Loader2 className="animate-spin mx-auto text-emerald-500 mb-4" size={48}/>
          <p className="text-slate-400 font-bold uppercase tracking-wider">Buscando precos historicos...</p>
          <p className="text-xs text-slate-300 mt-2">Expandindo sinonimos e consultando PNCP</p>
        </div>
      )}
      
      {/* Resultados por Apresentacao */}
      {!loadingPrecos && precosApresentacoes.length > 0 && (
        <div className="space-y-4" data-testid="precos-apresentacoes">
          {precosApresentacoes.map((ap, apIdx) => (
            <ApresentacaoCard key={`ap-${apIdx}`} ap={ap} apIdx={apIdx}
              precosApresentacaoAberta={precosApresentacaoAberta}
              setPrecosApresentacaoAberta={setPrecosApresentacaoAberta}
            />
          ))}
        </div>
      )}
      
      {/* Empty states */}
      {!loadingPrecos && precosTotalResultados === 0 && precosAgregacoes && (
        <div className="py-12 text-center text-slate-400 border-2 border-dashed border-slate-200 rounded-3xl">
          <Search size={36} className="mx-auto mb-3 opacity-50"/>
          <p className="font-black uppercase tracking-wider text-sm">Nenhum resultado relevante encontrado</p>
        </div>
      )}
      {!loadingPrecos && precosResultados.length === 0 && !precosAgregacoes && (
        <div className="py-20 text-center text-slate-300 border-2 border-dashed border-slate-200 rounded-3xl">
          <TrendingUp size={48} className="mx-auto mb-4 opacity-50"/>
          <p className="font-black uppercase tracking-wider text-sm">Digite um medicamento e clique em Pesquisar</p>
          <p className="text-xs mt-2">Ex: Insulina, Canabidiol, Prolia, Denosumabe</p>
        </div>
      )}
    </div>
  );
}

function ApresentacaoCard({ ap, apIdx, precosApresentacaoAberta, setPrecosApresentacaoAberta }) {
  const isOpen = precosApresentacaoAberta === ap.nome;
  const colorDot = apIdx === 0 ? 'bg-emerald-500' : apIdx === 1 ? 'bg-blue-500' : 'bg-amber-500';

  return (
    <div className="bg-white rounded-2xl shadow-lg border border-slate-200 overflow-hidden">
      <button data-testid={`apresentacao-header-${apIdx}`}
        onClick={() => setPrecosApresentacaoAberta(isOpen ? null : ap.nome)}
        className="w-full flex items-center justify-between px-6 py-4 hover:bg-slate-50 transition-colors">
        <div className="flex items-center gap-4">
          <div className={`w-3 h-3 rounded-full ${colorDot}`}/>
          <div className="text-left">
            <h3 className="text-lg font-black text-slate-800 uppercase tracking-wide">{ap.nome}</h3>
            <div className="flex items-center gap-2">
              <p className="text-xs text-slate-400 font-semibold">{ap.total} registro{ap.total !== 1 ? 's' : ''}</p>
              <a href={`https://pncp.gov.br/app/editais?q=${encodeURIComponent(ap.nome.split(' ')[0])}&pagina=1`}
                target="_blank" rel="noopener noreferrer" data-testid={`apresentacao-pncp-link-${apIdx}`}
                onClick={(e) => e.stopPropagation()}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-100 text-blue-700 hover:bg-blue-200 transition-colors">
                PNCP <ExternalLink size={9}/>
              </a>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-5">
          <TrendChart ap={ap} apIdx={apIdx} />
          <TrendIndicator ap={ap} apIdx={apIdx} />
          <div className="text-right"><p className="text-xs text-slate-400 font-bold uppercase">Min</p><p className="text-lg font-black text-emerald-600">R$ {ap.preco_minimo?.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</p></div>
          <div className="text-right"><p className="text-xs text-slate-400 font-bold uppercase">Medio</p><p className="text-lg font-black text-blue-600">R$ {ap.preco_medio?.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</p></div>
          <div className="text-right"><p className="text-xs text-slate-400 font-bold uppercase">Max</p><p className="text-lg font-black text-red-600">R$ {ap.preco_maximo?.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</p></div>
          <ChevronDown size={20} className={`text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}/>
        </div>
      </button>
      
      {isOpen && (
        <div className="border-t border-slate-200">
          <ExpandedChart ap={ap} apIdx={apIdx} />
          {ap.itens && <PriceTable ap={ap} apIdx={apIdx} />}
        </div>
      )}
    </div>
  );
}

function TrendChart({ ap, apIdx }) {
  if (!ap.tendencia || ap.tendencia.length < 2) return null;
  const t = ap.tendencia;
  const color = t[t.length-1].medio - t[0].medio >= 0 ? '#ef4444' : '#10b981';
  return (
    <div className="w-[140px] h-[48px]" data-testid={`tendencia-chart-${apIdx}`}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={t} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
          <defs><linearGradient id={`grad-${apIdx}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={color} stopOpacity={0.3}/><stop offset="100%" stopColor={color} stopOpacity={0.05}/></linearGradient></defs>
          <Tooltip contentStyle={{ fontSize: '10px', padding: '4px 8px', borderRadius: '8px', border: '1px solid #e2e8f0' }}
            formatter={(v) => [`R$ ${Number(v).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`, 'Medio']} labelFormatter={(l) => l}/>
          <Area type="monotone" dataKey="medio" stroke={color} strokeWidth={2} fill={`url(#grad-${apIdx})`} dot={false}/>
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function TrendIndicator({ ap, apIdx }) {
  if (!ap.tendencia || ap.tendencia.length < 2) return null;
  const t = ap.tendencia;
  const diff = t[t.length-1].medio - t[0].medio;
  const pct = ((diff / t[0].medio) * 100).toFixed(1);
  const isUp = diff >= 0;
  return (
    <div className={`text-center px-2 py-1 rounded-lg ${isUp ? 'bg-red-50' : 'bg-emerald-50'}`} data-testid={`tendencia-indicator-${apIdx}`}>
      {isUp ? <TrendingUp size={14} className="mx-auto text-red-500"/> : <TrendingDown size={14} className="mx-auto text-emerald-500"/>}
      <p className={`text-xs font-black ${isUp ? 'text-red-600' : 'text-emerald-600'}`}>{isUp ? '+' : ''}{pct}%</p>
    </div>
  );
}

function ExpandedChart({ ap, apIdx }) {
  if (!ap.tendencia || ap.tendencia.length < 2) return null;
  const t = ap.tendencia;
  const diff = t[t.length-1].medio - t[0].medio;
  const pct = ((diff / t[0].medio) * 100).toFixed(1);
  return (
    <div className="px-6 py-4 bg-slate-50 border-b border-slate-200">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs font-black text-slate-500 uppercase tracking-wider">Tendencia de Preco Medio por Mes</p>
        <p className={`text-xs font-black ${diff >= 0 ? 'text-red-600' : 'text-emerald-600'}`}>
          {diff >= 0 ? 'Tendencia de alta' : 'Tendencia de queda'}: {diff >= 0 ? '+' : ''}{pct}%
        </p>
      </div>
      <div className="h-[160px]" data-testid={`tendencia-chart-expanded-${apIdx}`}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={t} margin={{ top: 5, right: 20, bottom: 5, left: 20 }}>
            <defs><linearGradient id={`grad-exp-${apIdx}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#3b82f6" stopOpacity={0.2}/><stop offset="100%" stopColor="#3b82f6" stopOpacity={0.02}/></linearGradient></defs>
            <XAxis dataKey="mes" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={{ stroke: '#e2e8f0' }} tickLine={false}/>
            <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} tickFormatter={(v) => `R$${v}`} width={65}/>
            <Tooltip contentStyle={{ fontSize: '11px', padding: '8px 12px', borderRadius: '10px', border: '1px solid #e2e8f0', boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}
              formatter={(v, name) => { const labels = { medio: 'Medio', min: 'Minimo', max: 'Maximo' }; return [`R$ ${Number(v).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`, labels[name] || name]; }}
              labelFormatter={(l) => `Mes: ${l}`}/>
            <Area type="monotone" dataKey="max" stroke="#fbbf24" strokeWidth={1} fill="none" strokeDasharray="4 4" dot={false}/>
            <Area type="monotone" dataKey="medio" stroke="#3b82f6" strokeWidth={2.5} fill={`url(#grad-exp-${apIdx})`} dot={{ r: 3, fill: '#3b82f6', stroke: '#fff', strokeWidth: 2 }}/>
            <Area type="monotone" dataKey="min" stroke="#10b981" strokeWidth={1} fill="none" strokeDasharray="4 4" dot={false}/>
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function PriceTable({ ap, apIdx }) {
  const resolveSourceUrl = (item) => {
    const fonte = item.fonte || '';
    const np = item.numero_processo || '';
    if (fonte === 'PNCP' && np.match(/^\d{10,}\/\d{4}\/\d+$/)) return { url: `https://pncp.gov.br/app/editais/${np}`, label: 'PNCP' };
    if (fonte.includes('PNCP') || fonte.includes('Portal Nacional')) return { url: np ? `https://pncp.gov.br/app/editais?q=${encodeURIComponent(np.replace(/^PE\s*/i, ''))}` : 'https://pncp.gov.br/app/editais', label: 'PNCP' };
    if (fonte.includes('Licitar Digital')) return { url: 'https://licitardigital.com.br/', label: 'Licitar Digital' };
    if (fonte.includes('ComprasNet')) return { url: 'https://cnetmobile.estaleiro.serpro.gov.br/comprasnet-web/public/compras', label: 'ComprasNet' };
    if (fonte === 'BNC') return { url: 'https://bnc.org.br/', label: 'BNC' };
    if (fonte.includes('BLL')) return { url: 'https://bllcompras.com/', label: 'BLL Compras' };
    return null;
  };

  return (
    <div>
      <table className="w-full text-sm">
        <thead className="bg-slate-50">
          <tr className="text-xs font-black text-slate-400 uppercase tracking-wider">
            <th className="px-4 py-3 text-left">Orgao Comprador</th>
            <th className="px-4 py-3 text-left">UF</th>
            <th className="px-4 py-3 text-left">Descricao</th>
            <th className="px-4 py-3 text-right">Qtd</th>
            <th className="px-4 py-3 text-right">Valor Unitario</th>
            <th className="px-4 py-3 text-left">Data</th>
            <th className="px-4 py-3 text-left">Fonte</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {ap.itens.map((item, idx) => {
            const source = resolveSourceUrl(item);
            return (
              <tr key={`preco-${apIdx}-${idx}`} className="hover:bg-slate-50 transition-colors">
                <td className="px-4 py-3 font-semibold text-slate-700 max-w-[200px] truncate" title={item.orgao}>{item.orgao}</td>
                <td className="px-4 py-3 text-slate-500">{item.uf || '-'}</td>
                <td className="px-4 py-3 max-w-[280px] truncate text-slate-600" title={item.descricao}>{item.descricao?.replace(/<[^>]+>/g, ' ').replace(/&[a-z]+;/g, ' ')}</td>
                <td className="px-4 py-3 text-right font-bold text-slate-600">{item.quantidade} {item.unidade}</td>
                <td className="px-4 py-3 text-right font-black text-emerald-600">R$ {item.valor_unitario?.toLocaleString('pt-BR', { minimumFractionDigits: 2 }) || '0,00'}</td>
                <td className="px-4 py-3 text-slate-500 text-xs">{item.data_homologacao?.substring(0, 10) || '-'}</td>
                <td className="px-4 py-3">
                  {source ? (
                    <a href={source.url} target="_blank" rel="noopener noreferrer" data-testid={`preco-fonte-link-${apIdx}-${idx}`}
                      className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-bold bg-blue-100 text-blue-700 hover:bg-blue-200 transition-colors cursor-pointer"
                      title={`Abrir no ${source.label}`}>
                      {source.label} <ExternalLink size={11}/>
                    </a>
                  ) : (
                    <span className="px-2 py-1 rounded-full text-xs font-bold bg-slate-100 text-slate-600">{item.fonte}</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
