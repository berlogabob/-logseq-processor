import threading
from typing import Optional

from ollama import chat
from pydantic import ValidationError

from .metadata import ArticleMetadata
from .utils import clean_json
from .common import Config, logger, log_stage


def get_article_metadata(
    extracted_text: str, model: str, is_youtube: bool = False
) -> Optional[ArticleMetadata]:
    prompt = f"""Ты — точный аналитик. Верни ТОЛЬКО JSON без дополнительного текста.

Пример:
{{
  "summary_ru": "Краткое содержание...",
  "tags": ["тег1", "тег2"],
  "author": "Имя автора или null",
  "verification_notes": "Оценка...",
  "step_by_step_guidance": "1. Шаг...\n2. Шаг..."
}}

Текст:
{extracted_text[:8000]}
"""

    if is_youtube:
        prompt += (
            "\nЭто YouTube видео. Обязательно сделай подробное step_by_step_guidance."
        )

    config = Config.get()

    attempts_total = max(1, int(config.max_retries))

    for attempt in range(1, attempts_total + 1):
        temp = (
            config.llm_temperature_attempts[attempt - 1]
            if attempt - 1 < len(config.llm_temperature_attempts)
            else 0.5
        )
        result: list[Optional[ArticleMetadata]] = [None]
        error: list[Optional[str]] = [None]

        def call_llm():
            try:
                resp = chat(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    format="json",
                    options={"temperature": temp},
                    stream=False,
                )
                raw_content = resp["message"]["content"]
                cleaned = clean_json(raw_content)
                result[0] = ArticleMetadata.model_validate_json(cleaned)
            except ValidationError:
                error[0] = "ValidationError: Invalid JSON structure"
            except Exception as e:
                error[0] = f"{type(e).__name__}"

        thread = threading.Thread(target=call_llm, daemon=True)
        thread.start()
        log_stage("LLM", f"attempt {attempt}/{attempts_total} (temp={temp:.2f})")
        thread.join(timeout=config.llm_timeout_seconds)

        if thread.is_alive():
            logger.warning(
                "Attempt %d/%d — TimeoutError: LLM call exceeded %d seconds",
                attempt,
                attempts_total,
                config.llm_timeout_seconds,
            )
            logger.error(
                "LLM timeout detected; aborting retries to avoid stacking stuck calls"
            )
            break

        if error[0]:
            logger.warning("Attempt %d/%d — %s", attempt, attempts_total, error[0])
            continue

        if result[0]:
            logger.info("Successfully extracted metadata with temperature %.2f", temp)
            return result[0]

    logger.error("All LLM attempts failed, using fallback metadata")
    from .metadata import create_fallback_metadata

    return create_fallback_metadata("")
