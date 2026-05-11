import { useState, useEffect } from 'react';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export function useListasRadares() {
  const [minhasListas, setMinhasListas] = useState([
    {id: 1, name: 'Paloma', keywords: 'insulina, glicose'},
    {id: 2, name: 'Claudio', keywords: 'prolia, denosumabe'}
  ]);
  const [meusRadares, setMeusRadares] = useState([
    {id: 1, name: 'Radar Comercial SC', email: 'vendas.sc@gsm.com.br', freq: '8h', terms: 'canabidiol'}
  ]);
  const [radaresAtalho, setRadaresAtalho] = useState([
    {id: 'r1', name: 'Paloma', keywords: 'insulina'},
    {id: 'r2', name: 'Claudio', keywords: 'prolia'}
  ]);

  useEffect(() => {
    axios.get(`${API}/listas`).then(res => {
      const listas = res.data.listas || [];
      if (listas.length > 0) {
        setMinhasListas(listas.map(l => ({ id: l.id, name: l.nome, keywords: (l.medicamentos || []).join(', ') })));
        setRadaresAtalho(listas.slice(0, 5).map(l => ({ id: l.id, name: l.nome, keywords: (l.medicamentos || []).join(', ') })));
      }
    }).catch(() => {});

    axios.get(`${API}/radares`).then(res => {
      const radares = res.data.radares || [];
      if (radares.length > 0) {
        setMeusRadares(radares.map(r => ({ id: r.id, name: r.nome, email: r.email, freq: r.frequencia, terms: r.termos })));
      }
    }).catch(() => {});
  }, []);

  return {
    minhasListas, setMinhasListas,
    meusRadares, setMeusRadares,
    radaresAtalho,
    API,
  };
}
