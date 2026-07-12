import { useState, useEffect } from 'react';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export function useListasRadares() {
  const [minhasListas, setMinhasListas] = useState([]);
  const [meusRadares, setMeusRadares] = useState([]);

  const radaresAtalho = minhasListas.slice(0, 5);

  useEffect(() => {
    axios.get(`${API}/listas`).then(res => {
      const listas = res.data.listas || [];
      setMinhasListas(listas.map(l => ({ id: l.id, name: l.nome, keywords: (l.medicamentos || []).join(', ') })));
    }).catch(() => {});

    axios.get(`${API}/radares`).then(res => {
      const radares = res.data.radares || [];
      setMeusRadares(radares.map(r => ({ id: r.id, name: r.nome, email: r.email, freq: r.frequencia, terms: r.termos })));
    }).catch(() => {});
  }, []);

  return {
    minhasListas, setMinhasListas,
    meusRadares, setMeusRadares,
    radaresAtalho,
    API,
  };
}
