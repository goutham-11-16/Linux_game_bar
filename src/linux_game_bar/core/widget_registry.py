"""Widget registry and lifecycle descriptors."""

from dataclasses import dataclass
from typing import Dict, Type, Callable, Optional, List
from PySide6.QtWidgets import QWidget


@dataclass
class WidgetDescriptor:
    widget_id: str
    name: str
    icon_name: str
    description: str
    factory: Callable[[], QWidget]
    default_x: int = 100
    default_y: int = 100
    default_width: int = 320
    default_height: int = 400
    is_available: bool = True
    unavailable_reason: Optional[str] = None


class WidgetRegistry:
    """Central registry of all dashboard widgets."""

    def __init__(self):
        self._descriptors: Dict[str, WidgetDescriptor] = {}

    def register(self, descriptor: WidgetDescriptor) -> None:
        self._descriptors[descriptor.widget_id] = descriptor

    def get(self, widget_id: str) -> Optional[WidgetDescriptor]:
        return self._descriptors.get(widget_id)

    def get_all(self) -> List[WidgetDescriptor]:
        return list(self._descriptors.values())

    def get_available(self) -> List[WidgetDescriptor]:
        return [d for d in self._descriptors.values() if d.is_available]
