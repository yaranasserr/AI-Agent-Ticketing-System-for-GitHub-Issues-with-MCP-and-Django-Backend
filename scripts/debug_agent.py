# debug_agent.py - Run this script to debug the agent
import sys
import os
sys.path.append('/home/yara/Desktop/ADK/adkmcp/adk-mcp-tutorial')

from adk_agents.github_mcp.agent import agent

def debug_agent():
    print(f"Agent type: {type(agent)}")
    print(f"Agent class: {agent.__class__}")
    
    # List all methods and attributes
    methods = [attr for attr in dir(agent) if not attr.startswith('_')]
    print(f"\nAvailable methods and attributes:")
    for method in methods:
        attr = getattr(agent, method)
        if callable(attr):
            print(f"  {method}() - callable")
        else:
            print(f"  {method} - {type(attr)}")
    
    # Check for common agent execution methods
    execution_methods = ['run', 'execute', 'invoke', 'call', 'run_live', 'run_async']
    print(f"\nChecking for execution methods:")
    for method in execution_methods:
        if hasattr(agent, method):
            attr = getattr(agent, method)
            print(f"  ✓ {method}: {type(attr)} - {callable(attr)}")
        else:
            print(f"  ✗ {method}: Not found")
    
    # Try to examine the Runner class
    try:
        from google.adk.agents.runner import Runner
        runner = Runner()
        print(f"\nRunner type: {type(runner)}")
        runner_methods = [attr for attr in dir(runner) if not attr.startswith('_')]
        print(f"Runner methods: {runner_methods}")
    except Exception as e:
        print(f"\nError importing Runner: {e}")
    
    # Test a simple call if possible
    try:
        print(f"\nTesting simple prompt...")
        
        # Try different approaches
        test_prompt = "Hello"
        
        # Method 1: Direct agent call
        try:
            result = agent(test_prompt)
            print(f"Direct call result: {type(result)} - {result}")
        except Exception as e:
            print(f"Direct call failed: {e}")
        
        # Method 2: Using Runner
        try:
            from google.adk.agents.runner import Runner
            runner = Runner()
            
            import asyncio
            async def test_runner():
                responses = []
                async for response in runner.run_live(agent, test_prompt):
                    responses.append(response)
                    print(f"Runner response: {type(response)} - {response}")
                    if len(responses) >= 3:  # Limit responses for testing
                        break
                return responses
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                responses = loop.run_until_complete(test_runner())
                print(f"Runner collected {len(responses)} responses")
            finally:
                loop.close()
                
        except Exception as e:
            print(f"Runner test failed: {e}")
            import traceback
            traceback.print_exc()
    
    except Exception as e:
        print(f"Testing failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_agent()