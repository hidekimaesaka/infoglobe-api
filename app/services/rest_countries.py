import json
import re
import unicodedata
from urllib import error, parse, request


class RestCountriesRequestError(RuntimeError):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


class RestCountriesService:
    provider_name = "restcountries"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.restcountries.com/countries/v5",
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def get_country(self, country_name: str) -> dict[str, object]:
        country = self.get_country_record(country_name)
        return self.build_country_summary(country, fallback_name=country_name)

    def get_country_bundle(self, country_name: str) -> dict[str, object]:
        country = self.get_country_record(country_name)
        return {
            "data": self.build_country_summary(country, fallback_name=country_name),
            "metadata": {
                "country_name": self._read_field(country, "names.common") or country_name,
                "country_code": self._read_field(country, "codes.alpha_2"),
                "country_aliases": self._extract_candidate_names(country),
            },
        }

    def get_country_record(self, country_name: str) -> dict[str, object]:
        return self._fetch_country(country_name)

    def build_country_summary(
        self,
        country: dict[str, object],
        fallback_name: str,
    ) -> dict[str, object]:
        flag = self._read_field(country, "flag.url_svg")
        if not flag:
            flag = self._read_field(country, "flag.url_png")
        if not flag:
            flag = self._read_field(country, "flag.emoji")

        capitals = self._format_capitals(self._read_field(country, "capitals"))
        languages = self._format_languages(self._read_field(country, "languages"))
        currencies = self._format_currencies(self._read_field(country, "currencies"))
        population = self._read_field(country, "population")
        borders = self._read_field(country, "borders") or []
        common_name = self._read_field(country, "names.common") or fallback_name

        return {
            "pais": common_name,
            "bandeira": flag,
            "capital": capitals,
            "idiomas": languages,
            "moedas": currencies,
            "populacao": population,
            "fronteiras": borders,
        }

    def _fetch_country(self, country_name: str) -> dict[str, object]:
        country = self._fetch_country_exact(country_name)
        if country is not None:
            return country

        country = self._search_country_candidates(country_name)
        if country is not None:
            return country

        raise ValueError(f"Nenhum pais encontrado para '{country_name}'.")

    def _fetch_country_exact(self, country_name: str) -> dict[str, object] | None:
        encoded_country = parse.quote(country_name.strip(), safe="")
        base_request_url = f"{self.base_url}/names.common/{encoded_country}"
        try:
            payload = self._perform_api_request(base_request_url)
        except RestCountriesRequestError as exc:
            if exc.status_code == 404:
                return None
            raise

        objects = self._extract_objects(payload)
        return objects[0] if objects else None

    def _search_country_candidates(self, country_name: str) -> dict[str, object] | None:
        encoded_country = parse.quote(country_name.strip(), safe="")
        candidate_urls = [
            f"{self.base_url}/names.translations?q={encoded_country}",
            f"{self.base_url}/name?q={encoded_country}",
            f"{self.base_url}?q={encoded_country}",
        ]

        candidates: list[dict[str, object]] = []
        seen_codes: set[str] = set()
        for url in candidate_urls:
            try:
                payload = self._perform_api_request(url)
            except RestCountriesRequestError as exc:
                if exc.status_code in {400, 404}:
                    continue
                raise

            for country in self._extract_objects(payload):
                country_code = self._read_field(country, "codes.alpha_2")
                dedupe_key = str(country_code or self._read_field(country, "names.common") or "")
                if dedupe_key and dedupe_key in seen_codes:
                    continue
                if dedupe_key:
                    seen_codes.add(dedupe_key)
                candidates.append(country)

        if not candidates:
            return None

        return self._select_best_country_match(country_name, candidates)

    def _perform_api_request(self, url: str) -> dict[str, object]:
        auth_variants = [
            (url, {"Authorization": f"Bearer {self.api_key}"}),
            (url, {"Authorization": self.api_key}),
            (
                self._append_api_key_query(url),
                {},
            ),
        ]

        payload = None
        last_error = None
        for candidate_url, headers in auth_variants:
            try:
                payload = self._perform_request(candidate_url, headers)
                break
            except RestCountriesRequestError as exc:
                last_error = exc
                if exc.status_code in {401, 403}:
                    continue
                if exc.status_code == 404:
                    raise
            except RuntimeError as exc:
                last_error = exc

        if payload is None:
            raise last_error or RuntimeError("Falha ao consultar a API REST Countries.")

        return payload

    def _append_api_key_query(self, url: str) -> str:
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}{parse.urlencode({'api-key': self.api_key})}"

    def _extract_objects(self, payload: dict[str, object]) -> list[dict[str, object]]:
        if "errors" in payload:
            message = payload["errors"][0].get("message", "Erro desconhecido na API.")
            raise RuntimeError(message)
        objects = payload.get("data", {}).get("objects", [])
        return [country for country in objects if isinstance(country, dict)]

    def _select_best_country_match(
        self,
        country_name: str,
        candidates: list[dict[str, object]],
    ) -> dict[str, object] | None:
        normalized_input = self._normalize_text(country_name)
        ranked = sorted(
            candidates,
            key=lambda candidate: self._candidate_score(normalized_input, candidate),
            reverse=True,
        )
        if not ranked:
            return None

        best_candidate = ranked[0]
        best_score = self._candidate_score(normalized_input, best_candidate)
        return best_candidate if best_score > 0 else None

    def _candidate_score(self, normalized_input: str, candidate: dict[str, object]) -> int:
        best_score = 0
        for candidate_name in self._extract_candidate_names(candidate):
            normalized_candidate = self._normalize_text(candidate_name)
            if not normalized_candidate:
                continue
            if normalized_candidate == normalized_input:
                return 10_000 + len(normalized_candidate)
            if normalized_input in normalized_candidate:
                best_score = max(best_score, 5_000 + len(normalized_input))
            if normalized_candidate in normalized_input:
                best_score = max(best_score, 4_000 + len(normalized_candidate))

            input_tokens = set(normalized_input.split())
            candidate_tokens = set(normalized_candidate.split())
            overlap = len(input_tokens & candidate_tokens)
            if overlap:
                best_score = max(best_score, overlap * 100 + len(candidate_tokens & input_tokens))
        return best_score

    def _extract_candidate_names(self, candidate: dict[str, object]) -> list[str]:
        names: list[str] = []

        for field_name in ("names.common", "names.official"):
            value = self._read_field(candidate, field_name)
            if isinstance(value, str):
                names.append(value)

        alternates = self._read_field(candidate, "names.alternates")
        if isinstance(alternates, list):
            names.extend(str(value) for value in alternates if isinstance(value, str))

        for field_name in ("names.native", "names.translations"):
            localized_names = self._read_field(candidate, field_name)
            if not isinstance(localized_names, dict):
                continue
            for name_data in localized_names.values():
                if not isinstance(name_data, dict):
                    continue
                for key in ("common", "official"):
                    value = name_data.get(key)
                    if isinstance(value, str):
                        names.append(value)

        return names

    def _normalize_text(self, value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value)
        normalized = normalized.encode("ascii", "ignore").decode("ascii")
        normalized = normalized.lower()
        normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
        return " ".join(normalized.split())

    def normalize_country_name(self, value: str) -> str:
        return self._normalize_text(value)

    def _perform_request(self, url: str, headers: dict[str, str]) -> dict[str, object]:
        request_headers = {
            "Accept": "application/json",
            "User-Agent": "InfoGlobe/0.1 (+https://restcountries.com/docs)",
            **headers,
        }
        http_request = request.Request(url, headers=request_headers, method="GET")

        try:
            with request.urlopen(http_request, timeout=30) as response:
                return json.load(response)
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RestCountriesRequestError(
                exc.code,
                f"REST Countries retornou HTTP {exc.code}: {detail or exc.reason}"
            ) from exc
        except error.URLError as exc:
            raise RuntimeError(f"Falha ao conectar com REST Countries: {exc.reason}") from exc

    def _read_field(self, payload: object, field_path: str) -> object:
        if not isinstance(payload, dict):
            return None
        if field_path in payload:
            return payload[field_path]

        current = payload
        for part in field_path.split("."):
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
        return current

    def _format_capitals(self, capitals: object) -> list[str]:
        if not isinstance(capitals, list):
            return []
        values = []
        for capital in capitals:
            if isinstance(capital, dict):
                name = capital.get("name")
                if name:
                    values.append(name)
            elif isinstance(capital, str):
                values.append(capital)
        return values

    def _format_languages(self, languages: object) -> list[str]:
        if isinstance(languages, dict):
            return [str(value) for value in languages.values()]
        if not isinstance(languages, list):
            return []

        values = []
        for language in languages:
            if isinstance(language, dict):
                name = language.get("name") or language.get("english_name")
                native_name = language.get("native_name")
                if name and native_name and native_name != name:
                    values.append(f"{name} ({native_name})")
                elif name:
                    values.append(name)
            elif isinstance(language, str):
                values.append(language)
        return values

    def _format_currencies(self, currencies: object) -> list[dict[str, str | None]]:
        if isinstance(currencies, list):
            values = []
            for currency in currencies:
                if isinstance(currency, dict):
                    values.append(
                        {
                            "codigo": currency.get("code"),
                            "nome": currency.get("name"),
                            "simbolo": currency.get("symbol"),
                        }
                    )
            return values

        if not isinstance(currencies, dict):
            return []

        values = []
        for code, data in currencies.items():
            if isinstance(data, dict):
                values.append(
                    {
                        "codigo": str(code),
                        "nome": data.get("name"),
                        "simbolo": data.get("symbol"),
                    }
                )
            else:
                values.append(
                    {
                        "codigo": str(code),
                        "nome": str(data),
                        "simbolo": None,
                    }
                )
        return values
