# adk_agents/github_suggest_fix/prompt.py
def generate_prompt(issue):
    """
    Build the prompt text for the suggest_fix_agent.
    """
    prompt = f"""
Issue #{issue['issue_number']} in {issue['owner']}/{issue['repo']}:

Title: {issue['title']}
Body: {issue['body'][:500]}
Labels: {', '.join(issue.get('labels', []))}

Suggest a concise fix or next steps for this issue in JSON format:
{{
    "issue_id": {issue['id']},
    "suggested_fix": "..."
}}
"""
    return prompt
