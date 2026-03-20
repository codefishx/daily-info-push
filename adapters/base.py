"""数据源适配器抽象基类。"""

from __future__ import annotations

import logging
import os
import time
from abc import ABC, abstractmethod
from typing import List

from models import RawItem

DEFAULT_TIMEOUT = 15       # 每次请求超时秒数
DEFAULT_MAX_RETRIES = 3    # 最大重试次数
_BACKOFF_BASE = 1          # 退避基数（秒），实际等待: 1s, 2s, 4s

_logger = logging.getLogger(__name__)


class BaseAdapter(ABC):
    """所有数据源适配器必须继承此基类。

    子类通过继承自动获得：
    - self.timeout  — 请求超时秒数（优先读取 ADAPTER_TIMEOUT 环境变量，默认 DEFAULT_TIMEOUT）
    - fetch_with_retry()  — 带指数退避重试的抓取入口
    """

    @property
    def timeout(self) -> int:
        return int(os.environ.get("ADAPTER_TIMEOUT", DEFAULT_TIMEOUT))

    @property
    @abstractmethod
    def name(self) -> str:
        """数据源名称，如 'GitHub Trending'。"""

    @abstractmethod
    def fetch(self) -> List[RawItem]:
        """抓取并返回标准化数据列表。失败时抛出异常，由调用方捕获处理。"""

    def fetch_with_retry(self, max_retries: int | None = None) -> List[RawItem]:
        """带指数退避重试的 fetch 入口。

        重试间隔：1s → 2s → 4s（最多 max_retries 次重试，共 max_retries+1 次尝试）。
        所有尝试均失败时抛出最后一次异常。
        max_retries 优先读取 ADAPTER_MAX_RETRIES 环境变量，默认 DEFAULT_MAX_RETRIES。
        """
        if max_retries is None:
            max_retries = int(os.environ.get("ADAPTER_MAX_RETRIES", DEFAULT_MAX_RETRIES))
        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                return self.fetch()
            except Exception as exc:
                last_exc = exc
                if attempt < max_retries:
                    wait = _BACKOFF_BASE * (2 ** attempt)
                    _logger.debug(
                        "[%s] 第 %d 次失败，%.0fs 后重试: %s",
                        self.name, attempt + 1, wait, exc,
                    )
                    time.sleep(wait)
        raise last_exc  # type: ignore[misc]
