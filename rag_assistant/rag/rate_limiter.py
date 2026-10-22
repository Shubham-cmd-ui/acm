import re
import time
import random
import logging
from typing import Callable, Any, Optional

logger = logging.getLogger(__name__)


class RateLimitExceededError(Exception):
    """Raised when Gemini API rate limit is exceeded and max retries have been exhausted."""
    pass


def is_rate_limit_error(error: Exception) -> bool:
    """
    Determines if an exception is caused by Gemini API rate limits or quota exhaustion (HTTP 429).
    """
    if not error:
        return False

    # Check direct attributes on google.genai.errors.APIError or google-api-core
    code = getattr(error, 'code', None)
    if code == 429:
        return True

    status = getattr(error, 'status', None)
    if status and 'RESOURCE_EXHAUSTED' in str(status).upper():
        return True

    # Check string representation across SDK exceptions
    err_str = str(error).lower()
    rate_limit_keywords = [
        '429',
        'resource_exhausted',
        'quota exceeded',
        'rate limit',
        'too many requests',
        'quotafailure',
        'retryinfo',
        'embed_content_free_tier_requests',
        'generate_content_free_tier_requests',
    ]
    return any(keyword in err_str for keyword in rate_limit_keywords)


def extract_retry_delay(error: Exception, default_delay: float = 10.0) -> float:
    """
    Extracts the recommended retry delay (in seconds) from Gemini API error details or text.
    Adds a 1.0 second safety margin to ensure the quota window has truly refreshed.
    """
    # 1. Try inspecting structured details from google.genai.errors.APIError
    details = getattr(error, 'details', None)
    if isinstance(details, dict):
        # Often nested in details['error']['details'] or details['details']
        error_dict = details.get('error', details)
        info_list = error_dict.get('details', []) if isinstance(error_dict, dict) else []
        if isinstance(info_list, list):
            for item in info_list:
                if isinstance(item, dict) and 'retryDelay' in item:
                    delay_raw = str(item['retryDelay']).strip().rstrip('s')
                    try:
                        return max(float(delay_raw) + 1.0, 2.0)
                    except ValueError:
                        pass

    # 2. Check regex patterns against string representation
    err_str = str(error)

    # Pattern: "Please retry in 9.363317543s"
    match = re.search(r'retry in\s+([0-9]+(?:\.[0-9]+)?)s', err_str, re.IGNORECASE)
    if match:
        try:
            return max(float(match.group(1)) + 1.0, 2.0)
        except ValueError:
            pass

    # Pattern: 'retryDelay': '9s' or "retryDelay": "9.5s"
    match = re.search(r'["\']retryDelay["\']:\s*["\']([0-9]+(?:\.[0-9]+)?)s?["\']', err_str, re.IGNORECASE)
    if match:
        try:
            return max(float(match.group(1)) + 1.0, 2.0)
        except ValueError:
            pass

    return default_delay


def execute_with_rate_limit_retry(
    func: Callable[..., Any],
    *args,
    max_retries: int = 5,
    initial_delay: float = 5.0,
    backoff_factor: float = 1.5,
    max_delay: float = 60.0,
    context_desc: str = "Gemini API call",
    sleep_fn: Optional[Callable[[float], None]] = None,
    **kwargs
) -> Any:
    """
    Executes a callable with automatic exponential backoff and quota recovery
    when Gemini API rate limit (429 RESOURCE_EXHAUSTED) is encountered.
    """
    _sleep = sleep_fn if sleep_fn is not None else time.sleep

    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if not is_rate_limit_error(e):
                # Non-rate-limit errors are propagated immediately
                raise e

            if attempt >= max_retries:
                logger.error(f"{context_desc} failed: Rate limit exceeded after {max_retries} retries.")
                raise RateLimitExceededError(
                    "Gemini API rate limit reached (Free Tier limit: 100 requests/minute). "
                    "Please wait about 30-60 seconds before trying again."
                ) from e

            # Extract delay recommended by Google, or calculate exponential backoff
            raw_delay = extract_retry_delay(e, default_delay=0.0)
            if raw_delay > 0:
                delay = min(raw_delay, max_delay)
            else:
                delay = min(initial_delay * (backoff_factor ** attempt) + random.uniform(0.5, 1.5), max_delay)

            logger.warning(
                f"{context_desc} hit Gemini rate limit (429 RESOURCE_EXHAUSTED). "
                f"Backing off for {delay:.2f}s before retry ({attempt + 1}/{max_retries})..."
            )
            _sleep(delay)
