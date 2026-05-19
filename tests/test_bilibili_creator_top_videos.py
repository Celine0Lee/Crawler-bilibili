# -*- coding: utf-8 -*-
"""Unit tests for Bilibili creator-mode top-liked selection (no network)."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

import config
from media_platform.bilibili.core import BilibiliCrawler


@pytest.mark.asyncio
async def test_get_creator_videos_picks_top_by_like_in_window(monkeypatch):
    now_ts = int(time.time())
    monkeypatch.setattr(config, "BILI_CREATOR_VIDEO_LOOKBACK_DAYS", 365)
    monkeypatch.setattr(config, "BILI_CREATOR_TOP_LIKED_COUNT", 5)
    monkeypatch.setattr(config, "BILI_CREATOR_LIST_PAGE_SIZE", 30)
    monkeypatch.setattr(config, "CRAWLER_MAX_SLEEP_SEC", 0)
    monkeypatch.setattr(config, "MAX_CONCURRENCY_NUM", 2)

    async def noop_sleep(_t=None):
        return

    monkeypatch.setattr(asyncio, "sleep", noop_sleep)

    page1 = {
        "list": {
            "vlist": [
                {"bvid": "BVAAA", "created": now_ts - 10},
                {"bvid": "BVBBB", "created": now_ts - 20},
            ]
        },
        "page": {"count": 2},
    }

    async def fake_list(mid, pn, ps, order):
        if pn == 1:
            return page1
        return {"list": {"vlist": []}, "page": {"count": 2}}

    async def fake_info(aid, bvid, semaphore):
        likes = {"BVAAA": 100, "BVBBB": 500}
        return {
            "View": {
                "bvid": bvid,
                "aid": 111 if bvid == "BVAAA" else 222,
                "stat": {"like": likes[bvid]},
            }
        }

    captured = []

    async def fake_specified(url_list):
        captured.append(list(url_list))

    crawler = BilibiliCrawler()
    crawler.bili_client = MagicMock()
    crawler.bili_client.get_creator_videos = AsyncMock(side_effect=fake_list)
    monkeypatch.setattr(crawler, "get_video_info_task", fake_info)
    monkeypatch.setattr(crawler, "get_specified_videos", AsyncMock(side_effect=fake_specified))

    await crawler.get_creator_videos(999)

    assert len(captured) == 1
    assert captured[0] == ["BVBBB", "BVAAA"]


@pytest.mark.asyncio
async def test_get_creator_videos_stops_when_page_entirely_old(monkeypatch):
    now_ts = int(time.time())
    cutoff = now_ts - 86400 * 365
    old_ts = cutoff - 86400

    monkeypatch.setattr(config, "BILI_CREATOR_VIDEO_LOOKBACK_DAYS", 365)
    monkeypatch.setattr(config, "BILI_CREATOR_TOP_LIKED_COUNT", 5)
    monkeypatch.setattr(config, "BILI_CREATOR_LIST_PAGE_SIZE", 30)
    monkeypatch.setattr(config, "CRAWLER_MAX_SLEEP_SEC", 0)
    monkeypatch.setattr(config, "MAX_CONCURRENCY_NUM", 2)
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())

    old_page = {
        "list": {"vlist": [{"bvid": "BVOLD", "created": old_ts}]},
        "page": {"count": 100},
    }

    async def fake_list(mid, pn, ps, order):
        return old_page

    crawler = BilibiliCrawler()
    crawler.bili_client = MagicMock()
    crawler.bili_client.get_creator_videos = AsyncMock(side_effect=fake_list)
    monkeypatch.setattr(crawler, "get_video_info_task", AsyncMock())
    monkeypatch.setattr(crawler, "get_specified_videos", AsyncMock())

    await crawler.get_creator_videos(888)

    crawler.get_video_info_task.assert_not_called()
    crawler.get_specified_videos.assert_not_called()
