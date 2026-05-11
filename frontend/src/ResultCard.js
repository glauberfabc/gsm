import React from 'react';
import { MapPin, FileText, Calendar, Building, Check, RefreshCw } from 'lucide-react';

const ResultCard = ({ resultado, index, onRefresh, isRefreshing }) => {
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

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('pt-BR');
  };

  return (
    <div
      className={`bg-white rounded-lg shadow-md hover:shadow-xl transition-shadow p-6 border-l-4 ${
        resultado.is_mock ? 'border-gray-400' : 'border-green-500'
      }`}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <h3 className="font-bold text-lg text-gray-900 mb-1">
            {resultado.medicamento}
          </h3>
          <div className="flex items-center gap-2">
            <MapPin size={16} className="text-blue-600" />
            <span className="text-sm font-semibold text-blue-900">
              {resultado.estado}
            </span>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1">
          {resultado.is_mock ? (
            <span className="px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded-full">
              📋 Exemplo
            </span>
          ) : (
            <span className="px-2 py-1 bg-green-100 text-green-700 text-xs rounded-full flex items-center gap-1">
              <Check size={12} /> Real
            </span>
          )}
          {!resultado.is_mock && ['CE', 'ES', 'SP'].includes(resultado.estado) && (
            <button
              onClick={() => onRefresh(resultado.estado)}
              disabled={isRefreshing}
              className="p-1 text-blue-600 hover:bg-blue-50 rounded transition-colors disabled:opacity-50"
              title="Atualizar dados"
            >
              <RefreshCw size={16} className={isRefreshing ? 'animate-spin' : ''} />
            </button>
          )}
        </div>
      </div>

      {/* Status */}
      <div className="mb-3">
        <span className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(resultado.status)}`}>
          {resultado.status}
        </span>
      </div>

      {/* Tags */}
      {resultado.tags && resultado.tags.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-4">
          {resultado.tags.map((tag, tagIndex) => (
            <span
              key={`${tag}-${tagIndex}`}
              className="px-2 py-1 bg-blue-50 text-blue-700 text-xs rounded"
            >
              {tag === 'alto_custo' && '💰 Alto Custo'}
              {tag === 'importado' && '🌍 Importado'}
              {tag === 'judicial' && '⚖️ Judicial'}
            </span>
          ))}
        </div>
      )}

      {/* LOCAL */}
      <div className="bg-blue-50 p-3 rounded-lg border border-blue-200 mb-3">
        <div className="flex items-start gap-2">
          <Building size={18} className="mt-0.5 flex-shrink-0 text-blue-600" />
          <div>
            <p className="text-xs text-blue-600 font-semibold mb-1">LOCAL DA LICITAÇÃO:</p>
            <p className="font-bold text-gray-900">{resultado.orgao_licitante}</p>
          </div>
        </div>
      </div>

      {/* DATA */}
      <div className="bg-green-50 p-3 rounded-lg border border-green-200 mb-3">
        <div className="flex items-center gap-2">
          <Calendar size={18} className="flex-shrink-0 text-green-600" />
          <div>
            <p className="text-xs text-green-600 font-semibold mb-1">DATA DE REFERÊNCIA:</p>
            <p className="font-bold text-gray-900 text-base">{formatDate(resultado.data_referencia)}</p>
          </div>
        </div>
      </div>

      {/* PROCESSO */}
      <div className="flex items-start gap-2 text-gray-600 mb-4">
        <FileText size={16} className="mt-0.5 flex-shrink-0" />
        <div>
          <p className="font-medium text-gray-700">{resultado.modalidade}</p>
          <p className="text-xs text-gray-500">Processo Nº {resultado.numero_processo}</p>
        </div>
      </div>

      {/* Link */}
      <div className="mt-4 pt-4 border-t-2 border-gray-300">
        <a
          href={resultado.link_origem}
          target="_blank"
          rel="noopener noreferrer"
          className="block w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-4 rounded-lg text-center transition-colors"
        >
          🔗 ACESSAR EDITAL NO PORTAL OFICIAL
        </a>
        <p className="text-xs text-gray-500 mt-2 text-center">
          Clique para ver detalhes completos no site do estado
        </p>
      </div>
    </div>
  );
};

export default ResultCard;
