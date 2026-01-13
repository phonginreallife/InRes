#!/usr/bin/env python3
"""
Test script for Hybrid Agent.

This script tests the hybrid agent locally without Docker.

Usage:
    # Set your API key
    export ANTHROPIC_API_KEY=sk-ant-...
    
    # Run from agent directory
    cd server/agent
    python scripts/test_hybrid.py

    # Run with custom prompt
    python scripts/test_hybrid.py "Show me recent incidents"
"""

import asyncio
import os
import sys

# Add parent directory to path for imports
agent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, agent_dir)
os.chdir(agent_dir)  # Change to agent directory for relative imports


async def test_hybrid_agent():
    """Test the hybrid agent with a simple query."""
    from hybrid import HybridAgent, HybridAgentConfig
    from streaming.agent import INCIDENT_TOOLS
    
    # Get prompt from args or use default
    prompt = sys.argv[1] if len(sys.argv) > 1 else "Hello! What can you help me with?"
    
    print("=" * 60)
    print("HYBRID AGENT TEST")
    print("=" * 60)
    print(f"Prompt: {prompt}")
    print("-" * 60)
    
    # Create config
    config = HybridAgentConfig(
        model="claude-sonnet-4-20250514",
        streaming_model="claude-sonnet-4-20250514",
        planning_model="claude-sonnet-4-20250514",
        max_tokens=2048,
        max_planning_tokens=512,
        tools=INCIDENT_TOOLS,
        system_prompt="You are a helpful AI assistant for DevOps and incident response.",
        always_plan=False,  # Use heuristics
    )
    
    # Create agent
    agent = HybridAgent(config=config)
    
    # Create output queue
    output_queue = asyncio.Queue()
    
    # Simple tool executor (mock)
    async def mock_tool_executor(tool_name: str, tool_input: dict) -> str:
        print(f"\n[TOOL] {tool_name}")
        print(f"  Input: {tool_input}")
        return f"Mock result for {tool_name}: This is a test response."
    
    # Process message in background
    async def process():
        return await agent.process_message(
            prompt=prompt,
            output_queue=output_queue,
            tool_executor=mock_tool_executor
        )
    
    # Start processing
    task = asyncio.create_task(process())
    
    # Collect and display events
    full_response = ""
    print("\nStreaming Response:")
    print("-" * 60)
    
    while True:
        try:
            event = await asyncio.wait_for(output_queue.get(), timeout=0.1)
            
            if event["type"] == "delta":
                # Print token without newline for streaming effect
                print(event["content"], end="", flush=True)
                full_response += event["content"]
            elif event["type"] == "tool_use":
                print(f"\n[Tool: {event['name']}]")
            elif event["type"] == "tool_result":
                print(f"[Result: {event['content'][:50]}...]")
            elif event["type"] == "thinking":
                print(f"\n[Thinking: {event['content'][:100]}...]")
            elif event["type"] == "complete":
                print("\n")
                break
            elif event["type"] == "error":
                print(f"\n[ERROR: {event['error']}]")
                break
                
        except asyncio.TimeoutError:
            if task.done():
                break
            continue
    
    # Wait for task to complete
    result = await task
    
    print("-" * 60)
    print(f"Full response length: {len(result)} chars")
    print("=" * 60)
    
    return result


async def test_streaming_agent():
    """Test the pure streaming agent for comparison."""
    from streaming import StreamingAgent, INCIDENT_TOOLS
    
    prompt = sys.argv[1] if len(sys.argv) > 1 else "Hello! What can you help me with?"
    
    print("=" * 60)
    print("STREAMING AGENT TEST (for comparison)")
    print("=" * 60)
    print(f"Prompt: {prompt}")
    print("-" * 60)
    
    agent = StreamingAgent(
        tools=INCIDENT_TOOLS,
        system_prompt="You are a helpful AI assistant.",
    )
    
    output_queue = asyncio.Queue()
    
    async def mock_executor(tool_name: str, tool_input: dict) -> str:
        return f"Mock result for {tool_name}"
    
    async def process():
        return await agent.stream_response(
            prompt=prompt,
            output_queue=output_queue,
            tool_executor=mock_executor
        )
    
    task = asyncio.create_task(process())
    
    print("\nStreaming Response:")
    print("-" * 60)
    
    while True:
        try:
            event = await asyncio.wait_for(output_queue.get(), timeout=0.1)
            
            if event["type"] == "delta":
                print(event["content"], end="", flush=True)
            elif event["type"] == "complete":
                print("\n")
                break
            elif event["type"] == "error":
                print(f"\n[ERROR: {event['error']}]")
                break
                
        except asyncio.TimeoutError:
            if task.done():
                break
            continue
    
    result = await task
    print("-" * 60)
    print(f"Full response length: {len(result)} chars")
    print("=" * 60)


async def main():
    """Run tests."""
    # Check for API key
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set")
        print("Run: export ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)
    
    # Run hybrid test
    await test_hybrid_agent()
    
    # Optionally run streaming test for comparison
    if "--compare" in sys.argv:
        print("\n\n")
        await test_streaming_agent()


if __name__ == "__main__":
    asyncio.run(main())
