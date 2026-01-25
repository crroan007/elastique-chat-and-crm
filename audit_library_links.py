import json
import re
import sys
import os

# Ensure we can import from services
sys.path.append(os.path.join(os.getcwd()))

try:
    from services.citation_verifier import CitationVerifier
except ImportError:
    # If running from root without package structure
    from services.citation_verifier import CitationVerifier

def extract_urls_from_markdown(file_path):
    urls = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Regex for markdown links: [text](url)
            matches = re.findall(r'\[([^\]]+)\]\((http[^\)]+)\)', content)
            for text, url in matches:
                urls.append({'source': 'Markdown Table', 'label': text, 'url': url})
    except FileNotFoundError:
        print(f"File not found: {file_path}")
    return urls

def extract_urls_from_json(file_path):
    urls = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data:
                for fact in item.get('facts', []):
                    if fact.get('url'):
                        urls.append({
                            'source': 'JSON Library', 
                            'label': fact.get('citation', 'Unknown'), 
                            'url': fact.get('url')
                        })
    except FileNotFoundError:
        print(f"File not found: {file_path}")
    return urls

def main():
    verifier = CitationVerifier()
    
    # Files to check
    json_path = 'scientific_library.json'
    md_path = '07_Master_Research_Table.md'
    
    print(f"--- Starting Audit ---")
    
    all_links = extract_urls_from_json(json_path) + extract_urls_from_markdown(md_path)
    
    print(f"Found {len(all_links)} links to verify.\n")
    
    failures = []
    
    for link in all_links:
        print(f"Checking: {link['label'][:30]}... -> {link['url']}")
        is_valid, reason = verifier.verify_url(link['url'])
        
        if is_valid:
            print(f"   [PASS]")
        else:
            print(f"   [FAIL] {reason}")
            link['reason'] = reason
            failures.append(link)
            
    print("\n--- Audit Summary ---")
    print(f"Total: {len(all_links)}")
    print(f"Passed: {len(all_links) - len(failures)}")
    print(f"Failed: {len(failures)}")
    
    if failures:
        print("\nFailed Links (Action Required):")
        for f in failures:
            print(f"- {f['source']}: {f['label']} ({f['url']}) -> {f['reason']}")

if __name__ == "__main__":
    main()
