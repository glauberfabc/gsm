import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { 
  Activity, 
  Server, 
  Database, 
  Bell, 
  RefreshCw, 
  CheckCircle, 
  XCircle, 
  AlertTriangle,
  Clock,
  TrendingUp,
  Zap,
  Shield
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Componente para status badge
const StatusBadge = ({ status }) => {
  const configs = {
    'OK': { bg: 'bg-green-100', text: 'text-green-800', icon: CheckCircle },
    'ERRO': { bg: 'bg-red-100', text: 'text-red-800', icon: XCircle },
    'ATRASO': { bg: 'bg-yellow-100', text: 'text-yellow-800', icon: AlertTriangle },
    'INATIVO': { bg: 'bg-gray-100', text: 'text-gray-600', icon: Clock },
    'DESCONHECIDO': { bg: 'bg-gray-100', text: 'text-gray-500', icon: Clock },
  };
  
  const config = configs[status] || configs['DESCONHECIDO'];
  const Icon = config.icon;
  
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${config.bg} ${config.text}`}>
      <Icon className="w-3 h-3" />
      {status}
    </span>
  );
};

// Card de métrica simples
const MetricCard = ({ title, value, subtitle, icon: Icon, color = 'blue' }) => {
  const colorClasses = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    yellow: 'bg-yellow-50 text-yellow-600',
    purple: 'bg-purple-50 text-purple-600',
    red: 'bg-red-50 text-red-600',
  };
  
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
      <div className="flex items-center gap-3">
        <div className={`p-2 rounded-lg ${colorClasses[color]}`}>
          <Icon className="w-5 h-5" />
        </div>
        <div>
          <p className="text-xs text-gray-500 uppercase tracking-wide">{title}</p>
          <p className="text-2xl font-bold text-gray-900">{value}</p>
          {subtitle && <p className="text-xs text-gray-400">{subtitle}</p>}
        </div>
      </div>
    </div>
  );
};

// Score de saúde geral
const HealthScore = ({ score, status, emoji, detalhes }) => {
  const getColor = (score) => {
    if (score >= 80) return 'text-green-500';
    if (score >= 50) return 'text-yellow-500';
    return 'text-red-500';
  };
  
  const getBgColor = (score) => {
    if (score >= 80) return 'bg-green-50 border-green-200';
    if (score >= 50) return 'bg-yellow-50 border-yellow-200';
    return 'bg-red-50 border-red-200';
  };
  
  return (
    <div className={`rounded-xl border-2 p-6 ${getBgColor(score)}`}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <span className="text-4xl">{emoji}</span>
          <div>
            <h3 className="text-lg font-bold text-gray-800">Saúde do Sistema</h3>
            <p className="text-sm text-gray-600">{status}</p>
          </div>
        </div>
        <div className={`text-5xl font-bold ${getColor(score)}`}>
          {score}
          <span className="text-lg text-gray-400">/100</span>
        </div>
      </div>
      
      {detalhes && detalhes.length > 0 && (
        <div className="mt-4 space-y-1">
          {detalhes.map((detalhe, i) => (
            <p key={i} className="text-sm text-gray-600 flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-green-500" />
              {detalhe}
            </p>
          ))}
        </div>
      )}
    </div>
  );
};

// Seção de Workers
const WorkersSection = ({ workers }) => {
  if (!workers || !workers.workers) return null;
  
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-800 flex items-center gap-2">
          <Server className="w-5 h-5 text-blue-500" />
          Workers
        </h3>
        <div className="flex items-center gap-2 text-sm">
          <span className="text-green-600">{workers.resumo.ok} OK</span>
          <span className="text-gray-300">|</span>
          <span className="text-red-600">{workers.resumo.erro} Erro</span>
          <span className="text-gray-300">|</span>
          <span className="text-yellow-600">{workers.resumo.atraso} Atraso</span>
        </div>
      </div>
      
      <div className="space-y-3">
        {Object.entries(workers.workers).map(([key, worker]) => (
          <div key={key} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
            <div>
              <p className="font-medium text-gray-800">{worker.nome}</p>
              <p className="text-xs text-gray-500">{worker.mensagem}</p>
            </div>
            <StatusBadge status={worker.status} />
          </div>
        ))}
      </div>
    </div>
  );
};

// Seção de Fontes
const FontesSection = ({ fontes }) => {
  if (!fontes || !fontes.fontes) return null;
  
  // Ordenar por total de resultados
  const fontesOrdenadas = Object.entries(fontes.fontes)
    .sort((a, b) => (b[1].total_resultados || 0) - (a[1].total_resultados || 0));
  
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-800 flex items-center gap-2">
          <Database className="w-5 h-5 text-purple-500" />
          Fontes de Dados
        </h3>
        <span className="text-sm text-gray-500">{fontes.resumo.total} fontes</span>
      </div>
      
      <div className="space-y-2 max-h-64 overflow-y-auto">
        {fontesOrdenadas.slice(0, 10).map(([key, fonte]) => (
          <div key={key} className="flex items-center justify-between py-2 px-3 bg-gray-50 rounded-lg">
            <div className="flex items-center gap-2">
              <StatusBadge status={fonte.status} />
              <span className="font-medium text-gray-700">{fonte.fonte}</span>
            </div>
            <div className="text-right">
              <p className="text-sm font-medium text-gray-800">{fonte.total_resultados || 0} editais</p>
              <p className="text-xs text-gray-400">
                {fonte.taxa_sucesso !== undefined ? `${fonte.taxa_sucesso}% sucesso` : 'N/A'}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

// Seção de Pipeline
const PipelineSection = ({ pipeline }) => {
  if (!pipeline) return null;
  
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
      <h3 className="font-semibold text-gray-800 flex items-center gap-2 mb-4">
        <TrendingUp className="w-5 h-5 text-green-500" />
        Pipeline de Dados
      </h3>
      
      {/* Flow visual */}
      <div className="flex items-center justify-between mb-4">
        <div className="text-center">
          <p className="text-2xl font-bold text-gray-800">{pipeline.editais_raw}</p>
          <p className="text-xs text-gray-500">Raw</p>
        </div>
        <div className="flex-1 mx-2">
          <div className="h-1 bg-green-200 rounded relative">
            <div 
              className="h-1 bg-green-500 rounded" 
              style={{ width: `${pipeline.taxa_normalizacao}%` }}
            />
          </div>
          <p className="text-xs text-center text-gray-400 mt-1">{pipeline.taxa_normalizacao}%</p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-bold text-green-600">{pipeline.editais_normalizados}</p>
          <p className="text-xs text-gray-500">Normalizados</p>
        </div>
        <div className="flex-1 mx-2">
          <div className="h-1 bg-blue-200 rounded" />
        </div>
        <div className="text-center">
          <p className="text-2xl font-bold text-blue-600">{pipeline.matches?.total || 0}</p>
          <p className="text-xs text-gray-500">Matches</p>
        </div>
      </div>
      
      {/* Stats adicionais */}
      <div className="grid grid-cols-3 gap-2 mt-4 pt-4 border-t border-gray-100">
        <div className="text-center">
          <p className="text-lg font-semibold text-purple-600">{pipeline.saude?.total || 0}</p>
          <p className="text-xs text-gray-500">Saúde ({pipeline.saude?.percentual || 0}%)</p>
        </div>
        <div className="text-center">
          <p className="text-lg font-semibold text-amber-600">{pipeline.matches?.pendentes || 0}</p>
          <p className="text-xs text-gray-500">Pendentes</p>
        </div>
        <div className="text-center">
          <p className="text-lg font-semibold text-green-600">{pipeline.novos_24h || 0}</p>
          <p className="text-xs text-gray-500">Novos (24h)</p>
        </div>
      </div>
    </div>
  );
};

// Seção de Alertas
const AlertasSection = ({ alertas }) => {
  if (!alertas) return null;
  
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
      <h3 className="font-semibold text-gray-800 flex items-center gap-2 mb-4">
        <Bell className="w-5 h-5 text-yellow-500" />
        Sistema de Alertas
      </h3>
      
      <div className="grid grid-cols-2 gap-4">
        {/* Alertas */}
        <div className="bg-gray-50 rounded-lg p-3">
          <p className="text-xs text-gray-500 uppercase mb-2">Alertas</p>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xl font-bold text-gray-800">{alertas.alertas?.ativos || 0}</p>
              <p className="text-xs text-green-600">Ativos</p>
            </div>
            <div className="text-right">
              <p className="text-xl font-bold text-gray-400">{alertas.alertas?.inativos || 0}</p>
              <p className="text-xs text-gray-500">Inativos</p>
            </div>
          </div>
        </div>
        
        {/* Matches */}
        <div className="bg-gray-50 rounded-lg p-3">
          <p className="text-xs text-gray-500 uppercase mb-2">Matches</p>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xl font-bold text-green-600">{alertas.matches?.disparados || 0}</p>
              <p className="text-xs text-green-600">Disparados</p>
            </div>
            <div className="text-right">
              <p className="text-xl font-bold text-red-400">{alertas.matches?.suprimidos || 0}</p>
              <p className="text-xs text-gray-500">Suprimidos</p>
            </div>
          </div>
        </div>
      </div>
      
      {/* Score médio */}
      <div className="mt-4 pt-4 border-t border-gray-100 flex items-center justify-between">
        <span className="text-sm text-gray-600">Score médio dos matches</span>
        <span className="font-bold text-blue-600">{alertas.matches?.score_medio || 0} pts</span>
      </div>
      
      {/* Notificações */}
      <div className="mt-2 flex items-center justify-between">
        <span className="text-sm text-gray-600">Notificações não lidas</span>
        <span className="font-bold text-amber-600">{alertas.notificacoes?.nao_lidas || 0}</span>
      </div>
    </div>
  );
};

// Componente principal
const MonitoringDashboard = () => {
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  
  const fetchDashboard = useCallback(async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/monitoring/dashboard`);
      setDashboard(response.data);
      setLastUpdate(new Date());
      setError(null);
    } catch (err) {
      setError('Erro ao carregar dashboard');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);
  
  useEffect(() => {
    fetchDashboard();
    
    // Auto-refresh a cada 60 segundos
    const interval = setInterval(fetchDashboard, 60000);
    return () => clearInterval(interval);
  }, [fetchDashboard]);
  
  return (
    <div className="min-h-screen bg-gray-50 p-4 md:p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              <Activity className="w-7 h-7 text-blue-600" />
              Dashboard de Monitoramento
            </h1>
            <p className="text-gray-500 text-sm">
              Visão operacional do sistema GSM Buscador de Editais
            </p>
          </div>
          
          <div className="flex items-center gap-4 mt-4 md:mt-0">
            {lastUpdate && (
              <span className="text-xs text-gray-400">
                Atualizado: {lastUpdate.toLocaleTimeString()}
              </span>
            )}
            <button
              onClick={fetchDashboard}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              Atualizar
            </button>
          </div>
        </div>
        
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6">
            {error}
          </div>
        )}
        
        {dashboard && (
          <>
            {/* Saúde Geral */}
            <div className="mb-6">
              <HealthScore 
                score={dashboard.saude_geral?.score || 0}
                status={dashboard.saude_geral?.status || 'Carregando...'}
                emoji={dashboard.saude_geral?.emoji || '⏳'}
                detalhes={dashboard.saude_geral?.detalhes || []}
              />
            </div>
            
            {/* Métricas principais */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <MetricCard 
                title="Editais" 
                value={dashboard.pipeline?.editais_normalizados || 0}
                subtitle="Normalizados"
                icon={Database}
                color="blue"
              />
              <MetricCard 
                title="Matches" 
                value={dashboard.alertas?.matches?.disparados || 0}
                subtitle={`Score médio: ${dashboard.alertas?.matches?.score_medio || 0}`}
                icon={Zap}
                color="green"
              />
              <MetricCard 
                title="Alertas Ativos" 
                value={dashboard.alertas?.alertas?.ativos || 0}
                subtitle={`${dashboard.alertas?.alertas?.total || 0} total`}
                icon={Bell}
                color="yellow"
              />
              <MetricCard 
                title="Fontes" 
                value={dashboard.fontes?.resumo?.total || 0}
                subtitle={`${dashboard.fontes?.resumo?.ok || 0} OK`}
                icon={Server}
                color="purple"
              />
            </div>
            
            {/* Grid de seções */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <WorkersSection workers={dashboard.workers} />
              <FontesSection fontes={dashboard.fontes} />
              <PipelineSection pipeline={dashboard.pipeline} />
              <AlertasSection alertas={dashboard.alertas} />
            </div>
            
            {/* Footer com tempo de coleta */}
            <div className="mt-6 text-center text-xs text-gray-400">
              Tempo de coleta: {dashboard.tempo_coleta_ms?.toFixed(2)}ms
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default MonitoringDashboard;
