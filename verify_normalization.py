import sys
import os
import json
from unittest.mock import MagicMock

# Mock dependencies
sys.modules["streamlit"] = MagicMock()
sys.modules["langchain_google_genai"] = MagicMock()
sys.modules["langchain_core.messages"] = MagicMock()
sys.modules["langchain_core.output_parsers"] = MagicMock()
sys.modules["langchain_core.prompts"] = MagicMock()
sys.modules["nest_asyncio"] = MagicMock()
sys.modules["dotenv"] = MagicMock()
sys.modules["pydantic"] = MagicMock()
sys.modules["pydantic"].BaseModel = MagicMock
sys.modules["playwright"] = MagicMock()
sys.modules["playwright.async_api"] = MagicMock()
sys.modules["playwright_stealth"] = MagicMock()



# Add current directory to path to import main
sys.path.append(os.getcwd())

from main import normalize_step

def verify():
    try:
        with open("files/operations2.json", "r") as f:
            data = json.load(f)
        
        print("Original Data Loaded.")
        
        for i, step in enumerate(data):
            normalized = normalize_step(step)
            print(f"Step {i+1}:")
            print(f"  Type: {normalized['action_type']}")
            print(f"  Description: {normalized['description']}")
            print("-" * 20)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    verify()
