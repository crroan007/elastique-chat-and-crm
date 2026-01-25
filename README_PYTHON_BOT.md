# Custom Python Chatbot (Elastique Migration)

This is the standalone, off-GHL version of the Elastique Chatbot, powered by **Gemini 2.5 Pro**.

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10 or higher.
- A Google Gemini API Key.

### 2. Installation
Install the required dependencies:
```powershell
pip install -r requirements.txt
```

### 3. Configuration
1.  Look for the `.env` file in this directory.
2.  Ensure it contains your API Key:
    ```
    GEMINI_API_KEY=AIzaSy...
    ```

### 4. Running the Bot
Start the backend server:
```powershell
python server.py
```
*You should see "Uvicorn running on http://0.0.0.0:8000"*

### 5. Using the Chat
Open the `widget.html` file in your browser:
- **File:** `c:\Homebrew Apps\Elastique - GPT_chatbot\widget.html`
- Click the purple bubble to chat!

## 🧪 Testing & Verification
You can run the automated verification suite (bypasses browser) to test logic:
```powershell
python verification_suite.py
```

## 📂 Project Structure
- `server.py`: The Brain (FastAPI + Gemini + RAG).
- `widget.html`: The Frontend (HTML/JS/CSS).
- `elastique_products.json`: The Product Catalog (Source of Truth).
- `goal_prompt_fallback.txt`: The System Personality ("Sarah").
