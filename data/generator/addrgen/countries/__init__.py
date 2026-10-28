"""Country registry. Importing this package imports every country module, which registers itself."""
from __future__ import annotations

import importlib
import pkgutil

from addrgen.countries.base import _REGISTRY, CountryModule

for _module in pkgutil.iter_modules(__path__):
    if _module.name != "base":
        importlib.import_module(f"{__name__}.{_module.name}")


def codes() -> list[str]:
    return sorted(_REGISTRY)


def get(code: str) -> CountryModule:
    try:
        return _REGISTRY[code.upper()]
    except KeyError:
        raise KeyError(f"No country module for {code!r}; available: {', '.join(codes())}") from None
