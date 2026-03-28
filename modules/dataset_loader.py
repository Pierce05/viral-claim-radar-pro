"""Dataset loading and summary helpers."""

from __future__ import annotations

import os
from collections import Counter
from functools import lru_cache

from modules.utils import clean_sentence, ensure_label, get_project_root, safe_load_json

DATASET_PATH = os.path.join(get_project_root(), "data", "claims_dataset.json")

SAMPLE_DATASET = [
    {
        "claim": "The Great Wall of China is visible from space with the naked eye.",
        "label": "Refuted",
        "explanation": "Astronauts have repeatedly explained that it is not uniquely visible without aid.",
        "source": "NASA astronaut guidance",
        "topic": "Space & Astronomy",
        "keywords": ["great wall", "space", "astronaut"],
    },
    {
        "claim": "Climate change is primarily driven by human activities such as burning fossil fuels.",
        "label": "Supported",
        "explanation": "Major scientific bodies attribute recent warming mainly to human greenhouse gas emissions.",
        "source": "IPCC consensus summary",
        "topic": "Climate & Environment",
        "keywords": ["climate", "emissions", "fossil fuels"],
    },
    {
        "claim": "Vaccines cause autism in children.",
        "label": "Refuted",
        "explanation": "Large studies have found no causal link between vaccines and autism.",
        "source": "CDC and peer-reviewed studies",
        "topic": "Health & Medicine",
        "keywords": ["vaccines", "autism", "children"],
    },
    {
        "claim": "mRNA vaccines change a person's DNA.",
        "label": "Refuted",
        "explanation": "mRNA does not enter the nucleus to alter human DNA.",
        "source": "WHO vaccine explainer",
        "topic": "Health & Medicine",
        "keywords": ["mrna", "dna", "vaccine"],
    },
    {
        "claim": "Drinking water helps support healthy hydration and body function.",
        "label": "Supported",
        "explanation": "Hydration is essential for normal physiological processes.",
        "source": "General medical guidance",
        "topic": "Health & Medicine",
        "keywords": ["water", "hydration", "health"],
    },
    {
        "claim": "5G mobile networks spread COVID-19.",
        "label": "Refuted",
        "explanation": "Viruses are biological and cannot be transmitted by radio waves.",
        "source": "WHO mythbuster",
        "topic": "Technology & AI",
        "keywords": ["5g", "covid", "virus"],
    },
    {
        "claim": "The Moon landing was staged in a film studio.",
        "label": "Refuted",
        "explanation": "Apollo missions are supported by physical evidence and independent observations.",
        "source": "NASA historical record",
        "topic": "Space & Astronomy",
        "keywords": ["moon landing", "apollo", "staged"],
    },
    {
        "claim": "Renewable energy capacity has grown rapidly in recent years.",
        "label": "Supported",
        "explanation": "Solar and wind deployment trends show sustained growth globally.",
        "source": "Energy market reporting",
        "topic": "Climate & Environment",
        "keywords": ["renewable", "solar", "wind"],
    },
    {
        "claim": "Artificial intelligence can generate convincing deepfake videos.",
        "label": "Supported",
        "explanation": "Generative models can synthesize realistic audio and video content.",
        "source": "AI safety literature",
        "topic": "Technology & AI",
        "keywords": ["ai", "deepfake", "video"],
    },
    {
        "claim": "Bitcoin is controlled by a single central bank.",
        "label": "Refuted",
        "explanation": "Bitcoin operates on a decentralized network rather than a central bank.",
        "source": "Blockchain protocol overview",
        "topic": "Economy & Finance",
        "keywords": ["bitcoin", "central bank", "crypto"],
    },
    {
        "claim": "Exercise can improve cardiovascular health.",
        "label": "Supported",
        "explanation": "Regular physical activity is linked to better heart health outcomes.",
        "source": "Public health guidance",
        "topic": "Health & Medicine",
        "keywords": ["exercise", "heart", "health"],
    },
    {
        "claim": "A miracle supplement cures every cancer with 100 percent success.",
        "label": "Refuted",
        "explanation": "Extraordinary cure-all claims without rigorous evidence are not credible.",
        "source": "Oncology evidence standards",
        "topic": "Health & Medicine",
        "keywords": ["miracle", "supplement", "cancer"],
    },
]


def _sanitize_record(item: dict) -> dict:
    claim = clean_sentence(item.get("claim"))
    if not claim:
        return {}
    label = ensure_label(item.get("label"))
    explanation = clean_sentence(item.get("explanation")) or "No explanation available."
    source = clean_sentence(item.get("source")) or "Local knowledge base"
    topic = clean_sentence(item.get("topic")) or "General"
    keywords = item.get("keywords") if isinstance(item.get("keywords"), list) else []
    return {
        "claim": claim,
        "label": label,
        "explanation": explanation,
        "source": source,
        "topic": topic,
        "keywords": [clean_sentence(keyword).lower() for keyword in keywords if clean_sentence(keyword)],
    }


@lru_cache(maxsize=1)
def load_claims_dataset() -> list[dict]:
    raw = safe_load_json(DATASET_PATH, default=SAMPLE_DATASET)
    if not isinstance(raw, list):
        raw = SAMPLE_DATASET
    dataset = [_sanitize_record(item) for item in raw if isinstance(item, dict)]
    dataset = [item for item in dataset if item]
    return dataset or [_sanitize_record(item) for item in SAMPLE_DATASET]


def get_dataset_stats(dataset: list[dict] | None = None) -> dict:
    records = dataset or load_claims_dataset()
    counter = Counter(record.get("label", "Uncertain") for record in records)
    categories = sorted({record.get("topic", "General") for record in records})
    return {
        "total": len(records),
        "supported": counter.get("Supported", 0),
        "refuted": counter.get("Refuted", 0),
        "uncertain": counter.get("Uncertain", 0),
        "categories": categories,
    }
