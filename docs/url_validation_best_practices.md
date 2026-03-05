# URL Validation Fix: Instructions for LLM Implementation

These instructions address the two root causes of URL citation failures, specifically when using Gemini 3 Flash — **LLM hallucination** and **broken HTTP validation** — and provide exact code patterns to fix them.

---

## Part 1: Diagnose First

Before touching any code, answer these two questions by reading the codebase:

**Q1: Does the search pipeline actually run live web searches?**
Look for any function passed to your agents as a `search_fn` or equivalent. If it returns `[]` or contains a stub comment like `"replace with real implementation"`, web search is NOT running. The LLM is generating URLs from its training data. Go to Part 2A.

**Q2: Does your URL validator use `requests.head()`?**
Many sites (NN/g, RealEye, Medium, etc.) block `HEAD` requests with a `403` or `404`, causing valid links to appear broken. Go to Part 2B.

---

## Part 2A: Fix URL Hallucination in Prompts

Search your system prompts for any language that allows citations without a verified source. Common examples:

```
"DEPTH IS PRIORITY #1 ... include evidence even if the URL is uncertain"
"include it even if the URL is from a secondary or less stable source"
"we value context over clean link lists"
```

**Replace any such language with this strict rule:**

```
DEPTH AND VERIFIABILITY ARE BOTH REQUIRED: Only include source URLs that 
appear verbatim in the SEARCH RESULTS block provided to you. Do not generate 
or guess URLs. If a claim has no verifiable URL from the search results, 
either omit the claim, or state "No verified source available."
```

---

## Part 2B: Fix the HTTP Validator (`requests.head` → `requests.get`)

Replace your URL checking method with the following pattern:

```python
import re
import requests

def check_url(url: str) -> tuple[bool, str]:
    # Reject pure homepages (no path) but allow domain/article paths
    path = re.sub(r'https?://[^/]+', '', url).strip('/')
    if not path:
        return False, "HOMEPAGE_LINK"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        resp = requests.get(url, timeout=12, allow_redirects=True, headers=headers)
        if 200 <= resp.status_code < 400:
            return True, "OK"
        return False, f"HTTP_{resp.status_code}"
    except Exception as e:
        return False, str(e)
```

**Key changes vs. the broken pattern:**

| Issue | Old (Broken) | New (Fixed) |
|---|---|---|
| Request method | `requests.head()` | `requests.get()` |
| User-Agent | None or `"bot/1.0"` | Full Chrome UA string |
| Homepage detection | Regex on full URL | Strip domain, check if path is empty |
| Timeout | 10s | 12s |

---

## Part 3: Handle Broken Links Gracefully

If a URL fails validation and cannot be auto-fixed by a search, **do not silently remove it**. Label it instead:

```html
<a href="URL" class="unverified-link">Source Title 
  <span class="unverified-label">(Unverified)</span>
</a>
```

This preserves context while being transparent. Users can validate manually if needed.
