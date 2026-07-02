"""
LLM Client con fallback: OpenAI (gpt-4o-mini) -> Ollama (Qwen2.5:7b)

Características:
- Reintentos exponenciales con backoff
- Fallback automático a Ollama si OpenAI falla
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
from openai import AsyncOpenAI, APIError, RateLimitError, APITimeoutError

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """Proveedores LLM disponibles"""
    OPENAI = "openai"
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
    """Cliente LLM con fallback OpenAI -> Ollama"""

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        openai_base_url: Optional[str] = None,
        ollama_url: str = "http://localhost:11434",
        openai_model: str = "gpt-4o-mini",
        ollama_model: str = "qwen2.5:7b",
        max_retries: int = 3,
        timeout_seconds: int = 30,
        ollama_timeout_seconds: Optional[int] = None
    ):
        """
        Inicializar cliente LLM

        Args:
            openai_api_key: API key de OpenAI (default: desde env)
            openai_base_url: Base URL personalizada de OpenAI (opcional)
            ollama_url: URL de Ollama (default: localhost:11434)
            openai_model: Modelo de OpenAI a usar
            ollama_model: Modelo de Ollama a usar
            max_retries: Máximo número de reintentos por proveedor
            timeout_seconds: Timeout para requests OpenAI
            ollama_timeout_seconds: Timeout específico para Ollama (default: mismo que timeout_seconds)
        """
        # Configuración OpenAI
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.openai_base_url = openai_base_url or os.getenv("OPENAI_BASE_URL")
        self.openai_model = openai_model

        # Configuración Ollama
        self.ollama_url = ollama_url
        self.ollama_model = ollama_model

        # Configuración general
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds
        # Ollama necesita más tiempo para modelos locales
        self.ollama_timeout_seconds = ollama_timeout_seconds if ollama_timeout_seconds is not None else (timeout_seconds * 3)

        # Circuit breakers
        self.openai_breaker = CircuitBreaker(failure_threshold=5, timeout=60)
        self.ollama_breaker = CircuitBreaker(failure_threshold=3, timeout=30)

        # Cliente OpenAI
        self.openai_client: Optional[AsyncOpenAI] = None
        if self.openai_api_key:
            base_url = self.openai_base_url if self.openai_base_url else None
            # timeout explícito: el default del SDK es 600s y rompería el fast-fallback
            self.openai_client = AsyncOpenAI(
                api_key=self.openai_api_key,
                base_url=base_url,
                timeout=timeout_seconds
            )
            logger.info(f"OpenAI client initialized with model {self.openai_model}")
        else:
            logger.warning(
                f"No OPENAI_API_KEY found - OpenAI disabled, using Ollama only "
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
            temperature: Temperatura (más alto = más creativo)
            force_provider: Forzar proveedor específico (opcional)

        Returns:
            LLMResponse con contenido y metadata
        """
        start_time = time.time()

        # Si se especifica proveedor forzado
        if force_provider == LLMProvider.OLLAMA:
            return await self._generate_ollama(prompt, system_prompt, max_tokens, temperature)

        # Intentar OpenAI primero (si disponible y circuit breaker cerrado)
        if self.openai_client and not self.openai_breaker.is_open():
            try:
                response = await self._generate_openai(prompt, system_prompt, max_tokens, temperature)
                self.openai_breaker.record_success()
                return response

            except (RateLimitError, APITimeoutError) as e:
                logger.warning(f"OpenAI failed ({type(e).__name__}), falling back to Ollama: {e}")
                self.openai_breaker.record_failure()
                # Fallback automático a Ollama

            except APIError as e:
                logger.error(f"OpenAI API error: {e}")
                self.openai_breaker.record_failure()
                # Fallback a Ollama

            except Exception as e:
                logger.error(f"Unexpected error with OpenAI: {e}", exc_info=True)
                self.openai_breaker.record_failure()
                # Fallback a Ollama

        # Usar Ollama (como fallback o primario)
        if not self.ollama_breaker.is_open():
            try:
                response = await self._generate_ollama(prompt, system_prompt, max_tokens, temperature)
                response.fallback_used = self.openai_client is not None  # True si OpenAI estaba disponible
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

    async def _generate_openai(
        self,
        prompt: str,
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float
    ) -> LLMResponse:
        """Generar usando OpenAI con reintentos exponenciales"""

        for attempt in range(self.max_retries):
            try:
                start_time = time.time()

                # Construir mensajes (el system prompt va como primer mensaje)
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})

                # Llamada a OpenAI
                response = await self.openai_client.chat.completions.create(
                    model=self.openai_model,
                    max_completion_tokens=max_tokens,
                    temperature=temperature,
                    messages=messages
                )

                latency_ms = int((time.time() - start_time) * 1000)

                # Extraer contenido (content puede ser None)
                content = response.choices[0].message.content or ""
                usage = response.usage

                logger.info(
                    f"OpenAI response generated in {latency_ms}ms "
                    f"(input: {usage.prompt_tokens if usage else '?'}, "
                    f"output: {usage.completion_tokens if usage else '?'})"
                )

                return LLMResponse(
                    content=content,
                    provider=LLMProvider.OPENAI,
                    model=self.openai_model,
                    latency_ms=latency_ms,
                    tokens_used=usage.total_tokens if usage else None,
                    fallback_used=False
                )

            except (RateLimitError, APITimeoutError) as e:
                # No reintentar en rate limit o timeout - ir a fallback inmediatamente
                logger.warning(f"OpenAI {type(e).__name__} on attempt {attempt + 1}")
                raise

            except APIError as e:
                if attempt < self.max_retries - 1:
                    # Backoff exponencial: 1s, 2s, 4s
                    wait_time = 2 ** attempt
                    logger.warning(f"OpenAI API error on attempt {attempt + 1}, retrying in {wait_time}s: {e}")
                    await asyncio.sleep(wait_time)
                else:
                    raise

            except Exception as e:
                logger.error(f"Unexpected OpenAI error on attempt {attempt + 1}: {e}")
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
            "openai": {
                "available": self.openai_client is not None,
                "circuit_breaker": self.openai_breaker.state,
                "failures": self.openai_breaker.failures
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
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_base_url=os.getenv("OPENAI_BASE_URL"),
            ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            ollama_model=os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
            max_retries=int(os.getenv("LLM_MAX_RETRIES", "3")),
            timeout_seconds=30,  # OpenAI: siempre 30s (API remota rápida)
            ollama_timeout_seconds=base_timeout  # Ollama: usa LLM_TIMEOUT del .env
        )

    return _llm_client
