from enum import Enum

class MimeType(str, Enum):
    """
    Defines supported MIME types for content generation.
    """
    TEXT_PLAIN = "text/plain"
    APPLICATION_JSON = "application/json"
