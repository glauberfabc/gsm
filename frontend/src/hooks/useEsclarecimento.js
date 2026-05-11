import { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export function useEsclarecimento() {
  const [esclarecimentoModal, setEsclarecimentoModal] = useState(false);
  const [esclarecimentoAlerta, setEsclarecimentoAlerta] = useState(null);
  const [esclarecimentoEmpresa, setEsclarecimentoEmpresa] = useState('');
  const [esclarecimentoTexto, setEsclarecimentoTexto] = useState('');
  const [esclarecimentoGerando, setEsclarecimentoGerando] = useState(false);
  const [vigenciaValidacao, setVigenciaValidacao] = useState(null);
  const [vigenciaLoading, setVigenciaLoading] = useState(false);
  const [vigenciaBloqueio, setVigenciaBloqueio] = useState(false);
  const [vigenciaForceGenerate, setVigenciaForceGenerate] = useState(false);

  const gerarEsclarecimento = async () => {
    if (!esclarecimentoAlerta || !esclarecimentoEmpresa) {
      toast.warning('Selecione uma empresa');
      return;
    }
    setEsclarecimentoGerando(true);
    try {
      const res = await axios.post(`${API}/anvisa/esclarecimento`, {
        medicamento: esclarecimentoAlerta.medicamento_detectado || esclarecimentoAlerta.medicamento,
        principio_ativo: esclarecimentoAlerta.principio_ativo,
        situacao: esclarecimentoAlerta.situacao,
        link_prova: esclarecimentoAlerta.link || '',
        tipo_alerta: esclarecimentoAlerta.tipo_alerta,
        empresa_id: esclarecimentoEmpresa,
        force_generate: vigenciaForceGenerate,
      });
      if (res.data.bloqueado) {
        setVigenciaBloqueio(true);
        setVigenciaValidacao(prev => ({
          ...prev,
          bloqueios: res.data.vigencia_alertas || [],
          tem_bloqueio: true,
        }));
        toast.warning('Normas caducas/revogadas detectadas. Revise antes de gerar.');
        setEsclarecimentoGerando(false);
        return;
      }
      setEsclarecimentoTexto(res.data.texto);
      toast.success('Esclarecimento gerado com validacao DAMA!');
    } catch (err) {
      console.error('Erro ao gerar esclarecimento:', err);
      toast.error('Erro ao gerar esclarecimento');
    } finally {
      setEsclarecimentoGerando(false);
    }
  };

  const validarVigenciaEsclarecimento = async () => {
    setVigenciaLoading(true);
    try {
      const res = await axios.post(`${API}/dama/vigencia/validar-esclarecimento`);
      setVigenciaValidacao(res.data);
      setVigenciaBloqueio(res.data.tem_bloqueio || false);
      if (res.data.tem_bloqueio) {
        toast.warning('DAMA: Normas caducas detectadas!');
      }
    } catch (err) {
      console.error('Erro na validacao DAMA:', err);
    } finally {
      setVigenciaLoading(false);
    }
  };

  const openEsclarecimento = (alerta, medicamentoBuscado, companies) => {
    setEsclarecimentoAlerta({
      medicamento_detectado: alerta.medicamento_detectado || medicamentoBuscado,
      principio_ativo: alerta.principio_ativo || medicamentoBuscado,
      situacao: alerta.situacao || alerta.tipo_alerta || '',
      link: alerta.link || '',
      tipo_alerta: alerta.tipo_alerta || '',
    });
    setEsclarecimentoTexto('');
    setEsclarecimentoEmpresa(companies.find(c => c.name)?.id || '');
    setEsclarecimentoModal(true);
    setVigenciaValidacao(null);
    setVigenciaBloqueio(false);
    setVigenciaForceGenerate(false);
    validarVigenciaEsclarecimento();
  };

  return {
    esclarecimentoModal, setEsclarecimentoModal,
    esclarecimentoAlerta, setEsclarecimentoAlerta,
    esclarecimentoEmpresa, setEsclarecimentoEmpresa,
    esclarecimentoTexto,
    esclarecimentoGerando,
    vigenciaValidacao,
    vigenciaLoading,
    vigenciaBloqueio,
    vigenciaForceGenerate, setVigenciaForceGenerate,
    gerarEsclarecimento,
    validarVigenciaEsclarecimento,
    openEsclarecimento,
  };
}
