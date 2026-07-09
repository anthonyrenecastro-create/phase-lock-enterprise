from dataclasses import dataclass, field
from typing import Protocol


class StreamAdapter(Protocol):
    def publish(self, topic: str, payload: dict[str, object]) -> None:
        pass


@dataclass
class InMemoryStreamAdapter:
    topics: dict[str, list[dict[str, object]]] = field(default_factory=dict)

    def publish(self, topic: str, payload: dict[str, object]) -> None:
        self.topics.setdefault(topic, []).append(payload)
