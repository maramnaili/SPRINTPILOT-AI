from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    OpenAI,
)

from sprintpilot.config import create_llm_client, settings
from sprintpilot.models import ProjectAnalysis, ProjectBrief


SYSTEM_PROMPT = (
    "You analyze software project briefs. "
    "Extract a concise summary, goals, features, constraints, risks, assumptions, "
    "ambiguities and clarification questions. "
    "State missing information as ambiguities or assumptions. "
    "Do not invent requirements that are not supported by the brief."
)


def analyze_project_brief(
    brief: ProjectBrief,
    *,
    client: OpenAI | None = None,
) -> ProjectAnalysis:
    """Analyze a project brief into a validated ProjectAnalysis."""

    if client is None:
        client = create_llm_client()

    brief_json = brief.model_dump_json()

    try:
        completion = client.chat.completions.parse(
            model=settings.ollama_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": brief_json},
            ],
            response_format=ProjectAnalysis,
            max_tokens=1400,
        )
    except APITimeoutError as exc:
        raise RuntimeError(
            "The Ollama request timed out. Increase OLLAMA_TIMEOUT_SECONDS "
            "or use a faster local model."
        ) from exc
    except APIConnectionError as exc:
        raise RuntimeError(
            "Could not connect to Ollama. Make sure Ollama is running locally."
        ) from exc
    except APIStatusError as exc:
        raise RuntimeError(
            f"The local LLM service returned an HTTP {exc.status_code} status."
        ) from exc

    if not completion.choices:
        raise RuntimeError("The OpenAI response did not contain any choices.")

    result = completion.choices[0].message.parsed
    if result is None:
        raise RuntimeError("The OpenAI response did not contain a parsed ProjectAnalysis.")

    return result
