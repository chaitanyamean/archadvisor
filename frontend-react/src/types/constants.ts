export interface AgentConfig {
  icon: string;
  label: string;
  color: string;
  description: string;
}

export const AGENTS: Record<string, AgentConfig> = {
  architect:        { icon: '🏗️', label: 'Architect',           color: '#2563EB', description: 'Designs the system architecture with components, APIs, and data flows' },
  validator:        { icon: '🔍', label: 'Design Validator',     color: '#7C3AED', description: 'Deterministic engine checking for SPOFs, consistency issues, and gaps' },
  devils_advocate:  { icon: '😈', label: "Devil's Advocate",     color: '#DC2626', description: 'Challenges the design with hard questions to find weaknesses' },
  cost_analyzer:    { icon: '💰', label: 'Cost Analyzer',        color: '#059669', description: 'Estimates infrastructure costs across AWS, GCP, and Azure' },
  documentation:    { icon: '📝', label: 'Documentation',        color: '#D97706', description: 'Produces the final polished architecture document with diagrams' },
};

export const SEVERITY_CONFIG: Record<string, { icon: string; color: string; bg: string; border: string }> = {
  critical: { icon: '🔴', color: '#DC2626', bg: '#FEF2F2', border: '#FECACA' },
  high:     { icon: '🟠', color: '#EA580C', bg: '#FFF7ED', border: '#FED7AA' },
  medium:   { icon: '🟡', color: '#CA8A04', bg: '#FEFCE8', border: '#FEF08A' },
  low:      { icon: '🔵', color: '#2563EB', bg: '#EFF6FF', border: '#BFDBFE' },
};

export const STATUS_LABELS: Record<string, string> = {
  initializing: 'Initializing...', retrieving_context: 'Retrieving Context',
  designing: 'Architect Designing', validating: 'Validating Design',
  reviewing: "Devil's Advocate Reviewing", revising: 'Architect Revising',
  costing: 'Analyzing Costs', documenting: 'Generating Document',
  complete: 'Complete', error: 'Error', cancelled: 'Cancelled',
};

export const STATUS_TO_AGENT: Record<string, string> = {
  designing: 'architect', validating: 'validator', reviewing: 'devils_advocate',
  revising: 'architect', costing: 'cost_analyzer', documenting: 'documentation',
};

export const PIPELINE_STEPS = [
  { agentKey: 'architect',       label: 'Architect Design',         statuses: new Set(['designing']) },
  { agentKey: 'validator',       label: 'Design Validation',        statuses: new Set(['validating']) },
  { agentKey: 'devils_advocate', label: "Devil's Advocate Review",  statuses: new Set(['reviewing']) },
  { agentKey: 'architect',       label: 'Architect Revision',       statuses: new Set(['revising']) },
  { agentKey: 'cost_analyzer',   label: 'Cost Analysis',            statuses: new Set(['costing']) },
  { agentKey: 'documentation',   label: 'Documentation',            statuses: new Set(['documenting']) },
] as const;
