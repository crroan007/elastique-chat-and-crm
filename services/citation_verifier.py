import requests
import time
from typing import Dict, Tuple

class CitationVerifier:
    """
    Performs deep verification of scientific URLs.
    Detects 404s, Soft 404s, 'Prohibited' pages, and empty content.
    """
    
    BLOCKLIST_KEYWORDS = [
        "404 not found",
        "page not found",
        "access denied",
        "prohibited",
        "forbidden",
        "content removed",
        "site under maintenance",
        "domain expired",
        "blocked"
    ]

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    def verify_url(self, url: str) -> Tuple[bool, str]:
        """
        Returns (is_valid, reason).
        """
        if not url or not url.startswith('http'):
            return False, "Invalid URL Syntax"

        try:
            # We use GET, not HEAD, because we need to check the body content
            response = requests.get(url, headers=self.HEADERS, timeout=10, allow_redirects=True)
            
            # 1. Status Code Check
            if response.status_code != 200:
                return False, f"Status Code {response.status_code}"

            # 2. Content Length Check (Empty/Garbage pages)
            content = response.text.lower()
            if len(content) < 500:
                return False, f"Content too short ({len(content)} bytes) - Suspicious"

            # 3. Keyword/Soft-404 Check
            # We check the <title> specifically and the <body> generally
            for keyword in self.BLOCKLIST_KEYWORDS:
                if keyword in content:
                    # Double check context? For now, strict fail.
                    return False, f"Suspicious keyword found: '{keyword}'"

            return True, "Verified"

        except requests.exceptions.Timeout:
            return False, "Timed Out"
        except requests.exceptions.RequestException as e:
            return False, f"Connection Error: {str(e)}"

if __name__ == "__main__":
    # Quick Test
    verifier = CitationVerifier()
    test_urls = [
        "https://google.com", 
        "https://wexnermedical.osu.edu/sports-medicine", # From library
        "https://httpstat.us/403",
        "https://httpstat.us/404"
    ]
    
    print("Running Logic Test...")
    for u in test_urls:
        valid, reason = verifier.verify_url(u)
        print(f"[{'PASS' if valid else 'FAIL'}] {u}: {reason}")
