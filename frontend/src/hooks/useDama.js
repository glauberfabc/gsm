import { useState } from 'react';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export function useDama(companies) {
  const [damaStep, setDamaStep] = useState('upload');
  const [editalFiles, setEditalFiles] = useState([]);
  const [damaEmpresa, setDamaEmpresa] = useState('c1');
  const [damaProcessing, setDamaProcessing] = useState(false);
  const [damaZipBlob, setDamaZipBlob] = useState(null);
  const [damaStats, setDamaStats] = useState(null);
  const [damaItens, setDamaItens] = useState([]);
  const [damaMoeda, setDamaMoeda] = useState('BRL');
  const [damaExtraindo, setDamaExtraindo] = useState(false);
  const [damaItensExtraidos, setDamaItensExtraidos] = useState(false);
  const [damaPasso, setDamaPasso] = useState(1);
  const [damaItemNumero, setDamaItemNumero] = useState('');
  const [damaItemValor, setDamaItemValor] = useState('');
  const [damaItemValorRaw, setDamaItemValorRaw] = useState('');
  const [showPdfPreview, setShowPdfPreview] = useState(false);
  const [damaPalavraChave, setDamaPalavraChave] = useState('');
  const [damaItensGrid, setDamaItensGrid] = useState([]);

  const formatarMoeda = (valor, moeda) => {
    if (!valor && valor !== 0) return '';
    const numero = parseFloat(valor);
    if (isNaN(numero)) return '';
    if (moeda === 'BRL') {
      return numero.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    return numero.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };

  const handleValorChange = (e, itemId = null) => {
    let value = e.target.value;
    if (value === '' || value === null || value === undefined) {
      if (itemId) {
        setDamaItensGrid(prev => prev.map(item =>
          item.id === itemId ? { ...item, valor: '', valorRaw: '' } : item
        ));
      } else {
        setDamaItemValorRaw('');
        setDamaItemValor('');
      }
      return;
    }
    value = value.replace(/[^\d.,]/g, '');
    let numValue;
    if (damaMoeda === 'BRL') {
      numValue = value.replace(/\./g, '').replace(',', '.');
    } else {
      numValue = value.replace(/,/g, '');
    }
    const numero = parseFloat(numValue);
    if (itemId) {
      setDamaItensGrid(prev => prev.map(item =>
        item.id === itemId
          ? { ...item, valor: value, valorRaw: !isNaN(numero) ? numero.toString() : '' }
          : item
      ));
    } else {
      if (!isNaN(numero)) {
        setDamaItemValorRaw(numero.toString());
        setDamaItemValor(value);
      } else {
        setDamaItemValorRaw('');
        setDamaItemValor(value);
      }
    }
  };

  const extrairItensPorPalavraChave = async () => {
    if (!damaPalavraChave.trim()) {
      alert('Digite uma palavra-chave para filtrar (Ex: Canabidiol)');
      return;
    }
    if (editalFiles.length === 0) {
      alert('Faca upload do PDF do edital primeiro');
      return;
    }
    setDamaExtraindo(true);
    try {
      const formData = new FormData();
      editalFiles.forEach(file => formData.append('edital', file));
      formData.append('palavra_chave', damaPalavraChave);
      const response = await axios.post(`${API}/dama/extrair-itens-filtrado`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 120000
      });
      if (response.data.itens && response.data.itens.length > 0) {
        const itensComId = response.data.itens.map((item, idx) => ({
          id: `item-${Date.now()}-${idx}`,
          numero: item.numero || item.item || (idx + 1).toString(),
          descricao: item.descricao || '',
          quantidade: item.quantidade || 1,
          unidade: item.unidade || 'UN',
          valor: '',
          valorRaw: '',
          selecionado: true
        }));
        setDamaItensGrid(itensComId);
        setDamaItensExtraidos(true);
        const termos = damaPalavraChave.split(',').map(t => t.trim()).filter(t => t);
        alert(`${itensComId.length} item(ns) encontrado(s) com: ${termos.join(', ')}`);
      } else {
        const termos = damaPalavraChave.split(',').map(t => t.trim()).filter(t => t);
        alert(`Nenhum item encontrado com os termos: ${termos.join(', ')}. Tente outros termos.`);
      }
    } catch (error) {
      console.error('Erro ao extrair itens:', error);
      alert('Erro ao extrair itens: ' + (error.response?.data?.detail || error.message));
    } finally {
      setDamaExtraindo(false);
    }
  };

  const visualizarEdital = () => {
    if (editalFiles.length > 0) {
      const file = editalFiles[0];
      const url = URL.createObjectURL(file);
      window.open(url, '_blank');
    }
  };

  const resetDAMA = () => {
    setDamaStep('upload');
    setDamaPasso(1);
    setEditalFiles([]);
    if (damaZipBlob && damaZipBlob.startsWith('blob:')) {
      window.URL.revokeObjectURL(damaZipBlob);
    }
    setDamaZipBlob(null);
    setDamaStats(null);
    setDamaItemNumero('');
    setDamaItemValor('');
    setDamaItemValorRaw('');
    setDamaItens([]);
    setDamaItensExtraidos(false);
    setDamaMoeda('BRL');
    setShowPdfPreview(false);
    setDamaPalavraChave('');
    setDamaItensGrid([]);
  };

  const processarDAMASimplificado = async () => {
    const empresaSelecionada = companies.find(c => c.id === damaEmpresa);
    if (!editalFiles || editalFiles.length === 0) {
      alert('Selecione pelo menos um PDF do edital');
      return;
    }
    if (damaItensGrid.length === 0) {
      if (!damaItemNumero || !damaItemValorRaw) {
        alert('Informe o numero do item e o valor');
        return;
      }
    } else {
      const itensSelecionados = damaItensGrid.filter(i => i.selecionado && i.valorRaw);
      if (itensSelecionados.length === 0) {
        alert('Selecione pelo menos um item e preencha o valor');
        return;
      }
    }
    const temTimbradoEmMemoria = empresaSelecionada?.timbrado instanceof File;
    const temTimbradoCadastrado = empresaSelecionada?.timbradoNome && empresaSelecionada.timbradoNome.length > 0;
    if (!temTimbradoEmMemoria && !temTimbradoCadastrado) {
      alert('A empresa selecionada nao tem papel timbrado cadastrado. Clique em editar para adicionar.');
      return;
    }
    setDamaProcessing(true);
    try {
      const formData = new FormData();
      editalFiles.forEach((file) => formData.append('edital', file));
      if (temTimbradoEmMemoria) formData.append('timbrado', empresaSelecionada.timbrado);
      formData.append('empresa_id', damaEmpresa);
      formData.append('custo_unitario', '0');
      formData.append('moeda', damaMoeda);

      let itemConfig;
      let itensInfo;
      if (damaItensGrid.length > 0) {
        itemConfig = damaItensGrid
          .filter(item => item.selecionado && item.valorRaw)
          .map(item => ({
            item: item.numero,
            descricao: item.descricao,
            quantidade: item.quantidade || 1,
            preco_unitario: parseFloat(item.valorRaw) || 0,
            unidade: item.unidade || 'UN',
            participar: true
          }));
        itensInfo = itemConfig.map(i => `Item ${i.item}`).join(', ');
      } else {
        const valorNumerico = parseFloat(damaItemValorRaw) || 0;
        itemConfig = [{
          item: damaItemNumero,
          descricao: `Item ${damaItemNumero}`,
          quantidade: 1,
          preco_unitario: valorNumerico,
          unidade: 'UN',
          participar: true
        }];
        itensInfo = `Item ${damaItemNumero}`;
      }
      formData.append('itens_config', JSON.stringify(itemConfig));
      if (damaPalavraChave) formData.append('palavra_chave', damaPalavraChave);

      const response = await axios.post(`${API}/dama/process`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        responseType: 'blob',
        timeout: 180000
      });

      const zipFilename = `kit_licitacao_${damaPalavraChave || 'proposta'}_${Date.now()}.zip`;
      if (response.data.size > 0) {
        const blob = new Blob([response.data], { type: 'application/zip' });
        const blobUrl = window.URL.createObjectURL(blob);
        const nomesPdfs = editalFiles.map(f => f.name).join(', ');
        const valorTotal = itemConfig.reduce((sum, i) => sum + (i.preco_unitario * i.quantidade), 0);
        const valorExibicao = formatarMoeda(valorTotal, damaMoeda);
        setDamaZipBlob(blobUrl);
        setDamaStats({
          orgao: 'Processado com sucesso',
          numero_processo: nomesPdfs,
          itens_processados: itensInfo,
          empresa: empresaSelecionada?.name || 'Empresa nao encontrada',
          valor_total: `${damaMoeda === 'BRL' ? 'R$' : '$'} ${valorExibicao}`,
          moeda: damaMoeda === 'BRL' ? 'R$ Real' : '$ Dolar',
          zipFilename,
          arquivos: editalFiles.length,
          palavraChave: damaPalavraChave || '-'
        });
        setDamaStep('success');
      } else {
        throw new Error('ZIP vazio retornado pelo servidor');
      }
    } catch (error) {
      console.error('Erro no DAMA:', error);
      alert('Erro ao processar DAMA: ' + (error.response?.data?.detail || error.message));
    } finally {
      setDamaProcessing(false);
    }
  };

  return {
    damaStep, setDamaStep,
    editalFiles, setEditalFiles,
    damaEmpresa, setDamaEmpresa,
    damaProcessing,
    damaZipBlob,
    damaStats,
    damaMoeda, setDamaMoeda,
    damaExtraindo,
    damaItensExtraidos,
    damaItemNumero, setDamaItemNumero,
    damaItemValor, setDamaItemValor,
    damaItemValorRaw,
    damaPalavraChave, setDamaPalavraChave,
    damaItensGrid, setDamaItensGrid,
    handleValorChange,
    extrairItensPorPalavraChave,
    visualizarEdital,
    resetDAMA,
    processarDAMASimplificado,
    formatarMoeda,
  };
}
