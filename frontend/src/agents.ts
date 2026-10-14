// Who sits at the table, how each one "sounds", and how a run's events become a live picture.

import type { AgentEvent, AgentName, ToolCall } from './api'

export interface AgentMeta {
  name: string
  role: string
  initials: string
  color: string
  voice: string // CSS class that gives the agent its own written voice
  seat: { x: number; y: number; flip?: boolean } // badge centre, % of the room; flip = card opens to the left
}

export const AGENTS: Record<AgentName, AgentMeta> = {
  boss: {
    name: 'Boss',
    role: 'reads the ticket, routes it, makes the call',
    initials: 'B',
    color: '#0f2d52',
    voice: 'voice-memo',
    seat: { x: 41, y: 11 },
  },
  inventory: {
    name: 'Inventory',
    role: 'shelves, sizes, vendors, lead times',
    initials: 'IN',
    color: '#2e6b4a',
    voice: 'voice-tag',
    seat: { x: 4, y: 47 },
  },
  accounting: {
    name: 'Accounting',
    role: 'cash, invoices, margins, checks for you',
    initials: 'AC',
    color: '#8c2f39',
    voice: 'voice-ledger',
    seat: { x: 96, y: 47, flip: true },
  },
  facilities: {
    name: 'Facilities',
    role: 'the lease, the rent, the landlord',
    initials: 'FA',
    color: '#2f5d8a',
    voice: 'voice-blueprint',
    seat: { x: 94, y: 86, flip: true },
  },
  customer_service: {
    name: 'Customer Service',
    role: 'drafts what customers will read',
    initials: 'CS',
    color: '#b0662a',
    voice: 'voice-letter',
    seat: { x: 6, y: 86 },
  },
}

export const AGENT_ORDER: AgentName[] = ['boss', 'inventory', 'accounting', 'facilities', 'customer_service']

// What a tool call looks like from across the room.
const VERBS: Record<string, string> = {
  get_ticket: 'reading the ticket',
  list_tickets: 'scanning the board',
  check_stock: 'checking the shelf',
  get_vendor_status: 'checking the vendor ledger',
  get_rent_status: 'pulling the lease',
  get_invoice: 'pulling the invoice',
  quote_bulk_price: 'running the numbers',
  get_cash_position: 'counting the drawer',
  list_payment_requests: 'checking the approvals tray',
  update_ticket: 'writing on the board',
  save_draft: 'drafting a note',
  request_payment: 'writing you a check to sign',
  delegate: 'handing off',
  final_result: 'writing up',
}

export const verb = (tool: string) => VERBS[tool] ?? tool.replaceAll('_', ' ')

export function argLine(call: ToolCall): string {
  const a = call.args
  if (!a || typeof a !== 'object') return ''
  if (call.tool === 'delegate') return `→ ${AGENTS[(a as { to: AgentName }).to]?.name ?? String(a.to)}`
  if (call.tool === 'final_result') return ''
  const skip = new Set(['note', 'body', 'reason', 'agent', 'author', 'requested_by', 'subject'])
  return Object.entries(a)
    .filter(([k, v]) => !skip.has(k) && v !== null && v !== undefined && v !== '')
    .map(([, v]) => String(v))
    .join(' · ')
}

// ---------------------------------------------------------------------------
// Turning audit events into "what the table looks like right now"
// ---------------------------------------------------------------------------

export type Mood = 'idle' | 'thinking' | 'tool' | 'waiting' | 'done' | 'error'

export interface SeatState {
  mood: Mood
  task: string | null // what they were asked
  said: string | null // latest thing they said
  tool: ToolCall | null // what they're doing right now
  tools: Record<string, number> // tools used this run
  report: Record<string, unknown> | null // final AgentReport / TicketOutcome
  handoffsTo: AgentName[]
  calledBy: AgentName | null
}

export interface Wire {
  from: AgentName
  to: AgentName
  task: string
  done: boolean
}

export interface TableView {
  seats: Record<AgentName, SeatState>
  wires: Wire[]
  active: AgentName | null
  finished: boolean
  failed: string | null
  tokens: number
}

const blankSeat = (): SeatState => ({
  mood: 'idle', task: null, said: null, tool: null, tools: {}, report: null, handoffsTo: [], calledBy: null,
})

export function buildView(events: AgentEvent[]): TableView {
  const seats = Object.fromEntries(AGENT_ORDER.map((a) => [a, blankSeat()])) as Record<AgentName, SeatState>
  const wires: Wire[] = []
  const runAgent = new Map<string, AgentName>()
  let active: AgentName | null = null
  let finished = false
  let failed: string | null = null
  let tokens = 0

  for (const e of events) {
    const s = seats[e.agent]
    if (!s) continue
    if (e.cumulative_usage) tokens = e.cumulative_usage.input_tokens + e.cumulative_usage.output_tokens
    switch (e.event) {
      case 'run_start': {
        runAgent.set(e.run_id, e.agent)
        s.mood = 'thinking'
        s.task = e.said
        s.tool = null
        const parent = e.parent_run_id ? runAgent.get(e.parent_run_id) ?? null : null
        s.calledBy = parent
        active = e.agent
        break
      }
      case 'model_response': {
        if (e.said) s.said = e.said
        const calls = e.tool_calls ?? []
        const real = calls.find((c) => c.tool !== 'final_result') ?? calls[0] ?? null
        s.tool = real
        for (const c of calls) s.tools[c.tool] = (s.tools[c.tool] ?? 0) + 1
        for (const d of e.delegations ?? []) {
          if (!d.to) continue
          wires.push({ from: e.agent, to: d.to, task: d.task, done: false })
          if (!s.handoffsTo.includes(d.to)) s.handoffsTo.push(d.to)
        }
        s.mood = e.delegations?.length ? 'waiting' : calls.length ? 'tool' : 'thinking'
        active = e.agent
        break
      }
      case 'tool_results':
        s.mood = 'thinking'
        s.tool = null
        active = e.agent
        break
      case 'run_retry':
        s.said = 'Ran long thinking. Asked for the short version of the answer.'
        break
      case 'delegation_refused':
        s.said = `Hand-off refused by a guardrail: ${e.said ?? ''}`
        break
      case 'run_end': {
        s.mood = 'done'
        s.tool = null
        s.report = e.output
        const parent = e.parent_run_id ? runAgent.get(e.parent_run_id) : undefined
        if (parent) {
          const w = [...wires].reverse().find((x) => x.from === parent && x.to === e.agent && !x.done)
          if (w) w.done = true
          active = parent
        } else {
          finished = true
          active = null
        }
        break
      }
      case 'run_error':
        s.mood = 'error'
        s.said = e.error ?? e.said
        if (e.depth === 0) {
          failed = e.error ?? 'The run failed.'
          active = null
        }
        break
    }
  }
  return { seats, wires, active, finished, failed, tokens }
}

/** Events of the most recent run on a ticket (from its last Boss run_start onward). */
export function latestRun(all: AgentEvent[], ticketId: number): AgentEvent[] {
  let start = -1
  for (let i = all.length - 1; i >= 0; i--) {
    const e = all[i]
    if (e.ticket_id === ticketId && e.depth === 0 && e.event === 'run_start') {
      start = i
      break
    }
  }
  if (start < 0) return []
  return all.slice(start).filter((e) => e.ticket_id === ticketId)
}

// ---------------------------------------------------------------------------
// Money helpers
// ---------------------------------------------------------------------------

export const money = (n: number) =>
  n.toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 })

const ONES = ['', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven',
  'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen']
const TENS = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety']

function under1000(n: number): string {
  const h = Math.floor(n / 100)
  const r = n % 100
  const parts: string[] = []
  if (h) parts.push(`${ONES[h]} hundred`)
  if (r >= 20) parts.push(TENS[Math.floor(r / 10)] + (r % 10 ? `-${ONES[r % 10]}` : ''))
  else if (r) parts.push(ONES[r])
  return parts.join(' ')
}

/** 2400 -> "Two thousand four hundred and 00/100" (how a real check spells it out). */
export function checkWords(amount: number): string {
  const dollars = Math.floor(amount)
  const cents = Math.round((amount - dollars) * 100)
  const th = Math.floor(dollars / 1000)
  const rest = dollars % 1000
  let words = [th ? `${under1000(th)} thousand` : '', rest ? under1000(rest) : ''].filter(Boolean).join(' ')
  if (!words) words = 'zero'
  return `${words[0].toUpperCase()}${words.slice(1)} and ${String(cents).padStart(2, '0')}/100`
}
