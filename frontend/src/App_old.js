import React, { useState, useEffect } from 'react';
import './App.css';
import axios from 'axios';
import ListasManager from './components/ListasManager';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [medicamento, setMedicamento] = useState('');
  const [loading, setLoading] = useState(false);
  const [resultados, setResultados] = useState([]);
  const [totalResultados, setTotalResultados] = useState(0);
  const [tagsFiltro, setTagsFiltro] = useState([]);
  const [apenasReais, setApenasReais] = useState(false);
  const [apenasFuturas, setApenasFuturas] = useState(false);
  const [stats, setStats] = useState(null);
  const [mostrarListas, setMostrarListas] = useState(false);
  const [listaSelecionada, setListaSelecionada] = useState(null);

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API}/stats`);
      setStats(response.data);
    } catch (error) {
      console.error('Erro ao buscar estatísticas:', error);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);  

  const handleSearch = async (e) => {
    e.preventDefault();
    
    // Permitir busca apenas com filtros (sem medicamento) ou por lista
    if (!medicamento.trim() && tagsFiltro.length === 0 && !listaSelecionada) {
      alert('Digite um medicamento OU selecione pelo menos um filtro (Alto Custo, Importado ou Judicial) OU use uma lista');
      return;
    }

    setLoading(true);
    setResultados([]);
    
    try {
      const response = await axios.post(`${API}/search`, {
        medicamento: medicamento.trim() || null,
        tags: tagsFiltro.length > 0 ? tagsFiltro : null,
        apenas_reais: apenasReais,
        apenas_futuras: apenasFuturas,
        lista_id: listaSelecionada?.id || null
      });

      setTimeout(() => {
        setResultados(response.data.resultados || []);
        setTotalResultados(response.data.total || 0);
        setLoading(false);
        fetchStats();
      }, 200);
    } catch (error) {
      console.error('Erro na busca:', error);
      alert('Erro ao buscar medicamento. Tente novamente.');
      setLoading(false);
    }
  };

  const handleListaSelecionada = (lista) => {
    setListaSelecionada(lista);
    setMedicamento(''); // Limpar campo de medicamento quando selecionar lista
    // Automaticamente fazer a busca
    setTimeout(() => {
      const event = new Event('submit', { cancelable: true, bubbles: true });
      document.querySelector('form')?.dispatchEvent(event);
    }, 100);
  };

  const limparListaSelecionada = () => {
    setListaSelecionada(null);
  };

  const toggleTag = (tag) => {
    setTagsFiltro(prev => 
      prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag]
    );
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('pt-BR');
  };

  const getStatusColor = (status) => {
    const colors = {
      'Em Licitação': 'bg-blue-100 text-blue-800',
      'Contratado': 'bg-green-100 text-green-800',
      'Fornecimento Judicial': 'bg-purple-100 text-purple-800',
      'Em Análise': 'bg-yellow-100 text-yellow-800',
      'Suspenso': 'bg-red-100 text-red-800'
    };
    return colors[status] || 'bg-gray-100 text-gray-800';
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-green-50">
      {/* Header */}
      <header className="bg-white shadow-md border-b-4 border-blue-600">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold text-blue-900">BEM 🏥</h1>
              <p className="text-sm text-gray-600 mt-1">Buscador Estadual de Medicamentos</p>
            </div>
            <div className="flex items-center gap-6">
              <button
                onClick={() => setMostrarListas(true)}
                className="px-6 py-3 bg-gradient-to-r from-green-600 to-green-700 text-white rounded-lg hover:from-green-700 hover:to-green-800 transition-all shadow-md font-medium flex items-center gap-2"
              >
                📋 Minhas Listas
              </button>
              {stats && (
                <div className="text-right">
                  <p className="text-sm text-gray-600">Total de Licitações</p>
                  <p className="text-2xl font-bold text-blue-900">{stats.total_licitacoes}</p>
                  <p className="text-xs text-gray-500">
                    {stats.licitacoes_reais} reais | {stats.licitacoes_mock} mockadas
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* Lista Selecionada */}
        {listaSelecionada && (
          <div className="bg-green-50 border-2 border-green-300 rounded-lg p-4 mb-6 flex items-center justify-between">
            <div>
              <p className="text-sm text-green-700 font-medium">📋 Buscando por lista:</p>
              <p className="text-lg font-bold text-green-900">{listaSelecionada.nome}</p>
              <p className="text-sm text-green-600 mt-1">
                {listaSelecionada.medicamentos.length} medicamento(s): {listaSelecionada.medicamentos.slice(0, 3).join(', ')}
                {listaSelecionada.medicamentos.length > 3 && '...'}
              </p>
            </div>
            <button
              onClick={limparListaSelecionada}
              className="px-4 py-2 bg-green-700 text-white rounded-lg hover:bg-green-800 transition-colors font-medium"
            >
              Limpar Lista
            </button>
          </div>
        )}
        
        {/* Search */}
        <div className="bg-white rounded-lg shadow-lg p-6 mb-8">
          <form onSubmit={handleSearch} className="space-y-4">
            <div className="flex gap-4">
              <div className="flex-1">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Nome do Medicamento ou Princípio Ativo <span className="text-gray-400 font-normal">(opcional se usar filtros ou lista)</span>
                </label>
                <input
                  type="text"
                  value={medicamento}
                  onChange={(e) => setMedicamento(e.target.value)}
                  placeholder="Ex: Adalimumabe OU use 'Minhas Listas' acima"
                  disabled={!!listaSelecionada}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 disabled:text-gray-500"
                />
              </div>
              <div className="flex items-end">
                <button
                  type="submit"
                  disabled={loading}
                  className="px-8 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 font-medium"
                >
                  {loading ? 'Buscando...' : 'Buscar'}
                </button>
              </div>
            </div>

            {/* Filters */}
            <div className="flex flex-wrap gap-4 items-center pt-4 border-t border-gray-200">
              <button
                type="button"
                onClick={() => toggleTag('alto_custo')}
                className={`px-4 py-2 rounded-full text-sm font-medium ${
                  tagsFiltro.includes('alto_custo')
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700'
                }`}
              >
                💰 Alto Custo
              </button>
              <button
                type="button"
                onClick={() => toggleTag('importado')}
                className={`px-4 py-2 rounded-full text-sm font-medium ${
                  tagsFiltro.includes('importado')
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700'
                }`}
              >
                🌍 Importado
              </button>
              <button
                type="button"
                onClick={() => toggleTag('judicial')}
                className={`px-4 py-2 rounded-full text-sm font-medium ${
                  tagsFiltro.includes('judicial')
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700'
                }`}
              >
                ⚖️ Judicial
              </button>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={apenasReais}
                  onChange={(e) => setApenasReais(e.target.checked)}
                  className="w-4 h-4"
                />
                <span className="text-sm">Apenas dados reais (CE, ES, SP)</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={apenasFuturas}
                  onChange={(e) => setApenasFuturas(e.target.checked)}
                  className="w-4 h-4"
                />
                <span className="text-sm font-semibold text-green-700">🔮 Apenas Licitações Futuras</span>
              </label>
            </div>
          </form>
        </div>

        {/* Results Count */}
        {totalResultados > 0 && (
          <div className="mb-6">
            <p className="text-lg text-gray-700">
              <span className="font-bold text-blue-900">{totalResultados}</span> resultados encontrados
              {medicamento && ` para "${medicamento}"`}
            </p>
          </div>
        )}

        {/* Results */}
        {resultados.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {resultados.map((res, idx) => (
              <div
                key={`card-${idx}-${res.estado}-${res.numero_processo}`}
                className={`bg-white rounded-lg shadow-md p-6 border-l-4 ${
                  res.is_mock ? 'border-gray-400' : 'border-green-500'
                }`}
              >
                <div className="mb-4">
                  <h3 className="font-bold text-lg text-gray-900 mb-1">{res.medicamento}</h3>
                  <p className="text-sm font-semibold text-blue-900">📍 {res.estado}</p>
                  <span className={`inline-block mt-2 px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(res.status)}`}>
                    {res.status}
                  </span>
                </div>

                {res.tags && res.tags.length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-4">
                    {res.tags.map((tag, ti) => (
                      <span key={`tag-${ti}`} className="px-2 py-1 bg-blue-50 text-blue-700 text-xs rounded">
                        {tag === 'alto_custo' && '💰 Alto Custo'}
                        {tag === 'importado' && '🌍 Importado'}
                        {tag === 'judicial' && '⚖️ Judicial'}
                      </span>
                    ))}
                  </div>
                )}

                <div className="bg-blue-50 p-3 rounded-lg mb-3">
                  <p className="text-xs text-blue-600 font-semibold mb-1">LOCAL:</p>
                  <p className="font-bold text-gray-900 text-sm">{res.orgao_licitante}</p>
                </div>

                <div className="bg-green-50 p-3 rounded-lg mb-3">
                  <p className="text-xs text-green-600 font-semibold mb-1">DATA PUBLICAÇÃO:</p>
                  <p className="font-bold text-gray-900">{formatDate(res.data_referencia)}</p>
                </div>

                {res.data_abertura && (
                  <div className="bg-yellow-50 p-3 rounded-lg mb-3 border-2 border-yellow-400">
                    <p className="text-xs text-yellow-700 font-semibold mb-1">⏰ DATA DE ABERTURA:</p>
                    <p className="font-bold text-gray-900 text-lg">{formatDate(res.data_abertura)}</p>
                  </div>
                )}

                <div className="text-sm text-gray-600 mb-3">
                  <p className="font-medium">{res.modalidade}</p>
                  <p className="text-xs">Processo: {res.numero_processo}</p>
                  {res.fonte && (
                    <p className="text-xs mt-1">
                      <span className={`px-2 py-1 rounded ${res.fonte === 'PNCP' ? 'bg-purple-100 text-purple-700 font-semibold' : 'bg-gray-100 text-gray-600'}`}>
                        {res.fonte === 'PNCP' ? '🏛️ PNCP' : '🏢 ' + res.estado}
                      </span>
                    </p>
                  )}
                </div>

                {res.link_documento ? (
                  <>
                    <a
                      href={res.link_documento}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block w-full bg-green-600 hover:bg-green-700 text-white font-bold py-3 px-4 rounded-lg text-center mb-2"
                    >
                      📄 BAIXAR EDITAL (PDF)
                    </a>
                    <a
                      href={res.link_origem}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block w-full text-center text-sm text-blue-600 hover:underline"
                    >
                      Ver no portal oficial
                    </a>
                  </>
                ) : (
                  <a
                    href={res.link_origem}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-4 rounded-lg text-center mb-2"
                  >
                    🔗 ACESSAR PÁGINA DO EDITAL
                  </a>
                )}
                <p className="text-xs text-gray-500 text-center mt-1">
                  {res.link_documento ? 'PDF disponível para download' : 'Consulte o edital no portal oficial'}
                </p>
              </div>
            ))}
          </div>
        )}

        {!loading && medicamento && resultados.length === 0 && (
          <div className="text-center py-12">
            <p className="text-gray-600">Nenhum resultado encontrado para &quot;{medicamento}&quot;</p>
          </div>
        )}

        {/* Info */}
        <div className="mt-12 bg-blue-50 border border-blue-200 rounded-lg p-6">
          <h3 className="font-semibold text-blue-900 mb-2">💡 Nova Funcionalidade: Listas Customizadas</h3>
          <p className="text-sm text-gray-700">
            Crie até <strong>5 listas personalizadas</strong> com seus medicamentos de interesse! 
            Clique em &quot;Minhas Listas&quot; no topo da página.
          </p>
          <p className="text-sm text-gray-600 mt-2">
            <strong>Estados com scraping real:</strong> Ceará (CE), Espírito Santo (ES) e São Paulo (SP). 
            Os demais estados apresentam dados de exemplo.
          </p>
        </div>
      </main>

      {/* Modal de Listas */}
      {mostrarListas && (
        <ListasManager
          onClose={() => setMostrarListas(false)}
          onListaSelected={handleListaSelecionada}
        />
      )}
    </div>
  );
}

export default App;
