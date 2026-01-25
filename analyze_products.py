import json

def analyze():
    try:
        with open('valid_products.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        products = data.get('products', [])
        print(f"Total products: {len(products)}")
        
        print("\n--- 'Iconic' Matches ---")
        for p in products:
            if 'iconic' in p['handle'] or 'iconic' in p['title'].lower():
                print(f"Handle: {p['handle']} | Title: {p['title']}")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    analyze()
