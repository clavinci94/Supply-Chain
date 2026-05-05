"""Retailer agent — Demand-driven base-stock with damped pull.

Self-contained: depends only on supplychainbench.sdk + Python stdlib.

Algorithm (classical inventory theory):

    forecast  = mean of last WINDOW incoming orders          (smoothed demand)
    target    = forecast * (LEAD_TIME + 1)                   (base-stock target)
    position  = on_hand + incoming_shipment + pipeline - backlog
    gap       = (target - position) / DAMPING_HORIZON
    order     = max(0, round(forecast + gap))

Both target and order scale automatically with the demand level. The policy
makes no assumption about the specific demand distribution — only about the
engine's effective round-trip lead time.

Per-tier parameters:

* LEAD_TIME = 4         — bench's effective round-trip (order delay + ship delay).
                          Engine-specific, not scenario-specific.
* DAMPING_HORIZON = 48  — much longer than LEAD_TIME so each tick's gap
                          correction stays sub-unit. Prevents the bullwhip
                          spike that aggressive base-stock chasing creates.
* WINDOW = 1    — moving-average length. Grows upstream because each
                          tier sits one filter further from real customer
                          demand; smoothing more there pays off in bullwhip
                          damping more than it costs in lag.
* PRIOR_DEMAND = 5      — neutral seed for the buffer; replaced by real
                          observations after WINDOW ticks.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from supplychainbench.sdk import Agent, AgentDecision, LocalObservation, Message


class RetailerAgent(Agent):
    LEAD_TIME = 4
    DAMPING_HORIZON = 48
    WINDOW = 1
    PRIOR_DEMAND = 5

    def reset(self, *, role: str, config: dict[str, Any], seed: int) -> None:
        super().reset(role=role, config=config, seed=seed)
        # Prime the buffer so early-tick forecasts are stable.
        self._buf: deque[int] = deque(
            [self.PRIOR_DEMAND] * self.WINDOW, maxlen=self.WINDOW
        )

    def step(
        self,
        observation: LocalObservation,
        inbox: list[Message],
        t: int,
    ) -> AgentDecision:
        self._buf.append(observation.incoming_order_qty)
        forecast = sum(self._buf) / len(self._buf)

        # Base-stock target scales with current demand level. No fixed
        # assumption about steady-state — works for any demand mean.
        target = forecast * (self.LEAD_TIME + 1)

        position = (
            observation.inventory_on_hand
            + observation.incoming_shipment_qty
            + observation.pipeline_inventory
            - observation.backlog
        )

        # Damped pull: spread the position gap over DAMPING_HORIZON ticks so
        # no single tick injects a spike. Cumulatively the gap is closed.
        gap_per_tick = (target - position) / self.DAMPING_HORIZON

        order = forecast + gap_per_tick
        return AgentDecision(order_qty=max(0, int(round(order))))
