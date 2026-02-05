from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Literal, Optional, Union

from pydantic import BaseModel, Field

from src.schemas.enums.content_type import ExternalContentType
from src.schemas.enums.persona_type import PersonaType
from src.schemas.enums.project_type import ProjectType
from src.schemas.models.prompt.structured_analysis_refined_response import StructuredAnalysisRefinedResponse
from src.schemas.models.prompt.structured_analysis_response import StructuredAnalysisResponse


class ContentAnalysisResultState(str, Enum):
    """분석 상태"""
    UNAVAILABLE = "UNAVAILABLE"     # 사용 불가
    IN_PROGRESS = "IN_PROGRESS"     # 진행 중
    FAIL = "FAIL"                   # 실패
    COMPLETED = "COMPLETED"         # 완료

class ContentAnalysisResult(BaseModel):
    """분석 결과 기본 클래스 (Discriminated Union 기반)"""
    version: int = Field(description="결과 데이터 버전 (Discriminator)")

class ContentAnalysisResultDataV1(ContentAnalysisResult):
    """분석 결과 데이터 V1 - StructuredAnalysisResponse 기반"""
    version: Literal[1] = 1
    persona: PersonaType = Field(description="분석에 사용된 페르소나")
    data: StructuredAnalysisResponse = Field(description="V1 구조화된 분석 응답")
    refine_persona: Optional[PersonaType] = Field(default=None, description="요약 정제에 사용된 페르소나")
    refined_summary: Optional[StructuredAnalysisRefinedResponse] = Field(default=None, description="정제된 요약 결과")

class ContentAnalysisResultDocument(BaseModel):
    """ES에 저장될 분석 결과 문서"""
    project_id: str = Field(description="프로젝트 ID")
    project_type: ProjectType = Field(description="프로젝트 타입")
    content_type: ExternalContentType = Field(description="콘텐츠 타입")
    version: int = Field(default=0, description="버전 번호")
    state: ContentAnalysisResultState = Field(description="분석 상태")
    reason: Optional[str] = Field(default=None, description="실패/사용불가 사유")
    result: Optional[Union[ContentAnalysisResultDataV1]] = Field(
        default=None, 
        description="분석 결과 데이터",
        discriminator='version'
    )
    
    # 메타데이터
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="생성 시간")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="수정 시간")
    
    @classmethod
    def get_es_mapping(cls) -> Dict[str, Any]:
        """Elasticsearch index mapping 생성"""
        return {
            "mappings": {
                "properties": {
                    "project_id": {"type": "keyword"},
                    "project_type": {"type": "keyword"},
                    "content_type": {"type": "keyword"},
                    "version": {"type": "integer"},
                    "state": {"type": "keyword"},
                    "reason": {"type": "text"},
                    "result": {
                        "type": "object",
                        "properties": {
                            "version": {"type": "integer"},
                            "data": {
                                "type": "object",
                                "enabled": True
                            }
                        }
                    },
                    "created_at": {"type": "date"},
                    "updated_at": {"type": "date"}
                }
            }
        }

class ContentAnalysisResultQuery(BaseModel):
    """분석 결과 조회 쿼리"""
    project_id: str
    content_type: str