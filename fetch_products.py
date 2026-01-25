import urllib.request
import json
import ssl

def fetch_products():
    url = "https://www.elastiqueathletics.com/products.json?limit=250"
    try:
        context = ssl._create_unverified_context()
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        )
        with urllib.request.urlopen(req, context=context) as response:
            data = json.loads(response.read().decode('utf-8'))
            with open('valid_products.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            print(f"Successfully fetched {len(data.get('products', []))} products.")
            
    except Exception as e:
        print(f"Error fetching products: {e}")

if __name__ == "__main__":
    fetch_products()
