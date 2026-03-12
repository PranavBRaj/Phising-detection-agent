import logging
import re
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Static lookup tables used by the heuristics
# ---------------------------------------------------------------------------

# Free or abused TLDs commonly seen in disposable phishing domains
_SUSPICIOUS_TLDS: frozenset[str] = frozenset(
    {".tk", ".ml", ".ga", ".cf", ".gq", ".xyz", ".top", ".club", ".online", ".site", ".icu"}
)

# Well-known URL shortener root domains.
# Being behind a shortener is mildly suspicious; multiple shorteners in a
# chain is highly suspicious.
_URL_SHORTENERS: frozenset[str] = frozenset(
    {
        "bit.ly", "tinyurl.com", "goo.gl", "t.co", "ow.ly", "is.gd",
        "buff.ly", "adf.ly", "short.link", "rebrand.ly", "rb.gy",
        "cutt.ly", "shrtco.de", "tiny.cc", "clck.ru", "lnkd.in",
        "t.me", "go.ly", "yourls.org",
    }
)

# Regex patterns that imitate well-known brands in the *hostname*.
# Each pattern scores +0.35 if it matches because brand impersonation is a
# strong phishing indicator.
_PHISHING_HOSTNAME_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"paypa[l1]",
        r"app[l1]e[-.]",
        r"micro[-]?soft",
        r"go{2,}g[l1]e",
        r"[a@]mazon",
        r"netfl[i1]x",
        r"faceb[o0]{2}k",
        r"[il1]nstagram",
        r"twit+er",
        r"[il1]nter[-]?bank",
        r"secure[-.]?(login|signin|verify)",
        r"account[-.]?verif",
    ]
]

# Suspicious keywords anywhere in the URL path/query
_SUSPICIOUS_PATH_KEYWORDS: list[str] = [
    "phishing", "malware", "ransomware",
    "free-money", "win-prize", "claim-reward",
    "verify-account", "reset-password-now",
    "urgent-action", "account-suspended",
]

# Matches bare IP-address URLs, e.g. http://192.168.1.1/path
_IP_URL_RE = re.compile(r"^https?://(\d{1,3}\.){3}\d{1,3}([:/?#]|$)")

# Fraud decision threshold: URLs scoring at or above this are flagged
_FRAUD_THRESHOLD = 0.50


class FraudDetector:
    """
    Stateless heuristic analyser.  Call :meth:`analyze` with the dict
    produced by :class:`~app.services.url_tracer.URLTracer`.
    """

    def analyze(self, trace_result: dict) -> dict:
        """
        Run all heuristics against a trace result and return:

        {
            is_fraud    : bool   — True when score >= threshold,
            fraud_score : float  — normalised 0-1 risk score,
            fraud_reasons: list  — human-readable list of triggered rules,
        }
        """
        original_url: str = trace_result.get("original_url", "")
        final_url: str = trace_result.get("final_url", "")
        redirect_chain: list = trace_result.get("redirect_chain", [])
        redirect_count: int = trace_result.get("redirect_count", 0)

        score = 0.0
        reasons: list[str] = []

        # ── 1. Inspect the original URL ────────────────────────────────────
        s, r = self._check_url(original_url, "Original")
        score += s
        reasons.extend(r)

        # ── 2. Inspect the final (post-redirect) URL ───────────────────────
        if final_url and final_url != original_url:
            s, r = self._check_url(final_url, "Final")
            score += s * 0.8   # slightly discounted — we care most about origin
            reasons.extend(r)

        # ── 3. Analyse the redirect chain itself ───────────────────────────
        s, r = self._check_redirect_chain(redirect_chain, redirect_count)
        score += s
        reasons.extend(r)

        # ── 4. Cross-domain mismatch between origin and destination ────────
        if original_url and final_url and original_url != final_url:
            s, r = self._check_domain_mismatch(original_url, final_url)
            score += s
            reasons.extend(r)

        score = min(round(score, 4), 1.0)
        is_fraud = score >= _FRAUD_THRESHOLD

        logger.info(
            "Fraud analysis complete | score=%.4f | is_fraud=%s | url=%s",
            score, is_fraud, original_url,
        )

        return {
            "is_fraud": is_fraud,
            "fraud_score": score,
            "fraud_reasons": reasons,
        }

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _check_url(self, url: str, label: str) -> tuple[float, list[str]]:
        """Heuristics that operate on a single URL string."""
        score = 0.0
        reasons: list[str] = []

        if not url:
            return score, reasons

        try:
            parsed = urlparse(url)
            hostname: str = (parsed.hostname or "").lower()
            path: str = parsed.path or ""
            query: str = parsed.query or ""

            # Raw IP address — legitimate branded sites virtually never use bare IPs
            if _IP_URL_RE.match(url):
                score += 0.3
                reasons.append(f"{label} URL uses a raw IP address instead of a domain")

            # Suspicious free/abused TLD
            for tld in _SUSPICIOUS_TLDS:
                if hostname.endswith(tld):
                    score += 0.2
                    reasons.append(f"{label} URL has a high-risk TLD: {tld}")
                    break

            # Excessive subdomains (phishing kits often bury the brand name in subdomains)
            dot_count = hostname.count(".")
            if dot_count >= 3:
                score += 0.1 * (dot_count - 2)
                reasons.append(
                    f"{label} URL has an unusual number of subdomains ({dot_count} dots)"
                )

            # Brand impersonation in hostname
            for pattern in _PHISHING_HOSTNAME_PATTERNS:
                if pattern.search(hostname):
                    score += 0.35
                    reasons.append(
                        f"{label} URL hostname matches brand-impersonation pattern: {pattern.pattern!r}"
                    )
                    break

            # Suspicious path keywords
            full_path = (path + "?" + query).lower()
            for keyword in _SUSPICIOUS_PATH_KEYWORDS:
                if keyword in full_path:
                    score += 0.15
                    reasons.append(f"{label} URL path contains suspicious keyword: {keyword!r}")

            # Abnormally long URL — often used to hide the true destination
            if len(url) > 150:
                score += 0.1
                reasons.append(
                    f"{label} URL is unusually long ({len(url)} characters)"
                )

            # Sensitive page served over plain HTTP
            if parsed.scheme == "http":
                sensitive = {"login", "signin", "account", "password", "secure", "banking", "verify"}
                for kw in sensitive:
                    if kw in url.lower():
                        score += 0.2
                        reasons.append(
                            f"{label} URL uses unencrypted HTTP for a sensitive page (keyword: {kw!r})"
                        )
                        break

            # Excessive percent-encoding — common obfuscation technique
            if url.count("%") > 5:
                score += 0.15
                reasons.append(
                    f"{label} URL contains excessive percent-encoding (possible obfuscation)"
                )

        except Exception:
            logger.exception("Unexpected error checking URL: %s", url)

        return score, reasons

    def _check_redirect_chain(
        self, chain: list, redirect_count: int
    ) -> tuple[float, list[str]]:
        """Heuristics that operate on the full redirect chain."""
        score = 0.0
        reasons: list[str] = []

        # Long chains are a strong indicator of click-hijacking / traffic laundering
        if redirect_count >= 5:
            score += 0.3
            reasons.append(f"Excessive redirect chain: {redirect_count} hops detected")
        elif redirect_count >= 3:
            score += 0.1
            reasons.append(f"Multiple redirects in chain: {redirect_count} hops")

        # Count how many chain hops route through URL shorteners
        shortener_hops = 0
        for hop in chain:
            hop_url: str = hop.get("url", "")
            try:
                root = self._root_domain(urlparse(hop_url).hostname or "")
                if root in _URL_SHORTENERS:
                    shortener_hops += 1
            except Exception:
                pass

        if shortener_hops >= 2:
            score += 0.25
            reasons.append(
                f"Redirect chain passes through {shortener_hops} URL shortener services"
            )
        elif shortener_hops == 1:
            score += 0.1
            reasons.append("Redirect chain passes through a URL shortener")

        # Count distinct root domains in the chain
        root_domains: set[str] = set()
        for hop in chain:
            try:
                root = self._root_domain(urlparse(hop.get("url", "")).hostname or "")
                if root:
                    root_domains.add(root)
            except Exception:
                pass

        if len(root_domains) >= 3:
            score += 0.2
            reasons.append(
                f"Redirect chain crosses {len(root_domains)} distinct domains"
            )

        return score, reasons

    def _check_domain_mismatch(
        self, original_url: str, final_url: str
    ) -> tuple[float, list[str]]:
        """Checks whether the final destination domain differs from the original."""
        score = 0.0
        reasons: list[str] = []

        try:
            orig_root = self._root_domain(urlparse(original_url).hostname or "")
            final_root = self._root_domain(urlparse(final_url).hostname or "")

            if orig_root and final_root and orig_root != final_root:
                score += 0.2
                reasons.append(
                    f"Final destination ({final_root}) differs from original domain ({orig_root})"
                )

                if final_root in _URL_SHORTENERS:
                    score += 0.1
                    reasons.append(
                        f"Final destination is a URL shortener domain: {final_root}"
                    )

        except Exception:
            logger.exception("Error in domain mismatch check")

        return score, reasons

    @staticmethod
    def _root_domain(hostname: str) -> str:
        """Return the registered domain (last two labels), e.g. 'evil.xyz' from 'login.evil.xyz'."""
        if not hostname:
            return ""
        parts = hostname.rstrip(".").split(".")
        return ".".join(parts[-2:]) if len(parts) >= 2 else hostname
