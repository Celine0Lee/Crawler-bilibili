# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/config/xhs_config.py
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


# Xiaohongshu platform configuration

# Sorting method, the specific enumeration value is in media_platform/xhs/field.py
SORT_TYPE = "popularity_descending"

# Specify the note URL list, which must carry the xsec_token parameter
XHS_SPECIFIED_NOTE_URL_LIST = [
    "https://www.xiaohongshu.com/explore/64b95d01000000000c034587?xsec_token=AB0EFqJvINCkj6xOCKCQgfNNh8GdnBC_6XecG4QOddo3Q=&xsec_source=pc_cfeed"
    # ........................
]

# Specify the creator URL list, which needs to carry xsec_token and xsec_source parameters.

XHS_CREATOR_ID_LIST = [
    "https://www.xiaohongshu.com/user/profile/5f58bd990000000001003753?xsec_token=ABYVg1evluJZZzpMX-VWzchxQ1qSNVW3r-jOEnKqMcgZw=&xsec_source=pc_search"
    # ........................
]

# creator mode: scan videos by publish time. 0 means no lookback limit.
XHS_CREATOR_VIDEO_LOOKBACK_DAYS = 0

# creator mode: collect up to N recent videos as candidates before ranking
XHS_CREATOR_CANDIDATE_VIDEO_COUNT = 20

# creator mode: Xiaohongshu may put pinned notes before the chronological feed
XHS_CREATOR_PINNED_NOTE_HEAD_COUNT = 2

# creator mode: keep the top N liked videos from the candidate set
XHS_CREATOR_TOP_LIKED_COUNT = 5

# creator mode: "video" | "normal" | "all"
XHS_CREATOR_NOTE_TYPE = "video"

# Safety cap for creator mode to avoid excessive requests on high-volume accounts.
XHS_CREATOR_MAX_CRAWL_COUNT = 180

# XHS note-detail stage concurrency. Keep modest to balance speed and risk control.
XHS_NOTE_DETAIL_MAX_CONCURRENCY = 1

# Hard timeout for one XHS note API-detail stage (seconds).
XHS_NOTE_DETAIL_API_TIMEOUT_SEC = 20

# Hard timeout for one XHS note HTML-fallback stage (seconds).
XHS_NOTE_DETAIL_HTML_TIMEOUT_SEC = 20

# Heartbeat log interval while waiting on a slow note-detail request (seconds).
XHS_NOTE_DETAIL_PROGRESS_HEARTBEAT_SEC = 10

# Sleep after each XHS note detail request (seconds). Keep lower than comment crawling.
XHS_NOTE_DETAIL_SLEEP_SEC = 3

