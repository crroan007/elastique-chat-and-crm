import urllib.request
import urllib.error

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
TIMEOUT = 5

def check_link(url):
    try:
        # Use GET to follow redirects properly and check final URL
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': USER_AGENT}, 
            method='GET'
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            final_url = response.geturl()
            status = response.status
            
            print(f"Original: {url}")
            print(f"Final:    {final_url}")
            print(f"Status:   {status}")

            # Content-based check for elastiqueathletics.com
            if 'elastiqueathletics.com' in url:
                try:
                    content = response.read().decode('utf-8', errors='ignore').lower()
                    
                    import re
                    title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE)
                    title = title_match.group(1) if title_match else ""
                    print(f"Title: {title}")

                    if '404' in title or 'page not found' in title:
                         return 404, "404 Not Found (Title Match)"
                    if "we couldn't find the page" in content:
                         return 404, "404 Not Found (Body Text Match)"

                    if 'add to cart' in content or 'sold out' in content:
                        return 200, "OK (Verified by Content)"
                    
                except Exception as e:
                    pass 

            return status, "OK"
            
    except urllib.error.HTTPError as e:
        if 'elastiqueathletics.com' in url:
            try:
                content = e.read().decode('utf-8', errors='ignore').lower()
                if 'add to cart' in content or 'sold out' in content:
                     return 200, "OK (Verified by Content despite status)"
            except:
                pass
        return e.code, f"HTTP Error: {e.reason}"
    except urllib.error.URLError as e:
        return 0, f"Connection Error: {e.reason}"
    except Exception as e:
        return 0, f"Error: {str(e)}"

print(check_link("https://www.elastiqueathletics.com/products/iconic-3-4-sleeve-top"))
