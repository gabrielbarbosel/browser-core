from __future__ import annotations

from typing import Iterable, List

from .element_proxy import ElementProxy


class ElementListProxy(list):
    """Representa uma lista de ElementProxy com operações agregadas."""

    def __init__(self, elements: Iterable[ElementProxy]):
        super().__init__(elements)

    def get_attributes(self, name: str) -> List[str]:
        """Retorna uma lista com o valor do atributo para cada elemento."""
        return [el.get_attribute(name) for el in self]

    def get_texts(self) -> List[str]:
        """Retorna o texto de cada elemento."""
        return [el.text for el in self]
