import { useEffect, useState, useRef } from 'react';
import { api } from '../services/api';
import { useWebSocket } from '../hooks/useWebSocket';
import { AGENTS, SEVERITY_CONFIG, STATUS_LABELS, STATUS_TO_AGENT, PIPELINE_STEPS } from '../types/constants';
import type { SessionStatusResponse, WSEvent } from '../types/api';

interface ProcessingViewProps {
  sessionId: string;
  onComplete: () => void;
  onError: (status: string) => void;
}

export function ProcessingView({ sessionId, onComplete, onError }: ProcessingViewProps) {
  const [session, setSession] = useState<SessionStatusResponse | null>(null);
  const feedEndRef = useRef<HTMLDivElement>(null);

  // WebSocket for real-time events
  const { connected, events } = useWebSocket({
    sessionId,
    onEvent: (event) => {
      if (event.type === 'session_complete') onComplete();
      if (event.type === 'error' && !(event as any).recoverable) onError('error');
    },
  });

  // Polling fallback — also detects completion
  useEffect(() => {
    let active = true;
    const poll = async () => {
      try {
        const data = await api.getSession(sessionId);
        if (!active) return;
        setSession(data);
        if (data.status === 'complete') onComplete();
        else if (data.status === 'error' || data.status === 'cancelled') onError(data.status);
      } catch { /* ignore */ }
    };
    poll();
    const interval = setInterval(poll, 3000);
    return () => { active = false; clearInterval(interval); };
  }, [sessionId, onComplete, onError]);

  // Auto-scroll feed
  useEffect(() => {
    feedEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [events.length]);

  const status = session?.status ?? 'designing';
  const progress = session?.progress ?? { steps_completed: 0, total_steps: 5, debate_round: 0, current_agent: null };
  const costSoFar = session?.cost_so_far_usd ?? 0;
  const progressPct = Math.min((progress.steps_completed / Math.max(progress.total_steps, 1)) * 100, 95);

  const handleCancel = async () => {
    try { await api.cancelSession(sessionId); onError('cancelled'); } catch { /* ignore */ }
  };

  return (
    <div className="flex-1 px-6 py-6 overflow-hidden flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-2xl font-bold text-slate-900">Generating Architecture</h2>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5 px-3 py-2 bg-slate-100 rounded-lg text-xs">
            <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500 animate-pulse-dot' : 'bg-red-400'}`} />
            <span className={connected ? 'text-green-700' : 'text-red-600'}>
              {connected ? 'Live' : 'Connecting...'}
            </span>
          </div>
          <div className="px-4 py-2 bg-emerald-50 rounded-lg text-emerald-700 font-semibold text-sm">
            💰 ${costSoFar.toFixed(4)}
          </div>
          <button
            onClick={handleCancel}
            className="px-4 py-2 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors"
          >
            ⏹ Cancel
          </button>
        </div>
      </div>

      {/* Progress bar */}
      <div className="mb-6">
        <div className="flex justify-between text-xs text-slate-500 mb-1">
          <span>{STATUS_LABELS[status] ?? status}</span>
          <span>Step {progress.steps_completed}/{progress.total_steps}</span>
        </div>
        <div className="w-full h-2 bg-slate-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-blue-600 to-purple-600 rounded-full transition-all duration-700"
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>

      {/* Two-column layout */}
      <div className="flex-1 grid grid-cols-5 gap-6 min-h-0">
        {/* Pipeline (left) */}
        <div className="col-span-2 overflow-y-auto pr-2">
          <h3 className="text-sm font-semibold text-slate-600 uppercase tracking-wider mb-3">Agent Pipeline</h3>
          <Pipeline status={status} debateRound={progress.debate_round} messages={session?.messages ?? []} />
        </div>

        {/* Activity Feed (right) */}
        <div className="col-span-3 overflow-y-auto pr-2">
          <h3 className="text-sm font-semibold text-slate-600 uppercase tracking-wider mb-3">Live Activity</h3>
          <EventFeed events={events} status={status} />
          <div ref={feedEndRef} />
        </div>
      </div>
    </div>
  );
}

/* ── Pipeline Steps ── */

function Pipeline({ status, debateRound, messages }: { status: string; debateRound: number; messages: any[] }) {
  const completedAgents = new Set(messages.map((m: any) => m.agent));
  let foundActive = false;

  return (
    <div className="space-y-2">
      {PIPELINE_STEPS.map((step, i) => {
        const agent = AGENTS[step.agentKey];
        const isActive = step.statuses.has(status);
        const isDone = !isActive && !foundActive && completedAgents.has(step.agentKey);
        if (isActive) foundActive = true;

        if (isActive) {
          const roundLabel = debateRound > 0 ? ` (Round ${debateRound})` : '';
          return (
            <div key={i} className="p-3 rounded-xl border-l-4 bg-gradient-to-r" style={{ borderColor: agent.color, background: `linear-gradient(90deg, ${agent.color}08, transparent)` }}>
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-green-500 animate-pulse-dot" />
                <span className="font-bold text-sm">{agent.icon} {step.label}{roundLabel}</span>
              </div>
              <p className="text-xs text-slate-500 mt-1 ml-5">{agent.description}</p>
            </div>
          );
        }

        if (isDone) {
          const msg = messages.find((m: any) => m.agent === step.agentKey);
          return (
            <div key={i} className="p-3 rounded-xl border-l-4 border-green-500 bg-green-50">
              <div className="flex items-center gap-2">
                <span className="text-sm">✅</span>
                <span className="font-semibold text-sm text-green-700">{agent.icon} {step.label}</span>
                {msg && <span className="text-xs text-slate-400 ml-auto">{msg.duration_seconds.toFixed(1)}s</span>}
              </div>
              {msg && <p className="text-xs text-slate-600 mt-1 ml-5 line-clamp-2">{msg.summary}</p>}
            </div>
          );
        }

        return (
          <div key={i} className="p-3 rounded-xl border-l-4 border-slate-200 bg-slate-50 opacity-50">
            <span className="text-sm text-slate-400">⏳ {agent.icon} {step.label}</span>
          </div>
        );
      })}
    </div>
  );
}

/* ── Live Event Feed ── */

function EventFeed({ events, status }: { events: WSEvent[]; status: string }) {
  if (events.length === 0) {
    const agentKey = STATUS_TO_AGENT[status] ?? 'architect';
    const agent = AGENTS[agentKey];
    return (
      <div className="text-center py-12">
        <span className="text-4xl animate-pulse-dot block mb-3">{agent?.icon ?? '🏗️'}</span>
        <p className="text-sm text-slate-500">
          <strong>{agent?.label}</strong> is analyzing requirements...
        </p>
        <p className="text-xs text-slate-400 mt-1">This typically takes 10–30 seconds per step.</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {events.map((event, i) => (
        <EventCard key={i} event={event} />
      ))}
    </div>
  );
}

function EventCard({ event }: { event: WSEvent }) {
  switch (event.type) {
    case 'agent_started': {
      const agent = AGENTS[event.agent] ?? { icon: '⚙️', label: event.agent_label, color: '#64748B' };
      return (
        <div className="p-3 rounded-xl border-l-4" style={{ borderColor: agent.color, background: `${agent.color}06` }}>
          <p className="text-sm font-semibold">{agent.icon} {agent.label}</p>
          <p className="text-xs text-slate-500 mt-0.5">{event.message}</p>
        </div>
      );
    }
    case 'agent_completed': {
      const agent = AGENTS[event.agent] ?? { icon: '⚙️', label: event.agent, color: '#64748B' };
      return (
        <div className="p-3 rounded-xl border-l-4" style={{ borderColor: agent.color }}>
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold">{agent.icon} {agent.label} ✔️</p>
            <span className="text-xs text-slate-400">{event.duration_seconds.toFixed(1)}s · ${event.cost_usd.toFixed(4)}</span>
          </div>
          <p className="text-xs text-slate-600 mt-1">{event.summary}</p>
        </div>
      );
    }
    case 'debate_round_started':
      return (
        <div className="flex items-center gap-3 py-2">
          <div className="flex-1 h-px bg-slate-300" />
          <span className="text-xs font-semibold text-slate-500">🥊 Debate Round {event.round} of {event.max_rounds}</span>
          <div className="flex-1 h-px bg-slate-300" />
        </div>
      );
    case 'finding_discovered': {
      const sev = SEVERITY_CONFIG[event.severity] ?? SEVERITY_CONFIG.medium;
      return (
        <div className="p-3 rounded-xl border" style={{ background: sev.bg, borderColor: sev.border }}>
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold uppercase px-2 py-0.5 rounded-full" style={{ color: sev.color, background: `${sev.color}15`, border: `1px solid ${sev.border}` }}>
              {sev.icon} {event.severity}
            </span>
            <span className="text-xs text-slate-500">{event.component}</span>
          </div>
          <p className="text-xs text-slate-700 mt-1">{event.summary}</p>
        </div>
      );
    }
    case 'debate_round_completed': {
      const action = event.next_action.includes('proceed') ? 'Proceeding to cost analysis' : 'Architect will revise';
      const actionColor = event.next_action.includes('proceed') ? 'text-green-700' : 'text-amber-700';
      return (
        <div className="p-3 rounded-xl bg-slate-100">
          <p className="text-xs">
            <strong>Round complete</strong> — {event.findings_total} findings ({event.findings_critical} critical)
            {' · '}<span className={`font-semibold ${actionColor}`}>{action}</span>
          </p>
        </div>
      );
    }
    case 'workflow_progress':
      return (
        <div className="py-1 text-xs text-slate-500">▶ Step {event.step}/{event.total_steps}: {event.message}</div>
      );
    case 'session_complete':
      return (
        <div className="p-4 rounded-xl bg-green-50 border border-green-200 text-center">
          <span className="text-xl">✅</span>
          <p className="font-semibold text-green-800 mt-1">Architecture Complete!</p>
          <p className="text-xs text-slate-500 mt-1">
            {(event.duration_seconds / 60).toFixed(1)} min · ${event.total_cost_usd.toFixed(4)} · {event.debate_rounds} debate rounds
          </p>
        </div>
      );
    case 'error':
      return (
        <div className="p-3 rounded-xl bg-red-50 border border-red-200">
          <p className="text-sm text-red-700">❌ {event.message}</p>
        </div>
      );
    default:
      return null;
  }
}
