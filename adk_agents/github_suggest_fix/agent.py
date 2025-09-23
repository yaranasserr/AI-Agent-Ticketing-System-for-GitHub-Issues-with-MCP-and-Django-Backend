from google.adk.agents.llm_agent import Agent
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent / ".env"
if not env_path.exists():
    env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY is not set in .env")

agent = Agent(
    model="gemini-2.0-flash",
    name="github_suggest_fix_agent",
    instruction="""
You are a GitHub Issue Fix Suggestor.
When given a GitHub issue dict with title, body, labels, repo, and owner:
1. Suggest a concise fix.
2. Indicate the **files that likely need to be modified** to resolve the issue.
3. Return ONLY a JSON object with:
   - issue_id
   - suggested_fix
   - files_to_fix  (list of relative file paths in the repo)
Do not include any explanations outside the JSON.
"""
)
