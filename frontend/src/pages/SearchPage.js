import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Search, Filter, X, Zap, Database, Save, CheckCircle, MapPin } from 'lucide-react';
import LicitacaoCard from '../components/LicitacaoCard';
import ListasManager from '../components/ListasManager';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Categorias de Saúde (do serviço de enriquecimento)
const HEALTH_CATEGORIES = [
  { id: 'hospitalar', emoji: '🏥', label: 'Hospitalar', keywords: ['hospital', 'uti', 'upa', 'ubs'] },
  { id: 'medicamentos', emoji: '💊', label: 'Medicamentos', keywords: ['medicament', 'fármaco', 'antibiótico'] },
  { id: 'equipamentos', emoji: '🩺', label: 'Equipamentos Médicos', keywords: ['equipamento', 'ventilador', 'monitor'] },
  { id: 'laboratorio', emoji: '🧪', label: 'Laboratório', keywords: ['laborat', 'exame', 'reagente'] },
  { id: 'insumos', emoji: '💉', label: 'Insumos Médicos', keywords: ['seringa', 'luva', 'máscara', 'epi'] },
  { id: 'odontologia', emoji: '🦷', label: 'Odontologia', keywords: ['odontológic', 'dental'] },
  { id: 'oftalmologia', emoji: '👁️', label: 'Oftalmologia', keywords: ['oftalmológic', 'lente', 'colírio'] },
  { id: 'oncologia', emoji: '🩻', label: 'Oncologia', keywords: ['oncológic', 'quimioterapia'] },
  { id: 'cardiologia', emoji: '🫀', label: 'Cardiologia', keywords: ['cardiológic', 'stent', 'marca-passo'] },
  { id: 'especialidades', emoji: '🧬', label: 'Especialidades', keywords: ['insulina', 'vacina', 'hemodiálise'] },
  { id: 'servicos', emoji: '👨‍⚕️', label: 'Serviços de Saúde', keywords: ['serviço médico', 'fisioterapia'] },
  { id: 'saude_geral', emoji: '🩹', label: 'Saúde Geral', keywords: ['saúde', 'sus', 'secretaria de saúde'] },
];

const SearchPage = React.forwardRef((props, ref) => {
  const [medicamento, setMedicamento] = useState('');
  const [loading, setLoading] = useState(false);
  const [resultados, setResultados] = useState([]);
  const [totalResultados, setTotalResultados] = useState(0);
  const [paginationInfo, setPaginationInfo] = useState(null);
  
  // Filtros
  const [tagsFiltro, setTagsFiltro] = useState([]);
  const [apenasReais, setApenasReais] = useState(false);
  const [apenasFuturas, setApenasFuturas] = useState(false);
  const [statusFiltro, setStatusFiltro] = useState('Todas');
  const [modalidadeFiltro, setModalidadeFiltro] = useState([]);
  const [esferaFiltro, setEsferaFiltro] = useState('');
  const [mostrarFiltros, setMostrarFiltros] = useState(false);
  
  // NOVO: Filtro por categorias de saúde
  const [categoriaSaudeFiltro, setCategoriaSaudeFiltro] = useState([]);
  const [apenasSaude, setApenasSaude] = useState(false);
  const [apenasUrgentes, setApenasUrgentes] = useState(false);
  
  // 🔒 FILTRO TEMPORAL (OBRIGATÓRIO POR DEFAULT)
  const [incluirHistorico, setIncluirHistorico] = useState(false);
  const [periodoDias, setPeriodoDias] = useState(90);
  
  // 🎯 CLASSIFICAÇÃO DE OPORTUNIDADES V3 (PADRÃO GSM)
  const [incluirAtivas, setIncluirAtivas] = useState(true);
  const [incluirFuturas, setIncluirFuturas] = useState(false);
  const [incluirEncerradas, setIncluirEncerradas] = useState(false);
  const [excluirCredenciamentos, setExcluirCredenciamentos] = useState(false); // V3: Excluir, não incluir!
  const [classificacaoInfo, setClassificacaoInfo] = useState(null);
  
  // 🔒 P3: CAMADA DE CONFIABILIDADE DE DADOS
  const [incluirSuspeitos, setIncluirSuspeitos] = useState(false);
  const [incluirPlanejamento, setIncluirPlanejamento] = useState(false);
  const [confiabilidadeInfo, setConfiabilidadeInfo] = useState(null);
  
  // Paginação
  const [currentPage, setCurrentPage] = useState(1);
  const [perPage, setPerPage] = useState(25); // Padrão 25 como solicitado (entre 15-50)
  
  // Listas
  const [mostrarListas, setMostrarListas] = useState(false);
  const [listaSelecionada, setListaSelecionada] = useState(null);
  
  // 🚀 LOCAL-FIRST: Busca rápida no banco local
  const [usarBuscaLocal, setUsarBuscaLocal] = useState(true);
  const [filtrosDisponiveis, setFiltrosDisponiveis] = useState({ estados: [], modalidades: [], esferas: [], total_editais: 0 });
  const [estadoFiltro, setEstadoFiltro] = useState('');
  const [municipioFiltro, setMunicipioFiltro] = useState(''); // 🏙️ NOVO: Filtro por Município (v3.6)
  const [performanceInfo, setPerformanceInfo] = useState(null);
  
  // 🔀 BUSCA HÍBRIDA: Combina termo digitado + palavras-chave das listas
  const [usarBuscaHibrida, setUsarBuscaHibrida] = useState(true);
  const [listasUsuario, setListasUsuario] = useState([]);
  
  // 🆕 v4.1 AUTOCOMPLETE: Sugestões de medicamentos
  const [sugestoes, setSugestoes] = useState([]);
  const [mostrarSugestoes, setMostrarSugestoes] = useState(false);
  const [carregandoSugestoes, setCarregandoSugestoes] = useState(false);
  const [sugestaoSelecionada, setSugestaoSelecionada] = useState(-1);
  const [listasAtivas, setListasAtivas] = useState([]); // IDs das listas ativas para busca híbrida
  const [buscaHibridaInfo, setBuscaHibridaInfo] = useState(null);
  
  // 🆕 v4.2 HISTÓRICO DE BUSCAS: Armazenado no localStorage
  const [historicoBuscas, setHistoricoBuscas] = useState([]);
  
  // 💾 PERSISTÊNCIA DE ESTADO: Indicadores de sincronização
  const [isSaving, setIsSaving] = useState(false);
  const [preferencesLoaded, setPreferencesLoaded] = useState(false);
  
  // 🎯 MODO DE BUSCA: Toggle entre "apenas termo" e "termo + lista"
  // Default: quando lista está selecionada, busca combina termo + lista
  const [modoBusca, setModoBusca] = useState('termo_mais_lista'); // 'apenas_termo' | 'termo_mais_lista'
  
  // 🆕 v4.2: Carregar histórico de buscas do localStorage
  useEffect(() => {
    try {
      const historicoSalvo = localStorage.getItem('gsm_historico_buscas');
      if (historicoSalvo) {
        const historico = JSON.parse(historicoSalvo);
        // Limitar a 10 buscas mais recentes
        setHistoricoBuscas(historico.slice(0, 10));
      }
    } catch (e) {
      console.log('Erro ao carregar histórico de buscas:', e);
    }
  }, []);
  
  // 🆕 v4.2: Função para salvar busca no histórico
  const salvarBuscaNoHistorico = (termo) => {
    if (!termo || termo.trim().length < 2) return;
    
    const termoLimpo = termo.trim();
    
    // Remover duplicatas e adicionar no topo
    const novoHistorico = [
      termoLimpo,
      ...historicoBuscas.filter(h => h.toLowerCase() !== termoLimpo.toLowerCase())
    ].slice(0, 10); // Manter apenas 10 itens
    
    setHistoricoBuscas(novoHistorico);
    
    try {
      localStorage.setItem('gsm_historico_buscas', JSON.stringify(novoHistorico));
    } catch (e) {
      console.log('Erro ao salvar histórico:', e);
    }
  };
  
  // 🆕 v4.2: Função para limpar histórico
  const limparHistorico = () => {
    setHistoricoBuscas([]);
    localStorage.removeItem('gsm_historico_buscas');
  };
  
  // 💾 PERSISTÊNCIA: Carregar preferências do localStorage ao montar
  // 🛡️ DIRETRIZ ANTI-TELA BRANCA v3.3: Carregar preferências com fallback seguro
  useEffect(() => {
    try {
      // Carregar estado da busca local
      const savedBuscaLocal = localStorage.getItem('gsm_busca_local');
      if (savedBuscaLocal !== null) {
        try {
          setUsarBuscaLocal(JSON.parse(savedBuscaLocal));
        } catch { /* Manter valor default */ }
      }
      
      // Carregar estado da busca híbrida
      const savedBuscaHibrida = localStorage.getItem('gsm_busca_hibrida');
      if (savedBuscaHibrida !== null) {
        try {
          setUsarBuscaHibrida(JSON.parse(savedBuscaHibrida));
        } catch { /* Manter valor default */ }
      }
      
      // Carregar listas ativas
      const savedListasAtivas = localStorage.getItem('gsm_listas_ativas');
      if (savedListasAtivas !== null) {
        try {
          const parsed = JSON.parse(savedListasAtivas);
          // Garantir que é um array
          if (Array.isArray(parsed)) {
            setListasAtivas(parsed);
          }
        } catch { /* Manter valor default */ }
      }
      
      // Carregar filtro de estado
      const savedEstadoFiltro = localStorage.getItem('gsm_estado_filtro');
      if (savedEstadoFiltro !== null && typeof savedEstadoFiltro === 'string') {
        setEstadoFiltro(savedEstadoFiltro);
      }
      
      // Carregar filtro de esfera
      const savedEsferaFiltro = localStorage.getItem('gsm_esfera_filtro');
      if (savedEsferaFiltro !== null && typeof savedEsferaFiltro === 'string') {
        setEsferaFiltro(savedEsferaFiltro);
      }
      
      setPreferencesLoaded(true);
      console.log('✅ Preferências carregadas do localStorage');
    } catch (error) {
      console.error('Erro ao carregar preferências (ignorado):', error);
      // 🛡️ Garantir que o app continue funcionando mesmo com erro
      setPreferencesLoaded(true);
    }
  }, []);
  
  // 💾 PERSISTÊNCIA: Salvar preferências automaticamente quando mudarem
  useEffect(() => {
    // Só salvar depois que as preferências forem carregadas (evita sobrescrever com valores default)
    if (!preferencesLoaded) return;
    
    const savePreferences = () => {
      setIsSaving(true);
      try {
        localStorage.setItem('gsm_busca_local', JSON.stringify(usarBuscaLocal));
        localStorage.setItem('gsm_busca_hibrida', JSON.stringify(usarBuscaHibrida));
        localStorage.setItem('gsm_listas_ativas', JSON.stringify(listasAtivas));
        localStorage.setItem('gsm_estado_filtro', estadoFiltro);
        localStorage.setItem('gsm_esfera_filtro', esferaFiltro);
        
        // Simular delay de sincronização para feedback visual
        setTimeout(() => setIsSaving(false), 500);
      } catch (error) {
        console.error('Erro ao salvar preferências:', error);
        setIsSaving(false);
      }
    };
    
    // Debounce para não salvar a cada keystroke
    const timeoutId = setTimeout(savePreferences, 300);
    return () => clearTimeout(timeoutId);
  }, [usarBuscaLocal, usarBuscaHibrida, listasAtivas, estadoFiltro, esferaFiltro, preferencesLoaded]);
  
  // Carregar filtros disponíveis ao montar
  useEffect(() => {
    const carregarFiltros = async () => {
      try {
        const response = await axios.get(`${API}/search/local/filters`);
        setFiltrosDisponiveis(response.data);
      } catch (error) {
        console.log('Filtros locais não disponíveis:', error);
      }
    };
    carregarFiltros();
  }, []);
  
  // Carregar listas do usuário para busca híbrida
  useEffect(() => {
    const carregarListas = async () => {
      try {
        const response = await axios.get(`${API}/listas`);
        if (response.data.listas) {
          setListasUsuario(response.data.listas);
        }
      } catch (error) {
        console.log('Listas não disponíveis:', error);
      }
    };
    carregarListas();
  }, []);

  // 🆕 v4.1 AUTOCOMPLETE: Buscar sugestões quando o termo muda
  useEffect(() => {
    const buscarSugestoes = async () => {
      // Só buscar a partir de 2 caracteres
      if (medicamento.trim().length < 2) {
        setSugestoes([]);
        setMostrarSugestoes(false);
        return;
      }
      
      setCarregandoSugestoes(true);
      
      try {
        const response = await axios.get(`${API}/suggestions?q=${encodeURIComponent(medicamento.trim())}&limit=8`);
        
        if (response.data.sugestoes && response.data.sugestoes.length > 0) {
          setSugestoes(response.data.sugestoes);
          setMostrarSugestoes(true);
        } else {
          setSugestoes([]);
          setMostrarSugestoes(false);
        }
      } catch (error) {
        console.log('Sugestões não disponíveis:', error);
        setSugestoes([]);
      } finally {
        setCarregandoSugestoes(false);
      }
    };
    
    // Debounce: esperar 300ms após o usuário parar de digitar
    const timeoutId = setTimeout(buscarSugestoes, 300);
    return () => clearTimeout(timeoutId);
  }, [medicamento]);
  
  // 🆕 v4.1 AUTOCOMPLETE: Selecionar sugestão
  const handleSelecionarSugestao = (termo) => {
    setMedicamento(termo);
    setMostrarSugestoes(false);
    setSugestaoSelecionada(-1);
    
    // Disparar busca automaticamente após selecionar
    setTimeout(() => {
      handleSearch(null, 1);
    }, 100);
  };
  
  // 🆕 v4.1 AUTOCOMPLETE: Navegação por teclado
  const handleKeyDownAutocomplete = (e) => {
    if (!mostrarSugestoes || sugestoes.length === 0) return;
    
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setSugestaoSelecionada(prev => 
          prev < sugestoes.length - 1 ? prev + 1 : prev
        );
        break;
      case 'ArrowUp':
        e.preventDefault();
        setSugestaoSelecionada(prev => prev > 0 ? prev - 1 : -1);
        break;
      case 'Enter':
        if (sugestaoSelecionada >= 0 && sugestaoSelecionada < sugestoes.length) {
          e.preventDefault();
          handleSelecionarSugestao(sugestoes[sugestaoSelecionada].termo);
        }
        break;
      case 'Escape':
        setMostrarSugestoes(false);
        setSugestaoSelecionada(-1);
        break;
      default:
        break;
    }
  };

  // Expor função para abrir modal via ref
  React.useImperativeHandle(ref, () => ({
    showListas: () => setMostrarListas(true)
  }));

  const handleSearch = async (e, page = 1) => {
    if (e) e.preventDefault();
    
    // Validação: precisa ter ao menos um critério de busca
    const temTermoDigitado = medicamento.trim().length > 0;
    const temListaSelecionadaParaBusca = listaSelecionada && modoBusca === 'termo_mais_lista';
    const temListasAtivas = usarBuscaHibrida && listasAtivas.length > 0;
    const temFiltros = estadoFiltro || modalidadeFiltro.length > 0 || esferaFiltro || apenasSaude;
    
    if (!usarBuscaLocal && !temTermoDigitado && !temListaSelecionadaParaBusca && !temFiltros) {
      alert('Digite um termo de busca OU selecione uma lista OU use filtros');
      return;
    }
    
    // 🆕 v4.2 HISTÓRICO: Salvar termo no histórico de buscas
    if (temTermoDigitado) {
      salvarBuscaNoHistorico(medicamento.trim());
    }

    setLoading(true);
    setResultados([]);
    setPerformanceInfo(null);
    
    try {
      let response;
      const params = new URLSearchParams();
      
      // Sempre usar busca local (otimizada)
      if (usarBuscaLocal) {
        // 🔍 TERMO DIGITADO: sempre incluir se houver
        if (temTermoDigitado) {
          params.append('q', medicamento.trim());
        }
        
        // 🎯 KEYWORDS DAS LISTAS: coletar baseado no modo de busca
        const keywordsColetadas = [];
        
        // Modo 1: Lista selecionada + modoBusca = 'termo_mais_lista'
        if (listaSelecionada && modoBusca === 'termo_mais_lista') {
          if (listaSelecionada.medicamentos && listaSelecionada.medicamentos.length > 0) {
            keywordsColetadas.push(...listaSelecionada.medicamentos);
          }
        }
        
        // Modo 2: Busca híbrida com listas ativas (quando não tem lista selecionada específica)
        if (!listaSelecionada && usarBuscaHibrida && listasAtivas.length > 0) {
          listasUsuario
            .filter(lista => listasAtivas.includes(lista.id))
            .forEach(lista => {
              if (lista.medicamentos) {
                keywordsColetadas.push(...lista.medicamentos);
              }
            });
        }
        
        // Adicionar keywords se houver
        if (keywordsColetadas.length > 0) {
          // Remover duplicatas
          const keywordsUnicas = [...new Set(keywordsColetadas)];
          params.append('keywords', keywordsUnicas.join(','));
        }
        
        // Filtros adicionais
        if (estadoFiltro) params.append('estados', estadoFiltro);
        if (municipioFiltro) params.append('municipio', municipioFiltro); // 🏙️ NOVO v3.6
        if (modalidadeFiltro.length > 0) params.append('modalidade', modalidadeFiltro[0]);
        if (esferaFiltro) params.append('esfera', esferaFiltro);
        if (apenasSaude) params.append('apenas_saude', 'true');
        
        // 🔒 FILTRO TEMPORAL
        params.append('incluir_historico', incluirHistorico ? 'true' : 'false');
        params.append('periodo_dias', periodoDias.toString());
        
        // 🎯 CLASSIFICAÇÃO DE OPORTUNIDADES V3 (PADRÃO GSM)
        params.append('incluir_ativas', incluirAtivas ? 'true' : 'false');
        params.append('incluir_futuras', incluirFuturas ? 'true' : 'false');
        params.append('incluir_encerradas', incluirEncerradas ? 'true' : 'false');
        params.append('excluir_credenciamentos', excluirCredenciamentos ? 'true' : 'false');
        
        // 🔒 P3: CAMADA DE CONFIABILIDADE DE DADOS
        params.append('incluir_suspeitos', incluirSuspeitos ? 'true' : 'false');
        params.append('incluir_planejamento', incluirPlanejamento ? 'true' : 'false');
        
        params.append('limit', perPage);
        params.append('page', page);
        
        response = await axios.get(`${API}/search/local?${params.toString()}`);
        
        // Guardar info de classificação
        setClassificacaoInfo(response.data.classificacao_oportunidade || null);
        
        // 🔒 P3: Guardar info de confiabilidade
        setConfiabilidadeInfo(response.data.confiabilidade_dados || null);
        
        // Guardar info de performance e busca híbrida
        setPerformanceInfo(response.data.performance);
        
        // Montar info de busca para exibição
        const buscaInfo = {
          ativa: temTermoDigitado || keywordsColetadas.length > 0,
          termo_digitado: temTermoDigitado ? medicamento.trim() : null,
          keywords_lista: keywordsColetadas.length > 0 ? [...new Set(keywordsColetadas)] : [],
          modo: listaSelecionada ? modoBusca : 'hibrido'
        };
        setBuscaHibridaInfo(buscaInfo);
        
        setResultados(response.data.resultados || []);
        setTotalResultados(response.data.total || 0);
        setPaginationInfo(response.data.pagination);
        setCurrentPage(page);
      } else {
        // Fallback: Busca tradicional via scrapers (mais lenta)
        const payload = {
          medicamento: medicamento.trim() || null,
          tags: tagsFiltro.length > 0 ? tagsFiltro : null,
          apenas_reais: apenasReais,
          apenas_futuras: apenasFuturas,
          // Só passa lista_id se modo for 'termo_mais_lista'
          lista_id: (listaSelecionada && modoBusca === 'termo_mais_lista') ? listaSelecionada.id : null,
          status_filtro: statusFiltro !== 'Todas' ? statusFiltro : null,
          modalidade_filtro: modalidadeFiltro.length > 0 ? modalidadeFiltro : null,
          esfera_filtro: esferaFiltro || null,
          apenas_saude: apenasSaude,
          apenas_urgentes: apenasUrgentes,
          categorias_saude: categoriaSaudeFiltro.length > 0 ? categoriaSaudeFiltro : null,
          page: page,
          per_page: perPage
        };

        response = await axios.post(`${API}/search`, payload);
        
        setResultados(response.data.resultados || []);
        setTotalResultados(response.data.total || 0);
        setPaginationInfo(response.data.pagination);
        setCurrentPage(page);
      }
      
      setLoading(false);
    } catch (error) {
      console.error('Erro na busca:', error);
      // 🛡️ ANTI-TELA BRANCA: Reseta estado em caso de erro
      setResultados([]);
      setTotalResultados(0);
      setPaginationInfo(null);
      setLoading(false);
      
      // Mensagem de erro mais amigável
      const errorMsg = error?.response?.data?.detail || error?.message || 'Erro desconhecido';
      alert(`Erro ao buscar: ${errorMsg}. Tente novamente.`);
    }
  };

  const handlePageChange = (newPage) => {
    handleSearch(null, newPage);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleExport = async (formato) => {
    try {
      const params = new URLSearchParams();
      
      if (medicamento.trim()) params.append('medicamento', medicamento.trim());
      if (estadoFiltro) params.append('estado', estadoFiltro);
      if (municipioFiltro) params.append('municipio', municipioFiltro);
      if (statusFiltro !== 'Todas') params.append('status', statusFiltro);
      if (modalidadeFiltro.length > 0) params.append('modalidade', modalidadeFiltro[0]);
      if (esferaFiltro) params.append('esfera', esferaFiltro);
      if (listaSelecionada) params.append('lista_id', listaSelecionada.id);
      
      // Filtros de saúde
      if (apenasSaude) params.append('apenas_saude', 'true');
      if (categoriaSaudeFiltro.length > 0) params.append('categorias', categoriaSaudeFiltro.join(','));

      if (formato === 'excel') {
        window.open(`${API}/search/export-excel?${params.toString()}`, '_blank');
      } else {
        params.append('formato', formato);
        window.open(`${API}/export?${params.toString()}`, '_blank');
      }
    } catch (error) {
      console.error('Erro ao exportar:', error);
      alert('Erro ao exportar dados.');
    }
  };

  const limparListaSelecionada = () => {
    setListaSelecionada(null);
    setModoBusca('termo_mais_lista'); // Reset para default
    // NÃO limpa medicamento - usuário pode querer continuar buscando
    setResultados([]);
    setBuscaHibridaInfo(null);
  };

  const toggleTag = (tag) => {
    setTagsFiltro(prev =>
      prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag]
    );
  };

  const toggleModalidade = (mod) => {
    setModalidadeFiltro(prev =>
      prev.includes(mod) ? prev.filter(m => m !== mod) : [...prev, mod]
    );
  };

  return (
    <main className="max-w-7xl mx-auto px-4 py-6 md:py-8">
      {listaSelecionada && (
        <div className="bg-green-50 border-2 border-green-300 rounded-lg p-4 mb-6">
          <div className="flex items-start justify-between mb-3">
            <div>
              <p className="text-sm text-green-700 font-medium">📋 Lista selecionada:</p>
              <p className="text-lg font-bold text-green-900">{listaSelecionada.nome}</p>
              <p className="text-sm text-green-600 mt-1">
                {listaSelecionada.medicamentos.length} palavra(s): {listaSelecionada.medicamentos.slice(0, 3).join(', ')}
                {listaSelecionada.medicamentos.length > 3 && '...'}
              </p>
            </div>
            <button
              onClick={limparListaSelecionada}
              className="px-4 py-2 bg-green-700 text-white rounded-lg hover:bg-green-800 transition-colors font-medium text-sm"
            >
              ✕ Limpar
            </button>
          </div>
          
          {/* 🎯 TOGGLE MODO DE BUSCA - DIFERENCIAL COMPETITIVO */}
          <div className="flex items-center gap-4 pt-3 border-t border-green-200">
            <span className="text-sm font-medium text-green-800">Modo de busca:</span>
            <label className={`flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-all ${
              modoBusca === 'apenas_termo' 
                ? 'bg-blue-600 text-white shadow-md' 
                : 'bg-white text-gray-700 border border-gray-300 hover:border-blue-400'
            }`}>
              <input
                type="radio"
                name="modoBusca"
                value="apenas_termo"
                checked={modoBusca === 'apenas_termo'}
                onChange={() => setModoBusca('apenas_termo')}
                className="hidden"
              />
              <span className="text-sm font-medium">🔍 Apenas termo digitado</span>
            </label>
            <label className={`flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-all ${
              modoBusca === 'termo_mais_lista' 
                ? 'bg-purple-600 text-white shadow-md' 
                : 'bg-white text-gray-700 border border-gray-300 hover:border-purple-400'
            }`}>
              <input
                type="radio"
                name="modoBusca"
                value="termo_mais_lista"
                checked={modoBusca === 'termo_mais_lista'}
                onChange={() => setModoBusca('termo_mais_lista')}
                className="hidden"
              />
              <span className="text-sm font-medium">🔀 Termo + Lista combinados</span>
            </label>
          </div>
          
          {modoBusca === 'termo_mais_lista' && (
            <p className="text-xs text-green-600 mt-2 italic">
              💡 A busca incluirá o termo digitado E todas as palavras-chave da lista &quot;{listaSelecionada.nome}&quot;
            </p>
          )}
          {modoBusca === 'apenas_termo' && (
            <p className="text-xs text-blue-600 mt-2 italic">
              💡 A busca usará apenas o termo digitado, ignorando a lista
            </p>
          )}
        </div>
      )}

      <div className="bg-white rounded-lg shadow-lg p-4 md:p-6 mb-6 md:mb-8">
        <form onSubmit={handleSearch} className="space-y-4">
          {/* 🔍 CAMPOS DE BUSCA PRINCIPAL (v3.6 ELITE) */}
          <div className="grid grid-cols-1 md:grid-cols-12 gap-3">
            {/* Campo de Medicamento/Termo + AUTOCOMPLETE v4.1 + HISTÓRICO v4.2 */}
            <div className="md:col-span-5">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Buscar Medicamento ou Termo
              </label>
              <div className="relative">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 z-10" size={18} />
                <input
                  type="text"
                  value={medicamento}
                  onChange={(e) => setMedicamento(e.target.value)}
                  onKeyDown={handleKeyDownAutocomplete}
                  onFocus={() => {
                    // 🆕 v4.2: Mostrar histórico se campo vazio, ou sugestões se tem texto
                    if (medicamento.length >= 2 && sugestoes.length > 0) {
                      setMostrarSugestoes(true);
                    } else if (medicamento.length < 2 && historicoBuscas.length > 0) {
                      setMostrarSugestoes(true);
                    }
                  }}
                  onBlur={() => setTimeout(() => setMostrarSugestoes(false), 200)}
                  placeholder="Ex: Canabidiol, Insulina, Luva..."
                  className="w-full pl-12 pr-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 text-sm font-medium"
                  autoComplete="off"
                />
                
                {/* 🆕 v4.1 AUTOCOMPLETE: Dropdown de Sugestões */}
                {mostrarSugestoes && sugestoes.length > 0 && (
                  <div className="absolute z-50 w-full mt-1 bg-white border border-gray-300 rounded-xl shadow-2xl max-h-64 overflow-y-auto">
                    <div className="px-3 py-2 bg-gradient-to-r from-blue-50 to-indigo-50 border-b border-gray-200">
                      <span className="text-xs font-medium text-blue-700 flex items-center gap-1">
                        <span>💊</span> Sugestões de Medicamentos
                        {carregandoSugestoes && <span className="animate-pulse ml-2">...</span>}
                      </span>
                    </div>
                    
                    {sugestoes.map((sugestao, index) => (
                      <div
                        key={index}
                        onClick={() => handleSelecionarSugestao(sugestao.termo)}
                        className={`px-4 py-3 cursor-pointer flex items-center justify-between transition-colors ${
                          index === sugestaoSelecionada 
                            ? 'bg-blue-100 border-l-4 border-blue-500' 
                            : 'hover:bg-gray-50 border-l-4 border-transparent'
                        }`}
                      >
                        <div className="flex flex-col">
                          <span className="font-semibold text-gray-900 text-sm">
                            {/* Destacar o termo buscado */}
                            {sugestao.termo.split(new RegExp(`(${medicamento})`, 'gi')).map((part, i) => 
                              part.toLowerCase() === medicamento.toLowerCase() 
                                ? <mark key={i} className="bg-yellow-200 px-0.5 rounded">{part}</mark>
                                : <span key={i}>{part}</span>
                            )}
                          </span>
                          <span className="text-xs text-gray-500">{sugestao.categoria}</span>
                        </div>
                        
                        <span className={`text-xs px-2 py-1 rounded-full font-medium ${
                          sugestao.tipo === 'medicamento' 
                            ? 'bg-green-100 text-green-700' 
                            : sugestao.tipo === 'capturado'
                            ? 'bg-blue-100 text-blue-700'
                            : 'bg-gray-100 text-gray-600'
                        }`}>
                          {sugestao.tipo === 'medicamento' ? '💊' : 
                           sugestao.tipo === 'capturado' ? '📋' : '📄'}
                        </span>
                      </div>
                    ))}
                    
                    <div className="px-3 py-2 bg-gray-50 border-t border-gray-200">
                      <span className="text-xs text-gray-500">
                        Use ↑↓ para navegar e Enter para selecionar
                      </span>
                    </div>
                  </div>
                )}
                
                {/* 🆕 v4.2 HISTÓRICO DE BUSCAS: Mostrar quando campo focado e vazio */}
                {mostrarSugestoes && sugestoes.length === 0 && historicoBuscas.length > 0 && medicamento.length < 2 && (
                  <div className="absolute z-50 w-full mt-1 bg-white border border-gray-300 rounded-xl shadow-2xl max-h-64 overflow-y-auto">
                    <div className="px-3 py-2 bg-gradient-to-r from-amber-50 to-yellow-50 border-b border-gray-200 flex items-center justify-between">
                      <span className="text-xs font-medium text-amber-700 flex items-center gap-1">
                        <span>🕐</span> Buscas Recentes
                      </span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          limparHistorico();
                          setMostrarSugestoes(false);
                        }}
                        className="text-xs text-red-500 hover:text-red-700 font-medium"
                      >
                        Limpar
                      </button>
                    </div>
                    
                    {historicoBuscas.map((termo, index) => (
                      <div
                        key={index}
                        onClick={() => handleSelecionarSugestao(termo)}
                        className="px-4 py-3 cursor-pointer flex items-center justify-between hover:bg-amber-50 border-l-4 border-transparent hover:border-amber-400 transition-colors"
                      >
                        <div className="flex items-center gap-3">
                          <span className="text-amber-500">🔍</span>
                          <span className="font-medium text-gray-800 text-sm">{termo}</span>
                        </div>
                        <span className="text-xs text-gray-400">clique para buscar</span>
                      </div>
                    ))}
                    
                    <div className="px-3 py-2 bg-gray-50 border-t border-gray-200">
                      <span className="text-xs text-gray-500">
                        💡 Digite para buscar medicamentos ou selecione uma busca recente
                      </span>
                    </div>
                  </div>
                )}
              </div>
            </div>
            
            {/* 🏙️ NOVO: Campo de Município (v3.6 ELITE) */}
            <div className="md:col-span-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Município / Cidade
              </label>
              <div className="relative">
                <MapPin className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                <input
                  type="text"
                  value={municipioFiltro}
                  onChange={(e) => setMunicipioFiltro(e.target.value)}
                  placeholder="Ex: São Paulo, Florianópolis..."
                  className="w-full pl-12 pr-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 text-sm font-medium"
                />
              </div>
            </div>
            
            {/* Botão de Busca */}
            <div className="md:col-span-3 flex items-end">
              <button
                type="submit"
                disabled={loading}
                className="w-full px-6 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:bg-blue-300 transition-colors font-bold shadow-lg flex items-center justify-center gap-2 uppercase text-sm"
              >
                <Search className="w-4 h-4" />
                {loading ? 'Buscando...' : 'Pesquisar'}
              </button>
            </div>
          </div>

          {/* 🚀 Toggle Busca Local + 🔀 Busca Híbrida */}
          <div className="flex flex-col gap-3 p-3 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg border border-blue-200">
            {/* 💾 Indicador de Sincronização */}
            <div className="flex items-center justify-between text-xs">
              <span className="text-gray-500">Configurações de Busca</span>
              <div className="flex items-center gap-1.5">
                {isSaving ? (
                  <>
                    <Save className="w-3 h-3 text-amber-500 animate-pulse" />
                    <span className="text-amber-600">Salvando...</span>
                  </>
                ) : (
                  <>
                    <CheckCircle className="w-3 h-3 text-green-500" />
                    <span className="text-green-600">Preferências salvas</span>
                  </>
                )}
              </div>
            </div>
            
            <div className="flex flex-col md:flex-row md:items-center gap-3">
              <div className="flex items-center gap-3">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={usarBuscaLocal}
                    onChange={(e) => setUsarBuscaLocal(e.target.checked)}
                    className="w-5 h-5 text-blue-600 rounded"
                  />
                  <span className="flex items-center gap-1.5 font-medium text-blue-800">
                    <Zap className="w-4 h-4 text-yellow-500" />
                    Busca Local-First
                  </span>
                </label>
                {usarBuscaLocal && (
                  <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded-full font-medium">
                    ⚡ ~10ms
                  </span>
                )}
              </div>
              
              {usarBuscaLocal && filtrosDisponiveis.total_editais > 0 && (
                <div className="flex items-center gap-2 text-sm text-blue-600">
                  <Database className="w-4 h-4" />
                  <span>{filtrosDisponiveis.total_editais} editais sincronizados</span>
                </div>
              )}
              
              {performanceInfo && (
                <div className="ml-auto text-xs text-gray-500">
                  Tempo: <span className="font-mono text-green-600">{performanceInfo.tempo_ms}ms</span>
                </div>
              )}
            </div>
            
            {/* 🔀 BUSCA HÍBRIDA: Seleção de listas ativas */}
            {usarBuscaLocal && listasUsuario.length > 0 && (
              <div className="border-t border-blue-200 pt-3 mt-1">
                <div className="flex items-center gap-2 mb-2">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={usarBuscaHibrida}
                      onChange={(e) => {
                        setUsarBuscaHibrida(e.target.checked);
                        if (!e.target.checked) setListasAtivas([]);
                      }}
                      className="w-4 h-4 text-purple-600 rounded"
                    />
                    <span className="text-sm font-medium text-purple-800">
                      🔀 Busca Híbrida
                    </span>
                  </label>
                  <span className="text-xs text-gray-500">
                    (combina termo digitado + palavras-chave das suas listas)
                  </span>
                </div>
                
                {usarBuscaHibrida && (
                  <div className="flex flex-wrap gap-2">
                    {listasUsuario.map((lista) => (
                      <label 
                        key={lista.id}
                        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium cursor-pointer transition-all
                          ${listasAtivas.includes(lista.id)
                            ? 'bg-purple-600 text-white shadow-md'
                            : 'bg-white text-gray-700 border border-gray-300 hover:border-purple-400'
                          }`}
                      >
                        <input
                          type="checkbox"
                          checked={listasAtivas.includes(lista.id)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setListasAtivas([...listasAtivas, lista.id]);
                            } else {
                              setListasAtivas(listasAtivas.filter(id => id !== lista.id));
                            }
                          }}
                          className="hidden"
                        />
                        <span>{lista.nome}</span>
                        <span className={`px-1.5 py-0.5 rounded-full text-[10px] ${
                          listasAtivas.includes(lista.id) ? 'bg-purple-500' : 'bg-gray-200'
                        }`}>
                          {lista.medicamentos?.length || 0}
                        </span>
                      </label>
                    ))}
                  </div>
                )}
                
                {/* Indicador de busca expandida */}
                {buscaHibridaInfo?.ativa && (
                  <div className="mt-2 p-2 bg-purple-100 rounded-md text-xs text-purple-800">
                    <span className="font-medium">🔍 Busca expandida: </span>
                    {buscaHibridaInfo.termo_digitado && (
                      <span className="bg-purple-200 px-1.5 py-0.5 rounded mr-1">
                        &quot;{buscaHibridaInfo.termo_digitado}&quot;
                      </span>
                    )}
                    {buscaHibridaInfo.keywords_lista?.length > 0 && (
                      <>
                        <span className="text-purple-600">+</span>
                        <span className="ml-1">
                          {buscaHibridaInfo.keywords_lista.slice(0, 5).map((kw, i) => (
                            <span key={i} className="bg-white px-1.5 py-0.5 rounded mx-0.5 border border-purple-300">
                              {kw}
                            </span>
                          ))}
                          {buscaHibridaInfo.keywords_lista.length > 5 && (
                            <span className="text-purple-600 ml-1">+{buscaHibridaInfo.keywords_lista.length - 5} mais</span>
                          )}
                        </span>
                      </>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          <button
            type="button"
            onClick={() => setMostrarFiltros(!mostrarFiltros)}
            className="flex items-center gap-2 text-blue-600 hover:text-blue-800 font-medium transition-colors text-sm md:text-base"
          >
            <Filter className="w-4 h-4" />
            {mostrarFiltros ? 'Ocultar' : 'Mostrar'} Filtros Avançados
          </button>

          {mostrarFiltros && (
            <div className="bg-gray-50 p-4 rounded-lg space-y-4 border border-gray-200">
              {/* 🎯 CLASSIFICAÇÃO DE OPORTUNIDADES V3 (PADRÃO GSM) */}
              <div className="bg-gradient-to-r from-green-50 to-emerald-50 border-2 border-green-300 rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm font-bold text-green-800 flex items-center gap-2">
                    🎯 Status da Oportunidade
                    <span className="text-xs font-normal text-green-600 bg-green-100 px-2 py-0.5 rounded">Padrão GSM</span>
                  </span>
                </div>
                <p className="text-xs text-green-700 mb-3">
                  Por padrão, mostra <strong>todas oportunidades ATIVAS</strong> (competitivas + credenciamentos vigentes).
                  Credenciamentos são incluídos porque permitem adesão imediata.
                </p>
                
                {/* Linha 1: Status de oportunidade */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
                  <label className={`flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-all ${
                    incluirAtivas 
                      ? 'bg-green-500 text-white shadow-md' 
                      : 'bg-white text-gray-700 border border-gray-300 hover:border-green-400'
                  }`}>
                    <input
                      type="checkbox"
                      checked={incluirAtivas}
                      onChange={(e) => setIncluirAtivas(e.target.checked)}
                      className="w-4 h-4"
                    />
                    <span className="text-sm font-medium">🟢 ATIVAS</span>
                    <span className="text-xs opacity-80">(acionáveis agora)</span>
                  </label>
                  <label className={`flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-all ${
                    incluirFuturas 
                      ? 'bg-yellow-500 text-white shadow-md' 
                      : 'bg-white text-gray-700 border border-gray-300 hover:border-yellow-400'
                  }`}>
                    <input
                      type="checkbox"
                      checked={incluirFuturas}
                      onChange={(e) => setIncluirFuturas(e.target.checked)}
                      className="w-4 h-4"
                    />
                    <span className="text-sm font-medium">🟡 FUTURAS</span>
                    <span className="text-xs opacity-80">(em breve)</span>
                  </label>
                  <label className={`flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-all ${
                    incluirEncerradas 
                      ? 'bg-gray-500 text-white shadow-md' 
                      : 'bg-white text-gray-700 border border-gray-300 hover:border-gray-400'
                  }`}>
                    <input
                      type="checkbox"
                      checked={incluirEncerradas}
                      onChange={(e) => setIncluirEncerradas(e.target.checked)}
                      className="w-4 h-4"
                    />
                    <span className="text-sm font-medium">🔴 ENCERRADAS</span>
                    <span className="text-xs opacity-80">(histórico)</span>
                  </label>
                </div>
                
                {/* Linha 2: Opção para EXCLUIR credenciamentos */}
                <div className="border-t border-green-200 pt-3">
                  <label className={`flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-all w-full ${
                    excluirCredenciamentos 
                      ? 'bg-red-100 text-red-700 border border-red-300' 
                      : 'bg-white text-gray-700 border border-gray-300 hover:border-gray-400'
                  }`}>
                    <input
                      type="checkbox"
                      checked={excluirCredenciamentos}
                      onChange={(e) => setExcluirCredenciamentos(e.target.checked)}
                      className="w-4 h-4"
                    />
                    <span className="text-sm font-medium">❌ Excluir credenciamentos do resultado</span>
                    <span className="text-xs opacity-80">(mostrar apenas competitivos)</span>
                  </label>
                </div>
                
                {/* Contadores de status (quando disponível) */}
                {classificacaoInfo && classificacaoInfo.contagem_status && (
                  <div className="mt-3 pt-3 border-t border-green-200 flex flex-wrap gap-3 text-xs">
                    <span className="text-green-700 bg-green-100 px-2 py-1 rounded">
                      🟢 {classificacaoInfo.contagem_status.ATIVA || 0} ativas
                    </span>
                    <span className="text-blue-600 bg-blue-100 px-2 py-1 rounded">
                      🔵 {classificacaoInfo.contagem_status.CREDENCIAMENTOS || 0} credenciamentos
                    </span>
                    <span className="text-yellow-700 bg-yellow-100 px-2 py-1 rounded">
                      🟡 {classificacaoInfo.contagem_status.FUTURA || 0} futuras
                    </span>
                    <span className="text-gray-600 bg-gray-100 px-2 py-1 rounded">
                      🔴 {classificacaoInfo.contagem_status.ENCERRADA || 0} encerradas
                    </span>
                  </div>
                )}
              </div>
              
              {/* 🔒 P3: CAMADA DE CONFIABILIDADE DE DADOS */}
              <div className="bg-gradient-to-r from-amber-50 to-orange-50 border-2 border-amber-300 rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm font-bold text-amber-800 flex items-center gap-2">
                    🔒 Confiabilidade de Dados
                    <span className="text-xs font-normal text-amber-600 bg-amber-100 px-2 py-0.5 rounded">P3</span>
                  </span>
                </div>
                <p className="text-xs text-amber-700 mb-3">
                  Por padrão, mostra apenas oportunidades com <strong>quality_score ≥ 70</strong>.
                  Dados suspeitos ou de longo prazo são ocultados, mas você pode incluí-los explicitamente.
                </p>
                
                {/* Filtros de inclusão de dados especiais */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <label className={`flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-all ${
                    incluirSuspeitos 
                      ? 'bg-amber-500 text-white shadow-md' 
                      : 'bg-white text-gray-700 border border-gray-300 hover:border-amber-400'
                  }`}>
                    <input
                      type="checkbox"
                      checked={incluirSuspeitos}
                      onChange={(e) => setIncluirSuspeitos(e.target.checked)}
                      className="w-4 h-4"
                    />
                    <span className="text-sm font-medium">⚠️ Incluir datas atípicas</span>
                    <span className="text-xs opacity-80">(DATA_SUSPEITA)</span>
                  </label>
                  <label className={`flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-all ${
                    incluirPlanejamento 
                      ? 'bg-blue-500 text-white shadow-md' 
                      : 'bg-white text-gray-700 border border-gray-300 hover:border-blue-400'
                  }`}>
                    <input
                      type="checkbox"
                      checked={incluirPlanejamento}
                      onChange={(e) => setIncluirPlanejamento(e.target.checked)}
                      className="w-4 h-4"
                    />
                    <span className="text-sm font-medium">🧪 Incluir planejamento longo</span>
                    <span className="text-xs opacity-80">(&gt; 1 ano)</span>
                  </label>
                </div>
                
                {/* Estatísticas de confiabilidade (quando disponível) */}
                {confiabilidadeInfo && confiabilidadeInfo.auditoria && (
                  <div className="mt-3 pt-3 border-t border-amber-200 flex flex-wrap gap-3 text-xs">
                    <span className="text-green-700 bg-green-100 px-2 py-1 rounded">
                      ✅ {confiabilidadeInfo.auditoria.dados_validos || 0} válidos
                    </span>
                    <span className="text-amber-700 bg-amber-100 px-2 py-1 rounded">
                      ⚠️ {confiabilidadeInfo.auditoria.data_suspeita || 0} suspeitos
                    </span>
                    <span className="text-blue-600 bg-blue-100 px-2 py-1 rounded">
                      🧪 {confiabilidadeInfo.auditoria.planejamento_longo || 0} planejamento
                    </span>
                    <span className="text-red-600 bg-red-100 px-2 py-1 rounded">
                      ❌ {confiabilidadeInfo.auditoria.data_inconsistente || 0} inconsistentes
                    </span>
                  </div>
                )}
                
                {/* Estatísticas de qualidade */}
                {confiabilidadeInfo && confiabilidadeInfo.qualidade && (
                  <div className="mt-2 flex flex-wrap gap-3 text-xs">
                    <span className="text-purple-700 bg-purple-100 px-2 py-1 rounded">
                      📊 Score médio: {confiabilidadeInfo.qualidade.score_medio || 0}
                    </span>
                    <span className="text-green-600 bg-green-100 px-2 py-1 rounded">
                      ✅ {confiabilidadeInfo.qualidade.qualificam_default || 0} no feed
                    </span>
                    <span className="text-gray-600 bg-gray-100 px-2 py-1 rounded">
                      🚫 {confiabilidadeInfo.qualidade.excluidos_default || 0} filtrados
                    </span>
                  </div>
                )}
              </div>
              
              {/* 📅 FILTRO TEMPORAL */}
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-semibold text-blue-800 flex items-center gap-2">
                    📅 Filtro Temporal
                    <span className="text-xs font-normal text-blue-600">(complementar)</span>
                  </span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="flex items-center gap-2 text-sm text-blue-700">
                      <input
                        type="checkbox"
                        checked={incluirHistorico}
                        onChange={(e) => setIncluirHistorico(e.target.checked)}
                        className="w-4 h-4 text-blue-600"
                      />
                      📚 Incluir histórico completo
                    </label>
                    <p className="text-xs text-blue-500 mt-1 ml-6">
                      Mostrar processos antigos além do período
                    </p>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-blue-700 mb-1">Período de publicação</label>
                    <select
                      value={periodoDias}
                      onChange={(e) => setPeriodoDias(parseInt(e.target.value))}
                      className="w-full px-2 py-1 border border-blue-300 rounded text-sm bg-white"
                    >
                      <option value={30}>Últimos 30 dias</option>
                      <option value={90}>Últimos 90 dias (padrão)</option>
                      <option value={180}>Últimos 180 dias</option>
                      <option value={365}>Último ano</option>
                    </select>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={apenasReais}
                      onChange={(e) => setApenasReais(e.target.checked)}
                      className="w-4 h-4 text-blue-600"
                    />
                    Apenas Dados Reais (sem mock)
                  </label>
                </div>
                <div>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={apenasFuturas}
                      onChange={(e) => setApenasFuturas(e.target.checked)}
                      className="w-4 h-4 text-blue-600"
                    />
                    Apenas Futuras
                  </label>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Status</label>
                <select
                  value={statusFiltro}
                  onChange={(e) => setStatusFiltro(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                >
                  <option value="Todas">Todas</option>
                  <option value="Ativa">Ativa</option>
                  <option value="Encerrada">Encerrada</option>
                </select>
              </div>

              {/* Estado (UF) - Dados reais do banco local */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Estado (UF)
                  {usarBuscaLocal && filtrosDisponiveis.estados.length > 0 && (
                    <span className="text-xs text-green-600 ml-2">({filtrosDisponiveis.estados.length} disponíveis)</span>
                  )}
                </label>
                <select
                  value={estadoFiltro}
                  onChange={(e) => setEstadoFiltro(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                >
                  <option value="">Todos os Estados</option>
                  {filtrosDisponiveis.estados.length > 0 ? (
                    filtrosDisponiveis.estados.map((uf) => (
                      <option key={uf} value={uf}>{uf}</option>
                    ))
                  ) : (
                    <>
                      <option value="SP">São Paulo</option>
                      <option value="RJ">Rio de Janeiro</option>
                      <option value="MG">Minas Gerais</option>
                      <option value="BA">Bahia</option>
                      <option value="PR">Paraná</option>
                      <option value="RS">Rio Grande do Sul</option>
                      <option value="PE">Pernambuco</option>
                      <option value="CE">Ceará</option>
                      <option value="DF">Distrito Federal</option>
                      <option value="SC">Santa Catarina</option>
                      <option value="GO">Goiás</option>
                      <option value="ES">Espírito Santo</option>
                    </>
                  )}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Esfera
                  {usarBuscaLocal && filtrosDisponiveis.esferas.length > 0 && (
                    <span className="text-xs text-green-600 ml-2">({filtrosDisponiveis.esferas.length} disponíveis)</span>
                  )}
                </label>
                <select
                  value={esferaFiltro}
                  onChange={(e) => setEsferaFiltro(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                >
                  <option value="">Todas</option>
                  {filtrosDisponiveis.esferas.length > 0 ? (
                    filtrosDisponiveis.esferas.map((esfera) => (
                      <option key={esfera} value={esfera}>{esfera}</option>
                    ))
                  ) : (
                    <>
                      <option value="Federal">Federal</option>
                      <option value="Estadual">Estadual</option>
                      <option value="Municipal">Municipal</option>
                    </>
                  )}
                </select>
              </div>

              {/* NOVO: Filtros de Inteligência de Negócios (Saúde) */}
              <div className="col-span-1 md:col-span-2 border-t border-gray-300 pt-4 mt-2">
                <h4 className="text-sm font-bold text-emerald-700 mb-3 flex items-center gap-2">
                  🏥 Filtros de Saúde (Inteligência de Negócios)
                </h4>
                
                <div className="grid grid-cols-2 gap-2 mb-3">
                  <label className="flex items-center gap-2 text-sm bg-emerald-50 p-2 rounded-lg border border-emerald-200">
                    <input
                      type="checkbox"
                      checked={apenasSaude}
                      onChange={(e) => setApenasSaude(e.target.checked)}
                      className="w-4 h-4 text-emerald-600"
                    />
                    <span className="font-medium text-emerald-800">Apenas Saúde</span>
                  </label>
                  <label className="flex items-center gap-2 text-sm bg-red-50 p-2 rounded-lg border border-red-200">
                    <input
                      type="checkbox"
                      checked={apenasUrgentes}
                      onChange={(e) => setApenasUrgentes(e.target.checked)}
                      className="w-4 h-4 text-red-600"
                    />
                    <span className="font-medium text-red-800">🚨 Urgentes</span>
                  </label>
                </div>

                <p className="text-xs text-gray-500 mb-2">Filtrar por categoria de saúde:</p>
                <div className="flex flex-wrap gap-2">
                  {HEALTH_CATEGORIES.map((cat) => (
                    <button
                      key={cat.id}
                      type="button"
                      onClick={() => {
                        setCategoriaSaudeFiltro(prev =>
                          prev.includes(cat.id)
                            ? prev.filter(c => c !== cat.id)
                            : [...prev, cat.id]
                        );
                      }}
                      className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
                        categoriaSaudeFiltro.includes(cat.id)
                          ? 'bg-emerald-600 text-white shadow-md ring-2 ring-emerald-300'
                          : 'bg-gray-100 text-gray-700 hover:bg-emerald-100 hover:text-emerald-800'
                      }`}
                    >
                      <span>{cat.emoji}</span>
                      <span>{cat.label}</span>
                    </button>
                  ))}
                </div>
                
                {categoriaSaudeFiltro.length > 0 && (
                  <button
                    type="button"
                    onClick={() => setCategoriaSaudeFiltro([])}
                    className="mt-2 text-xs text-red-600 hover:text-red-800 flex items-center gap-1"
                  >
                    <X size={12} /> Limpar categorias selecionadas
                  </button>
                )}
              </div>
            </div>
          )}
        </form>
      </div>

      {loading && (
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-blue-500 border-t-transparent"></div>
          <p className="mt-4 text-gray-600">Buscando licitações...</p>
        </div>
      )}

      {/* 🛡️ DIRETRIZ ANTI-TELA BRANCA v3.3: Validação segura de resultados */}
      {!loading && Array.isArray(resultados) && resultados.length > 0 && (
        <div className="space-y-4">
          <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-4">
            <div className="flex flex-col md:flex-row md:items-center gap-2 md:gap-4 w-full">
              <h2 className="text-xl md:text-2xl font-bold text-gray-800">
                {totalResultados || resultados.length} resultado(s) encontrado(s)
              </h2>
              
              {/* Seletor de Resultados por Página (Topo) */}
              <div className="flex items-center gap-2 bg-gray-100 px-3 py-1.5 rounded-lg border border-gray-200">
                <span className="text-[10px] font-bold text-gray-500 uppercase">Mostrar:</span>
                <select
                  value={perPage}
                  onChange={(e) => {
                    const val = parseInt(e.target.value);
                    setPerPage(val);
                    setTimeout(() => handleSearch(null, 1), 10);
                  }}
                  className="text-xs font-bold text-blue-700 bg-transparent focus:outline-none cursor-pointer"
                >
                  <option value={15}>15 por página</option>
                  <option value={20}>20 por página</option>
                  <option value={25}>25 por página</option>
                  <option value={50}>50 por página</option>
                  <option value={100}>100 por página</option>
                </select>
              </div>
            </div>

            <div className="flex gap-2 w-full md:w-auto overflow-x-auto pb-2 md:pb-0">
              <button
                onClick={() => handleExport('excel')}
                className="whitespace-nowrap px-3 py-1 md:px-4 md:py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors text-xs md:text-sm font-medium flex items-center gap-2"
              >
                📊 Excel Premium
              </button>
              <button
                onClick={() => handleExport('csv')}
                className="whitespace-nowrap px-3 py-1 md:px-4 md:py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-xs md:text-sm font-medium"
              >
                📥 CSV
              </button>
              <button
                onClick={() => handleExport('json')}
                className="whitespace-nowrap px-3 py-1 md:px-4 md:py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors text-xs md:text-sm font-medium"
              >
                📥 JSON
              </button>
            </div>
          </div>

          {/* 🛡️ Renderização segura: verifica cada item antes de renderizar */}
          {/* 🖍️ v3.7: Passa termo de busca para Grifo Visual (Highlight) */}
          {resultados.map((licitacao, index) => {
            // Proteção contra itens nulos ou inválidos
            if (!licitacao || typeof licitacao !== 'object') {
              return null;
            }
            return (
              <LicitacaoCard 
                key={licitacao.id || licitacao._id || `licitacao-${index}`} 
                licitacao={licitacao}
                termoBusca={medicamento}
              />
            );
          })}

          {paginationInfo && paginationInfo.total_pages > 1 && (
            <div className="flex flex-col md:flex-row justify-center items-center gap-4 mt-8 pb-10">
              {/* Seletor de Resultados por Página */}
              <div className="flex items-center gap-2 bg-white px-3 py-1.5 rounded-lg border border-gray-300 shadow-sm">
                <span className="text-xs font-semibold text-gray-500 uppercase">Ver:</span>
                <select
                  value={perPage}
                  onChange={(e) => {
                    const val = parseInt(e.target.value);
                    setPerPage(val);
                    // Disparar busca imediatamente com o novo limite
                    setTimeout(() => handleSearch(null, 1), 10);
                  }}
                  className="text-sm font-bold text-blue-600 bg-transparent focus:outline-none cursor-pointer"
                >
                  <option value={15}>15</option>
                  <option value={20}>20</option>
                  <option value={25}>25</option>
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                </select>
              </div>

              {/* Controles de Navegação */}
              <div className="flex items-center gap-1">
                <button
                  onClick={() => handlePageChange(currentPage - 1)}
                  disabled={!paginationInfo.has_prev}
                  className="p-2 bg-white border border-gray-300 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50 transition-colors shadow-sm"
                  title="Anterior"
                >
                  <span className="text-blue-600 font-bold">←</span>
                </button>
                
                <div className="flex items-center bg-blue-50 px-4 py-2 rounded-lg border border-blue-200">
                  <span className="text-sm font-bold text-blue-700">
                    Página {paginationInfo.page || currentPage} de {paginationInfo.total_pages}
                  </span>
                </div>

                <button
                  onClick={() => handlePageChange(currentPage + 1)}
                  disabled={!paginationInfo.has_next}
                  className="p-2 bg-white border border-gray-300 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50 transition-colors shadow-sm"
                  title="Próxima"
                >
                  <span className="text-blue-600 font-bold">→</span>
                </button>
              </div>

              {/* Atalho para primeira/última (opcional, mas pro) */}
              <div className="hidden lg:flex items-center gap-2">
                <button 
                  onClick={() => handlePageChange(1)}
                  className="text-xs font-semibold text-gray-400 hover:text-blue-600 transition-colors uppercase tracking-wider"
                >
                  Primeira
                </button>
                <span className="text-gray-300">|</span>
                <button 
                  onClick={() => handlePageChange(paginationInfo.total_pages)}
                  className="text-xs font-semibold text-gray-400 hover:text-blue-600 transition-colors uppercase tracking-wider"
                >
                  Última
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {!loading && resultados.length === 0 && totalResultados === 0 && medicamento && (
        <div className="text-center py-12 bg-gray-50 rounded-lg">
          <p className="text-gray-600 text-lg">Nenhum resultado encontrado para &quot;{medicamento}&quot;</p>
        </div>
      )}

      {mostrarListas && (
        <ListasManager
          onClose={() => setMostrarListas(false)}
          onListaSelected={(lista) => {
            setListaSelecionada(lista);
            setMostrarListas(false);
          }}
        />
      )}
    </main>
  );
});

SearchPage.displayName = 'SearchPage';

export default SearchPage;