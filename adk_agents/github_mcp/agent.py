import os
import json
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

def deep_filter_problematic_functions(toolset):
    """
    Aggressively filter out function declarations that contain additional_properties
    or any other problematic fields that cause Google API validation errors.
    """
    if not hasattr(toolset, 'function_declarations') or not toolset.function_declarations:
        print("No function declarations to filter")
        return 0
    
    original_count = len(toolset.function_declarations)
    safe_functions = []
    problematic_functions = []
    
    # List of known safe issue-related functions
    safe_function_names = {
        'list_issues',
        'get_issue', 
        'get_issue_comments',
        'search_issues'
    }
    
    for func in toolset.function_declarations:
        func_name = getattr(func, 'name', 'unknown')
        
        try:
            # Convert function to string to check for problematic content
            func_str = str(func)
            func_repr = repr(func)
            
            # Check for problematic patterns
            has_additional_properties = (
                'additional_properties' in func_str.lower() or
                'additional_properties' in func_repr.lower()
            )
            
            # Check if function has problematic parameters by trying to serialize
            has_problematic_params = False
            if hasattr(func, 'parameters'):
                try:
                    # Try to convert parameters to dict/json to detect issues
                    params_str = str(func.parameters)
                    if 'additional_properties' in params_str.lower():
                        has_problematic_params = True
                except Exception:
                    has_problematic_params = True
            
            # Only keep functions that are:
            # 1. In our safe list AND
            # 2. Don't contain additional_properties AND  
            # 3. Don't have problematic parameters
            if (func_name in safe_function_names and 
                not has_additional_properties and 
                not has_problematic_params):
                
                safe_functions.append(func)
                print(f"✅ Keeping safe function: {func_name}")
            else:
                problematic_functions.append(func_name)
                reason = []
                if func_name not in safe_function_names:
                    reason.append("not in safe list")
                if has_additional_properties:
                    reason.append("has additional_properties")
                if has_problematic_params:
                    reason.append("problematic parameters")
                
                print(f"❌ Filtering out: {func_name} ({', '.join(reason)})")
                
        except Exception as e:
            problematic_functions.append(func_name)
            print(f"⚠️  Error processing {func_name}: {e}")
    
    # Update toolset with only safe functions
    toolset.function_declarations = safe_functions
    
    print(f"\nFiltering Summary:")
    print(f"Original functions: {original_count}")
    print(f"Safe functions kept: {len(safe_functions)}")
    print(f"Problematic functions removed: {len(problematic_functions)}")
    
    if problematic_functions:
        print(f"Removed functions: {problematic_functions}")
    
    return len(safe_functions)

# Initialize GitHub MCP tool
print("Initializing GitHub MCP toolset...")
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


print("Applying deep filtering to remove problematic functions...")
remaining_tools = deep_filter_problematic_functions(github_tool)



# Create agent with filtered tools
agent = Agent(
    model="gemini-2.0-flash",
    name="github_issues_agent", 
    instruction="""
You are a GitHub Issues Extractor with access to filtered GitHub MCP tools.

When given a GitHub URL like https://github.com/owner/repo/issues/123:
1. Parse the URL to extract owner, repo, and issue_number
2. Use get_issue(owner="owner", repo="repo", issue_number=123) to fetch the issue
3. Return ONLY these fields in clean JSON format:
   - repo
   - owner
   - issue_number
   - title  
   - body (first 200 characters)
   - labels
   - type

For repository URLs, use list_issues(owner="owner", repo="repo") to get recent issues.
Use only the safe MCP tools available to you.
""",
    tools=[github_tool] if remaining_tools > 0 else []
)

