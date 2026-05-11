import { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export function useAnvisa() {
  const [anvisaAlertas, setAnvisaAlertas] = useState([]);
  const [anvisaStats, setAnvisaStats] = useState(null);
  const [anvisaLoading, setAnvisaLoading] = useState(false);
  const [anvisaAtualizando, setAnvisaAtualizando] = useState(false);
  const [anvisaCruzamento, setAnvisaCruzamento] = useState(null);
  const [anvisaCruzando, setAnvisaCruzando] = useState(false);
  const [anvisaBuscaTermo, setAnvisaBuscaTermo] = useState('');
  const [anvisaBuscaResultados, setAnvisaBuscaResultados] = useState(null);
  const [anvisaBuscaLoading, setAnvisaBuscaLoading] = useState(false);

  const carregarAnvisa = async () => {
    setAnvisaLoading(true);
    try {
      const res = await axios.get(`${API}/anvisa/alertas`);
      setAnvisaAlertas(res.data.alertas || []);
      setAnvisaStats(res.data.estatisticas || null);
    } catch (err) {
      console.error('Erro ao carregar ANVISA:', err);
    } finally {
      setAnvisaLoading(false);
    }
  };

  const atualizarAnvisa = async () => {
    setAnvisaAtualizando(true);
    try {
      await axios.post(`${API}/anvisa/atualizar`);
      toast.info('Coleta ANVISA + DOU iniciada. Aguarde ~60s...');
      let attempts = 0;
      const pollInterval = setInterval(async () => {
        attempts++;
        try {
          await carregarAnvisa();
          if (attempts >= 9) {
            clearInterval(pollInterval);
            setAnvisaAtualizando(false);
            toast.success('ANVISA atualizada!');
          }
        } catch (e) { /* ignore */ }
      }, 10000);
      setTimeout(() => {
        clearInterval(pollInterval);
        setAnvisaAtualizando(false);
        carregarAnvisa();
      }, 90000);
    } catch (err) {
      console.error('Erro ao atualizar ANVISA:', err);
      toast.error('Erro ao atualizar ANVISA');
      setAnvisaAtualizando(false);
    }
  };

  const cruzarLicitacoes = async () => {
    setAnvisaCruzando(true);
    try {
      const res = await axios.post(`${API}/anvisa/cruzar-licitacoes`);
      setAnvisaCruzamento(res.data);
      const total = res.data.resumo?.medicamentos_com_licitacao || 0;
      if (total > 0) {
        toast.success(`${total} medicamento(s) com licitacoes encontradas!`);
      } else {
        toast.info('Nenhuma licitacao encontrada para os medicamentos em alerta');
      }
    } catch (err) {
      console.error('Erro ao cruzar licitacoes:', err);
      toast.error('Erro ao buscar licitacoes');
    } finally {
      setAnvisaCruzando(false);
    }
  };

  const buscarMedicamentoAnvisa = async () => {
    if (!anvisaBuscaTermo.trim()) {
      toast.warning('Digite o nome do medicamento');
      return;
    }
    setAnvisaBuscaLoading(true);
    setAnvisaBuscaResultados(null);
    try {
      const res = await axios.get(`${API}/anvisa/buscar-medicamento`, { params: { q: anvisaBuscaTermo.trim() } });
      setAnvisaBuscaResultados(res.data);
      if (res.data.total > 0) {
        toast.success(`${res.data.total} resultado(s) encontrado(s) para "${anvisaBuscaTermo}"`);
      } else {
        toast.info(`Nenhum resultado para "${anvisaBuscaTermo}"`);
      }
    } catch (err) {
      console.error('Erro busca medicamento:', err);
      toast.error('Erro na busca de medicamento');
    } finally {
      setAnvisaBuscaLoading(false);
    }
  };

  return {
    anvisaAlertas, anvisaStats, anvisaLoading,
    anvisaAtualizando, anvisaCruzamento, anvisaCruzando,
    anvisaBuscaTermo, setAnvisaBuscaTermo,
    anvisaBuscaResultados, setAnvisaBuscaResultados,
    anvisaBuscaLoading,
    carregarAnvisa, atualizarAnvisa, cruzarLicitacoes, buscarMedicamentoAnvisa,
  };
}
