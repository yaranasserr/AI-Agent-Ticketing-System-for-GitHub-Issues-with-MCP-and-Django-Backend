# issues/services/suggest_fix_integration.py
import json
import logging
import subprocess
import tempfile
import os
from pathlib import Path
from issues.models import Ticket

logger = logging.getLogger(__name__)

def get_suggested_fix_for_issue(ticket_id: int):
    ticket = Ticket.objects.get(id=ticket_id)

    # Construct GitHub issue URL dynamically
    issue_url = f"https://github.com/{ticket.owner}/{ticket.repo}/issues/{ticket.issue_number}"

    prompt_text = f"""
GitHub issue URL: {issue_url}
Issue title: {ticket.title}
Issue body: {ticket.body}
Labels: {ticket.labels}
Repo: {ticket.repo}

Suggest a concise fix and which files to modify. Return ONLY a JSON object with:
- issue_id
- suggested_fix
- files_to_fix (list of file paths)
"""

    try:
        # Find the agent folder
        agent_dir = Path(__file__).parent.parent.parent / "adk_agents" / "github_suggest_fix"
        if not agent_dir.exists():
            logger.error(f"Agent directory not found at {agent_dir}")
            return get_mock_suggested_fix(ticket)

        # Create replay JSON file
        replay_data = {
            "state": {},
            "queries": [prompt_text]
        }
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(replay_data, f, indent=2)
            replay_file = f.name

        # Run ADK CLI in replay mode
        result = subprocess.run([
            'adk', 'run', str(agent_dir), '--replay', replay_file
        ],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(agent_dir.parent)
        )

        # Cleanup temp file
        try:
            os.unlink(replay_file)
        except:
            pass

        if result.returncode == 0:
            suggested_fix = parse_adk_output(result.stdout, ticket)
            if suggested_fix:
                return suggested_fix
        logger.error(f"ADK CLI failed or no valid output. stdout: {result.stdout}, stderr: {result.stderr}")

    except subprocess.TimeoutExpired:
        logger.error("ADK CLI replay timed out")
    except Exception as e:
        logger.error(f"ADK CLI execution failed: {e}")

    # fallback
    return get_mock_suggested_fix(ticket)


def parse_adk_output(output, ticket):
    """
    Parse JSON output from ADK CLI for suggested fix
    """
    import re
    try:
        # Try to extract JSON from stdout
        matches = re.findall(r'(\{.*"suggested_fix".*\})', output, re.DOTALL)
        for match in matches:
            try:
                data = json.loads(match)
                if "suggested_fix" in data:
                    # Ensure issue_id and files_to_fix exist
                    data.setdefault("issue_id", ticket.issue_number)
                    data.setdefault("files_to_fix", [])
                    return data
            except json.JSONDecodeError:
                continue
        return None
    except Exception as e:
        logger.error(f"Error parsing ADK output: {e}")
        return None


