"""Trust Rails: budget cap, attempt cap, wall-clock timeout, kill switch. Every rail that fires is logged."""
import time


class RailFired(Exception):
    def __init__(self, rail: str, detail: str = ""):
        super().__init__(f"{rail}: {detail}")
        self.rail = rail
        self.detail = detail


class Rails:
    def __init__(self, budget_usd: float, max_attempts: int, timeout_s: float):
        self.budget_usd = budget_usd
        self.max_attempts = max_attempts
        self.timeout_s = timeout_s
        self.killed = False
        self.fired: list[dict] = []
        self._t0 = time.monotonic()

    def fire(self, rail: str, detail: str = "") -> dict:
        rec = {"rail": rail, "detail": detail, "t": round(time.monotonic() - self._t0, 2)}
        self.fired.append(rec)
        return rec

    def kill(self):
        self.killed = True

    def check_kill(self):
        if self.killed:
            raise RailFired("kill_switch", "stopped by operator")

    def check_budget(self, stats):
        if stats.cost_usd is not None and isinstance(stats.cost_usd, (int, float)):
            if stats.cost_usd >= self.budget_usd:
                raise RailFired("budget", f"spent ${stats.cost_usd:.6f} of ${self.budget_usd:.6f} cap")

    def check_time(self):
        if time.monotonic() - self._t0 >= self.timeout_s:
            raise RailFired("timeout", f"exceeded {self.timeout_s}s wall clock")

    def summary(self) -> dict:
        return {
            "budget_usd": self.budget_usd,
            "max_attempts": self.max_attempts,
            "timeout_s": self.timeout_s,
            "sandbox": "network blocked, 15s check timeout, generated code only ever opened in headless Chromium",
            "approval_gate": "human approval required before a build is marked Approved",
            "fired": self.fired,
        }
