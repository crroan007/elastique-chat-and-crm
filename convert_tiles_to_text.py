import json
import re

def html_to_text_tile(product):
    """Converts product data into a text-based tile."""
    title = product['title']
    price = product['price']
    benefits = product.get('benefits', 'Wellness')
    url = product['product_url']
    
    # Create text tile
    tile = f"""
┌─────────────────────────────┐
│  {title[:25].ljust(25)}  │
│  {benefits[:25].ljust(25)}  │
│  {price.ljust(25)}  │
│  [View Product →]           │
└─────────────────────────────┘
Link: {url}
"""
    return tile

def main():
    # Load existing tiles
    with open('ghl_product_tiles.json', 'r') as f:
        tiles = json.load(f)
    
    kb_entries = []
    
    for item in tiles:
        product = item['product']
        text_tile = html_to_text_tile(product)
        
        # Create KB entry
        entry = {
            "question": f"Show {product['title']}",
            "answer": f"Here is the {product['title']}:\n{text_tile}\n\n{product['description'][:100]}...",
            "document_id": None
        }
        kb_entries.append(entry)
        
    # Save new KB
    with open('ghl_knowledge_base_text.json', 'w') as f:
        json.dump(kb_entries, f, indent=2)
        
    print(f"Created {len(kb_entries)} text-based entries.")

if __name__ == "__main__":
    main()
