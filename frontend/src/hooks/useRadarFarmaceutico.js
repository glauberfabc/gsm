import { useState, useCallback } from 'react';
import axios from 'axios';

const API_BASE = process.env.REACT_APP_BACKEND_URL;

export function useRadarFarmaceutico() {
  const [listaInteresse, setListaInteresse] = useState(null);
  const [desabastecimento, setDesabastecimento] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [scanLoading, setScanLoading] = useState(false);
  const [addLoading, setAddLoading] = useState(false);

  const carregarListaInteresse = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/api/radar-farmaceutico/lista-interesse`);
      setListaInteresse(res.data);
    } catch (e) {
      console.error('Erro ao carregar lista interesse:', e);
    }
  }, []);

  const carregarDesabastecimento = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API_BASE}/api/radar-farmaceutico/desabastecimento`);
      setDesabastecimento(res.data);
      setStats(res.data.estatisticas);
    } catch (e) {
      console.error('Erro ao carregar desabastecimento:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  const carregarStats = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/api/radar-farmaceutico/stats`);
      setStats(res.data);
    } catch (e) {
      console.error('Erro ao carregar stats:', e);
    }
  }, []);

  const adicionarInteresse = useCallback(async (item) => {
    setAddLoading(true);
    try {
      await axios.post(`${API_BASE}/api/radar-farmaceutico/lista-interesse`, item);
      await carregarListaInteresse();
      return true;
    } catch (e) {
      console.error('Erro ao adicionar interesse:', e);
      return false;
    } finally {
      setAddLoading(false);
    }
  }, [carregarListaInteresse]);

  const removerInteresse = useCallback(async (itemId) => {
    try {
      await axios.delete(`${API_BASE}/api/radar-farmaceutico/lista-interesse/${itemId}`);
      await carregarListaInteresse();
      return true;
    } catch (e) {
      console.error('Erro ao remover interesse:', e);
      return false;
    }
  }, [carregarListaInteresse]);

  const executarScan = useCallback(async () => {
    setScanLoading(true);
    try {
      await axios.post(`${API_BASE}/api/radar-farmaceutico/scan`);
      // Aguardar scan em background e recarregar
      setTimeout(async () => {
        await carregarDesabastecimento();
        await carregarStats();
        setScanLoading(false);
      }, 30000);
    } catch (e) {
      console.error('Erro ao executar scan:', e);
      setScanLoading(false);
    }
  }, [carregarDesabastecimento, carregarStats]);

  return {
    listaInteresse,
    desabastecimento,
    stats,
    loading,
    scanLoading,
    addLoading,
    carregarListaInteresse,
    carregarDesabastecimento,
    carregarStats,
    adicionarInteresse,
    removerInteresse,
    executarScan,
  };
}
