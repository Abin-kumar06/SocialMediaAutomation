import base64
import os
import logging
from typing import Dict, List, Optional
from openai import AsyncOpenAI
from app.config import settings

logger = logging.getLogger(__name__)

class OpenAICaptionService:
    """Generate platform-specific captions and hashtags using OpenAI (GPT-4o)"""

    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.model = settings.OPENAI_MODEL
        self.client = AsyncOpenAI(api_key=self.api_key) if self.api_key else None

    def _encode_image(self, image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    async def generate_caption(self, platform: str, topic: Optional[str] = None, image_path: Optional[str] = None) -> Dict:
        """Unified method for platform-specific generation with optional image analysis"""
        if not self.client:
            raise ValueError("OpenAI API Key is missing. Please add 'OPENAI_API_KEY' to your .env file and restart the server.")

        platform = platform.lower()
        
        # System prompt for consistent output
        system_prompt = (
            "You are a social media expert. Your task is to write high-quality, engaging captions.\n"
            "Return only the final caption with hashtags at the end.\n"
            "Do not include preamble like 'Here is your caption:'."
        )

        # Build user prompt based on platform and inputs
        user_content = []
        
        platform_rules = {
            "instagram": "Write a fun, engaging Instagram caption. Use emojis. Include exactly 5 relevant hashtags.",
            "linkedin": (
                "Write a professional, viral-style LinkedIn post. Structure: \n"
                "1. A strong opening 'Hook' line to grab attention.\n"
                "2. 2-3 short, insightful paragraphs providing value or context.\n"
                "3. A 'Call-to-Action' at the end.\n"
                "Tone: Visionary, professional, yet readable. Include 4-5 relevant industry hashtags."
            )
        }
        
        rule = platform_rules.get(platform, platform_rules["instagram"])
        
        # Build prompt text
        if topic:
            prompt_text = f"{rule}\n\nTopic/Context: {topic}"
        elif image_path:
            # Vision-first fallback if no prompt provided
            prompt_text = (
                f"{rule}\n\n"
                "Carefully analyze the provided image and write a creative, engaging caption based on what you see. "
                "Describe the scene, mood, and key elements naturally in the caption."
            )
        else:
            prompt_text = f"{rule}"

        if image_path:
            # If prompt exists, remind to include details
            if topic:
                prompt_text += "\n\nAnalyze the provided image and include details from it in the caption to make it more relevant and authentic."
            
            base64_image = self._encode_image(image_path)
            user_content.append({
                "type": "text",
                "text": prompt_text
            })
            user_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}"
                }
            })
        else:
            user_content.append({
                "type": "text",
                "text": prompt_text
            })

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                max_tokens=500
            )
            
            result = response.choices[0].message.content.strip()
            
            # Strip surrounding quotes if present
            if (result.startswith('"') and result.endswith('"')) or \
               (result.startswith("'") and result.endswith("'")):
                result = result[1:-1].strip()

            # Parse hashtags
            import re
            hashtags = re.findall(r"#\w+", result)
            caption = re.split(r"\n\s*#", result)[0].strip()

            return {
                "caption": caption,
                "hashtags": hashtags,
                "full_caption": result,
                "platform": platform
            }
        except Exception as e:
            logger.error(f"OpenAI Generation Error: {str(e)}")
            raise Exception(f"Failed to generate caption with OpenAI: {str(e)}")

    async def generate_multi_captions(self, topic: Optional[str] = None, image_path: Optional[str] = None) -> Dict:
        """Generate tailored captions for all platforms in a single request using JSON mode"""
        if not self.client:
            raise ValueError("OpenAI API Key is missing.")

        system_prompt = (
            "You are a social media expert. Your task is to write high-quality, engaging captions for multiple platforms based on the provided input.\n"
            "You MUST return the results in JSON format with keys: 'instagram', 'linkedin'.\n\n"
            "Rules for each platform:\n"
            "- 'instagram': Fun, engaging, emojis, exactly 5 hashtags.\n"
            "- 'linkedin': Professional, viral-style structure (Hook, 2-3 paragraphs of insights, Call-to-action). 4-5 industry hashtags."
        )

        user_content = []
        prompt_text = "Generate captions for all platforms."
        if topic:
            prompt_text += f"\n\nTopic/Context: {topic}"
        elif image_path:
            prompt_text += "\n\nAnalyze the provided image and generate creative captions based on its visual elements."

        if image_path:
            base64_image = self._encode_image(image_path)
            user_content.append({"type": "text", "text": prompt_text})
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
            })
        else:
            user_content.append({"type": "text", "text": prompt_text})

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                response_format={"type": "json_object"},
                max_tokens=1000
            )
            
            import json
            result = json.loads(response.choices[0].message.content)
            return {
                "instagram": result.get("instagram", ""),
                "linkedin": result.get("linkedin", "")
            }
        except Exception as e:
            logger.error(f"OpenAI Multi-Generation Error: {str(e)}")
            raise Exception(f"Failed to generate multi-platform captions: {str(e)}")

# Singleton instance
openai_service = OpenAICaptionService()
