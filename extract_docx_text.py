import xml.etree.ElementTree as ET
import os

def extract_text_from_docx_xml(xml_path):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        # XML namespaces in Word docs
        namespaces = {
            'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
        }
        
        text_content = []
        for p in root.findall('.//w:p', namespaces):
            texts = [node.text for node in p.findall('.//w:t', namespaces) if node.text]
            if texts:
                text_content.append(''.join(texts))
        
        return '\n'.join(text_content)
    except Exception as e:
        return f"Error reading {xml_path}: {str(e)}"

endorsements_path = r'C:\Homebrew Apps\Elastique - GPT_chatbot\Training Data\Endorsements_Unzipped\word\document.xml'
huberman_path = r'C:\Homebrew Apps\Elastique - GPT_chatbot\Training Data\Huberman_Unzipped\word\document.xml'

print("--- ENDORSEMENTS ---")
print(extract_text_from_docx_xml(endorsements_path))
print("\n--- HUBERMAN ---")
# Huberman might be huge, let's limit output or just print the first 2000 chars to check, 
# but actually I need the whole thing to find science. 
# The tool output might truncate, but I can read it in chunks if needed. 
# For now let's print it all and see if it fits. 
# Wait, Huberman file size is 1.6MB, the text might be very long.
# I'll print the first 5000 characters of Huberman to verify, then I might need to read it differently or just grep it.
# Actually, let's just print it. The system handles large outputs by truncating usually, but I need to read it.
# I'll save the output to a file and then read the file.
full_text = extract_text_from_docx_xml(huberman_path)
print(full_text[:2000] + "\n...[TRUNCATED]...")

with open(r'C:\Homebrew Apps\Elastique - GPT_chatbot\Training Data\huberman_text.txt', 'w', encoding='utf-8') as f:
    f.write(full_text)
