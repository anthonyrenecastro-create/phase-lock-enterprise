from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from .types import FeedbackResponse, StabilizeResponse, TelemetryResponse


@dataclass
class PhaseLockClient:
    base_url: str = "http://127.0.0.1:8000"
    api_key: str | None = None
    timeout_seconds: float = 20.0

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def stabilize(
        self,
        *,
        tenant_id: str,
        request_id: str,
        metric_window: list[float],
        text: str | None = None,
        embedding: list[float] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> StabilizeResponse:
        payload = {
            "tenant_id": tenant_id,
            "request_id": request_id,
            "text": text,
            "embedding": embedding,
            "metric_window": metric_window,
            "metadata": metadata or {},
        }
        res = requests.post(
            f"{self.base_url}/v1/stabilize",
            json=payload,
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        res.raise_for_status()
        return res.json()

    def feedback(
        self,
        *,
        tenant_id: str,
        request_id: str,
        corrected: bool,
        correction_score: float,
        observed_risk_level: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> FeedbackResponse:
        payload = {
            "tenant_id": tenant_id,
            "request_id": request_id,
            "corrected": corrected,
            "correction_score": correction_score,
            "observed_risk_level": observed_risk_level,
            "metadata": metadata or {},
        }
        res = requests.post(
            f"{self.base_url}/v1/feedback",
            json=payload,
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        res.raise_for_status()
        return res.json()

    def telemetry(self, format: str = "json") -> TelemetryResponse | str:
        res = requests.get(
            f"{self.base_url}/v1/telemetry",
            params={"format": format},
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        res.raise_for_status()
        if format == "prometheus":
            return res.text
        return res.json()

    def health(self) -> dict[str, Any]:
        res = requests.get(
            f"{self.base_url}/v1/health",
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        res.raise_for_status()
        return res.json()
