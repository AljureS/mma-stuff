"""
Tests unitarios para LLMClient con mocks

Ejecutar:
    pytest tests/test_llm_client.py -v
    pytest tests/test_llm_client.py::test_openai_success -v
"""

import pytest
import asyncio
import aiohttp
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from openai import RateLimitError, APITimeoutError, APIError

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'api'))

import llm_client as llm_module
from llm_client import LLMClient, LLMProvider, LLMResponse, CircuitBreaker


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def llm_client_with_openai():
    """Cliente LLM con OpenAI configurado"""
    return LLMClient(
        openai_api_key="test-api-key",
        ollama_url="http://localhost:11434",
        max_retries=3,
        timeout_seconds=10
    )


@pytest.fixture
def llm_client_ollama_only(monkeypatch):
    """Cliente LLM solo con Ollama (sin API key)"""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    return LLMClient(
        openai_api_key=None,
        ollama_url="http://localhost:11434"
    )


def make_openai_response(text: str, prompt_tokens: int = 100, completion_tokens: int = 200):
    """Construir un mock con la forma de respuesta de chat.completions"""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content=text))]
    mock_response.usage = MagicMock(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens
    )
    return mock_response


# ============================================================================
# CIRCUIT BREAKER TESTS
# ============================================================================

def test_circuit_breaker_initial_state():
    """Circuit breaker debe iniciar en estado cerrado"""
    cb = CircuitBreaker(failure_threshold=3, timeout=60)
    assert cb.state == "closed"
    assert cb.failures == 0
    assert not cb.is_open()


def test_circuit_breaker_opens_after_threshold():
    """Circuit breaker debe abrirse después del threshold de fallas"""
    cb = CircuitBreaker(failure_threshold=3, timeout=60)

    cb.record_failure()
    assert cb.state == "closed"

    cb.record_failure()
    assert cb.state == "closed"

    cb.record_failure()
    assert cb.state == "open"
    assert cb.is_open()


def test_circuit_breaker_resets_on_success():
    """Circuit breaker debe resetearse en éxito"""
    cb = CircuitBreaker(failure_threshold=3, timeout=60)

    cb.record_failure()
    cb.record_failure()
    assert cb.failures == 2

    cb.record_success()
    assert cb.failures == 0
    assert cb.state == "closed"


# ============================================================================
# OPENAI TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_openai_success(llm_client_with_openai):
    """Test: El cliente por defecto usa Luna sin razonamiento y retorna su respuesta"""

    mock_response = make_openai_response("Este es un análisis de MMA detallado.")

    with patch.object(
        llm_client_with_openai.openai_client.chat.completions,
        'create',
        new_callable=AsyncMock,
        return_value=mock_response
    ) as mock_create:
        response = await llm_client_with_openai.generate(
            prompt="Analiza Jon Jones vs Stipe Miocic",
            max_tokens=500
        )

        mock_create.assert_awaited_once_with(
            model="gpt-6-luna",
            max_completion_tokens=500,
            temperature=0.7,
            messages=[{"role": "user", "content": "Analiza Jon Jones vs Stipe Miocic"}],
            reasoning_effort="none"
        )
        assert response.provider == LLMProvider.OPENAI
        assert response.model == "gpt-6-luna"
        assert response.content == "Este es un análisis de MMA detallado."
        assert response.tokens_used == 300
        assert not response.fallback_used
        assert response.latency_ms >= 0  # con mocks la llamada puede tardar <1ms


@pytest.mark.asyncio
@pytest.mark.parametrize("configured_model", [None, "gpt-6-luna", "gpt-4o-mini"])
async def test_factory_openai_request_respects_model_override(monkeypatch, configured_model):
    """La factory usa Luna por defecto y omite effort en el override legado"""
    monkeypatch.setattr(llm_module, "_llm_client", None)
    monkeypatch.setenv("OPENAI_API_KEY", "test-api-key")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    if configured_model is None:
        monkeypatch.delenv("OPENAI_MODEL", raising=False)
    else:
        monkeypatch.setenv("OPENAI_MODEL", configured_model)

    client = llm_module.get_llm_client()
    expected_model = configured_model or "gpt-6-luna"
    try:
        with patch.object(
            client.openai_client.chat.completions,
            'create',
            new_callable=AsyncMock,
            return_value=make_openai_response("Análisis desde el modelo configurado")
        ) as mock_create:
            response = await client.generate(
                prompt="Analiza pelea",
                system_prompt="Eres un experto en MMA",
                max_tokens=800,
                temperature=0.7
            )

            expected_kwargs = {
                "model": expected_model,
                "max_completion_tokens": 800,
                "temperature": 0.7,
                "messages": [
                    {"role": "system", "content": "Eres un experto en MMA"},
                    {"role": "user", "content": "Analiza pelea"}
                ]
            }
            if expected_model == "gpt-6-luna":
                expected_kwargs["reasoning_effort"] = "none"
            mock_create.assert_awaited_once_with(**expected_kwargs)
            assert response.provider == LLMProvider.OPENAI
            assert response.model == expected_model
            assert response.content == "Análisis desde el modelo configurado"
            assert response.fallback_used is False
    finally:
        await client.openai_client.close()


@pytest.mark.asyncio
async def test_openai_rate_limit_fallback_to_ollama(llm_client_with_openai):
    """Test: Rate limit en OpenAI debe hacer fallback a Ollama"""

    # Mock OpenAI lanzando RateLimitError
    with patch.object(
        llm_client_with_openai.openai_client.chat.completions,
        'create',
        new_callable=AsyncMock,
        side_effect=RateLimitError("Rate limit exceeded", response=MagicMock(), body={})
    ):
        # Mock Ollama exitoso
        mock_ollama_response = {"response": "Análisis desde Ollama"}

        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.return_value.__aenter__.return_value.json = AsyncMock(
                return_value=mock_ollama_response
            )
            mock_post.return_value.__aenter__.return_value.raise_for_status = Mock()

            response = await llm_client_with_openai.generate(
                prompt="Analiza pelea",
                max_tokens=500
            )

            assert response.provider == LLMProvider.OLLAMA
            assert response.fallback_used is True
            assert "Análisis desde Ollama" in response.content


@pytest.mark.asyncio
async def test_openai_timeout_fallback_to_ollama(llm_client_with_openai):
    """Test: Timeout en OpenAI debe hacer fallback a Ollama"""

    with patch.object(
        llm_client_with_openai.openai_client.chat.completions,
        'create',
        new_callable=AsyncMock,
        side_effect=APITimeoutError(request=MagicMock())
    ):
        mock_ollama_response = {"response": "Análisis rápido desde Ollama"}

        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.return_value.__aenter__.return_value.json = AsyncMock(
                return_value=mock_ollama_response
            )
            mock_post.return_value.__aenter__.return_value.raise_for_status = Mock()

            response = await llm_client_with_openai.generate(
                prompt="Analiza pelea urgente",
                max_tokens=300
            )

            assert response.provider == LLMProvider.OLLAMA
            assert response.fallback_used is True


@pytest.mark.asyncio
async def test_openai_retries_on_api_error(llm_client_with_openai):
    """Test: OpenAI debe reintentar en errores de API"""

    call_count = 0

    async def mock_create_with_retries(*args, **kwargs):
        nonlocal call_count
        call_count += 1

        if call_count < 3:
            raise APIError("Temporary error", request=MagicMock(), body={})

        # Éxito en el tercer intento
        return make_openai_response("Éxito después de reintentos", prompt_tokens=50, completion_tokens=100)

    with patch.object(
        llm_client_with_openai.openai_client.chat.completions,
        'create',
        new_callable=AsyncMock,
        side_effect=mock_create_with_retries
    ):
        response = await llm_client_with_openai.generate(
            prompt="Test retry",
            max_tokens=200
        )

        assert call_count == 3
        assert response.provider == LLMProvider.OPENAI
        assert "Éxito después de reintentos" in response.content


# ============================================================================
# OLLAMA TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_ollama_success(llm_client_ollama_only):
    """Test: Ollama debe generar respuesta exitosa"""

    mock_ollama_response = {"response": "Análisis completo desde Ollama local"}

    with patch('aiohttp.ClientSession.post') as mock_post:
        mock_post.return_value.__aenter__.return_value.json = AsyncMock(
            return_value=mock_ollama_response
        )
        mock_post.return_value.__aenter__.return_value.raise_for_status = Mock()

        response = await llm_client_ollama_only.generate(
            prompt="Analiza pelea",
            max_tokens=500
        )

        assert response.provider == LLMProvider.OLLAMA
        assert response.content == "Análisis completo desde Ollama local"
        assert not response.fallback_used
        assert response.latency_ms >= 0  # con mocks la llamada puede tardar <1ms


@pytest.mark.asyncio
async def test_ollama_retries_on_connection_error(llm_client_ollama_only):
    """Test: Ollama debe reintentar en errores de conexión"""

    call_count = 0

    def mock_post_with_retries(*args, **kwargs):
        nonlocal call_count
        call_count += 1

        # Solo aiohttp.ClientError dispara el reintento en _generate_ollama
        if call_count < 2:
            raise aiohttp.ClientError("Connection refused")

        # Éxito en segundo intento: mock del async context manager
        cm = MagicMock()
        cm.__aenter__.return_value.json = AsyncMock(
            return_value={"response": "Conectado después de reintentos"}
        )
        cm.__aenter__.return_value.raise_for_status = Mock()
        return cm

    with patch('aiohttp.ClientSession.post', side_effect=mock_post_with_retries):
        response = await llm_client_ollama_only.generate(
            prompt="Test Ollama retry",
            max_tokens=300
        )

        assert call_count == 2
        assert response.provider == LLMProvider.OLLAMA
        assert "Conectado después de reintentos" in response.content


# ============================================================================
# FALLBACK TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_both_providers_fail_returns_error_response(llm_client_with_openai):
    """Test: Si ambos proveedores fallan, debe retornar respuesta de error"""

    # Mock OpenAI fallando
    with patch.object(
        llm_client_with_openai.openai_client.chat.completions,
        'create',
        new_callable=AsyncMock,
        side_effect=APIError("OpenAI down", request=MagicMock(), body={})
    ):
        # Mock Ollama fallando
        with patch('aiohttp.ClientSession.post', side_effect=Exception("Ollama down")):
            response = await llm_client_with_openai.generate(
                prompt="Test total failure",
                max_tokens=200
            )

            assert response.error is not None
            assert "no está disponible" in response.content.lower()
            assert response.fallback_used is True


@pytest.mark.asyncio
async def test_circuit_breaker_prevents_repeated_calls(llm_client_with_openai):
    """Test: Circuit breaker debe prevenir llamadas repetidas después de múltiples fallas"""

    # Simular múltiples fallas en OpenAI
    with patch.object(
        llm_client_with_openai.openai_client.chat.completions,
        'create',
        new_callable=AsyncMock,
        side_effect=APIError("Persistent error", request=MagicMock(), body={})
    ):
        # Mock Ollama funcionando
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.return_value.__aenter__.return_value.json = AsyncMock(
                return_value={"response": "Ollama response"}
            )
            mock_post.return_value.__aenter__.return_value.raise_for_status = Mock()

            # Hacer múltiples requests para abrir circuit breaker
            for i in range(6):
                await llm_client_with_openai.generate(prompt=f"Test {i}", max_tokens=100)

            # Circuit breaker de OpenAI debe estar abierto
            assert llm_client_with_openai.openai_breaker.is_open()


# ============================================================================
# HEALTH CHECK TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_health_check_ollama_reachable(llm_client_with_openai):
    """Test: Health check debe detectar Ollama disponible"""

    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_get.return_value.__aenter__.return_value.status = 200

        health = await llm_client_with_openai.health_check()

        assert health['openai']['available'] is True
        assert health['ollama']['available'] is True
        assert health['ollama']['reachable'] is True


@pytest.mark.asyncio
async def test_health_check_ollama_unreachable(llm_client_with_openai):
    """Test: Health check debe detectar Ollama no disponible"""

    with patch('aiohttp.ClientSession.get', side_effect=Exception("Connection refused")):
        health = await llm_client_with_openai.health_check()

        assert health['ollama']['reachable'] is False
        assert 'error' in health['ollama']


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_system_prompt_passed_to_openai(llm_client_with_openai):
    """Test: System prompt debe pasarse correctamente a OpenAI"""

    mock_response = make_openai_response("Respuesta con system prompt", prompt_tokens=50, completion_tokens=100)

    with patch.object(
        llm_client_with_openai.openai_client.chat.completions,
        'create',
        new_callable=AsyncMock,
        return_value=mock_response
    ) as mock_create:
        await llm_client_with_openai.generate(
            prompt="Analiza pelea",
            system_prompt="Eres un experto en MMA",
            max_tokens=300
        )

        # Verificar que system prompt fue pasado como primer mensaje
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs['messages'][0] == {"role": "system", "content": "Eres un experto en MMA"}
        assert call_kwargs['messages'][1] == {"role": "user", "content": "Analiza pelea"}


@pytest.mark.asyncio
async def test_temperature_and_max_tokens_respected(llm_client_with_openai):
    """Test: Parámetros de temperatura y max_tokens deben respetarse"""

    mock_response = make_openai_response("Test", prompt_tokens=10, completion_tokens=20)

    with patch.object(
        llm_client_with_openai.openai_client.chat.completions,
        'create',
        new_callable=AsyncMock,
        return_value=mock_response
    ) as mock_create:
        await llm_client_with_openai.generate(
            prompt="Test",
            max_tokens=1500,
            temperature=0.9
        )

        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs['max_completion_tokens'] == 1500
        assert call_kwargs['temperature'] == 0.9


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
