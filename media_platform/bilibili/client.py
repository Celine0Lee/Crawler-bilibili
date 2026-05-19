# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/media_platform/bilibili/client.py
# GitHub: https://github.com/NanmiCoder
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#

# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。
# 5. 不得用于任何非法或不当的用途。
#
# 详细许可条款请参阅项目根目录下的LICENSE文件。
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。

# -*- coding: utf-8 -*-
# @Author  : relakkes@gmail.com
# @Time    : 2023/12/2 18:44
# @Desc    : bilibili request client
import asyncio
import json
import random
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple, Union
from urllib.parse import urlencode

import httpx
from playwright.async_api import BrowserContext, Page
from tools.httpx_util import make_async_client

import config
from base.base_crawler import AbstractApiClient
from proxy.proxy_mixin import ProxyRefreshMixin
from tools import utils

if TYPE_CHECKING:
    from proxy.proxy_ip_pool import ProxyIpPool

from .exception import DataFetchError
from .field import CommentOrderType, SearchOrderType
from .help import BilibiliSign


def resolve_bili_comment_order_mode() -> CommentOrderType:
    mode = str(getattr(config, "BILI_COMMENT_ORDER_MODE", "time")).lower()
    if mode in ("time", "ctime"):
        return CommentOrderType.TIME
    if mode in ("mixed", "mix"):
        return CommentOrderType.MIXED
    return CommentOrderType.DEFAULT


def _comment_page_size() -> int:
    return max(1, int(getattr(config, "BILI_COMMENT_PAGE_SIZE", 20)))


def _sub_comment_page_size() -> int:
    return max(1, int(getattr(config, "BILI_SUB_COMMENT_PAGE_SIZE", 20)))


class BilibiliClient(AbstractApiClient, ProxyRefreshMixin):

    def __init__(
        self,
        timeout=60,  # For media crawling, Bilibili long videos need a longer timeout
        proxy=None,
        *,
        headers: Dict[str, str],
        playwright_page: Page,
        cookie_dict: Dict[str, str],
        proxy_ip_pool: Optional["ProxyIpPool"] = None,
    ):
        self.proxy = proxy
        self.timeout = timeout
        self.headers = headers
        self._host = "https://api.bilibili.com"
        self.cookie_urls = ["https://www.bilibili.com"]
        self.playwright_page = playwright_page
        self.cookie_dict = cookie_dict
        # Initialize proxy pool (from ProxyRefreshMixin)
        self.init_proxy_pool(proxy_ip_pool)

    async def request(self, method, url, **kwargs) -> Any:
        # Check if proxy has expired before each request
        await self._refresh_proxy_if_expired()

        async with make_async_client(proxy=self.proxy) as client:
            response = await client.request(method, url, timeout=self.timeout, **kwargs)
        try:
            data: Dict = response.json()
        except json.JSONDecodeError:
            utils.logger.error(f"[BilibiliClient.request] Failed to decode JSON from response. status_code: {response.status_code}, response_text: {response.text}")
            raise DataFetchError(f"Failed to decode JSON, content: {response.text}")
        if data.get("code") != 0:
            raise DataFetchError(data.get("message", "unkonw error"))
        else:
            return data.get("data", {})

    async def pre_request_data(self, req_data: Dict) -> Dict:
        """
        Send request to sign request parameters
        Need to get wbi_img_urls parameter from localStorage, value as follows:
        https://i0.hdslb.com/bfs/wbi/7cd084941338484aae1ad9425b84077c.png-https://i0.hdslb.com/bfs/wbi/4932caff0ff746eab6f01bf08b70ac45.png
        :param req_data:
        :return:
        """
        if not req_data:
            return {}
        img_key, sub_key = await self.get_wbi_keys()
        return BilibiliSign(img_key, sub_key).sign(req_data)

    async def get_wbi_keys(self) -> Tuple[str, str]:
        """
        Get the latest img_key and sub_key
        :return:
        """
        local_storage = await self.playwright_page.evaluate("() => window.localStorage")
        wbi_img_urls = local_storage.get("wbi_img_urls", "")
        if not wbi_img_urls:
            img_url_from_storage = local_storage.get("wbi_img_url")
            sub_url_from_storage = local_storage.get("wbi_sub_url")
            if img_url_from_storage and sub_url_from_storage:
                wbi_img_urls = f"{img_url_from_storage}-{sub_url_from_storage}"
        if wbi_img_urls and "-" in wbi_img_urls:
            img_url, sub_url = wbi_img_urls.split("-")
        else:
            resp = await self.request(method="GET", url=self._host + "/x/web-interface/nav")
            img_url: str = resp['wbi_img']['img_url']
            sub_url: str = resp['wbi_img']['sub_url']
        img_key = img_url.rsplit('/', 1)[1].split('.')[0]
        sub_key = sub_url.rsplit('/', 1)[1].split('.')[0]
        return img_key, sub_key

    async def get(self, uri: str, params=None, enable_params_sign: bool = True) -> Dict:
        final_uri = uri
        if enable_params_sign:
            params = await self.pre_request_data(params)
        if isinstance(params, dict):
            final_uri = (f"{uri}?"
                         f"{urlencode(params)}")
        return await self.request(method="GET", url=f"{self._host}{final_uri}", headers=self.headers)

    async def post(self, uri: str, data: dict) -> Dict:
        data = await self.pre_request_data(data)
        json_str = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
        return await self.request(method="POST", url=f"{self._host}{uri}", data=json_str, headers=self.headers)

    async def pong(self) -> bool:
        """get a note to check if login state is ok"""
        utils.logger.info("[BilibiliClient.pong] Begin pong bilibili...")
        ping_flag = False
        try:
            check_login_uri = "/x/web-interface/nav"
            response = await self.get(check_login_uri)
            if response.get("isLogin"):
                utils.logger.info("[BilibiliClient.pong] Use cache login state get web interface successfull!")
                ping_flag = True
        except Exception as e:
            utils.logger.error(f"[BilibiliClient.pong] Pong bilibili failed: {e}, and try to login again...")
            ping_flag = False
        return ping_flag

    async def update_cookies(self, browser_context: BrowserContext, urls: Optional[list[str]] = None):
        cookie_str, cookie_dict = await utils.convert_browser_context_cookies(
            browser_context,
            urls=urls or self.cookie_urls,
        )
        self.headers["Cookie"] = cookie_str
        self.cookie_dict = cookie_dict

    async def search_video_by_keyword(
        self,
        keyword: str,
        page: int = 1,
        page_size: int = 20,
        order: SearchOrderType = SearchOrderType.DEFAULT,
        pubtime_begin_s: int = 0,
        pubtime_end_s: int = 0,
    ) -> Dict:
        """
        KuaiShou web search api
        :param keyword: Search keyword
        :param page: Page number for pagination
        :param page_size: Number of items per page
        :param order: Sort order for search results, default is comprehensive sorting
        :param pubtime_begin_s: Publish time start timestamp
        :param pubtime_end_s: Publish time end timestamp
        :return:
        """
        uri = "/x/web-interface/wbi/search/type"
        post_data = {
            "search_type": "video",
            "keyword": keyword,
            "page": page,
            "page_size": page_size,
            "order": order.value,
            "pubtime_begin_s": pubtime_begin_s,
            "pubtime_end_s": pubtime_end_s
        }
        return await self.get(uri, post_data)

    async def get_video_info(self, aid: Union[int, None] = None, bvid: Union[str, None] = None) -> Dict:
        """
        Bilibli web video detail api, choose one parameter between aid and bvid
        :param aid: Video aid
        :param bvid: Video bvid
        :return:
        """
        if not aid and not bvid:
            raise ValueError("Please provide at least one parameter: aid or bvid")

        uri = "/x/web-interface/view/detail"
        params = dict()
        if aid:
            params.update({"aid": aid})
        else:
            params.update({"bvid": bvid})
        return await self.get(uri, params, enable_params_sign=False)

    async def get_video_play_url(self, aid: int, cid: int) -> Dict:
        """
        Bilibli web video play url api
        :param aid: Video aid
        :param cid: cid
        :return:
        """
        if not aid or not cid or aid <= 0 or cid <= 0:
            raise ValueError("aid and cid must exist")
        uri = "/x/player/wbi/playurl"
        qn_value = getattr(config, "BILI_QN", 80)
        params = {
            "avid": aid,
            "cid": cid,
            "qn": qn_value,
            "fourk": 1,
            "fnval": 1,
            "platform": "pc",
        }

        return await self.get(uri, params, enable_params_sign=True)

    async def get_video_media(self, url: str) -> Union[bytes, None]:
        # Follow CDN 302 redirects and treat any 2xx as success (some endpoints return 206)
        async with make_async_client(proxy=self.proxy, follow_redirects=True) as client:
            try:
                response = await client.request("GET", url, timeout=self.timeout, headers=self.headers)
                response.raise_for_status()
                if 200 <= response.status_code < 300:
                    return response.content
                utils.logger.error(
                    f"[BilibiliClient.get_video_media] Unexpected status {response.status_code} for {url}"
                )
                return None
            except httpx.HTTPError as exc:  # some wrong when call httpx.request method, such as connection error, client error, server error or response status code is not 2xx
                utils.logger.error(f"[BilibiliClient.get_video_media] {exc.__class__.__name__} for {exc.request.url} - {exc}")  # Keep original exception type name for developer debugging
                return None

    async def get_video_comments(
        self,
        video_id: str,
        order_mode: CommentOrderType = CommentOrderType.DEFAULT,
        next: int = 0,
        ps: int = 20,
    ) -> Dict:
        """get video comments
        :param video_id: Video ID
        :param order_mode: Sort order
        :param next: Comment page selection
        :param ps: Page size
        :return:
        """
        uri = "/x/v2/reply/wbi/main"
        post_data = {"oid": video_id, "mode": order_mode.value, "type": 1, "ps": ps, "next": next}
        return await self.get(uri, post_data)

    async def _fetch_video_comments_page_with_retry(
        self,
        video_id: str,
        order_mode: CommentOrderType,
        next_page: int,
        ps: int,
        max_retries: int = 3,
    ) -> Optional[Dict]:
        """Fetch one page of level-1 comments with backoff on API/network errors."""
        retryable = (DataFetchError, httpx.RemoteProtocolError, httpx.HTTPError, httpx.ConnectError, httpx.ReadError)
        last_err: Optional[Exception] = None
        for attempt in range(max_retries):
            try:
                return await self.get_video_comments(video_id, order_mode, next_page, ps)
            except retryable as e:
                last_err = e
                if attempt < max_retries - 1:
                    delay = 5 * (2**attempt) + random.uniform(0, 1)
                    utils.logger.warning(
                        f"[BilibiliClient] Retry comments video_id={video_id} page={next_page} "
                        f"in {delay:.2f}s ({attempt + 1}/{max_retries}): {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    utils.logger.error(
                        f"[BilibiliClient] Max retries for comments video_id={video_id} page={next_page}: {e}"
                    )
        if last_err:
            utils.logger.error(f"[BilibiliClient] Giving up comment page video_id={video_id}: {last_err}")
        return None

    async def get_video_all_comments(
        self,
        video_id: str,
        crawl_interval: float = 1.0,
        is_fetch_sub_comments=False,
        callback: Optional[Callable] = None,
        max_count: int = 10,
    ):
        """
        Fetch level-1 comments (paginated), then optional level-2 replies per root comment.
        max_count <= 0 means no cap on level-1 count.
        """
        order_mode = resolve_bili_comment_order_mode()
        ps = _comment_page_size()
        unlimited = max_count <= 0

        level_one_comments: List[Dict] = []
        is_end = False
        next_page = 0

        # Phase 1: paginate all level-1 comments
        while not is_end:
            if not unlimited and len(level_one_comments) >= max_count:
                break

            comments_res = await self._fetch_video_comments_page_with_retry(
                video_id, order_mode, next_page, ps
            )
            if not comments_res:
                break

            cursor_info: Dict = comments_res.get("cursor") or {}
            comment_list: List[Dict] = list(comments_res.get("replies") or [])

            if not unlimited and len(level_one_comments) + len(comment_list) > max_count:
                comment_list = comment_list[: max_count - len(level_one_comments)]

            if callback and comment_list:
                await callback(video_id, comment_list)

            level_one_comments.extend(comment_list)

            if "is_end" not in cursor_info or "next" not in cursor_info:
                utils.logger.warning(
                    f"[BilibiliClient.get_video_all_comments] Missing cursor for video_id={video_id}, stop L1."
                )
                break

            is_end = cursor_info.get("is_end")
            next_page = cursor_info.get("next")
            if not isinstance(is_end, bool):
                is_end = True

            if is_end:
                break

            await asyncio.sleep(crawl_interval)

        l1_count = len(level_one_comments)
        l2_count = 0

        # Phase 2: level-2 replies for roots with rcount > 0
        if is_fetch_sub_comments:
            sub_ps = _sub_comment_page_size()
            sub_order = CommentOrderType.DEFAULT
            for comment in level_one_comments:
                if int(comment.get("rcount") or 0) <= 0:
                    continue
                comment_id = comment["rpid"]
                try:
                    n = await self.get_video_all_level_two_comments(
                        video_id,
                        comment_id,
                        sub_order,
                        sub_ps,
                        crawl_interval,
                        callback,
                    )
                    l2_count += n
                except Exception as e:
                    utils.logger.error(
                        f"[BilibiliClient.get_video_all_comments] L2 failed video_id={video_id} "
                        f"root={comment_id}: {e}"
                    )
                await asyncio.sleep(crawl_interval)

        total_saved = l1_count + l2_count
        utils.logger.info(
            f"[BilibiliClient.get_video_all_comments] video_id={video_id} "
            f"level1={l1_count} level2={l2_count} total_stored≈{total_saved} "
            f"order={order_mode.name} unlimited_l1={unlimited}"
        )
        return level_one_comments

    async def get_video_all_level_two_comments(
        self,
        video_id: str,
        level_one_comment_id: int,
        order_mode: CommentOrderType,
        ps: int = 10,
        crawl_interval: float = 1.0,
        callback: Optional[Callable] = None,
    ) -> int:
        """
        get video all level two comments for a level one comment
        Returns number of reply comments stored via callback.
        """
        stored = 0
        pn = 1
        while True:
            try:
                result = await self.get_video_level_two_comments(
                    video_id, level_one_comment_id, pn, ps, order_mode
                )
            except (DataFetchError, httpx.RemoteProtocolError, httpx.HTTPError) as e:
                utils.logger.error(
                    f"[BilibiliClient.get_video_all_level_two_comments] video_id={video_id} "
                    f"root={level_one_comment_id} pn={pn}: {e}"
                )
                break

            comment_list: List[Dict] = list(result.get("replies") or [])
            if callback and comment_list:
                await callback(video_id, comment_list)
            stored += len(comment_list)
            await asyncio.sleep(crawl_interval)
            page_count = int((result.get("page") or {}).get("count") or 0)
            if page_count <= pn * ps:
                break
            pn += 1
        return stored

    async def get_video_level_two_comments(
        self,
        video_id: str,
        level_one_comment_id: int,
        pn: int,
        ps: int,
        order_mode: CommentOrderType,
    ) -> Dict:
        """get video level two comments
        :param video_id: Video ID
        :param level_one_comment_id: Level one comment ID
        :param order_mode: Sort order

        :return:
        """
        uri = "/x/v2/reply/reply"
        post_data = {
            "oid": video_id,
            "mode": order_mode.value,
            "type": 1,
            "ps": ps,
            "pn": pn,
            "root": level_one_comment_id,
        }
        result = await self.get(uri, post_data)
        return result

    async def get_creator_videos(self, creator_id: str, pn: int, ps: int = 30, order_mode: SearchOrderType = SearchOrderType.LAST_PUBLISH) -> Dict:
        """get all videos for a creator
        :param creator_id: Creator ID
        :param pn: Page number
        :param ps: Number of videos per page
        :param order_mode: Sort order

        :return:
        """
        uri = "/x/space/wbi/arc/search"
        post_data = {
            "mid": creator_id,
            "pn": pn,
            "ps": ps,
            "order": order_mode.value,
        }
        return await self.get(uri, post_data)

    async def get_creator_info(self, creator_id: int) -> Dict:
        """
        get creator info
        :param creator_id: Creator ID
        """
        uri = "/x/space/wbi/acc/info"
        post_data = {
            "mid": creator_id,
        }
        return await self.get(uri, post_data)

    async def get_creator_fans(
        self,
        creator_id: int,
        pn: int,
        ps: int = 24,
    ) -> Dict:
        """
        get creator fans
        :param creator_id: Creator ID
        :param pn: Start page number
        :param ps: Number of items per page
        :return:
        """
        uri = "/x/relation/fans"
        post_data = {
            'vmid': creator_id,
            "pn": pn,
            "ps": ps,
            "gaia_source": "main_web",
        }
        return await self.get(uri, post_data)

    async def get_creator_followings(
        self,
        creator_id: int,
        pn: int,
        ps: int = 24,
    ) -> Dict:
        """
        get creator followings
        :param creator_id: Creator ID
        :param pn: Start page number
        :param ps: Number of items per page
        :return:
        """
        uri = "/x/relation/followings"
        post_data = {
            "vmid": creator_id,
            "pn": pn,
            "ps": ps,
            "gaia_source": "main_web",
        }
        return await self.get(uri, post_data)

    async def get_creator_dynamics(self, creator_id: int, offset: str = ""):
        """
        get creator comments
        :param creator_id: Creator ID
        :param offset: Parameter required for sending request
        :return:
        """
        uri = "/x/polymer/web-dynamic/v1/feed/space"
        post_data = {
            "offset": offset,
            "host_mid": creator_id,
            "platform": "web",
        }

        return await self.get(uri, post_data)

    async def get_creator_all_fans(
        self,
        creator_info: Dict,
        crawl_interval: float = 1.0,
        callback: Optional[Callable] = None,
        max_count: int = 100,
    ) -> List:
        """
        get creator all fans
        :param creator_info:
        :param crawl_interval:
        :param callback:
        :param max_count: Maximum number of fans to crawl for a creator

        :return: List of creator fans
        """
        creator_id = creator_info["id"]
        result = []
        pn = config.START_CONTACTS_PAGE
        while len(result) < max_count:
            fans_res: Dict = await self.get_creator_fans(creator_id, pn=pn)
            fans_list: List[Dict] = fans_res.get("list", [])

            pn += 1
            if len(result) + len(fans_list) > max_count:
                fans_list = fans_list[:max_count - len(result)]
            if callback:  # If there is a callback function, execute it
                await callback(creator_info, fans_list)
            await asyncio.sleep(crawl_interval)
            if not fans_list:
                break
            result.extend(fans_list)
        return result

    async def get_creator_all_followings(
        self,
        creator_info: Dict,
        crawl_interval: float = 1.0,
        callback: Optional[Callable] = None,
        max_count: int = 100,
    ) -> List:
        """
        get creator all followings
        :param creator_info:
        :param crawl_interval:
        :param callback:
        :param max_count: Maximum number of followings to crawl for a creator

        :return: List of creator followings
        """
        creator_id = creator_info["id"]
        result = []
        pn = config.START_CONTACTS_PAGE
        while len(result) < max_count:
            followings_res: Dict = await self.get_creator_followings(creator_id, pn=pn)
            followings_list: List[Dict] = followings_res.get("list", [])

            pn += 1
            if len(result) + len(followings_list) > max_count:
                followings_list = followings_list[:max_count - len(result)]
            if callback:  # If there is a callback function, execute it
                await callback(creator_info, followings_list)
            await asyncio.sleep(crawl_interval)
            if not followings_list:
                break
            result.extend(followings_list)
        return result

    async def get_creator_all_dynamics(
        self,
        creator_info: Dict,
        crawl_interval: float = 1.0,
        callback: Optional[Callable] = None,
        max_count: int = 20,
    ) -> List:
        """
        get creator all followings
        :param creator_info:
        :param crawl_interval:
        :param callback:
        :param max_count: Maximum number of dynamics to crawl for a creator

        :return: List of creator dynamics
        """
        creator_id = creator_info["id"]
        result = []
        offset = ""
        has_more = True
        while has_more and len(result) < max_count:
            dynamics_res = await self.get_creator_dynamics(creator_id, offset)
            dynamics_list: List[Dict] = dynamics_res["items"]
            has_more = dynamics_res["has_more"]
            offset = dynamics_res["offset"]
            if len(result) + len(dynamics_list) > max_count:
                dynamics_list = dynamics_list[:max_count - len(result)]
            if callback:
                await callback(creator_info, dynamics_list)
            await asyncio.sleep(crawl_interval)
            result.extend(dynamics_list)
        return result
