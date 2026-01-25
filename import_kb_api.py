import requests
import json
import time

# Configuration
LOCATION_ID = "1UDsAfE56YeB8XC5VEV5"
BOT_ID = "TXljH8UswVh2KkV1cekU" # From URL in initial request
KB_ID = "F3njY9CYCtZtva7R2ZSI" # From URL in research phase
COOKIE_STRING = '_ga=GA1.2.1445759167.1763911142; _gid=GA1.2.2129598008.1763911142; g_state={"i_l":0,"i_ll":1763911147555}; a=eyJhcGlLZXkiOiI4NjE1N2UwMC1jYjA4LTRhYTgtYWEwMS01NzEwMWQ4ODdkOTAiLCJ1c2VySWQiOiJhQkpjdkJ0QWx5M0toRlBrWWVhdCIsImNvbXBhbnlJZCI6IkhkczVtMWtaNUJYcmFmejkxNE54In0=; m_a=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJjaGFubmVsIjoiQVBQIiwic291cmNlIjoiV0VCX1VTRVIiLCJzb3VyY2VJZCI6ImFCSmN2QnRBbHkzS2hGUGtZZWF0IiwiYXV0aENsYXNzIjoiVXNlciIsImF1dGhDbGFzc0lkIjoiYUJKY3ZCdEFseTNLaEZQa1llYXQiLCJwcmltYXJ5QXV0aENsYXNzSWQiOiJhQkpjdkJ0QWx5M0toRlBrWWVhdCIsInByaW1hcnlVc2VyIjp7fSwiYXBwTWV0YSI6e30sImp0aSI6IjY5MjMyNjA5OGM4MTVkM2FjNGUyZGJhNSIsImlhdCI6MTc2MzkxMTE3Ny44ODEsImV4cCI6MTc2MzkxNDc3Ny44ODF9.c8SNDWT4AJCD8n04904HJckdn5NUCUpwkd9DsDgyQtQbWljhF4GobIXsy2KfBDF_Zok4BmDX3JMrE4ZdbMrbJPdZEa9YM52OLl_ASIMAWh_4Tcm4HaYP7Nr93EX_rWxF69I6E5jt98o836frj2XiCUe2RCFDtR3m1zLK8WRllEb1FuK51o5xPeF50UQsdj3JMzi_fQOY1p0CdmVI53Gsy4SYglpFnLFrylQTEzgbJXl4gS5X-IgvAOQO5E0GtGCBLnKp-SZeta4iQc1qQtr8WT1MRHcuvI5vxhjs2bXyfr-JSs2f1oSjbxMZInLrTcpZWSQDlO5WwiPHQdbAc0-7P0FFTF-uvSXauJgjmg8wqliq1S8HtDn5qzzBTTPi5DXXgY9cr6vO9OMVSNGNryO-uQzIXQqQ2vVPME5YvRpKIdOSBZOz3HvUQAIweqZMTqB99JLz0-cFamb835VqKfSR0vL73kjQh4tbgx8d_YQB29SZTtjZrA64rWKxirejTp8hV7KZucejv6e38dIVZPAoUIhq0MHuVfoH88M_8ina78VVPl3lZO5MyCzkbGBBHk5UnqxVHj_KJsVEt0NxzjxiKRKJQ-VRz1G_ahBCRtotHz3gERnx-UHgI0XDqpjOThApAsAal9gX_unmfRG3dQkRcRzftA5ivC-N2bHfnr15ryU; _ga_MX6Z1X7L8K=GS2.2.s1763911141$o1$g1$t1763913040$j23$l0$h0'

# Extract the JWT token from the cookie (m_a value)
TOKEN = None
for cookie in COOKIE_STRING.split('; '):
    if cookie.startswith('m_a='):
        TOKEN = cookie.split('m_a=')[1]
        break

if not TOKEN:
    print("Error: Could not extract m_a token from cookies")
    exit(1)

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "version": "2021-07-28", # Common GHL version header
    "source": "WEB_USER"
}

# API Endpoint (Reverse engineered guess based on UI)
# Usually: https://services.leadconnectorhq.com/conversation-ai/knowledge-base/{kb_id}/faq
API_URL = f"https://services.leadconnectorhq.com/conversation-ai/knowledge-base/{KB_ID}/faq"

def import_faqs():
    with open('ghl_knowledge_base_text.json', 'r') as f:
        faqs = json.load(f)
    
    print(f"Loaded {len(faqs)} FAQs to import.")
    
    success_count = 0
    fail_count = 0
    
    for i, faq in enumerate(faqs):
        payload = {
            "question": faq['question'],
            "answer": faq['answer'],
            "locationId": LOCATION_ID
        }
        
        try:
            response = requests.post(API_URL, headers=HEADERS, json=payload)
            
            if response.status_code in [200, 201]:
                print(f"[{i+1}/{len(faqs)}] Successfully imported: {faq['question']}")
                success_count += 1
            else:
                print(f"[{i+1}/{len(faqs)}] Failed to import: {faq['question']}")
                print(f"Status: {response.status_code}, Response: {response.text}")
                fail_count += 1
                
        except Exception as e:
            print(f"Error importing {faq['question']}: {str(e)}")
            fail_count += 1
            
        # Rate limiting pause
        time.sleep(1)
        
    print(f"\nImport Complete. Success: {success_count}, Failed: {fail_count}")

if __name__ == "__main__":
    import_faqs()
