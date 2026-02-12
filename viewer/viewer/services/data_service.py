"""Viewer 데이터 조회 서비스"""

import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

# viewer 패키지 경로를 sys.path에 추가
_viewer_root = Path(__file__).parent.parent.parent
if str(_viewer_root) not in sys.path:
    sys.path.insert(0, str(_viewer_root))

import requests

from viewer.config import settings
from viewer.schemas.models import ProjectInfo, ResultDocument
from viewer.services.es_client import ESClient

logger = logging.getLogger(__name__)


class ViewerDataService:
    """ES 분석 결과 조회 서비스"""

    # Wadiz API 세션 (Queue-it 쿠키 유지)
    _wadiz_session: Optional[requests.Session] = None

    def __init__(self):
        es = ESClient()
        self.client = es.client
        self.result_index_alias = es.result_index_alias

    def get_project_ids(self) -> List[str]:
        """고유 project_id 목록 조회"""
        try:
            response = self.client.search(
                index=self.result_index_alias,
                size=0,
                aggs={"unique_projects": {"terms": {"field": "project_id", "size": 10000}}},
            )
            buckets = response["aggregations"]["unique_projects"]["buckets"]
            project_ids = [str(b["key"]) for b in buckets]

            # 숫자로 정렬
            try:
                project_ids.sort(key=lambda x: int(x), reverse=True)
            except ValueError:
                project_ids.sort(reverse=True)

            logger.info(f"Found {len(project_ids)} projects")
            return project_ids
        except Exception as e:
            logger.error(f"Failed to get project IDs: {e}")
            return []

    def get_content_types_by_project(self, project_id: str) -> List[str]:
        """특정 프로젝트의 content_type 목록 조회"""
        try:
            response = self.client.search(
                index=self.result_index_alias,
                size=0,
                query={"term": {"project_id": project_id}},
                aggs={"content_types": {"terms": {"field": "content_type"}}},
            )
            buckets = response["aggregations"]["content_types"]["buckets"]
            content_types = [b["key"] for b in buckets]
            return content_types
        except Exception as e:
            logger.error(f"Failed to get content types for project {project_id}: {e}")
            return []

    def get_all_content_types_batch(self) -> Dict[str, List[str]]:
        """모든 프로젝트의 content_type을 한 번에 조회 (배치 쿼리)"""
        try:
            # ES 복합 집계로 한 번에 조회
            response = self.client.search(
                index=self.result_index_alias,
                size=0,
                aggs={
                    "projects": {
                        "terms": {"field": "project_id", "size": 10000},
                        "aggs": {
                            "content_types": {"terms": {"field": "content_type"}}
                        }
                    }
                },
            )

            result = {}
            for bucket in response["aggregations"]["projects"]["buckets"]:
                project_id = str(bucket["key"])
                content_types = [ct["key"] for ct in bucket["content_types"]["buckets"]]
                result[project_id] = content_types

            logger.info(f"Batch loaded content_types for {len(result)} projects")
            return result
        except Exception as e:
            logger.error(f"Failed to batch get content types: {e}")
            return {}

    def get_result(self, project_id: str, content_type: str) -> Optional[ResultDocument]:
        """특정 project/content_type의 최신 결과 조회"""
        try:
            response = self.client.search(
                index=self.result_index_alias,
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
                logger.info(f"Found result for project {project_id}, content_type {content_type}")
                try:
                    return ResultDocument(**source)
                except Exception as parse_error:
                    logger.error(f"Failed to parse result document: {parse_error}")
                    logger.error(f"Source keys: {source.keys()}")
                    return None

            logger.warning(f"No result found for project {project_id}, content_type {content_type}")
            return None
        except Exception as e:
            logger.error(f"Failed to get result: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    # === Wadiz API ===

    @classmethod
    def _get_wadiz_session(cls) -> requests.Session:
        """Wadiz API 세션 획득"""
        if cls._wadiz_session is None:
            cls._wadiz_session = requests.Session()
            cls._wadiz_session.headers.update({
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "application/json",
            })
            try:
                cls._wadiz_session.get(settings.WADIZ_API_BASE_URL, timeout=10)
                logger.info("Wadiz session initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Wadiz session: {e}")
        return cls._wadiz_session

    @classmethod
    def get_project_info(cls, project_id: int) -> Optional[ProjectInfo]:
        """Wadiz API에서 프로젝트 정보 조회"""
        api_url = f"{settings.WADIZ_API_BASE_URL}/web/apip/funding/campaigns/{project_id}/detail"
        detail_link = f"{settings.WADIZ_API_BASE_URL}/web/campaign/detail/{project_id}"

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

    def get_all_projects_with_info(self) -> List[Dict]:
        """모든 프로젝트의 ID, 제목, content_types를 반환"""
        # 프로젝트 ID 및 content_types 배치 조회
        project_ids = self.get_project_ids()
        all_content_types = self.get_all_content_types_batch()

        projects = []
        for pid in project_ids:
            info = self.get_project_info(int(pid))
            projects.append({
                "id": pid,
                "title": info.title if info else None,
                "thumbnail_url": info.thumbnail_url if info else None,
                "link": info.link if info else None,
                "content_types": all_content_types.get(pid, [])
            })

        return projects
