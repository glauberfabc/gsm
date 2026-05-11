import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { 
  Bell, Plus, Trash2, Edit2, Check, X, Clock, 
  AlertCircle, CheckCircle, Archive, RefreshCw,
  ChevronDown, ChevronUp, Filter
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// ==================== MODAL DE CRIAR/EDITAR ALERTA ====================
const AlertaModal = ({ isOpen, onClose, alerta, onSave }) => {
  const [formData, setFormData] = useState({
    nome: '',
    tipo: 'palavra_chave',
    ativo: true,
    palavras_chave: '',
    estados: [],
    modalidades: [],
    frequencia_horas: 6,
    email_notificacao: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const estados = ['AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS', 
                   'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC', 
                   'SP', 'SE', 'TO'];
  
  const modalidades = ['Pregão Eletrônico', 'Concorrência', 'Tomada de Preços', 'Dispensa'];

  useEffect(() => {
    if (alerta) {
      setFormData({
        nome: alerta.nome || '',
        tipo: alerta.tipo || 'palavra_chave',
        ativo: alerta.ativo !== false,
        palavras_chave: (alerta.palavras_chave || []).join(', '),
        estados: alerta.estados || [],
        modalidades: alerta.modalidades || [],
        frequencia_horas: alerta.frequencia_horas || 6,
        email_notificacao: alerta.email_notificacao || ''
      });
    } else {
      setFormData({
        nome: '',
        tipo: 'palavra_chave',
        ativo: true,
        palavras_chave: '',
        estados: [],
        modalidades: [],
        frequencia_horas: 6,
        email_notificacao: ''
      });
    }
    setError('');
  }, [alerta, isOpen]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const palavrasArray = formData.palavras_chave
        .split(',')
        .map(p => p.trim().toLowerCase())
        .filter(p => p.length > 0);

      const payload = {
        nome: formData.nome,
        tipo: formData.tipo,
        ativo: formData.ativo,
        palavras_chave: palavrasArray,
        estados: formData.estados,
        modalidades: formData.modalidades,
        frequencia_horas: formData.frequencia_horas,
        email_notificacao: formData.email_notificacao || null
      };

      if (alerta?.id) {
        await axios.put(`${API}/alertas/${alerta.id}`, payload);
      } else {
        await axios.post(`${API}/alertas`, payload);
      }

      onSave();
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || 'Erro ao salvar alerta');
    } finally {
      setLoading(false);
    }
  };

  const toggleEstado = (uf) => {
    setFormData(prev => ({
      ...prev,
      estados: prev.estados.includes(uf)
        ? prev.estados.filter(e => e !== uf)
        : [...prev.estados, uf]
    }));
  };

  const toggleModalidade = (mod) => {
    setFormData(prev => ({
      ...prev,
      modalidades: prev.modalidades.includes(mod)
        ? prev.modalidades.filter(m => m !== mod)
        : [...prev.modalidades, mod]
    }));
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="p-6 border-b">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-bold text-gray-800">
              {alerta ? 'Editar Alerta' : 'Criar Novo Alerta'}
            </h2>
            <button onClick={onClose} className="text-gray-500 hover:text-gray-700">
              <X className="w-6 h-6" />
            </button>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          {error && (
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-600 flex items-center gap-2">
              <AlertCircle className="w-5 h-5" />
              {error}
            </div>
          )}

          {/* Nome do Alerta */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Nome do Alerta *
            </label>
            <input
              type="text"
              value={formData.nome}
              onChange={(e) => setFormData(prev => ({ ...prev, nome: e.target.value }))}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="Ex: Alerta Insulina SP"
              required
            />
          </div>

          {/* Palavras-chave */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Palavras-chave (separadas por vírgula)
            </label>
            <textarea
              value={formData.palavras_chave}
              onChange={(e) => setFormData(prev => ({ ...prev, palavras_chave: e.target.value }))}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="insulina, diabetes, medicamento"
              rows={2}
            />
            <p className="mt-1 text-xs text-gray-500">
              O alerta será acionado quando uma licitação contiver qualquer uma dessas palavras
            </p>
          </div>

          {/* Estados */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Estados (deixe vazio para todos)
            </label>
            <div className="flex flex-wrap gap-2">
              {estados.map(uf => (
                <button
                  key={uf}
                  type="button"
                  onClick={() => toggleEstado(uf)}
                  className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
                    formData.estados.includes(uf)
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {uf}
                </button>
              ))}
            </div>
          </div>

          {/* Modalidades */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Modalidades (deixe vazio para todas)
            </label>
            <div className="flex flex-wrap gap-2">
              {modalidades.map(mod => (
                <button
                  key={mod}
                  type="button"
                  onClick={() => toggleModalidade(mod)}
                  className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
                    formData.modalidades.includes(mod)
                      ? 'bg-green-600 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {mod}
                </button>
              ))}
            </div>
          </div>

          {/* Frequência */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Frequência de Verificação
            </label>
            <select
              value={formData.frequencia_horas}
              onChange={(e) => setFormData(prev => ({ ...prev, frequencia_horas: parseInt(e.target.value) }))}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value={1}>A cada 1 hora</option>
              <option value={3}>A cada 3 horas</option>
              <option value={6}>A cada 6 horas</option>
              <option value={12}>A cada 12 horas</option>
              <option value={24}>Uma vez por dia</option>
            </select>
          </div>

          {/* Email de Notificação */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              E-mail para Notificações
            </label>
            <input
              type="email"
              value={formData.email_notificacao}
              onChange={(e) => setFormData(prev => ({ ...prev, email_notificacao: e.target.value }))}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="claudio@gruposmartmedical.com.br"
            />
            <p className="mt-1 text-xs text-gray-500">
              E-mail específico para receber notificações deste alerta. Pode ser diferente do e-mail da conta.
            </p>
          </div>

          {/* Ativo */}
          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              id="ativo"
              checked={formData.ativo}
              onChange={(e) => setFormData(prev => ({ ...prev, ativo: e.target.checked }))}
              className="w-5 h-5 text-blue-600 rounded focus:ring-blue-500"
            />
            <label htmlFor="ativo" className="text-sm font-medium text-gray-700">
              Alerta ativo
            </label>
          </div>

          {/* Botões */}
          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-3 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 font-medium"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <RefreshCw className="w-5 h-5 animate-spin" />
                  Salvando...
                </>
              ) : (
                <>
                  <Check className="w-5 h-5" />
                  {alerta ? 'Atualizar' : 'Criar Alerta'}
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

// ==================== CARD DE ALERTA ====================
const AlertaCard = ({ alerta, onEdit, onDelete, onToggle }) => {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className={`bg-white rounded-lg shadow-md border-l-4 ${
      alerta.ativo ? 'border-green-500' : 'border-gray-300'
    }`}>
      <div className="p-4">
        <div className="flex justify-between items-start">
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-gray-800">{alerta.nome}</h3>
              {alerta.ativo ? (
                <span className="px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded-full">
                  Ativo
                </span>
              ) : (
                <span className="px-2 py-0.5 bg-gray-100 text-gray-500 text-xs rounded-full">
                  Inativo
                </span>
              )}
            </div>
            
            <div className="mt-2 flex flex-wrap gap-1">
              {alerta.palavras_chave?.slice(0, 3).map((p, i) => (
                <span key={i} className="px-2 py-0.5 bg-blue-50 text-blue-600 text-xs rounded">
                  {p}
                </span>
              ))}
              {alerta.palavras_chave?.length > 3 && (
                <span className="px-2 py-0.5 bg-gray-100 text-gray-500 text-xs rounded">
                  +{alerta.palavras_chave.length - 3}
                </span>
              )}
            </div>

            <div className="mt-2 text-xs text-gray-500 flex items-center gap-4">
              <span className="flex items-center gap-1">
                <Clock className="w-3 h-3" />
                A cada {alerta.frequencia_horas}h
              </span>
              {alerta.estados?.length > 0 && (
                <span>Estados: {alerta.estados.join(', ')}</span>
              )}
              <span>{alerta.total_notificacoes || 0} notificações</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => onToggle(alerta)}
              className={`p-2 rounded-lg transition-colors ${
                alerta.ativo 
                  ? 'text-green-600 hover:bg-green-50' 
                  : 'text-gray-400 hover:bg-gray-50'
              }`}
              title={alerta.ativo ? 'Desativar' : 'Ativar'}
            >
              {alerta.ativo ? <CheckCircle className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
            </button>
            <button
              onClick={() => onEdit(alerta)}
              className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg"
              title="Editar"
            >
              <Edit2 className="w-5 h-5" />
            </button>
            <button
              onClick={() => onDelete(alerta)}
              className="p-2 text-red-600 hover:bg-red-50 rounded-lg"
              title="Excluir"
            >
              <Trash2 className="w-5 h-5" />
            </button>
            <button
              onClick={() => setExpanded(!expanded)}
              className="p-2 text-gray-500 hover:bg-gray-50 rounded-lg"
            >
              {expanded ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
            </button>
          </div>
        </div>

        {expanded && (
          <div className="mt-4 pt-4 border-t text-sm text-gray-600">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="font-medium text-gray-700">Palavras-chave:</p>
                <p>{alerta.palavras_chave?.join(', ') || 'Nenhuma'}</p>
              </div>
              <div>
                <p className="font-medium text-gray-700">Estados:</p>
                <p>{alerta.estados?.join(', ') || 'Todos'}</p>
              </div>
              <div>
                <p className="font-medium text-gray-700">Modalidades:</p>
                <p>{alerta.modalidades?.join(', ') || 'Todas'}</p>
              </div>
              <div>
                <p className="font-medium text-gray-700">E-mail para notificações:</p>
                <p className="text-blue-600">{alerta.email_notificacao || 'Padrão da conta'}</p>
              </div>
              <div>
                <p className="font-medium text-gray-700">Última verificação:</p>
                <p>{alerta.ultima_verificacao 
                  ? new Date(alerta.ultima_verificacao).toLocaleString('pt-BR')
                  : 'Nunca'
                }</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

// ==================== CARD DE NOTIFICAÇÃO ====================
const NotificacaoCard = ({ notificacao, onMarcarLida, onArquivar }) => {
  const statusColors = {
    pendente: 'bg-yellow-50 border-yellow-200',
    lida: 'bg-gray-50 border-gray-200',
    arquivada: 'bg-gray-100 border-gray-300'
  };

  return (
    <div className={`p-4 rounded-lg border ${statusColors[notificacao.status] || statusColors.pendente}`}>
      <div className="flex justify-between items-start gap-4">
        <div className="flex-1 min-w-0">
          <h4 className="font-medium text-gray-800 truncate">{notificacao.titulo}</h4>
          <div className="mt-1 text-sm text-gray-600">
            <span className="inline-flex items-center gap-1">
              📍 {notificacao.estado} | 🏛️ {notificacao.orgao?.substring(0, 40)}...
            </span>
          </div>
          <div className="mt-2 flex flex-wrap gap-2 text-xs">
            <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded">
              {notificacao.modalidade}
            </span>
            <span className="px-2 py-0.5 bg-purple-100 text-purple-700 rounded">
              {notificacao.motivo_match}
            </span>
            {notificacao.data_limite && (
              <span className="px-2 py-0.5 bg-red-100 text-red-700 rounded">
                Limite: {new Date(notificacao.data_limite).toLocaleDateString('pt-BR')}
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {notificacao.status === 'pendente' && (
            <button
              onClick={() => onMarcarLida(notificacao.id)}
              className="p-2 text-green-600 hover:bg-green-50 rounded-lg"
              title="Marcar como lida"
            >
              <Check className="w-5 h-5" />
            </button>
          )}
          {notificacao.link_origem && (
            <a
              href={notificacao.link_origem}
              target="_blank"
              rel="noopener noreferrer"
              className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg"
              title="Ver licitação"
            >
              🔗
            </a>
          )}
          <button
            onClick={() => onArquivar(notificacao.id)}
            className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg"
            title="Arquivar"
          >
            <Archive className="w-5 h-5" />
          </button>
        </div>
      </div>
      <div className="mt-2 text-xs text-gray-400">
        {new Date(notificacao.criado_em).toLocaleString('pt-BR')}
      </div>
    </div>
  );
};

// ==================== PÁGINA PRINCIPAL ====================
const NotificacoesPage = () => {
  const [alertas, setAlertas] = useState([]);
  const [notificacoes, setNotificacoes] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [verificando, setVerificando] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [alertaEdit, setAlertaEdit] = useState(null);
  const [filtroStatus, setFiltroStatus] = useState('pendente');
  const [activeTab, setActiveTab] = useState('alertas');

  const fetchData = useCallback(async () => {
    try {
      const [alertasRes, notificacoesRes, statsRes] = await Promise.all([
        axios.get(`${API}/alertas`),
        axios.get(`${API}/notificacoes?status=${filtroStatus}&por_pagina=50`),
        axios.get(`${API}/notificacoes/stats`)
      ]);

      setAlertas(alertasRes.data.alertas || []);
      setNotificacoes(notificacoesRes.data.notificacoes || []);
      setStats(statsRes.data);
    } catch (error) {
      console.error('Erro ao carregar dados:', error);
    } finally {
      setLoading(false);
    }
  }, [filtroStatus]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleVerificar = async () => {
    setVerificando(true);
    try {
      await axios.post(`${API}/notificacoes/verificar?forcar=true`);
      await fetchData();
    } catch (error) {
      console.error('Erro ao verificar:', error);
    } finally {
      setVerificando(false);
    }
  };

  const handleDeleteAlerta = async (alerta) => {
    if (!window.confirm(`Deseja excluir o alerta "${alerta.nome}"?`)) return;
    
    try {
      await axios.delete(`${API}/alertas/${alerta.id}`);
      await fetchData();
    } catch (error) {
      console.error('Erro ao excluir:', error);
    }
  };

  const handleToggleAlerta = async (alerta) => {
    try {
      await axios.put(`${API}/alertas/${alerta.id}`, { ativo: !alerta.ativo });
      await fetchData();
    } catch (error) {
      console.error('Erro ao atualizar:', error);
    }
  };

  const handleMarcarLida = async (id) => {
    try {
      await axios.post(`${API}/notificacoes/${id}/lida`);
      await fetchData();
    } catch (error) {
      console.error('Erro ao marcar como lida:', error);
    }
  };

  const handleArquivar = async (id) => {
    try {
      await axios.post(`${API}/notificacoes/${id}/arquivar`);
      await fetchData();
    } catch (error) {
      console.error('Erro ao arquivar:', error);
    }
  };

  const handleMarcarTodasLidas = async () => {
    try {
      await axios.post(`${API}/notificacoes/marcar-todas-lidas`);
      await fetchData();
    } catch (error) {
      console.error('Erro ao marcar todas como lidas:', error);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-800 flex items-center gap-2">
            <Bell className="w-7 h-7 text-blue-600" />
            Sistema de Notificações
          </h1>
          <p className="text-gray-600 mt-1">
            Gerencie alertas e receba notificações de novas licitações
          </p>
        </div>

        <div className="flex gap-3">
          <button
            onClick={handleVerificar}
            disabled={verificando}
            className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 font-medium flex items-center gap-2 disabled:opacity-50"
          >
            <RefreshCw className={`w-5 h-5 ${verificando ? 'animate-spin' : ''}`} />
            {verificando ? 'Verificando...' : 'Verificar Agora'}
          </button>
          <button
            onClick={() => { setAlertaEdit(null); setModalOpen(true); }}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium flex items-center gap-2"
          >
            <Plus className="w-5 h-5" />
            Novo Alerta
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-white rounded-lg shadow p-4">
            <p className="text-sm text-gray-500">Pendentes</p>
            <p className="text-2xl font-bold text-yellow-600">{stats.total_pendentes}</p>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <p className="text-sm text-gray-500">Lidas</p>
            <p className="text-2xl font-bold text-green-600">{stats.total_lidas}</p>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <p className="text-sm text-gray-500">Arquivadas</p>
            <p className="text-2xl font-bold text-gray-600">{stats.total_arquivadas}</p>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <p className="text-sm text-gray-500">Alertas Ativos</p>
            <p className="text-2xl font-bold text-blue-600">{stats.total_alertas_ativos}</p>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b mb-6">
        <button
          onClick={() => setActiveTab('alertas')}
          className={`px-6 py-3 font-medium border-b-2 transition-colors ${
            activeTab === 'alertas'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          🔔 Meus Alertas ({alertas.length})
        </button>
        <button
          onClick={() => setActiveTab('notificacoes')}
          className={`px-6 py-3 font-medium border-b-2 transition-colors ${
            activeTab === 'notificacoes'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          📬 Notificações
          {stats?.total_pendentes > 0 && (
            <span className="ml-2 px-2 py-0.5 bg-yellow-100 text-yellow-700 text-xs rounded-full">
              {stats.total_pendentes}
            </span>
          )}
        </button>
      </div>

      {/* Content */}
      {activeTab === 'alertas' ? (
        <div className="space-y-4">
          {alertas.length === 0 ? (
            <div className="text-center py-12 bg-gray-50 rounded-lg">
              <Bell className="w-12 h-12 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-500 mb-4">Nenhum alerta configurado</p>
              <button
                onClick={() => { setAlertaEdit(null); setModalOpen(true); }}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                Criar Primeiro Alerta
              </button>
            </div>
          ) : (
            alertas.map(alerta => (
              <AlertaCard
                key={alerta.id}
                alerta={alerta}
                onEdit={(a) => { setAlertaEdit(a); setModalOpen(true); }}
                onDelete={handleDeleteAlerta}
                onToggle={handleToggleAlerta}
              />
            ))
          )}
        </div>
      ) : (
        <div>
          {/* Filtros de Notificações */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Filter className="w-5 h-5 text-gray-500" />
              <select
                value={filtroStatus}
                onChange={(e) => setFiltroStatus(e.target.value)}
                className="px-3 py-2 border rounded-lg text-sm"
              >
                <option value="pendente">Pendentes</option>
                <option value="lida">Lidas</option>
                <option value="arquivada">Arquivadas</option>
              </select>
            </div>
            
            {filtroStatus === 'pendente' && notificacoes.length > 0 && (
              <button
                onClick={handleMarcarTodasLidas}
                className="text-sm text-blue-600 hover:underline"
              >
                Marcar todas como lidas
              </button>
            )}
          </div>

          {/* Lista de Notificações */}
          <div className="space-y-3">
            {notificacoes.length === 0 ? (
              <div className="text-center py-12 bg-gray-50 rounded-lg">
                <CheckCircle className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                <p className="text-gray-500">Nenhuma notificação {filtroStatus}</p>
              </div>
            ) : (
              notificacoes.map(notificacao => (
                <NotificacaoCard
                  key={notificacao.id}
                  notificacao={notificacao}
                  onMarcarLida={handleMarcarLida}
                  onArquivar={handleArquivar}
                />
              ))
            )}
          </div>
        </div>
      )}

      {/* Modal */}
      <AlertaModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        alerta={alertaEdit}
        onSave={fetchData}
      />
    </div>
  );
};

export default NotificacoesPage;
