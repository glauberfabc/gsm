import { useState } from 'react';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export function useSearch() {
  const [searchTerm, setSearchTerm] = useState('');
  const [searchCity, setSearchCity] = useState('');
  const [selectedUF, setSelectedUF] = useState('');
  const [selectedRadarId, setSelectedRadarId] = useState(null);
  const [results, setResults] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [totalResults, setTotalResults] = useState(0);
  const [expandedItens, setExpandedItens] = useState({});
  const [isSmartSearch, setIsSmartSearch] = useState(false);
  
  // Paginação
  const [perPage, setPerPage] = useState(25);
  const [currentPage, setCurrentPage] = useState(1);
  const [paginationInfo, setPaginationInfo] = useState(null);

  const executarBusca = async (termo, cidade, uf, smart = false, page = 1) => {
    if (!termo && !cidade) return;
    setIsLoading(true);
    try {
      const params = new URLSearchParams();
      if (termo) params.append('q', termo);
      if (cidade) params.append('municipio', cidade);
      if (uf) params.append('estados', uf);
      if (smart) params.append('smart_search', 'true');
      params.append('limit', perPage);
      params.append('page', page || currentPage);
      
      const res = await axios.get(`${API}/search/unified?${params.toString()}`);
      const resultados = res.data.resultados || [];
      setTotalResults(res.data.total || resultados.length);
      setPaginationInfo(res.data.pagination || null);
      if (page) setCurrentPage(page);
      
      setResults(resultados.map(e => ({
        id: e.id || e.id_gsm || e.hash_dedup || e.id_externo || `${Date.now()}-${Math.random()}`,
        portal: (e.portal_captura || e.fonte || 'PNCP').replace(/AGREGADOR\//g, ''),
        uasg: e.uasg || e.dados_orgao?.cnpj || e.cnpj_orgao || e.codigo_uasg || 'N/A',
        licitacao_num: e.numero_processo || e.numero_licitacao || e.numero_compra || 'N/A',
        modalidade: e.modalidade || 'Pregao Eletronico',
        orgao: e.orgao || e.nome_orgao || 'Orgao nao informado',
        cidade: e.municipio || e.cidade || '',
        uf: e.uf || e.estado || '',
        objeto: e.objeto || e.descricao || e.medicamento || 'Objeto nao informado',
        data_publicacao: e.data_publicacao ? new Date(e.data_publicacao).toLocaleDateString('pt-BR') : '-',
        data_abertura: e.data_abertura ? new Date(e.data_abertura).toLocaleString('pt-BR') : '-',
        data_final: (e.data_encerramento || e.data_final) ? new Date(e.data_encerramento || e.data_final).toLocaleString('pt-BR') : '-',
        valor_total: (e.valor_total || e.valor_total_estimado) ? `R$ ${Number(e.valor_total || e.valor_total_estimado).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}` : 'A definir',
        valor_estimado: e.valor_estimado ? `R$ ${Number(e.valor_estimado).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}` : null,
        link_portal: e.link_portal || e.link_origem || e.link_edital || e.link_documento || e.url || '#',
        link_documento: e.link_documento || e.link_edital || null,
        link_origem: e.link_origem || e.link_portal || e.url || '#',
        link_pdf: e.link_pdf || null,
        status: e.status_oportunidade || e.status || 'ATIVA',
        situacao: e.situacao || '',
        id_gsm: e.id_externo || e.id_gsm || e.hash_dedup || '-',
        id_externo: e.id_externo || '',
        perfil_busca: termo || 'Busca Direta',
        fonte_origem: e.fonte_origem || '',
        anexos: e.anexos || [],
        pncp_cnpj: e._pncp_cnpj || '',
        pncp_ano: e._pncp_ano || '',
        pncp_seq: e._pncp_seq || '',
        itens_texto: typeof e.itens === 'string' && e.itens.length > 5 ? e.itens : null,
        itens: Array.isArray(e.itens_correspondentes) && e.itens_correspondentes.length > 0
          ? e.itens_correspondentes.map((it, idx) => ({
              grupo: it.grupo || '1',
              numero: it.numero_item || String(idx + 1),
              descricao: it.descricao || it.nome || 'Item',
              exclusivo_mpe: it.exclusivo_mpe ? 'Sim' : 'Nao',
              quantidade: it.quantidade || it.qtd || '-',
              unidade: it.unidade || 'UN',
              valor_unitario: it.valor_unitario ? `R$ ${Number(it.valor_unitario).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}` : '-',
              valor_total: it.valor_total ? `R$ ${Number(it.valor_total).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}` : '-'
            }))
          : []
      })));
    } catch (err) {
      console.error('Erro na busca:', err);
      setResults([]);
    } finally { 
      setIsLoading(false); 
    }
  };

  const handleSelectRadar = (id, keywords) => {
    setSelectedRadarId(id);
    setSearchCity('');
    setSelectedUF('');
    if (keywords) {
      setSearchTerm(keywords);
      executarBusca(keywords, '', '');
    } else {
      setSearchTerm('');
    }
  };

  const handleManualTyping = (val) => {
    setSearchTerm(val);
    if (val !== '') setSelectedRadarId(null);
  };

  const getBidDownloadUrl = (bid) => {
    if (bid.link_pdf && bid.link_pdf.startsWith('/api/')) return `${API}${bid.link_pdf.replace('/api', '')}`;
    if (bid.link_pdf && bid.link_pdf.startsWith('http')) return bid.link_pdf;
    let url = bid.link_portal || bid.link_edital || bid.link_origem || bid.link_documento || '#';
    if (url.includes('pncp.gov.br/app/compras/')) {
      url = url.replace('/app/compras/', '/app/editais/');
    }
    return url;
  };

  return {
    searchTerm, setSearchTerm,
    searchCity, setSearchCity,
    selectedUF, setSelectedUF,
    selectedRadarId, setSelectedRadarId,
    results, setResults,
    isLoading, totalResults,
    expandedItens, setExpandedItens,
    isSmartSearch, setIsSmartSearch,
    executarBusca, handleSelectRadar, handleManualTyping, getBidDownloadUrl,
    perPage, setPerPage,
    currentPage, setCurrentPage,
    paginationInfo,
    API,
  };
}
