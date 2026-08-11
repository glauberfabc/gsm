import React from 'react';
import { Package, Database, Hash, Building, Tag, Star, MapPin, Calendar, Clock, DollarSign, ChevronRight, Download } from 'lucide-react';
import { HighlightText } from './HighlightText';
import axios from 'axios';
import { toast } from 'sonner';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const highlightText = (text, highlight) => <HighlightText text={text} highlight={highlight} />;

export function BidCard({ bid, searchTerm, expandedItens, setExpandedItens, setResults, getBidDownloadUrl }) {
  return (
    <div className="bg-white rounded-2xl shadow-lg border border-slate-200 overflow-hidden hover:shadow-xl transition-all" data-testid={`bid-card-${bid.id}`}>
      {/* HEADER */}
      <div className="bg-slate-100 px-6 py-4 border-b border-slate-200">
        <div className="flex flex-wrap justify-between items-center gap-4">
          <div className="flex flex-wrap gap-6 text-xs font-bold text-slate-600">
            <span className="flex items-center gap-2"><Database size={16} className="text-blue-600"/><span className="text-slate-400">Portal:</span> {bid.portal}</span>
            <span className="flex items-center gap-2"><Hash size={16} className="text-indigo-600"/><span className="text-slate-400">Licitacao:</span> {bid.licitacao_num}</span>
            <span className="flex items-center gap-2 bg-blue-100 px-3 py-1 rounded-full"><Building size={16} className="text-blue-700"/><span className="text-blue-700 font-black">UASG: {bid.uasg}</span></span>
            <span className="flex items-center gap-2"><Tag size={16} className="text-emerald-600"/><span className="text-slate-400">Modalidade:</span> {bid.modalidade}</span>
          </div>
          <div className="flex items-center gap-3">
            <span className={`px-3 py-1 rounded-full text-xs font-black uppercase ${bid.status === 'ATIVA' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>{bid.status}</span>
            <button className="p-2 text-slate-400 hover:text-yellow-500 transition-all"><Star size={20}/></button>
          </div>
        </div>
      </div>

      {/* CORPO */}
      <div className="p-6">
        <div className="mb-4">
          <h2 className="text-sm font-black text-blue-600 uppercase tracking-wide flex items-center gap-2">
            <MapPin size={16}/> {bid.cidade} - {bid.uf} / {bid.orgao}
          </h2>
        </div>
        <h3 className="text-xl font-black text-slate-800 leading-tight mb-6">
          {highlightText(bid.objeto, searchTerm)}
        </h3>

        {/* DATAS E VALORES */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-slate-50 p-4 rounded-xl">
            <p className="text-xs font-bold text-slate-400 uppercase mb-1 flex items-center gap-1"><Calendar size={12}/> Data Publicacao</p>
            <p className="text-sm font-black text-slate-700">{bid.data_publicacao}</p>
          </div>
          <div className="bg-red-50 p-4 rounded-xl border border-red-100">
            <p className="text-xs font-bold text-red-400 uppercase mb-1 flex items-center gap-1"><Clock size={12}/> Prazo Limite</p>
            <p className="text-sm font-black text-red-600">{bid.data_final !== '-' ? bid.data_final : bid.data_abertura}</p>
          </div>
          <div className="bg-slate-50 p-4 rounded-xl">
            <p className="text-xs font-bold text-slate-400 uppercase mb-1">ID GSM</p>
            <p className="text-sm font-bold text-slate-600">{bid.id_gsm}</p>
          </div>
          <div className="bg-blue-50 p-4 rounded-xl border border-blue-100">
            <p className="text-xs font-bold text-blue-400 uppercase mb-1 flex items-center gap-1"><DollarSign size={12}/> Valor Estimado</p>
            <p className="text-lg font-black text-blue-700">{bid.valor_total}</p>
          </div>
        </div>

        {/* VER ITENS */}
        <div className="mb-6">
          <button data-testid={`ver-itens-btn-${bid.id}`}
            onClick={async () => {
              const newState = !expandedItens[bid.id];
              setExpandedItens(prev => ({...prev, [bid.id]: newState ? 'loading' : false}));
              if (newState && bid.pncp_cnpj && bid.pncp_ano && bid.pncp_seq && bid.itens.length === 0 && !bid.itens_texto) {
                try {
                  const res = await axios.get(`${API}/editais/itens/${bid.pncp_cnpj}/${bid.pncp_ano}/${bid.pncp_seq}`);
                  const itensApi = (res.data.itens || []).map((it, idx) => ({
                    numero: it.numero || String(idx + 1), descricao: it.descricao || '',
                    quantidade: it.quantidade || '-', unidade: it.unidade || 'UN',
                    valor_total: it.valor_total ? `R$ ${Number(it.valor_total).toLocaleString('pt-BR', {minimumFractionDigits: 2})}` : '-'
                  }));
                  setResults(prev => prev.map(b => b.id === bid.id ? {...b, itens: itensApi} : b));
                } catch (err) { /* fallback */ }
              }
              setExpandedItens(prev => ({...prev, [bid.id]: newState}));
            }}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-50 text-indigo-700 rounded-lg font-bold text-sm hover:bg-indigo-100 transition-all border border-indigo-200"
          >
            <Package size={16}/>
            {expandedItens[bid.id] ? 'Ocultar Itens' : 'Ver Itens'}
            <ChevronRight size={14} className={`transition-transform ${expandedItens[bid.id] ? 'rotate-90' : ''}`}/>
          </button>

          {expandedItens[bid.id] && (
            <ExpandedItems bid={bid} searchTerm={searchTerm} expandedItens={expandedItens} setExpandedItens={setExpandedItens} />
          )}
        </div>

        {/* DOWNLOAD */}
        {getBidDownloadUrl(bid) !== '#' ? (
          <button data-testid={`download-edital-${bid.id}`}
            onClick={async (e) => {
              const btn = e.currentTarget;
              if (btn.dataset.loading === 'true') return;
              btn.dataset.loading = 'true';
              const origHTML = btn.innerHTML;
              btn.innerHTML = '<svg class="animate-spin h-5 w-5 mr-2" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg> BAIXANDO EDITAL...';
              btn.style.opacity = '0.7'; btn.style.pointerEvents = 'none';
              const url = getBidDownloadUrl(bid);
              // O nosso proxy (/api/editais/download/...) as vezes recebe do
              // PNCP um corpo JSON de erro em vez do arquivo real. Como esse
              // caso ainda responde HTTP 200 as vezes, validamos a resposta
              // antes de salvar - sem isso o navegador baixaria o JSON como
              // se fosse o edital, sem nenhum aviso de erro.
              const isNossoProxy = url.includes('/api/editais/download/');
              try {
                if (isNossoProxy) {
                  const res = await axios.get(url, { responseType: 'blob', validateStatus: () => true });
                  const contentType = (res.headers['content-type'] || '').toLowerCase();
                  if (res.status !== 200 || contentType.includes('json')) {
                    throw new Error('Falha ao baixar o edital');
                  }
                  const blobUrl = window.URL.createObjectURL(res.data);
                  const cd = res.headers['content-disposition'] || '';
                  const match = cd.match(/filename="?([^";]+)"?/);
                  const link = document.createElement('a');
                  link.href = blobUrl;
                  link.download = match ? decodeURIComponent(match[1]) : `edital_${bid.id}.pdf`;
                  document.body.appendChild(link); link.click(); document.body.removeChild(link);
                  window.URL.revokeObjectURL(blobUrl);
                } else {
                  // Fallback externo (ex: pagina do edital no site do PNCP,
                  // quando nao temos o link direto do arquivo) - abre numa
                  // nova aba, sem validar conteudo.
                  const link = document.createElement('a');
                  link.href = url; link.target = '_blank'; link.rel = 'noopener noreferrer';
                  document.body.appendChild(link); link.click(); document.body.removeChild(link);
                }
                btn.innerHTML = '<svg class="h-5 w-5 mr-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M5 13l4 4L19 7"/></svg> DOWNLOAD INICIADO!';
                btn.style.opacity = '1'; btn.className = btn.className.replace('bg-emerald-600', 'bg-green-500');
                await new Promise(r => setTimeout(r, 2000));
              } catch (err) {
                toast.error('Não foi possível baixar o edital agora. Tente novamente ou abra direto no site do PNCP.');
              }
              btn.innerHTML = origHTML; btn.style.opacity = '1'; btn.style.pointerEvents = 'auto';
              btn.className = btn.className.replace('bg-green-500', 'bg-emerald-600'); btn.dataset.loading = 'false';
            }}
            className="w-full flex items-center justify-center gap-3 bg-emerald-600 text-white py-4 rounded-xl font-black text-sm hover:bg-emerald-700 transition-all shadow-lg active:scale-95 cursor-pointer border-0"
          >
            <Download size={20}/> BAIXAR EDITAL OFICIAL (PDF/ZIP)
          </button>
        ) : (
          <div className="w-full flex items-center justify-center gap-3 bg-slate-400 text-white py-4 rounded-xl font-black text-sm cursor-not-allowed">
            <Download size={20}/> EDITAL INDISPONIVEL
          </div>
        )}
      </div>
    </div>
  );
}

function ExpandedItems({ bid, searchTerm, expandedItens, setExpandedItens }) {
  if (expandedItens[bid.id] === 'loading') {
    return <div className="mt-3 border border-slate-200 rounded-xl p-6 text-center text-slate-400">Carregando itens do PNCP...</div>;
  }

  if (bid.itens.length > 0) {
    const termoBusca = searchTerm ? searchTerm.toLowerCase().split(/\s+/).filter(p => p.length >= 3) : [];
    let itensMatch = [], itensOutros = [];
    if (termoBusca.length > 0) {
      bid.itens.forEach(item => {
        const desc = (item.descricao || '').toLowerCase();
        (termoBusca.some(p => desc.includes(p)) ? itensMatch : itensOutros).push(item);
      });
    } else {
      itensOutros = bid.itens;
    }
    const showAll = expandedItens[bid.id] === 'all';

    return (
      <div className="mt-3 border border-slate-200 rounded-xl overflow-hidden">
        {itensMatch.length > 0 && (
          <div className="bg-emerald-50 border-b-2 border-emerald-300">
            <p className="px-4 py-2 text-xs font-black text-emerald-700 uppercase bg-emerald-100">
              {itensMatch.length} item(ns) com "{searchTerm}" (de {bid.itens.length} itens totais)
            </p>
            <ItemsTable items={itensMatch} bid={bid} searchTerm={searchTerm} variant="match" />
          </div>
        )}
        {itensOutros.length > 0 && (
          <div>
            {(showAll || itensMatch.length === 0) && (
              <ItemsTable
                items={itensMatch.length === 0 && !showAll ? itensOutros.slice(0, 15) : itensOutros}
                bid={bid} searchTerm={searchTerm} variant="other"
              />
            )}
            {itensMatch.length > 0 && !showAll && (
              <button onClick={() => setExpandedItens(prev => ({...prev, [bid.id]: 'all'}))}
                className="w-full py-2 text-xs font-bold text-slate-500 hover:text-blue-600 hover:bg-blue-50 transition-all">
                Ver todos os {itensOutros.length} itens restantes
              </button>
            )}
            {itensMatch.length === 0 && !showAll && itensOutros.length > 15 && (
              <button onClick={() => setExpandedItens(prev => ({...prev, [bid.id]: 'all'}))}
                className="w-full py-2 text-xs font-bold text-slate-500 hover:text-blue-600 hover:bg-blue-50 transition-all">
                Ver todos os {itensOutros.length} itens (+{itensOutros.length - 15} restantes)
              </button>
            )}
          </div>
        )}
      </div>
    );
  }

  if (bid.itens_texto) {
    return (
      <div className="mt-3 border border-slate-200 rounded-xl p-4 bg-slate-50 max-h-64 overflow-y-auto">
        <p className="text-xs font-bold text-slate-400 uppercase mb-2">Itens do Edital:</p>
        <div className="text-sm text-slate-700 leading-relaxed whitespace-pre-line">
          {highlightText(bid.itens_texto, searchTerm)}
        </div>
      </div>
    );
  }

  return <div className="mt-3 border border-slate-200 rounded-xl p-4 text-center text-slate-400 text-sm">Nenhum item encontrado para este edital</div>;
}

function ItemsTable({ items, bid, searchTerm, variant }) {
  const isMatch = variant === 'match';
  return (
    <table className="w-full text-sm">
      <thead className={isMatch ? 'bg-emerald-100' : 'bg-slate-100'}>
        <tr className={`text-xs font-black uppercase tracking-wider ${isMatch ? 'text-emerald-600' : 'text-slate-500'}`}>
          <th className="px-4 py-2 text-left">Item</th>
          <th className="px-4 py-2 text-left">Descricao</th>
          <th className="px-4 py-2 text-right">Qtd</th>
          <th className="px-4 py-2 text-right">Valor</th>
        </tr>
      </thead>
      <tbody className={`divide-y ${isMatch ? 'divide-emerald-100' : 'divide-slate-100'}`}>
        {items.map((item, idx) => (
          <tr key={`${variant}-${bid.id}-${idx}`} className={isMatch ? 'bg-emerald-50/50' : 'hover:bg-slate-50'}>
            <td className={`px-4 py-3 font-black ${isMatch ? 'text-emerald-700' : 'text-blue-600'}`}>#{item.numero}</td>
            <td className="px-4 py-3 font-semibold text-slate-800">{highlightText(item.descricao, searchTerm)}</td>
            <td className="px-4 py-3 text-right font-bold">{item.quantidade} {item.unidade}</td>
            <td className="px-4 py-3 text-right font-black">{item.valor_total}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
