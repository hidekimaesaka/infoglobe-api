import json
from urllib import error, request


class OpenRouterService:
    provider_name = "openrouter"
    free_models = [
        "nex-agi/nex-n2-pro:free",
        "nvidia/nemotron-3-ultra-550b-a55b:free",
    ]

    def __init__(
        self,
        api_key: str,
        model: str | None = None,
        base_url: str = "https://openrouter.ai/api/v1/chat/completions",
    ) -> None:
        self.api_key = api_key
        self.model = self._resolve_model(model)
        self.base_url = base_url

    def generate_country_summary(self, country_name: str) -> dict[str, object]:
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an assistant that replies only with valid JSON. "
                        "Do not use markdown. Do not use code fences. "
                        "All textual content must be written in English."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Create a short summary about the country {country_name}. "
                        "Return JSON with the exact keys: "
                        "country_name, presidente_atual, personalidades, cultura, empresas, tipo_de_governo. "
                        "Use presidente_atual for the current president, or the closest current executive national leader when the country does not use the title president. "
                        "Use country_name as a string in English, personalidades as a list of 3 strings, "
                        "cultura as a short string in English, empresas as a list of 3 company names, "
                        "and tipo_de_governo as a short string in English. "
                        "If there is ambiguity, choose the most widely known country. "
                        "Every textual field must be in English."
                    ),
                },
            ],
            "temperature": 0.2,
        }
        response_payload = self._perform_request_with_model(payload)
        message_content = self._extract_message_content(response_payload)
        parsed_content = self._parse_json_content(message_content)
        parsed_content["provider"] = self.provider_name
        parsed_content["model"] = response_payload.get("model", self.model)
        return parsed_content

    def _resolve_model(self, model: str | None) -> str:
        if model and ":free" in model:
            return model
        return self.free_models[0]

    def _perform_request_with_model(self, payload: dict[str, object]) -> dict[str, object]:
        last_error = None
        for model in self._candidate_models():
            try:
                request_payload = dict(payload)
                request_payload["model"] = model
                return self._perform_request(request_payload)
            except RuntimeError as exc:
                last_error = exc
        raise last_error or RuntimeError("Falha ao consultar o OpenRouter.")

    def _candidate_models(self) -> list[str]:
        if self.model in self.free_models:
            return [self.model, *[model for model in self.free_models if model != self.model]]
        return list(self.free_models)

    def _perform_request(self, payload: dict[str, object]) -> dict[str, object]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost",
            "X-Title": "InfoGlobe",
        }
        body = json.dumps(payload).encode("utf-8")
        http_request = request.Request(
            self.base_url,
            data=body,
            headers=headers,
            method="POST",
        )

        try:
            with request.urlopen(http_request, timeout=60) as response:
                return json.load(response)
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(
                f"OpenRouter retornou HTTP {exc.code}: {detail or exc.reason}"
            ) from exc
        except error.URLError as exc:
            raise RuntimeError(f"Falha ao conectar com OpenRouter: {exc.reason}") from exc

    def _extract_message_content(self, payload: dict[str, object]) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("Resposta invalida do OpenRouter: choices ausente.")

        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise RuntimeError("Resposta invalida do OpenRouter: message ausente.")

        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text = item.get("text")
                    if isinstance(text, str):
                        text_parts.append(text)
            if text_parts:
                return "\n".join(text_parts)

        raise RuntimeError("Resposta invalida do OpenRouter: content ausente.")

    def _parse_json_content(self, content: str) -> dict[str, object]:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines:
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"OpenRouter retornou conteudo fora do JSON esperado: {content}"
            ) from exc

        if not isinstance(data, dict):
            raise RuntimeError("OpenRouter retornou JSON em formato inesperado.")
        return data
