import zipfile
import os

def create_zip():
    zip_filename = "lymphatic_bot_materials.zip"
    
    # List of specific files to include from the root
    files_to_include = [
        "01_Science_and_Behavior.docx", "01_Science_and_Behavior.md",
        "02_Product_Catalog.docx", "02_Product_Catalog.md",
        "03_Consultation_and_Logistics.docx", "03_Consultation_and_Logistics.md",
        "04_Research_Library.docx", "04_Research_Library.md",
        "05_Protocol_Templates.docx", "05_Protocol_Templates.md",
        "06_Provider_Directory_Structure.docx", "06_Provider_Directory_Structure.md",
        "07_Master_Research_Table.docx", "07_Master_Research_Table.md",
        "08_Master_Knowledge_Cards.md",
        "09_Rich_Text_Snippets.md",
        "10_Master_Protocol_Library.docx", "10_Master_Protocol_Library.md",
        "lymphatic_consultant_manual.txt",
        "lymphatic_knowledge_base.pdf", "lymphatic_knowledge_base.txt",
        "master_training_materials.md",
        "scientific_library.json",
        "📘 ELASTIQUE PRACTITIONER TRAINING MANUAL- draft.pdf",
        ".env",
        "PRODUCT_NAVIGATION_GUIDE.docx", "PRODUCT_NAVIGATION_GUIDE.md",
        "PRODUCT_URL_REFERENCE.docx", "PRODUCT_URL_REFERENCE.md",
        "LINK_AUDIT_REPORT.csv", "LINK_AUDIT_REPORT.md",
        "elastique_products.json",
        "valid_products.json",
        "comprehensive_product_catalog.md",
        "consolidated_products.txt",
        "ghl_product_tiles.json",
        "ghl_knowledge_base.json", "ghl_knowledge_base_text.json",
        "CATALOG_PARSER.md",
        "CATEGORIZED_PRODUCT_MAP.md",
        "exhaustive_faq.docx", "exhaustive_faq.md", "exhaustive_faq_v2.docx",
        "faq.docx",
        "Master_Research_Citations.csv",
        "PRODUCT_CATALOG.csv",
        "system_prompt.txt", "system_prompt_exhaustive.txt",
        "consultant_persona.txt",
        "bot_goals_prompt.txt", "goal_prompt.txt", "personality_prompt.txt",
        "RETRAINING_GUIDE.md", "RETRAINING_INSTRUCTIONS.md"
    ]

    print(f"Creating {zip_filename}...")
    
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Add root files
        for filename in files_to_include:
            if os.path.exists(filename):
                print(f"Adding: {filename}")
                zipf.write(filename)
            else:
                print(f"Skipping (not found): {filename}")

        # Add Training Data directory
        training_data_dir = "Training Data"
        if os.path.exists(training_data_dir):
            for root, dirs, files in os.walk(training_data_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    print(f"Adding: {file_path}")
                    zipf.write(file_path)
        else:
             print(f"Warning: {training_data_dir} directory not found.")
             
    print(f"\nZip creation complete: {os.path.abspath(zip_filename)}")

if __name__ == "__main__":
    create_zip()
