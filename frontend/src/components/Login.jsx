import React, { useState } from 'react';
import { LogIn, Loader2, Eye, EyeOff } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
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
          <label htmlFor="login-email" className="text-xs font-black text-slate-500 uppercase">Email</label>
          <input
            id="login-email"
            type="email"
            required
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:border-blue-400"
            data-testid="login-email"
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="login-password" className="text-xs font-black text-slate-500 uppercase">Senha</label>
          <div className="relative">
            <input
              id="login-password"
              type={showPassword ? 'text' : 'password'}
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full p-3 pr-12 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:border-blue-400"
              data-testid="login-password"
            />
            <button
              type="button"
              onClick={() => setShowPassword((v) => !v)}
              tabIndex={-1}
              aria-label={showPassword ? 'Ocultar senha' : 'Mostrar senha'}
              data-testid="login-password-toggle"
              className="absolute right-0 top-0 h-full w-12 flex items-center justify-center text-slate-400 hover:text-slate-600"
            >
              {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
            </button>
          </div>
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
