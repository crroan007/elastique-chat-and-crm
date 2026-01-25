import os

# Hardcoded path based on discovery
SITE_PACKAGES = r"C:\Users\Kado\AppData\Roaming\Python\Python310\site-packages"
TARGET_FILE = os.path.join(SITE_PACKAGES, "basicsr", "data", "degradations.py")

def patch():
    print(f"Patching {TARGET_FILE}...")
    if not os.path.exists(TARGET_FILE):
        print("ERROR: File not found!")
        # Try to find it dynamically if hardcode fails (though we know it exists)
        return

    try:
        with open(TARGET_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # The fix: functional_tensor is gone, use functional
        old_import = "from torchvision.transforms.functional_tensor import rgb_to_grayscale"
        new_import = "from torchvision.transforms.functional import rgb_to_grayscale"
        
        if old_import in content:
            new_content = content.replace(old_import, new_import)
            with open(TARGET_FILE, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print("SUCCESS: File patched!")
        else:
            print("WARNING: Target string not found. Already patched?")
            
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    patch()
