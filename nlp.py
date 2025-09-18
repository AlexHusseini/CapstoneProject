from collections import Counter
import re
from typing import List, Dict

# Simple keyword-based red-flag detector
RED_FLAG_KEYWORDS = [
    "harass", "threat", "unsafe", "violence", "abuse", "bully",
    "discrim", "cheat", "plagiar", "drugs", "weapon", "suicide",
    "self-harm", "assault", "racist", "sexist", "hate", "stalker",
]

def detect_red_flags(text: str) -> List[str]:
    if not text:
        return []
    t = text.lower()
    found = sorted({k for k in RED_FLAG_KEYWORDS if k in t})
    return found

def simple_summarize(texts: List[str], max_sentences: int = 3) -> str:
    # Frequency-based extractive summarizer (very basic)
    full_text = " ".join(texts)
    sentences = re.split(r"(?<=[.!?])\s+", full_text)
    if len(sentences) <= max_sentences:
        return full_text.strip()
    words = re.findall(r"[a-zA-Z']+", full_text.lower())
    freq = Counter(words)
    scored = [(sum(freq.get(w,0) for w in re.findall(r"[a-zA-Z']+", s.lower())), s) for s in sentences]
    top = [s for _, s in sorted(scored, reverse=True)[:max_sentences]]
    return " ".join(top).strip()

# Optional: OpenAI-powered improvements (used only if OPENAI_API_KEY provided)
def openai_summarize(api_key: str, texts: List[str]) -> str:
    try:
        import openai  # type: ignore
        openai.api_key = api_key
        joined = "\n".join(texts)
        # Using Chat Completions for compatibility
        resp = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role":"system","content":"Summarize peer feedback succinctly in 3 bullet points."},
                {"role":"user","content": joined}
            ],
            temperature=0.2,
            max_tokens=200
        )
        return resp.choices[0].message["content"].strip()
    except Exception as e:
        return simple_summarize(texts)
