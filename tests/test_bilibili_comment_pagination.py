# -*- coding: utf-8 -*-
"""Unit tests for Bilibili full comment pagination (no network)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

import config
from media_platform.bilibili.client import BilibiliClient, resolve_bili_comment_order_mode
from media_platform.bilibili.field import CommentOrderType


@pytest.mark.asyncio
async def test_get_video_all_comments_paginates_level1_then_level2(monkeypatch):
    monkeypatch.setattr(config, "BILI_COMMENT_ORDER_MODE", "time")
    monkeypatch.setattr(config, "BILI_COMMENT_PAGE_SIZE", 20)
    monkeypatch.setattr(config, "BILI_SUB_COMMENT_PAGE_SIZE", 10)
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())

    pages = [
        {
            "cursor": {"is_end": False, "next": 2},
            "replies": [{"rpid": 1, "rcount": 1}, {"rpid": 2, "rcount": 0}],
        },
        {
            "cursor": {"is_end": True, "next": 0},
            "replies": [{"rpid": 3, "rcount": 2}],
        },
    ]
    page_idx = {"i": 0}

    async def fake_page(video_id, order_mode, next_page, ps):
        i = page_idx["i"]
        page_idx["i"] += 1
        if i < len(pages):
            return pages[i]
        return {"cursor": {"is_end": True, "next": 0}, "replies": []}

    l2_calls = []

    async def fake_l2(video_id, root_id, order_mode, ps, crawl_interval, callback):
        l2_calls.append(root_id)
        if callback:
            await callback(video_id, [{"rpid": 100 + root_id}])
        return 1

    stored_l1 = []
    stored_l2 = []

    async def fake_cb(video_id, comments):
        for c in comments:
            if "rcount" in c:
                stored_l1.append(c)
            else:
                stored_l2.append(c)

    client = BilibiliClient(
        proxy=None,
        headers={},
        playwright_page=MagicMock(),
        cookie_dict={},
    )
    client._fetch_video_comments_page_with_retry = AsyncMock(side_effect=fake_page)
    client.get_video_all_level_two_comments = AsyncMock(side_effect=fake_l2)

    await client.get_video_all_comments(
        video_id="999",
        crawl_interval=0,
        is_fetch_sub_comments=True,
        callback=fake_cb,
        max_count=0,
    )

    assert client._fetch_video_comments_page_with_retry.await_count == 2
    assert len(stored_l1) == 3
    assert len(stored_l2) == 2
    assert set(l2_calls) == {1, 3}


@pytest.mark.asyncio
async def test_get_video_all_comments_respects_max_count(monkeypatch):
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())

    async def fake_page(video_id, order_mode, next_page, ps):
        return {
            "cursor": {"is_end": True, "next": 0},
            "replies": [{"rpid": i, "rcount": 0} for i in range(10)],
        }

    stored = []

    async def fake_cb(video_id, comments):
        stored.extend(comments)

    client = BilibiliClient(
        proxy=None,
        headers={},
        playwright_page=MagicMock(),
        cookie_dict={},
    )
    client._fetch_video_comments_page_with_retry = AsyncMock(side_effect=fake_page)

    await client.get_video_all_comments(
        video_id="999",
        crawl_interval=0,
        is_fetch_sub_comments=False,
        callback=fake_cb,
        max_count=5,
    )

    assert len(stored) == 5


def test_resolve_comment_order_mode():
    assert resolve_bili_comment_order_mode() == CommentOrderType.TIME
