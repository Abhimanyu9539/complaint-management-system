from fastapi import FastAPI
from fastapi.testclient import TestClient

from cms.api.v1.routes import flywheel
from cms.config.settings import get_settings
from cms.schemas.flywheel import MintResult


def _client(monkeypatch, secret, mint_error=None) -> TestClient:
    async def list_candidates(day):
        return ["t1", "t2"]

    async def mint_case(ticket_id):
        if mint_error:
            raise mint_error
        return MintResult(ticket_id=ticket_id, outcome="minted", case_id="c1")

    monkeypatch.setattr(get_settings(), "flywheel_job_secret", secret)
    monkeypatch.setattr(flywheel.case_minting, "list_candidates", list_candidates)
    monkeypatch.setattr(flywheel.case_minting, "mint_case", mint_case)
    app = FastAPI()
    app.include_router(flywheel.router)
    return TestClient(app)


def test_the_job_is_off_without_a_secret(monkeypatch) -> None:
    response = _client(monkeypatch, None).get(
        "/flywheel/candidates", params={"day": "2026-11-07"}, headers={"X-Job-Secret": "x"}
    )
    assert response.status_code == 503


def test_a_wrong_secret_is_refused(monkeypatch) -> None:
    response = _client(monkeypatch, "s3cret").post("/flywheel/tickets/t1/mint", headers={"X-Job-Secret": "x"})
    assert response.status_code == 401


def test_the_right_secret_lists_and_mints(monkeypatch) -> None:
    client = _client(monkeypatch, "s3cret")
    headers = {"X-Job-Secret": "s3cret"}

    listed = client.get("/flywheel/candidates", params={"day": "2026-11-07"}, headers=headers)
    minted = client.post("/flywheel/tickets/t1/mint", headers=headers)

    assert listed.json() == {"day": "2026-11-07", "ticket_ids": ["t1", "t2"]}
    assert minted.json()["outcome"] == "minted"


def test_a_failed_mint_answers_500_so_airflow_retries(monkeypatch) -> None:
    client = _client(monkeypatch, "s3cret", mint_error=RuntimeError("qdrant down"))

    response = client.post("/flywheel/tickets/t1/mint", headers={"X-Job-Secret": "s3cret"})

    assert response.status_code == 500 and "qdrant" not in response.text
