"""Per-country routing of the debt engine (R0 step 8, D-S15-008): every
engine entry point asks `config/debt.yaml` `countries` which module builds
a country's register, aggregates and official totals, which source carries
its sub-sector chain items and how V31 cross-checks its stock. A country
that is not configured raises `DebtCountryNotConfigured` — the engine never
runs another country's path for it.
"""

from __future__ import annotations

import importlib

from ggfiscal import config


class DebtCountryNotConfigured(LookupError):
    """The country has no entry in config/debt.yaml `countries`."""


def configured() -> dict[str, dict]:
    """iso3 -> engine config, in the file's order (the concatenation order)."""
    return dict(config.debt().get("countries") or {})


def country_cfg(iso3: str) -> dict:
    cfg = configured().get(iso3)
    if cfg is None:
        raise DebtCountryNotConfigured(
            f"{iso3}: no entry in config/debt.yaml `countries` "
            f"(configured: {', '.join(configured()) or 'none'}); the debt engine "
            "builds only countries declared there")
    return cfg


def resolve(spec: str, default_function: str):
    """`module` or `module:function` under ggfiscal.debt -> the callable;
    ImportError / AttributeError propagate with the spec named."""
    module, _, function = spec.partition(":")
    try:
        mod = importlib.import_module(f"ggfiscal.debt.{module}")
    except ImportError as e:
        raise ImportError(f"debt module {module!r} (from spec {spec!r}) cannot be imported: {e}") from e
    fn = getattr(mod, function or default_function, None)
    if fn is None:
        raise AttributeError(f"ggfiscal.debt.{module} has no {function or default_function!r} (spec {spec!r})")
    return fn


def builder(iso3: str, role: str, default_function: str):
    """The callable for one role (register / aggregates / official_totals)
    of one country, or None where the country declares none for it."""
    spec = country_cfg(iso3).get(role)
    return resolve(spec, default_function) if spec else None
