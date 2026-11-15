from typing import List, Optional
import os
import json

try:
    from pydantic import BaseModel, Field, field_validator
    from pydantic_settings import BaseSettings, SettingsConfigDict
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False
    from dataclasses import dataclass, field


DEFAULT_TARGET_MODELS = [
    # Mainstream Bang-For-Buck
    {"make": "Hyundai", "model": "Ioniq 5", "min_year": 2022},
    {"make": "Hyundai", "model": "Ioniq 6", "min_year": 2023},
    {"make": "Kia", "model": "EV6", "min_year": 2022},
    {"make": "Tesla", "model": "Model Y", "min_year": 2022},
    {"make": "Tesla", "model": "Model 3", "min_year": 2022},
    {"make": "Ford", "model": "Mustang Mach-E", "min_year": 2022},
    {"make": "Chevrolet", "model": "Bolt EUV", "min_year": 2022, "max_year": 2023},

    # Upmarket & Luxury EV Depreciation Bargains
    {"make": "BMW", "model": "i4", "min_year": 2022},
    {"make": "Mercedes-Benz", "model": "EQS", "min_year": 2022},
    {"make": "Mercedes-Benz", "model": "EQE", "min_year": 2023},
    {"make": "Cadillac", "model": "Lyriq", "min_year": 2023},
    {"make": "Genesis", "model": "GV60", "min_year": 2023},
    {"make": "Polestar", "model": "2", "min_year": 2022},
    {"make": "Audi", "model": "Q4 e-tron", "min_year": 2022},
]

if HAS_PYDANTIC:
    class TargetVehicleConfig(BaseModel):
        """
        A single watchlist surveillance target (make/model plus optional year & trim bounds).

        Pre-conditions:
            - `make` and `model` must be non-empty human readable strings.
            - `min_year` / `max_year`, when provided, must be 4-digit calendar years.
            - `trims`, when provided, must be a list of trim label strings.

        Post-conditions:
            - All provided fields are stored verbatim and coerced to their annotated types.
            - Optional fields default to `None`, meaning "no constraint applied" for that dimension.
            - The instance is JSON-serializable for Temporal activity/workflow transport.
        """

        make: str
        model: str
        min_year: Optional[int] = None
        max_year: Optional[int] = None
        trims: Optional[List[str]] = None

    class Settings(BaseSettings):
        """
        Immutable-by-default application configuration sourced from environment/.env values.

        Pre-conditions:
            - The process environment (and optional `.env` file) may supply overrides for any field.
            - Unknown extra environment keys are ignored rather than raising validation errors.
            - No network, database, or filesystem access occurs during construction.

        Post-conditions:
            - Every field resolves to a fully typed, usable value (no `None` leakage where a
              concrete default is declared).
            - `temporal_ui_url` is `None` unless `TEMPORAL_UI_URL` was explicitly provided, so
              no hardcoded dashboard hostname is ever assumed.
            - `search_target_models` always contains one `TargetVehicleConfig` per entry of
              `DEFAULT_TARGET_MODELS` unless overridden.
        """

        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore"
        )

        search_name: str = "Bay Area EV Watchlist"
        search_zip_code: str = "94103"
        search_radius_miles: int = 60
        search_min_price: int = 20000
        search_max_price: int = 60000
        search_min_year: int = 2021
        search_max_year: int = 2026
        search_powertrains: List[str] = Field(default_factory=lambda: ["BEV"])

        search_target_models: List[TargetVehicleConfig] = Field(
            default_factory=lambda: [TargetVehicleConfig(**m) for m in DEFAULT_TARGET_MODELS]
        )

        database_url: str = "postgresql+asyncpg://researcher:researcher_pass@localhost:5432/researcher"
        database_echo: bool = False

        temporal_host: str = "localhost:7233"
        temporal_namespace: str = "default"
        temporal_task_queue_default: str = "car-research-queue"
        temporal_task_queue_scrapers: str = "car-scraper-queue"
        temporal_ui_url: Optional[str] = None

        @field_validator("temporal_ui_url", mode="before")
        @classmethod
        def _normalize_temporal_ui_url(cls, v: Optional[str]) -> Optional[str]:
            if isinstance(v, str):
                v = v.strip()
                return v if v else None
            return v

        scraper_headless: bool = True
        scraper_concurrency: int = 3
        scraper_residential_proxy_url: Optional[str] = None

        discord_webhook_url: Optional[str] = None
        telegram_bot_token: Optional[str] = None
        telegram_chat_id: Optional[str] = None

else:
    @dataclass
    class TargetVehicleConfig:
        """
        A single watchlist surveillance target (make/model plus optional year & trim bounds).

        Pre-conditions:
            - `make` and `model` must be non-empty human readable strings.
            - `min_year` / `max_year`, when provided, must be 4-digit calendar years.
            - `trims`, when provided, must be a list of trim label strings.

        Post-conditions:
            - All provided fields are stored verbatim as plain dataclass attributes.
            - Optional fields default to `None`, meaning "no constraint applied" for that dimension.
            - The instance stays JSON-serializable for Temporal activity/workflow transport.
        """

        make: str
        model: str
        min_year: Optional[int] = None
        max_year: Optional[int] = None
        trims: Optional[List[str]] = None

    @dataclass
    class Settings:
        """
        Zero-dependency dataclass fallback for application configuration (no pydantic installed).

        Pre-conditions:
            - The process environment may supply `TEMPORAL_UI_URL`; other fields keep their
              shipped defaults because no environment binding layer is available.
            - No network, database, or filesystem access occurs during construction.

        Post-conditions:
            - Every field resolves to a fully typed, usable value.
            - `temporal_ui_url` is `None` unless `TEMPORAL_UI_URL` was set to a non-blank value
              (blank/whitespace values normalize to `None`), so no hardcoded UI hostname is used.
            - `search_target_models` always contains one `TargetVehicleConfig` per entry of
              `DEFAULT_TARGET_MODELS`.
        """

        search_name: str = "Bay Area EV Watchlist"
        search_zip_code: str = "94103"
        search_radius_miles: int = 60
        search_min_price: int = 20000
        search_max_price: int = 60000
        search_min_year: int = 2021
        search_max_year: int = 2026
        search_powertrains: List[str] = field(default_factory=lambda: ["BEV"])

        search_target_models: List[TargetVehicleConfig] = field(
            default_factory=lambda: [TargetVehicleConfig(**m) for m in DEFAULT_TARGET_MODELS]
        )

        database_url: str = "postgresql+asyncpg://researcher:researcher_pass@localhost:5432/researcher"
        database_echo: bool = False

        temporal_host: str = "localhost:7233"
        temporal_namespace: str = "default"
        temporal_task_queue_default: str = "car-research-queue"
        temporal_task_queue_scrapers: str = "car-scraper-queue"
        temporal_ui_url: Optional[str] = field(
            default_factory=lambda: (os.environ.get("TEMPORAL_UI_URL") or "").strip() or None
        )

        scraper_headless: bool = True
        scraper_concurrency: int = 3
        scraper_residential_proxy_url: Optional[str] = None

        discord_webhook_url: Optional[str] = None
        telegram_bot_token: Optional[str] = None
        telegram_chat_id: Optional[str] = None

        def __post_init__(self) -> None:
            if isinstance(self.temporal_ui_url, str):
                self.temporal_ui_url = self.temporal_ui_url.strip() or None


settings = Settings()
