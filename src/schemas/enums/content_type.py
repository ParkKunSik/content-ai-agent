from enum import Enum
from typing import List, Dict, Any


class InternalContentType(str, Enum):
    """내부 ES 조회에서 사용하는 콘텐츠 타입 - 모든 내부 로직 처리"""

    # g2 인덱스 사용 타입들 (groupsubcode 사용)
    SUPPORT = ("wadiz_db_comment_g2_*", True)
    SUGGESTION = ("wadiz_db_comment_g2_*", True)
    REVIEW = ("wadiz_db_comment_g2_*", True)
    PHOTO_REVIEW = ("wadiz_db_comment_g2_*", True)

    # g4 인덱스 사용 타입 (groupsubcode 미사용)
    SATISFACTION = ("wadiz_db_comment_g4_*", False)

    def __init__(self, index_pattern: str, uses_groupsubcode: bool):
        """
        생성자에서 인덱스 패턴, groupsubcode 사용 여부를 주입

        Args:
            index_pattern: ES 인덱스 패턴
            uses_groupsubcode: groupsubcode 필터 사용 여부
        """
        self._value_ = self.name
        self._index_pattern = index_pattern
        self._uses_groupsubcode = uses_groupsubcode

    @property
    def index_pattern(self) -> str:
        """ES 인덱스 패턴 반환"""
        return self._index_pattern

    @property
    def uses_groupsubcode(self) -> bool:
        """groupsubcode 필터 사용 여부"""
        return self._uses_groupsubcode

    def get_es_query_conditions(self, project_id: int) -> Dict[str, Any]:
        """
        ES 쿼리 조건 생성 (단일 내부 타입용)

        Args:
            project_id: 프로젝트 ID (캠페인 ID)

        Returns:
            dict: ES bool 쿼리
        """
        must_conditions = [{"term": {"campaignid": project_id}}]

        # groupsubcode 사용 타입인 경우만 추가
        if self.uses_groupsubcode:
            must_conditions.append({"term": {"groupsubcode": self.value}})

        return {
            "bool": {
                "must": must_conditions
            }
        }

    @classmethod
    def get_combined_query_conditions(
        cls,
        internal_types: List['InternalContentType'],
        project_id: int
    ) -> Dict[str, Any]:
        """
        복수 내부 타입에 대한 ES 쿼리 조건 생성

        Args:
            internal_types: 내부 타입 리스트
            project_id: 프로젝트 ID (캠페인 ID)

        Returns:
            dict: ES bool 쿼리
        """
        if len(internal_types) == 1:
            # 단일 타입인 경우
            return internal_types[0].get_es_query_conditions(project_id)

        # 복수 타입인 경우 (REVIEW: REVIEW + PHOTO_REVIEW)
        # groupsubcode 사용하는 타입들만 필터링
        groupsubcodes = [
            internal_type.value
            for internal_type in internal_types
            if internal_type.uses_groupsubcode
        ]

        if groupsubcodes:
            return {
                "bool": {
                    "must": [
                        {"term": {"campaignid": project_id}},
                        {"terms": {"groupsubcode": groupsubcodes}}
                    ]
                }
            }
        else:
            # groupsubcode를 사용하지 않는 타입들만 있는 경우
            return {
                "bool": {
                    "must": [{"term": {"campaignid": project_id}}]
                }
            }


class ExternalContentType(str, Enum):
    """외부 API에서 사용하는 콘텐츠 타입 - 단순 변환만 담당"""

    SUPPORT = ([InternalContentType.SUPPORT])
    SUGGESTION = ([InternalContentType.SUGGESTION])
    REVIEW = ([InternalContentType.REVIEW, InternalContentType.PHOTO_REVIEW])
    SATISFACTION = ([InternalContentType.SATISFACTION])

    def __init__(self, internal_types: List[InternalContentType]):
        self._value_ = self.name
        self._internal_types = internal_types

    def to_internal(self) -> List[InternalContentType]:
        """외부 타입을 내부 타입 리스트로 변환 (변환 기능만)"""
        return self._internal_types
