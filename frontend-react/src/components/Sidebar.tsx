import { useEffect, useState } from 'react';
import { api } from '../services/api';
import type { HealthResponse, SessionStatusResponse } from '../types/api';

interface SidebarProps {
  currentSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
  preferences: { cloud_provider: string; max_debate_rounds: number; detail_level: string };
  onPreferencesChange: (p: SidebarProps['preferences']) => void;
}

export function Sidebar({ currentSessionId, onSelectSession, onNewSession, preferences, onPreferencesChange }: SidebarProps) {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [sessions, setSessions] = useState<SessionStatusResponse[]>([]);
  const [settingsOpen, setSettingsOpen] = useState(false);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
    api.listSessions(10).then(setSessions).catch(() => {});
  }, [currentSessionId]);

  const healthStatus = health?.status ?? 'unavailable';
  const healthDot = healthStatus === 'healthy' ? 'bg-green-400' : healthStatus === 'degraded' ? 'bg-yellow-400' : 'bg-red-400';

  return (
    <aside className="w-72 bg-slate-900 text-slate-200 flex flex-col h-screen shrink-0">
      {/* Branding */}
      <div className="px-6 pt-6 pb-4 text-center">
        <span className="text-4xl">🏗️</span>
        <h1 className="text-xl font-bold text-white mt-1">ArchAdvisor</h1>
        <p className="text-xs text-slate-400 mt-0.5">Multi-Agent Architecture Design</p>
      </div>

      <div className="border-t border-slate-700 mx-4" />

      {/* Health */}
      <div className="px-6 py-3 flex items-center gap-2 text-xs text-slate-400">
        <span className={`w-2 h-2 rounded-full ${healthDot}`} />
        Backend: <span className="font-semibold text-slate-300">{healthStatus}</span>
      </div>

      <div className="border-t border-slate-700 mx-4" />

      {/* New Session */}
      <div className="px-4 py-3">
        <button
          onClick={onNewSession}
          className="w-full py-2 px-4 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-semibold transition-colors"
        >
          + New Session
        </button>
      </div>

      {/* Settings */}
      <div className="px-4">
        <button
          onClick={() => setSettingsOpen(!settingsOpen)}
          className="w-full text-left text-xs text-slate-400 hover:text-slate-200 py-2 flex items-center justify-between"
        >
          <span>⚙️ Settings</span>
          <span>{settingsOpen ? '▲' : '▼'}</span>
        </button>
        {settingsOpen && (
          <div className="space-y-3 pb-3">
            <label className="block">
              <span className="text-xs text-slate-400">Cloud Provider</span>
              <select
                value={preferences.cloud_provider}
                onChange={(e) => onPreferencesChange({ ...preferences, cloud_provider: e.target.value })}
                className="w-full mt-1 bg-slate-800 border border-slate-700 rounded px-2 py-1 text-sm text-slate-200"
              >
                <option value="all">All Providers</option>
                <option value="aws">AWS</option>
                <option value="gcp">GCP</option>
                <option value="azure">Azure</option>
              </select>
            </label>
            <label className="block">
              <span className="text-xs text-slate-400">Max Debate Rounds: {preferences.max_debate_rounds}</span>
              <input
                type="range" min={1} max={5}
                value={preferences.max_debate_rounds}
                onChange={(e) => onPreferencesChange({ ...preferences, max_debate_rounds: +e.target.value })}
                className="w-full mt-1"
              />
            </label>
            <label className="block">
              <span className="text-xs text-slate-400">Detail Level</span>
              <div className="flex gap-2 mt-1">
                {(['brief', 'detailed', 'comprehensive'] as const).map((level) => (
                  <button
                    key={level}
                    onClick={() => onPreferencesChange({ ...preferences, detail_level: level })}
                    className={`flex-1 py-1 text-xs rounded ${
                      preferences.detail_level === level
                        ? 'bg-blue-600 text-white'
                        : 'bg-slate-800 text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    {level}
                  </button>
                ))}
              </div>
            </label>
          </div>
        )}
      </div>

      <div className="border-t border-slate-700 mx-4" />

      {/* Recent Sessions */}
      <div className="px-4 py-3 flex-1 overflow-y-auto">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Recent Sessions</p>
        {sessions.length === 0 && <p className="text-xs text-slate-500">No sessions yet</p>}
        {sessions.map((s) => {
          const short = s.session_id.slice(-8);
          const isActive = s.session_id === currentSessionId;
          const emoji = s.status === 'complete' ? '✅' : s.status === 'error' ? '❌' : '⏳';
          return (
            <button
              key={s.session_id}
              onClick={() => onSelectSession(s.session_id)}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm mb-1 transition-colors ${
                isActive ? 'bg-slate-700 text-white' : 'hover:bg-slate-800 text-slate-400'
              }`}
            >
              <span className="mr-1">{emoji}</span>
              <span className="font-mono">{short}</span>
              <span className="text-xs ml-2">{s.status}</span>
            </button>
          );
        })}
      </div>
    </aside>
  );
}
