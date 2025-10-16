#!/usr/bin/env python3
"""Test directo del LLM client sin pasar por la API"""

import asyncio
import sys
from pathlib import Path

# Agregar el directorio api al path
sys.path.insert(0, str(Path(__file__).parent / 'api'))

from llm_client import get_llm_client
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv(Path(__file__).parent / 'api' / '.env')


async def test_llm():
    """Probar generación de texto con Ollama"""

    print("🧪 Testing LLM Client...")
    print("=" * 60)

    # Obtener cliente
    client = get_llm_client()

    # Mostrar configuración
    print(f"\n✓ LLM Client initialized:")
    print(f"  - Claude available: {client.claude_client is not None}")
    print(f"  - Ollama URL: {client.ollama_url}")
    print(f"  - Ollama model: {client.ollama_model}")
    print(f"  - Ollama timeout: {client.ollama_timeout_seconds}s")
    print(f"  - Claude timeout: {client.timeout_seconds}s")

    # Probar generación
    print(f"\n🚀 Generating text with Ollama (this may take ~2 minutes)...")

    prompt = """Analiza esta pelea de MMA:

**Fighter A**: Azamat Bekoev
- Record: 10-2-0
- Altura: 180cm, Alcance: 185cm
- Edad: 28 años

**Fighter B**: Yousri Belgaroui
- Record: 8-4-0
- Altura: 193cm, Alcance: 203cm
- Edad: 30 años

Predicción del modelo: 19.5% para Bekoev vs 80.5% para Belgaroui

Da un análisis breve de 2 párrafos sobre esta pelea."""

    try:
        response = await client.generate(
            prompt=prompt,
            system_prompt="Eres un analista experto en MMA.",
            max_tokens=500,
            temperature=0.7
        )

        print(f"\n✅ SUCCESS!")
        print(f"  - Provider: {response.provider.value}")
        print(f"  - Model: {response.model}")
        print(f"  - Latency: {response.latency_ms}ms ({response.latency_ms/1000:.1f}s)")
        print(f"  - Content length: {len(response.content)} chars")
        print(f"  - Fallback used: {response.fallback_used}")
        print(f"\n📝 Generated content:")
        print("=" * 60)
        print(response.content)
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_llm())
