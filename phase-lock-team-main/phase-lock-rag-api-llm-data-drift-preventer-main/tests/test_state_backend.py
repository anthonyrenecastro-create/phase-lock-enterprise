from gateway.core.state_backend import MemoryStateBackend


def test_memory_state_backend_int_and_revocation_operations():
    backend = MemoryStateBackend()

    assert backend.get_int("tenant:acme:spike", default=0) == 0
    backend.set_int("tenant:acme:spike", 2, ttl_seconds=3600)
    assert backend.get_int("tenant:acme:spike", default=0) == 2

    assert backend.is_session_revoked("sid-1") is False
    backend.revoke_session("sid-1", ttl_seconds=3600)
    assert backend.is_session_revoked("sid-1") is True


def test_memory_state_backend_atomic_increment_and_consume_once():
    backend = MemoryStateBackend()

    assert backend.incr_int("tenant:acme:spike", delta=1, ttl_seconds=60) == 1
    assert backend.incr_int("tenant:acme:spike", delta=2, ttl_seconds=60) == 3
    assert backend.consume_once("oidc:state:abc", ttl_seconds=60) is True
    assert backend.consume_once("oidc:state:abc", ttl_seconds=60) is False


def test_memory_state_backend_health_ok():
    backend = MemoryStateBackend()
    health = backend.health()
    assert health["backend"] == "memory"
    assert health["status"] == "ok"
