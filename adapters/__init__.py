"""适配器注册表 — 在此注册所有已启用的数据源适配器。

注意：使用类列表而非实例列表，通过 get_adapters() 按需实例化，
避免模块导入时过早读取环境变量。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from adapters.base import BaseAdapter

from adapters.github_trending import GitHubTrendingAdapter
from adapters.hackernews import HackerNewsAdapter
from adapters.huggingface_papers import HuggingFacePapersAdapter
from adapters.lobsters import LobstersAdapter
# from adapters.reddit import RedditAdapter
from adapters.devto import DevToAdapter
from adapters.producthunt import ProductHuntAdapter
from adapters.ycombinator import YCombinatorAdapter
from adapters.substack import SubstackAdapter
from adapters.quanta_magazine import QuantaMagazineAdapter
from adapters.newsapi import NewsAPIAdapter
from adapters.pubmed import PubMedAdapter
from adapters.nber import NBERAdapter
from adapters.rand import RANDAdapter
from adapters.brookings import BrookingsAdapter
from adapters.wikipedia_current_events import WikipediaCurrentEventsAdapter
from adapters.mit_tech_review import MITTechReviewAdapter
from adapters.kr36 import Kr36Adapter
from adapters.openai_blog import OpenAIBlogAdapter
from adapters.google_ai_blog import GoogleAIBlogAdapter
from adapters.nature import NatureAdapter
from adapters.changelog import ChangelogAdapter
from adapters.science_journal import ScienceJournalAdapter
from adapters.import_ai import ImportAIAdapter
from adapters.nautilus import NautilusAdapter
from adapters.sspai import SspaiAdapter
from adapters.ft import FTAdapter

_ADAPTER_CLASSES = [
    GitHubTrendingAdapter,
    HackerNewsAdapter,
    HuggingFacePapersAdapter,
    LobstersAdapter,
    # RedditAdapter,
    DevToAdapter,
    ProductHuntAdapter,
    YCombinatorAdapter,
    SubstackAdapter,
    QuantaMagazineAdapter,
    NewsAPIAdapter,
    PubMedAdapter,
    NBERAdapter,
    RANDAdapter,
    BrookingsAdapter,
    WikipediaCurrentEventsAdapter,
    MITTechReviewAdapter,
    Kr36Adapter,
    OpenAIBlogAdapter,
    GoogleAIBlogAdapter,
    NatureAdapter,
    ChangelogAdapter,
    ScienceJournalAdapter,
    ImportAIAdapter,
    NautilusAdapter,
    SspaiAdapter,
    FTAdapter,
]


_adapters_cache: list[BaseAdapter] | None = None


def get_adapters() -> list[BaseAdapter]:
    """懒加载：首次调用时实例化所有适配器并缓存，后续直接返回缓存。"""
    global _adapters_cache
    if _adapters_cache is None:
        _adapters_cache = [cls() for cls in _ADAPTER_CLASSES]
    return _adapters_cache
