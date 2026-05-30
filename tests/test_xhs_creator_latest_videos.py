# -*- coding: utf-8 -*-
"""Unit tests for Xiaohongshu creator-mode top-liked recent-video selection."""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest
import asyncio

import config
from media_platform.xhs.core import XiaoHongShuCrawler


@pytest.mark.asyncio
async def test_collect_creator_top_liked_recent_videos_picks_top_five_from_twenty(monkeypatch):
    now_ms = int(time.time() * 1000)
    monkeypatch.setattr(config, "XHS_CREATOR_VIDEO_LOOKBACK_DAYS", 365, raising=False)
    monkeypatch.setattr(config, "XHS_CREATOR_CANDIDATE_VIDEO_COUNT", 20, raising=False)
    monkeypatch.setattr(config, "XHS_CREATOR_TOP_LIKED_COUNT", 5, raising=False)
    monkeypatch.setattr(config, "XHS_CREATOR_NOTE_TYPE", "video")
    monkeypatch.setattr(config, "XHS_CREATOR_MAX_CRAWL_COUNT", 30)
    monkeypatch.setattr("media_platform.xhs.core.asyncio.sleep", AsyncMock())

    note_summaries = [
        {"note_id": f"n{i}", "xsec_source": "pc_feed", "xsec_token": f"t{i}"}
        for i in range(1, 23)
    ]
    page_calls = []

    async def fake_get_notes_by_creator(creator, cursor, page_size=30, xsec_token="", xsec_source="pc_feed"):
        page_calls.append((creator, cursor))
        return {"has_more": True, "cursor": "next-page", "notes": note_summaries}

    detail_calls = []
    likes = {f"n{i}": i for i in range(1, 23)}
    likes.update({"n3": 900, "n7": 700, "n11": 1100, "n17": 1700, "n20": 1200})

    async def fake_get_note_detail_async_task(note_id, xsec_source, xsec_token, semaphore):
        detail_calls.append(note_id)
        return {
            "note_id": note_id,
            "type": "video",
            "time": now_ms - 86_400_000,
            "xsec_token": xsec_token,
            "interact_info": {"liked_count": likes[note_id]},
        }

    crawler = XiaoHongShuCrawler()
    crawler.xhs_client = MagicMock()
    crawler.xhs_client.get_notes_by_creator = AsyncMock(side_effect=fake_get_notes_by_creator)
    crawler.get_note_detail_async_task = AsyncMock(side_effect=fake_get_note_detail_async_task)
    monkeypatch.setattr("store.xhs.update_xhs_note", AsyncMock())
    monkeypatch.setattr(crawler, "get_notice_media", AsyncMock())

    selected = await crawler.collect_creator_top_liked_recent_videos(
        user_id="creator_123",
        crawl_interval=0,
        xsec_token="creator-token",
        xsec_source="pc_feed",
    )

    assert page_calls == [("creator_123", "")]
    assert detail_calls == [f"n{i}" for i in range(1, 21)]
    assert [note["note_id"] for note in selected] == ["n17", "n20", "n11", "n3", "n7"]


@pytest.mark.asyncio
async def test_collect_creator_top_liked_recent_videos_stops_when_note_is_older_than_window(monkeypatch):
    now_ms = int(time.time() * 1000)
    old_ms = now_ms - 366 * 86_400_000
    monkeypatch.setattr(config, "XHS_CREATOR_VIDEO_LOOKBACK_DAYS", 365, raising=False)
    monkeypatch.setattr(config, "XHS_CREATOR_CANDIDATE_VIDEO_COUNT", 20, raising=False)
    monkeypatch.setattr(config, "XHS_CREATOR_TOP_LIKED_COUNT", 5, raising=False)
    monkeypatch.setattr(config, "XHS_CREATOR_NOTE_TYPE", "video")
    monkeypatch.setattr(config, "XHS_CREATOR_MAX_CRAWL_COUNT", 30)
    monkeypatch.setattr("media_platform.xhs.core.asyncio.sleep", AsyncMock())

    note_summaries = [
        {"note_id": "n1", "type": "video", "xsec_source": "pc_feed", "xsec_token": "t1"},
        {"note_id": "n2", "type": "normal", "xsec_source": "pc_feed", "xsec_token": "t2"},
        {"note_id": "n3", "type": "video", "xsec_source": "pc_feed", "xsec_token": "t3"},
        {"note_id": "n4", "type": "video", "xsec_source": "pc_feed", "xsec_token": "t4"},
        {"note_id": "n5", "type": "video", "xsec_source": "pc_feed", "xsec_token": "t5"},
        {"note_id": "old", "type": "video", "xsec_source": "pc_feed", "xsec_token": "t-old"},
        {"note_id": "after-old", "type": "video", "xsec_source": "pc_feed", "xsec_token": "t-after"},
    ]

    async def fake_get_notes_by_creator(creator, cursor, page_size=30, xsec_token="", xsec_source="pc_feed"):
        return {"has_more": False, "cursor": "", "notes": note_summaries}

    detail_calls = []

    async def fake_get_note_detail_async_task(note_id, xsec_source, xsec_token, semaphore):
        detail_calls.append(note_id)
        return {
            "note_id": note_id,
            "type": "video",
            "time": old_ms if note_id == "old" else now_ms - 86_400_000,
            "xsec_token": xsec_token,
            "interact_info": {"liked_count": {"n1": 10, "n3": 30, "n4": 20, "n5": 50}.get(note_id, 1)},
        }

    crawler = XiaoHongShuCrawler()
    crawler.xhs_client = MagicMock()
    crawler.xhs_client.get_notes_by_creator = AsyncMock(side_effect=fake_get_notes_by_creator)
    crawler.get_note_detail_async_task = AsyncMock(side_effect=fake_get_note_detail_async_task)
    monkeypatch.setattr("store.xhs.update_xhs_note", AsyncMock())
    monkeypatch.setattr(crawler, "get_notice_media", AsyncMock())

    selected = await crawler.collect_creator_top_liked_recent_videos(
        user_id="creator_skip_summary",
        crawl_interval=0,
        xsec_token="creator-token",
        xsec_source="pc_feed",
    )

    assert detail_calls == ["n1", "n3", "n4", "n5", "old"]
    assert [note["note_id"] for note in selected] == ["n5", "n3", "n4", "n1"]


@pytest.mark.asyncio
async def test_collect_creator_top_liked_recent_videos_turns_page_until_twenty_candidates(monkeypatch):
    now_ms = int(time.time() * 1000)
    monkeypatch.setattr(config, "XHS_CREATOR_VIDEO_LOOKBACK_DAYS", 365, raising=False)
    monkeypatch.setattr(config, "XHS_CREATOR_CANDIDATE_VIDEO_COUNT", 20, raising=False)
    monkeypatch.setattr(config, "XHS_CREATOR_TOP_LIKED_COUNT", 5, raising=False)
    monkeypatch.setattr(config, "XHS_CREATOR_NOTE_TYPE", "video")
    monkeypatch.setattr(config, "XHS_CREATOR_MAX_CRAWL_COUNT", 30)
    sleep_mock = AsyncMock()
    monkeypatch.setattr("media_platform.xhs.core.asyncio.sleep", sleep_mock)

    page1 = {
        "has_more": True,
        "cursor": "page-2",
        "notes": [
            {"note_id": f"n{i}", "xsec_source": "pc_feed", "xsec_token": f"t{i}"}
            for i in range(1, 11)
        ],
    }
    page2 = {
        "has_more": False,
        "cursor": "",
        "notes": [
            {"note_id": f"n{i}", "xsec_source": "pc_feed", "xsec_token": f"t{i}"}
            for i in range(11, 23)
        ],
    }

    async def fake_get_notes_by_creator(creator, cursor, page_size=30, xsec_token="", xsec_source="pc_feed"):
        if cursor == "":
            return page1
        if cursor == "page-2":
            return page2
        return {"has_more": False, "cursor": "", "notes": []}

    async def fake_get_note_detail_async_task(note_id, xsec_source, xsec_token, semaphore):
        note_number = int(note_id[1:])
        return {
            "note_id": note_id,
            "type": "video",
            "time": now_ms - 86_400_000,
            "xsec_token": xsec_token,
            "interact_info": {"liked_count": note_number},
        }

    crawler = XiaoHongShuCrawler()
    crawler.xhs_client = MagicMock()
    crawler.xhs_client.get_notes_by_creator = AsyncMock(side_effect=fake_get_notes_by_creator)
    crawler.get_note_detail_async_task = AsyncMock(side_effect=fake_get_note_detail_async_task)
    monkeypatch.setattr("store.xhs.update_xhs_note", AsyncMock())
    monkeypatch.setattr(crawler, "get_notice_media", AsyncMock())

    selected = await crawler.collect_creator_top_liked_recent_videos(
        user_id="creator_456",
        crawl_interval=3,
        xsec_token="creator-token",
        xsec_source="pc_feed",
    )

    assert crawler.xhs_client.get_notes_by_creator.await_count == 2
    assert sleep_mock.await_count == 1
    assert crawler.get_note_detail_async_task.await_count == 20
    assert [note["note_id"] for note in selected] == ["n20", "n19", "n18", "n17", "n16"]


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
