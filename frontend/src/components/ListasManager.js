import React, { useState, useEffect } from 'react';
import { X, Plus, Edit2, Trash2, Save } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

export default function ListasManager({ onClose, onListaSelected }) {
  const [listas, setListas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editando, setEditando] = useState(null);
  const [criandoNova, setCriandoNova] = useState(false);
  
  // Form state
  const [formNome, setFormNome] = useState('');
  const [formDescricao, setFormDescricao] = useState('');
  const [formMedicamentos, setFormMedicamentos] = useState('');

  useEffect(() => {
    carregarListas();
  }, []);

  const carregarListas = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`${API_URL}/api/listas`);
      const data = await response.json();
      
      if (response.ok) {
        setListas(data.listas || []);
      } else {
        throw new Error(data.detail || 'Erro ao carregar listas');
      }
    } catch (err) {
      setError(err.message);
      console.error('Erro ao carregar listas:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCriarLista = async () => {
    if (!formNome.trim()) {
      alert('Nome da lista é obrigatório');
      return;
    }

    try {
      const medicamentos = formMedicamentos
        .split('\n')
        .map(m => m.trim())
        .filter(m => m.length > 0);

      const response = await fetch(`${API_URL}/api/listas`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nome: formNome.trim(),
          descricao: formDescricao.trim() || null,
          medicamentos
        })
      });

      const data = await response.json();

      if (response.ok) {
        await carregarListas();
        limparForm();
        setCriandoNova(false);
      } else {
        alert(data.detail || 'Erro ao criar lista');
      }
    } catch (err) {
      alert('Erro ao criar lista: ' + err.message);
      console.error(err);
    }
  };

  const handleAtualizarLista = async (listaId) => {
    try {
      const medicamentos = formMedicamentos
        .split('\n')
        .map(m => m.trim())
        .filter(m => m.length > 0);

      const response = await fetch(`${API_URL}/api/listas/${listaId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nome: formNome.trim(),
          descricao: formDescricao.trim() || null,
          medicamentos
        })
      });

      const data = await response.json();

      if (response.ok) {
        await carregarListas();
        limparForm();
        setEditando(null);
      } else {
        alert(data.detail || 'Erro ao atualizar lista');
      }
    } catch (err) {
      alert('Erro ao atualizar lista: ' + err.message);
      console.error(err);
    }
  };

  const handleDeletarLista = async (listaId) => {
    if (!window.confirm('Tem certeza que deseja deletar esta lista?')) {
      return;
    }

    try {
      const response = await fetch(`${API_URL}/api/listas/${listaId}`, {
        method: 'DELETE'
      });

      if (response.ok) {
        await carregarListas();
      } else {
        const data = await response.json();
        alert(data.detail || 'Erro ao deletar lista');
      }
    } catch (err) {
      alert('Erro ao deletar lista: ' + err.message);
      console.error(err);
    }
  };

  const iniciarEdicao = (lista) => {
    setEditando(lista.id);
    setFormNome(lista.nome);
    setFormDescricao(lista.descricao || '');
    setFormMedicamentos(lista.medicamentos.join('\n'));
    setCriandoNova(false);
  };

  const limparForm = () => {
    setFormNome('');
    setFormDescricao('');
    setFormMedicamentos('');
    setEditando(null);
    setCriandoNova(false);
  };

  const handleSelecionarLista = (lista) => {
    if (onListaSelected) {
      onListaSelected(lista);
    }
    if (onClose) {
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="bg-gradient-to-r from-blue-600 to-blue-700 text-white p-6 flex justify-between items-center">
          <div>
            <h2 className="text-2xl font-bold">Minhas Listas de Medicamentos</h2>
            <p className="text-blue-100 text-sm mt-1">
              Gerencie até 5 listas customizadas • <span>{listas.length}</span>/5 criadas
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-white hover:bg-blue-800 rounded-full p-2 transition-colors"
          >
            <X size={24} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {loading && (
            <div className="text-center py-8">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              <p className="mt-2 text-gray-600">Carregando listas...</p>
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
              {error}
            </div>
          )}

          {!loading && !error && (
            <>
              {/* Botão Nova Lista */}
              {!criandoNova && !editando && listas.length < 5 && (
                <button
                  onClick={() => setCriandoNova(true)}
                  className="w-full mb-6 border-2 border-dashed border-blue-300 rounded-lg p-6 text-blue-600 hover:border-blue-500 hover:bg-blue-50 transition-all flex items-center justify-center gap-2"
                >
                  <Plus size={20} />
                  <span className="font-medium">Criar Nova Lista</span>
                </button>
              )}

              {/* Form: Nova Lista ou Editar */}
              {(criandoNova || editando) && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 mb-6">
                  <h3 className="text-lg font-bold text-gray-800 mb-4">
                    {criandoNova ? 'Nova Lista' : 'Editar Lista'}
                  </h3>
                  
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Nome da Lista *
                      </label>
                      <input
                        type="text"
                        value={formNome}
                        onChange={(e) => setFormNome(e.target.value)}
                        placeholder="Ex: Canabidiol, Importados, Alto Custo"
                        className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        maxLength={100}
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Descrição (opcional)
                      </label>
                      <input
                        type="text"
                        value={formDescricao}
                        onChange={(e) => setFormDescricao(e.target.value)}
                        placeholder="Breve descrição da lista"
                        className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        maxLength={500}
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Medicamentos (um por linha)
                      </label>
                      <textarea
                        value={formMedicamentos}
                        onChange={(e) => setFormMedicamentos(e.target.value)}
                        placeholder="Canabidiol&#10;Mevatyl&#10;CBD"
                        rows={6}
                        className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm"
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        <span>{formMedicamentos.split('\n').filter(m => m.trim()).length}</span> medicamentos
                      </p>
                    </div>

                    <div className="flex gap-3">
                      <button
                        onClick={() => editando ? handleAtualizarLista(editando) : handleCriarLista()}
                        className="flex-1 bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 transition-colors font-medium flex items-center justify-center gap-2"
                      >
                        <Save size={18} />
                        {editando ? 'Atualizar' : 'Criar'} Lista
                      </button>
                      <button
                        onClick={limparForm}
                        className="px-6 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors font-medium"
                      >
                        Cancelar
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Lista de Listas */}
              {listas.length === 0 ? (
                <div className="text-center py-12 text-gray-500">
                  <p className="text-lg">Nenhuma lista criada ainda</p>
                  <p className="text-sm mt-2">Clique em "Criar Nova Lista" para começar</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {listas.map((lista) => (
                    <div
                      key={lista.id}
                      className="border border-gray-200 rounded-lg p-5 hover:border-blue-300 transition-colors bg-white shadow-sm"
                    >
                      <div className="flex justify-between items-start mb-3">
                        <div className="flex-1">
                          <h4 className="text-lg font-bold text-gray-800">{lista.nome}</h4>
                          {lista.descricao && (
                            <p className="text-sm text-gray-600 mt-1">{lista.descricao}</p>
                          )}
                          <p className="text-xs text-gray-500 mt-2">
                            <span>{lista.medicamentos.length}</span> medicamento(s)
                          </p>
                        </div>
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleSelecionarLista(lista)}
                            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-sm font-medium"
                          >
                            Usar
                          </button>
                          <button
                            onClick={() => iniciarEdicao(lista)}
                            className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                            title="Editar"
                          >
                            <Edit2 size={18} />
                          </button>
                          <button
                            onClick={() => handleDeletarLista(lista.id)}
                            className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                            title="Deletar"
                          >
                            <Trash2 size={18} />
                          </button>
                        </div>
                      </div>

                      {lista.medicamentos.length > 0 && (
                        <div className="bg-gray-50 rounded-lg p-3 mt-3">
                          <p className="text-xs font-medium text-gray-600 mb-2">Medicamentos:</p>
                          <div className="flex flex-wrap gap-2">
                            {lista.medicamentos.slice(0, 10).map((med, idx) => (
                              <span
                                key={idx}
                                className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded-full"
                              >
                                {med}
                              </span>
                            ))}
                            {lista.medicamentos.length > 10 && (
                              <span className="px-2 py-1 bg-gray-200 text-gray-600 text-xs rounded-full">
                                +<span>{lista.medicamentos.length - 10}</span> mais
                              </span>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
