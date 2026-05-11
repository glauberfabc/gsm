import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  Plus, Trash2, Search, Bell, AlertTriangle, 
  Activity, List as ListIcon, ShieldAlert,
  ChevronRight, ExternalLink, RefreshCw
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const RadarFarmaceuticoPage = () => {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [stats, setStats] = useState(null);
  const [interesseData, setInteresseData] = useState([]);
  const [matches, setMatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [scanLoading, setScanLoading] = useState(false);
  const [newMed, setNewMed] = useState({
    medicamento: '',
    principio_ativo: '',
    categoria: 'Oncologia',
    prioridade: 'media',
    target_type: 'Importacao'
  });

  useEffect(() => {
    fetchData();
  }, [activeTab]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [statsRes, interesseRes, matchesRes] = await Promise.all([
        axios.get(`${API}/radar-farma/stats`),
        axios.get(`${API}/radar-farma/interesse`),
        axios.get(`${API}/radar-farma/matches`)
      ]);
      setStats(statsRes.data);
      setInteresseData(interesseRes.data);
      setMatches(matchesRes.data);
    } catch (error) {
      console.error('Erro ao buscar dados do Radar:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAddInteresse = async (e) => {
    e.preventDefault();
    try {
      await axios.post(`${API}/radar-farma/interesse`, newMed);
      setNewMed({
        medicamento: '',
        principio_ativo: '',
        categoria: 'Oncologia',
        prioridade: 'media',
        target_type: 'Importacao'
      });
      fetchData();
    } catch (error) {
      alert('Erro ao adicionar medicamento');
    }
  };

  const handleRemoveInteresse = async (id) => {
    if (window.confirm('Deseja remover este medicamento da lista de interesse?')) {
      try {
        await axios.delete(`${API}/radar-farma/interesse/${id}`);
        fetchData();
      } catch (error) {
        alert('Erro ao remover');
      }
    }
  };

  const handleRunScan = async () => {
    setScanLoading(true);
    try {
      const response = await axios.post(`${API}/radar-farma/scan`);
      alert(response.data.message);
    } catch (error) {
      alert('Erro ao iniciar varredura');
    } finally {
      setTimeout(() => setScanLoading(false), 2000);
    }
  };

  const renderDashboard = () => (
    <div className="space-y-6">
      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 flex items-center space-x-4">
          <div className="bg-blue-100 p-3 rounded-xl text-blue-600">
            <ListIcon size={24} />
          </div>
          <div>
            <p className="text-sm text-gray-500 font-medium text-nowrap">Lista de Interesse</p>
            <p className="text-2xl font-bold text-gray-800">{stats?.total_lista_interesse || 0}</p>
          </div>
        </div>
        
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 flex items-center space-x-4">
          <div className="bg-red-100 p-3 rounded-xl text-red-600">
            <AlertTriangle size={24} />
          </div>
          <div>
            <p className="text-sm text-gray-500 font-medium text-nowrap">Casos Críticos</p>
            <p className="text-2xl font-bold text-gray-800">{stats?.criticos || 0}</p>
          </div>
        </div>

        <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 flex items-center space-x-4">
          <div className="bg-amber-100 p-3 rounded-xl text-amber-600">
            <Search size={24} />
          </div>
          <div>
            <p className="text-sm text-gray-500 font-medium text-nowrap">Total Detecções</p>
            <p className="text-2xl font-bold text-gray-800">{stats?.total_desabastecimento || 0}</p>
          </div>
        </div>

        <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 flex items-center space-x-4">
          <div className="bg-green-100 p-3 rounded-xl text-green-600">
            <RefreshCw size={24} />
          </div>
          <div>
            <p className="text-sm text-gray-500 font-medium text-nowrap">Reativações</p>
            <p className="text-2xl font-bold text-gray-800">{stats?.reativados || 0}</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Radar Status Table */}
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
          <h3 className="text-lg font-bold text-gray-800 mb-4 flex items-center">
            <ShieldAlert size={20} className="mr-2 text-red-500" />
            Alertas Críticos Recentes
          </h3>
          <div className="space-y-4">
            {matches.filter(m => m.score_boost >= 95).slice(0, 5).map((match, i) => (
              <div key={i} className="flex items-center justify-between p-3 bg-red-50 rounded-xl border border-red-100">
                <div className="flex items-center space-x-3">
                  <div className="bg-white p-2 rounded-lg text-red-600 border border-red-200">
                    <Activity size={16} />
                  </div>
                  <div>
                    <p className="text-sm font-bold text-gray-800">{match.medicamento}</p>
                    <p className="text-xs text-red-600 font-medium uppercase tracking-wider">{match.status_anvisa.replace(/_/g, ' ')}</p>
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                   <div className="text-right mr-3">
                      <p className="text-[10px] text-gray-400 font-semibold uppercase">Publicação</p>
                      <p className="text-xs text-gray-600 font-bold">{match.data_interrupcao}</p>
                   </div>
                   <ChevronRight size={16} className="text-red-400" />
                </div>
              </div>
            ))}
            {matches.filter(m => m.score_boost >= 95).length === 0 && (
              <div className="text-center py-8">
                <p className="text-gray-400 text-sm italic">Nenhum alerta crítico detectado nas últimas 24h.</p>
              </div>
            )}
          </div>
        </div>

        {/* Categories Chart (Placeholder conceptually, using list) */}
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
          <h3 className="text-lg font-bold text-gray-800 mb-4">Monitoramento por Categoria</h3>
          <div className="space-y-3">
            {stats && Object.entries(stats.por_categoria).map(([cat, count], i) => (
              <div key={i}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="font-medium text-gray-700">{cat}</span>
                  <span className="text-gray-500 font-bold">{count} docs</span>
                </div>
                <div className="w-full bg-gray-100 rounded-full h-2">
                  <div 
                    className="bg-blue-500 h-2 rounded-full transition-all duration-500" 
                    style={{ width: `${Math.min((count / (stats.total_desabastecimento || 1)) * 100, 100)}%` }}
                  ></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );

  const renderInteresse = () => (
    <div className="space-y-6">
      <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
        <h3 className="text-lg font-bold text-gray-800 mb-4">Adicionar Medicamento Estratégico</h3>
        <form onSubmit={handleAddInteresse} className="grid grid-cols-1 md:grid-cols-5 gap-4">
          <input 
            type="text" 
            placeholder="Medicamento" 
            className="px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500 outline-none text-sm"
            value={newMed.medicamento}
            onChange={e => setNewMed({...newMed, medicamento: e.target.value})}
            required
          />
          <input 
            type="text" 
            placeholder="Princípio Ativo" 
            className="px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500 outline-none text-sm"
            value={newMed.principio_ativo}
            onChange={e => setNewMed({...newMed, principio_ativo: e.target.value})}
          />
          <select 
            className="px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500 outline-none text-sm"
            value={newMed.categoria}
            onChange={e => setNewMed({...newMed, categoria: e.target.value})}
          >
            <option value="Oncologia">Oncologia</option>
            <option value="Doencas Raras">Doenças Raras</option>
            <option value="Peptideos">Peptídeos</option>
            <option value="Especialidades">Especialidades</option>
          </select>
          <select 
            className="px-4 py-2 rounded-xl border border-gray-200 focus:ring-2 focus:ring-blue-500 outline-none text-sm"
            value={newMed.prioridade}
            onChange={e => setNewMed({...newMed, prioridade: e.target.value})}
          >
            <option value="alta">Prioridade Alta</option>
            <option value="media">Prioridade Média</option>
            <option value="baixa">Prioridade Baixa</option>
          </select>
          <button 
            type="submit"
            className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded-xl transition-all flex items-center justify-center space-x-2 shadow-lg shadow-blue-200"
          >
            <Plus size={18} />
            <span>Adicionar</span>
          </button>
        </form>
      </div>

      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
        <table className="w-full text-left">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-100">
              <th className="px-6 py-4 text-xs font-bold text-gray-500 uppercase">Medicamento</th>
              <th className="px-6 py-4 text-xs font-bold text-gray-500 uppercase">Princípio Ativo</th>
              <th className="px-6 py-4 text-xs font-bold text-gray-500 uppercase">Categoria</th>
              <th className="px-6 py-4 text-xs font-bold text-gray-500 uppercase">Prioridade</th>
              <th className="px-6 py-4 text-xs font-bold text-gray-500 uppercase text-right">Ações</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 text-sm">
            {interesseData.map((item, i) => (
              <tr key={i} className="hover:bg-blue-50 transition-colors">
                <td className="px-6 py-4 font-bold text-gray-800">{item.medicamento}</td>
                <td className="px-6 py-4 text-gray-600">{item.principio_ativo}</td>
                <td className="px-6 py-4">
                  <span className="bg-blue-100 text-blue-700 text-[10px] font-bold px-2 py-1 rounded-full uppercase tracking-wider">
                    {item.categoria}
                  </span>
                </td>
                <td className="px-6 py-4">
                   <span className={`text-xs font-bold ${item.prioridade === 'alta' ? 'text-red-500' : 'text-amber-500'}`}>
                    {item.prioridade.toUpperCase()}
                  </span>
                </td>
                <td className="px-6 py-4 text-right">
                  <button 
                    onClick={() => handleRemoveInteresse(item.id)}
                    className="text-red-400 hover:text-red-600 p-1 hover:bg-red-50 rounded-lg transition-all"
                  >
                    <Trash2 size={18} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );

  const renderDeteccao = () => (
    <div className="space-y-6">
      <div className="flex justify-between items-center bg-white p-4 rounded-2xl border border-gray-100 shadow-sm">
        <p className="text-sm text-gray-500 italic">Varredura automática via DOU Seção 1 (v78.0 Inteligência)</p>
        <button 
          onClick={handleRunScan}
          disabled={scanLoading}
          className={`${scanLoading ? 'bg-gray-100 text-gray-400' : 'bg-blue-600 text-white hove:bg-blue-700'} text-xs font-bold py-2 px-4 rounded-xl flex items-center space-x-2 transition-all`}
        >
          <RefreshCw size={14} className={scanLoading ? 'animate-spin' : ''} />
          <span>{scanLoading ? 'Varrendo...' : 'Forçar Varredura Manual'}</span>
        </button>
      </div>

      <div className="grid grid-cols-1 gap-4">
        {matches.map((match, i) => (
          <div key={i} className={`bg-white rounded-2xl p-6 border-l-4 shadow-sm border border-gray-100 ${match.score_boost >= 95 ? 'border-l-red-500' : 'border-l-blue-400'}`}>
            <div className="flex justify-between items-start mb-4">
              <div>
                <div className="flex items-center space-x-2 mb-1">
                  <h4 className="text-lg font-bold text-gray-800">{match.medicamento}</h4>
                  {match.score_boost >= 95 && (
                    <span className="bg-red-100 text-red-600 text-[9px] font-black px-2 py-0.5 rounded-full uppercase">Alerta Crítico</span>
                  )}
                </div>
                <p className="text-sm text-gray-500">{match.principio_ativo} | {match.categoria_terapeutica}</p>
              </div>
              <div className="text-right">
                <span className={`text-[10px] font-black px-2 py-1 rounded-md uppercase tracking-tight ${match.score_boost >= 95 ? 'bg-red-50 text-red-600' : 'bg-blue-50 text-blue-600'}`}>
                  SCORE GSM: {match.score_boost}%
                </span>
                <p className="text-[10px] text-gray-400 mt-1 font-bold uppercase">{match.fonte_deteccao}</p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-4">
               <div className="bg-gray-50 p-3 rounded-xl">
                 <p className="text-[10px] text-gray-400 font-bold uppercase mb-1">Status ANVISA</p>
                 <p className="text-sm font-bold text-gray-700 uppercase tracking-tight">{match.status_anvisa.replace(/_/g, ' ')}</p>
               </div>
               <div className="bg-gray-50 p-3 rounded-xl">
                 <p className="text-[10px] text-gray-400 font-bold uppercase mb-1">Data Publicação</p>
                 <p className="text-sm font-bold text-gray-700">{match.data_interrupcao}</p>
               </div>
               <div className="bg-gray-50 p-3 rounded-xl">
                 <p className="text-[10px] text-gray-400 font-bold uppercase mb-1">Retorno Previsto</p>
                 <p className="text-sm font-bold text-blue-600">{match.previsao_retorno || 'NÃO INFORMADO'}</p>
               </div>
            </div>

            <div className="p-4 bg-gray-50 italic text-gray-600 text-xs rounded-xl border border-gray-100 line-clamp-2 hover:line-clamp-none transition-all">
               "{match.descricao_fonte}..."
            </div>
            
            <div className="mt-4 flex justify-end">
              <a 
                href={match.link_fonte} 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-blue-600 text-[11px] font-bold flex items-center space-x-1 hover:underline"
              >
                <span>Ver Publicação Original</span>
                <ExternalLink size={12} />
              </a>
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <div className="p-4 md:p-8 max-w-7xl mx-auto min-h-screen">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
        <div>
          <h1 className="text-3xl font-black text-gray-800 tracking-tight flex items-center">
            Radar Farmacêutico
            <span className="ml-3 bg-red-600 text-white text-[10px] px-2 py-0.5 rounded-full font-black uppercase tracking-widest animate-pulse">PRO v3.1</span>
          </h1>
          <p className="text-gray-500 font-medium">Inteligência Estratégica de Desabastecimento e Antecipação Normativa</p>
        </div>
        <div className="flex space-x-2">
           <div className="bg-white px-4 py-2 rounded-2xl shadow-sm border border-gray-100 flex items-center space-x-3">
              <div className="w-2 h-2 bg-green-500 rounded-full animate-ping"></div>
              <span className="text-xs font-bold text-gray-700 uppercase">Sistema Ativo (Real-Time)</span>
           </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex space-x-1 p-1 bg-gray-200/50 rounded-2xl mb-8 w-fit">
        <button 
          onClick={() => setActiveTab('dashboard')}
          className={`flex items-center space-x-2 px-6 py-2.5 rounded-xl font-bold text-sm transition-all ${activeTab === 'dashboard' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}
        >
          <Activity size={18} />
          <span>Dashboard</span>
        </button>
        <button 
          onClick={() => setActiveTab('interesse')}
          className={`flex items-center space-x-2 px-6 py-2.5 rounded-xl font-bold text-sm transition-all ${activeTab === 'interesse' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}
        >
          <ListIcon size={18} />
          <span>Lista de Interesse</span>
        </button>
        <button 
          onClick={() => setActiveTab('deteccao')}
          className={`flex items-center space-x-2 px-6 py-2.5 rounded-xl font-bold text-sm transition-all ${activeTab === 'deteccao' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}
        >
          <Bell size={18} />
          <span>Detecção DOU/ANVISA</span>
          {stats?.criticos > 0 && (
            <span className="ml-1 bg-red-500 text-white text-[9px] w-4 h-4 flex items-center justify-center rounded-full">
              {stats.criticos}
            </span>
          )}
        </button>
      </div>

      {/* Content */}
      <div className="transition-all duration-300">
        {loading ? (
          <div className="flex flex-col items-center justify-center py-20">
             <RefreshCw size={40} className="text-blue-500 animate-spin mb-4" />
             <p className="text-gray-500 font-bold animate-pulse">Carregando Inteligência de Mercado...</p>
          </div>
        ) : (
          <>
            {activeTab === 'dashboard' && renderDashboard()}
            {activeTab === 'interesse' && renderInteresse()}
            {activeTab === 'deteccao' && renderDeteccao()}
          </>
        )}
      </div>
    </div>
  );
};

export default RadarFarmaceuticoPage;
