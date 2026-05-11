import React, { useState, useEffect } from 'react';
import { Activity, CheckCircle, XCircle, AlertCircle, Clock, TrendingUp, Play } from 'lucide-react';

const HealthDashboard = () => {
  const [systemHealth, setSystemHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [testingSource, setTestingSource] = useState(null);
  const [testResult, setTestResult] = useState(null);

  const fetchHealth = async () => {
    try {
      const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/status/scrapers`);
      const data = await response.json();
      setSystemHealth(data);
      setLoading(false);
    } catch (error) {
      console.error('Erro ao buscar status:', error);
      setLoading(false);
    }
  };

  const handleTestScraper = async (fonte) => {
    setTestingSource(fonte);
    setTestResult(null);
    try {
      const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/status/scrapers/${encodeURIComponent(fonte)}/test`, {
        method: 'POST'
      });
      const data = await response.json();
      setTestResult({ fonte, ...data });
      // Atualizar a saúde após o teste
      fetchHealth();
    } catch (error) {
      console.error('Erro ao testar scraper:', error);
      setTestResult({ fonte, status: 'error', detail: error.message });
    } finally {
      setTestingSource(null);
    }
  };

  useEffect(() => {
    fetchHealth();

    // Auto-refresh a cada 60 segundos se ativado
    if (autoRefresh) {
      const interval = setInterval(fetchHealth, 60000);
      return () => clearInterval(interval);
    }
  }, [autoRefresh]);

  const getStatusColor = (status) => {
    switch (status) {
      case 'UP':
      case 'HEALTHY':
        return 'text-green-600 bg-green-100';
      case 'DEGRADED':
        return 'text-yellow-600 bg-yellow-100';
      case 'DOWN':
        return 'text-red-600 bg-red-100';
      default:
        return 'text-gray-600 bg-gray-100';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'UP':
      case 'HEALTHY':
        return <CheckCircle className="w-5 h-5" />;
      case 'DEGRADED':
        return <AlertCircle className="w-5 h-5" />;
      case 'DOWN':
        return <XCircle className="w-5 h-5" />;
      default:
        return <Activity className="w-5 h-5" />;
    }
  };

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return 'N/A';
    const date = new Date(timestamp);
    return date.toLocaleString('pt-BR');
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Activity className="w-12 h-12 text-blue-600 animate-spin mx-auto mb-4" />
          <p className="text-gray-600">Carregando status do sistema...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
                <Activity className="w-8 h-8 text-blue-600" />
                Dashboard de Saúde do Sistema
              </h1>
              <p className="text-gray-600 mt-1">Monitoramento em tempo real dos scrapers</p>
            </div>
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 text-sm text-gray-600">
                <input
                  type="checkbox"
                  checked={autoRefresh}
                  onChange={(e) => setAutoRefresh(e.target.checked)}
                  className="rounded"
                />
                Auto-refresh (60s)
              </label>
              <button
                onClick={fetchHealth}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition text-sm"
              >
                Atualizar Agora
              </button>
            </div>
          </div>

          {/* Status Geral */}
          <div className="bg-white rounded-lg shadow p-6 border-l-4 border-blue-600">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Status Geral do Sistema</p>
                <div className="flex items-center gap-2 mt-2">
                  <span className={`px-4 py-2 rounded-full font-semibold flex items-center gap-2 ${getStatusColor(systemHealth?.status_geral)}`}>
                    {getStatusIcon(systemHealth?.status_geral)}
                    {systemHealth?.status_geral || 'UNKNOWN'}
                  </span>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-6 text-center">
                <div>
                  <p className="text-3xl font-bold text-green-600">{systemHealth?.fontes_up || 0}</p>
                  <p className="text-sm text-gray-600">UP</p>
                </div>
                <div>
                  <p className="text-3xl font-bold text-yellow-600">{systemHealth?.fontes_degraded || 0}</p>
                  <p className="text-sm text-gray-600">DEGRADED</p>
                </div>
                <div>
                  <p className="text-3xl font-bold text-red-600">{systemHealth?.fontes_down || 0}</p>
                  <p className="text-sm text-gray-600">DOWN</p>
                </div>
              </div>
            </div>
            <p className="text-xs text-gray-500 mt-4">
              Última atualização: {formatTimestamp(systemHealth?.timestamp)}
            </p>
          </div>
        </div>

        {/* Cards dos Scrapers */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {systemHealth?.scrapers?.map((scraper) => (
            <div key={scraper.fonte} className="bg-white rounded-lg shadow-md overflow-hidden">
              {/* Header do Card */}
              <div className={`p-4 ${getStatusColor(scraper.status)}`}>
                <div className="flex items-center justify-between">
                  <h3 className="font-bold text-lg">{scraper.fonte}</h3>
                  {getStatusIcon(scraper.status)}
                </div>
                <p className="text-sm mt-1">{scraper.status}</p>
              </div>

              {/* Conteúdo do Card */}
              <div className="p-4 space-y-3">
                {/* Execuções 24h */}
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-600">Execuções 24h:</span>
                  <span className="font-semibold">{scraper.total_execucoes_24h}</span>
                </div>

                {/* Taxa de Sucesso */}
                <div>
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-sm text-gray-600">Taxa de Sucesso:</span>
                    <span className="font-semibold">{scraper.taxa_sucesso_24h}%</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full transition-all ${
                        scraper.taxa_sucesso_24h >= 90 ? 'bg-green-600' :
                        scraper.taxa_sucesso_24h >= 70 ? 'bg-yellow-600' :
                        'bg-red-600'
                      }`}
                      style={{ width: `${scraper.taxa_sucesso_24h}%` }}
                    ></div>
                  </div>
                </div>

                {/* Sucessos e Erros */}
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div className="bg-green-50 p-2 rounded">
                    <p className="text-gray-600 text-xs">Sucessos</p>
                    <p className="font-semibold text-green-700">{scraper.total_sucessos_24h}</p>
                  </div>
                  <div className="bg-red-50 p-2 rounded">
                    <p className="text-gray-600 text-xs">Erros</p>
                    <p className="font-semibold text-red-700">{scraper.total_erros_24h}</p>
                  </div>
                </div>

                {/* Resultados Totais */}
                <div className="flex items-center gap-2 text-sm pt-2 border-t">
                  <TrendingUp className="w-4 h-4 text-blue-600" />
                  <span className="text-gray-600">Resultados:</span>
                  <span className="font-semibold text-blue-600">{scraper.total_resultados_24h}</span>
                </div>

                {/* Tempo Médio */}
                {scraper.tempo_medio_execucao_ms && (
                  <div className="flex items-center gap-2 text-sm">
                    <Clock className="w-4 h-4 text-gray-500" />
                    <span className="text-gray-600">Tempo médio:</span>
                    <span className="font-semibold">{scraper.tempo_medio_execucao_ms}ms</span>
                  </div>
                )}

                {/* Última Execução Sucesso */}
                {scraper.ultima_execucao_sucesso && (
                  <div className="text-xs text-gray-500 pt-2 border-t">
                    <p>Último sucesso:</p>
                    <p className="font-mono">{formatTimestamp(scraper.ultima_execucao_sucesso)}</p>
                  </div>
                )}

                {/* Última Mensagem de Erro */}
                {scraper.ultima_mensagem_erro && (
                  <div className="bg-red-50 p-2 rounded text-xs mt-2 border border-red-100">
                    <p className="text-red-700 font-semibold flex items-center gap-1">
                      <AlertCircle className="w-3 h-3" />
                      Último erro:
                    </p>
                    <p className="text-red-600 mt-1 line-clamp-2" title={scraper.ultima_mensagem_erro}>
                      {scraper.ultima_mensagem_erro}
                    </p>
                  </div>
                )}

                {/* Botões de Ação */}
                <div className="pt-3 border-t mt-3">
                  <button
                    onClick={() => handleTestScraper(scraper.fonte)}
                    disabled={testingSource === scraper.fonte}
                    className={`w-full py-2 px-4 rounded font-medium text-sm flex items-center justify-center gap-2 transition-all ${
                      testingSource === scraper.fonte
                        ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                        : 'bg-blue-50 text-blue-600 hover:bg-blue-100'
                    }`}
                  >
                    {testingSource === scraper.fonte ? (
                      <>
                        <Activity className="w-4 h-4 animate-spin" />
                        Testando...
                      </>
                    ) : (
                      <>
                        <Play className="w-4 h-4" />
                        Testar Scraper
                      </>
                    )}
                  </button>
                </div>

                {/* Resultado do Teste Local */}
                {testResult?.fonte === scraper.fonte && (
                  <div className={`mt-2 p-2 rounded text-xs border ${
                    testResult.status === 'success' ? 'bg-green-50 border-green-100 text-green-700' : 'bg-red-50 border-red-100 text-red-700'
                  }`}>
                    <div className="flex justify-between items-start">
                      <p className="font-bold">
                        {testResult.status === 'success' ? '✅ Teste OK' : '❌ Falha no Teste'}
                      </p>
                      <button onClick={() => setTestResult(null)} className="text-gray-400 hover:text-gray-600">×</button>
                    </div>
                    {testResult.status === 'success' ? (
                      <p className="mt-1">
                        Encontrados {testResult.resultados_count} itens em {testResult.tempo_ms}ms
                      </p>
                    ) : (
                      <p className="mt-1 line-clamp-2">{testResult.detail}</p>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Rodapé */}
        <div className="mt-8 text-center text-sm text-gray-500">
          <p>Dashboard de monitoramento GSM - Buscador de Editais</p>
          <p>Métricas baseadas nas últimas 24 horas</p>
        </div>
      </div>
    </div>
  );
};

export default HealthDashboard;
