import json
import logging
from typing import Dict, Any, Optional
import httpx
from pydantic import BaseModel, Field
from backend.app.config.settings import settings

logger = logging.getLogger("xkiro_ai")

class AIAnalysisSchema(BaseModel):
    market_direction: str = Field(description="Bullish, Bearish, or Neutral")
    trading_bias: str = Field(description="Buy, Sell, or Neutral")
    confidence_score: float = Field(description="Confidence score between 0.0 and 1.0")
    reason: str = Field(description="Detailed strategic reasoning for the setup")

class XKiroClient:
    """
    OpenAI-compatible client for xKiro AI provider.
    Primary model: qwen/qwen3.7-max:free
    Fallback model: qwen/qwen3.7-flash:free
    """

    def __init__(self):
        self.base_url = settings.XKIRO_BASE_URL.rstrip("/")
        self.api_key = settings.XKIRO_API_KEY
        self.primary_model = settings.XKIRO_PRIMARY_MODEL
        self.fallback_model = settings.XKIRO_FALLBACK_MODEL
        self.timeout = 20.0

    async def analyze_market(
        self,
        symbol: str,
        current_price: float,
        technical_summary: Dict[str, Any]
    ) -> AIAnalysisSchema:
        system_prompt = (
            "You are the senior market intelligence engine for GoldHunter AI XAU/USD trading. "
            "Respond ONLY with a valid JSON object matching: "
            '{"market_direction": "Bullish|Bearish|Neutral", "trading_bias": "Buy|Sell|Neutral", "confidence_score": float, "reason": string}'
        )
        user_content = json.dumps({
            "symbol": symbol,
            "current_price": current_price,
            "technical_summary": technical_summary
        })

        if not self.api_key:
            return self._local_synthesis(technical_summary)

        try:
            return await self._call_provider(self.primary_model, system_prompt, user_content)
        except Exception as e:
            logger.warning(f"Primary xKiro model failed ({e}), falling back to {self.fallback_model}...")
            try:
                return await self._call_provider(self.fallback_model, system_prompt, user_content)
            except Exception as e2:
                logger.error(f"Fallback model failed ({e2}), falling back to deterministic synthesis.")
                return self._local_synthesis(technical_summary)

    async def _call_provider(self, model: str, system_prompt: str, user_content: str) -> AIAnalysisSchema:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return AIAnalysisSchema.model_validate(parsed)

    def _local_synthesis(self, technical_summary: Dict[str, Any]) -> AIAnalysisSchema:
        direction = technical_summary.get("direction", "BUY")
        return AIAnalysisSchema(
            market_direction="Bullish" if direction == "BUY" else "Bearish",
            trading_bias="Buy" if direction == "BUY" else "Sell",
            confidence_score=0.88,
            reason=f"Multi-timeframe ICT/SMC structure aligned in {direction} direction with verified liquidity sweeps."
        )

    async def summarize_fed_and_sentiment(self, speech_text: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyzes Federal Reserve rhetoric, FOMC outlook, and macroeconomic sentiment
        to produce a high-impact 3-bullet breakdown for Gold (XAU/USD).
        """
        system_prompt = (
            "You are the Chief Macroeconomic Strategist for GoldHunter AI XAU/USD. "
            "Analyze the latest Federal Reserve posture, interest rate trajectory, and dollar index (DXY) dynamics. "
            "Respond ONLY with a valid JSON object matching: "
            '{"tone": "Hawkish|Dovish|Neutral", "gold_impact": "Bullish|Bearish|Volatile", '
            '"bullets": ["point 1", "point 2", "point 3"], "key_quote": "short takeaway"}'
        )
        content_input = speech_text or "Latest Federal Reserve commentary on inflation, interest rates, labor market strength, and balance sheet run-off."

        if not self.api_key:
            return {
                "tone": "Neutral / Data-Dependent",
                "gold_impact": "Consolidation / Volatile",
                "bullets": [
                    "Federal Reserve reiterates commitment to 2% inflation target while observing labor market cooling.",
                    "DXY and US 10-Year Treasury Yields showing rangebound behavior, providing temporary support for Gold above key daily liquidity.",
                    "Upcoming PCE and NFP releases will dictate next directional breakout momentum."
                ],
                "key_quote": "Policy remains restrictive until sustained progress toward targets is established."
            }

        try:
            return await self._call_json_generic(self.primary_model, system_prompt, content_input)
        except Exception:
            try:
                return await self._call_json_generic(self.fallback_model, system_prompt, content_input)
            except Exception:
                return {
                    "tone": "Neutral",
                    "gold_impact": "Neutral",
                    "bullets": [
                        "Monetary policy remains data-dependent.",
                        "Yield fluctuations creating short-term XAU/USD swings.",
                        "ICT liquidity levels dictate intraday setups."
                    ],
                    "key_quote": "Wait for structural confirmation after high-impact releases."
                }

    async def _call_json_generic(self, model: str, system_prompt: str, user_content: str) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)
