from unittest.mock import AsyncMock, Mock

import pytest

from cms.ingestion.seed import SeedEntry
from cms.services import admin_stats


async def test_options_come_from_disk_with_db_status_joined(monkeypatch) -> None:
    """The exact bug this feature fixes: a partially seeded corpus (one row
    for one of many seed files) must not make the other files invisible."""
    entries = [
        SeedEntry(source_ref="account-security-policy.md", title="Account Security Policy"),
        SeedEntry(source_ref="billing-refunds-policy.md", title="Billing & Refunds Policy"),
        SeedEntry(source_ref="warranty-policy.md", title="Warranty Policy"),
    ]
    monkeypatch.setattr(admin_stats.seed_module, "list_seed_entries", Mock(return_value=entries))
    monkeypatch.setattr(
        admin_stats.policies,
        "statuses_for_source_refs",
        AsyncMock(return_value={"warranty-policy.md": "indexed"}),
    )

    options = await admin_stats.build_document_options("policy", 200)

    assert len(options) == 3
    by_ref = {option.source_ref: option.status for option in options}
    assert by_ref["warranty-policy.md"] == "indexed"
    assert by_ref["account-security-policy.md"] is None
    assert by_ref["billing-refunds-policy.md"] is None


async def test_a_status_lookup_failure_is_not_swallowed(monkeypatch) -> None:
    entries = [SeedEntry(source_ref="warranty-policy.md", title="Warranty Policy")]
    monkeypatch.setattr(admin_stats.seed_module, "list_seed_entries", Mock(return_value=entries))
    monkeypatch.setattr(
        admin_stats.policies,
        "statuses_for_source_refs",
        AsyncMock(side_effect=RuntimeError("supabase unreachable")),
    )

    with pytest.raises(RuntimeError):
        await admin_stats.build_document_options("policy", 200)
