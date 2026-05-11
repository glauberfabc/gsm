import React, { useState, useEffect, useRef } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import './App.css';
import axios from 'axios';

// Layout
import Header from './components/layout/Header';

// Pages
import SearchPage from './pages/SearchPage';
import HealthDashboard from './pages/HealthDashboard';
import MetricsDashboard from './pages/MetricsDashboard';
import NotificacoesPage from './pages/NotificacoesPage';
import MonitoringDashboard from './pages/MonitoringDashboard';
import RadarFarmaceuticoPage from './pages/RadarFarmaceuticoPage';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [stats, setStats] = useState(null);
  // Ref para comunicar com SearchPage
  const searchPageRef = useRef(null);

  useEffect(() => {
    const loadStats = async () => {
      try {
        const response = await axios.get(`${API}/stats`);
        setStats(response.data);
      } catch (error) {
        console.error('Erro ao buscar estatísticas:', error);
      }
    };
    loadStats();
  }, []);

  const handleShowListas = () => {
    // Trigger listas modal via ref
    if (searchPageRef.current) {
      searchPageRef.current.showListas();
    }
  };

  return (
    <Router>
      <div className="min-h-screen bg-gradient-to-br from-gray-50 to-blue-50">
        <Header 
          stats={stats} 
          onShowListas={handleShowListas}
        />
        
        <Routes>
          <Route 
            path="/" 
            element={<SearchPage ref={searchPageRef} />} 
          />
          <Route 
            path="/dashboard" 
            element={<HealthDashboard />} 
          />
          <Route 
            path="/metrics" 
            element={<MetricsDashboard />} 
          />
          <Route 
            path="/notificacoes" 
            element={<NotificacoesPage />} 
          />
          <Route 
            path="/monitoring" 
            element={<MonitoringDashboard />} 
          />
          <Route 
            path="/radar-farma" 
            element={<RadarFarmaceuticoPage />} 
          />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
