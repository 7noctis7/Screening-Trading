"""Registry générique — colonne vertébrale de l'architecture en plugins.

Objectif (cf. 01_ARCHITECTURE.md, règles d'or 4) : ajouter une stratégie /
un indicateur / un exchange / un facteur = créer **un fichier qui s'auto-
enregistre**, jamais modifier le cœur.

Usage :
    from packages.core.registry import Registry
    strategies = Registry[Strategy]("strategy")

    @strategies.register("ma_crossover")
    class MaCrossover(Strategy): ...

    obj = strategies.create("ma_crossover", fast=20, slow=50)
"""

from __future__ import annotations

from typing import Callable, Generic, Iterator, TypeVar

T = TypeVar("T")


class Registry(Generic[T]):
    """Registre typé. Une instance par famille (strategy, indicator, factor...)."""

    def __init__(self, kind: str) -> None:
        self._kind = kind
        self._items: dict[str, type[T]] = {}

    def register(self, name: str) -> Callable[[type[T]], type[T]]:
        """Décorateur d'auto-enregistrement."""

        def _decorator(cls: type[T]) -> type[T]:
            key = name.lower()
            if key in self._items:
                raise ValueError(f"{self._kind} '{name}' déjà enregistré")
            self._items[key] = cls
            return cls

        return _decorator

    def get(self, name: str) -> type[T]:
        key = name.lower()
        if key not in self._items:
            raise KeyError(
                f"{self._kind} '{name}' introuvable. "
                f"Disponibles : {sorted(self._items)}"
            )
        return self._items[key]

    def create(self, name: str, **kwargs: object) -> T:
        """Instancie le plugin par son nom + kwargs (config-driven YAML)."""
        return self.get(name)(**kwargs)  # type: ignore[call-arg]

    def names(self) -> list[str]:
        return sorted(self._items)

    def __contains__(self, name: str) -> bool:
        return name.lower() in self._items

    def __iter__(self) -> Iterator[str]:
        return iter(sorted(self._items))

    def __len__(self) -> int:
        return len(self._items)
