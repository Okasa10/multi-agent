"""
AI Recruiter Assistant - LLM Client Helper
Provides a clean, unified interface to invoke LLMs (Groq, OpenAI, or Gemini)
via standard HTTP requests, with seamless fallback to deterministic mock agents.
"""

import os
import json
import logging
import requests
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class LLMClient:
    """Lightweight HTTP-based LLM caller with zero external SDK dependencies."""

    def __init__(self):
        self.groq_api_key = os.getenv("GROQ_API_KEY", "").strip()
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")

    def is_configured(self) -> bool:
        """Returns True if any supported LLM provider API key is present."""
        return bool(self.groq_api_key or self.openai_api_key or self.gemini_api_key)

    def get_active_provider(self) -> str:
        """Returns the name of the active LLM provider, or 'none'."""
        if self.groq_api_key:
            return "Groq"
        if self.openai_api_key:
            return "OpenAI"
        if self.gemini_api_key:
            return "Gemini"
        return "none"

    def generate_json(self, system_prompt: str, user_prompt: str, timeout: int = 15) -> Optional[Dict[str, Any]]:
        """
        Sends request to configured LLM expecting JSON output.
        Returns parsed dictionary if successful, or None to trigger deterministic fallback.
        """
        if not self.is_configured():
            return None

        # Try Groq first if available (fast and free tier available)
        if self.groq_api_key:
            try:
                headers = {
                    "Authorization": f"Bearer {self.groq_api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
                    "messages": [
                        {"role": "system", "content": system_prompt + "\nRespond strictly in valid JSON format."},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"}
                }
                resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=timeout)
                if resp.status_code == 200:
                    content = resp.json()["choices"][0]["message"]["content"]
                    return json.loads(content)
                else:
                    logger.warning(f"Groq API error ({resp.status_code}): {resp.text}")
            except Exception as e:
                logger.warning(f"Groq LLM call failed: {e}")

        # Try OpenAI
        if self.openai_api_key:
            try:
                headers = {
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                    "messages": [
                        {"role": "system", "content": system_prompt + "\nRespond strictly in valid JSON format."},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"}
                }
                resp = requests.post(f"{self.openai_base_url}/chat/completions", headers=headers, json=payload, timeout=timeout)
                if resp.status_code == 200:
                    content = resp.json()["choices"][0]["message"]["content"]
                    return json.loads(content)
                else:
                    logger.warning(f"OpenAI API error ({resp.status_code}): {resp.text}")
            except Exception as e:
                logger.warning(f"OpenAI LLM call failed: {e}")

        # Try Gemini
        if self.gemini_api_key:
            try:
                model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.gemini_api_key}"
                headers = {"Content-Type": "application/json"}
                prompt_text = f"{system_prompt}\n\nStrictly output valid JSON only.\n\nInput:\n{user_prompt}"
                payload = {
                    "contents": [{"parts": [{"text": prompt_text}]}],
                    "generationConfig": {"response_mime_type": "application/json"}
                }
                resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
                if resp.status_code == 200:
                    raw_text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                    return json.loads(raw_text)
                else:
                    logger.warning(f"Gemini API error ({resp.status_code}): {resp.text}")
            except Exception as e:
                logger.warning(f"Gemini LLM call failed: {e}")

        return None
