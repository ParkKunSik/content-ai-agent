"""
뷰어용 ES 데이터 조회 서비스 (읽기 전용)

기존 ESContentAnalysisResultService와 독립적으로 동작하며,
뷰어에 필요한 조회 기능만 제공합니다.
"""
import logging
from dataclasses import dataclass
from typing import Optional
import json

import requests

from src.schemas.enums.persona_type import PersonaType
from src.schemas.models.es.content_analysis_result import ContentAnalysisResultDocument
from src.viewer.viewer_es_client import ViewerESClient

logger = logging.getLogger(__name__)


@dataclass
class ProjectInfo:
    """프로젝트 기본 정보"""
    project_id: int
    title: str
    thumbnail_url: str
    link: str


class ViewerDataService:
    """뷰어용 ES 데이터 조회 서비스"""

    def __init__(self):
        es = ViewerESClient()
        self.client = es.client
        self.index_name = es.index_name

    @staticmethod
    def _preprocess_persona_fields(source: dict) -> dict:
        """
        ES에서 읽은 source dict의 PersonaType 문자열을 enum으로 변환

        ES에 저장 시 field_serializer로 PersonaType.name (문자열)로 직렬화되었으나,
        역직렬화 시 Pydantic이 자동으로 enum으로 변환하지 못하는 문제 해결
        """
        if "result" in source and source["result"]:
            result = source["result"]
            # meta_persona 변환
            if "meta_persona" in result and isinstance(result["meta_persona"], str):
                try:
                    result["meta_persona"] = PersonaType[result["meta_persona"]]
                except KeyError:
                    logger.warning(f"Unknown meta_persona: {result['meta_persona']}")
            # persona 변환
            if "persona" in result and isinstance(result["persona"], str):
                try:
                    result["persona"] = PersonaType[result["persona"]]
                except KeyError:
                    logger.warning(f"Unknown persona: {result['persona']}")
        return source

    def get_project_ids(self) -> list[str]:
        """
        고유 project_id 목록 조회 (ES aggregation)

        Returns:
            project_id 문자열 목록 (정렬됨)
        """
        try:
            response = self.client.search(
                index=self.index_name,
                size=0,  # 문서 본문 불필요
                aggs={"unique_projects": {"terms": {"field": "project_id", "size": 10000}}},
            )
            buckets = response["aggregations"]["unique_projects"]["buckets"]
            project_ids = [b["key"] for b in buckets]
            # 숫자로 정렬 (project_id가 숫자인 경우)
            try:
                project_ids.sort(key=lambda x: int(x), reverse=True)
            except ValueError:
                project_ids.sort(reverse=True)
            logger.info(f"Found {len(project_ids)} projects")
            return project_ids
        except Exception as e:
            logger.error(f"Failed to get project IDs: {e}")
            return []

    def get_content_types_by_project(self, project_id: str) -> list[str]:
        """
        특정 project의 content_type 목록 조회

        Args:
            project_id: 프로젝트 ID

        Returns:
            content_type 문자열 목록
        """
        try:
            response = self.client.search(
                index=self.index_name,
                size=0,
                query={"term": {"project_id": project_id}},
                aggs={"content_types": {"terms": {"field": "content_type"}}},
            )
            buckets = response["aggregations"]["content_types"]["buckets"]
            content_types = [b["key"] for b in buckets]
            logger.info(f"Project {project_id} has content types: {content_types}")
            return content_types
        except Exception as e:
            logger.error(f"Failed to get content types for project {project_id}: {e}")
            return []

    def get_result(
        self, project_id: str, content_type: str
    ) -> Optional[ContentAnalysisResultDocument]:
        """
        특정 project/content_type의 최신 결과 조회

        Args:
            project_id: 프로젝트 ID
            content_type: 콘텐츠 타입

        Returns:
            ContentAnalysisResultDocument 또는 None
        """
        try:
            response = self.client.search(
                index=self.index_name,
                query={
                    "bool": {
                        "must": [
                            {"term": {"project_id": project_id}},
                            {"term": {"content_type": content_type}},
                        ]
                    }
                },
                sort=[{"version": {"order": "desc"}}],
                size=1,
            )

            if response["hits"]["hits"]:
                source = response["hits"]["hits"][0]["_source"]
                logger.info(
                    f"Found result for project {project_id}, content_type {content_type}"
                )
                # PersonaType 문자열을 enum으로 전처리
                source = self._preprocess_persona_fields(source)
                return ContentAnalysisResultDocument(**source)

            logger.warning(
                f"No result found for project {project_id}, content_type {content_type}"
            )
            return None
        except Exception as e:
            logger.error(f"Failed to get result: {e}")
            return None

    def get_all_results_summary(self) -> list[dict]:
        """
        전체 결과 요약 조회 (project_id, content_type, version, state, updated_at)

        Returns:
            요약 정보 딕셔너리 목록
        """
        try:
            response = self.client.search(
                index=self.index_name,
                size=1000,
                source=["project_id", "content_type", "version", "state", "updated_at"],
                sort=[{"updated_at": {"order": "desc"}}],
            )

            results = []
            for hit in response["hits"]["hits"]:
                results.append(hit["_source"])

            logger.info(f"Found {len(results)} total results")
            return results
        except Exception as e:
            logger.error(f"Failed to get all results summary: {e}")
            return []

    # Wadiz API 세션 (Queue-it 쿠키 유지)
    _wadiz_session: Optional[requests.Session] = None

    @classmethod
    def _get_wadiz_session(cls) -> requests.Session:
        """Wadiz API 세션 획득 (Queue-it 쿠키 포함)"""
        if cls._wadiz_session is None:
            cls._wadiz_session = requests.Session()
            cls._wadiz_session.headers.update({
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "application/json",
            })
            # 메인 페이지 방문하여 Queue-it 쿠키 획득
            try:
                cls._wadiz_session.get("https://www.wadiz.kr/", timeout=10)
                logger.info("Wadiz session initialized with Queue-it cookie")
            except Exception as e:
                logger.warning(f"Failed to initialize Wadiz session: {e}")
        return cls._wadiz_session

    @classmethod
    def get_project_info(cls, project_id: int) -> Optional[ProjectInfo]:
        """
        Wadiz API에서 프로젝트 정보 조회

        Args:
            project_id: 프로젝트 ID

        Returns:
            ProjectInfo 또는 None (실패 시)
        """
        api_url = f"https://www.wadiz.kr/web/apip/funding/campaigns/{project_id}/detail"
        detail_link = f"https://www.wadiz.kr/web/campaign/detail/{project_id}"

        try:
            session = cls._get_wadiz_session()
            response = session.get(api_url, timeout=10)
            response.raise_for_status()
            data = response.json()

            if "data" in data:
                return ProjectInfo(
                    project_id=project_id,
                    title=data["data"].get("title", ""),
                    thumbnail_url=data["data"].get("thumbnailUrl", ""),
                    link=detail_link,
                )
            return None
        except Exception as e:
            logger.warning(f"Failed to get project info for {project_id}: {e}")
            return None
