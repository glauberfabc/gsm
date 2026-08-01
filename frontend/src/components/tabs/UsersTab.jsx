import React, { useState } from 'react';
import { Plus, Trash2, Pencil, ShieldCheck, User as UserIcon } from 'lucide-react';
import { useUsers } from '../../hooks/useUsers';

const emptyForm = { email: '', password: '', role: 'normal' };

export function UsersTab() {
  const { usuarios, loading, criarUsuario, editarUsuario, deletarUsuario } = useUsers();
  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState(null);
  const [error, setError] = useState('');

  const resetForm = () => {
    setForm(emptyForm);
    setEditingId(null);
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    try {
      if (editingId) {
        const payload = { email: form.email, role: form.role };
        if (form.password) payload.password = form.password;
        await editarUsuario(editingId, payload);
      } else {
        await criarUsuario(form);
      }
      resetForm();
    } catch (err) {
      setError(err.response?.data?.detail || 'Erro ao salvar usuario');
    }
  };

  const startEdit = (usuario) => {
    setEditingId(usuario.id);
    setForm({ email: usuario.email, password: '', role: usuario.role });
  };

  const handleDelete = async (usuario) => {
    if (!window.confirm(`Deletar o login ${usuario.email}?`)) return;
    try {
      await deletarUsuario(usuario.id);
    } catch (err) {
      alert(err.response?.data?.detail || 'Erro ao deletar usuario');
    }
  };

  return (
    <div className="space-y-8">
      <h2 className="text-3xl font-black text-slate-800 uppercase tracking-tight">Usuarios</h2>

      <form onSubmit={handleSubmit} className="bg-white p-8 rounded-2xl shadow-lg border border-slate-200 space-y-4" data-testid="users-form">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <input
            type="email"
            required
            placeholder="Email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            className="p-3 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:border-blue-400"
            data-testid="users-form-email"
          />
          <input
            type="password"
            required={!editingId}
            placeholder={editingId ? 'Nova senha (opcional)' : 'Senha'}
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            className="p-3 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:border-blue-400"
            data-testid="users-form-password"
          />
          <select
            value={form.role}
            onChange={(e) => setForm({ ...form, role: e.target.value })}
            className="p-3 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:border-blue-400"
            data-testid="users-form-role"
          >
            <option value="normal">Normal</option>
            <option value="super_admin">Super Admin</option>
          </select>
        </div>

        {error && <p className="text-red-600 text-sm font-bold" data-testid="users-form-error">{error}</p>}

        <div className="flex gap-3">
          <button type="submit" className="bg-blue-600 text-white px-8 py-3 rounded-xl font-black text-sm uppercase flex items-center gap-2 hover:bg-blue-700" data-testid="users-form-submit">
            <Plus size={18}/> {editingId ? 'Salvar edicao' : 'Criar login'}
          </button>
          {editingId && (
            <button type="button" onClick={resetForm} className="px-8 py-3 rounded-xl font-black text-sm uppercase text-slate-500 hover:text-slate-700">
              Cancelar
            </button>
          )}
        </div>
      </form>

      {loading ? (
        <p className="text-slate-400 font-bold uppercase text-sm">Carregando...</p>
      ) : (
        <div className="bg-white rounded-2xl shadow-lg border border-slate-200 overflow-hidden">
          <table className="w-full text-left">
            <thead className="bg-slate-50 text-slate-500 text-xs font-black uppercase">
              <tr>
                <th className="px-6 py-4">Email</th>
                <th className="px-6 py-4">Papel</th>
                <th className="px-6 py-4">Criado em</th>
                <th className="px-6 py-4 text-right">Acoes</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {usuarios.map((usuario) => (
                <tr key={usuario.id} data-testid={`user-row-${usuario.id}`}>
                  <td className="px-6 py-4 font-bold text-slate-700">{usuario.email}</td>
                  <td className="px-6 py-4">
                    <span className={`px-3 py-1 rounded-full text-[10px] font-black uppercase flex items-center gap-1 w-fit ${usuario.role === 'super_admin' ? 'bg-purple-100 text-purple-700' : 'bg-slate-100 text-slate-600'}`}>
                      {usuario.role === 'super_admin' ? <ShieldCheck size={12}/> : <UserIcon size={12}/>}
                      {usuario.role === 'super_admin' ? 'Super Admin' : 'Normal'}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-slate-400 text-sm">{new Date(usuario.created_at).toLocaleDateString('pt-BR')}</td>
                  <td className="px-6 py-4 text-right space-x-2">
                    <button onClick={() => startEdit(usuario)} data-testid={`user-edit-${usuario.id}`} className="p-2 rounded-lg text-slate-400 hover:text-blue-600 hover:bg-blue-50">
                      <Pencil size={16}/>
                    </button>
                    <button onClick={() => handleDelete(usuario)} data-testid={`user-delete-${usuario.id}`} className="p-2 rounded-lg text-slate-400 hover:text-red-600 hover:bg-red-50">
                      <Trash2 size={16}/>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
