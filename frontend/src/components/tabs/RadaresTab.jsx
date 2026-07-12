import React from 'react';
import { Plus, Mail, Clock, Search, CheckCircle } from 'lucide-react';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export function RadaresTab({ meusRadares, setMeusRadares, onSearch }) {
  return (
    <div className="space-y-8">
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-black text-slate-800 uppercase tracking-tight">Gestao de Radares (E-mail)</h2>
        <button className="bg-emerald-600 text-white px-8 py-4 rounded-xl font-black text-sm uppercase flex items-center gap-2 shadow-lg hover:bg-emerald-700" onClick={() => {
          const novoRadar = { nome: 'Novo Radar', termos: '', email: '', frequencia: '24h' };
          axios.post(`${API}/radares`, novoRadar).then((res) => {
            const radarCriado = res.data.radar;
            setMeusRadares(prev => [...prev, { id: radarCriado.id, name: radarCriado.nome, terms: radarCriado.termos, email: radarCriado.email, freq: radarCriado.frequencia }]);
          }).catch(() => alert('Erro ao criar radar'));
        }}>
          <Plus size={20}/> Novo Radar
        </button>
      </div>
      <div className="space-y-6">
        {meusRadares.map(radar => (
          <div key={`radar-${radar.id}`} className="bg-white p-8 rounded-2xl shadow-lg border border-slate-200 relative overflow-hidden" data-testid={`radar-${radar.id}`}>
            <div className="absolute top-0 left-0 w-2 h-full bg-emerald-500"></div>
            <div className="pl-4 grid md:grid-cols-2 gap-8">
              <div className="space-y-4">
                <input className="text-2xl font-black text-slate-800 outline-none w-full bg-transparent" defaultValue={radar.name}
                  onChange={(e) => {
                    const idx = meusRadares.findIndex(r => r.id === radar.id);
                    if (idx >= 0) { const updated = [...meusRadares]; updated[idx] = { ...updated[idx], name: e.target.value }; setMeusRadares(updated); }
                  }}
                />
                <textarea className="w-full p-4 bg-slate-50 border-2 border-slate-100 rounded-xl h-32 font-medium outline-none focus:border-emerald-400" defaultValue={radar.terms} placeholder="Termos de busca..."
                  onChange={(e) => {
                    const idx = meusRadares.findIndex(r => r.id === radar.id);
                    if (idx >= 0) { const updated = [...meusRadares]; updated[idx] = { ...updated[idx], terms: e.target.value }; setMeusRadares(updated); }
                  }}
                />
              </div>
              <div className="space-y-4">
                <div className="bg-blue-50 p-4 rounded-xl border border-blue-100">
                  <label className="text-xs font-black text-blue-500 uppercase mb-2 block flex items-center gap-2">
                    <Mail size={14}/> E-mail para Notificacoes
                  </label>
                  <input className="w-full bg-transparent font-bold text-blue-800 outline-none text-lg" defaultValue={radar.email}
                    onChange={(e) => {
                      const idx = meusRadares.findIndex(r => r.id === radar.id);
                      if (idx >= 0) { const updated = [...meusRadares]; updated[idx] = { ...updated[idx], email: e.target.value }; setMeusRadares(updated); }
                    }}
                  />
                </div>
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-100 flex justify-between items-center">
                  <span className="flex items-center gap-2 text-sm font-bold text-slate-500"><Clock size={16} className="text-emerald-500"/> Frequencia:</span>
                  <select className="bg-transparent font-black text-emerald-700 outline-none" defaultValue={radar.freq}
                    onChange={(e) => {
                      const idx = meusRadares.findIndex(r => r.id === radar.id);
                      if (idx >= 0) { const updated = [...meusRadares]; updated[idx] = { ...updated[idx], freq: e.target.value }; setMeusRadares(updated); }
                    }}
                  >
                    <option value="8h">8 em 8 horas</option>
                    <option value="12h">12 em 12 horas</option>
                    <option value="24h">Diario (24h)</option>
                  </select>
                </div>
                <button className="w-full bg-slate-900 text-white py-4 rounded-xl font-black uppercase text-sm hover:bg-emerald-600 transition-all"
                  onClick={() => {
                    const radarData = meusRadares.find(r => r.id === radar.id);
                    if (!radarData) return;
                    axios.put(`${API}/radares/${radar.id}`, { nome: radarData.name, termos: radarData.terms, email: radarData.email, frequencia: radarData.freq })
                      .then(() => alert('Radar salvo com sucesso!')).catch(() => alert('Erro ao salvar radar'));
                  }}
                >
                  Salvar Radar
                </button>
                <button data-testid={`radar-pesquisar-${radar.id}`}
                  className="w-full bg-indigo-600 text-white py-4 rounded-xl font-black uppercase text-sm hover:bg-indigo-700 transition-all flex items-center justify-center gap-2"
                  onClick={() => {
                    if (radar.terms) { onSearch(radar.id, radar.terms); } else { alert('Cadastre os termos de busca antes de pesquisar'); }
                  }}
                >
                  <Search size={16}/> Pesquisar Editais
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
