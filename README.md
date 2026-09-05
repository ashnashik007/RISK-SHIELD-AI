# RiskShield AI — Working Full-Stack Prototype

RiskShield doesn't just score a transaction and stop. It runs a closed
loop:

```
DETECT → INVESTIGATE → DECIDE → CHECK (policy) → EXECUTE → VERIFY
```

1. **Detect** — a transparent, rule-based engine scores every transaction
   0-100 from explainable signals (amount deviation, velocity, device,
   location, beneficiary, time-of-day, customer history).
2. **Investigate** — the signals are turned into plain-language evidence
   and a root-cause narrative (why the risk exists, not just that it
   exists).
3. **Decide** — the risk band and evidence pick a recommended action
   from a fixed catalog (monitor / flag / request verification / hold /
   freeze account).
4. **Check** — the action is checked against the Policy Guard's
   autonomous-action allowlist. High-impact actions outside the
   allowlist are routed to a human for approval instead of running.
5. **Execute** — the (simulated) action is applied and the transaction's
   status changes.
6. **Verify** — the transaction is re-scored to check whether the action
   actually reduced the risk. If it didn't, the case is escalated
   instead of silently closed.

Every one of those six stages writes a row to the audit trail, so any
decision is fully reconstructable afterwards (Audit Trail page).

This is a **simulation**: no real bank, payment network, or customer
data is touched. "Freeze account" etc. only change a status field in
the local database.

## What's real here

- A FastAPI backend with a SQLite database that actually persists every
  transaction, investigation, policy change and audit-log entry.
- The Policy Guard is real: change a threshold or an autonomy toggle on
  the Policy Guard page and the **next** transaction routes differently.
- The Risk Simulator runs the same backend pipeline as live traffic —
  it isn't a separate mocked calculation.
- "Live monitoring" is a real Server-Sent-Events stream from the
  backend, not a client-side `setInterval` faking activity.
- Analytics (category risk bars, autonomous-action rate, verification
  pass rate, escalation rate) are computed from the actual stored data,
  not hardcoded numbers.
- Optional: set `ANTHROPIC_API_KEY` and the Investigate stage will ask
  Claude to write the root-cause narrative from the same structured
  evidence, instead of the deterministic template. Everything else
  (scoring, policy, execution, verification) stays deterministic either
  way — the model never controls money or policy, only prose.

## Run it

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open **http://127.0.0.1:8000** — the backend serves the frontend
directly, so that's the whole app (dashboard + API).

The database (`backend/riskshield.db`) is created and seeded with six
sample customers/transactions automatically on first run. Delete that
file to reset to a fresh seeded state.

Interactive API docs: **http://127.0.0.1:8000/docs**

## Project layout

```
riskshield-ai/
├── backend/
│   ├── requirements.txt
│   └── app/
│       ├── main.py              FastAPI app, mounts the frontend
│       ├── database.py          SQLite/SQLAlchemy setup
│       ├── models.py            Customer, Transaction, Investigation,
│       │                        AuditLog, Policy
│       ├── schemas.py           Pydantic request/response models
│       ├── seed.py              Seed customers + initial transactions
│       ├── engine/
│       │   ├── risk_engine.py   Stage 1: DETECT (scoring)
│       │   ├── investigator.py  Stage 2: INVESTIGATE (evidence + why)
│       │   ├── policy_engine.py Stage 3-4: DECIDE + CHECK (policy gate)
│       │   ├── executor.py      Stage 5: EXECUTE (simulated)
│       │   ├── verifier.py      Stage 6: VERIFY (did risk actually drop)
│       │   ├── pipeline.py      Orchestrates the six stages + audit log
│       │   └── generator.py     Synthetic transaction generator
│       └── routers/             transactions, investigations, simulate,
│                                 policies, analytics, audit, stream
└── frontend/
    ├── index.html
    ├── styles.css
    └── app.js                   Calls the API above for every page —
                                  no local mock data
```

## Try the closed loop yourself

1. **Transactions → Generate transaction** a few times until one comes
   back medium/high/critical risk.
2. **Investigations** — open the card. Read the evidence and the "Why"
   root-cause explanation. If it says "Pending approval", click
   **Review & approve action** and watch the before/after score.
3. **Policy Guard** — turn off autonomy for an action, or lower a
   threshold, hit **Save policies**, then generate more transactions —
   routing changes immediately.
4. **Risk Simulator** — build a specific scenario by hand, **Analyze
   with AI**, then **Execute safe simulation** to run stages 5-6 and see
   the verified before/after risk.
5. **Audit Trail** — see every detect/investigate/decide/check/execute/
   verify event, in order, across every case above.

## Limitations, honestly

- Risk scoring is a transparent rule-based engine, not a trained ML
  model — there's no historical ground-truth dataset to train or
  evaluate a classifier against, so no precision/recall/F1 numbers are
  shown (those would have to be fabricated). What's shown instead
  (autonomous-action rate, verification pass rate, escalation rate) is
  computed from real recorded case outcomes.
- Single-process SQLite is intentional for a runnable-anywhere prototype,
  not a production data layer.
- "Execute" actions only change local database state; nothing external
  is contacted.
