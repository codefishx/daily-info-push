"""适配器注册表 — 在此注册所有已启用的数据源适配器。"""

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

ADAPTERS = [
    GitHubTrendingAdapter(),
    HackerNewsAdapter(),
    HuggingFacePapersAdapter(),
    LobstersAdapter(),
    # RedditAdapter(),
    DevToAdapter(),
    ProductHuntAdapter(),
    YCombinatorAdapter(),
    SubstackAdapter(),
    QuantaMagazineAdapter(),
    NewsAPIAdapter(),
    PubMedAdapter(),
    NBERAdapter(),
    RANDAdapter(),
    BrookingsAdapter(),
    WikipediaCurrentEventsAdapter(),
    MITTechReviewAdapter(),
    Kr36Adapter(),
    OpenAIBlogAdapter(),
    GoogleAIBlogAdapter(),
    NatureAdapter(),
    ChangelogAdapter(),
    ScienceJournalAdapter(),
    ImportAIAdapter(),
    NautilusAdapter(),
    SspaiAdapter(),
    FTAdapter(),
]
