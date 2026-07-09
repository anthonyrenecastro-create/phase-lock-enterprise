def test_replay_harness_reports_totals(app_modules):
    from gateway.core.replay import replay_requests
    from gateway.core.schemas import StabilizeRequest

    _, routes, _ = app_modules
    service = routes.service

    reqs = [
        StabilizeRequest(
            tenant_id="acme",
            request_id="r1",
            text="ok",
            embedding=[0.1],
            metric_window=[0.1] * 24,
            metadata={},
        ),
        StabilizeRequest(
            tenant_id="acme",
            request_id="r2",
            text="high drift",
            embedding=[0.1],
            metric_window=[1.0] * 24,
            metadata={},
        ),
    ]

    report = replay_requests(service, reqs)
    assert report.total_requests == 2
    assert 0.0 <= report.avg_drift_score <= 1.0
    assert report.incidents_prevented >= 1


def test_replay_harness_handles_empty_input(app_modules):
    from gateway.core.replay import replay_requests

    _, routes, _ = app_modules
    report = replay_requests(routes.service, [])
    assert report.total_requests == 0
    assert report.incidents_prevented == 0
    assert report.avg_drift_score == 0.0
