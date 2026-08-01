import React, { useState } from 'react';
import { LogIn, Loader2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await login(email, password);
    } catch (err) {
      setError('Email ou senha invalidos');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-100 flex items-center justify-center px-4">
      <form
        onSubmit={handleSubmit}
        className="bg-white p-10 rounded-2xl shadow-2xl border border-slate-200 w-full max-w-md space-y-6"
        data-testid="login-form"
      >
        <h1 className="text-2xl font-black text-slate-800 uppercase text-center">GSM Intelligence</h1>

        <div className="space-y-2">
          <label className="text-xs font-black text-slate-500 uppercase">Email</label>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:border-blue-400"
            data-testid="login-email"
          />
        </div>

        <div className="space-y-2">
          <label className="text-xs font-black text-slate-500 uppercase">Senha</label>
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:border-blue-400"
            data-testid="login-password"
          />
        </div>

        {error && <p className="text-red-600 text-sm font-bold" data-testid="login-error">{error}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="w-full bg-blue-600 text-white py-3 rounded-xl font-black uppercase flex items-center justify-center gap-2 hover:bg-blue-700 disabled:opacity-50"
          data-testid="login-submit"
        >
          {submitting ? <Loader2 className="animate-spin" size={18} /> : <LogIn size={18} />}
          Entrar
        </button>
      </form>
    </div>
  );
}
