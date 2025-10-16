"""
LLM Client con fallback: Claude (Anthropic) -> Ollama (Qwen2.5:7b)

Características:
- Reintentos exponenciales con backoff
- Fallback automático a Ollama si Claude falla
- Logging detallado de métricas
- Circuit breaker para proteger servicios
"""

import os
import time
import asyncio
import logging
from typing import Optional, Dict, Any, Literal
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta

import aiohttp
from anthropic import AsyncAnthropic, APIError, RateLimitError, APITimeoutError

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """Proveedores LLM disponibles"""
    CLAUDE = "claude"
    OLLAMA = "ollama"


@dataclass
class LLMResponse:
    """Respuesta estandarizada de LLM"""
    content: str
    provider: LLMProvider
    model: str
    latency_ms: int
    tokens_used: Optional[int] = None
    cached: bool = False
    fallback_used: bool = False
    error: Optional[str] = None


class CircuitBreaker:
    """Circuit breaker para proteger servicios de sobrecarga"""

    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure_time: Optional[datetime] = None
        self.state: Literal["closed", "open", "half_open"] = "closed"

    def is_open(self) -> bool:
        """Verificar si el circuit breaker está abierto"""
        if self.state == "open":
            # Check if timeout has passed
            if self.last_failure_time and \
               (datetime.now() - self.last_failure_time).seconds >= self.timeout:
                self.state = "half_open"
                logger.info("Circuit breaker entering half-open state")
                return False
            return True
        return False

    def record_success(self):
        """Registrar éxito - resetear contador"""
        self.failures = 0
        self.state = "closed"

    def record_failure(self):
        """Registrar falla - incrementar contador"""
        self.failures += 1
        self.last_failure_time = datetime.now()

        if self.failures >= self.failure_threshold:
            self.state = "open"
            logger.warning(f"Circuit breaker opened after {self.failures} failures")


class LLMClient:
    """Cliente LLM con fallback Claude -> Ollama"""

    def __init__(
        self,
        anthropic_api_key: Optional[str] = None,
        anthropic_endpoint: Optional[str] = None,
        ollama_url: str = "http://localhost:11434",
        claude_model: str = "claude-sonnet-4-5-20250514",
        ollama_model: str = "qwen2.5:7b",
        max_retries: int = 3,
        timeout_seconds: int = 30,
        ollama_timeout_seconds: Optional[int] = None
    ):
        """
        Inicializar cliente LLM

        Args:
            anthropic_api_key: API key de Anthropic (default: desde env)
            anthropic_endpoint: Endpoint personalizado de Anthropic (opcional)
            ollama_url: URL de Ollama (default: localhost:11434)
            claude_model: Modelo de Claude a usar
            ollama_model: Modelo de Ollama a usar
            max_retries: Máximo número de reintentos por proveedor
            timeout_seconds: Timeout para requests Claude
            ollama_timeout_seconds: Timeout específico para Ollama (default: mismo que timeout_seconds)
        """
        # Configuración Claude
        self.anthropic_api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        self.anthropic_endpoint = anthropic_endpoint or os.getenv("ANTHROPIC_ENDPOINT")
        self.claude_model = claude_model

        # Configuración Ollama
        self.ollama_url = ollama_url
        self.ollama_model = ollama_model

        # Configuración general
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds
        # Ollama necesita más tiempo para modelos locales (default: 3x Claude timeout)
        self.ollama_timeout_seconds = ollama_timeout_seconds or timeout_seconds

        # Circuit breakers
        self.claude_breaker = CircuitBreaker(failure_threshold=5, timeout=60)
        self.ollama_breaker = CircuitBreaker(failure_threshold=3, timeout=30)

        # Cliente Anthropic
        self.claude_client: Optional[AsyncAnthropic] = None
        if self.anthropic_api_key:
            base_url = self.anthropic_endpoint if self.anthropic_endpoint else None
            self.claude_client = AsyncAnthropic(
                api_key=self.anthropic_api_key,
                base_url=base_url,
                timeout=timeout_seconds
            )
            logger.info(f"Claude client initialized with model {self.claude_model}")
        else:
            logger.warning(
                f"No ANTHROPIC_API_KEY found - Claude disabled, using Ollama only "
                f"({self.ollama_model} at {self.ollama_url}, timeout: {self.ollama_timeout_seconds}s)"
            )

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        force_provider: Optional[LLMProvider] = None
    ) -> LLMResponse:
        """
        Generar respuesta usando LLM con fallback automático

        Args:
            prompt: Prompt del usuario
            system_prompt: System prompt (opcional)
            max_tokens: Máximo de tokens a generar
            temperature: Temperatura (0-1, más alto = más creativo)
            force_provider: Forzar proveedor específico (opcional)

        Returns:
            LLMResponse con contenido y metadata
        """
        start_time = time.time()

        # Si se especifica proveedor forzado
        if force_provider == LLMProvider.OLLAMA:
            return await self._generate_ollama(prompt, system_prompt, max_tokens, temperature)

        # Intentar Claude primero (si disponible y circuit breaker cerrado)
        if self.claude_client and not self.claude_breaker.is_open():
            try:
                response = await self._generate_claude(prompt, system_prompt, max_tokens, temperature)
                self.claude_breaker.record_success()
                return response

            except (RateLimitError, APITimeoutError) as e:
                logger.warning(f"Claude failed ({type(e).__name__}), falling back to Ollama: {e}")
                self.claude_breaker.record_failure()
                # Fallback automático a Ollama

            except APIError as e:
                logger.error(f"Claude API error: {e}")
                self.claude_breaker.record_failure()
                # Fallback a Ollama

            except Exception as e:
                logger.error(f"Unexpected error with Claude: {e}", exc_info=True)
                self.claude_breaker.record_failure()
                # Fallback a Ollama

        # Usar Ollama (como fallback o primario)
        if not self.ollama_breaker.is_open():
            try:
                response = await self._generate_ollama(prompt, system_prompt, max_tokens, temperature)
                response.fallback_used = self.claude_client is not None  # True si Claude estaba disponible
                self.ollama_breaker.record_success()
                return response

            except Exception as e:
                logger.error(f"Ollama also failed: {e}", exc_info=True)
                self.ollama_breaker.record_failure()

                # Ambos fallaron - retornar error
                return LLMResponse(
                    content="Lo siento, el análisis LLM no está disponible temporalmente.",
                    provider=LLMProvider.OLLAMA,
                    model="error",
                    latency_ms=int((time.time() - start_time) * 1000),
                    fallback_used=True,
                    error=str(e)
                )

        # Si ambos circuit breakers están abiertos
        return LLMResponse(
            content="Servicio LLM temporalmente no disponible debido a múltiples fallos.",
            provider=LLMProvider.OLLAMA,
            model="circuit_breaker_open",
            latency_ms=int((time.time() - start_time) * 1000),
            fallback_used=True,
            error="All circuit breakers open"
        )

    async def _generate_claude(
        self,
        prompt: str,
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float
    ) -> LLMResponse:
        """Generar usando Claude con reintentos exponenciales"""

        for attempt in range(self.max_retries):
            try:
                start_time = time.time()

                # Construir mensajes
                messages = [{"role": "user", "content": prompt}]

                # Llamada a Claude
                response = await self.claude_client.messages.create(
                    model=self.claude_model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system_prompt if system_prompt else "",
                    messages=messages
                )

                latency_ms = int((time.time() - start_time) * 1000)

                # Extraer contenido
                content = response.content[0].text if response.content else ""

                logger.info(
                    f"Claude response generated in {latency_ms}ms "
                    f"(input: {response.usage.input_tokens}, output: {response.usage.output_tokens})"
                )

                return LLMResponse(
                    content=content,
                    provider=LLMProvider.CLAUDE,
                    model=self.claude_model,
                    latency_ms=latency_ms,
                    tokens_used=response.usage.input_tokens + response.usage.output_tokens,
                    fallback_used=False
                )

            except (RateLimitError, APITimeoutError) as e:
                # No reintentar en rate limit o timeout - ir a fallback inmediatamente
                logger.warning(f"Claude {type(e).__name__} on attempt {attempt + 1}")
                raise

            except APIError as e:
                if attempt < self.max_retries - 1:
                    # Backoff exponencial: 1s, 2s, 4s
                    wait_time = 2 ** attempt
                    logger.warning(f"Claude API error on attempt {attempt + 1}, retrying in {wait_time}s: {e}")
                    await asyncio.sleep(wait_time)
                else:
                    raise

            except Exception as e:
                logger.error(f"Unexpected Claude error on attempt {attempt + 1}: {e}")
                raise

    async def _generate_ollama(
        self,
        prompt: str,
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float
    ) -> LLMResponse:
        """Generar usando Ollama con reintentos"""

        for attempt in range(self.max_retries):
            try:
                start_time = time.time()

                # Construir payload para Ollama
                payload = {
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens
                    }
                }

                if system_prompt:
                    payload["system"] = system_prompt

                # Llamada HTTP a Ollama (con timeout extendido para modelos locales)
                timeout = aiohttp.ClientTimeout(total=self.ollama_timeout_seconds)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(
                        f"{self.ollama_url}/api/generate",
                        json=payload
                    ) as response:
                        response.raise_for_status()
                        result = await response.json()

                latency_ms = int((time.time() - start_time) * 1000)

                content = result.get("response", "")

                logger.info(f"Ollama ({self.ollama_model}) response generated in {latency_ms}ms ({len(content)} chars)")

                return LLMResponse(
                    content=content,
                    provider=LLMProvider.OLLAMA,
                    model=self.ollama_model,
                    latency_ms=latency_ms,
                    fallback_used=False
                )

            except aiohttp.ClientError as e:
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Ollama connection error on attempt {attempt + 1}, retrying in {wait_time}s: {e}")
                    await asyncio.sleep(wait_time)
                else:
                    raise Exception(f"Ollama failed after {self.max_retries} attempts: {e}")

            except Exception as e:
                logger.error(f"Unexpected Ollama error on attempt {attempt + 1}: {e}")
                raise

    async def health_check(self) -> Dict[str, Any]:
        """Verificar estado de ambos proveedores"""
        status = {
            "claude": {
                "available": self.claude_client is not None,
                "circuit_breaker": self.claude_breaker.state,
                "failures": self.claude_breaker.failures
            },
            "ollama": {
                "available": True,  # Asumimos que Ollama siempre está configurado
                "circuit_breaker": self.ollama_breaker.state,
                "failures": self.ollama_breaker.failures
            }
        }

        # Test rápido de Ollama
        try:
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{self.ollama_url}/api/tags") as response:
                    status["ollama"]["reachable"] = response.status == 200
        except Exception as e:
            status["ollama"]["reachable"] = False
            status["ollama"]["error"] = str(e)

        return status


# Instancia global (singleton)
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Obtener instancia singleton de LLMClient"""
    global _llm_client

    if _llm_client is None:
        # Obtener timeout base
        base_timeout = int(os.getenv("LLM_TIMEOUT", "30"))

        _llm_client = LLMClient(
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            anthropic_endpoint=os.getenv("ANTHROPIC_ENDPOINT"),
            ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
            claude_model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250514"),
            ollama_model=os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
            max_retries=int(os.getenv("LLM_MAX_RETRIES", "3")),
            timeout_seconds=30,  # Claude: siempre 30s (API remota rápida)
            ollama_timeout_seconds=base_timeout  # Ollama: usa LLM_TIMEOUT del .env
        )

    return _llm_client
