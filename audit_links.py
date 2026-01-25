import os
import re
import urllib.request
import urllib.error
import zipfile
import xml.etree.ElementTree as ET
import csv
import json
import time
from urllib.parse import urlparse

# Configuration
ROOT_DIRS = ['.', 'Training Data']
EXTENSIONS = {'.md', '.txt', '.csv', '.json', '.docx'}
REPORT_FILE = 'LINK_AUDIT_REPORT_CLEAN.md'
TIMEOUT = 5
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

def extract_text_from_docx(docx_path):
    try:
        with zipfile.ZipFile(docx_path) as zf:
            if 'word/document.xml' not in zf.namelist():
                return ""
            xml_content = zf.read('word/document.xml')
            
        tree = ET.fromstring(xml_content)
        namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        
        text_content = []
        for p in tree.findall('.//w:p', namespaces):
            texts = [node.text for node in p.findall('.//w:t', namespaces) if node.text]
            if texts:
                text_content.append(''.join(texts))
        return '\n'.join(text_content)
    except Exception as e:
        print(f"Error reading docx {docx_path}: {e}")
        return ""

def extract_links_with_context(text, file_path):
    # Regex for http/https URLs
    # Simplified regex to capture common URLs
    # Regex for http/https URLs
    # Exclude backticks and common markdown closing chars from the valid URL set
    url_pattern = re.compile(r'(https?://[^\s)"`]+)')
    
    links = []
    lines = text.split('\n')
    for line_num, line in enumerate(lines, 1):
        for match in url_pattern.finditer(line):
            url = match.group(1)
            # Remove trailing punctuation that might have been caught
            url = url.rstrip('.,;:>`)]')
            
            start = max(0, match.start() - 50)
            end = min(len(line), match.end() + 50)
            context = line[start:end].replace('\n', ' ').strip()
            
            links.append({
                'file': file_path,
                'line': line_num,
                'url': url,
                'context': context
            })
    return links

def check_link(url):
    # FILTER: Only check Elastique Product links as requested. 
    # Also ignore Calendly as requested.
    if 'calendly.com' in url:
        return 200, "Skipped (Calendly)"
        
    if 'elastiqueathletics.com' not in url:
        return 200, "Skipped (Non-Product Link)"

    try:
        # Use GET to fetch content
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': USER_AGENT}, 
            method='GET'
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            final_url = response.geturl()
            status = response.status
            
            # --- STRICT DOM VISUAL CONFIRMATION ---
            try:
                content = response.read().decode('utf-8', errors='ignore').lower()
                
                # 1. Negative Check: Title or H1 for 404
                # Title often contains "404 Not Found"
                if '<title>404' in content or 'page not found' in content.split('</title>')[0]:
                     return 404, "404 Not Found (Title Match)"
                
                # 2. Strong Positive Check (Visual Elements)
                # A valid product page MUST have an "Add to Cart" form/button specifically for the main product.
                # Simply finding "add to cart" text is risky because 404 pages have "Recommended Products".
                # We look for the main product form or button.
                
                # Common Shopify signals for the PRIMARY product:
                has_product_form = 'form' in content and 'action="/cart/add"' in content
                has_add_button = 'name="add"' in content or 'type="submit"' in content
                
                if has_product_form:
                    return 200, "OK (Verified Product Page - Form Found)"
                    
                # If we don't see a product form, it might be a blog or collection, but if it was supposed to be a product...
                # Let's check for "Sold Out" specifically in a button
                if 'sold out' in content and '<button' in content:
                     return 200, "OK (Verified Product Page - Sold Out)"

                # If we are here, we have a 200 OK page, but it lacks a product form.
                # It is likely a "Soft 404" (Redirect to Home/Collection) or a Broken Product Page.
                
                # Check for "Soft 404" redirection indicators
                if final_url.strip('/') == 'https://www.elastiqueathletics.com':
                    return 404, "404 (Soft - Redirected to Home)"
                if '/collections/all' in final_url:
                    return 404, "404 (Soft - Redirected to Collection)"

                # Fallback: If it lacks "Add to Cart" form, treat as broken for a "Product" link check.
                # This is the "Visual Confirmation" - if no buy button, it's not a working product page.
                return 404, "404 (No Product Form Detected)"

            except Exception as e:
                # If we can't read content, we can't verify visually.
                return status, f"Warning: Content mismatch ({str(e)})"
            
    except urllib.error.HTTPError as e:
        return e.code, f"HTTP Error: {e.reason}"

    except urllib.error.URLError as e:
        return 0, f"Connection Error: {e.reason}"
    except Exception as e:
        return 0, f"Error: {str(e)}"

def main():
    print("Starting Link Audit...")
    all_links = []
    
    # 1. Scan files
    files_to_scan = []
    for root_dir in ROOT_DIRS:
        if root_dir == '.':
            # Scan root but exclude directories starting with . or venv
            for item in os.listdir('.'):
                if os.path.isfile(item) and os.path.splitext(item)[1].lower() in EXTENSIONS:
                     files_to_scan.append(os.path.abspath(item))
                elif os.path.isdir(item) and not item.startswith('.') and item != 'Training Data': 
                     # Recurse into other subdirs if needed, but 'Training Data' is handled explicitly
                     # For now, let's just stick to the plan of scanning . and Training Data specifically
                     pass 
        else:
            if os.path.exists(root_dir):
                for root, dirs, files in os.walk(root_dir):
                    for file in files:
                        if os.path.splitext(file)[1].lower() in EXTENSIONS:
                            files_to_scan.append(os.path.join(root, file))

    print(f"Found {len(files_to_scan)} files to scan.")

    # 2. Extract links
    for file_path in files_to_scan:
        try:
            ext = os.path.splitext(file_path)[1].lower()
            content = ""
            
            # File-specific handling
            if ext == '.json':
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    # Recursively extract strings from JSON
                    def get_strings(obj):
                        if isinstance(obj, str):
                            yield obj
                        elif isinstance(obj, dict):
                            for v in obj.values():
                                yield from get_strings(v)
                        elif isinstance(obj, list):
                            for item in obj:
                                yield from get_strings(item)
                    
                    content = '\n'.join(get_strings(data))
                except Exception as e:
                    print(f"Error parsing JSON {file_path}: {e}")
                    continue

            elif ext == '.docx':
                content = extract_text_from_docx(file_path)
            
            else:
                # Text/CSV/MD
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except UnicodeDecodeError:
                    try:
                        with open(file_path, 'r', encoding='cp1252') as f:
                            content = f.read()
                    except:
                        print(f"Skipping binary/unreadable text file: {file_path}")
                        continue

            file_links = extract_links_with_context(content, file_path)
            
            # Post-processing for CSV/Common errors
            for link in file_links:
                u = link['url']
                # If URL ends with logical delimiters that are likely not part of URL
                # In CSVs, commas are delimiters.
                if ',' in u and ext == '.csv':
                    u = u.split(',')[0]
                
                # Also handle the \n issue if it persisted (should be fixed by JSON parsing, but good to be safe)
                if '\\n' in u: 
                    u = u.split('\\n')[0]
                
                link['url'] = u.strip('.,;:')
                
            all_links.extend(file_links)
        except Exception as e:
            print(f"Failed to process {file_path}: {e}")

    print(f"Found {len(all_links)} links total. Verifying...")

    # 3. Verify links
    results = []
    unique_urls = set(l['url'] for l in all_links)
    url_cache = {}
    
    import concurrent.futures

    # 3. Verify links
    # Let's verify ONLY elastique links
    elastique_urls = {u for u in unique_urls if 'elastiqueathletics.com' in u}
    skipped_urls = unique_urls - elastique_urls
    
    # Mark skipped as skipped
    for u in skipped_urls:
        url_cache[u] = (200, "Skipped (Non-Product Link)")

    print(f"Scanned {len(unique_urls)} total links. Checking {len(elastique_urls)} product links (elastiqueathletics.com)...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_url = {executor.submit(check_link, url): url for url in elastique_urls}
        completed = 0
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                status, message = future.result()
            except Exception as exc:
                status, message = 0, str(exc)
            
            url_cache[url] = (status, message)
            completed += 1
            if completed % 10 == 0:
                print(f"Progress: {completed}/{len(unique_urls)}", end='\r')
    
    print(f"Verification complete. Generating report...")

    # 4. Compile Report
    with open(REPORT_FILE, 'w', encoding='utf-8') as report:
        report.write("# Link Audit Report\n\n")
        report.write(f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        report.write(f"**Files Scanned:** {len(files_to_scan)}\n")
        report.write(f"**Total Links Found:** {len(all_links)}\n")
        report.write(f"**Unique Links:** {len(unique_urls)}\n\n")
        
        broken_links = []
        suspicious_links = [] # non-200 status
        valid_links = []

        for link_info in all_links:
            url = link_info['url']
            status, message = url_cache[url]
            link_info['status'] = status
            link_info['message'] = message
            
            if 'elastiqueathletics.com' not in url:
                continue

            if status >= 400 or status == 0:
                broken_links.append(link_info)
            elif status != 200:
                suspicious_links.append(link_info)
            else:
                valid_links.append(link_info)

        report.write("## 🚨 Broken Product Links (Confirmed 404)\n")
        if not broken_links:
            report.write("No broken links found!\n")
        else:
            for item in broken_links:
                report.write(f"- [ ] **URL**: `{item['url']}`\n")
                report.write(f"  - **Status**: {item['status']} ({item['message']})\n")
                report.write(f"  - **File**: `{os.path.basename(item['file'])}` (Line {item['line']})\n")
                report.write(f"  - **Context**: ...{item['context'].replace(item['url'], '**'+item['url']+'**')}...\n\n")

        report.write("\n## ⚠️ Redirects / Suspicious\n")
        if not suspicious_links:
            report.write("No suspicious links found.\n")
        else:
            for item in suspicious_links:
                report.write(f"- [ ] **URL**: `{item['url']}`\n")
                report.write(f"  - **Status**: {item['status']} ({item['message']})\n")
                report.write(f"  - **File**: `{os.path.basename(item['file'])}` (Line {item['line']})\n")
                report.write(f"  - **Context**: ...{item['context'].replace(item['url'], '**'+item['url']+'**')}...\n\n")

        report.write("\n## ✅ Valid Product Links\n")
        if not valid_links:
            report.write("No valid product links found.\n")
        else:
            # Group by URL to avoid dupes in list
            unique_valid = {}
            for item in valid_links:
                 if item['url'] not in unique_valid:
                     unique_valid[item['url']] = item
            
            for url, item in unique_valid.items():
                report.write(f"- {url} ({item['message']})\n")

    # 5. Generate CSV Report
    csv_file = REPORT_FILE.replace('.md', '.csv')
    print(f"Generating CSV report: {csv_file}")
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Status', 'URL', 'Message', 'File', 'Line', 'Context'])
        
        # Helper to sort: Broken (404/0) -> Suspicious -> Valid
        def sort_key(item):
            s = item['status']
            if s >= 400 or s == 0: return 0 # Broken
            if s != 200: return 1 # Suspicious
            return 2 # Valid
            
        sorted_links = sorted(all_links, key=lambda x: (sort_key(x), x['file'], x['line']))
        
        for item in sorted_links:
            # Re-apply filters
            if 'calendly.com' in item['url']: continue
            if 'elastiqueathletics.com' not in item['url']: continue
            
            context_clean = item['context'].replace('\n', ' ').strip()
            writer.writerow([
                item['status'],
                item['url'],
                item['message'],
                os.path.basename(item['file']),
                item['line'],
                context_clean
            ])

    print(f"Report generated at {os.path.abspath(REPORT_FILE)}")

if __name__ == "__main__":
    main()
