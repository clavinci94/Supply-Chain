# Supply Chain Bundle — `team_bundle`

A four-tier supply chain agent bundle for the FHNW Supply Chain Management
module S09. Built by a 5-person team owning all four tiers.

## The four agents

```
team_bundle/
├── retailer/agent.py        Agent 1 — sees real customer demand
├── wholesaler/agent.py      Agent 2 — between retailer and distributor
├── distributor/agent.py     Agent 3 — between wholesaler and factory
└── factory/agent.py         Agent 4 — most upstream; order_qty = production starts
```

Each tick the bench harness gives every agent a `LocalObservation`
(its own inventory, backlog, the order it just received, the shipment
about to arrive, its pipeline, a bounded history window, and its
costs to date) and the agent returns an `AgentDecision` with one
field that matters: `order_qty`.

## How they coordinate

The Phase-1 message bus is a no-op (verified in the SDK source:
*"messages are recorded but not delivered; Phase 2 wires the typed
delivery semantics"*). The four tiers therefore coordinate
**implicitly** — every tier runs the same algorithm with the same
constants, so each tier can rely on the others to behave predictably
without explicit messages.

The only role-specific parameter is `WINDOW` (the moving-average
length): `1` at the retailer + wholesaler, `3` at the distributor +
factory. Bullwhip principle: smooth more the further you sit from
the real customer demand.

## The algorithm — Demand-driven base-stock with damped pull

Every tier runs this rule (only `WINDOW` differs):

```
forecast  = mean of last WINDOW incoming orders            # smoothed demand
target    = forecast × (LEAD_TIME + 1)                     # base-stock target
position  = on_hand + incoming_shipment + pipeline − backlog
gap       = (target − position) / DAMPING_HORIZON
order     = max(0, round(forecast + gap))
```

Two ideas in one formula:

* **Forecast term** — orders track recent demand. `WINDOW = 1` at
  the retailer means "react fast to the customer", `WINDOW = 3`
  upstream means "filter out the noise that downstream tiers leak".
* **Damped pull term** — gently steers inventory position toward
  the base-stock target. `DAMPING_HORIZON = 48` is much longer than
  `LEAD_TIME = 4`, so each tick's correction is sub-unit. This
  prevents the bullwhip spike that aggressive base-stock chasing
  creates.

`target` scales **automatically** with the demand level: at mean=5
the target is 25, at mean=12 the target is 60. No assumption about
which scenario will be graded — the policy adapts to whatever
demand shows up.

## Build path

Plain Python. No framework, no LLM calls, no tool calls, no
inter-tier messages. The decision architecture is **rules +
calculations** — a single ~10-line formula per tier.

LLM calls were considered and rejected: the bench's composite score
penalises tokens directly (geometric mean against a baseline of zero
tokens), so an LLM would have to make decisions dramatically better
than this formula to break even. For a four-tier inventory game
where the optimal action is a closed-form base-stock policy, that's
not realistic.

## Run locally

### macOS (bash / zsh)

```bash
# Install the bench wheel (provided separately by the course)
pip install supplychainbench_student-0_3_0-py3-none-any.whl

# Validate the bundle (5-tick smoke test)
supplychainbench test-bundle team_bundle
# Expected: OK

# Run a scenario
supplychainbench run-scenario --bundle team_bundle \
    --scenario s1.1 --seed 0 --out runs \
    --class-run-id dev --team-id $(jq -r .team_id team_bundle/manifest.json)

# Read metrics
supplychainbench metrics --class-run-id dev --out runs
```

### Windows (PowerShell)

```powershell
# Install the bench wheel (provided separately by the course)
pip install supplychainbench_student-0_3_0-py3-none-any.whl

# Validate the bundle (5-tick smoke test)
supplychainbench test-bundle team_bundle
# Expected: OK

# Run a scenario (read team_id without jq; use backtick for line continuation)
$teamId = (Get-Content team_bundle/manifest.json | ConvertFrom-Json).team_id
supplychainbench run-scenario --bundle team_bundle `
    --scenario s1.1 --seed 0 --out runs `
    --class-run-id dev --team-id $teamId

# Read metrics
supplychainbench metrics --class-run-id dev --out runs
```

## File structure

```
team_bundle/
├── manifest.json                 # team_id, team_name, sdk_version
├── README.md                     # this file
├── retailer/
│   ├── agent.py                  # RetailerAgent
│   └── agent.yaml                # role manifest (memory_mode, entrypoint)
├── wholesaler/
│   ├── agent.py                  # WholesalerAgent
│   └── agent.yaml
├── distributor/
│   ├── agent.py                  # DistributorAgent
│   └── agent.yaml
├── factory/
│   ├── agent.py                  # FactoryAgent
│   └── agent.yaml
└── tests/
    └── test_local.py             # validator + smoke test (from starter)
```

Four agents (the four `agent.py` files), four role manifests (the
four `agent.yaml` files — metadata only, no code), one bundle
manifest, one README, one starter test. Eleven files total.

## Design discipline

The local scenarios `s1.1` (stable demand) and `s2.3` (step shock)
were used during development to understand how the bench engine
behaves — what `incoming_shipment_qty` actually means tick-by-tick,
how `pipeline_inventory` accounts for orders in transit, what the
effective round-trip lead time is. They were **not** treated as
optimization targets. The grading runs on a separate, unseen
scenario at the cluster, and a policy that overfits constants to
two visible scenarios would likely fail there.

Concretely: this bundle has no `SHOCK_THRESHOLD`, no `SHOCK_MULT`,
no fixed `TARGET_BASE`. The four constants in the code are:

| Constant | Value | Why |
|---|---|---|
| `LEAD_TIME` | 4 | Engine-specific (order delay + ship delay). Same for any scenario. |
| `DAMPING_HORIZON` | 48 | ≫ `LEAD_TIME`, so per-tick gap correction stays sub-unit. Theoretical, not fitted. |
| `WINDOW` | 1 / 1 / 3 / 3 (per tier) | Bullwhip principle: smooth more the further from real demand. |
| `PRIOR_DEMAND` | 5 | Neutral seed; replaced by real observations within `WINDOW` ticks. |

