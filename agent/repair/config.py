"""Configuration for the repair pipeline: routing.yml, prices.yml and environment variables. No secrets are read here
except through the Anthropic SDK, which reads ANTHROPIC_API_KEY from the environment itself."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"
DEFAULT_MODEL = "claude-haiku-5-5"   # current small model; see docs/decisions/agent.md (checked 2026-10-30)


class ConfigError(Exception):
    pass


def load_routing(path: Path = CONFIG_DIR / "routing.yml") -> dict:
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    cfg["max_cost_usd_per_payment"] = float(os.environ.get("MAX_COST_USD_PER_PAYMENT", cfg["max_cost_usd_per_payment"]))
    return cfg


@dataclass
class Prices:
    table: dict
    checked: str

    @classmethod
    def load(cls, path: Path = CONFIG_DIR / "prices.yml") -> "Prices":
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls(data["models"], str(data.get("checked", "")))

    def cost(self, model: str, tokens_in: int, tokens_out: int) -> float:
        p = self.table.get(model)
        if p is None:
            raise ConfigError(f"no price for model '{model}' in agent/config/prices.yml")
        long = p.get("long_prompt_tokens")
        if long and tokens_in > long:
            rin, rout = p["long_input_per_mtok"], p["long_output_per_mtok"]
        else:
            rin, rout = p["input_per_mtok"], p["output_per_mtok"]
        return (tokens_in * rin + tokens_out * rout) / 1_000_000


def model_from_env() -> str:
    return os.environ.get("PAYSTRUCT_MODEL", DEFAULT_MODEL)


def run_budget_usd() -> float:
    return float(os.environ.get("PAYSTRUCT_RUN_BUDGET_USD", "2.00"))
