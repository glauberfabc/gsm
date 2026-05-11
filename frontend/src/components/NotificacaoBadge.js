import React, { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { Bell, X, Check, Archive, RefreshCw } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const NotificacaoBadge = () => {
  const [stats, setStats] = useState(null);
  const [notificacoes, setNotificacoes] = useState([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const dropdownRef = useRef(null);

  const fetchStats = async () => {
    try {
      const [statsRes, notifRes] = await Promise.all([
        axios.get(`${API}/notificacoes/stats`),
        axios.get(`${API}/notificacoes?status=pendente&por_pagina=5`)
      ]);
      setStats(statsRes.data);
      setNotificacoes(notifRes.data.notificacoes || []);
    } catch (error) {
      console.error('Erro ao buscar notificações:', error);
    }
  };

  useEffect(() => {
    fetchStats();
    // Atualizar a cada 5 minutos
    const interval = setInterval(fetchStats, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  // Fechar dropdown ao clicar fora
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleMarcarLida = async (id, e) => {
    e.preventDefault();
    e.stopPropagation();
    setLoading(true);
    try {
      await axios.post(`${API}/notificacoes/${id}/lida`);
      await fetchStats();
    } catch (error) {
      console.error('Erro ao marcar como lida:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleArquivar = async (id, e) => {
    e.preventDefault();
    e.stopPropagation();
    setLoading(true);
    try {
      await axios.post(`${API}/notificacoes/${id}/arquivar`);
      await fetchStats();
    } catch (error) {
      console.error('Erro ao arquivar:', error);
    } finally {
      setLoading(false);
    }
  };

  const pendentes = stats?.total_pendentes || 0;

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Botão do sino */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 text-white hover:bg-blue-600 rounded-lg transition-colors"
        title="Notificações"
      >
        <Bell className="w-6 h-6" />
        {pendentes > 0 && (
          <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs font-bold rounded-full flex items-center justify-center animate-pulse">
            {pendentes > 9 ? '9+' : pendentes}
          </span>
        )}
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-80 bg-white rounded-lg shadow-xl border z-50">
          {/* Header do dropdown */}
          <div className="p-3 border-b flex items-center justify-between">
            <h3 className="font-semibold text-gray-800">Notificações</h3>
            <button
              onClick={() => setIsOpen(false)}
              className="text-gray-400 hover:text-gray-600"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Lista de notificações */}
          <div className="max-h-80 overflow-y-auto">
            {loading ? (
              <div className="p-4 text-center">
                <RefreshCw className="w-6 h-6 animate-spin text-blue-600 mx-auto" />
              </div>
            ) : notificacoes.length === 0 ? (
              <div className="p-6 text-center text-gray-500">
                <Bell className="w-10 h-10 text-gray-300 mx-auto mb-2" />
                <p className="text-sm">Nenhuma notificação pendente</p>
              </div>
            ) : (
              notificacoes.map(notif => (
                <div
                  key={notif.id}
                  className="p-3 border-b hover:bg-gray-50 transition-colors"
                >
                  <div className="flex justify-between items-start gap-2">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-800 truncate">
                        {notif.titulo}
                      </p>
                      <p className="text-xs text-gray-500 mt-1">
                        {notif.estado} • {notif.modalidade}
                      </p>
                      <p className="text-xs text-purple-600 mt-1">
                        {notif.motivo_match}
                      </p>
                    </div>
                    <div className="flex gap-1 flex-shrink-0">
                      <button
                        onClick={(e) => handleMarcarLida(notif.id, e)}
                        className="p-1.5 text-green-600 hover:bg-green-50 rounded"
                        title="Marcar como lida"
                      >
                        <Check className="w-4 h-4" />
                      </button>
                      <button
                        onClick={(e) => handleArquivar(notif.id, e)}
                        className="p-1.5 text-gray-400 hover:bg-gray-100 rounded"
                        title="Arquivar"
                      >
                        <Archive className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Footer do dropdown */}
          <div className="p-3 border-t bg-gray-50">
            <Link
              to="/notificacoes"
              onClick={() => setIsOpen(false)}
              className="block w-full text-center text-sm text-blue-600 hover:text-blue-800 font-medium"
            >
              Ver todas as notificações →
            </Link>
          </div>
        </div>
      )}
    </div>
  );
};

export default NotificacaoBadge;
