import re
import unicodedata
from html.parser import HTMLParser
from urllib import error, request


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)

    def get_text(self) -> str:
        return "\n".join(self.parts)


class GeoNamesService:
    provider_name = "geonames"

    def __init__(self, base_url: str = "https://www.geonames.org/countries") -> None:
        self.base_url = base_url.rstrip("/")

    def get_country_area(
        self,
        country_code: str,
        country_name: str,
        country_slug: str | None = None,
    ) -> dict[str, object]:
        normalized_code = country_code.strip().upper()
        normalized_name = country_name.strip()
        slug = country_slug or self._slugify_country_name(normalized_name)
        url = f"{self.base_url}/{normalized_code}/{slug}.html"
        page_text = self._fetch_page_text(url)
        area_text = self._extract_area_text(page_text)

        return {
            "provider": self.provider_name,
            "country_code": normalized_code,
            "country_name": normalized_name,
            "country_slug": slug,
            "area_km2": self._parse_area_value(area_text),
            "area_text": area_text,
            "source_url": url,
        }

    def _fetch_page_text(self, url: str) -> str:
        headers = {
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "InfoGlobe/0.1 (+https://www.geonames.org/)",
        }
        http_request = request.Request(url, headers=headers, method="GET")

        try:
            with request.urlopen(http_request, timeout=30) as response:
                html = response.read().decode("utf-8", errors="ignore")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(
                f"GeoNames retornou HTTP {exc.code}: {detail or exc.reason}"
            ) from exc
        except error.URLError as exc:
            raise RuntimeError(f"Falha ao conectar com GeoNames: {exc.reason}") from exc

        extractor = _TextExtractor()
        extractor.feed(html)
        return extractor.get_text()

    def _extract_area_text(self, page_text: str) -> str:
        match = re.search(r"area\s*:\s*([0-9,]+(?:\.[0-9]+)?)\s*km²", page_text, re.IGNORECASE)
        if not match:
            raise ValueError("Nao foi possivel localizar o campo de area na pagina do GeoNames.")
        return match.group(1)

    def _parse_area_value(self, area_text: str) -> float:
        return float(area_text.replace(",", ""))

    def _slugify_country_name(self, country_name: str) -> str:
        ascii_name = unicodedata.normalize("NFKD", country_name)
        ascii_name = ascii_name.encode("ascii", "ignore").decode("ascii")
        ascii_name = ascii_name.lower()
        ascii_name = re.sub(r"[^a-z0-9]+", "-", ascii_name)
        return ascii_name.strip("-")
