"""
Configuration settings for the Deceptive UI/UX Detection and Remediation Engine.
"""

from pydantic import BaseModel


class Settings(BaseModel):
    APP_NAME: str = "Deceptive UI/UX Detection and Remediation Engine"
    APP_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    
    # NLP Configuration
    SPACY_MODEL: str = "en_core_web_sm"
    
    # Playwright Configuration
    PLAYWRIGHT_HEADLESS: bool = True
    BROWSER_TIMEOUT_MS: int = 30000
    VIEWPORT_WIDTH: int = 1280
    VIEWPORT_HEIGHT: int = 800
    USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36 DeceptiveUIDetector/1.0"
    )

    # Deception Scoring Weights
    SEVERITY_WEIGHTS: dict[str, float] = {
        "critical": 25.0,
        "high": 15.0,
        "medium": 8.0,
        "low": 3.0,
    }

    # Contrast & Visual Salience Thresholds
    MIN_WCAG_CONTRAST_RATIO: float = 4.5
    LOW_CONTRAST_THRESHOLD: float = 3.0
    TINY_FONT_SIZE_PX: float = 11.0


settings = Settings()
