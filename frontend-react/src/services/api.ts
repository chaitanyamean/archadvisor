import type {
  CreateSessionResponse,
  HealthResponse,
  SessionOutputResponse,
  SessionStatusResponse,
  Template,
} from '../types/api';

const BASE = '/api/v1';

export class ApiError extends Error {
  status: number;
  statusText: string;
  detail: any;

  constructor(status: number, statusText: string, detail: any) {
    const msg =
      typeof detail === 'object' && detail?.message
        ? detail.message
        : `${status} ${statusText}`;
    super(msg);
    this.status = status;
    this.statusText = statusText;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!res.ok) {
    let detail: any;
    try {
      const body = await res.json();
      detail = body.detail ?? body;
    } catch {
      detail = await res.text().catch(() => '');
    }
    throw new ApiError(res.status, res.statusText, detail);
  }
  return res.json();
}

export const api = {
  health: () => request<HealthResponse>('/health'),

  templates: () => request<Template[]>('/templates'),

  createSession: (requirements: string, preferences: {
    cloud_provider?: string;
    max_debate_rounds?: number;
    detail_level?: string;
  } = {}) =>
    request<CreateSessionResponse>('/sessions', {
      method: 'POST',
      body: JSON.stringify({
        requirements,
        preferences: {
          cloud_provider: preferences.cloud_provider ?? 'all',
          max_debate_rounds: preferences.max_debate_rounds ?? 3,
          output_format: 'markdown',
          detail_level: preferences.detail_level ?? 'detailed',
        },
      }),
    }),

  getSession: (id: string) =>
    request<SessionStatusResponse>(`/sessions/${id}`),

  getSessionOutput: (id: string) =>
    request<SessionOutputResponse>(`/sessions/${id}/output`),

  cancelSession: (id: string) =>
    request<{ message: string }>(`/sessions/${id}/cancel`, { method: 'POST' }),

  listSessions: (limit = 20) =>
    request<SessionStatusResponse[]>(`/sessions?limit=${limit}`),
};
