import urllib.request
import urllib.error

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

def get_page_content(url):
    print(f"Checking: {url}")
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': USER_AGENT}, 
            method='GET'
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            content = response.read().decode('utf-8', errors='ignore')
            print(f"Status: {response.status}")
            print(f"Final URL: {response.geturl()}")
            print(f"Content Length: {len(content)}")
            
            # Check for common indicators
            import re
            title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE)
            if title_match:
                print(f"Title: {title_match.group(1)}")

            indicators = [
                "Page not found",
                "404 Page Not Found",
                "Add to cart",
                "Sold out"
            ]
            print("Indicators found in body:")
            for ind in indicators:
                if ind.lower() in content.lower():
                    print(f"  - {ind}")
                    
            return content
    except Exception as e:
        print(f"Error: {e}")
        return None

print("--- BROKEN LINK ---")
content_broken = get_page_content("https://www.elastiqueathletics.com/products/iconic-3-4-sleeve-top")

print("\n--- REPORTED WORKING LINK ---")
content_working = get_page_content("https://www.elastiqueathletics.com/products/loriginal-leggings")
