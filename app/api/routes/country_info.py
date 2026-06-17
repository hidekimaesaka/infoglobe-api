from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.schemas.country import CountryInfoRequest, CountryInfoResponse
from app.services.geonames import GeoNamesService
from app.services.mongodb import MongoCountryCacheService
from app.services.openrouter import OpenRouterService
from app.services.rest_countries import RestCountriesService
from app.services.wikipedia import WikipediaService


router = APIRouter(tags=["country-info"])


@router.post("/country-info", response_model=CountryInfoResponse)
def get_country_info(payload: CountryInfoRequest) -> CountryInfoResponse:
    if not settings.mongo_db_url_conn:
        raise HTTPException(
            status_code=500,
            detail="MONGO_DB_URL_CONN nao configurada.",
        )
    if not settings.rest_countries_api_key:
        raise HTTPException(
            status_code=500,
            detail="API_KEY_REST_COUNTRIES nao configurada.",
        )
    if not settings.openrouter_api_key:
        raise HTTPException(
            status_code=500,
            detail="API_KEY_OPENROUTER nao configurada.",
        )

    rest_countries_service = RestCountriesService(
        api_key=settings.rest_countries_api_key
    )
    cache_service = MongoCountryCacheService(
        uri=settings.mongo_db_url_conn,
        database_name=settings.mongo_db_name,
        collection_name=settings.mongo_country_collection,
    )
    geonames_service = GeoNamesService()
    openrouter_service = OpenRouterService(
        api_key=settings.openrouter_api_key,
        model=settings.openrouter_model or None,
    )
    wikipedia_service = WikipediaService()
    lookup_key = rest_countries_service.normalize_country_name(payload.country_name)
    cached_response = None
    stale_cached_response = None

    try:
        cache_entry = cache_service.get_country_cache_entry(lookup_key)
        if cache_entry:
            cached_response = cache_entry.get("response")
            if cache_entry.get("is_stale"):
                stale_cached_response = cached_response
                cached_response = None
    except RuntimeError:
        cache_entry = None
    except Exception:
        cache_entry = None

    if cached_response:
        return CountryInfoResponse(**cached_response)

    try:
        country_bundle = rest_countries_service.get_country_bundle(payload.country_name)
        country_data = country_bundle["data"]
        metadata = country_bundle["metadata"]
        area_data = geonames_service.get_country_area(
            country_code=str(metadata["country_code"]),
            country_name=str(metadata["country_name"]),
        )
        ai_data = openrouter_service.generate_country_summary(
            str(metadata["country_name"])
        )
    except ValueError as exc:
        if stale_cached_response:
            return CountryInfoResponse(**stale_cached_response)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        if stale_cached_response:
            return CountryInfoResponse(**stale_cached_response)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    presidente_atual = _ensure_optional_string(ai_data.get("presidente_atual"))
    imagem_presidente = ""
    if presidente_atual:
        try:
            wikipedia_data = wikipedia_service.get_person_image(presidente_atual)
            imagem_presidente = _ensure_non_empty_string(
                wikipedia_data.get("image_url")
            )
        except (RuntimeError, ValueError):
            imagem_presidente = ""

    response = CountryInfoResponse(
        **country_data,
        area=area_data["area_km2"],
        presidente_atual=presidente_atual,
        imagem_presidente=imagem_presidente,
        personalidades=_ensure_string_list(ai_data.get("personalidades")),
        cultura=_ensure_optional_string(ai_data.get("cultura")),
        empresas=_ensure_string_list(ai_data.get("empresas")),
        tipo_de_governo=_ensure_optional_string(ai_data.get("tipo_de_governo")),
    )
    lookup_keys = _build_lookup_keys(
        rest_countries_service,
        payload.country_name,
        metadata.get("country_aliases"),
    )
    try:
        cache_service.save_country_info(
            country_code=_ensure_optional_string(metadata.get("country_code")),
            country_name=_ensure_optional_string(metadata.get("country_name")) or response.pais,
            lookup_keys=lookup_keys,
            response=_model_dump(response),
        )
    except Exception:
        pass

    return response


def _ensure_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def _ensure_optional_string(value: object) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _ensure_non_empty_string(value: object) -> str:
    if isinstance(value, str):
        return value
    return ""


def _build_lookup_keys(
    rest_countries_service: RestCountriesService,
    requested_name: str,
    aliases: object,
) -> list[str]:
    keys = {rest_countries_service.normalize_country_name(requested_name)}
    if isinstance(aliases, list):
        for alias in aliases:
            if isinstance(alias, str):
                keys.add(rest_countries_service.normalize_country_name(alias))
    return sorted(key for key in keys if key)


def _model_dump(response: CountryInfoResponse) -> dict[str, object]:
    if hasattr(response, "model_dump"):
        return response.model_dump()
    return response.dict()
