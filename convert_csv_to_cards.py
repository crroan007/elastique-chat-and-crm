import csv

def convert_csv_to_cards(csv_file, output_file):
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        with open(output_file, 'w', encoding='utf-8') as out:
            out.write("# Master Research Knowledge Cards\n\n")
            out.write("Use these cards to answer user questions based on their specific concerns.\n\n")
            
            for row in reader:
                # Skip empty rows
                if not row['User_Concern']:
                    continue
                    
                out.write(f"## Knowledge Card: {row['User_Concern']}\n\n")
                out.write(f"**Trigger Keywords:** {row['Trigger_Keywords']}\n\n")
                
                out.write("**Scientific Truth:**\n")
                out.write(f"{row['Scientific_Finding']}\n\n")
                
                out.write("**Bot Script (Citation):**\n")
                out.write(f"{row['Citation_Text']}\n\n")
                
                out.write("**Source:**\n")
                out.write(f"[{row['Study_Title']}]({row['Study_URL']})\n\n")
                
                out.write("**Follow-Up Questions:**\n")
                out.write(f"1. {row['Driver_Question_1']}\n")
                out.write(f"2. {row['Driver_Question_2']}\n\n")
                
                out.write("**Protocol Addition:**\n")
                out.write(f"{row['Protocol_Addition']}\n\n")
                
                out.write("---\n\n")

if __name__ == "__main__":
    convert_csv_to_cards('Master_Research_Citations.csv', '08_Master_Knowledge_Cards.md')
    print("Successfully created 08_Master_Knowledge_Cards.md")
