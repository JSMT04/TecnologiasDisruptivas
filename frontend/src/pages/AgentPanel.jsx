import { useState, useEffect, useCallback } from 'react';

const API_BASE = 'http://localhost:8000';

/* ── Relative time formatter ── */
function timeAgo(timestamp) {
  if (!timestamp) return '—';
  const now = Date.now();
  const then = new Date(timestamp).getTime();
  const diffSec = Math.floor((now - then) / 1000);
  if (diffSec < 60) return `hace ${diffSec}s`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `hace ${diffMin} min`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `hace ${diffHr}h`;
  return new Date(timestamp).toLocaleDateString('es-ES');
}

/* ── Status badge component ── */
function StatusBadge({ status }) {
  const styles = {
    Idle:    'bg-gray-500/20 text-gray-400 border-gray-500/30',
    Working: 'bg-amber-500/20 text-amber-400 border-amber-500/30 agent-working',
    Error:   'bg-red-500/20 text-red-400 border-red-500/30',
    Success: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    Pending: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  };
  const labels = {
    Idle:    'Inactivo',
    Working: 'Trabajando',
    Error:   'Error',
    Success: 'Éxito',
    Pending: 'Pendiente',
  };
  return (
    <span className={`inline-flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-lg border ${styles[status] || styles.Idle}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${
        status === 'Working' ? 'bg-amber-400 animate-pulse' :
        status === 'Error'   ? 'bg-red-400' :
        status === 'Success' ? 'bg-emerald-400' :
        status === 'Pending' ? 'bg-yellow-400' :
        'bg-gray-400'
      }`} />
      {labels[status] || status}
    </span>
  );
}

/* ── Agent Status Card ── */
function AgentCard({ name, emoji, status, lastAction, lastActionTime, totalActions, onTrigger, canTrigger }) {
  return (
    <div className="glass p-6 flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-primary/20 to-accent/20 flex items-center justify-center text-2xl">
            {emoji}
          </div>
          <div>
            <h3 className="text-base font-bold text-white">{name}</h3>
            <StatusBadge status={status} />
          </div>
        </div>
        <div className="text-right">
          <span className="block text-2xl font-extrabold text-white">{totalActions ?? 0}</span>
          <span className="text-[10px] text-gray-500 uppercase tracking-wider">Acciones</span>
        </div>
      </div>

      {/* Last action */}
      <div className="bg-white/[0.03] rounded-xl p-3 border border-white/5">
        <p className="text-xs text-gray-500 mb-1">Última acción</p>
        <p className="text-sm text-gray-300 leading-relaxed">{lastAction || 'Sin actividad registrada'}</p>
        {lastActionTime && (
          <p className="text-[10px] text-gray-600 mt-1">{timeAgo(lastActionTime)}</p>
        )}
      </div>

      {/* Trigger button */}
      {canTrigger ? (
        <button
          onClick={onTrigger}
          className="w-full py-2.5 rounded-xl bg-primary/20 border border-primary/30 text-primary text-sm font-semibold hover:bg-primary/30 transition-all flex items-center justify-center gap-2"
        >
          ⚡ Ejecutar Tarea
        </button>
      ) : (
        <div className="w-full py-2.5 rounded-xl bg-white/[0.03] border border-white/5 text-gray-600 text-sm text-center cursor-not-allowed">
          Activación automática (Triage)
        </div>
      )}
    </div>
  );
}

/* ── Activity Log Entry ── */
function LogEntry({ entry }) {
  const agentEmojis = { Organizador: '🧠', Ejecutor: '⚡' };
  const emoji = agentEmojis[entry.agent] || '🤖';

  return (
    <div className="flex items-start gap-3 py-3 border-b border-white/5 last:border-0">
      <span className="text-lg mt-0.5">{emoji}</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-xs font-semibold text-white">{entry.agent || 'Agente'}</span>
          <StatusBadge status={entry.status || 'Success'} />
        </div>
        <p className="text-sm text-gray-400 leading-relaxed truncate">{entry.description || entry.action}</p>
      </div>
      <span className="text-[10px] text-gray-600 whitespace-nowrap mt-1">{timeAgo(entry.timestamp)}</span>
    </div>
  );
}

/* ── Main Agent Panel ── */
export default function AgentPanel({ token, sessionId }) {
  const [healthOk, setHealthOk] = useState(null);
  const [agents, setAgents] = useState({
    organizador: { status: 'Idle', lastAction: null, lastActionTime: null, totalActions: 0 },
    ejecutor:    { status: 'Idle', lastAction: null, lastActionTime: null, totalActions: 0 },
  });
  const [log, setLog] = useState([]);
  const [isLogLoading, setIsLogLoading] = useState(true);
  const [showExecuteInput, setShowExecuteInput] = useState(false);
  const [executePageId, setExecutePageId] = useState('');
  const [executeLoading, setExecuteLoading] = useState(false);

  /* ── Health check ── */
  const checkHealth = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/notion/health`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setHealthOk(res.ok);
    } catch {
      setHealthOk(false);
    }
  }, [token]);

  /* ── Fetch activity log + agent statuses ── */
  const fetchLog = useCallback(async () => {
    try {
      // Fetch log entries and agent status in parallel
      const [logRes, statusRes] = await Promise.all([
        fetch(`${API_BASE}/api/v1/notion/agent-log?limit=20`, {
          headers: { Authorization: `Bearer ${token}` },
        }),
        fetch(`${API_BASE}/api/v1/notion/agents-status`, {
          headers: { Authorization: `Bearer ${token}` },
        }),
      ]);

      // Parse log entries
      let entries = [];
      if (logRes.ok) {
        const logData = await logRes.json();
        entries = Array.isArray(logData) ? logData : logData.logs || [];
        setLog(entries);
      }

      // Parse real-time agent status from AgentManager
      let liveAgents = {};
      if (statusRes.ok) {
        const statusData = await statusRes.json();
        liveAgents = statusData.agents || {};
      }

      // Derive per-agent info by combining live status + log history
      const orgEntries = entries.filter(e => e.agent === 'Organizador');
      const ejEntries = entries.filter(e => e.agent === 'Ejecutor');

      const mapStatus = (liveState) => {
        if (!liveState) return 'Idle';
        if (liveState === 'working') return 'Working';
        if (liveState === 'error') return 'Error';
        return 'Idle';
      };

      const liveOrg = liveAgents['Organizador'] || {};
      const liveEj = liveAgents['Ejecutor'] || {};

      setAgents({
        organizador: {
          status: orgEntries.length > 0 && orgEntries[0].status === 'Error'
            ? 'Error'
            : mapStatus(liveOrg.state),
          lastAction: liveOrg.last_action || (orgEntries[0]?.description || orgEntries[0]?.action) || null,
          lastActionTime: liveOrg.last_action_at || orgEntries[0]?.timestamp || null,
          totalActions: orgEntries.length,
        },
        ejecutor: {
          status: ejEntries.length > 0 && ejEntries[0].status === 'Error'
            ? 'Error'
            : mapStatus(liveEj.state),
          lastAction: liveEj.last_action || (ejEntries[0]?.description || ejEntries[0]?.action) || null,
          lastActionTime: liveEj.last_action_at || ejEntries[0]?.timestamp || null,
          totalActions: ejEntries.length,
        },
      });
    } catch {
      // silently fail for log
    } finally {
      setIsLogLoading(false);
    }
  }, [token]);

  /* ── Mount + intervals ── */
  useEffect(() => {
    checkHealth();
    fetchLog();
    const healthInterval = setInterval(checkHealth, 30000);
    const logInterval = setInterval(fetchLog, 10000);
    return () => {
      clearInterval(healthInterval);
      clearInterval(logInterval);
    };
  }, [checkHealth, fetchLog]);

  /* ── Manual execute trigger ── */
  const handleExecute = async () => {
    if (!executePageId.trim()) return;
    setExecuteLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/notion/tasks/${executePageId.trim()}/execute`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error('Error al ejecutar');
      setShowExecuteInput(false);
      setExecutePageId('');
      await fetchLog();
    } catch (err) {
      alert(`Error: ${err.message}`);
    } finally {
      setExecuteLoading(false);
    }
  };

  return (
    <div className="w-full max-w-5xl mx-auto px-4 py-6 pb-24 fade-in-up">
      {/* ── Header ── */}
      <div className="glass p-5 mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl sm:text-2xl font-extrabold text-white flex items-center gap-2">
              🤖 <span className="gradient-text">Panel de Agentes</span>
            </h1>
            <p className="text-xs text-gray-500 mt-0.5">
              Monitoreo y control del sistema multi-agente
            </p>
          </div>

          {/* Notion connection status */}
          <div className="flex items-center gap-2">
            <span className={`w-2.5 h-2.5 rounded-full ${
              healthOk === null ? 'bg-gray-500 animate-pulse' :
              healthOk ? 'bg-emerald-400 status-pulse' : 'bg-red-500'
            }`} />
            <span className="text-xs text-gray-400">
              {healthOk === null ? 'Verificando...' : healthOk ? 'Notion Conectado' : 'Notion Desconectado'}
            </span>
          </div>
        </div>
      </div>

      {/* ── Main content grid ── */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Agent cards - left side (2 cols) */}
        <div className="lg:col-span-2 space-y-4">
          <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wider px-1 mb-2">
            Estado de Agentes
          </h2>

          <AgentCard
            name="Organizador"
            emoji="🧠"
            status={agents.organizador.status}
            lastAction={agents.organizador.lastAction}
            lastActionTime={agents.organizador.lastActionTime}
            totalActions={agents.organizador.totalActions}
            canTrigger={false}
          />

          <AgentCard
            name="Ejecutor"
            emoji="⚡"
            status={agents.ejecutor.status}
            lastAction={agents.ejecutor.lastAction}
            lastActionTime={agents.ejecutor.lastActionTime}
            totalActions={agents.ejecutor.totalActions}
            canTrigger={true}
            onTrigger={() => setShowExecuteInput(!showExecuteInput)}
          />

          {/* Execute input modal */}
          {showExecuteInput && (
            <div className="glass p-4 border-primary/20 card-slide-in">
              <label className="block text-xs text-gray-400 mb-2">
                Page ID de la tarea a ejecutar:
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={executePageId}
                  onChange={e => setExecutePageId(e.target.value)}
                  placeholder="Pegar Page ID aquí..."
                  className="flex-1 bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-primary/40 transition-colors"
                />
                <button
                  onClick={handleExecute}
                  disabled={executeLoading || !executePageId.trim()}
                  className="px-4 py-2 rounded-xl bg-primary/20 border border-primary/30 text-primary text-sm font-semibold hover:bg-primary/30 transition-all disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1.5"
                >
                  {executeLoading ? (
                    <span className="w-4 h-4 rounded-full border-2 border-primary/30 border-t-primary animate-spin" />
                  ) : (
                    <>⚡ Ejecutar</>
                  )}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Activity log - right side (3 cols) */}
        <div className="lg:col-span-3">
          <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wider px-1 mb-2">
            Registro de Actividad
          </h2>

          <div className="glass p-5 max-h-[600px] overflow-y-auto">
            {isLogLoading ? (
              <div className="space-y-4">
                {[1, 2, 3, 4, 5].map(i => (
                  <div key={i} className="flex items-start gap-3 py-3 animate-pulse">
                    <div className="w-8 h-8 bg-white/10 rounded-full" />
                    <div className="flex-1 space-y-2">
                      <div className="h-3 bg-white/10 rounded w-1/3" />
                      <div className="h-2 bg-white/10 rounded w-2/3" />
                    </div>
                  </div>
                ))}
              </div>
            ) : log.length === 0 ? (
              <div className="text-center py-12">
                <span className="text-4xl block mb-3">📭</span>
                <p className="text-sm text-gray-500">Sin actividad registrada todavía</p>
                <p className="text-xs text-gray-600 mt-1">Las acciones de los agentes aparecerán aquí</p>
              </div>
            ) : (
              <div>
                {log.map((entry, idx) => (
                  <LogEntry key={entry.id || idx} entry={entry} />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
