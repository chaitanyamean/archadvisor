import { useEffect, useState, useCallback, useRef } from 'react';
import { api } from '../services/api';
import { AGENTS } from '../types/constants';
import type { SessionOutputResponse, SessionStatusResponse } from '../types/api';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import mermaid from 'mermaid';

// Initialize mermaid once
mermaid.initialize({ startOnLoad: false, theme: 'default', securityLevel: 'loose' });

interface ResultsViewProps {
  sessionId: string;
}

type Tab = 'document' | 'diagrams' | 'conversation' | 'metrics';

export function ResultsView({ sessionId }: ResultsViewProps) {
  const [output, setOutput] = useState<SessionOutputResponse | null>(null);
  const [session, setSession] = useState<SessionStatusResponse | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>('document');
  const [error, setError] = useState('');

  useEffect(() => {
    api.getSessionOutput(sessionId).then(setOutput).catch((e) => setError(e.message));
    api.getSession(sessionId).then(setSession).catch(() => {});
  }, [sessionId]);

  if (error) return <div className="p-8 text-center text-red-600">{error}</div>;
  if (!output) return <div className="p-8 text-center text-slate-500">Loading output...</div>;

  const meta = output.metadata;
  const tabs: { key: Tab; label: string }[] = [
    { key: 'document', label: '📄 Document' },
    { key: 'diagrams', label: '📊 Diagrams' },
    { key: 'conversation', label: '💬 Conversation' },
    { key: 'metrics', label: '📈 Metrics' },
  ];

  return (
    <div className="flex-1 px-6 py-6 overflow-hidden flex flex-col">
      {/* Header metrics */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-slate-900 mb-4">Architecture Complete</h2>
        <div className="grid grid-cols-4 gap-4">
          <MetricCard icon="⏱️" value={`${(meta.total_duration_seconds / 60).toFixed(1)} min`} label="Total Time" />
          <MetricCard icon="💰" value={`$${meta.total_cost_usd.toFixed(4)}`} label="Total Cost" />
          <MetricCard icon="🥊" value={String(meta.debate_rounds)} label="Debate Rounds" />
          <MetricCard icon="🤖" value={String(meta.models_used.length)} label="Models Used" />
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-slate-200 mb-4">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-5 py-2.5 text-sm font-medium rounded-t-lg transition-colors ${
              activeTab === tab.key
                ? 'bg-white border border-b-white border-slate-200 text-blue-600 -mb-px'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto">
        {activeTab === 'document' && <DocumentTab output={output} />}
        {activeTab === 'diagrams' && <DiagramsTab output={output} />}
        {activeTab === 'conversation' && <ConversationTab session={session} />}
        {activeTab === 'metrics' && <MetricsTab output={output} session={session} />}
      </div>
    </div>
  );
}

function MetricCard({ icon, value, label }: { icon: string; value: string; label: string }) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-4 text-center">
      <div className="text-2xl font-bold text-slate-900">{icon} {value}</div>
      <div className="text-xs text-slate-500 mt-1">{label}</div>
    </div>
  );
}

/* ── Mermaid Diagram Component ── */
function MermaidDiagram({ code }: { code: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    const id = `mermaid-${Math.random().toString(36).slice(2, 9)}`;
    mermaid.render(id, code.trim()).then(
      ({ svg: renderedSvg }) => {
        if (!cancelled) setSvg(renderedSvg);
      },
      (err) => {
        if (!cancelled) setError(String(err));
      }
    );
    return () => { cancelled = true; };
  }, [code]);

  if (error) {
    return (
      <div className="my-4">
        <p className="text-xs text-red-500 mb-2">Diagram render failed — showing source:</p>
        <pre className="bg-slate-900 text-slate-100 rounded-xl p-4 overflow-x-auto text-xs">
          <code>{code}</code>
        </pre>
      </div>
    );
  }

  if (!svg) return <div className="my-4 p-4 text-center text-slate-400 text-sm">Rendering diagram...</div>;

  return (
    <div
      ref={containerRef}
      className="my-4 bg-white border border-slate-200 rounded-xl p-4 overflow-x-auto"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}

/* ── Document Tab ── */
function DocumentTab({ output }: { output: SessionOutputResponse }) {
  const handleDownload = useCallback(() => {
    const blob = new Blob([output.document], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'architecture_document.md';
    a.click();
    URL.revokeObjectURL(url);
  }, [output.document]);

  return (
    <div>
      <div className="flex justify-end mb-4">
        <button onClick={handleDownload} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-500">
          ⬇️ Download .md
        </button>
      </div>
      <div className="prose prose-slate max-w-none
        prose-headings:text-slate-900
        prose-h1:text-2xl prose-h1:font-bold prose-h1:mt-8 prose-h1:mb-4
        prose-h2:text-xl prose-h2:font-bold prose-h2:mt-8 prose-h2:mb-3
        prose-h3:text-lg prose-h3:font-semibold prose-h3:mt-6 prose-h3:mb-2
        prose-table:border-collapse prose-table:w-full
        prose-th:border prose-th:border-slate-200 prose-th:bg-slate-50 prose-th:px-3 prose-th:py-2 prose-th:text-sm prose-th:font-semibold prose-th:text-left
        prose-td:border prose-td:border-slate-200 prose-td:px-3 prose-td:py-2 prose-td:text-sm
        prose-code:bg-slate-100 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-sm prose-code:text-slate-800
        prose-li:text-sm
      ">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            code({ className, children, ...props }) {
              const match = /language-mermaid/.exec(className || '');
              if (match) {
                return <MermaidDiagram code={String(children).replace(/\n$/, '')} />;
              }
              return (
                <code className={className} {...props}>
                  {children}
                </code>
              );
            },
            pre({ children }) {
              return <>{children}</>;
            },
          }}
        >
          {output.document}
        </ReactMarkdown>
      </div>
    </div>
  );
}

/* ── Diagrams Tab ── */
function DiagramsTab({ output }: { output: SessionOutputResponse }) {
  if (output.diagrams.length === 0) return <p className="text-slate-500">No diagrams available.</p>;

  return (
    <div className="space-y-8">
      {output.diagrams.map((d, i) => (
        <div key={i} className="bg-white border border-slate-200 rounded-xl p-6">
          <div className="flex justify-between items-center mb-4">
            <div>
              <h3 className="text-lg font-semibold">{d.title}</h3>
              <span className="text-xs text-slate-400 uppercase">{d.type}</span>
            </div>
            <button
              onClick={() => navigator.clipboard.writeText(d.mermaid_code)}
              className="text-xs px-3 py-1.5 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
            >
              📋 Copy Mermaid
            </button>
          </div>
          <MermaidDiagram code={d.mermaid_code} />
        </div>
      ))}
    </div>
  );
}

/* ── Conversation Tab ── */
function ConversationTab({ session }: { session: SessionStatusResponse | null }) {
  if (!session?.messages?.length) return <p className="text-slate-500">No conversation history.</p>;

  let debateRound = 0;
  return (
    <div className="space-y-3">
      {session.messages.map((msg, i) => {
        const agent = AGENTS[msg.agent] ?? { icon: '⚙️', label: msg.role, color: '#64748B' };
        const showDivider = msg.agent === 'devils_advocate';
        if (showDivider) debateRound++;

        return (
          <div key={i}>
            {showDivider && (
              <div className="flex items-center gap-3 my-4">
                <div className="flex-1 h-px bg-slate-300" />
                <span className="text-xs font-semibold text-slate-500">🥊 Debate Round {debateRound}</span>
                <div className="flex-1 h-px bg-slate-300" />
              </div>
            )}
            <div className="p-4 rounded-xl border-l-4 bg-slate-50" style={{ borderColor: agent.color }}>
              <div className="flex items-center justify-between">
                <span className="font-semibold text-sm">{agent.icon} {msg.role}</span>
                <span className="text-xs text-slate-400">
                  🤖 {msg.model} · ⏱️ {msg.duration_seconds.toFixed(1)}s · 💰 ${msg.cost_usd.toFixed(4)}
                </span>
              </div>
              <p className="text-sm text-slate-700 mt-2">{msg.summary}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ── Metrics Tab ── */
function MetricsTab({ output, session }: { output: SessionOutputResponse; session: SessionStatusResponse | null }) {
  const meta = output.metadata;
  const messages = session?.messages ?? [];

  // Aggregate cost and duration per agent
  const agentStats: Record<string, { cost: number; duration: number }> = {};
  for (const msg of messages) {
    const key = AGENTS[msg.agent]?.label ?? msg.agent;
    if (!agentStats[key]) agentStats[key] = { cost: 0, duration: 0 };
    agentStats[key].cost += msg.cost_usd;
    agentStats[key].duration += msg.duration_seconds;
  }

  const costData = Object.entries(agentStats).map(([name, s]) => ({
    name,
    value: +s.cost.toFixed(4),
    color: Object.values(AGENTS).find(a => a.label === name)?.color ?? '#64748B',
  }));

  const durationData = Object.entries(agentStats).map(([name, s]) => ({
    name,
    seconds: +s.duration.toFixed(1),
    color: Object.values(AGENTS).find(a => a.label === name)?.color ?? '#64748B',
  }));

  return (
    <div className="space-y-8">
      {/* Summary */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <p className="text-sm text-slate-500">Total Duration</p>
          <p className="text-xl font-bold">{(meta.total_duration_seconds / 60).toFixed(1)} min</p>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <p className="text-sm text-slate-500">Total Cost</p>
          <p className="text-xl font-bold">${meta.total_cost_usd.toFixed(4)}</p>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <p className="text-sm text-slate-500">Models Used</p>
          <p className="text-sm font-semibold mt-1">{meta.models_used.join(', ')}</p>
        </div>
      </div>

      {/* Per-agent table */}
      {messages.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-slate-600 uppercase tracking-wider mb-3">Per-Agent Breakdown</h3>
          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-50">
                <tr>
                  <th className="text-left px-4 py-2 font-semibold">Agent</th>
                  <th className="text-left px-4 py-2 font-semibold">Model</th>
                  <th className="text-right px-4 py-2 font-semibold">Duration</th>
                  <th className="text-right px-4 py-2 font-semibold">Cost</th>
                </tr>
              </thead>
              <tbody>
                {messages.map((msg, i) => {
                  const agent = AGENTS[msg.agent];
                  return (
                    <tr key={i} className="border-t border-slate-100">
                      <td className="px-4 py-2">{agent?.icon} {msg.role}</td>
                      <td className="px-4 py-2 text-slate-500">{msg.model}</td>
                      <td className="px-4 py-2 text-right">{msg.duration_seconds.toFixed(1)}s</td>
                      <td className="px-4 py-2 text-right">${msg.cost_usd.toFixed(4)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Charts */}
      <div className="grid grid-cols-2 gap-6">
        {costData.length > 0 && (
          <div className="bg-white border border-slate-200 rounded-xl p-4">
            <h3 className="text-sm font-semibold text-slate-600 mb-4">Cost per Agent</h3>
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie data={costData} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={50} outerRadius={90} label={({ name, percent }: any) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`} labelLine={false}>
                  {costData.map((d, i) => <Cell key={i} fill={d.color} />)}
                </Pie>
                <Tooltip formatter={(v: any) => `$${Number(v).toFixed(4)}`} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}
        {durationData.length > 0 && (
          <div className="bg-white border border-slate-200 rounded-xl p-4">
            <h3 className="text-sm font-semibold text-slate-600 mb-4">Duration per Agent</h3>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={durationData} layout="vertical" margin={{ left: 80 }}>
                <XAxis type="number" unit="s" />
                <YAxis type="category" dataKey="name" width={80} tick={{ fontSize: 12 }} />
                <Tooltip formatter={(v: any) => `${Number(v)}s`} />
                <Bar dataKey="seconds" radius={[0, 4, 4, 0]}>
                  {durationData.map((d, i) => <Cell key={i} fill={d.color} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
}
