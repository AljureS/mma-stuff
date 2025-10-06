"""
Tests unitarios para LLMClient con mocks

Ejecutar:
    pytest tests/test_llm_client.py -v
    pytest tests/test_llm_client.py::test_claude_success -v
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from anthropic import RateLimitError, APITimeoutError, APIError

import sys
sys.path.insert(0, '/home/saidsimon2/mma-predictor/api')

from llm_client import LLMClient, LLMProvider, LLMResponse, CircuitBreaker


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def llm_client_with_claude():
    """Cliente LLM con Claude configurado"""
    return LLMClient(
        anthropic_api_key="test-api-key",
        ollama_url="http://localhost:11434",
        max_retries=3,
        timeout_seconds=10
    )


@pytest.fixture
def llm_client_ollama_only():
    """Cliente LLM solo con Ollama (sin API key)"""
    return LLMClient(
        anthropic_api_key=None,
        ollama_url="http://localhost:11434"
    )


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
# CLAUDE TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_claude_success(llm_client_with_claude):
    """Test: Claude debe generar respuesta exitosa"""

    # Mock del cliente Anthropic
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Este es un análisis de MMA detallado.")]
    mock_response.usage = MagicMock(input_tokens=100, output_tokens=200)

    with patch.object(
        llm_client_with_claude.claude_client.messages,
        'create',
        new_callable=AsyncMock,
        return_value=mock_response
    ):
        response = await llm_client_with_claude.generate(
            prompt="Analiza Jon Jones vs Stipe Miocic",
            max_tokens=500
        )

        assert response.provider == LLMProvider.CLAUDE
        assert response.content == "Este es un análisis de MMA detallado."
        assert response.tokens_used == 300
        assert not response.fallback_used
        assert response.latency_ms > 0


@pytest.mark.asyncio
async def test_claude_rate_limit_fallback_to_ollama(llm_client_with_claude):
    """Test: Rate limit en Claude debe hacer fallback a Ollama"""

    # Mock Claude lanzando RateLimitError
    with patch.object(
        llm_client_with_claude.claude_client.messages,
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

            response = await llm_client_with_claude.generate(
                prompt="Analiza pelea",
                max_tokens=500
            )

            assert response.provider == LLMProvider.OLLAMA
            assert response.fallback_used is True
            assert "Análisis desde Ollama" in response.content


@pytest.mark.asyncio
async def test_claude_timeout_fallback_to_ollama(llm_client_with_claude):
    """Test: Timeout en Claude debe hacer fallback a Ollama"""

    with patch.object(
        llm_client_with_claude.claude_client.messages,
        'create',
        new_callable=AsyncMock,
        side_effect=APITimeoutError("Request timeout")
    ):
        mock_ollama_response = {"response": "Análisis rápido desde Ollama"}

        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.return_value.__aenter__.return_value.json = AsyncMock(
                return_value=mock_ollama_response
            )
            mock_post.return_value.__aenter__.return_value.raise_for_status = Mock()

            response = await llm_client_with_claude.generate(
                prompt="Analiza pelea urgente",
                max_tokens=300
            )

            assert response.provider == LLMProvider.OLLAMA
            assert response.fallback_used is True


@pytest.mark.asyncio
async def test_claude_retries_on_api_error(llm_client_with_claude):
    """Test: Claude debe reintentar en errores de API"""

    call_count = 0

    async def mock_create_with_retries(*args, **kwargs):
        nonlocal call_count
        call_count += 1

        if call_count < 3:
            raise APIError("Temporary error", request=MagicMock(), body={})

        # Éxito en el tercer intento
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Éxito después de reintentos")]
        mock_response.usage = MagicMock(input_tokens=50, output_tokens=100)
        return mock_response

    with patch.object(
        llm_client_with_claude.claude_client.messages,
        'create',
        new_callable=AsyncMock,
        side_effect=mock_create_with_retries
    ):
        response = await llm_client_with_claude.generate(
            prompt="Test retry",
            max_tokens=200
        )

        assert call_count == 3
        assert response.provider == LLMProvider.CLAUDE
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
        assert response.latency_ms > 0


@pytest.mark.asyncio
async def test_ollama_retries_on_connection_error(llm_client_ollama_only):
    """Test: Ollama debe reintentar en errores de conexión"""

    call_count = 0

    async def mock_post_with_retries(*args, **kwargs):
        nonlocal call_count
        call_count += 1

        if call_count < 2:
            raise Exception("Connection refused")

        # Éxito en segundo intento
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={"response": "Conectado después de reintentos"})
        mock_response.raise_for_status = Mock()
        return mock_response

    with patch('aiohttp.ClientSession.post', side_effect=mock_post_with_retries):
        # Capturamos la excepción final si falla
        try:
            response = await llm_client_ollama_only.generate(
                prompt="Test Ollama retry",
                max_tokens=300
            )
            # Si tuvo éxito después de reintentos
            assert call_count >= 2
        except Exception:
            # Si falla después de todos los reintentos
            assert call_count == llm_client_ollama_only.max_retries


# ============================================================================
# FALLBACK TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_both_providers_fail_returns_error_response(llm_client_with_claude):
    """Test: Si ambos proveedores fallan, debe retornar respuesta de error"""

    # Mock Claude fallando
    with patch.object(
        llm_client_with_claude.claude_client.messages,
        'create',
        new_callable=AsyncMock,
        side_effect=APIError("Claude down", request=MagicMock(), body={})
    ):
        # Mock Ollama fallando
        with patch('aiohttp.ClientSession.post', side_effect=Exception("Ollama down")):
            response = await llm_client_with_claude.generate(
                prompt="Test total failure",
                max_tokens=200
            )

            assert response.error is not None
            assert "no está disponible" in response.content.lower()
            assert response.fallback_used is True


@pytest.mark.asyncio
async def test_circuit_breaker_prevents_repeated_calls(llm_client_with_claude):
    """Test: Circuit breaker debe prevenir llamadas repetidas después de múltiples fallas"""

    # Simular múltiples fallas en Claude
    with patch.object(
        llm_client_with_claude.claude_client.messages,
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
                await llm_client_with_claude.generate(prompt=f"Test {i}", max_tokens=100)

            # Circuit breaker de Claude debe estar abierto
            assert llm_client_with_claude.claude_breaker.is_open()


# ============================================================================
# HEALTH CHECK TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_health_check_ollama_reachable(llm_client_with_claude):
    """Test: Health check debe detectar Ollama disponible"""

    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_get.return_value.__aenter__.return_value.status = 200

        health = await llm_client_with_claude.health_check()

        assert health['claude']['available'] is True
        assert health['ollama']['available'] is True
        assert health['ollama']['reachable'] is True


@pytest.mark.asyncio
async def test_health_check_ollama_unreachable(llm_client_with_claude):
    """Test: Health check debe detectar Ollama no disponible"""

    with patch('aiohttp.ClientSession.get', side_effect=Exception("Connection refused")):
        health = await llm_client_with_claude.health_check()

        assert health['ollama']['reachable'] is False
        assert 'error' in health['ollama']


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_system_prompt_passed_to_claude(llm_client_with_claude):
    """Test: System prompt debe pasarse correctamente a Claude"""

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Respuesta con system prompt")]
    mock_response.usage = MagicMock(input_tokens=50, output_tokens=100)

    with patch.object(
        llm_client_with_claude.claude_client.messages,
        'create',
        new_callable=AsyncMock,
        return_value=mock_response
    ) as mock_create:
        await llm_client_with_claude.generate(
            prompt="Analiza pelea",
            system_prompt="Eres un experto en MMA",
            max_tokens=300
        )

        # Verificar que system prompt fue pasado
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs['system'] == "Eres un experto en MMA"


@pytest.mark.asyncio
async def test_temperature_and_max_tokens_respected(llm_client_with_claude):
    """Test: Parámetros de temperatura y max_tokens deben respetarse"""

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Test")]
    mock_response.usage = MagicMock(input_tokens=10, output_tokens=20)

    with patch.object(
        llm_client_with_claude.claude_client.messages,
        'create',
        new_callable=AsyncMock,
        return_value=mock_response
    ) as mock_create:
        await llm_client_with_claude.generate(
            prompt="Test",
            max_tokens=1500,
            temperature=0.9
        )

        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs['max_tokens'] == 1500
        assert call_kwargs['temperature'] == 0.9


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
