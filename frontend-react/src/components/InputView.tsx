import { useEffect, useState } from 'react';
import { api } from '../services/api';
import { AGENTS } from '../types/constants';
import type { Template } from '../types/api';

interface InputViewProps {
  onSessionCreated: (sessionId: string) => void;
  preferences: { cloud_provider: string; max_debate_rounds: number; detail_level: string };
}

export function InputView({ onSessionCreated, preferences }: InputViewProps) {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [requirements, setRequirements] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api.templates().then(setTemplates).catch(() => {});
  }, []);

  const MAX_LENGTH = 2000;

  const handleGenerate = async () => {
    if (requirements.length < 50 || requirements.length > MAX_LENGTH) return;
    setLoading(true);
    setError('');
    try {
      const resp = await api.createSession(requirements, preferences);
      onSessionCreated(resp.session_id);
    } catch (e: any) {
      setError(e.message || 'Failed to create session');
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async () => {
    if (requirements.length < 50) return;
    setLoading(true);
    setError('');
    try {
      const resp = await api.createSession(requirements, preferences);
      onSessionCreated(resp.session_id);
    } catch (e: any) {
      setError(e.message || 'Failed to create session');
    } finally {
      setLoading(false);
    }
  };

  const complexityColor: Record<string, string> = {
    simple: 'text-green-600 bg-green-50 border-green-200',
    medium: 'text-amber-600 bg-amber-50 border-amber-200',
    complex: 'text-red-600 bg-red-50 border-red-200',
  };

  return (
    <div className="max-w-4xl mx-auto px-6 py-10">
      <div className="text-center mb-8">
        <h2 className="text-3xl font-bold text-slate-900">Design Your Architecture</h2>
        <p className="text-slate-500 mt-2 max-w-2xl mx-auto">
          Describe your system requirements below, then let our AI agents collaboratively
          design, challenge, and document a production-ready architecture.
        </p>
      </div>

      {/* Templates */}
      {templates.length > 0 && (
        <div className="mb-6">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Quick Start Templates</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {templates.map((t) => (
              <button
                key={t.id}
                onClick={() => setRequirements(t.requirements)}
                className="text-left p-4 rounded-xl border border-slate-200 hover:border-blue-400 hover:shadow-md transition-all bg-white"
              >
                <p className="font-semibold text-sm text-slate-800">{t.name}</p>
                <p className="text-xs text-slate-500 mt-1 line-clamp-2">{t.description}</p>
                <span className={`inline-block mt-2 text-[10px] font-bold uppercase px-2 py-0.5 rounded-full border ${complexityColor[t.complexity] ?? ''}`}>
                  {t.complexity}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Requirements textarea */}
      <div className="mb-4">
        <textarea
          value={requirements}
          onChange={(e) => setRequirements(e.target.value)}
          rows={10}
          placeholder="Describe your system requirements in detail...&#10;&#10;Example: Design a real-time notification system for an e-commerce platform with 50M users, supporting push, email, SMS, and in-app channels..."
          className="w-full rounded-xl border border-slate-300 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-y"
        />
        <div className="flex justify-between items-center mt-2">
          <span className={`text-xs ${requirements.length < 50 ? 'text-slate-400' : 'text-green-600'}`}>
            {requirements.length}/50 characters minimum
          </span>
          {error && <span className="text-xs text-red-600">{error}</span>}
        </div>
      </div>

      {/* Generate button */}
      <div className="text-center mb-12">
        <button
          onClick={handleGenerate}
          disabled={requirements.length < 50 || loading}
          className="px-8 py-3 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-300 disabled:cursor-not-allowed text-white font-semibold rounded-xl text-lg transition-colors shadow-lg shadow-blue-600/20"
        >
          {loading ? (
            <span className="flex items-center gap-2">
              <span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Creating session...
            </span>
          ) : (
            '🚀 Generate Architecture'
          )}
        </button>
      </div>

      {/* Agent cards */}
      <div>
        <h3 className="text-center text-lg font-semibold text-slate-700 mb-4">How It Works</h3>
        <div className="grid grid-cols-5 gap-4">
          {Object.entries(AGENTS).map(([key, agent]) => (
            <div key={key} className="text-center p-4">
              <span className="text-3xl block mb-2">{agent.icon}</span>
              <p className="font-semibold text-sm" style={{ color: agent.color }}>{agent.label}</p>
              <p className="text-xs text-slate-500 mt-1">{agent.description}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
