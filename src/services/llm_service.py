import logging
from typing import Any, Dict, List, Optional

from google.genai import errors, types

from src.core.session_factory import SessionFactory
from src.core.validation_error_handler import ValidationErrorHandler
from src.schemas.enums.mime_type import MimeType
from src.schemas.enums.persona_type import PersonaType
from src.schemas.enums.project_type import ProjectType
from src.schemas.models.common.content_item import ContentItem
from src.schemas.models.prompt.analysis_content_item import AnalysisContentItem
from src.schemas.models.prompt.structured_analysis_refined_summary import StructuredAnalysisRefinedSummary
from src.schemas.models.prompt.structured_analysis_result import StructuredAnalysisResult
from src.schemas.models.prompt.structured_analysis_summary import StructuredAnalysisSummary
from src.utils.prompt_manager import PromptManager

logger = logging.getLogger(__name__)

class LLMService:
    """
    Vertex AI LLM 통신을 전담하는 서비스 클래스.
    """

    def __init__(self, prompt_manager: PromptManager):
        self.prompt_manager = prompt_manager
        self.validation_handler = ValidationErrorHandler(max_retries=3, delay_between_retries=1.0)

    async def count_total_tokens(self, contents: List[str]) -> int:
        total = 0
        for text in contents:
            try:
                token_count = SessionFactory.count_tokens(text, PersonaType.COMMON_TOKEN_COUNTER)
                total += token_count
            except Exception as e:
                logger.warning(f"Failed to count tokens: {e}")
                total += len(text) // 2
        return total

    async def generate(self, prompt: str, persona_type: PersonaType, mime_type: MimeType = MimeType.TEXT_PLAIN, response_schema: Optional[Dict[str, Any]] = None) -> str:
        """Generic method to generate content using a specific persona."""
        session = SessionFactory.start_session(
            persona_type=persona_type,
            mime_type=mime_type,
            schema=response_schema
        )
        
        # AsyncGenAISession을 사용한 콘텐츠 생성
        response = session.generate_content(prompt)
        
        # GenerateContentResponse에서 텍스트 추출 (고수준 예외처리)
        return self._extract_text_safely(response, persona_type)
    
    def _extract_text_safely(self, response: 'types.GenerateContentResponse', persona_type: PersonaType) -> str:
        """GenerateContentResponse에서 안전하게 텍스트를 추출한다 (베스트 프랙티스)."""
        try:
            # 1. 후보 응답(Candidates) 확인
            if not response.candidates:
                raise ValueError(f"모델이 응답을 생성하지 못했습니다 (persona: {persona_type.value})")
            
            candidate = response.candidates[0]
            
            # 2. 종료 사유에 따른 분기 처리
            if candidate.finish_reason == types.FinishReason.SAFETY:
                raise ValueError(f"안전 정책에 의해 응답이 거부되었습니다 (persona: {persona_type.value})")
            elif candidate.finish_reason == types.FinishReason.PROHIBITED_CONTENT:
                raise ValueError(f"금지된 콘텐츠로 인해 응답이 거부되었습니다 (persona: {persona_type.value})")
            elif candidate.finish_reason == types.FinishReason.BLOCKLIST:
                raise ValueError(f"차단 목록 단어로 인해 응답이 거부되었습니다 (persona: {persona_type.value})")
            elif candidate.finish_reason == types.FinishReason.SPII:
                raise ValueError(f"개인정보 포함으로 인해 응답이 거부되었습니다 (persona: {persona_type.value})")
            elif candidate.finish_reason == types.FinishReason.MAX_TOKENS:
                logger.warning(f"답변이 너무 길어 중간에 끊겼습니다 (persona: {persona_type.value})")
                # MAX_TOKENS의 경우 부분 응답이라도 사용
            
            # 3. 정상적인 경우에만 텍스트 추출
            return response.text
            
        except errors.ClientError as e:
            # 429 Rate Limit 에러 특별 처리
            if "429" in str(e) or "quota" in str(e).lower() or "rate" in str(e).lower():
                logger.warning(f"Rate limit 도달 (persona: {persona_type.value}): {e}")
                # ValidationErrorHandler의 재시도 로직에 위임하도록 재발생
                raise e  # 원본 에러 유지하여 상위 레벨에서 재시도 가능
            else:
                # 기타 클라이언트 오류 (인증, 잘못된 파라미터 등)
                logger.error(f"클라이언트 오류 발생 (persona: {persona_type.value}): {e}")
                raise ValueError(f"클라이언트 오류: {e}") from e
        except errors.ServerError as e:
            # Google 서버 측 문제 (5xx) - 재시도 로직 검토 필요
            logger.error(f"서버 오류 발생 (persona: {persona_type.value}): {e}")
            raise ValueError(f"서버 오류: {e}") from e
        except Exception as e:
            logger.error(f"예상치 못한 오류 (persona: {persona_type.value}): {e}")
            raise

    def _convert_to_analysis_items(self, content_items: List[ContentItem]) -> List[AnalysisContentItem]:
        """
        ContentItem 리스트를 AnalysisContentItem 리스트로 변환
        
        Args:
            content_items: ContentItem 객체 리스트
            
        Returns:
            List[AnalysisContentItem]: 분석용 AnalysisContentItem 리스트
        """
        analysis_items = []
        for content_item in content_items:
            # 토큰 절약을 위해 has_image가 True인 경우만 설정, 나머지는 None 처리
            analysis_item = AnalysisContentItem(
                id=content_item.content_id,  # int 타입 유지
                content=content_item.content,
                has_image=content_item.has_image if content_item.has_image is True else None
            )
            analysis_items.append(analysis_item)
        return analysis_items

    async def structure_content_analysis(
        self,
        project_id: int,
        project_type: ProjectType,
        content_items: List[ContentItem]
    ) -> StructuredAnalysisResult:
        """
        상세 분석 수행 (Main Analysis) - Phase 2 세션 기반 검증 적용
        PRO_DATA_ANALYST 페르소나를 사용하여 콘텐츠를 구조화하고 심층 분석합니다.
        """
        analysis_items = self._convert_to_analysis_items(content_items)

        prompt = self.prompt_manager.get_content_analysis_structuring_prompt(
            project_id=project_id,
            project_type=project_type,
            analysis_content_items=analysis_items
        )

        schema = StructuredAnalysisResult.model_json_schema()
        
        # ValidationErrorHandler를 사용한 재시도 로직 적용
        async def response_generator() -> str:
            return await self.generate(prompt, PersonaType.PRO_DATA_ANALYST, mime_type=MimeType.APPLICATION_JSON, response_schema=schema)
        
        return await self.validation_handler.validate_with_retry(
            response_generator=response_generator,
            model_class=StructuredAnalysisResult,
            error_context="content_analysis_structuring"
        )

    async def refine_analysis_summary(
        self,
        project_id: int,
        project_type: ProjectType,
        refine_content_items: StructuredAnalysisSummary,
        persona_type: PersonaType
    ) -> StructuredAnalysisRefinedSummary:
        """
        분석 요약 정제 (Refinement) - Phase 2 세션 기반 검증 적용
        분석된 데이터를 바탕으로 요약의 길이를 최적화하고 정제합니다.
        """
        prompt = self.prompt_manager.get_content_analysis_summary_refine_prompt(
            project_id=project_id,
            project_type=project_type,
            refine_content_items=refine_content_items
        )

        schema = StructuredAnalysisRefinedSummary.model_json_schema()
        
        # ValidationErrorHandler를 사용한 재시도 로직 적용
        async def response_generator() -> str:
            return await self.generate(prompt, persona_type, mime_type=MimeType.APPLICATION_JSON, response_schema=schema)
        
        return await self.validation_handler.validate_with_retry(
            response_generator=response_generator,
            model_class=StructuredAnalysisRefinedSummary,
            error_context="analysis_refinement"
        )

