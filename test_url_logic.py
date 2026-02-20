import requests
import re

urls = [
    "https://www.expediagroup.com/investors/financial-information/", # Deep link
    "https://www.skift.com/", # Root (should be rejected)
    "https://www.booking.com/broken-link-123", # 404 (should be rejected)
]

def check(url):
    try:
        if re.match(r'https?://[^/]+/?$', url):
            return False, "ROOT"
        resp = requests.head(url, timeout=5, allow_redirects=True)
        return resp.status_code == 200, resp.status_code
    except Exception as e:
        return False, str(e)

for u in urls:
    print(f"{u} -> {check(u)}")
