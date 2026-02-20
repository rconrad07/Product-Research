import re
import requests
import sys
from pathlib import Path
from typing import List, Tuple
from src.utils import get_logger

# We need a search function for the auto-fix. 
# We'll use the one from main/researcher if possible, or a local stub for testing.
try:
    from src.main import default_api_search_web as search_web
except ImportError:
    # Fallback for direct script execution if needed, 
    # but in the pipeline it should be passed in.
    def search_web(q): return []

logger = get_logger("validator", "URL_VALIDATOR")

class URLValidator:
    def __init__(self, report_path: str):
        self.report_path = Path(report_path)
        if not self.report_path.exists():
            raise FileNotFoundError(f"Report not found: {report_path}")
        self.content = self.report_path.read_text(encoding="utf-8")

    def validate_and_fix(self):
        """Main entry point to check URLs and patch the HTML if needed."""
        urls = self._extract_urls()
        if not urls:
            logger.info("No external URLs found to validate.")
            return

        logger.info(f"Validating {len(urls)} unique URLs...")
        
        replacements = []
        for url in urls:
            is_valid, reason = self._check_url(url)
            if not is_valid:
                logger.warning(f"  [FAIL] {reason}: {url}")
                new_url = self._attempt_fix(url)
                if new_url and new_url != url:
                    logger.info(f"  [FIXED] Found better link: {new_url}")
                    replacements.append((url, new_url))
            else:
                logger.info(f"  [PASS] {url}")

        if replacements:
            self._apply_patches(replacements)
            logger.info(f"Fixed {len(replacements)} URLs in {self.report_path.name}")
        else:
            logger.info("No URL fixes required.")

    def _extract_urls(self) -> List[str]:
        # Regex to find href="http..." while excluding common non-citation domains
        pattern = r'href="(https?://[^"]+)"'
        matches = re.findall(pattern, self.content)
        skip_domains = ["fonts.googleapis.com", "fonts.gstatic.com", "ajax.googleapis.com"]
        
        unique_urls = []
        for url in matches:
            if any(d in url for d in skip_domains):
                continue
            if url not in unique_urls:
                unique_urls.append(url)
        return unique_urls

    def _check_url(self, url: str) -> Tuple[bool, str]:
        """Checks status code and if it's just a root domain."""
        try:
            # Check for root/homepage
            match = re.match(r'https?://[^/]+/?$', url)
            if match:
                return False, "HOMEPAGE_LINK"

            # Check HTTP status
            resp = requests.head(url, timeout=10, allow_redirects=True)
            if 200 <= resp.status_code < 400:
                return True, "OK"
            return False, f"HTTP_{resp.status_code}"
        except Exception as e:
            return False, str(e)

    def _attempt_fix(self, broken_url: str) -> str:
        """Attempts to find a better deep-link using the context in the HTML."""
        # Find the text of the link or the preceding header/title
        # For simplicity in this regex approach, we look for the <a> tag content
        tag_pattern = rf'<a[^>]*href="{re.escape(broken_url)}"[^>]*>(.*?)</a>'
        match = re.search(tag_pattern, self.content)
        if not match:
            return None
        
        anchor_text = match.group(1).strip()
        # Clean the text for search
        search_query = f"{anchor_text} article research"
        logger.info(f"    Searching for better link: '{search_query}'")
        
        results = search_web(search_query)
        for r in results:
            new_url = r.get("url")
            if new_url:
                is_valid, _ = self._check_url(new_url)
                if is_valid:
                    return new_url
        return None

    def _apply_patches(self, replacements: List[Tuple[str, str]]):
        new_content = self.content
        for old, new in replacements:
            new_content = new_content.replace(f'href="{old}"', f'href="{new}"')
        self.report_path.write_text(new_content, encoding="utf-8")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python url_validator.py <path_to_html>")
        sys.exit(1)
    
    val = URLValidator(sys.argv[1])
    val.validate_and_fix()
