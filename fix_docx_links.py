import os
import zipfile
import shutil
import tempfile

REPLACEMENTS = {
    'products/iconic-3-4-sleeve-top': 'products/iconic-top',
    'collections/loriginal-collection': 'collections/loriginal',
    'calendly.com/sarah-lymphatic': '#',
    'bodyflow.com/schedule': '#'
}

ROOT_DIRS = ['.', 'Training Data']

def fix_docx_links():
    count = 0
    for root_dir in ROOT_DIRS:
        if root_dir == '.':
             for item in os.listdir('.'):
                if os.path.isfile(item) and item.lower().endswith('.docx'):
                     if process_docx(item): count += 1
        else:
             if os.path.exists(root_dir):
                for root, dirs, files in os.walk(root_dir):
                    for file in files:
                        if file.lower().endswith('.docx'):
                            filepath = os.path.join(root, file)
                            if process_docx(filepath): count += 1
    
    print(f"Fixed links in {count} .docx files.")

def process_docx(filepath):
    try:
        temp_dir = tempfile.mkdtemp()
        temp_docx_path = os.path.join(temp_dir, os.path.basename(filepath))
        
        modified = False
        
        with zipfile.ZipFile(filepath, 'r') as zin, zipfile.ZipFile(temp_docx_path, 'w') as zout:
            for item in zin.infolist():
                content = zin.read(item.filename)
                
                if item.filename == 'word/document.xml':
                    text = content.decode('utf-8')
                    old_text = text
                    
                    for target, replacement in REPLACEMENTS.items():
                        if target in text:
                            text = text.replace(target, replacement)
                            modified = True
                            print(f"Fixed '{target}' in {filepath}")
                    
                    if modified:
                        zout.writestr(item, text.encode('utf-8'))
                    else:
                        zout.writestr(item, content)
                else:
                    zout.writestr(item, content)
        
        if modified:
            # Replace original with new
            shutil.move(temp_docx_path, filepath)
            shutil.rmtree(temp_dir)
            return True
        else:
            shutil.rmtree(temp_dir)
            return False

    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False

if __name__ == "__main__":
    fix_docx_links()
