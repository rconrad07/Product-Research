import re
import requests
import sys
from pathlib import Path
from typing import List, Tuple
from src.utils import get_logger

# We need a search function for the auto-fix. 
try:
    from src.main import default_api_search_web as search_web
except ImportError:
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
        to_delete = []
        
        for url in urls:
            is_valid, reason = self._check_url(url)
            if not is_valid:
                logger.warning(f"  [FAIL] {reason}: {url}")
                new_url = self._attempt_fix(url)
                if new_url and new_url != url:
                    logger.info(f"  [FIXED] Found better link: {new_url}")
                    replacements.append((url, new_url))
                else:
                    logger.error(f"  [LABEL] No fix found for broken link. Marking as unverified.")
                    to_delete.append(url)
            else:
                logger.info(f"  [PASS] {url}")

        if replacements or to_delete:
            self._apply_patches(replacements, to_delete)
            logger.info(f"Updated {self.report_path.name}: {len(replacements)} fixed, {len(to_delete)} labeled as unverified.")
        else:
            logger.info("No URL actions required.")

    def _extract_urls(self) -> List[str]:
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
        try:
            if re.match(r'https?://[^/]+/?$', url):
                return False, "HOMEPAGE_LINK"
            resp = requests.head(url, timeout=10, allow_redirects=True)
            if 200 <= resp.status_code < 400:
                return True, "OK"
            return False, f"HTTP_{resp.status_code}"
        except Exception as e:
            return False, str(e)

    def _attempt_fix(self, broken_url: str) -> str:
        tag_pattern = rf'<a[^>]*href="{re.escape(broken_url)}"[^>]*>(.*?)</a>'
        match = re.search(tag_pattern, self.content)
        if not match:
            return None
        
        anchor_text = match.group(1).strip()
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

    def _apply_patches(self, replacements: List[Tuple[str, str]], to_delete: List[str]):
        new_content = self.content
        
        # 1. Apply replacements
        for old, new in replacements:
            new_content = new_content.replace(f'href="{old}"', f'href="{new}"')
        
        for url in to_delete:
            # 1. Label the source link in the Sources section
            source_link_pattern = rf'(<div class="source-link">.*?href="{re.escape(url)}".*?)(</div>)'
            new_content = re.sub(source_link_pattern, r'\1 <span class="unverified-label">(Unverified)</span>\2', new_content, flags=re.DOTALL)
            
            # 2. Add unverified class to any link with this URL
            new_content = new_content.replace(f'href="{url}"', f'href="{url}" class="unverified-link"')
            
            # 3. Append label to anchor tags
            anchor_pattern = rf'(<a[^>]*href="{re.escape(url)}"[^>]*>.*?)(</a>)'
            new_content = re.sub(anchor_pattern, r'\1 <span class="unverified-label">(Unverified)</span>\2', new_content, flags=re.DOTALL)

        self.report_path.write_text(new_content, encoding="utf-8")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(1)
    
    val = URLValidator(sys.argv[1])
    val.validate_and_fix()
