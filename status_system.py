from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class StatusEffect:
    name: str
    duration: float
    potency: float = 1.0
    stacks: int = 1
    modifiers: Dict[str, float] = field(default_factory=dict)


class StatusComponent:
    """Generic timed status container for combat entities."""

    def __init__(self):
        self._effects: Dict[str, StatusEffect] = {}

    def add(
        self,
        name: str,
        duration: float,
        potency: float = 1.0,
        stacks: int = 1,
        modifiers: Optional[Dict[str, float]] = None,
        refresh_duration: bool = True,
    ) -> StatusEffect:
        if name in self._effects:
            effect = self._effects[name]
            if refresh_duration:
                effect.duration = max(effect.duration, duration)
            effect.stacks += stacks
            effect.potency = max(effect.potency, potency)
            if modifiers:
                effect.modifiers.update(modifiers)
            return effect

        effect = StatusEffect(
            name=name,
            duration=duration,
            potency=potency,
            stacks=stacks,
            modifiers=modifiers or {},
        )
        self._effects[name] = effect
        return effect

    def remove(self, name: str):
        self._effects.pop(name, None)

    def has(self, name: str) -> bool:
        return name in self._effects

    def get(self, name: str) -> Optional[StatusEffect]:
        return self._effects.get(name)

    def update(self, dt: float):
        expired = []
        for name, effect in self._effects.items():
            effect.duration -= dt
            if effect.duration <= 0:
                expired.append(name)
        for name in expired:
            del self._effects[name]

    def get_multiplier(self, stat_name: str, default: float = 1.0) -> float:
        value = default
        for effect in self._effects.values():
            if stat_name in effect.modifiers:
                value *= effect.modifiers[stat_name]
        return value

    def to_dict(self) -> Dict[str, Dict]:
        return {
            name: {
                "duration": effect.duration,
                "potency": effect.potency,
                "stacks": effect.stacks,
                "modifiers": dict(effect.modifiers),
            }
            for name, effect in self._effects.items()
        }
