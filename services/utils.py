"""工具模块 — 网络容错、重试机制"""
import time
import functools

import requests


def retry_on_network_error(max_retries: int = 3, base_delay: float = 1.0):
    """装饰器：网络异常时自动重试，指数退避

    Args:
        max_retries: 最大重试次数（不含首次调用）
        base_delay: 基础等待秒数，每次重试翻倍（1s → 2s → 4s）
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except requests.ConnectionError as e:
                    last_error = e
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt)
                        time.sleep(delay)
                except requests.Timeout as e:
                    last_error = e
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt)
                        time.sleep(delay)
                except requests.HTTPError as e:
                    # 5xx 服务端错误才重试，4xx 客户端错误不重试
                    if e.response is not None and e.response.status_code >= 500:
                        last_error = e
                        if attempt < max_retries:
                            delay = base_delay * (2 ** attempt)
                            time.sleep(delay)
                    else:
                        raise
            raise last_error  # type: ignore
        return wrapper
    return decorator
