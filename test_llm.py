#!/usr/bin/env python3
"""
Test script for LLM Client (Claude + Ollama fallback)
Run with: python test_llm.py
"""

import asyncio
import sys
import os
from pathlib import Path

# Add api directory to path
sys.path.insert(0, str(Path(__file__).parent / 'api'))

from llm_client import get_llm_client, LLMProvider
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent / 'api' / '.env')

async def test_llm_client():
    """Test both Claude and Ollama providers"""

    client = get_llm_client()

    print("=" * 80)
    print("🧪 Testing LLM Client")
    print("=" * 80)

    test_prompt = "Explain in 2-3 sentences what makes a good MMA fighter."
    system_prompt = "You are an MMA expert analyst."

    # Test 1: Try Claude first (will fallback to Ollama if it fails)
    print("\n📝 Test 1: Auto fallback (Claude → Ollama if needed)")
    print("-" * 80)
    try:
        response = await client.generate(
            prompt=test_prompt,
            system_prompt=system_prompt,
            max_tokens=150,
            temperature=0.7
        )

        print(f"✅ Success!")
        print(f"   Provider: {response.provider.value}")
        print(f"   Model: {response.model}")
        print(f"   Latency: {response.latency_ms}ms")
        print(f"   Fallback used: {response.fallback_used}")
        print(f"   Tokens: {response.tokens_used}")
        print(f"\n📄 Response:\n{response.content}\n")

    except Exception as e:
        print(f"❌ Failed: {e}")

    # Test 2: Force Ollama
    print("\n📝 Test 2: Force Ollama (local model)")
    print("-" * 80)
    try:
        response = await client.generate(
            prompt=test_prompt,
            system_prompt=system_prompt,
            max_tokens=150,
            temperature=0.7,
            force_provider=LLMProvider.OLLAMA
        )

        print(f"✅ Success!")
        print(f"   Provider: {response.provider.value}")
        print(f"   Model: {response.model}")
        print(f"   Latency: {response.latency_ms}ms")
        print(f"\n📄 Response:\n{response.content}\n")

    except Exception as e:
        print(f"❌ Failed: {e}")

    # Test 3: Health check
    print("\n📝 Test 3: Health Check")
    print("-" * 80)
    try:
        health = await client.health_check()
        print(f"✅ Health check results:")
        print(f"   Claude: {health['claude']}")
        print(f"   Ollama: {health['ollama']}")

    except Exception as e:
        print(f"❌ Failed: {e}")

    print("\n" + "=" * 80)
    print("✅ All tests completed!")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_llm_client())
