# issues/services/adk_integration.py
import json
import re
import subprocess
import tempfile
import os
from pathlib import Path


def get_issues_from_url(url: str):
    """
    Extract GitHub issues from a URL using ADK CLI replay.
    """
    prompt_text = f"Extract issues from {url}"

    # Locate the agent directory
    agent_dir = Path(__file__).parent.parent.parent / "adk_agents" / "github_mcp"

    # Create replay JSON file
    replay_data = {"state": {}, "queries": [prompt_text]}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(replay_data, f, indent=2)
        replay_file = f.name

    try:
        # Run ADK CLI with replay
        result = subprocess.run(
            ["adk", "run", str(agent_dir), "--replay", replay_file],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(agent_dir.parent),
        )

        if result.returncode == 0:
            return parse_adk_output(result.stdout, url)
        return []

    finally:
        try:
            os.unlink(replay_file)
        except OSError:
            pass


def parse_adk_output(output: str, url: str):
    """
    Parse JSON issue objects from ADK CLI output.
    """
    json_patterns = [
        r"(\{[^{}]*\"repo\"[^{}]*\})",            # Single issue object
        r"(\[[^\[\]]*\{[^{}]*\"repo\"[^{}]*\}[^\[\]]*\])",  # Array of issues
        r"```json\s*(\{.*?\})\s*```",             # JSON in markdown block
        r"```json\s*(\[.*?\])\s*```",             # JSON array in markdown block
    ]

    for pattern in json_patterns:
        matches = re.findall(pattern, output, re.DOTALL)
        for match in matches:
            try:
                issues = json.loads(match)
                if isinstance(issues, dict):
                    issues = [issues]

                valid_issues = []
                for issue in issues:
                    if isinstance(issue, dict):
                        issue = fill_missing_fields(issue, url)
                        if all(k in issue for k in ["repo", "owner", "issue_number", "title"]):
                            valid_issues.append(issue)

                if valid_issues:
                    return valid_issues

            except json.JSONDecodeError:
                continue

    return []


def fill_missing_fields(issue: dict, url: str):
    """
    Fill in missing fields from the GitHub issue URL.
    """
    github_match = re.match(r"https://github\.com/([^/]+)/([^/]+)", url)
    if github_match:
        issue.setdefault("owner", github_match.group(1))
        issue.setdefault("repo", github_match.group(2))

    issue_match = re.search(r"/issues/(\d+)", url)
    if issue_match:
        issue.setdefault("issue_number", int(issue_match.group(1)))

    issue.setdefault("title", f"Issue from {url}")
    issue.setdefault("body", "")
    issue.setdefault("labels", [])
    issue.setdefault("type", "issue")

    return issue
