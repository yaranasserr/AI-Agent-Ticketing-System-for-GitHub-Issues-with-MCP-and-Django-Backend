import os
from pathlib import Path
from dotenv import load_dotenv
from google.adk.agents.llm_agent import Agent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters

# Load environment variables
env_path = Path(__file__).parent / ".env"
if not env_path.exists():
    env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

GITHUB_PAT = os.getenv("GITHUB_PAT")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GITHUB_PAT:
    raise ValueError("GITHUB_PAT is not set in .env")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY is not set in .env")

# Initialize GitHub MCP tool
github_tool = MCPToolset(
    connection_params=StdioServerParameters(
        command="docker",
        args=[
            "run", "-i", "--rm",
            "-e", f"GITHUB_PERSONAL_ACCESS_TOKEN={GITHUB_PAT}",
            "ghcr.io/github/github-mcp-server"
        ]
    )
)

# Keep only safe functions
safe_function_names = {'list_issues', 'get_issue', 'get_issue_comments', 'search_issues'}
github_tool.function_declarations = [
    f for f in getattr(github_tool, 'function_declarations', [])
    if getattr(f, 'name', None) in safe_function_names
]

# Create agent with filtered tools
agent = Agent(
    model="gemini-2.0-flash",
    name="github_issues_agent", 
    instruction="""
You are a GitHub Issues Extractor with access to filtered GitHub MCP tools.

Given a GitHub URL (issue or repo), fetch issue info or list recent issues.
Return ONLY JSON with:
- repo
- owner
- issue_number
- title
- body (first 200 characters)
- labels
- type

Use only the safe MCP tools available to you.
""",
    tools=[github_tool] if github_tool.function_declarations else []
)
