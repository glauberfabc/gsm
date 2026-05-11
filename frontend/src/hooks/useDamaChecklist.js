import { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export function useDamaChecklist() {
  const [checklistResultado, setChecklistResultado] = useState(null);
  const [checklistLoading, setChecklistLoading] = useState(false);
  const [checklistMedicamento, setChecklistMedicamento] = useState('');

  const executarChecklist = async (medicamento, normas = []) => {
    if (!medicamento?.trim()) {
      toast.warning('Informe o medicamento para o checklist');
      return null;
    }
    setChecklistLoading(true);
    setChecklistMedicamento(medicamento);
    setChecklistResultado(null);
    try {
      const res = await axios.post(`${API}/dama/checklist`, { medicamento, normas });
      setChecklistResultado(res.data);
      const score = res.data.score_conformidade || 0;
      if (score >= 75) {
        toast.success(`Checklist DAMA: ${score}% - Aprovado`);
      } else if (score >= 25) {
        toast.warning(`Checklist DAMA: ${score}% - Atencao: verificar alertas`);
      } else {
        toast.error(`Checklist DAMA: ${score}% - Bloqueios detectados`);
      }
      return res.data;
    } catch (err) {
      console.error('Erro no checklist DAMA:', err);
      toast.error('Erro ao executar checklist DAMA');
      return null;
    } finally {
      setChecklistLoading(false);
    }
  };

  const gerarProvaDocumental = async (resultado, empresaId = '') => {
    if (!resultado) {
      toast.warning('Selecione um resultado para gerar a prova documental');
      return;
    }
    try {
      toast.info('Gerando PDF de Prova Documental...');
      const response = await axios.post(`${API}/dama/prova-documental`, {
        medicamento: resultado.medicamento_detectado || resultado.titulo || '',
        fonte: resultado.fonte_busca || resultado.fonte || 'ANVISA/DOU',
        titulo: resultado.titulo || '',
        descricao: resultado.descricao || '',
        data_publicacao: resultado.data_publicacao || '',
        link: resultado.link || '',
        tipo_alerta: resultado.tipo_alerta || '',
        risco: resultado.risco || '',
        classificacao_dama: resultado.classificacao_dama || '',
        empresa_id: empresaId,
      }, { responseType: 'blob' });

      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      const nome = (resultado.titulo || 'prova').replace(/[^a-zA-Z0-9]/g, '_').substring(0, 30);
      a.href = url;
      a.download = `prova_documental_${nome}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      toast.success('PDF de Prova Documental baixado!');
    } catch (err) {
      console.error('Erro ao gerar prova documental:', err);
      toast.error('Erro ao gerar PDF');
    }
  };

  return {
    checklistResultado, checklistLoading, checklistMedicamento,
    executarChecklist, gerarProvaDocumental,
  };
}
