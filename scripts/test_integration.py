# test_integration.py - Test the ADK integration
import sys
import os
sys.path.append('/home/yara/Desktop/ADK/adkmcp/adk-mcp-tutorial')

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'github_issues_project.settings')
import django
django.setup()

from issues.services.adk_integration import get_issues_from_url

def test_integration():
    print("Testing ADK integration...")
    
    # Test URL
    test_url = "https://github.com/ultralytics/ultralytics/issues/22188"
    
    print(f"Testing with URL: {test_url}")
    
    try:
        issues = get_issues_from_url(test_url)
        
        print(f"Received {len(issues)} issues")
        
        for i, issue in enumerate(issues):
            print(f"\nIssue {i+1}:")
            for key, value in issue.items():
                if isinstance(value, str) and len(value) > 100:
                    print(f"  {key}: {value[:100]}...")
                else:
                    print(f"  {key}: {value}")
    
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_integration()