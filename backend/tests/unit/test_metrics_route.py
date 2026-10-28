from cms.api.v1.routes import metrics as metrics_route


async def test_one_process_serves_its_own_counts(monkeypatch) -> None:
    monkeypatch.delenv(metrics_route.MULTIPROC_DIR_VAR, raising=False)

    response = await metrics_route.metrics()

    assert b"cms_ticket_transitions_total" in response.body


async def test_with_the_folder_set_every_workers_counts_are_read(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(metrics_route.MULTIPROC_DIR_VAR, str(tmp_path))
    collected = []
    monkeypatch.setattr(metrics_route.multiprocess, "MultiProcessCollector", collected.append)

    response = await metrics_route.metrics()

    assert len(collected) == 1
    assert response.status_code == 200
