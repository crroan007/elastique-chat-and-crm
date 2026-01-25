from fpdf import FPDF
import os

def create_pdf(text_file, pdf_file):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    with open(text_file, "r", encoding="utf-8") as f:
        for line in f:
            # Handle basic markdown-like headers
            if line.startswith("### "):
                pdf.set_font("Arial", 'B', size=14)
                pdf.cell(200, 10, txt=line.replace("### ", "").strip(), ln=1, align='L')
                pdf.set_font("Arial", size=12)
            elif line.startswith("**Question:**"):
                pdf.set_font("Arial", 'B', size=12)
                pdf.multi_cell(0, 10, txt=line.strip())
                pdf.set_font("Arial", size=12)
            else:
                # Replace unsupported characters if any
                clean_line = line.encode('latin-1', 'replace').decode('latin-1')
                pdf.multi_cell(0, 6, txt=clean_line)

    pdf.output(pdf_file)
    print(f"PDF created: {pdf_file}")

if __name__ == "__main__":
    text_path = r"c:\Homebrew Apps\Elastique - GPT_chatbot\lymphatic_consultant_manual.txt"
    pdf_path = r"c:\Homebrew Apps\Elastique - GPT_chatbot\lymphatic_consultant_manual.pdf"
    create_pdf(text_path, pdf_path)
