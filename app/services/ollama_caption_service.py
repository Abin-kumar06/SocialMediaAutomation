import json
import requests
from typing import List, Optional
from fastapi import HTTPException
from app.config import settings

class OllamaCaptionService:
    """Generate platform-specific captions and hashtags using local Ollama (llama3)"""

    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_MODEL
        self.generate_url = f"{self.base_url}/api/generate"

    def _call_ollama(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }
        try:
            response = requests.post(self.generate_url, json=payload, timeout=180)
            response.raise_for_status()
            result = response.json()
            raw = result.get("response", "").strip()
            # Strip surrounding quotes that LLMs sometimes add
            if (raw.startswith('"') and raw.endswith('"')) or \
               (raw.startswith("'") and raw.endswith("'")):
                raw = raw[1:-1].strip()
            return raw
        except requests.exceptions.RequestException as e:
            raise HTTPException(
                status_code=503,
                detail=f"Ollama service error: {str(e)}. Ensure Ollama is running and {self.model} is installed."
            )

    def generate_instagram(self, topic: str) -> str:
        prompt = (
            f"Write a fun, engaging Instagram caption about {topic}.\n"
            "Use an informal tone.\n"
            "Include exactly 5 relevant hashtags."
        )
        return self._call_ollama(prompt)

    def generate_linkedin(self, topic: str) -> str:
        prompt = (
            f"Write a professional LinkedIn post about {topic}.\n"
            "Use a formal, insightful tone.\n"
            "Include 4–5 professional hashtags."
        )
        return self._call_ollama(prompt)

    def generate_x(self, topic: str) -> str:
        prompt = (
            f"Write a concise, catchy X (Twitter) post about {topic}.\n"
            "Limit to 280 characters.\n"
            "Include 2–3 hashtags."
        )
        return self._call_ollama(prompt)

    def generate_caption(self, platform: str, topic: str) -> dict:
        """Unified method for platform-specific generation"""
        platform = platform.lower()
        if platform == "instagram":
            result = self.generate_instagram(topic)
        elif platform == "linkedin":
            result = self.generate_linkedin(topic)
        elif platform in ["x", "twitter"]:
            result = self.generate_x(topic)
        else:
            # Default to Instagram rules if platform is unknown
            result = self.generate_instagram(topic)

        # Basic parsing of hashtags if needed for API compatibility
        import re
        hashtags = re.findall(r"#\w+", result)
        caption = re.split(r"\n\s*#", result)[0].strip()

        return {
            "caption": caption,
            "hashtags": hashtags,
            "full_caption": result,
            "platform": platform
        }
