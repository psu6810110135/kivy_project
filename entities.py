from dataclasses import dataclass
from typing import Tuple

from kivy.graphics import Rectangle, Color
from kivy.vector import Vector


@dataclass
class Entity:
    pos: Vector
    size: Tuple[float, float]
    color: Tuple[float, float, float]

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


class PlayerEntity(Entity):
    def __init__(self, pos: Vector):
        super().__init__(pos=pos, size=(50, 50), color=(0.2, 0.9, 0.3))
