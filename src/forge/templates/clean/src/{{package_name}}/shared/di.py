from __future__ import annotations
from typing import Callable, Dict, Any, Type

class Container:
    def __init__(self):
        self._providers: Dict[str, Callable[[], Any]] = {}
        self._singletons: Dict[str, Any] = {}

    def register(self, key: str, provider: Callable[[], Any], *, singleton: bool = True):
        if singleton:
            def _single():
                if key not in self._singletons:
                    self._singletons[key] = provider()
                return self._singletons[key]
            self._providers[key] = _single
        else:
            self._providers[key] = provider

    def get(self, key: str) -> Any:
        return self._providers[key]()

    def factory(self, cls: Type, /, **deps_keys: str):
        def _factory():
            deps = {name: self.get(dep_key) for name, dep_key in deps_keys.items()}
            return cls(**deps)
        return _factory