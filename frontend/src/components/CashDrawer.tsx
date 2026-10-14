import { useState } from 'react'
import type { Cash, PaymentRequest } from '../api'
import { checkWords, money } from '../agents'

/** Rolling-digit balance: each digit is a little drum that turns when the number changes. */
export function Odometer({ value }: { value: number }) {
  const text = money(value)
  return (
    <span className="odometer" aria-label={text}>
      {[...text].map((ch, i) =>
        /\d/.test(ch) ? (
          <span key={i} className="drum">
            <span className="drum-strip" style={{ transform: `translateY(-${Number(ch) * 10}%)` }}>
              {'0123456789'.split('').map((d) => (
                <span key={d}>{d}</span>
              ))}
            </span>
          </span>
        ) : (
          <span key={i} className="drum-sep">{ch}</span>
        ),
      )}
    </span>
  )
}

interface Props {
  cash: Cash | null
  requests: PaymentRequest[]
  signer: string
  setSigner: (s: string) => void
  onApprove: (r: PaymentRequest) => Promise<string | null>
  onReject: (r: PaymentRequest) => Promise<string | null>
  busy: boolean
  dropped: number | null
}

const KIND = { invoice: 'Vendor invoice', rent: 'Rent', purchase_order: 'Purchase order' } as const

export function CashDrawer({ cash, requests, signer, setSigner, onApprove, onReject, busy, dropped }: Props) {
  const balance = cash?.balance ?? 0
  const pending = requests.reduce((s, r) => s + r.amount, 0)
  const after = balance - pending
  const pct = (n: number) => `${Math.max(0, Math.min(100, (n / Math.max(balance, 1)) * 100))}%`

  return (
    <aside className="drawer">
      <div className="drawer-head">
        <span className="eyebrow">Checking account</span>
        <span className="asof">as of shop date {cash?.as_of ?? '…'}</span>
      </div>
      <div className={`balance ${dropped !== null ? 'just-dropped' : ''}`}>
        <Odometer value={balance} />
        {dropped !== null && <span className="drop">−{money(dropped)}</span>}
      </div>

      <div className="runway" title="How much of the balance the checks on your desk would use">
        <div className="runway-bar">
          {requests.map((r) => (
            <span key={r.request_id} className={`seg seg-${r.kind}`} style={{ width: pct(r.amount) }} title={`#${r.request_id} ${money(r.amount)}`} />
          ))}
        </div>
        <div className="runway-legend">
          <span>{requests.length ? `${money(pending)} waiting for your signature` : 'No checks waiting'}</span>
          <strong className={after < 0 ? 'neg' : ''}>{money(after)} left if you sign all</strong>
        </div>
        {after < 0 && <p className="runway-warn">Not enough cash for every check. The bank will refuse the last one.</p>}
      </div>

      <div className="checks-head">
        <span className="eyebrow">Checks to sign</span>
        <label className="signer">
          <span>Signing as</span>
          <input value={signer} onChange={(e) => setSigner(e.target.value)} placeholder="your name" aria-label="Your name for signing" />
        </label>
      </div>
      {requests.length === 0 && <p className="nothing">Nothing to sign. The agents only write checks; you're the one who signs them.</p>}
      {requests.map((r) => (
        <Check key={r.request_id} r={r} signer={signer} setSigner={setSigner} busy={busy} onApprove={onApprove} onReject={onReject} />
      ))}

      <div className="tape">
        <span className="eyebrow">Register tape</span>
        {cash?.payments_made.length ? (
          <ul>
            {cash.payments_made.map((p) => (
              <li key={p.payment_id}>
                <span>{p.paid_at}</span>
                <span>{p.kind === 'invoice' ? `INV ${p.ref_id}` : p.kind === 'rent' ? `RENT L${p.ref_id}` : `PO ${p.ref_id}`}</span>
                <span>−{money(p.amount)}</span>
                <span className="by">ok {p.approved_by}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="tape-empty">— no payments today —</p>
        )}
      </div>
    </aside>
  )
}

function Check({ r, signer, setSigner, busy, onApprove, onReject }: {
  r: PaymentRequest
  signer: string
  setSigner: (s: string) => void
  busy: boolean
  onApprove: Props['onApprove']
  onReject: Props['onReject']
}) {
  const [error, setError] = useState<string | null>(null)
  const [paid, setPaid] = useState(false)
  const [working, setWorking] = useState(false)
  const signed = signer.trim().length > 1

  async function act(fn: Props['onApprove']) {
    setWorking(true)
    setError(null)
    const err = await fn(r)
    setWorking(false)
    if (err) setError(err)
    else if (fn === onApprove) setPaid(true)
  }

  return (
    <div className={`check ${paid ? 'is-paid' : ''}`}>
      <div className="check-top">
        <span className="check-kind">{KIND[r.kind]} · ticket {r.ticket_id}</span>
        <span className="check-no">No. {String(r.request_id).padStart(4, '0')}</span>
      </div>
      <div className="check-pay">
        <span className="check-label">Pay to the order of</span>
        <span className="check-payee">{r.payee ?? '—'}</span>
        <span className="check-amount">{money(r.amount)}</span>
      </div>
      <div className="check-words">{checkWords(r.amount)} dollars</div>
      <div className="check-memo">
        <span className="check-label">Memo</span> {r.reason}
      </div>
      <div className="check-sign">
        <input
          className="signature"
          value={signer}
          onChange={(e) => setSigner(e.target.value)}
          placeholder="type your name to sign"
          aria-label="Your signature"
        />
        <span className="check-label">Prepared by {r.requested_by} · needs a human signature</span>
      </div>
      {error && <p className="check-error">{error}</p>}
      {!signed && <p className="check-hint">Type your name on the signature line to enable Sign & pay.</p>}
      {signed && busy && <p className="check-hint">The team is working on a ticket. You can sign as soon as the run ends.</p>}
      <div className="check-actions">
        <button className="btn-void" disabled={busy || working || !signed} onClick={() => act(onReject)}>
          Void
        </button>
        <button className="btn-sign" disabled={busy || working || !signed} onClick={() => act(onApprove)}>
          {working ? 'Paying…' : `Sign & pay ${money(r.amount)}`}
        </button>
      </div>
      {paid && <span className="stamp stamp-in paid">Paid</span>}
    </div>
  )
}
