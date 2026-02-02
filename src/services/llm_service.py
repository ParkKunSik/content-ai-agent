import asyncio
import json
import logging
from typing import List, Dict, Any, Optional

from google.api_core import exceptions
from vertexai.generative_models import GenerationConfig
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    wait_random_exponential,
    retry_if_exception
)

from src.core.model_factory import ModelFactory
from src.core.config import settings
from src.schemas.enums.persona_type import PersonaType
from src.schemas.enums.project_type import ProjectType
from src.schemas.enums.finish_reason import FinishReason
from src.schemas.models.prompt.detailed_analysis_refined_response import DetailedAnalysisRefinedResponse
from src.schemas.models.prompt.detailed_analysis_response import DetailedAnalysisResponse
from src.schemas.models.prompt.analysis_content_item import AnalysisContentItem
from src.utils.prompt_manager import PromptManager

logger = logging.getLogger(__name__)

def create_json_config(temperature: float, response_schema: Optional[Dict[str, Any]] = None):
    """Generates a GenerationConfig instance for JSON output."""
    if temperature is None:
        raise ValueError("Temperature must be provided for GenerationConfig.")

    
    return GenerationConfig(
        max_output_tokens=settings.MAX_OUTPUT_TOKENS,
        temperature=temperature,
        response_mime_type="application/json",
        response_schema=response_schema
    )


def is_quota_error(exception):
    """할당량 관련 오류 판단"""
    error_msg = str(exception).lower()
    return (
        isinstance(exception, exceptions.ResourceExhausted) or
        "429" in error_msg or 
        "resource exhausted" in error_msg
    )


def is_retryable_error(exception):
    """재시도 가능한 서버/네트워크 오류 판단"""
    error_msg = str(exception).lower()
    return (
        isinstance(exception, (
            exceptions.InternalServerError,
            exceptions.ServiceUnavailable,
            exceptions.DeadlineExceeded
        )) or
        "event loop is closed" in error_msg or
        "connection" in error_msg or
        any(code in error_msg for code in ["500", "502", "503", "504"])
    )


class LLMService:
    """
    Vertex AI LLM 통신을 전담하는 서비스 클래스.
    """

    def __init__(self, prompt_manager: PromptManager):
        self.prompt_manager = prompt_manager

    async def count_total_tokens(self, contents: List[str]) -> int:
        model = ModelFactory.get_model(PersonaType.COMMON_TOKEN_COUNTER)
        total = 0
        for text in contents:
            try:
                resp = model.count_tokens(text)
                total += resp.total_tokens
            except Exception as e:
                logger.warning(f"Failed to count tokens: {e}")
                total += len(text) // 2
        return total

    async def generate(self, prompt: str, persona_type: PersonaType, response_schema: Optional[Dict[str, Any]] = None) -> str:
        """Generic method to generate content using a specific persona."""
        model = ModelFactory.get_model(persona_type)
        return await self._safe_generate_content(
            model, 
            prompt, 
            temperature=persona_type.temperature,
            response_schema=response_schema
        )

    async def run_single_pass_analysis(
        self, 
        contents: List[str],
        persona_type: PersonaType,
        project_id: int,
        project_type: ProjectType
    ) -> str:
        """단일 패스 분석 수행"""
        model = ModelFactory.get_model(persona_type)
        
        # Use high-level PromptManager method
        prompt = self.prompt_manager.get_contents_analysis_prompt(
            project_id=project_id,
            project_type=project_type,
            combined_summary="\n\n".join(contents)
        )
        
        return await self._safe_generate_content(
            model, 
            prompt, 
            temperature=persona_type.temperature
        )

    async def run_map_reduce_analysis(
        self,
        contents: List[str],
        persona_type: PersonaType,
        project_id: int,
        project_type: ProjectType
    ) -> str:
        """Map-Reduce 분석 수행 (청킹 단계에서도 동일한 템플릿 사용)"""
        # Map Phase: Flash 모델로 각 콘텐츠 요약
        flash_persona = PersonaType.SUMMARY_DATA_ANALYST
        flash_model = ModelFactory.get_model(flash_persona)

        chunk_summaries = []
        for i, chunk in enumerate(contents):
            logger.info(f"Processing chunk {i+1}/{len(contents)}")

            # Use high-level method for chunks (use base project_id for chunks)
            chunk_prompt = self.prompt_manager.get_contents_analysis_prompt(
                project_id=project_id,
                project_type=project_type,
                combined_summary=chunk
            )

            result_json = await self._safe_generate_content(
                flash_model, 
                chunk_prompt, 
                temperature=flash_persona.temperature
            )
            summary_text = self._parse_summary(result_json)
            chunk_summaries.append(summary_text)

            await asyncio.sleep(0.1)

        await asyncio.sleep(0.2)
        logger.info("Map phase completed, starting Reduce phase")

        # Reduce Phase: Pro 모델로 통합 분석
        pro_model = ModelFactory.get_model(persona_type)
        final_prompt = self.prompt_manager.get_contents_analysis_prompt(
            project_id=project_id,
            project_type=project_type,
            combined_summary="\n---\n".join(chunk_summaries)
        )

        return await self._safe_generate_content(
            pro_model, 
            final_prompt, 
            temperature=persona_type.temperature
        )

    def _convert_to_analysis_items(self, content_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        content_items를 AnalysisContentItem으로 변환하여 프롬프트 최적화된 딕셔너리 리스트 반환
        """
        analysis_items = []
        for item in content_items:
            content_item = AnalysisContentItem(
                id=item.get("content_id") or item.get("id"),  # Support both keys
                content=item.get("content"),
                has_image=None if item.get("has_image") is False else item.get("has_image")  # 삼항연산자 활용
            )
            analysis_items.append(content_item.model_dump(exclude_none=True))  # None 필드 제외
        return analysis_items

    async def perform_detailed_analysis(
        self,
        project_id: int,
        project_type: ProjectType,
        content_items: List[Dict[str, Any]]
    ) -> DetailedAnalysisResponse:
        """
        상세 분석 수행 (Main Analysis)
        PRO_DATA_ANALYST 페르소나를 사용하여 콘텐츠를 구조화하고 심층 분석합니다.
        """
        analysis_items = self._convert_to_analysis_items(content_items)

        prompt = self.prompt_manager.get_detailed_analysis_prompt(
            project_id=project_id,
            project_type=project_type,
            content_items=json.dumps(analysis_items, ensure_ascii=False, separators=(',', ':'))
        )

        schema = DetailedAnalysisResponse.model_json_schema()
        response_str = await self.generate(prompt, PersonaType.PRO_DATA_ANALYST, response_schema=schema)
        return self._parse_detailed_analysis_response(response_str)

    async def refine_analysis_summary(
        self,
        project_id: int,
        project_type: ProjectType,
        raw_analysis_data: str,
        persona_type: PersonaType
    ) -> DetailedAnalysisRefinedResponse:
        """
        분석 요약 정제 (Refinement)
        분석된 데이터를 바탕으로 요약의 길이를 최적화하고 정제합니다.
        """
        prompt = self.prompt_manager.get_detailed_analysis_summary_refine_prompt(
            project_id=project_id,
            project_type=project_type,
            raw_analysis_data=raw_analysis_data
        )

        schema = DetailedAnalysisRefinedResponse.model_json_schema()
        response_str = await self.generate(prompt, persona_type, response_schema=schema)
        return self._parse_refined_response(response_str)

    @retry(
        retry=retry_if_exception(is_quota_error),
        wait=wait_exponential(multiplier=60, min=60, max=600),
        stop=stop_after_attempt(5),
        reraise=True
    )
    @retry(
        retry=retry_if_exception(is_retryable_error),
        wait=wait_random_exponential(multiplier=1, max=60),
        stop=stop_after_attempt(3),
        reraise=True
    )
    async def _safe_generate_content(
        self, 
        model, 
        prompt: str, 
        temperature: float, 
        response_schema: Optional[Dict[str, Any]] = None
    ) -> str:
        """안전한 모델 호출 및 재시도"""
        generation_config = create_json_config(
            temperature=temperature, 
            response_schema=response_schema
        )

        try:
            response = await model.generate_content_async(
                prompt,
                generation_config=generation_config
            )
            
            # Check for truncation or safety filters first
            if hasattr(response, 'usage_metadata'):
                logger.info(f"Prompt tokens: {response.usage_metadata.prompt_token_count}")
                logger.info(f"Output tokens: {response.usage_metadata.candidates_token_count}")
                logger.info(f"Total tokens: {response.usage_metadata.total_token_count}")

            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                finish_reason_code = getattr(candidate, 'finish_reason', None)
                finish_reason = FinishReason.from_value(finish_reason_code)

                logger.info(f"Response candidates: {len(response.candidates) if hasattr(response, 'candidates') else 0}")
                logger.info(f"Response finish_reason: {finish_reason.name} ({finish_reason.value})")
                logger.info(f"Response text length: {len(response.text)} chars")

                if finish_reason == FinishReason.MAX_TOKENS:
                    prompt_tokens = getattr(response.usage_metadata, 'prompt_token_count', 'unknown')
                    total_tokens = getattr(response.usage_metadata, 'total_token_count', 'unknown')
                    logger.warning(
                        f"Response generation stopped due to MAX_TOKENS. "
                        f"Prompt tokens: {prompt_tokens}, Total tokens: {total_tokens}. "
                        f"Response might be incomplete."
                    )
                    # Truncation is critical for JSON parsing, so we treat it as an error to trigger retry
                    # or allow caller to handle. For now, raising ValueError.
                    raise ValueError(f"Response truncated due to MAX_TOKENS limit ({settings.MAX_OUTPUT_TOKENS}).")
                
                if finish_reason == FinishReason.SAFETY:
                     raise ValueError(f"Response blocked by safety filters: {candidate.safety_ratings}")

            # Try to get text from response
            try:
                return response.text
            except (ValueError, AttributeError) as text_error:
                raise ValueError(f"Cannot extract text from response: {text_error}")
        except Exception as e:
            logger.error(f"Model call failed: {e}")
            raise

    def _parse_summary(self, json_str: str) -> str:
        """JSON 응답에서 summary 필드 추출"""
        try:
            cleaned = json_str.strip().replace("```json", "").replace("```", "").strip()
            data = json.loads(cleaned)
            return data.get("summary", json_str)
        except Exception:
            return json_str

    def _parse_detailed_analysis_response(self, response_str: str) -> DetailedAnalysisResponse:
        """Parses and validates Step 1 response."""
        data = None
        cleaned = response_str.strip().replace("```json", "").replace("```", "").strip()
        
        try:
            data = json.loads(cleaned)
            return DetailedAnalysisResponse(**data)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Step 1 response: {e}")

            # 원본 응답 전체 로깅 (디버깅용)
            logger.error(f"Raw Step 1 response_str:\n{response_str}")

            # 파싱 오류 위치 전후 컨텍스트 로깅 (디버깅용)
            error_pos = getattr(e, 'pos', 0)
            context_start = max(0, error_pos - 100)
            context_end = min(len(cleaned), error_pos + 100)
            error_context = cleaned[context_start:context_end]
            logger.debug(f"Error context around position {error_pos}: ...{error_context}...")

            # 일반적인 JSON 오류 패턴 자동 수정 시도
            try:
                import re
                # 시도 1: Trailing comma 제거 (가장 흔한 오류)
                # , } -> }
                # , ] -> ]
                # \s*는 공백 문자를 포함
                attempt = re.sub(r',\s*}', '}', cleaned)
                attempt = re.sub(r',\s*]', ']', attempt)

                data = json.loads(attempt)
                logger.warning("Successfully parsed after removing trailing commas")
                return DetailedAnalysisResponse(**data)

            except Exception as comma_error:
                logger.debug(f"Trailing comma correction failed: {comma_error}")

                try:
                    # 시도 2: 연속된 공백 정리 (기존 로직 유지)
                    import re
                    attempt = re.sub(r'\s+', ' ', cleaned)
                    data = json.loads(attempt)
                    logger.warning("Successfully parsed after whitespace normalization")
                    return DetailedAnalysisResponse(**data)
                except Exception as ws_error:
                    logger.error(f"Whitespace correction failed: {ws_error}")

            # 원본 에러 정보로 최종 실패 처리
            logger.debug(f"Raw response (first 1000 chars): {response_str[:1000]}")
            logger.debug(f"Raw response (last 1000 chars): {response_str[-1000:]}")
            raise ValueError(f"Step 1 analysis failed: JSON parsing error at position {error_pos}: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to validate Step 1 response: {e}")

            # 원본 응답 전체 로깅 (Validation 에러 시)
            logger.error(f"Raw Step 1 response_str (validation error):\n{response_str}")

            # Validation 에러 시 파싱된 데이터 전체 로깅
            if data is not None:
                logger.error(f"Parsed data that failed validation:")
                logger.error(json.dumps(data, indent=2, ensure_ascii=False))

            raise ValueError(f"Step 1 analysis failed: {str(e)}")

    def _parse_refined_response(self, response_str: str) -> DetailedAnalysisRefinedResponse:
        """Parses and validates Step 2 response."""
        try:
            cleaned = response_str.strip().replace("```json", "").replace("```", "").strip()
            data = json.loads(cleaned)

            # Robustness: Handle if LLM returns a list containing the object
            if isinstance(data, list) and len(data) > 0:
                logger.warning("Step 2 response returned as a list, extracting the first element.")
                data = data[0]

            return DetailedAnalysisRefinedResponse(**data)
        except Exception as e:
            logger.error(f"Failed to parse Step 2 response: {e}")

            # 원본 응답 전체 로깅 (Step 2 에러 시)
            logger.error(f"Raw Step 2 response_str:\n{response_str}")

            raise ValueError(f"Step 2 refinement failed: {str(e)}")
