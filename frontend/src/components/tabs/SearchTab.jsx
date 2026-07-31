import React from 'react';
import { Search, Info, Sparkles, Package, MapPin, Globe, Loader2, Radar, CheckCircle, Database, Hash, Building, Tag, Star, Calendar, Clock, DollarSign, ChevronRight, Download } from 'lucide-react';
import { HighlightText } from '../common/HighlightText';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export function SearchTab({
  searchTerm, setSearchTerm, searchCity, setSearchCity,
  selectedUF, setSelectedUF, selectedRadarId,
  results, setResults, isLoading, totalResults,
  expandedItens, setExpandedItens,
  isSmartSearch, setIsSmartSearch,
  executarBusca, handleManualTyping, handleSelectRadar, getBidDownloadUrl,
  radaresAtalho,
  perPage, setPerPage,
  currentPage, setCurrentPage,
  paginationInfo,
}) {
  const highlightText = (text, highlight) => <HighlightText text={text} highlight={highlight} />;

  return (
    <div className="space-y-8">
      {/* PAINEL DE FILTROS */}
      <div className="bg-white p-8 rounded-3xl shadow-xl border border-slate-200">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
          <div className="md:col-span-4 relative">
            <label className="block text-xs font-black text-slate-500 uppercase tracking-wider mb-2 ml-2">
              <Package size={14} className="inline mr-1"/> Medicamento / Produto / NCM
            </label>
            <div className="relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={20} />
              <input 
                type="text" 
                placeholder="Ex: Insulina, Canabidiol, Prolia..." 
                className="w-full pl-12 pr-4 py-4 bg-slate-50 border-2 border-slate-200 rounded-xl font-semibold text-lg focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none transition-all" 
                value={searchTerm} 
                onChange={(e) => handleManualTyping(e.target.value)} 
                onFocus={() => setSearchTerm('')}
                data-testid="search-input"
              />
            </div>
          </div>
          <div className="md:col-span-3 relative">
            <label className="block text-xs font-black text-slate-500 uppercase tracking-wider mb-2 ml-2">
              <MapPin size={14} className="inline mr-1"/> Municipio / Cidade
            </label>
            <div className="relative">
              <MapPin className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={20} />
              <input 
                type="text" placeholder="Ex: Sao Paulo, Barretos..." 
                className="w-full pl-12 pr-4 py-4 bg-slate-50 border-2 border-slate-200 rounded-xl font-semibold text-lg focus:border-blue-500 outline-none transition-all" 
                value={searchCity} onChange={(e) => setSearchCity(e.target.value)} 
              />
            </div>
          </div>
          <div className="md:col-span-1">
            <label className="block text-xs font-black text-slate-500 uppercase tracking-wider mb-2 ml-2">
              <Globe size={14} className="inline mr-1"/> UF
            </label>
            <select 
              className="w-full py-4 px-3 bg-slate-50 border-2 border-slate-200 rounded-xl font-semibold text-base focus:border-blue-500 outline-none transition-all cursor-pointer truncate" 
              value={selectedUF} onChange={(e) => setSelectedUF(e.target.value)} style={{ minWidth: '120px' }}
            >
              <option value="">Todos</option>
              {['AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO'].map(uf => (
                <option key={uf} value={uf}>{uf}</option>
              ))}
            </select>
          </div>
          <div className="md:col-span-4 flex items-end gap-3">
            {/* TOGGLE SMART SEARCH */}
            <div className="flex flex-col items-center mb-1 bg-slate-50 p-2 rounded-xl border border-slate-200 min-w-[70px]">
              <div className="flex items-center gap-1 mb-1">
                <span className="text-[9px] font-black text-slate-400 uppercase tracking-tighter">Smart</span>
                <div className="relative group">
                  <Info size={12} className="text-slate-300 hover:text-blue-500 cursor-help transition-colors"/>
                  <div className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 w-48 p-3 bg-slate-900 text-white text-[10px] rounded-xl shadow-2xl z-[100] hidden group-hover:block border border-slate-700 leading-relaxed animate-in fade-in zoom-in-95">
                    <span className="text-blue-400 font-bold block mb-1">BUSCA INTELIGENTE GSM</span>
                    Ativa o processamento de linguagem natural: ignora acentos, resolve plural/singular e variações de gênero.
                  </div>
                </div>
              </div>
              <button 
                onClick={() => setIsSmartSearch(!isSmartSearch)}
                className={`relative w-10 h-5 rounded-full transition-all duration-300 ${isSmartSearch ? 'bg-blue-600 shadow-inner' : 'bg-slate-300'}`}
              >
                <div className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow-md transition-all duration-300 transform ${isSmartSearch ? 'translate-x-5' : 'translate-x-0'}`}></div>
              </button>
            </div>

            {/* BOTAO PESQUISAR */}
            <button 
              onClick={() => executarBusca(searchTerm, searchCity, selectedUF, isSmartSearch)} disabled={isLoading}
              className={`flex-1 py-4 rounded-xl font-black uppercase text-sm shadow-lg transition-all active:scale-95 disabled:opacity-50 flex items-center justify-center gap-2 ${isSmartSearch ? 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white' : 'bg-slate-800 text-white'}`}
              data-test-id="search-btn"
            >
              {isLoading ? <Loader2 className="animate-spin" size={20}/> : (isSmartSearch ? <Sparkles size={20}/> : <Search size={20}/>)}
              {isLoading ? 'Buscando...' : 'Pesquisar'}
            </button>
          </div>
        </div>
      </div>

      {/* RADARES DE ATALHO */}
      <div className="flex flex-wrap gap-3 px-2">
        <p className="text-xs font-black text-slate-400 uppercase tracking-widest w-full mb-1 flex items-center gap-2">
          <Radar size={16}/> Radares de Atalho / Perfis de Busca:
        </p>
        {radaresAtalho.map(r => (
          <button key={r.id} onClick={() => handleSelectRadar(r.id, r.keywords)}
            className={`px-5 py-2 rounded-full border-2 text-xs font-black uppercase tracking-wider transition-all ${selectedRadarId === r.id ? 'bg-blue-600 text-white border-blue-500 shadow-lg' : 'bg-white text-slate-500 border-slate-200 hover:border-blue-300 hover:text-blue-600'}`}>
            {r.name}
          </button>
        ))}
      </div>

      {/* CONTADOR */}
      {results.length > 0 && (
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 px-2">
          <div className="flex items-center gap-4">
            <p className="text-sm font-bold text-slate-600">
              <CheckCircle size={16} className="inline mr-2 text-emerald-500"/>
              <span className="text-2xl font-black text-slate-800">{totalResults}</span> editais encontrados
            </p>
            
            {/* Seletor de Resultados por Página (Topo) */}
            <div className="flex items-center gap-2 bg-slate-100 px-3 py-1.5 rounded-lg border border-slate-200">
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-tighter">Mostrar:</span>
              <select
                value={perPage}
                onChange={(e) => {
                  const val = parseInt(e.target.value);
                  setPerPage(val);
                  // O hook usará o novo perPage na busca
                  setTimeout(() => executarBusca(searchTerm, searchCity, selectedUF, isSmartSearch, 1), 10);
                }}
                className="text-xs font-bold text-blue-700 bg-transparent focus:outline-none cursor-pointer"
              >
                <option value={15}>15 por página</option>
                <option value={20}>20 por página</option>
                <option value={25}>25 por página</option>
                <option value={50}>50 por página</option>
                <option value={100}>100 por página</option>
                <option value={250}>250 por página</option>
              </select>
            </div>
          </div>

          <div className="flex flex-col items-end">
             <p className="text-xs text-slate-400">
              Perfil: <span className="font-bold text-blue-600">{searchTerm || 'Todos'}</span>
            </p>
            {paginationInfo && paginationInfo.total_pages > 1 && (
              <p className="text-[10px] font-bold text-slate-300 uppercase mt-1">
                Página {currentPage} de {paginationInfo.total_pages}
              </p>
            )}
          </div>
        </div>
      )}

      {/* RESULTADOS */}
      <div className="space-y-6">
        {isLoading ? (
          <div className="py-20 text-center">
            <Loader2 className="animate-spin mx-auto text-blue-500 mb-4" size={48}/>
            <p className="text-slate-400 font-bold uppercase tracking-wider">Buscando editais em todas as fontes...</p>
            <p className="text-xs text-slate-300 mt-2">PNCP - ComprasNet - BNC - Portais Estaduais</p>
          </div>
        ) : results.length > 0 ? (
          results.map(bid => (
            <BidCard 
              key={bid.id} bid={bid} searchTerm={searchTerm}
              expandedItens={expandedItens} setExpandedItens={setExpandedItens}
              setResults={setResults} getBidDownloadUrl={getBidDownloadUrl}
              highlightText={highlightText}
            />
          ))
        ) : (
          <div className="py-20 text-center text-slate-300 border-2 border-dashed border-slate-200 rounded-3xl">
            <Search size={48} className="mx-auto mb-4 opacity-50"/>
            <p className="font-black uppercase tracking-wider text-sm">Digite um termo, cidade ou estado e clique em Pesquisar</p>
            <p className="text-xs mt-2">Use os filtros: Medicamento, Municipio ou Estado (isoladamente ou combinados)</p>
          </div>
        )}
      </div>

      {/* PAGINAÇÃO INFERIOR */}
      {paginationInfo && paginationInfo.total_pages > 1 && (
        <div className="flex flex-col md:flex-row justify-center items-center gap-6 mt-12 pb-10 border-t border-slate-100 pt-10">
          {/* Info */}
          <div className="flex items-center gap-2 bg-slate-50 px-4 py-2 rounded-xl border border-slate-200">
            <span className="text-xs font-black text-slate-400 uppercase tracking-widest">Página</span>
            <span className="text-lg font-black text-blue-600">{currentPage}</span>
            <span className="text-xs font-black text-slate-300">/</span>
            <span className="text-sm font-black text-slate-400">{paginationInfo.total_pages}</span>
          </div>

          {/* Controles */}
          <div className="flex items-center gap-3">
            <button
              onClick={() => executarBusca(searchTerm, searchCity, selectedUF, isSmartSearch, 1)}
              disabled={currentPage === 1}
              className="px-4 py-3 bg-white border-2 border-slate-200 rounded-xl disabled:opacity-30 disabled:cursor-not-allowed hover:border-blue-500 hover:text-blue-600 transition-all font-black text-xs uppercase shadow-sm"
              title="Primeira Página"
            >
              Primeira
            </button>

            <button
              onClick={() => executarBusca(searchTerm, searchCity, selectedUF, isSmartSearch, currentPage - 1)}
              disabled={!paginationInfo.has_prev}
              className="p-3 bg-white border-2 border-slate-200 rounded-xl disabled:opacity-30 disabled:cursor-not-allowed hover:border-blue-500 hover:text-blue-600 transition-all shadow-sm"
            >
              <ChevronRight size={24} className="rotate-180" />
            </button>

            <button
              onClick={() => executarBusca(searchTerm, searchCity, selectedUF, isSmartSearch, currentPage + 1)}
              disabled={!paginationInfo.has_next}
              className="px-6 py-3 bg-blue-600 text-white rounded-xl disabled:bg-slate-200 disabled:cursor-not-allowed hover:bg-blue-700 transition-all shadow-lg flex items-center gap-2 font-black uppercase text-xs tracking-wider"
            >
              Próxima <ChevronRight size={20} />
            </button>

            <button
              onClick={() => executarBusca(searchTerm, searchCity, selectedUF, isSmartSearch, paginationInfo.total_pages)}
              disabled={currentPage === paginationInfo.total_pages}
              className="px-4 py-3 bg-white border-2 border-slate-200 rounded-xl disabled:opacity-30 disabled:cursor-not-allowed hover:border-blue-500 hover:text-blue-600 transition-all font-black text-xs uppercase shadow-sm"
              title="Última Página"
            >
              Última
            </button>
          </div>

          {/* Seletor de Resultados por Página (Rodapé) */}
          <div className="flex items-center gap-2 bg-white px-4 py-2 rounded-xl border-2 border-slate-200 shadow-sm">
            <span className="text-[10px] font-black text-slate-400 uppercase tracking-tighter">Itens por página:</span>
            <select
              value={perPage}
              onChange={(e) => {
                const val = parseInt(e.target.value);
                setPerPage(val);
                setTimeout(() => executarBusca(searchTerm, searchCity, selectedUF, isSmartSearch, 1), 10);
              }}
              className="text-sm font-black text-blue-600 bg-transparent focus:outline-none cursor-pointer"
            >
              <option value={15}>15</option>
              <option value={20}>20</option>
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={250}>250</option>
            </select>
          </div>
        </div>
      )}
    </div>
  );
}

function BidCard({ bid, searchTerm, expandedItens, setExpandedItens, setResults, getBidDownloadUrl, highlightText }) {
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
            <ExpandedItems bid={bid} searchTerm={searchTerm} expandedItens={expandedItens} setExpandedItens={setExpandedItens} highlightText={highlightText} />
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
              try {
                const link = document.createElement('a');
                link.href = getBidDownloadUrl(bid); link.download = '';
                document.body.appendChild(link); link.click(); document.body.removeChild(link);
                await new Promise(r => setTimeout(r, 3000));
                btn.innerHTML = '<svg class="h-5 w-5 mr-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M5 13l4 4L19 7"/></svg> DOWNLOAD INICIADO!';
                btn.style.opacity = '1'; btn.className = btn.className.replace('bg-emerald-600', 'bg-green-500');
                await new Promise(r => setTimeout(r, 2000));
              } catch(err) {}
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

function ExpandedItems({ bid, searchTerm, expandedItens, setExpandedItens, highlightText }) {
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
            <ItemsTable items={itensMatch} bid={bid} searchTerm={searchTerm} highlightText={highlightText} variant="match" />
          </div>
        )}
        {itensOutros.length > 0 && (
          <div>
            {(showAll || itensMatch.length === 0) && (
              <ItemsTable 
                items={itensMatch.length === 0 && !showAll ? itensOutros.slice(0, 15) : itensOutros}
                bid={bid} searchTerm={searchTerm} highlightText={highlightText} variant="other"
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

function ItemsTable({ items, bid, searchTerm, highlightText, variant }) {
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
