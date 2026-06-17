import json
from urllib import error, parse, request


class WikipediaService:
    provider_name = "wikipedia"

    def __init__(self, base_url: str = "https://en.wikipedia.org/w/api.php") -> None:
        self.base_url = base_url

    def get_person_image(self, person_name: str) -> dict[str, object]:
        page_title = self._search_page_title(person_name)
        if not page_title:
            raise ValueError(f"No Wikipedia page found for '{person_name}'.")

        image_data = self._fetch_page_image(page_title)
        return {
            "provider": self.provider_name,
            "person_name": person_name,
            "page_title": page_title,
            "image_url": image_data.get("original") or image_data.get("thumbnail"),
            "thumbnail_url": image_data.get("thumbnail"),
            "page_url": f"https://en.wikipedia.org/wiki/{parse.quote(page_title.replace(' ', '_'))}",
        }

    def _search_page_title(self, person_name: str) -> str | None:
        params = {
            "action": "query",
            "list": "search",
            "srsearch": person_name,
            "utf8": "1",
            "format": "json",
            "srlimit": "1",
        }
        payload = self._perform_request(params)
        results = payload.get("query", {}).get("search", [])
        if not isinstance(results, list) or not results:
            return None

        first = results[0]
        if not isinstance(first, dict):
            return None
        title = first.get("title")
        return title if isinstance(title, str) else None

    def _fetch_page_image(self, page_title: str) -> dict[str, str | None]:
        params = {
            "action": "query",
            "prop": "pageimages",
            "titles": page_title,
            "piprop": "original|thumbnail",
            "pithumbsize": "600",
            "format": "json",
        }
        payload = self._perform_request(params)
        pages = payload.get("query", {}).get("pages", {})
        if not isinstance(pages, dict) or not pages:
            return {"original": None, "thumbnail": None}

        first_page = next(iter(pages.values()))
        if not isinstance(first_page, dict):
            return {"original": None, "thumbnail": None}

        original = first_page.get("original")
        thumbnail = first_page.get("thumbnail")
        return {
            "original": self._extract_source(original),
            "thumbnail": self._extract_source(thumbnail),
        }

    def _extract_source(self, payload: object) -> str | None:
        if not isinstance(payload, dict):
            return None
        source = payload.get("source")
        return source if isinstance(source, str) else None

    def _perform_request(self, params: dict[str, str]) -> dict[str, object]:
        query = parse.urlencode(params)
        url = f"{self.base_url}?{query}"
        headers = {
            "Accept": "application/json",
            "User-Agent": "InfoGlobe/0.1 (+https://www.mediawiki.org/)",
        }
        http_request = request.Request(url, headers=headers, method="GET")

        try:
            with request.urlopen(http_request, timeout=60) as response:
                return json.load(response)
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(
                f"Wikipedia returned HTTP {exc.code}: {detail or exc.reason}"
            ) from exc
        except error.URLError as exc:
            raise RuntimeError(f"Failed to connect to Wikipedia: {exc.reason}") from exc
