import logging
import json
import asyncio
from typing import List

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    wait_random_exponential,
    retry_if_exception
)
from google.api_core import exceptions

from src.core.model_factory import ModelFactory
from src.schemas.enums import AnalysisMode, PersonaType
from src.utils.prompt_manager import PromptManager

logger = logging.getLogger(__name__)


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

    async def run_single_pass_analysis(
        self, 
        contents: List[str],
        persona_type: PersonaType,
        project_id: str
    ) -> str:
        """단일 패스 분석 수행"""
        model = ModelFactory.get_model(persona_type)
        
        # Use high-level PromptManager method
        prompt = self.prompt_manager.get_contents_analysis_prompt(
            project_id=project_id,
            combined_summary="\n\n".join(contents)
        )
        
        return await self._safe_generate_content(model, prompt)

    async def run_map_reduce_analysis(
        self,
        contents: List[str],
        persona_type: PersonaType,
        project_id: str
    ) -> str:
        """Map-Reduce 분석 수행 (청킹 단계에서도 동일한 템플릿 사용)"""
        # Map Phase: Flash 모델로 각 콘텐츠 요약
        flash_model = ModelFactory.get_model(PersonaType.SUMMARY_DATA_ANALYST)

        chunk_summaries = []
        for i, chunk in enumerate(contents):
            logger.info(f"Processing chunk {i+1}/{len(contents)}")

            # Use high-level method for chunks
            chunk_prompt = self.prompt_manager.get_contents_analysis_prompt(
                project_id=f"{project_id}_chunk_{i+1}",
                combined_summary=chunk
            )

            result_json = await self._safe_generate_content(flash_model, chunk_prompt)
            summary_text = self._parse_summary(result_json)
            chunk_summaries.append(summary_text)

            await asyncio.sleep(0.1)

        await asyncio.sleep(0.2)
        logger.info("Map phase completed, starting Reduce phase")

        # Reduce Phase: Pro 모델로 통합 분석
        pro_model = ModelFactory.get_model(persona_type)
        final_prompt = self.prompt_manager.get_contents_analysis_prompt(
            project_id=project_id,
            combined_summary="\n---\n".join(chunk_summaries)
        )

        return await self._safe_generate_content(pro_model, final_prompt)

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
    async def _safe_generate_content(self, model, prompt: str) -> str:
        """안전한 모델 호출 및 재시도"""
        try:
            response = await model.generate_content_async(prompt)
            if hasattr(response, 'text'):
                return response.text
            raise ValueError("Invalid response format")
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
