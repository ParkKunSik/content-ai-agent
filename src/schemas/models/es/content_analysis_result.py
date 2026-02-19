from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Literal, Optional, Union

from pydantic import BaseModel, Field, field_serializer

from src.schemas.enums.content_type import ExternalContentType
from src.schemas.enums.persona_type import PersonaType
from src.schemas.enums.project_type import ProjectType
from src.schemas.models.common.structured_analysis_refine_result import StructuredAnalysisRefineResult
from src.schemas.models.prompt.response.structured_analysis_result import StructuredAnalysisResult


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
    """분석 결과 데이터 V1 - StructuredAnalysisResult 기반"""
    version: Literal[1] = 1
    meta_persona: PersonaType = Field(description="분석에 사용된 페르소나")
    meta_data: StructuredAnalysisResult = Field(description="V1 구조화된 분석 결과")
    persona: PersonaType = Field(description="요약 정제에 사용된 페르소나")
    data: StructuredAnalysisRefineResult = Field(description="정제된 최종 분석 결과")

    @field_serializer('meta_persona', 'persona')
    def serialize_persona(self, persona: PersonaType, _info):
        """PersonaType Enum을 문자열(이름)로 직렬화하여 내부 함수 객체가 포함되지 않도록 함"""
        return persona.name

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

    @field_serializer('project_type')
    def serialize_project_type(self, project_type: ProjectType, _info):
        """ProjectType Enum 직렬화"""
        return project_type.value
    
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
                            "meta_persona": {"type": "keyword"},
                            "meta_data": {
                                "type": "object",
                                "enabled": True
                            },
                            "persona": {"type": "keyword"},
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
