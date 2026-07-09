from gateway.core.config import load_settings
from gateway.core.egress import is_url_allowed


def test_egress_allows_when_airgap_disabled(monkeypatch):
    monkeypatch.setenv("AIRGAPPED_MODE", "false")
    settings = load_settings()
    assert is_url_allowed("https://example.com/data", settings) is True


def test_egress_blocks_external_when_airgap_enabled(monkeypatch):
    monkeypatch.setenv("AIRGAPPED_MODE", "true")
    monkeypatch.setenv("ALLOW_OUTBOUND_NETWORK", "false")
    monkeypatch.delenv("AIRGAP_ALLOWED_HOSTS", raising=False)
    settings = load_settings()
    assert is_url_allowed("https://example.com/data", settings) is False


def test_egress_allows_allowlisted_host(monkeypatch):
    monkeypatch.setenv("AIRGAPPED_MODE", "true")
    monkeypatch.setenv("ALLOW_OUTBOUND_NETWORK", "false")
    monkeypatch.setenv("AIRGAP_ALLOWED_HOSTS", "example.com,internal.repo")
    settings = load_settings()
    assert is_url_allowed("https://example.com/data", settings) is True
