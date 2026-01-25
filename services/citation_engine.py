import re
from typing import List, Dict, Optional
import json

class CitationEngine:
    """
    Manages the retrieval and formatting of scientific citations.
    Enforces the "Friendly Link" protocol: [Colloquial Intro] + [Friendly Name](URL).
    """

    def __init__(self, db_connection_string: str = None):
        # In a real deployment, this connects to Supabase/PostgreSQL
        # For this file-system version, we will mock the library with the JSON data
        self.library: List[Dict] = [] 
        # TODO: Load from d:/Homebrew Apps/Elastique - Chatbot_Text/scientific_library.json initially

    def load_local_library(self, json_path: str):
        """Loads a local JSON file into memory for the engine to use."""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                self.library = json.load(f)
            print(f"Loaded {len(self.library)} scientific facts.")
        except Exception as e:
            print(f"Error loading library: {e}")

    def find_relevant_citation(self, query: str, threshold: float = 0.5) -> Optional[Dict]:
        """
        Searches the library for a fact relevant to the query.
        (Currently supports keyword matching; v2 will be Vector Semantic Search).
        """
        # Simple Keyword Score (Temporary until PGVector)
        query_words = set(query.lower().split())
        best_match = None
        best_score = 0

        for item in self.library:
            score = 0
            # Search mechanism, category, and facts
            text_corpus = f"{item.get('category', '')} {item.get('mechanism', '')}"
            for fact in item.get('facts', []):
                fact_text = f"{fact.get('statement', '')} {fact.get('citation', '')}"
                
                # Intersection count
                matches = sum(1 for word in query_words if word in fact_text.lower())
                if matches > best_score:
                    best_score = matches
                    best_match = fact
            
            if matches > best_score:
                best_score = matches
                # We return the specific fact, not the whole item
                # This logic inside the loop needs to capture the specific fact
                pass

        # Re-implemented for clarity
        ranking = []
        for item in self.library:
            for fact in item.get('facts', []):
                # Check for validity (must have URL to be used)
                if not fact.get('url'):
                    continue

                corpus = (fact['statement'] + " " + fact['citation'] + " " + item.get('category', '')).lower()
                score = sum(1 for word in query_words if word in corpus)
                if score > 0:
                    ranking.append({'fact': fact, 'score': score})
        
        ranking.sort(key=lambda x: x['score'], reverse=True)
        
        if ranking and ranking[0]['score'] >= 1: # Low threshold for now
            return ranking[0]['fact']
        
        return None

    def format_citation(self, fact: Dict) -> str:
        """
        Takes a raw fact dict and returns a Colloquial Friendly Line.
        Example Output: "Interestingly, a study by Ohio State University found that compression reduces vibration..."
        """
        citation_name = fact.get('citation', 'a clinical study')
        url = fact.get('url', '#')
        statement = fact.get('statement', '')

        # Colloquial Templates
        # format: "Interestingly, [Friendly Link] [Statement Fragment]."
        
        # We clean the statement to integrate flow if needed
        statement = statement.rstrip('.')

        friendly_link = f"[{citation_name}]({url})"
        
        return f"Interestingly, **{friendly_link}** shows that {statement.lower()}."

    def inject_citation_into_response(self, text_response: str, query: str) -> str:
        """
        The main public method. Takes a generated response, tries to find a backing citation,
        and appends/injects it if relevant.
        """
        fact = self.find_relevant_citation(query)
        if fact:
            citation_text = self.format_citation(fact)
            return f"{text_response}\n\n(Source: {citation_text})"
        return text_response
