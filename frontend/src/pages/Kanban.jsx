import { useState, useEffect, useCallback } from 'react';

const API_BASE = 'http://localhost:8000';

/* ── Column definitions ── */
const COLUMNS = [
  { key: 'Backlog',       label: 'Backlog',        emoji: '📥', color: 'border-gray-500',    bg: 'bg-gray-500/10',  badge: 'bg-gray-500/20 text-gray-300' },
  { key: 'To Do',         label: 'To Do',          emoji: '📝', color: 'border-primary',     bg: 'bg-primary/10',   badge: 'bg-primary/20 text-primary' },
  { key: 'In Progress',   label: 'In Progress',    emoji: '🔄', color: 'border-amber-400',   bg: 'bg-amber-400/10', badge: 'bg-amber-400/20 text-amber-300' },
  { key: 'En Revisión',   label: 'En Revisión',    emoji: '🔍', color: 'border-purple-400',  bg: 'bg-purple-400/10',badge: 'bg-purple-400/20 text-purple-300' },
  { key: 'Done',          label: 'Done',           emoji: '✅', color: 'border-emerald-400', bg: 'bg-emerald-400/10',badge: 'bg-emerald-400/20 text-emerald-300' },
];

const COLUMN_ORDER = COLUMNS.map(c => c.key);

/* ── Priority badge colors ── */
const PRIORITY_STYLES = {
  Alta:  'bg-red-500/20 text-red-400 border-red-500/30',
  Media: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  Baja:  'bg-blue-500/20 text-blue-400 border-blue-500/30',
};

/* ── Type emoji map ── */
const TYPE_EMOJI = {
  'Código':        '🔧',
  'Archivo':       '📄',
  'Web':           '🌐',
  'Comunicación':  '💬',
  'Otro':          '📌',
};

/* ── Agent display ── */
const AGENT_DISPLAY = {
  'Organizador': '🧠 Organizador',
  'Ejecutor':    '⚡ Ejecutor',
  'Usuario':     '👤 Usuario',
};

/* ── Task Card Component ── */
function TaskCard({ task, onMove, onExecute, onComplete, onVerify, verificationResult, index, isLoading }) {
  const priorityClass = PRIORITY_STYLES[task.priority] || PRIORITY_STYLES.Media;
  const typeEmoji = TYPE_EMOJI[task.type] || '📌';
  const agentLabel = AGENT_DISPLAY[task.agent] || `👤 ${task.agent || 'Sin asignar'}`;

  const colIdx = COLUMN_ORDER.indexOf(task.status);
  const canMoveLeft = colIdx > 0;
  const canExecute = task.status === 'To Do' || task.status === 'In Progress';
  
  // File verification requirement (Phase C)
  const hasExpectedPath = !!task.expected_path;
  const isVerified = task.verificado || verificationResult?.verificado;
  
  // Block moving right to "Done" if task needs verification but isn't verified
  const nextColIsDone = colIdx + 1 === COLUMN_ORDER.indexOf('Done');
  const blockedByVerification = nextColIsDone && hasExpectedPath && !isVerified;
  const canMoveRight = colIdx < COLUMN_ORDER.length - 1 && !blockedByVerification;
  
  // Disable Complete if expected_path is present but not verified
  const canComplete = (task.status === 'In Progress' || task.status === 'En Revisión') && (!hasExpectedPath || isVerified);

  return (
    <div
      className="kanban-card card-slide-in"
      style={{ animationDelay: `${index * 0.06}s` }}
    >
      {/* Task name */}
      <h4 className="text-sm font-semibold text-white mb-2.5 leading-snug">{task.name || task.title}</h4>

      {/* Badges row */}
      <div className="flex flex-wrap gap-1.5 mb-3">
        {/* Priority */}
        {task.priority && (
          <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md border ${priorityClass}`}>
            {task.priority}
          </span>
        )}
        {/* Effort */}
        {task.effort && (
          <span className="text-[10px] font-medium px-2 py-0.5 rounded-md bg-white/10 text-gray-300 border border-white/5">
            ⏱ {task.effort}
          </span>
        )}
        {/* Type */}
        <span className="text-[10px] font-medium px-2 py-0.5 rounded-md bg-white/10 text-gray-300 border border-white/5">
          {typeEmoji} {task.type || 'Otro'}
        </span>
      </div>

      {/* Agent */}
      <div className="text-[11px] text-gray-500 mb-3">{agentLabel}</div>

      {/* File verification panel (Phase C) */}
      {hasExpectedPath && (
        <div className="mt-2 mb-3 p-2 bg-white/5 rounded-xl border border-white/5 space-y-1.5">
          <div className="flex items-center justify-between gap-1 text-[11px] text-gray-400">
            <span className="truncate flex-1" title={task.expected_path}>
              📁 {task.expected_path}
            </span>
            <button
              onClick={() => onVerify(task.page_id)}
              disabled={isLoading}
              className="px-1.5 py-0.5 rounded bg-primary/20 hover:bg-primary/30 text-primary text-[10px] font-semibold transition-all shrink-0 disabled:opacity-50 disabled:cursor-not-allowed"
              title="Verificar archivo en sistema local"
            >
              {isLoading ? '⏳...' : '🔍 Verificar'}
            </button>
          </div>
          {verificationResult && (
            <div className={`text-[10px] font-medium leading-relaxed p-1.5 rounded-lg ${
              verificationResult.verificado
                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/10'
                : 'bg-red-500/10 text-red-400 border border-red-500/10'
            }`}>
              {verificationResult.verificado ? '✅' : '❌'} {verificationResult.detalle}
            </div>
          )}
        </div>
      )}

      {/* Action buttons */}
      <div className="flex items-center gap-1.5 pt-2 border-t border-white/5">
        {canMoveLeft && (
          <button
            onClick={() => onMove(task.page_id, COLUMN_ORDER[colIdx - 1])}
            className="p-1.5 rounded-lg hover:bg-white/10 text-gray-400 hover:text-white transition-colors text-xs"
            title="Mover a la izquierda"
          >
            ←
          </button>
        )}
        {canMoveRight && (
          <button
            onClick={() => onMove(task.page_id, COLUMN_ORDER[colIdx + 1])}
            className="p-1.5 rounded-lg hover:bg-white/10 text-gray-400 hover:text-white transition-colors text-xs"
            title="Mover a la derecha"
          >
            →
          </button>
        )}
        {blockedByVerification && (
          <button
            disabled
            className="p-1.5 rounded-lg text-gray-600 cursor-not-allowed text-xs"
            title="🔒 Verifica el archivo antes de mover a Done"
          >
            →🔒
          </button>
        )}
        <div className="flex-1" />
        {canExecute && (
          <button
            onClick={() => onExecute(task.page_id)}
            className="p-1.5 rounded-lg hover:bg-amber-500/20 text-amber-400 hover:text-amber-300 transition-colors text-xs font-medium"
            title="Ejecutar tarea"
          >
            ⚡
          </button>
        )}
        {canComplete && (
          <button
            onClick={() => onComplete(task.page_id)}
            className="p-1.5 rounded-lg hover:bg-emerald-500/20 text-emerald-400 hover:text-emerald-300 transition-colors text-xs font-medium"
            title="Completar tarea"
          >
            ✅
          </button>
        )}
      </div>
    </div>
  );
}

/* ── Main Kanban Board ── */
export default function Kanban({ token, sessionId, onBack, onSessionExpired }) {
  const [tasks, setTasks] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState(null); // page_id of task being acted on
  const [verificationResults, setVerificationResults] = useState({});

  /* ── Fetch tasks ── */
  const fetchTasks = useCallback(async (silent = false) => {
    if (!silent) setIsLoading(true);
    else setIsRefreshing(true);

    try {
      const res = await fetch(`${API_BASE}/api/v1/notion/tasks?session_id=${sessionId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 401) {
        if (onSessionExpired) onSessionExpired();
        throw new Error('Tu sesión ha expirado. Por favor, inicia una nueva sesión.');
      }
      if (!res.ok) throw new Error(`Error ${res.status}`);
      const data = await res.json();
      setTasks(Array.isArray(data) ? data : data.tasks || []);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [token, sessionId]);

  /* ── Mount + auto-refresh ── */
  useEffect(() => {
    fetchTasks();
    const interval = setInterval(() => fetchTasks(true), 15000);
    return () => clearInterval(interval);
  }, [fetchTasks]);

  /* ── Verify task ── */
  const handleVerify = useCallback(async (pageId) => {
    setActionLoading(pageId);
    try {
      const res = await fetch(`${API_BASE}/api/v1/notion/tasks/${pageId}/verify`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error('Error al verificar archivo');
      const data = await res.json();
      setVerificationResults(prev => ({
        ...prev,
        [pageId]: data
      }));
      // Update local task representation immediately for instant UI reaction
      setTasks(prevTasks => prevTasks.map(t => {
        if (t.page_id === pageId) {
          return { ...t, verificado: data.verificado };
        }
        return t;
      }));
      // Refresh task list in the background
      fetchTasks(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setActionLoading(null);
    }
  }, [token, fetchTasks]);

  /* ── Move task ── */
  const handleMove = useCallback(async (pageId, newStatus) => {
    setActionLoading(pageId);
    // Optimistic update in frontend to make it feel extremely fast and snappy!
    setTasks(prevTasks => prevTasks.map(t => {
      if (t.page_id === pageId) {
        return { ...t, status: newStatus };
      }
      return t;
    }));

    try {
      const res = await fetch(`${API_BASE}/api/v1/notion/tasks/${pageId}/move`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ status: newStatus }),
      });
      if (!res.ok) {
        // Rollback on error
        await fetchTasks(true);
        throw new Error('Error al mover tarea');
      }
      const data = await res.json();
      if (data.task) {
        setTasks(prevTasks => prevTasks.map(t => {
          if (t.page_id === pageId) {
            return { ...t, ...data.task };
          }
          return t;
        }));
      }
      fetchTasks(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setActionLoading(null);
    }
  }, [token, fetchTasks]);

  /* ── Execute task ── */
  const handleExecute = useCallback(async (pageId) => {
    setActionLoading(pageId);
    try {
      const res = await fetch(`${API_BASE}/api/v1/notion/tasks/${pageId}/execute`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error('Error al ejecutar tarea');
      const data = await res.json();
      if (data.task) {
        setTasks(prevTasks => prevTasks.map(t => {
          if (t.page_id === pageId) {
            return { ...t, ...data.task };
          }
          return t;
        }));
      }
      fetchTasks(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setActionLoading(null);
    }
  }, [token, fetchTasks]);

  /* ── Complete task ── */
  const handleComplete = useCallback(async (pageId) => {
    setActionLoading(pageId);
    // Optimistic update
    setTasks(prevTasks => prevTasks.map(t => {
      if (t.page_id === pageId) {
        return { ...t, status: 'Done' };
      }
      return t;
    }));

    try {
      const res = await fetch(`${API_BASE}/api/v1/notion/tasks/${pageId}/complete`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        // Rollback
        await fetchTasks(true);
        throw new Error('Error al completar tarea');
      }
      const data = await res.json();
      if (data.task) {
        setTasks(prevTasks => prevTasks.map(t => {
          if (t.page_id === pageId) {
            return { ...t, ...data.task };
          }
          return t;
        }));
      }
      fetchTasks(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setActionLoading(null);
    }
  }, [token, fetchTasks]);

  /* ── Group tasks by column ── */
  const tasksByColumn = COLUMNS.reduce((acc, col) => {
    acc[col.key] = tasks.filter(t => t.status === col.key);
    return acc;
  }, {});

  const totalTasks = tasks.length;

  return (
    <div className="w-full max-w-[1400px] mx-auto px-4 py-6 pb-24 fade-in-up">
      {/* ── Header Bar ── */}
      <div className="glass p-5 mb-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          {/* Back button */}
          <button
            onClick={onBack}
            className="p-2 rounded-xl hover:bg-white/10 text-gray-400 hover:text-white transition-colors"
            title="Volver"
          >
            ← 
          </button>

          <div>
            <h1 className="text-xl sm:text-2xl font-extrabold text-white flex items-center gap-2">
              📋 <span className="gradient-text">Tablero Kanban</span>
            </h1>
            <p className="text-xs text-gray-500 mt-0.5">
              Sesión: {sessionId ? sessionId.slice(0, 12) + '...' : 'N/A'}
              {' · '}{totalTasks} tarea{totalTasks !== 1 ? 's' : ''}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Connection status */}
          <div className="flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full ${error ? 'bg-red-500' : 'bg-emerald-400'} status-pulse`} />
            <span className="text-[11px] text-gray-500">{error ? 'Error' : 'Conectado'}</span>
          </div>

          {/* Refresh button */}
          <button
            onClick={() => fetchTasks(true)}
            disabled={isRefreshing}
            className={`p-2.5 rounded-xl border border-white/10 hover:bg-white/10 text-gray-400 hover:text-white transition-all text-sm ${
              isRefreshing ? 'spin-refresh' : ''
            }`}
            title="Actualizar"
          >
            🔄
          </button>
        </div>
      </div>

      {/* ── Error banner ── */}
      {error && (
        <div className="mb-4 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center gap-2">
          <span>⚠️</span>
          <span>{error}</span>
          <button
            onClick={() => setError(null)}
            className="ml-auto text-red-400/60 hover:text-red-400 text-xs"
          >
            ✕
          </button>
        </div>
      )}

      {/* ── Loading skeleton ── */}
      {isLoading ? (
        <div className="kanban-grid">
          {COLUMNS.map(col => (
            <div key={col.key} className={`kanban-column border-t-[3px] ${col.color}`}>
              <div className="flex items-center gap-2 mb-3 px-1">
                <span>{col.emoji}</span>
                <span className="text-sm font-semibold text-gray-400">{col.label}</span>
              </div>
              {[1, 2].map(i => (
                <div key={i} className="glass p-4 mb-3 animate-pulse">
                  <div className="h-3 bg-white/10 rounded w-3/4 mb-3" />
                  <div className="h-2 bg-white/10 rounded w-1/2 mb-2" />
                  <div className="h-2 bg-white/10 rounded w-1/3" />
                </div>
              ))}
            </div>
          ))}
        </div>
      ) : totalTasks === 0 ? (
        /* ── Empty state ── */
        <div className="glass p-12 text-center max-w-lg mx-auto">
          <span className="text-5xl block mb-4">📭</span>
          <h3 className="text-lg font-bold text-white mb-2">Sin tareas todavía</h3>
          <p className="text-sm text-gray-400 leading-relaxed mb-6">
            Aún no hay tareas en tu tablero. Completa el proceso de Triage para generar tu plan
            de trabajo y verás las tareas organizadas aquí automáticamente.
          </p>
          <button
            onClick={onBack}
            className="px-6 py-2.5 rounded-xl bg-primary/20 border border-primary/30 text-primary text-sm font-semibold hover:bg-primary/30 transition-all"
          >
            ← Volver al Roadmap
          </button>
        </div>
      ) : (
        /* ── Kanban grid ── */
        <div className="kanban-grid">
          {COLUMNS.map(col => {
            const colTasks = tasksByColumn[col.key] || [];
            return (
              <div key={col.key} className={`kanban-column border-t-[3px] ${col.color}`}>
                {/* Column header */}
                <div className="flex items-center justify-between mb-3 px-1">
                  <div className="flex items-center gap-2">
                    <span className="text-base">{col.emoji}</span>
                    <span className="text-sm font-semibold text-white">{col.label}</span>
                  </div>
                  <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full ${col.badge}`}>
                    {colTasks.length}
                  </span>
                </div>

                {/* Task cards */}
                {colTasks.map((task, idx) => (
                  <TaskCard
                    key={task.page_id || task.id || idx}
                    task={task}
                    index={idx}
                    onMove={handleMove}
                    onExecute={handleExecute}
                    onComplete={handleComplete}
                    onVerify={handleVerify}
                    verificationResult={verificationResults[task.page_id]}
                    isLoading={actionLoading === task.page_id}
                  />
                ))}

                {/* Empty column hint */}
                {colTasks.length === 0 && (
                  <div className="text-center py-8 text-gray-600 text-xs">
                    Sin tareas
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
