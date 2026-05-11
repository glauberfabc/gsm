import { useState, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export function useRadarLmr() {
  const [oportunidades, setOportunidades] = useState(null);
  const [loading, setLoading] = useState(false);
  const [analiseDetalhe, setAnaliseDetalhe] = useState(null);
  const [analiseLoading, setAnaliseLoading] = useState(false);
  const [alertaAberto, setAlertaAberto] = useState(null);
  const [alertaLoading, setAlertaLoading] = useState(false);

  const carregarOportunidades = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/dama/lmr-analysis?limite=30`);
      setOportunidades(res.data);
      const total = res.data.total || 0;
      if (total > 0) {
        toast.success(`Radar LMR: ${total} oportunidade(s) identificada(s)`);
      } else {
        toast.info('Radar LMR: Nenhuma oportunidade identificada. Atualize a base ANVISA.');
      }
    } catch (err) {
      console.error('Erro ao carregar radar LMR:', err);
      toast.error('Erro ao carregar oportunidades LMR');
    } finally {
      setLoading(false);
    }
  }, []);

  const analisarMedicamento = useCallback(async (medicamento, precoReferencia = 0, tipoProduto = 'sintetico') => {
    if (!medicamento?.trim()) {
      toast.warning('Informe o medicamento para analise');
      return null;
    }
    setAnaliseLoading(true);
    setAnaliseDetalhe(null);
    try {
      const res = await axios.post(`${API}/dama/lmr-analise-medicamento`, {
        medicamento,
        preco_referencia: precoReferencia,
        tipo_produto: tipoProduto,
      });
      setAnaliseDetalhe(res.data);
      return res.data;
    } catch (err) {
      console.error('Erro na analise LMR:', err);
      toast.error('Erro na analise LMR');
      return null;
    } finally {
      setAnaliseLoading(false);
    }
  }, []);

  const carregarAlertaPorId = useCallback(async (alertaId) => {
    if (!alertaId) return;
    setAlertaLoading(true);
    setAlertaAberto(null);
    try {
      const res = await axios.get(`${API}/notificacoes/oportunidades/${alertaId}`);
      setAlertaAberto(res.data);
      // Se veio com analise_lmr, setar como detalhe
      if (res.data.analise_lmr) {
        setAnaliseDetalhe(res.data.analise_lmr);
      }
      toast.success(`Alerta LMR carregado: ${res.data.alerta?.medicamento || 'N/A'}`);
    } catch (err) {
      console.error('Erro ao carregar alerta:', err);
      toast.error('Alerta nao encontrado ou expirado');
      // Fallback: tentar mostrar dados basicos
      setAlertaAberto({ alerta: { id: alertaId, erro: true }, analise_lmr: null });
    } finally {
      setAlertaLoading(false);
    }
  }, []);

  const fecharAlerta = useCallback(() => {
    setAlertaAberto(null);
  }, []);

  return {
    oportunidades, loading, analiseDetalhe, analiseLoading,
    alertaAberto, alertaLoading,
    carregarOportunidades, analisarMedicamento, setAnaliseDetalhe,
    carregarAlertaPorId, fecharAlerta,
  };
}
