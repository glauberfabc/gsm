import { useState } from 'react';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export function usePrecos() {
  const [precosTermo, setPrecosTermo] = useState('');
  const [precosUF, setPrecosUF] = useState('');
  const [precosMeses, setPrecosMeses] = useState(12);
  const [loadingPrecos, setLoadingPrecos] = useState(false);
  const [precosResultados, setPrecosResultados] = useState([]);
  const [precosAgregacoes, setPrecosAgregacoes] = useState(null);
  const [precosTotalResultados, setPrecosTotalResultados] = useState(0);
  const [precosApresentacoes, setPrecosApresentacoes] = useState([]);
  const [precosApresentacaoAberta, setPrecosApresentacaoAberta] = useState(null);

  const buscarPrecos = async () => {
    if (!precosTermo.trim()) {
      alert('Digite um termo para pesquisar');
      return;
    }
    
    setLoadingPrecos(true);
    setPrecosResultados([]);
    setPrecosAgregacoes(null);
    setPrecosApresentacoes([]);
    setPrecosApresentacaoAberta(null);
    
    try {
      const params = new URLSearchParams();
      params.append('q', precosTermo);
      if (precosUF) params.append('uf', precosUF);
      params.append('limite', '200');
      params.append('use_cache', 'false');
      params.append('meses', precosMeses.toString());
      
      const response = await axios.get(`${API}/precos/search?${params.toString()}`);
      const data = response.data;
      
      setPrecosResultados(data.resultados || []);
      setPrecosAgregacoes(data.agregacoes || null);
      setPrecosTotalResultados(data.total || 0);
      setPrecosApresentacoes(data.apresentacoes || []);
      
      if (data.apresentacoes && data.apresentacoes.length > 0) {
        setPrecosApresentacaoAberta(data.apresentacoes[0].nome);
      }
      
    } catch (error) {
      console.error('Erro ao buscar precos:', error);
      alert('Erro ao buscar precos: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoadingPrecos(false);
    }
  };

  return {
    precosTermo, setPrecosTermo,
    precosUF, setPrecosUF,
    precosMeses, setPrecosMeses,
    loadingPrecos,
    precosResultados,
    precosAgregacoes,
    precosTotalResultados,
    precosApresentacoes,
    precosApresentacaoAberta, setPrecosApresentacaoAberta,
    buscarPrecos,
    API,
  };
}
