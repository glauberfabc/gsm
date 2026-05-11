import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Tag, TrendingUp, Calendar, Zap, ClipboardList, Filter, LayoutDashboard, BarChart3, Clock, RefreshCw, Activity } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts';

// --- CONFIGURAÇÃO DE CORES E CATEGORIAS ---
const COLORS = ['#8884d8', '#82ca9d', '#ffc658', '#ff8042', '#a4de6c', '#d0ed57', '#00c49f', '#0088fe', '#ffbb28', '#f94144', '#f3722c', '#f8961e'];

const healthCategories = [
  { key: 'hospitalar', label: '🏥 Hospitalar', fullLabel: '🏥 Hospitalar', color: '#5b21b6' },
  { key: 'medicamentos', label: '💊 Medicamentos', fullLabel: '💊 Medicamentos', color: '#10b981' },
  { key: 'equipamentos', label: '🩺 Equipamentos', fullLabel: '🩺 Equipamentos Médicos', color: '#3b82f6' },
  { key: 'laboratorio', label: '🧪 Laboratório', fullLabel: '🧪 Laboratório', color: '#ef4444' },
  { key: 'insumos', label: '💉 Insumos', fullLabel: '💉 Insumos Médicos', color: '#f59e0b' },
  { key: 'odontologia', label: '🦷 Odontologia', fullLabel: '🦷 Odontologia', color: '#14b8a6' },
  { key: 'oftalmologia', label: '👁️ Oftalmologia', fullLabel: '👁️ Oftalmologia', color: '#9333ea' },
  { key: 'oncologia', label: '🩻 Oncologia', fullLabel: '🩻 Oncologia', color: '#db2777' },
  { key: 'cardiologia', label: '🫀 Cardiologia', fullLabel: '🫀 Cardiologia', color: '#eab308' },
  { key: 'especialidades', label: '🧬 Especialidades', fullLabel: '🧬 Especialidades', color: '#7e22ce' },
  { key: 'servicos', label: '👨‍⚕️ Serviços', fullLabel: '👨‍⚕️ Serviços de Saúde', color: '#0d9488' },
  { key: 'saude_geral', label: '🩹 Saúde Geral', fullLabel: '🩹 Saúde Geral', color: '#4c1d95' },
];

// Componente auxiliar para as métricas do topo
const MetricCard = ({ title, value, badgeColor, icon: Icon = Tag, trend, loading }) => (
  <div className="p-5 bg-white rounded-xl shadow-md border-t-4 border-b-2 border-gray-100 hover:border-indigo-400 transition-all duration-300 flex justify-between items-center">
    <div>
      <p className="text-sm font-medium text-gray-500">{title}</p>
      {loading ? (
        <div className="animate-pulse bg-gray-200 h-8 w-20 rounded mt-1"></div>
      ) : (
        <p className="text-3xl font-extrabold text-gray-900 mt-1">{value}</p>
      )}
      {trend && (
        <p className={`text-xs mt-1 ${trend > 0 ? 'text-green-600' : 'text-gray-500'}`}>
          {trend > 0 ? '↑' : '→'} {Math.abs(trend)}% vs ontem
        </p>
      )}
    </div>
    <div className={`p-3 rounded-full bg-opacity-10`} style={{ backgroundColor: `${badgeColor}20`, borderColor: badgeColor, borderWidth: '2px' }}>
      <Icon className="w-6 h-6" style={{ color: badgeColor }} />
    </div>
  </div>
);

// --- Componente de Gráficos (Dashboard) ---
const AnalyticsDashboard = ({ licitacoes, categories, loading }) => {

  // 1. Dados para o Gráfico de Distribuição por Categoria
  const categoryData = useMemo(() => {
    const counts = {};
    licitacoes.forEach(licitacao => {
      const tags = licitacao.tags_saude || [];
      tags.forEach(tag => {
        const category = categories.find(c => tag.includes(c.label.split(' ')[1]) || tag.includes(c.fullLabel));
        if (category) {
          counts[category.key] = (counts[category.key] || 0) + 1;
        }
      });
    });
    return categories
      .map(cat => ({
        name: cat.label.split(' ').slice(1).join(' '),
        fullName: cat.fullLabel,
        count: counts[cat.key] || 0,
        color: cat.color,
      }))
      .filter(item => item.count > 0)
      .sort((a, b) => b.count - a.count);
  }, [licitacoes, categories]);

  // 2. Dados para o Gráfico de Distribuição de Score (Agrupado)
  const scoreBins = [
    { name: 'Baixa (0-50)', min: 0, max: 50, color: '#9ca3af' },
    { name: 'Média (51-75)', min: 51, max: 75, color: '#fcd34d' },
    { name: 'Alta (76-90)', min: 76, max: 90, color: '#34d399' },
    { name: 'Crítica (91+)', min: 91, max: 500, color: '#ef4444' },
  ];

  const scoreData = useMemo(() => {
    const counts = scoreBins.map(bin => ({ ...bin, count: 0 }));
    
    licitacoes.forEach(licitacao => {
      const score = licitacao.score_relevancia || 0;
      scoreBins.forEach((bin, index) => {
        if (score >= bin.min && score <= bin.max) {
          counts[index].count++;
        }
      });
    });

    return counts;
  }, [licitacoes]);

  // 3. Dados para o Gráfico de Status (Urgente vs Não Urgente)
  const urgencyData = useMemo(() => {
    const urgentCount = licitacoes.filter(l => l.is_urgente).length;
    const saudeCount = licitacoes.filter(l => l.is_saude && !l.is_urgente).length;
    const outrosCount = licitacoes.filter(l => !l.is_saude && !l.is_urgente).length;

    return [
      { name: '🚨 Urgente', value: urgentCount, color: '#dc2626' },
      { name: '🏥 Saúde', value: saudeCount, color: '#10b981' },
      { name: '📋 Outros', value: outrosCount, color: '#6366f1' }
    ].filter(item => item.value > 0);
  }, [licitacoes]);

  // 4. Dados para Gráfico de Iminência
  const iminenciaData = useMemo(() => {
    const bins = [
      { name: 'HOJE', min: 0, max: 0, color: '#dc2626' },
      { name: '1-3 dias', min: 1, max: 3, color: '#f97316' },
      { name: '4-7 dias', min: 4, max: 7, color: '#eab308' },
      { name: '8-30 dias', min: 8, max: 30, color: '#22c55e' },
      { name: '30+ dias', min: 31, max: 9999, color: '#3b82f6' },
    ];

    return bins.map(bin => {
      const count = licitacoes.filter(l => {
        const imin = l.iminencia;
        if (imin === null || imin === undefined) return false;
        return imin >= bin.min && imin <= bin.max;
      }).length;
      return { ...bin, count };
    }).filter(item => item.count > 0);
  }, [licitacoes]);

  // Formatador para os Tooltips
  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="p-3 bg-white border border-gray-300 rounded-lg shadow-lg text-sm text-gray-800">
          <p className="font-semibold">{label || payload[0]?.name}</p>
          <p className="text-indigo-600 font-bold">{`${payload[0].value} licitações`}</p>
        </div>
      );
    }
    return null;
  };
  
  // Componente customizado para o rótulo do Pie Chart
  const RADIAN = Math.PI / 180;
  const renderCustomizedLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent, name }) => {
    const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
    const x = cx + radius * Math.cos(-midAngle * RADIAN);
    const y = cy + radius * Math.sin(-midAngle * RADIAN);
    
    if (percent * 100 < 5) return null;

    return (
      <text x={x} y={y} fill="white" textAnchor={x > cx ? 'start' : 'end'} dominantBaseline="central" className="font-bold text-xs">
        {`${(percent * 100).toFixed(0)}%`}
      </text>
    );
  };

  if (loading) {
    return (
      <div className="space-y-8 animate-pulse">
        <div className="h-8 bg-gray-200 rounded w-1/3"></div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="bg-gray-200 rounded-xl h-80"></div>
          <div className="bg-gray-200 rounded-xl h-80 lg:col-span-2"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <h2 className="text-2xl font-semibold text-gray-800 mb-6 border-b pb-2 flex items-center">
        <BarChart3 className="w-6 h-6 mr-2 text-indigo-600"/>
        Métricas de Distribuição - Inteligência de Negócios
      </h2>
      
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Gráfico 1: Urgência e Tipo */}
        <div className="bg-white p-6 rounded-xl shadow-lg">
          <h3 className="text-lg font-semibold text-gray-700 mb-4 flex items-center">
            <Zap className="w-5 h-5 mr-2 text-red-500" />
            Classificação Geral
          </h3>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie
                data={urgencyData}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={80}
                fill="#8884d8"
                paddingAngle={3}
                dataKey="value"
                labelLine={false}
                label={renderCustomizedLabel}
              >
                {urgencyData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
              <Legend 
                verticalAlign="bottom" 
                height={36}
                formatter={(value, entry) => <span className="text-sm text-gray-700">{value}</span>}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Gráfico 2: Score de Relevância */}
        <div className="bg-white p-6 rounded-xl shadow-lg lg:col-span-2">
          <h3 className="text-lg font-semibold text-gray-700 mb-4 flex items-center">
            <TrendingUp className="w-5 h-5 mr-2 text-indigo-600" />
            Distribuição de Score de Relevância GSM
          </h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart
              data={scoreData}
              margin={{ top: 5, right: 20, left: 10, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="name" stroke="#6b7280" tick={{ fontSize: 11 }} />
              <YAxis stroke="#6b7280" tick={{ fontSize: 12 }} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="count" name="Licitações" radius={[4, 4, 0, 0]}>
                {scoreData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Segunda linha de gráficos */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Gráfico 3: Iminência */}
        <div className="bg-white p-6 rounded-xl shadow-lg">
          <h3 className="text-lg font-semibold text-gray-700 mb-4 flex items-center">
            <Clock className="w-5 h-5 mr-2 text-orange-500" />
            Distribuição por Iminência (Dias)
          </h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart
              data={iminenciaData}
              margin={{ top: 5, right: 20, left: 10, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="name" stroke="#6b7280" tick={{ fontSize: 11 }} />
              <YAxis stroke="#6b7280" tick={{ fontSize: 12 }} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="count" name="Licitações" radius={[4, 4, 0, 0]}>
                {iminenciaData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        
        {/* Gráfico 4: Categorias de Saúde */}
        <div className="bg-white p-6 rounded-xl shadow-lg">
          <h3 className="text-lg font-semibold text-gray-700 mb-4 flex items-center">
            <Tag className="w-5 h-5 mr-2 text-green-600" />
            Top Categorias de Saúde
          </h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart
              data={categoryData.slice(0, 8)}
              layout="vertical"
              margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis type="number" stroke="#6b7280" tick={{ fontSize: 12 }} />
              <YAxis 
                dataKey="name" 
                type="category" 
                stroke="#6b7280" 
                width={90} 
                tick={{ fontSize: 11 }}
              />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="count" name="Licitações" radius={[0, 4, 4, 0]}>
                {categoryData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};

// --- Componente Principal ---
const MetricsDashboard = () => {
  const [licitacoes, setLicitacoes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    total: 0,
    reais: 0,
    saude: 0,
    urgentes: 0
  });
  const [lastUpdate, setLastUpdate] = useState(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      // Buscar licitações com enriquecimento
      const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          medicamento: '',
          apenas_futuras: true,
          apenas_reais: false,
          page: 1,
          per_page: 200
        })
      });
      
      if (response.ok) {
        const data = await response.json();
        const resultados = data.resultados || [];
        
        setLicitacoes(resultados);
        setStats({
          total: data.total || resultados.length,
          reais: resultados.filter(l => !l.is_mock).length,
          saude: resultados.filter(l => l.is_saude).length,
          urgentes: resultados.filter(l => l.is_urgente).length
        });
        setLastUpdate(new Date());
      }
    } catch (error) {
      console.error('Erro ao buscar dados:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Filtrar apenas licitações de saúde para os gráficos principais
  const licitacoesSaude = useMemo(() => 
    licitacoes.filter(l => l.is_saude),
    [licitacoes]
  );

  return (
    <div className="min-h-screen bg-gray-50 p-4 sm:p-8">
      {/* Header */}
      <header className="max-w-7xl mx-auto mb-8">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-gray-900 flex items-center gap-3">
              <LayoutDashboard className="w-8 h-8 text-indigo-600"/>
              Dashboard de Métricas GSM
            </h1>
            <p className="text-gray-600 mt-1">
              Análise de distribuição e inteligência de negócios em tempo real
            </p>
          </div>
          
          <div className="flex items-center gap-4">
            {lastUpdate && (
              <span className="text-sm text-gray-500">
                Atualizado: {lastUpdate.toLocaleTimeString('pt-BR')}
              </span>
            )}
            <button
              onClick={fetchData}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              Atualizar
            </button>
          </div>
        </div>
      </header>

      {/* Cards de Métricas */}
      <div className="max-w-7xl mx-auto grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-10">
        <MetricCard 
          title="Total de Licitações" 
          value={stats.total.toLocaleString('pt-BR')} 
          badgeColor="#6366f1" 
          icon={ClipboardList}
          loading={loading}
        />
        <MetricCard 
          title="Licitações Reais" 
          value={stats.reais.toLocaleString('pt-BR')} 
          badgeColor="#10b981" 
          icon={Activity}
          loading={loading}
        />
        <MetricCard 
          title="Licitações de Saúde" 
          value={stats.saude.toLocaleString('pt-BR')} 
          badgeColor="#3b82f6" 
          icon={Tag}
          loading={loading}
        />
        <MetricCard 
          title="🚨 Urgentes" 
          value={stats.urgentes.toLocaleString('pt-BR')} 
          badgeColor="#dc2626" 
          icon={Zap}
          loading={loading}
        />
      </div>
      
      {/* Dashboard de Gráficos */}
      <div className="max-w-7xl mx-auto">
        <AnalyticsDashboard 
          licitacoes={licitacoes}
          categories={healthCategories}
          loading={loading}
        />
      </div>

      {/* Tabela Resumo por Fonte */}
      <div className="max-w-7xl mx-auto mt-10">
        <div className="bg-white p-6 rounded-xl shadow-lg">
          <h3 className="text-lg font-semibold text-gray-700 mb-4 flex items-center">
            <Activity className="w-5 h-5 mr-2 text-indigo-600" />
            Distribuição por Fonte de Dados
          </h3>
          
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Fonte</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Total</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Saúde</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Urgentes</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Score Médio</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {(() => {
                  const fontes = {};
                  licitacoes.forEach(l => {
                    const fonte = l.fonte || 'Desconhecido';
                    if (!fontes[fonte]) {
                      fontes[fonte] = { total: 0, saude: 0, urgentes: 0, scores: [] };
                    }
                    fontes[fonte].total++;
                    if (l.is_saude) fontes[fonte].saude++;
                    if (l.is_urgente) fontes[fonte].urgentes++;
                    if (l.score_relevancia) fontes[fonte].scores.push(l.score_relevancia);
                  });
                  
                  return Object.entries(fontes)
                    .sort((a, b) => b[1].total - a[1].total)
                    .slice(0, 10)
                    .map(([fonte, data]) => (
                      <tr key={fonte} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{fonte}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{data.total}</td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className="px-2 py-1 text-xs font-semibold rounded-full bg-green-100 text-green-800">
                            {data.saude}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          {data.urgentes > 0 ? (
                            <span className="px-2 py-1 text-xs font-semibold rounded-full bg-red-100 text-red-800">
                              {data.urgentes}
                            </span>
                          ) : '-'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {data.scores.length > 0 
                            ? Math.round(data.scores.reduce((a, b) => a + b, 0) / data.scores.length)
                            : '-'}
                        </td>
                      </tr>
                    ));
                })()}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="max-w-7xl mx-auto mt-12 pt-6 border-t border-gray-200 text-center text-sm text-gray-500">
        GSM - Buscador de Editais | Sistema de Inteligência de Negócios para Saúde
      </footer>
    </div>
  );
};

export default MetricsDashboard;
