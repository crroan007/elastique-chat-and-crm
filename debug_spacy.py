import spacy

try:
    nlp = spacy.load("en_core_web_sm")
    print("Model Loaded.")
except Exception as e:
    print(f"Load Error: {e}")
    exit()

test_cases = [
    "You can call me Jim",
    "I am Jim",
    "My name is Bob",
    "Jim Johnson",
    "Hi it is Jim",
    "I am Sarah"
]

for text in test_cases:
    doc = nlp(text)
    ents = [(ent.text, ent.label_) for ent in doc.ents]
    print(f"Text: '{text}' | Entities: {ents}")
