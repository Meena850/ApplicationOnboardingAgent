import json
import logging
from typing import Any, Dict, Optional

from openai import AzureOpenAI, OpenAIError

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class LLMNotConfiguredError(Exception):
    """Azure OpenAI settings are missing."""


class LLMError(Exception):
    """The model call failed or returned unusable output."""


class AzureOpenAIService:
    """Thin wrapper around Azure OpenAI chat completions that returns parsed JSON."""

    def __init__(self, settings: Optional[Settings] = None, client: Any = None) -> None:
        s = settings or get_settings()
        self.deployment = s.azure_openai_deployment or ""
        if client is None:
            missing = [n for n, v in (("AZURE_OPENAI_ENDPOINT", s.azure_openai_endpoint),
                                      ("AZURE_OPENAI_API_KEY", s.azure_openai_api_key),
                                      ("AZURE_OPENAI_DEPLOYMENT", s.azure_openai_deployment)) if not v]
            if missing:
                raise LLMNotConfiguredError(
                    f"Azure OpenAI is not configured. Set in backend/.env: {', '.join(missing)}")
            client = AzureOpenAI(azure_endpoint=s.azure_openai_endpoint, api_key=s.azure_openai_api_key,
                                 api_version=s.azure_openai_api_version, timeout=s.azure_openai_timeout,
                                 max_retries=2)
        self.client = client

    def complete_json(self, system: str, user: str) -> Dict[str, Any]:
        try:
            resp = self.client.chat.completions.create(
                model=self.deployment,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
        except OpenAIError as exc:
            logger.warning("Azure OpenAI call failed: %s", exc)
            raise LLMError(f"Azure OpenAI request failed: {exc}") from exc
        choice = resp.choices[0]
        if choice.finish_reason == "length":
            raise LLMError("Model output was truncated; reduce the repository context size.")
        try:
            data = json.loads(choice.message.content or "")
        except json.JSONDecodeError as exc:
            raise LLMError("Model did not return valid JSON.") from exc
        if not isinstance(data, dict):
            raise LLMError("Model returned JSON that is not an object.")
        return data
