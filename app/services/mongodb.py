from datetime import datetime, timedelta, timezone

from pymongo import MongoClient
from pymongo.collection import Collection


class MongoCountryCacheService:
    cache_ttl = timedelta(days=30)

    def __init__(
        self,
        uri: str,
        database_name: str = "infoglobe",
        collection_name: str = "country_info_cache",
    ) -> None:
        self.client = MongoClient(
            uri,
            serverSelectionTimeoutMS=8000,
            connectTimeoutMS=8000,
        )
        database = self.client.get_default_database(default=database_name)
        self.collection: Collection = database[collection_name]
        self._ensure_indexes()

    def get_country_info(self, lookup_key: str) -> dict[str, object] | None:
        entry = self.get_country_cache_entry(lookup_key)
        if not entry:
            return None
        response = entry.get("response")
        return response if isinstance(response, dict) else None

    def get_country_cache_entry(self, lookup_key: str) -> dict[str, object] | None:
        document = self.collection.find_one(
            {"lookup_keys": lookup_key},
            {"_id": 0, "response": 1, "updated_at": 1},
        )
        if not document:
            return None

        response = document.get("response")
        if not isinstance(response, dict):
            return None

        updated_at = self._normalize_datetime(document.get("updated_at"))
        return {
            "response": response,
            "updated_at": updated_at,
            "is_stale": self._is_stale(updated_at),
        }

    def save_country_info(
        self,
        country_code: str | None,
        country_name: str,
        lookup_keys: list[str],
        response: dict[str, object],
    ) -> None:
        unique_lookup_keys = sorted({key for key in lookup_keys if key})
        filter_query = {"country_code": country_code} if country_code else {"country_name": country_name}
        now = datetime.now(timezone.utc)
        self.collection.update_one(
            filter_query,
            {
                "$set": {
                    "country_code": country_code,
                    "country_name": country_name,
                    "response": response,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
                "$addToSet": {"lookup_keys": {"$each": unique_lookup_keys}},
            },
            upsert=True,
        )

    def _ensure_indexes(self) -> None:
        self.collection.create_index("country_code", unique=False)
        self.collection.create_index("lookup_keys")

    def _normalize_datetime(self, value: object) -> datetime | None:
        if not isinstance(value, datetime):
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _is_stale(self, updated_at: datetime | None) -> bool:
        if updated_at is None:
            return True
        return datetime.now(timezone.utc) - updated_at > self.cache_ttl
