from typing import Type

from .base import PluginAgent

_REGISTRY: dict[str, Type[PluginAgent]] = {}


def register_plugin(cls: Type[PluginAgent]) -> Type[PluginAgent]:
    _REGISTRY[cls.name] = cls
    return cls


def get_plugin(name: str) -> Type[PluginAgent]:
    return _REGISTRY[name]


def all_plugins() -> dict[str, Type[PluginAgent]]:
    return dict(_REGISTRY)
