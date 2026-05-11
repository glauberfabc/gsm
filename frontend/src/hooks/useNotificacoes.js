import { useState, useCallback, useEffect } from 'react';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export function useNotificacoes() {
  const [notificacoes, setNotificacoes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);

  const carregarNotificacoes = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/notificacoes/oportunidades?limite=15`);
      setNotificacoes(res.data.alertas || []);
    } catch (err) {
      console.error('Erro ao carregar notificacoes:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const marcarLida = useCallback(async (alertaId) => {
    try {
      await axios.post(`${API}/notificacoes/oportunidades/${alertaId}/lida`);
      setNotificacoes(prev => prev.map(n => n.id === alertaId ? { ...n, lida: true } : n));
    } catch (err) {
      console.error('Erro ao marcar notificacao:', err);
    }
  }, []);

  const naoLidas = notificacoes.filter(n => !n.lida).length;

  // Auto-load on mount
  useEffect(() => {
    carregarNotificacoes();
  }, [carregarNotificacoes]);

  return {
    notificacoes, loading, showDropdown, setShowDropdown,
    naoLidas, carregarNotificacoes, marcarLida,
  };
}
