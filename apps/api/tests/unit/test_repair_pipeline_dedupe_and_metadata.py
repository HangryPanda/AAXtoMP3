"""Unit tests for repair pipeline de-dupe and metadata extraction helpers."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import LocalItem
from services.repair_pipeline import _dedupe_local_items, _extract_asin_from_metadata_sync


@pytest.mark.asyncio
async def test_dedupe_local_items_collapses_equivalent_paths(test_session: AsyncSession, tmp_path: Path) -> None:
    # Two rows that refer to the same canonical output path.
    p = tmp_path / "a.m4b"
    p.write_bytes(b"x")

    li1 = LocalItem(title="A", output_path=str(p))
    li2 = LocalItem(title="B", output_path=str(p))
    test_session.add_all([li1, li2])
    await test_session.commit()

    deleted = await _dedupe_local_items(test_session)
    await test_session.commit()

    assert deleted == 1


def test_extract_asin_from_metadata_sync_reads_tags(tmp_path: Path) -> None:
    f = tmp_path / "x.m4b"
    f.write_bytes(b"x")

    payload = {
        "format": {
            "tags": {
                "ASIN": "B012345678",
                "title": "My Title",
            }
        }
    }
    proc = SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")

    with patch("services.repair_pipeline.subprocess.run", return_value=proc):
        asin, title = _extract_asin_from_metadata_sync(f)

    assert asin == "b012345678"
    assert title == "My Title"

