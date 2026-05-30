# -*- coding: utf-8 -*-
"""Unit tests for Xiaohongshu creator-mode latest-video selection."""

from unittest.mock import AsyncMock, MagicMock

import pytest
import asyncio

import config
from media_platform.xhs.core import XiaoHongShuCrawler


@pytest.mark.asyncio
async def test_collect_creator_latest_notes_stops_after_five_videos(monkeypatch):
    monkeypatch.setattr(config, "XHS_CREATOR_LATEST_COUNT", 5, raising=False)
    monkeypatch.setattr(config, "XHS_CREATOR_NOTE_TYPE", "video")
    monkeypatch.setattr(config, "XHS_CREATOR_MAX_CRAWL_COUNT", 30)
    monkeypatch.setattr("media_platform.xhs.core.asyncio.sleep", AsyncMock())

    note_summaries = [
        {"note_id": "n1", "xsec_source": "pc_feed", "xsec_token": "t1"},
        {"note_id": "n2", "xsec_source": "pc_feed", "xsec_token": "t2"},
        {"note_id": "n3", "xsec_source": "pc_feed", "xsec_token": "t3"},
        {"note_id": "n4", "xsec_source": "pc_feed", "xsec_token": "t4"},
        {"note_id": "n5", "xsec_source": "pc_feed", "xsec_token": "t5"},
        {"note_id": "n6", "xsec_source": "pc_feed", "xsec_token": "t6"},
        {"note_id": "n7", "xsec_source": "pc_feed", "xsec_token": "t7"},
    ]
    page_calls = []

    async def fake_get_notes_by_creator(creator, cursor, page_size=30, xsec_token="", xsec_source="pc_feed"):
        page_calls.append((creator, cursor))
        return {"has_more": True, "cursor": "next-page", "notes": note_summaries}

    detail_calls = []
    note_types = {
        "n1": "video",
        "n2": "normal",
        "n3": "video",
        "n4": "video",
        "n5": "video",
        "n6": "video",
        "n7": "video",
    }

    async def fake_get_note_detail_async_task(note_id, xsec_source, xsec_token, semaphore):
        detail_calls.append(note_id)
        return {"note_id": note_id, "type": note_types[note_id], "xsec_token": xsec_token}

    crawler = XiaoHongShuCrawler()
    crawler.xhs_client = MagicMock()
    crawler.xhs_client.get_notes_by_creator = AsyncMock(side_effect=fake_get_notes_by_creator)
    crawler.get_note_detail_async_task = AsyncMock(side_effect=fake_get_note_detail_async_task)
    monkeypatch.setattr("store.xhs.update_xhs_note", AsyncMock())
    monkeypatch.setattr(crawler, "get_notice_media", AsyncMock())

    selected = await crawler.collect_creator_latest_notes(
        user_id="creator_123",
        crawl_interval=0,
        xsec_token="creator-token",
        xsec_source="pc_feed",
    )

    assert page_calls == [("creator_123", "")]
    assert detail_calls == ["n1", "n2", "n3", "n4", "n5", "n6"]
    assert [note["note_id"] for note in selected] == ["n1", "n3", "n4", "n5", "n6"]


@pytest.mark.asyncio
async def test_collect_creator_latest_notes_skips_non_video_summaries_before_detail(monkeypatch):
    monkeypatch.setattr(config, "XHS_CREATOR_LATEST_COUNT", 5, raising=False)
    monkeypatch.setattr(config, "XHS_CREATOR_NOTE_TYPE", "video")
    monkeypatch.setattr(config, "XHS_CREATOR_MAX_CRAWL_COUNT", 30)
    monkeypatch.setattr("media_platform.xhs.core.asyncio.sleep", AsyncMock())

    note_summaries = [
        {"note_id": "n1", "type": "video", "xsec_source": "pc_feed", "xsec_token": "t1"},
        {"note_id": "n2", "type": "normal", "xsec_source": "pc_feed", "xsec_token": "t2"},
        {"note_id": "n3", "type": "video", "xsec_source": "pc_feed", "xsec_token": "t3"},
        {"note_id": "n4", "type": "video", "xsec_source": "pc_feed", "xsec_token": "t4"},
        {"note_id": "n5", "type": "video", "xsec_source": "pc_feed", "xsec_token": "t5"},
        {"note_id": "n6", "type": "video", "xsec_source": "pc_feed", "xsec_token": "t6"},
    ]

    async def fake_get_notes_by_creator(creator, cursor, page_size=30, xsec_token="", xsec_source="pc_feed"):
        return {"has_more": False, "cursor": "", "notes": note_summaries}

    detail_calls = []

    async def fake_get_note_detail_async_task(note_id, xsec_source, xsec_token, semaphore):
        detail_calls.append(note_id)
        return {"note_id": note_id, "type": "video", "xsec_token": xsec_token}

    crawler = XiaoHongShuCrawler()
    crawler.xhs_client = MagicMock()
    crawler.xhs_client.get_notes_by_creator = AsyncMock(side_effect=fake_get_notes_by_creator)
    crawler.get_note_detail_async_task = AsyncMock(side_effect=fake_get_note_detail_async_task)
    monkeypatch.setattr("store.xhs.update_xhs_note", AsyncMock())
    monkeypatch.setattr(crawler, "get_notice_media", AsyncMock())

    selected = await crawler.collect_creator_latest_notes(
        user_id="creator_skip_summary",
        crawl_interval=0,
        xsec_token="creator-token",
        xsec_source="pc_feed",
    )

    assert detail_calls == ["n1", "n3", "n4", "n5", "n6"]
    assert [note["note_id"] for note in selected] == ["n1", "n3", "n4", "n5", "n6"]


@pytest.mark.asyncio
async def test_collect_creator_latest_notes_turns_page_when_first_page_not_enough(monkeypatch):
    monkeypatch.setattr(config, "XHS_CREATOR_LATEST_COUNT", 5, raising=False)
    monkeypatch.setattr(config, "XHS_CREATOR_NOTE_TYPE", "video")
    monkeypatch.setattr(config, "XHS_CREATOR_MAX_CRAWL_COUNT", 30)
    sleep_mock = AsyncMock()
    monkeypatch.setattr("media_platform.xhs.core.asyncio.sleep", sleep_mock)

    page1 = {
        "has_more": True,
        "cursor": "page-2",
        "notes": [
            {"note_id": "n1", "xsec_source": "pc_feed", "xsec_token": "t1"},
            {"note_id": "n2", "xsec_source": "pc_feed", "xsec_token": "t2"},
        ],
    }
    page2 = {
        "has_more": False,
        "cursor": "",
        "notes": [
            {"note_id": "n3", "xsec_source": "pc_feed", "xsec_token": "t3"},
            {"note_id": "n4", "xsec_source": "pc_feed", "xsec_token": "t4"},
            {"note_id": "n5", "xsec_source": "pc_feed", "xsec_token": "t5"},
            {"note_id": "n6", "xsec_source": "pc_feed", "xsec_token": "t6"},
        ],
    }

    async def fake_get_notes_by_creator(creator, cursor, page_size=30, xsec_token="", xsec_source="pc_feed"):
        if cursor == "":
            return page1
        if cursor == "page-2":
            return page2
        return {"has_more": False, "cursor": "", "notes": []}

    note_types = {
        "n1": "video",
        "n2": "normal",
        "n3": "video",
        "n4": "video",
        "n5": "video",
        "n6": "video",
    }

    async def fake_get_note_detail_async_task(note_id, xsec_source, xsec_token, semaphore):
        return {"note_id": note_id, "type": note_types[note_id], "xsec_token": xsec_token}

    crawler = XiaoHongShuCrawler()
    crawler.xhs_client = MagicMock()
    crawler.xhs_client.get_notes_by_creator = AsyncMock(side_effect=fake_get_notes_by_creator)
    crawler.get_note_detail_async_task = AsyncMock(side_effect=fake_get_note_detail_async_task)
    monkeypatch.setattr("store.xhs.update_xhs_note", AsyncMock())
    monkeypatch.setattr(crawler, "get_notice_media", AsyncMock())

    selected = await crawler.collect_creator_latest_notes(
        user_id="creator_456",
        crawl_interval=3,
        xsec_token="creator-token",
        xsec_source="pc_feed",
    )

    assert crawler.xhs_client.get_notes_by_creator.await_count == 2
    assert sleep_mock.await_count == 1
    assert [note["note_id"] for note in selected] == ["n1", "n3", "n4", "n5", "n6"]


@pytest.mark.asyncio
async def test_get_note_detail_async_task_times_out_stuck_note(monkeypatch):
    monkeypatch.setattr(config, "XHS_NOTE_DETAIL_API_TIMEOUT_SEC", 0.01, raising=False)
    monkeypatch.setattr(config, "XHS_NOTE_DETAIL_HTML_TIMEOUT_SEC", 0.01, raising=False)
    monkeypatch.setattr(config, "XHS_NOTE_DETAIL_PROGRESS_HEARTBEAT_SEC", 0, raising=False)
    monkeypatch.setattr(config, "XHS_NOTE_DETAIL_SLEEP_SEC", 0, raising=False)

    async def slow_api(*args, **kwargs):
        await asyncio.sleep(0.05)
        return {"note_id": "slow-note", "type": "video"}

    async def slow_html(*args, **kwargs):
        await asyncio.sleep(0.05)
        return {"note_id": "slow-note", "type": "video"}

    crawler = XiaoHongShuCrawler()
    crawler.xhs_client = MagicMock()
    crawler.xhs_client.get_note_by_id = AsyncMock(side_effect=slow_api)
    crawler.xhs_client.get_note_by_id_from_html = AsyncMock(side_effect=slow_html)

    detail = await crawler.get_note_detail_async_task(
        note_id="slow-note",
        xsec_source="pc_feed",
        xsec_token="token",
        semaphore=asyncio.Semaphore(1),
    )

    assert detail is None
