# test_adk_replay.py - Test the ADK replay functionality
import json
import subprocess
import tempfile
import os
from pathlib import Path

def test_adk_replay():
    print("Testing ADK replay functionality...")
    
    # Find the agent directory
    agent_dir = Path(__file__).parent / "adk_agents" / "github_mcp"
    
    if not agent_dir.exists():
        print(f"Agent directory not found at {agent_dir}")
        return
    
    print(f"Using agent directory: {agent_dir}")
    
    # Create a test replay file
    test_queries = [
        "Hello, can you help me?",
        "Extract issues from https://github.com/ultralytics/ultralytics/issues/22188"
    ]
    
    for i, query in enumerate(test_queries):
        print(f"\n=== Test {i+1}: {query} ===")
        
        replay_data = {
            "session_state": {},
            "user_queries": [query]
        }
        
        # Create temporary replay file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(replay_data, f, indent=2)
            replay_file = f.name
        
        print(f"Created replay file: {replay_file}")
        print(f"Replay content: {json.dumps(replay_data, indent=2)}")
        
        try:
            # Run ADK with replay
            result = subprocess.run([
                'adk', 'run', str(agent_dir), '--replay', replay_file
            ], 
            capture_output=True, 
            text=True, 
            timeout=60
            )
            
            print(f"Return code: {result.returncode}")
            print(f"STDOUT:\n{result.stdout}")
            if result.stderr:
                print(f"STDERR:\n{result.stderr}")
                
        except subprocess.TimeoutExpired:
            print("Command timed out")
        except Exception as e:
            print(f"Command failed: {e}")
        finally:
            # Clean up
            try:
                os.unlink(replay_file)
            except:
                pass

def test_adk_web():
    """Test starting the ADK web interface"""
    print("\n=== Testing ADK Web Interface ===")
    
    agent_dir = Path(__file__).parent / "adk_agents" / "github_mcp"
    
    if not agent_dir.exists():
        print(f"Agent directory not found at {agent_dir}")
        return
    
    print(f"Starting ADK web interface for {agent_dir}...")
    print("This will start a web server - you should be able to access it at http://localhost:8000")
    print("Press Ctrl+C to stop the server")
    
    try:
        # Start web server (this will block)
        result = subprocess.run([
            'adk', 'web', str(agent_dir)
        ], timeout=10)  # Short timeout just to test if it starts
        
    except subprocess.TimeoutExpired:
        print("Web server started successfully (timed out as expected)")
    except KeyboardInterrupt:
        print("Web server stopped by user")
    except Exception as e:
        print(f"Failed to start web server: {e}")

if __name__ == "__main__":
    test_adk_replay()
    
    # Uncomment to test web interface
    # test_adk_web()