import logging
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# A benign user-agent so sites do not block the probe request
_USER_AGENT = "Mozilla/5.0 (compatible; FraudDetector/1.0; +https://github.com/fraud-detector)"


class URLTracer:
    """
    Traces a URL through its full redirect chain and returns metadata
    about each hop, the final destination, and timing information.
    """

    def __init__(self, max_redirects: int = 10, timeout: int = 10) -> None:
        self.max_redirects = max_redirects
        self.timeout = timeout

    async def trace(self, url: str) -> dict:
        """
        Follow all HTTP redirects for *url* and return a summary dict.

        Returns
        -------
        {
            original_url    : str   — the input URL,
            final_url       : str   — URL after all redirects,
            redirect_chain  : list  — [{url, status_code}, …] for each hop,
            redirect_count  : int   — number of hops (0 = no redirects),
            status_code     : int | None — final HTTP status,
            response_time_ms: int   — total wall-clock time in milliseconds,
        }
        """
        chain: list[dict] = []
        start = time.monotonic()

        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                max_redirects=self.max_redirects,
                timeout=self.timeout,
                verify=False,  # Intentional: we analyse suspicious sites that may use invalid certs
                headers={"User-Agent": _USER_AGENT},
            ) as client:
                response = await client.get(url)

                # httpx stores all intermediate responses in response.history
                for hist in response.history:
                    chain.append(
                        {
                            "url": str(hist.url),
                            "status_code": hist.status_code,
                        }
                    )

                final_url = str(response.url)
                status_code: Optional[int] = response.status_code

        except httpx.TooManyRedirects:
            logger.warning("Too many redirects for %s", url)
            final_url = url
            status_code = None
            chain.append({"url": url, "status_code": None, "error": "too_many_redirects"})

        except httpx.TimeoutException:
            logger.warning("Timeout tracing %s", url)
            final_url = url
            status_code = None
            chain.append({"url": url, "status_code": None, "error": "timeout"})

        except httpx.RequestError as exc:
            logger.warning("Request error tracing %s: %s", url, exc)
            final_url = url
            status_code = None
            chain.append({"url": url, "status_code": None, "error": str(exc)})

        response_time_ms = int((time.monotonic() - start) * 1000)

        return {
            "original_url": url,
            "final_url": final_url,
            "redirect_chain": chain,
            "redirect_count": len(chain),
            "status_code": status_code,
            "response_time_ms": response_time_ms,
        }
