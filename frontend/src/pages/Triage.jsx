import { useState } from 'react';

export default function Triage({ session_id, token, onTriageComplete, onBackToLanding }) {
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const maxChars = 2000;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    // Split text into individual tasks by line breaks, filter out empty lines
    const parsedTasks = inputText
      .split('\n')
      .map((t) => t.trim())
      .filter((t) => t.length >= 3);

    if (parsedTasks.length === 0) {
      setError('Por favor, ingresa al menos una tarea válida (mínimo 3 caracteres).');
      return;
    }

    if (parsedTasks.length > 20) {
      setError('El límite máximo es de 20 tareas por sesión para optimizar tu enfoque.');
      return;
    }

    setIsLoading(true);

    try {
      const response = await fetch(`http://localhost:8000/api/v1/session/${session_id}/tasks`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ raw_tasks: parsedTasks }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Fallo al procesar el triage con la IA.');
      }

      const data = await response.json();
      onTriageComplete(data);
    } catch (err) {
      setError(err.message || 'Error de conexión con el backend.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="w-full max-w-2xl px-4 py-8">
      {/* ── Header Back Button ── */}
      <button
        onClick={onBackToLanding}
        className="flex items-center gap-2 text-sm text-gray-500 hover:text-white mb-8 transition-colors duration-200"
      >
        <span>←</span> Volver a Inicio
      </button>

      {/* ── Main Triage Card ── */}
      <div className="glass p-8 sm:p-10 pulse-glow relative overflow-hidden">
        {/* Floating background orb inside card */}
        <div className="absolute -top-12 -right-12 w-32 h-32 bg-primary/20 rounded-full blur-2xl pointer-events-none" />

        {/* Card Header */}
        <div className="flex items-center gap-3 mb-6 border-b border-white/5 pb-4">
          <div className="w-3 h-3 rounded-full bg-danger" />
          <div className="w-3 h-3 rounded-full bg-warning" />
          <div className="w-3 h-3 rounded-full bg-success" />
          <span className="ml-auto text-xs text-gray-500 font-mono">flowstep://triage-session</span>
        </div>

        <h2 className="text-2xl sm:text-3xl font-extrabold text-white mb-2 tracking-tight">
          Ingresa tus pendientes
        </h2>
        <p className="text-sm text-gray-400 mb-8 leading-relaxed">
          Escribe todo lo que planeas hacer hoy en lenguaje natural. Nuestro agente organizará y priorizará tu plan de forma inteligente.
        </p>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="relative">
            <label
              htmlFor="triage-input"
              className="block text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3"
            >
              Lista de pendientes (Una tarea por línea)
            </label>
            <textarea
              id="triage-input"
              rows={8}
              maxLength={maxChars}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              disabled={isLoading}
              placeholder={
                "Ejemplo:\n- Terminar de codificar la interfaz de usuario en React\n- Escribir un correo electrónico a Juan de avances\n- Investigar la API de OpenClaw\n- Crear el archivo de configuración config.json"
              }
              className="w-full bg-surface/60 border border-white/10 rounded-xl px-5 py-4 
                text-gray-100 placeholder-gray-600 text-sm leading-relaxed
                resize-none outline-none
                transition-all duration-300
                focus:border-primary/50 focus:ring-2 focus:ring-primary/20 focus:bg-surface/80
                disabled:opacity-50 disabled:cursor-not-allowed"
            />
          </div>

          {/* Error Message */}
          {error && (
            <div className="p-4 rounded-xl bg-danger/10 border border-danger/20 text-danger text-sm flex items-start gap-3 animated-fade-in">
              <span className="text-lg">⚠️</span>
              <span>{error}</span>
            </div>
          )}

          {/* Footer Actions */}
          <div className="flex items-center justify-between mt-4">
            <span
              className={`text-xs font-mono transition-colors duration-200 ${
                inputText.length > maxChars * 0.9
                  ? 'text-danger'
                  : inputText.length > maxChars * 0.7
                  ? 'text-warning'
                  : 'text-gray-500'
              }`}
            >
              {inputText.length} / {maxChars}
            </span>

            <button
              type="submit"
              disabled={isLoading || inputText.trim().length < 3}
              className="relative inline-flex items-center justify-center gap-2 px-8 py-3.5 
                rounded-xl font-bold text-sm overflow-hidden
                bg-gradient-to-r from-primary to-accent text-white
                shadow-lg shadow-primary/25
                transition-all duration-300
                hover:scale-105 hover:shadow-primary/40 active:scale-95
                disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
            >
              {isLoading ? (
                <>
                  <span className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                  <span>Analizando con IA...</span>
                </>
              ) : (
                <>
                  <span>Generar Hoja de Ruta</span>
                  <span>→</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Decorative Tips */}
      <div className="mt-8 text-center text-xs text-gray-500 max-w-md mx-auto leading-relaxed">
        💡 **Tip:** No te preocupes por el orden. La IA priorizará tu día balanceando automáticamente las tareas de alto impacto.
      </div>
    </div>
  );
}
