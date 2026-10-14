"""Explicit, logged retries. Only `TransientError` is retried, and only up to `RetryPolicy.max_attempts`."""

import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from rlcdselect.core.types import AttemptLog, FatalRunError, ProviderError, RetryPolicy, TransientError

T = TypeVar("T")


def error_kind(exc: BaseException) -> str:
    if isinstance(exc, TransientError):
        return "transient"
    if isinstance(exc, ProviderError):
        return exc.kind
    return "provider_error"


async def call_with_retry(
    fn: Callable[[], Awaitable[T]], policy: RetryPolicy
) -> tuple[T | None, BaseException | None, tuple[AttemptLog, ...]]:
    """Run `fn` under `policy`. Returns (result, final_error, attempts); exactly one of the first two is set."""
    attempts: list[AttemptLog] = []
    last: BaseException | None = None
    for index in range(policy.max_attempts):
        start = time.perf_counter()
        try:
            result = await fn()
        except FatalRunError:
            raise  # invalidates the run: never converted into a per-task error
        except TransientError as exc:
            attempts.append(AttemptLog(index, _ms(start), "transient", str(exc)))
            last = exc
            continue
        except Exception as exc:
            attempts.append(AttemptLog(index, _ms(start), error_kind(exc), str(exc)))
            return None, exc, tuple(attempts)
        attempts.append(AttemptLog(index, _ms(start)))
        return result, None, tuple(attempts)
    return None, last, tuple(attempts)


def total_latency(attempts: tuple[AttemptLog, ...]) -> float:
    """Wall time across all attempts, including failed ones (backoff, if any, is the client's)."""
    return sum(a.latency_ms for a in attempts)


def _ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000
