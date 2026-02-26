from dataclasses import dataclass, field
from typing import Tuple

from kivy.graphics import Color, Rectangle
from kivy.vector import Vector

from status_system import StatusComponent


@dataclass
class Entity:
    pos: Vector
    size: Tuple[float, float]
    color: Tuple[float, float, float]
    status: StatusComponent = field(default_factory=StatusComponent)

    def draw(self, canvas):
        Color(*self.color)
        Rectangle(pos=self.pos, size=self.size)

    @property
    def x(self) -> float:
        return self.pos.x

    @property
    def y(self) -> float:
        return self.pos.y

    def move(self, delta: Vector):
        self.pos = self.pos + delta

    def update_statuses(self, dt: float):
        self.status.update(dt)

    def add_status(self, name: str, duration: float, potency: float = 1.0, stacks: int = 1, modifiers=None):
        return self.status.add(name, duration, potency=potency, stacks=stacks, modifiers=modifiers)

    def has_status(self, name: str) -> bool:
        return self.status.has(name)

    def remove_status(self, name: str):
        self.status.remove(name)

    def get_status_multiplier(self, stat_name: str, default: float = 1.0) -> float:
        return self.status.get_multiplier(stat_name, default=default)
