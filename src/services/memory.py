import json
import logging
from typing import Dict, Any, Optional

import redis
from elasticsearch import Elasticsearch

from src.core.config import settings

logger = logging.getLogger(__name__)

class MemoryService:
    """
    Manages dual-layer memory for the AI Agent.
    - Redis: Ephemeral project context (Short-term)
    - Elasticsearch: Analysis history (Long-term)
    """

    def __init__(self):
        # 1. Initialize Redis Client
        try:
            self.redis_client = redis.Redis.from_url(
                settings.redis_url, 
                decode_responses=True,
                socket_connect_timeout=5
            )
            logger.info(f"Redis connected to {settings.REDIS_HOST}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_client = None

        # 2. Initialize Elasticsearch Client
        try:
            es_kwargs = {"hosts": [settings.ELASTICSEARCH_URL]}
            if settings.ELASTICSEARCH_API_KEY:
                es_kwargs["api_key"] = settings.ELASTICSEARCH_API_KEY
            
            self.es_client = Elasticsearch(**es_kwargs)
            logger.info(f"Elasticsearch connected to {settings.ELASTICSEARCH_URL}")
        except Exception as e:
            logger.error(f"Failed to connect to Elasticsearch: {e}")
            self.es_client = None

    def _get_redis_key(self, project_id: str) -> str:
        """
        Generates a key prefixed with the environment profile and internal agent ID.
        Format: {ENV}:{AGENT_ID}:proj:{PROJECT_ID}:context
        """
        return f"{settings.ENV}:{settings.INTERNAL_AGENT_ID}:proj:{project_id}:context"

    # --- Redis: Project Context Management ---

    def save_project_context(self, project_id: str, context_data: Dict[str, Any], ttl_seconds: int = 86400):
        """Saves analysis context to Redis with a default 24h TTL."""
        if not self.redis_client:
            return
        
        key = self._get_redis_key(project_id)
        try:
            self.redis_client.set(key, json.dumps(context_data), ex=ttl_seconds)
        except Exception as e:
            logger.error(f"Error saving context to Redis: {e}")

    def get_project_context(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves project context from Redis."""
        if not self.redis_client:
            return None
            
        key = self._get_redis_key(project_id)
        try:
            data = self.redis_client.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"Error reading context from Redis: {e}")
            return None

    def clear_project_context(self, project_id: str):
        """Force deletes the project context."""
        if self.redis_client:
            self.redis_client.delete(self._get_redis_key(project_id))

    # --- Elasticsearch: History Management ---

    def save_history(self, project_id: str, persona_type: str, result_data: Dict[str, Any]):
        """Archives the final analysis result to Elasticsearch."""
        if not self.es_client:
            logger.warning("History not saved: Elasticsearch client not initialized.")
            return

        doc = {
            "agent_id": settings.INTERNAL_AGENT_ID,  # Explicitly store Agent ID
            "project_id": project_id,
            "persona_type": persona_type,
            "env": settings.ENV,
            "timestamp": "now",
            "analysis_result": result_data
        }
        
        try:
            index = settings.ELASTICSEARCH_INDEX_HISTORY
            if not self.es_client.indices.exists(index=index):
                self.es_client.indices.create(index=index)
                
            self.es_client.index(index=index, document=doc)
            logger.info(f"History archived for project {project_id} (Agent: {settings.INTERNAL_AGENT_ID})")
        except Exception as e:
            logger.error(f"Failed to archive history to Elasticsearch: {e}")
