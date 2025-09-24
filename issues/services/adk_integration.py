# issues/services/adk_integration.py (Replay-Based Version)
import json
import logging
import subprocess
import tempfile
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)

def get_issues_from_url(url, start_date=None, end_date=None):
    """
    Extract GitHub issues from a URL using ADK CLI replay functionality.
    """
    try:
        # Build the prompt
        prompt_text = f"Extract issues from {url}"
        if start_date and end_date:
            prompt_text += f" between {start_date} and {end_date}"
        
        logger.info(f"Calling ADK CLI with replay for prompt: {prompt_text}")
        
        # Find the agent directory (not the file)
        agent_dir = Path(__file__).parent.parent.parent / "adk_agents" / "github_mcp"
        
        # Create a replay JSON file
        replay_data = {
            "state": {},
            "queries": [prompt_text]
        }
        
        # Try ADK run with replay
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(replay_data, f, indent=2)
                replay_file = f.name
            
            logger.info(f"Created replay file: {replay_file}")
            logger.info(f"Replay content: {json.dumps(replay_data, indent=2)}")
            
            try:
                # Run ADK with replay
                result = subprocess.run([
                    'adk', 'run', str(agent_dir), '--replay', replay_file
                ], 
                capture_output=True, 
                text=True, 
                timeout=120,  # 2 minute timeout
                cwd=str(agent_dir.parent)
                )
                
                logger.info(f"ADK CLI return code: {result.returncode}")
                logger.info(f"ADK CLI stdout: {result.stdout}")
                if result.stderr:
                    logger.info(f"ADK CLI stderr: {result.stderr}")
                
                if result.returncode == 0:
                    # Parse the output
                    issues = parse_adk_output(result.stdout, url)
                    if issues:
                        return issues
                else:
                    logger.error(f"ADK CLI failed with return code {result.returncode}")
                    
            finally:
                # Clean up temp file
                try:
                    os.unlink(replay_file)
                except:
                    pass
                    
        except subprocess.TimeoutExpired:
            logger.error("ADK CLI replay timed out")
        except Exception as e:
            logger.error(f"ADK CLI replay failed: {e}")
        
       
        
    except Exception as e:
        logger.error(f"Error in replay integration: {str(e)}", exc_info=True)
        return [{
            'error': 'Replay integration failed',
            'error_message': str(e),
            'url': url
        }]



def parse_adk_output(output, url):
    """Parse the output from ADK CLI"""
    try:
        logger.info(f"Parsing ADK output: {output[:500]}...")
        
        # Look for JSON in the output
        import re
        
        # Try to find JSON content - look for our expected structure
        json_patterns = [
            r'(\{[^{}]*"repo"[^{}]*\})',  # Single issue object
            r'(\[[^\[\]]*\{[^{}]*"repo"[^{}]*\}[^\[\]]*\])',  # Array of issues
            r'```json\s*(\{.*?\})\s*```',  # JSON in markdown code block
            r'```json\s*(\[.*?\])\s*```',  # JSON array in markdown code block
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, output, re.DOTALL)
            for match in matches:
                try:
                    logger.info(f"Trying to parse JSON: {match[:200]}...")
                    issues = json.loads(match)
                    
                    # Ensure it's a list
                    if isinstance(issues, dict):
                        issues = [issues]
                    
                    # Validate and fill missing fields
                    valid_issues = []
                    for issue in issues:
                        if isinstance(issue, dict):
                            issue = fill_missing_fields(issue, url)
                            if all(key in issue for key in ['repo', 'owner', 'issue_number', 'title']):
                                valid_issues.append(issue)
                    
                    if valid_issues:
                        logger.info(f"Successfully parsed {len(valid_issues)} issues from ADK output")
                        return valid_issues
                        
                except json.JSONDecodeError:
                    continue
        
        logger.warning("No valid JSON found in ADK output")
        return None
        
    except Exception as e:
        logger.error(f"Error parsing ADK output: {e}")
        return None

def parse_web_response(response, url):
    """Parse response from ADK web API"""
    try:
        # This is speculative - depends on the actual web API format
        if 'message' in response:
            return parse_adk_output(response['message'], url)
        elif 'response' in response:
            return parse_adk_output(response['response'], url)
        elif 'content' in response:
            return parse_adk_output(response['content'], url)
        else:
            logger.warning(f"Unknown web API response format: {response}")
            return None
    except Exception as e:
        logger.error(f"Error parsing web response: {e}")
        return None

def fill_missing_fields(issue, url):
    """Fill in missing fields from URL and provide defaults"""
    import re
    
    # Extract owner/repo from URL
    github_match = re.match(r'https://github\.com/([^/]+)/([^/]+)', url)
    if github_match:
        if 'owner' not in issue or not issue['owner']:
            issue['owner'] = github_match.group(1)
        if 'repo' not in issue or not issue['repo']:
            issue['repo'] = github_match.group(2)
    
    # Extract issue number from URL if it's an issue URL
    issue_match = re.search(r'/issues/(\d+)', url)
    if issue_match and ('issue_number' not in issue or not issue['issue_number']):
        issue['issue_number'] = int(issue_match.group(1))
    
    # Set defaults for missing fields
    if 'title' not in issue or not issue['title']:
        issue['title'] = f"Issue from {url}"
    if 'body' not in issue:
        issue['body'] = ""
    if 'labels' not in issue:
        issue['labels'] = []
    if 'type' not in issue:
        issue['type'] = "issue"
    
    return issue

