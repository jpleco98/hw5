// Thin client for the FastAPI backend (backend/main.py) at http://localhost:8000.

export const API_BASE: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export type AgentName = 'boss' | 'inventory' | 'accounting' | 'facilities' | 'customer_service'

export interface Ticket {
  ticket_id: number
  type: string
  requester: string
  subject: string
  notes: string | null
  sku: string | null
  size: string | null
  qty: number | null
  status: string
  state: 'open' | 'running' | 'resolved'
  running: boolean
  pending_approvals: number
  decision: string | null
  draft_count: number
}

export interface Draft {
  draft_id: number
  ticket_id: number
  audience: string
  recipient: string
  subject: string
  body: string
  author: string
  status: string
}

export interface PaymentRequest {
  request_id: number
  ticket_id: number
  kind: 'invoice' | 'rent' | 'purchase_order'
  ref_id: number | null
  vendor_id: number | null
  sku: string | null
  size: string | null
  qty: number | null
  amount: number
  reason: string
  requested_by: string
  status: string
  shop_date: string
  payee?: string
}

export interface TicketDetail {
  ticket_id: number
  status: string
  updates: { agent: string; status: string; note: string; shop_date: string }[]
  drafts: Draft[]
  payment_requests: PaymentRequest[]
}

export interface Payment {
  payment_id: number
  kind: string
  ref_id: number | null
  amount: number
  account: string
  paid_at: string
  approved_by: string
}

export interface Cash {
  account: string
  balance: number
  as_of: string
  pending_total: number
  cash_after_pending: number
  payments_made: Payment[]
}

export interface ToolCall {
  tool: string
  call_id?: string
  args?: Record<string, unknown> | string | null
}

export interface AgentEvent {
  index: number
  ts: string
  ticket_id: number | null
  agent: AgentName
  event: 'run_start' | 'model_response' | 'tool_results' | 'delegation_refused' | 'run_retry' | 'run_end' | 'run_error'
  depth: number
  chain: AgentName[]
  run_id: string
  parent_run_id: string | null
  said: string | null
  tools_used: string[]
  tool_calls: ToolCall[]
  delegations: { to: AgentName; task: string }[]
  tool_results: { tool: string; ok: boolean; result: string }[]
  cumulative_usage: { requests: number; tool_calls: number; input_tokens: number; output_tokens: number } | null
  output: Record<string, unknown> | null
  error: string | null
}

export interface Job {
  job_id: string
  ticket_id: number
  status: 'queued' | 'running' | 'done' | 'failed'
  outcome?: Record<string, unknown>
  error?: string
}

export interface Health {
  ok: boolean
  model: string
  agents_ready: boolean
  agents_error: string | null
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* not JSON */
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => call<Health>('/api/health'),
  tickets: () => call<Ticket[]>('/api/tickets'),
  ticket: (id: number) => call<TicketDetail>(`/api/tickets/${id}`),
  run: (id: number) => call<Job>(`/api/tickets/${id}/run`, { method: 'POST' }),
  job: (jobId: string) => call<Job>(`/api/runs/${jobId}`),
  events: (since: number) =>
    call<{ events: AgentEvent[]; next_since: number; total: number }>(`/api/events?since=${since}&limit=1000`),
  cash: () => call<Cash>('/api/cash'),
  requests: () => call<PaymentRequest[]>('/api/payment-requests'),
  approve: (id: number, approved_by: string) =>
    call<{ account_balance_after: number }>(`/api/payment-requests/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ approved_by }),
    }),
  reject: (id: number, rejected_by: string, reason: string) =>
    call(`/api/payment-requests/${id}/reject`, { method: 'POST', body: JSON.stringify({ rejected_by, reason }) }),
  reset: () => call('/api/reset', { method: 'POST' }),
}
