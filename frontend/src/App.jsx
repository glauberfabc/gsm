import React, { useState, useEffect, lazy, Suspense } from 'react';
import { BrowserRouter } from 'react-router-dom';
import { Toaster } from 'sonner';
import { Loader2 } from 'lucide-react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Login } from './components/Login';

import ErrorBoundary from './components/common/ErrorBoundary';
import Header from './components/layout/Header';
import { Footer } from './components/layout/Footer';
import { SearchTab } from './components/tabs/SearchTab';
import { EsclarecimentoModal } from './components/modals/EsclarecimentoModal';

// Lazy-loaded tabs (reduz bundle inicial)
const ListasTab = lazy(() => import('./components/tabs/ListasTab').then(m => ({ default: m.ListasTab })));
const RadaresTab = lazy(() => import('./components/tabs/RadaresTab').then(m => ({ default: m.RadaresTab })));
const DamaTab = lazy(() => import('./components/tabs/DamaTab').then(m => ({ default: m.DamaTab })));
const PrecosTab = lazy(() => import('./components/tabs/PrecosTab').then(m => ({ default: m.PrecosTab })));
const AnvisaTab = lazy(() => import('./components/tabs/AnvisaTab').then(m => ({ default: m.AnvisaTab })));
const SettingsTab = lazy(() => import('./components/tabs/SettingsTab').then(m => ({ default: m.SettingsTab })));
const RadarLmrTab = lazy(() => import('./components/tabs/RadarLmrTab').then(m => ({ default: m.RadarLmrTab })));
const RadarFarmaceuticoTab = lazy(() => import('./components/tabs/RadarFarmaceuticoTab').then(m => ({ default: m.RadarFarmaceuticoTab })));
const UsersTab = lazy(() => import('./components/tabs/UsersTab').then(m => ({ default: m.UsersTab })));

import { useSearch } from './hooks/useSearch';
import { usePrecos } from './hooks/usePrecos';
import { useAnvisa } from './hooks/useAnvisa';
import { useDama } from './hooks/useDama';
import { useCompanies } from './hooks/useCompanies';
import { useEsclarecimento } from './hooks/useEsclarecimento';
import { useListasRadares } from './hooks/useListasRadares';
import { useDamaChecklist } from './hooks/useDamaChecklist';
import { useRadarLmr } from './hooks/useRadarLmr';
import { useRadarFarmaceutico } from './hooks/useRadarFarmaceutico';
import { useNotificacoes } from './hooks/useNotificacoes';

// Fallback estavel (fora do render para evitar recreacao)
const LazyFallback = (
  <div className="py-20 text-center">
    <Loader2 className="animate-spin mx-auto text-blue-500 mb-4" size={48}/>
    <p className="text-slate-400 font-bold uppercase tracking-wider text-sm">Carregando modulo...</p>
  </div>
);

function AppContent() {
  const [activeTab, setActiveTab] = useState('search');
  const { user, logout } = useAuth();

  const search = useSearch();
  const precos = usePrecos();
  const anvisa = useAnvisa();
  const companiesHook = useCompanies();
  const dama = useDama(companiesHook.companies);
  const esclarecimento = useEsclarecimento();
  const listasRadares = useListasRadares();
  const damaChecklist = useDamaChecklist();
  const radarLmr = useRadarLmr();
  const radarFarma = useRadarFarmaceutico();
  const notificacoesHook = useNotificacoes();
  const { carregarAlertaPorId } = radarLmr;

  // Deep-link: ?alerta=<ID> abre Radar LMR com analise automatica
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const alertaId = params.get('alerta');
    if (alertaId) {
      setActiveTab('radar-lmr');
      carregarAlertaPorId(alertaId);
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, [carregarAlertaPorId]);

  const handleSearchFromRadar = (id, keywords) => {
    search.handleSelectRadar(id, keywords);
    setActiveTab('search');
  };

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col">
      <Toaster position="top-right" richColors expand />

      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onAnvisaLoad={anvisa.carregarAnvisa}
        notificacoes={notificacoesHook}
        user={user}
        onLogout={logout}
      />

      <main className="flex-grow max-w-7xl mx-auto w-full py-8 px-6">
        {/* Pesquisa - carregado eagerly (tab default) */}
        <div style={{ display: activeTab === 'search' ? 'block' : 'none' }}>
          <SearchTab
            {...search}
            radaresAtalho={listasRadares.radaresAtalho}
          />
        </div>

        {/* Cada Suspense isola seu proprio boundary - evita insertBefore */}
        {activeTab === 'lists' && (
          <Suspense fallback={LazyFallback}>
            <ListasTab
              minhasListas={listasRadares.minhasListas}
              setMinhasListas={listasRadares.setMinhasListas}
              onSearch={handleSearchFromRadar}
            />
          </Suspense>
        )}

        {activeTab === 'radar' && (
          <Suspense fallback={LazyFallback}>
            <RadaresTab
              meusRadares={listasRadares.meusRadares}
              setMeusRadares={listasRadares.setMeusRadares}
              onSearch={handleSearchFromRadar}
            />
          </Suspense>
        )}

        {activeTab === 'dama' && (
          <Suspense fallback={LazyFallback}>
            <DamaTab
              {...dama}
              companies={companiesHook.companies}
              showEmpresaModal={companiesHook.showEmpresaModal}
              setShowEmpresaModal={companiesHook.setShowEmpresaModal}
              editingCompanyId={companiesHook.editingCompanyId}
              setEditingCompanyId={companiesHook.setEditingCompanyId}
              editCompanyForm={companiesHook.editCompanyForm}
              setEditCompanyForm={companiesHook.setEditCompanyForm}
              saveCompany={companiesHook.saveCompany}
            />
          </Suspense>
        )}

        {activeTab === 'precos' && (
          <Suspense fallback={LazyFallback}>
            <div data-testid="precos-tab">
              <PrecosTab {...precos} />
            </div>
          </Suspense>
        )}

        {activeTab === 'anvisa' && (
          <Suspense fallback={LazyFallback}>
            <div data-testid="anvisa-dashboard">
              <AnvisaTab
                {...anvisa}
                companies={companiesHook.companies}
                openEsclarecimento={(alerta, med, comps) => esclarecimento.openEsclarecimento(alerta, med, comps)}
                setSearchTerm={search.setSearchTerm}
                setActiveTab={setActiveTab}
                executarBusca={search.executarBusca}
                damaChecklist={damaChecklist}
              />
            </div>
          </Suspense>
        )}

        {activeTab === 'radar-lmr' && (
          <Suspense fallback={LazyFallback}>
            <div data-testid="radar-lmr-dashboard">
              <RadarLmrTab {...radarLmr} />
            </div>
          </Suspense>
        )}

        {activeTab === 'radar-farma' && (
          <Suspense fallback={LazyFallback}>
            <div data-testid="radar-farma-dashboard">
              <RadarFarmaceuticoTab {...radarFarma} />
            </div>
          </Suspense>
        )}

        {activeTab === 'settings' && (
          <Suspense fallback={LazyFallback}>
            <SettingsTab
              companies={companiesHook.companies}
              editingCompanyId={companiesHook.editingCompanyId}
              editCompanyForm={companiesHook.editCompanyForm}
              setEditCompanyForm={companiesHook.setEditCompanyForm}
              startEditCompany={companiesHook.startEditCompany}
              cancelEditCompany={companiesHook.cancelEditCompany}
              saveCompany={companiesHook.saveCompany}
            />
          </Suspense>
        )}

        {activeTab === 'usuarios' && (
          <Suspense fallback={LazyFallback}>
            <UsersTab />
          </Suspense>
        )}

        {/* Modal Esclarecimento */}
        <EsclarecimentoModal
          {...esclarecimento}
          companies={companiesHook.companies}
        />
      </main>

      <Footer />
    </div>
  );
}

function AuthGate() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-100">
        <Loader2 className="animate-spin text-blue-500" size={48} />
      </div>
    );
  }

  if (!user) {
    return <Login />;
  }

  return <AppContent />;
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <AuthProvider>
          <AuthGate />
        </AuthProvider>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
