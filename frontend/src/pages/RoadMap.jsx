import { useState } from 'react';

export default function RoadMap({ session_id, token, triageData, onStartSession, onResetSession }) {
  const [tasks, setTasks] = useState(triageData.tasks || []);
  const [estimatedTime, setEstimatedTime] = useState(triageData.tiempo_total_estimado_min || 0);
  const [warning, setWarning] = useState(triageData.advertencia || null);
  
  const [editingTaskId, setEditingTaskId] = useState(null);
  const [editTitle, setEditTitle] = useState('');
  const [editEffort, setEditEffort] = useState('');
  const [editUrgency, setEditUrgency] = useState('');
  const [editType, setEditType] = useState('');
  
  const [isActionLoading, setIsActionLoading] = useState(false);
  const [error, setError] = useState(null);

  // Type details for tags
  const TYPE_DETAILS = {
    código: { icon: '💻', color: 'text-indigo-400 bg-indigo-500/10 border-indigo-500/20' },
    archivo: { icon: '📂', color: 'text-teal-400 bg-teal-500/10 border-teal-500/20' },
    web: { icon: '🌐', color: 'text-sky-400 bg-sky-500/10 border-sky-500/20' },
    comunicación: { icon: '📧', color: 'text-pink-400 bg-pink-500/10 border-pink-500/20' },
    otro: { icon: '⚙️', color: 'text-gray-400 bg-gray-500/10 border-gray-500/20' },
  };

  const URGENCY_BORDER = {
    alta: 'border-l-4 border-l-red-500',
    media: 'border-l-4 border-l-amber-500',
    baja: 'border-l-4 border-l-slate-600',
  };

  // Reorder task action
  const handleReorder = async (taskId, currentIndex, direction) => {
    const newIndex = direction === 'up' ? currentIndex - 1 : currentIndex + 1;
    if (newIndex < 1 || newIndex > tasks.length) return;

    setIsActionLoading(true);
    setError(null);

    try {
      const response = await fetch(`http://localhost:8000/api/v1/task/${taskId}/reorder`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ new_index: newIndex }),
      });

      if (!response.ok) {
        throw new Error('Fallo al reordenar la tarea en la base de datos.');
      }

      const updatedTasks = await response.json();
      setTasks(updatedTasks);
    } catch (err) {
      setError(err.message || 'Error de conexión.');
    } finally {
      setIsActionLoading(false);
    }
  };

  // Start editing a task inline
  const startEditing = (task) => {
    setEditingTaskId(task.id);
    setEditTitle(task.title);
    setEditEffort(task.effort);
    setEditUrgency(task.urgency);
    setEditType(task.tipo);
  };

  // Save edited task
  const saveEdit = async (taskId) => {
    if (!editTitle.trim()) return;

    setIsActionLoading(true);
    setError(null);

    try {
      // In this phase, we update title, effort, urgency, tipo via the status API mock notes or directly mock
      // Since the Spec Kit specifies PUT /task/{id}/status for status/notes, we can simulate local UI updates
      // for the edited parameters so the user has immediate seamless UX, which is what they requested ("lo más cómodo posible").
      
      const updatedTasks = tasks.map((t) => {
        if (t.id === taskId) {
          return {
            ...t,
            title: editTitle,
            effort: editEffort,
            urgency: editUrgency,
            tipo: editType
          };
        }
        return t;
      });

      setTasks(updatedTasks);
      setEditingTaskId(null);

      // Re-calculate mock time total
      let newTotalTime = 0;
      updatedTasks.forEach((t) => {
        if (t.effort === 'alto') newTotalTime += 150;
        else if (t.effort === 'medio') newTotalTime += 60;
        else newTotalTime += 15;
      });
      setEstimatedTime(newTotalTime);

    } catch (err) {
      setError('Error al actualizar los datos.');
    } finally {
      setIsActionLoading(false);
    }
  };

  // Delete task local update
  const handleDelete = (taskId) => {
    const filteredTasks = tasks.filter((t) => t.id !== taskId);
    // Recalculate indexes sequentially
    const updatedTasks = filteredTasks.map((t, idx) => ({
      ...t,
      order_index: idx + 1
    }));
    
    setTasks(updatedTasks);

    // Re-calculate mock time total
    let newTotalTime = 0;
    updatedTasks.forEach((t) => {
      if (t.effort === 'alto') newTotalTime += 150;
      else if (t.effort === 'medio') newTotalTime += 60;
      else newTotalTime += 15;
    });
    setEstimatedTime(newTotalTime);
  };

  return (
    <div className="w-full max-w-3xl px-4 py-8">
      {/* ── Header Reset Button ── */}
      <button
        onClick={onResetSession}
        className="flex items-center gap-2 text-sm text-gray-500 hover:text-white mb-8 transition-colors duration-200"
      >
        <span>←</span> Volver a ingresar tareas
      </button>

      {/* ── Main RoadMap Container ── */}
      <div className="space-y-6">
        
        {/* ── Dashboard Stats ── */}
        <div className="glass p-6 sm:p-8 flex flex-col sm:flex-row items-center justify-between gap-6 relative overflow-hidden">
          <div className="absolute -top-12 -left-12 w-24 h-24 bg-accent/20 rounded-full blur-2xl pointer-events-none" />
          
          <div>
            <span className="text-xs font-semibold uppercase tracking-wider text-primary">Sesión Generada</span>
            <h2 className="text-2xl font-bold text-white mt-1">Hoja de Ruta del Día</h2>
          </div>

          <div className="flex gap-8 text-center sm:text-right">
            <div>
              <span className="block text-xs text-gray-500 font-medium">Tiempo Estimado</span>
              <span className="text-3xl font-extrabold text-white font-mono">
                {Math.floor(estimatedTime / 60)}h {estimatedTime % 60}m
              </span>
            </div>
            <div>
              <span className="block text-xs text-gray-500 font-medium">Total Tareas</span>
              <span className="text-3xl font-extrabold text-primary font-mono">{tasks.length}</span>
            </div>
          </div>
        </div>

        {/* ── Cognitive Warning ── */}
        {warning && (
          <div className="p-5 rounded-2xl bg-warning/10 border border-warning/20 text-warning text-sm flex items-start gap-4 animated-fade-in shadow-lg">
            <span className="text-2xl">🧠</span>
            <div>
              <h4 className="font-bold text-white mb-1">Aviso de Carga Cognitiva</h4>
              <p className="text-gray-300 leading-relaxed text-xs sm:text-sm">{warning}</p>
            </div>
          </div>
        )}

        {/* ── Error Banner ── */}
        {error && (
          <div className="p-4 rounded-xl bg-danger/10 border border-danger/20 text-danger text-sm flex items-center gap-3">
            <span>⚠️</span>
            <span>{error}</span>
          </div>
        )}

        {/* ── Task List ── */}
        <div className="space-y-3.5">
          {tasks.map((task, idx) => {
            const isEditing = editingTaskId === task.id;
            const details = TYPE_DETAILS[task.tipo] || TYPE_DETAILS.otro;

            return (
              <div
                key={task.id}
                className={`glass p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 
                  transition-all duration-300 hover:bg-surface/50 border-white/5 
                  ${URGENCY_BORDER[task.urgency] || ''}
                  ${isEditing ? 'border border-primary/50 bg-surface/75' : ''}`}
              >
                {isEditing ? (
                  /* ── EDIT MODE ── */
                  <div className="flex-1 space-y-4">
                    <input
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      className="w-full bg-surface border border-white/10 rounded-lg px-4 py-2 text-white text-sm outline-none focus:border-primary/50"
                      placeholder="Título de la tarea"
                    />
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                      <div>
                        <label className="block text-xxs text-gray-500 uppercase tracking-wider mb-1">Tipo</label>
                        <select
                          value={editType}
                          onChange={(e) => setEditType(e.target.value)}
                          className="w-full bg-surface border border-white/10 rounded-lg px-3 py-1.5 text-white text-xs outline-none"
                        >
                          <option value="código">💻 Código</option>
                          <option value="archivo">📂 Archivo</option>
                          <option value="web">🌐 Web</option>
                          <option value="comunicación">📧 Comunicación</option>
                          <option value="otro">⚙️ Otro</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-xxs text-gray-500 uppercase tracking-wider mb-1">Urgencia</label>
                        <select
                          value={editUrgency}
                          onChange={(e) => setEditUrgency(e.target.value)}
                          className="w-full bg-surface border border-white/10 rounded-lg px-3 py-1.5 text-white text-xs outline-none"
                        >
                          <option value="alta">🔴 Alta</option>
                          <option value="media">🟡 Media</option>
                          <option value="baja">⚪ Baja</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-xxs text-gray-500 uppercase tracking-wider mb-1">Esfuerzo</label>
                        <select
                          value={editEffort}
                          onChange={(e) => setEditEffort(e.target.value)}
                          className="w-full bg-surface border border-white/10 rounded-lg px-3 py-1.5 text-white text-xs outline-none"
                        >
                          <option value="bajo">🟢 Bajo (≤30m)</option>
                          <option value="medio">🟡 Medio (30m-2h)</option>
                          <option value="alto">🔴 Alto (&gt;2h)</option>
                        </select>
                      </div>
                    </div>
                    <div className="flex gap-2 justify-end">
                      <button
                        onClick={() => setEditingTaskId(null)}
                        className="px-4 py-1.5 rounded-lg border border-white/10 text-gray-400 hover:text-white text-xs"
                      >
                        Cancelar
                      </button>
                      <button
                        onClick={() => saveEdit(task.id)}
                        className="px-4 py-1.5 rounded-lg bg-primary hover:bg-primary-dark text-white text-xs font-semibold"
                      >
                        Guardar
                      </button>
                    </div>
                  </div>
                ) : (
                  /* ── VIEW MODE ── */
                  <>
                    <div className="flex-1 flex gap-4 items-start">
                      {/* Order Index Badge */}
                      <span className="w-6 h-6 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center text-xs font-mono text-gray-400 font-bold shrink-0 mt-0.5">
                        {idx + 1}
                      </span>
                      
                      <div className="space-y-1.5">
                        <p className="text-white text-sm font-medium leading-relaxed">{task.title}</p>
                        
                        <div className="flex flex-wrap gap-2 items-center">
                          {/* Type tag */}
                          <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-xxs font-medium border ${details.color}`}>
                            <span>{details.icon}</span>
                            <span className="capitalize">{task.tipo}</span>
                          </span>

                          {/* Effort tag */}
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-xxs font-medium bg-white/5 border border-white/5 text-gray-400">
                            ⏱️ {task.effort === 'alto' ? 'Alto (>2h)' : task.effort === 'medio' ? 'Medio (30m-2h)' : 'Bajo (≤30m)'}
                          </span>

                          {/* Urgency tag */}
                          <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xxs font-semibold uppercase tracking-wider
                            ${task.urgency === 'alta' ? 'text-red-400 bg-red-500/10' : task.urgency === 'media' ? 'text-amber-400 bg-amber-500/10' : 'text-slate-400 bg-slate-500/10'}`}>
                            {task.urgency}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Actions and Reordering row */}
                    <div className="flex items-center justify-between md:justify-end gap-3 border-t md:border-t-0 border-white/5 pt-3 md:pt-0">
                      {/* Up/Down buttons for sorting */}
                      <div className="flex items-center gap-1">
                        <button
                          disabled={idx === 0 || isActionLoading}
                          onClick={() => handleReorder(task.id, idx + 1, 'up')}
                          className="w-8 h-8 rounded-lg bg-white/5 hover:bg-white/10 flex items-center justify-center text-gray-400 hover:text-white transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                          title="Subir"
                        >
                          ▲
                        </button>
                        <button
                          disabled={idx === tasks.length - 1 || isActionLoading}
                          onClick={() => handleReorder(task.id, idx + 1, 'down')}
                          className="w-8 h-8 rounded-lg bg-white/5 hover:bg-white/10 flex items-center justify-center text-gray-400 hover:text-white transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                          title="Bajar"
                        >
                          ▼
                        </button>
                      </div>

                      {/* Edit / Delete actions */}
                      <div className="flex items-center gap-1.5">
                        <button
                          onClick={() => startEditing(task)}
                          className="px-3 py-1.5 rounded-lg border border-white/5 hover:bg-white/5 text-xs text-gray-400 hover:text-white transition-colors"
                        >
                          Editar
                        </button>
                        <button
                          onClick={() => handleDelete(task.id)}
                          className="px-3 py-1.5 rounded-lg border border-red-500/20 bg-red-500/5 hover:bg-red-500/10 text-xs text-red-400 transition-colors"
                        >
                          Eliminar
                        </button>
                      </div>
                    </div>
                  </>
                )}
              </div>
            );
          })}
        </div>

        {/* ── Confirm Session CTA ── */}
        <div className="flex flex-col sm:flex-row justify-between items-center gap-4 pt-6 border-t border-white/5">
          <p className="text-xs text-gray-500 text-center sm:text-left leading-relaxed">
            Al comenzar, tu agente FlowStep AI te guiará paso a paso y validará tus avances en tiempo real.
          </p>
          <button
            onClick={() => onStartSession(tasks)}
            className="w-full sm:w-auto relative inline-flex items-center justify-center gap-2 px-10 py-4 
              rounded-xl font-bold text-sm overflow-hidden
              bg-gradient-to-r from-primary to-accent text-white
              shadow-lg shadow-primary/25
              transition-all duration-300
              hover:scale-105 hover:shadow-primary/45 active:scale-95 shrink-0"
          >
            <span>Comenzar con este Plan</span>
            <span>🚀</span>
          </button>
        </div>

      </div>
    </div>
  );
}
