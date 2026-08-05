import React, { useRef, useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Search, ListChecks, Radar, TrendingUp, Pill, Zap, Settings, ShieldCheck, BriefcaseBusiness, Target, Bell, Activity, Users, LogOut } from 'lucide-react';

const TABS = [
  { id: 'search', label: 'Pesquisa', icon: Search, color: 'blue' },
  { id: 'lists', label: 'Minhas Listas', icon: ListChecks, color: 'indigo' },
  { id: 'radar', label: 'Radares', icon: Radar, color: 'emerald' },
  { id: 'precos', label: 'Precos', icon: TrendingUp, color: 'amber' },
  { id: 'anvisa', label: 'Janela ANVISA', icon: Pill, color: 'red' },
  { id: 'radar-lmr', label: 'Radar LMR', icon: Target, color: 'teal' },
  { id: 'radar-farma', label: 'Radar Farma', icon: Activity, color: 'rose' },
  { id: 'dama', label: 'DAMA IA', icon: Zap, color: 'purple' },
];

export default function Header({ activeTab: propsActiveTab, setActiveTab: propsSetActiveTab, onAnvisaLoad, notificacoes, user, onLogout }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { notificacoes: alertas = [], naoLidas = 0, showDropdown, setShowDropdown, marcarLida } = notificacoes || {};
  const dropdownRef = useRef(null);
  const [notifExpandidaId, setNotifExpandidaId] = useState(null);

  // Determinar aba ativa pela rota se não for passado via props
  const getActiveTabFromPath = () => {
    const path = location.pathname;
    if (path === '/') return propsActiveTab || 'search';
    if (path === '/notificacoes') return 'notificacoes';
    if (path === '/dashboard') return 'anvisa'; // Mapeamento legado do projeto
    if (path === '/radar-farma') return 'radar-farma';
    return propsActiveTab || 'search';
  };

  const activeTab = getActiveTabFromPath();

  const tabs = user?.role === 'super_admin'
    ? [...TABS, { id: 'usuarios', label: 'Usuarios', icon: Users, color: 'slate' }]
    : TABS;

  const handleTabClick = (tabId) => {
    if (tabId === 'search') navigate('/');
    else if (tabId === 'radar-farma') navigate('/radar-farma');
    else if (tabId === 'anvisa') navigate('/dashboard');
    else if (tabId === 'notificacoes') navigate('/notificacoes');
    else navigate('/'); // abas sem rota propria: garante que a URL nao fique presa numa rota antiga (ex: /radar-farma), o que travava o destaque no header

    if (propsSetActiveTab) propsSetActiveTab(tabId);
    if (tabId === 'anvisa' && onAnvisaLoad) onAnvisaLoad();
  };

  useEffect(() => {
    function handleClickOutside(e) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setShowDropdown?.(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [setShowDropdown]);

  return (
    <header className="bg-[#0F172A] text-white p-6 sticky top-0 z-50 shadow-2xl border-b-4 border-blue-600">
      <div className="max-w-7xl mx-auto flex justify-between items-center">
        <div className="flex items-center gap-8">
          <div className="rounded-2xl shadow-xl overflow-hidden" style={{minWidth: '200px'}}>
            <img 
              src="https://customer-assets.emergentagent.com/job_edital-seeker/artifacts/m5l6jiyo_LOGO-2-2048x828.png" 
              alt="Grupo Smart Medical" 
              className="h-16 w-auto object-contain"
              style={{display: 'block'}}
            />
          </div>
          <div className="hidden lg:block">
            <p className="text-xs text-emerald-400 font-bold uppercase tracking-widest flex items-center gap-2">
              <ShieldCheck size={16}/> v74.0 - Sistema Proprietario GSM Intelligence
            </p>
          </div>
        </div>
        
        <nav className="flex items-center gap-2">
          <div className="flex bg-slate-800 p-1.5 rounded-2xl border border-slate-700">
            {tabs.map(tab => (
              <button 
                key={tab.id}
                onClick={() => handleTabClick(tab.id)}
                data-testid={`tab-${tab.id}`}
                className={`px-4 py-3 rounded-xl text-[11px] font-black uppercase flex items-center gap-1.5 transition-all ${
                  activeTab === tab.id 
                    ? `bg-${tab.color}-600 text-white shadow-lg` 
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <tab.icon size={18}/> {tab.label}
              </button>
            ))}
          </div>

          {/* Notification Bell */}
          <div className="relative" ref={dropdownRef}>
            <button
              data-testid="notificacao-bell"
              onClick={() => setShowDropdown?.(!showDropdown)}
              className="relative p-3 rounded-xl transition-all hover:bg-slate-700"
            >
              <Bell size={22} className={naoLidas > 0 ? 'text-amber-400' : 'text-slate-400'}/>
              {naoLidas > 0 && (
                <span data-testid="notificacao-badge"
                  className="absolute -top-0.5 -right-0.5 min-w-[20px] h-5 flex items-center justify-center rounded-full text-[10px] font-black bg-gradient-to-r from-amber-400 to-emerald-400 text-slate-900 shadow-lg shadow-amber-400/30 animate-pulse">
                  {naoLidas}
                </span>
              )}
            </button>

            {showDropdown && (
              <div data-testid="notificacao-dropdown"
                className="absolute right-0 top-full mt-2 w-96 bg-white rounded-2xl shadow-2xl border-2 border-slate-200 z-[100] overflow-hidden">
                <div className="bg-gradient-to-r from-slate-700 to-slate-800 px-4 py-2.5 flex items-center justify-between">
                  <span className="text-white font-black text-xs uppercase tracking-wider flex items-center gap-2">
                    📋 Feed Regulatório ANVISA/DOU
                  </span>
                  <span className="text-white/80 text-[10px] font-bold">{naoLidas} nova(s)</span>
                </div>
                <div className="max-h-80 overflow-y-auto divide-y divide-slate-100">
                  {alertas.length === 0 ? (
                    <div className="px-4 py-8 text-center">
                      <Bell size={28} className="text-slate-300 mx-auto mb-2"/>
                      <p className="text-slate-400 text-xs font-bold">Nenhuma notificação ainda</p>
                      <p className="text-slate-300 text-[10px]">Desabastecimento, novos registros, cancelamentos e notícias de laboratório aparecem aqui</p>
                    </div>
                  ) : alertas.map((a, i) => {
                    const expandida = notifExpandidaId === a.id;
                    const CATEGORIA_COR = {
                      desabastecimento: 'bg-red-100 text-red-700',
                      cancelamento_suspensao: 'bg-orange-100 text-orange-700',
                      novo_registro: 'bg-blue-100 text-blue-700',
                      laboratorio: 'bg-purple-100 text-purple-700',
                    };
                    const CATEGORIA_LABEL = {
                      desabastecimento: 'Desabastecimento',
                      cancelamento_suspensao: 'Cancelamento/Suspensão',
                      novo_registro: 'Novo Registro',
                      laboratorio: 'Laboratório',
                    };
                    return (
                      <div key={a.id || i}
                        data-testid={`notificacao-item-${i}`}
                        onClick={() => { setNotifExpandidaId(expandida ? null : a.id); marcarLida?.(a.id); }}
                        className={`px-4 py-3 cursor-pointer transition-colors hover:bg-slate-50 ${!a.lida ? 'bg-amber-50/50' : ''}`}>
                        <div className="flex items-center gap-2 mb-1">
                          <span className={`px-2 py-0.5 rounded-full text-[10px] font-black shadow-sm ${CATEGORIA_COR[a.categoria] || 'bg-slate-100 text-slate-700'}`}>
                            {CATEGORIA_LABEL[a.categoria] || a.categoria}
                          </span>
                          {!a.lida && <span className="w-2 h-2 bg-amber-500 rounded-full flex-shrink-0 animate-pulse"/>}
                        </div>
                        <p className="text-xs font-bold text-slate-800 line-clamp-2">{a.titulo}</p>
                        <div className="flex items-center gap-2 mt-1">
                          {a.medicamento && <span className="text-[9px] text-slate-400">{a.medicamento}</span>}
                          {a.data_evento && <span className="text-[9px] text-slate-400">{a.data_evento}</span>}
                        </div>
                        {expandida && (
                          <div className="mt-2 pt-2 border-t border-slate-100">
                            <p className="text-[10px] text-slate-500">{a.descricao}</p>
                            {a.url_fonte_oficial && (
                              <a href={a.url_fonte_oficial} target="_blank" rel="noopener noreferrer"
                                onClick={(e) => e.stopPropagation()}
                                className="inline-flex items-center gap-1 mt-2 text-[10px] font-bold text-blue-600 hover:text-blue-800">
                                🔗 Acessar Documento Oficial
                              </a>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          <button 
            onClick={() => handleTabClick('settings')} 
            data-testid="tab-settings"
            className={`p-3 transition-all rounded-xl ${activeTab === 'settings' ? 'text-white bg-slate-700' : 'text-slate-400 hover:text-white'}`}
          >
            <Settings size={22}/>
          </button>

          <button
            onClick={onLogout}
            data-testid="logout-button"
            className="p-3 text-slate-400 hover:text-red-400 transition-all rounded-xl"
            title="Sair"
          >
            <LogOut size={22} />
          </button>
        </nav>
      </div>
    </header>
  );
}
