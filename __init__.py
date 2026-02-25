from importlib import import_module
import sys

from .aiophyn import HomeInventory, async_get_api

_SUBMODULES = [
	"api",
	"const",
	"device",
	"errors",
	"home",
	"home_inventory",
	"mqtt",
]

for _submodule in _SUBMODULES:
	_module = import_module(f".aiophyn.{_submodule}", __name__)
	sys.modules[f"{__name__}.{_submodule}"] = _module

__all__ = ["async_get_api", "HomeInventory"]
