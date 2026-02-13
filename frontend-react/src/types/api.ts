/* ── Backend API types ── */

export interface SessionPreferences {
  cloud_provider: 'aws' | 'gcp' | 'azure' | 'all';
  max_debate_rounds: number;
  output_format: 'markdown';
  detail_level: 'brief' | 'detailed' | 'comprehensive';
}

export interface CreateSessionRequest {
  requirements: string;
  preferences: SessionPreferences;
}

export interface CreateSessionResponse {
  session_id: string;
  status: string;
  created_at: string;
  websocket_url: string;
  estimated_duration_seconds: number;
  estimated_cost_usd: number;
}

export interface AgentMessage {
  agent: string;
  role: string;
  summary: string;
  timestamp: string;
  duration_seconds: number;
  model: string;
  cost_usd: number;
}

export interface SessionProgress {
  current_agent: string | null;
  debate_round: number;
  steps_completed: number;
  total_steps: number;
}

export type SessionStatus =
  | 'initializing' | 'retrieving_context' | 'designing' | 'validating'
  | 'reviewing' | 'revising' | 'costing' | 'documenting'
  | 'complete' | 'error' | 'cancelled';

export interface SessionStatusResponse {
  session_id: string;
  status: SessionStatus;
  progress: SessionProgress;
  messages: AgentMessage[];
  cost_so_far_usd: number;
  created_at: string;
  completed_at: string | null;
}

export interface Diagram {
  type: string;
  title: string;
  mermaid_code: string;
}

export interface SessionOutputMetadata {
  total_duration_seconds: number;
  total_cost_usd: number;
  debate_rounds: number;
  models_used: string[];
}

export interface SessionOutputResponse {
  session_id: string;
  format: string;
  document: string;
  diagrams: Diagram[];
  metadata: SessionOutputMetadata;
}

export interface Template {
  id: string;
  name: string;
  description: string;
  requirements: string;
  complexity: 'simple' | 'medium' | 'complex';
}

export interface HealthDependency {
  status: 'healthy' | 'unhealthy' | 'degraded';
  latency_ms: number | null;
  message: string | null;
}

export interface HealthResponse {
  status: 'healthy' | 'unhealthy' | 'degraded';
  version: string;
  uptime_seconds: number;
  dependencies: { redis: HealthDependency };
}

/* ── WebSocket event types ── */

export type WSEvent =
  | { type: 'agent_started'; agent: string; agent_label: string; message: string }
  | { type: 'agent_thinking'; agent: string; message: string }
  | { type: 'agent_completed'; agent: string; summary: string; duration_seconds: number; cost_usd: number }
  | { type: 'workflow_progress'; step: number; total_steps: number; status: string; message: string }
  | { type: 'debate_round_started'; round: number; max_rounds: number; message: string }
  | { type: 'finding_discovered'; agent: string; severity: string; category: string; component: string; summary: string }
  | { type: 'debate_round_completed'; round: number; findings_total: number; findings_critical: number; findings_resolved: number; next_action: string }
  | { type: 'session_complete'; duration_seconds: number; total_cost_usd: number; debate_rounds: number; output_url: string }
  | { type: 'error'; message: string; recoverable: boolean }
  | { type: 'event_history'; events: WSEvent[]; count: number };
