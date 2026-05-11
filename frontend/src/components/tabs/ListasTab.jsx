import React from 'react';
import { Plus, CheckCircle, Search } from 'lucide-react';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export function ListasTab({ minhasListas, setMinhasListas, onSearch }) {
  return (
    <div className="space-y-8">
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-black text-slate-800 uppercase tracking-tight">Minhas Listas / Atalhos</h2>
        <button
          onClick={() => {
            const novaLista = { id: `l${Date.now()}`, nome: 'Nova Lista', medicamentos: [] };
            axios.post(`${API}/listas`, novaLista).then(() => {
              setMinhasListas(prev => [...prev, { id: novaLista.id, name: novaLista.nome, keywords: '' }]);
            }).catch(() => alert('Erro ao criar lista'));
          }}
          className="bg-indigo-600 text-white px-8 py-4 rounded-xl font-black text-sm uppercase flex items-center gap-2 shadow-lg hover:bg-indigo-700"
        >
          <Plus size={20}/> Nova Lista
        </button>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {minhasListas.map(list => (
          <div key={`lista-${list.id}`} className="bg-white p-8 rounded-2xl shadow-lg border border-slate-200 relative overflow-hidden group" data-testid={`lista-${list.id}`}>
            <div className="absolute top-0 left-0 w-2 h-full bg-indigo-500 group-hover:w-3 transition-all"></div>
            <div className="pl-4 space-y-4">
              <input
                className="text-2xl font-black text-slate-800 uppercase bg-transparent outline-none w-full focus:bg-slate-50 px-2 py-1 rounded"
                defaultValue={list.name}
                onChange={(e) => {
                  const idx = minhasListas.findIndex(l => l.id === list.id);
                  if (idx >= 0) {
                    const updated = [...minhasListas];
                    updated[idx] = { ...updated[idx], name: e.target.value };
                    setMinhasListas(updated);
                  }
                }}
              />
              <textarea
                className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl font-medium text-slate-600 outline-none focus:border-indigo-400 resize-none"
                rows="2"
                defaultValue={list.keywords}
                placeholder="Termos separados por virgula: insulina, glicose, canabidiol"
                onChange={(e) => {
                  const idx = minhasListas.findIndex(l => l.id === list.id);
                  if (idx >= 0) {
                    const updated = [...minhasListas];
                    updated[idx] = { ...updated[idx], keywords: e.target.value };
                    setMinhasListas(updated);
                  }
                }}
              />
              <div className="flex gap-3">
                <button
                  onClick={() => {
                    const listaData = minhasListas.find(l => l.id === list.id);
                    if (!listaData) return;
                    axios.put(`${API}/listas/${list.id}`, {
                      nome: listaData.name,
                      medicamentos: listaData.keywords.split(',').map(t => t.trim()).filter(t => t)
                    }).then(() => alert('Lista salva com sucesso!')).catch(() => alert('Erro ao salvar lista'));
                  }}
                  className="flex-1 bg-slate-800 text-white py-3 rounded-xl font-bold text-sm uppercase hover:bg-indigo-600 transition-all flex items-center justify-center gap-2"
                >
                  <CheckCircle size={16}/> Salvar
                </button>
                <button
                  onClick={() => onSearch(list.id, list.keywords)}
                  className="flex-1 bg-indigo-600 text-white py-3 rounded-xl font-bold text-sm uppercase hover:bg-indigo-700 transition-all flex items-center justify-center gap-2"
                >
                  <Search size={16}/> Pesquisar
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
