import { useCallback, useEffect, useState } from 'react';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export function useUsers() {
  const [usuarios, setUsuarios] = useState([]);
  const [loading, setLoading] = useState(true);

  const carregarUsuarios = useCallback(() => {
    setLoading(true);
    axios
      .get(`${API}/users`)
      .then((res) => setUsuarios(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    carregarUsuarios();
  }, [carregarUsuarios]);

  const criarUsuario = useCallback((payload) => {
    return axios.post(`${API}/users`, payload).then((res) => {
      setUsuarios((prev) => [...prev, res.data]);
      return res.data;
    });
  }, []);

  const editarUsuario = useCallback((id, payload) => {
    return axios.put(`${API}/users/${id}`, payload).then((res) => {
      setUsuarios((prev) => prev.map((u) => (u.id === id ? res.data : u)));
      return res.data;
    });
  }, []);

  const deletarUsuario = useCallback((id) => {
    return axios.delete(`${API}/users/${id}`).then(() => {
      setUsuarios((prev) => prev.filter((u) => u.id !== id));
    });
  }, []);

  return { usuarios, loading, carregarUsuarios, criarUsuario, editarUsuario, deletarUsuario };
}
