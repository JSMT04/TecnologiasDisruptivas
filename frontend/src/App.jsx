import { useState, useEffect } from 'react';
import Triage from './pages/Triage';
import RoadMap from './pages/RoadMap';
import Kanban from './pages/Kanban';
import AgentPanel from './pages/AgentPanel';

/* ── Decorative floating orb ── */
function FloatingOrb({ size, color, top, left, delay }) {
  return (
    <div
      className="absolute rounded-full blur-3xl opacity-20 pointer-events-none float animate-pulse"
      style={{
        width: size,
        height: size,
        background: color,
        top,
        left,
        animationDelay: delay,
      }}
    />
  );
}

/* ── Feature card with glassmorphism ── */
function FeatureCard({ icon, title, description }) {
  return (
    <div
      className="glass p-8 flex flex-col items-center text-center 
        transition-all duration-500 ease-out
        hover:scale-105 hover:border-primary/30 hover:shadow-lg hover:shadow-primary/10
        cursor-default"
    >
      <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary/20 to-accent/20 flex items-center justify-center mb-5 text-3xl">
        {icon}
      </div>
      <h3 className="text-lg font-semibold text-white mb-2">{title}</h3>
      <p className="text-sm text-gray-400 leading-relaxed">{description}</p>
    </div>
  );
}

export default function App() {
  // --- Persisted States via localStorage ---
  const [currentPage, setCurrentPage] = useState(() => localStorage.getItem('fs_page') || 'landing');
  const [sessionId, setSessionId] = useState(() => localStorage.getItem('fs_session_id') || '');
  const [token, setToken] = useState(() => localStorage.getItem('fs_token') || '');
  const [triageData, setTriageData] = useState(() => {
    const data = localStorage.getItem('fs_triage_data');
    return data ? JSON.parse(data) : null;
  });
  const [activeTasks, setActiveTasks] = useState(() => {
    const data = localStorage.getItem('fs_active_tasks');
    return data ? JSON.parse(data) : null;
  });

  const [isLoadingSession, setIsLoadingSession] = useState(false);
  const [sessionError, setSessionError] = useState(null);

  // Sync state changes with localStorage for total reload-resilience
  useEffect(() => {
    localStorage.setItem('fs_page', currentPage);
  }, [currentPage]);

  useEffect(() => {
    localStorage.setItem('fs_session_id', sessionId);
  }, [sessionId]);

  useEffect(() => {
    localStorage.setItem('fs_token', token);
  }, [token]);

  useEffect(() => {
    if (triageData) {
      localStorage.setItem('fs_triage_data', JSON.stringify(triageData));
    } else {
      localStorage.removeItem('fs_triage_data');
    }
  }, [triageData]);

  useEffect(() => {
    if (activeTasks) {
      localStorage.setItem('fs_active_tasks', JSON.stringify(activeTasks));
    } else {
      localStorage.removeItem('fs_active_tasks');
    }
  }, [activeTasks]);

  // --- Handlers ---
  const handleStartNewSession = async () => {
    setIsLoadingSession(true);
    setSessionError(null);

    try {
      const response = await fetch('http://localhost:8000/api/v1/auth/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!response.ok) {
        throw new Error('Fallo al conectar con el servidor para iniciar sesión.');
      }

      const data = await response.json();
      setSessionId(data.session_id);
      setToken(data.token);
      
      // Clear old cached tasks for clean session
      setTriageData(null);
      setActiveTasks(null);

      // Move to Triage capture page
      setCurrentPage('triage');
    } catch (err) {
      setSessionError(err.message || 'Error de red.');
    } finally {
      setIsLoadingSession(false);
    }
  };

  const handleTriageComplete = (data) => {
    setTriageData(data);
    setCurrentPage('roadmap');
  };

  const handleStartSessionPlan = (finalTasks) => {
    setActiveTasks(finalTasks);
    setCurrentPage('kanban');
  };

  const handleResetSessionFlow = () => {
    setTriageData(null);
    setCurrentPage('triage');
  };

  const handleFullReset = () => {
    localStorage.clear();
    setCurrentPage('landing');
    setSessionId('');
    setToken('');
    setTriageData(null);
    setActiveTasks(null);
  };

  // --- Render Views ---
  const renderView = () => {
    switch (currentPage) {
      case 'triage':
        return (
          <Triage
            session_id={sessionId}
            token={token}
            onTriageComplete={handleTriageComplete}
            onBackToLanding={() => setCurrentPage('landing')}
            onSessionExpired={handleFullReset}
          />
        );

      case 'roadmap':
        return (
          <RoadMap
            session_id={sessionId}
            token={token}
            triageData={triageData}
            onStartSession={handleStartSessionPlan}
            onResetSession={handleResetSessionFlow}
            onSessionExpired={handleFullReset}
          />
        );

      case 'kanban':
        return (
          <Kanban
            token={token}
            sessionId={sessionId}
            onBack={() => setCurrentPage('roadmap')}
            onSessionExpired={handleFullReset}
          />
        );

      case 'agents':
        return (
          <AgentPanel
            token={token}
            sessionId={sessionId}
            onSessionExpired={handleFullReset}
          />
        );

      case 'landing':
      default:
        return (
          <div className="relative z-10 flex flex-col items-center justify-center min-h-screen px-4 py-16 w-full max-w-4xl">
            {/* Top Badge */}
            <div className="fade-in-up mb-8">
              <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-medium tracking-wide bg-primary/10 text-primary border border-primary/20">
                <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
                Fase Alpha · Notion Multi-Agent
              </span>
            </div>

            {/* Hero title */}
            <h1 className="fade-in-up text-5xl sm:text-6xl md:text-7xl font-extrabold tracking-tight text-center mb-4">
              <span className="gradient-text">FlowStep</span>
              <span className="text-white"> AI</span>
            </h1>

            {/* Tagline */}
            <p className="fade-in-up-delay-1 text-lg sm:text-xl text-gray-400 text-center max-w-2xl mb-12 leading-relaxed">
              Tu agente de productividad personal con{' '}
              <span className="text-accent font-medium">organización inteligente con agentes IA + Notion</span>
            </p>

            {/* Central Splash Card */}
            <div className="fade-in-up-delay-2 w-full max-w-xl glass p-8 sm:p-10 text-center relative overflow-hidden pulse-glow mb-12">
              <div className="absolute -top-10 -right-10 w-24 h-24 bg-primary/30 rounded-full blur-2xl pointer-events-none" />
              
              <h2 className="text-xl font-bold text-white mb-3">Organiza tu día sin esfuerzo</h2>
              <p className="text-sm text-gray-400 leading-relaxed mb-8 max-w-md mx-auto">
                Crea una sesión de trabajo de un solo clic. Generamos tu plan, priorizamos tus pendientes y auditamos tus avances reales.
              </p>

              {sessionError && (
                <div className="p-4 rounded-xl bg-danger/10 border border-danger/20 text-danger text-sm flex items-center justify-center gap-2 mb-6">
                  <span>⚠️</span>
                  <span>{sessionError}</span>
                </div>
              )}

              <button
                onClick={handleStartNewSession}
                disabled={isLoadingSession}
                className="relative inline-flex items-center justify-center gap-3 px-12 py-4.5 
                  rounded-xl font-bold text-base overflow-hidden
                  bg-gradient-to-r from-primary to-accent text-white
                  shadow-lg shadow-primary/35
                  transition-all duration-300
                  hover:scale-105 hover:shadow-primary/50 active:scale-95
                  disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoadingSession ? (
                  <>
                    <span className="w-5 h-5 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                    <span>Iniciando Sesión...</span>
                  </>
                ) : (
                  <>
                    <span>Iniciar Nueva Sesión</span>
                    <span>⚡</span>
                  </>
                )}
              </button>
            </div>

            {/* Features Row */}
            <div className="fade-in-up-delay-3 w-full grid grid-cols-1 md:grid-cols-3 gap-6">
              <FeatureCard
                icon="🧠"
                title="Agentes IA"
                description="Sistema multi-agente que organiza y ejecuta tus tareas de forma autónoma."
              />
              <FeatureCard
                icon="📋"
                title="Kanban en Notion"
                description="Tablero visual sincronizado en tiempo real con tu workspace de Notion."
              />
              <FeatureCard
                icon="📊"
                title="Trazabilidad Total"
                description="Registro completo de actividad de agentes y progreso de tareas."
              />
            </div>
          </div>
        );
    }
  };

  return (
    <div className="relative min-h-screen animated-gradient overflow-x-hidden">
      {/* ── Floating background orbs ── */}
      <FloatingOrb size="500px" color="#6366f1" top="-10%" left="-5%" delay="0s" />
      <FloatingOrb size="450px" color="#22d3ee" top="50%" left="70%" delay="2s" />
      <FloatingOrb size="300px" color="#a78bfa" top="20%" left="45%" delay="4s" />

      {/* Noise background texture overlay */}
      <div
        className="absolute inset-0 opacity-[0.03] pointer-events-none"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='1'/%3E%3C/svg%3E")`,
          backgroundRepeat: 'repeat',
        }}
      />

      {/* Main Page Content Wrapper */}
      <div className="relative z-10 flex flex-col items-center justify-center min-h-screen">
        {renderView()}

        {/* Subtle footer */}
        <footer className={`py-12 text-center text-xs text-gray-600 w-full mt-auto ${sessionId && currentPage !== 'landing' ? 'pb-24' : ''}`}>
          <p>
            Hecho con <span className="text-danger">♥</span> por{' '}
            <span className="text-gray-400 font-medium">FlowStep AI</span>
            {' · '}Productividad sin fricciones
          </p>
        </footer>
      </div>

      {/* ── Floating Navigation Bar ── */}
      {sessionId && currentPage !== 'landing' && (
        <nav className="nav-bar">
          <button
            onClick={() => setCurrentPage('triage')}
            className={`nav-tab ${currentPage === 'triage' ? 'active' : ''}`}
          >
            📝 Triage
          </button>
          <button
            onClick={() => setCurrentPage('kanban')}
            className={`nav-tab ${currentPage === 'kanban' ? 'active' : ''}`}
          >
            📋 Kanban
          </button>
          <button
            onClick={() => setCurrentPage('agents')}
            className={`nav-tab ${currentPage === 'agents' ? 'active' : ''}`}
          >
            🤖 Agentes
          </button>
        </nav>
      )}
    </div>
  );
}
