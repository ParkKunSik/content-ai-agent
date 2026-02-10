from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.schemas.enums.content_type import ExternalContentType
from src.schemas.enums.persona_type import PersonaType
from src.schemas.enums.project_type import ProjectType
from src.schemas.models.common.structured_analysis_refine_result import StructuredAnalysisRefineResult
from src.schemas.models.es.content_analysis_result import (
    ContentAnalysisResultDataV1,
    ContentAnalysisResultDocument,
    ContentAnalysisResultState,
)
from src.schemas.models.prompt.structured_analysis_result import StructuredAnalysisResult
from src.services.es_content_analysis_result_service import ESContentAnalysisResultService


class TestESContentSummaryService:
    
    @pytest.fixture
    def mock_es_client(self):
        """Mock Elasticsearch Client"""
        with patch('src.services.es_content_analysis_result_service.es_manager') as mock_manager:
            mock_client = MagicMock()
            mock_manager.main_client = mock_client
            # index method mock
            mock_client.index.return_value = {"result": "created"}
            # indices.exists mock
            mock_client.indices.exists.return_value = True
            yield mock_client

    @pytest.fixture
    def service(self, mock_es_client):
        return ESContentAnalysisResultService()

    @pytest.mark.asyncio
    async def test_save_result(self, service, mock_es_client):
        """분석 결과 저장 테스트"""
        # Given
        result_data = ContentAnalysisResultDataV1(
            meta_persona=PersonaType.PRO_DATA_ANALYST,
            meta_data=StructuredAnalysisResult(
                summary="test result",
                categories=[]
            ),
            persona=PersonaType.CUSTOMER_FACING_SMART_BOT,
            data=StructuredAnalysisRefineResult(
                summary="refined test result",
                categories=[]
            )
        )
        
        doc = ContentAnalysisResultDocument(
            project_id="12345",
            project_type=ProjectType.FUNDING_AND_PREORDER,
            content_type=ExternalContentType.REVIEW,
            version=1,
            state=ContentAnalysisResultState.COMPLETED,
            result=result_data
        )

        # When
        doc_id = await service.save_result(doc)

        # Then
        assert doc_id == "12345_REVIEW_v1"
        mock_es_client.index.assert_called_once()
        
        # Verify call args
        call_args = mock_es_client.index.call_args
        assert call_args.kwargs['index'] == service.index_name
        assert call_args.kwargs['id'] == doc_id
        assert call_args.kwargs['document']['project_id'] == "12345"
        assert call_args.kwargs['document']['state'] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_save_analysis_result(self, service, mock_es_client):
        """새로운 save_analysis_result 헬퍼 메서드 테스트"""
        # Given
        structured_response = StructuredAnalysisResult(
            summary="분석 요약",
            categories=[]
        )
        refined_result = StructuredAnalysisRefineResult(
            summary="정제된 요약",
            categories=[]
        )

        # When
        doc_id = await service.save_analysis_result(
            project_id="12345",
            project_type=ProjectType.FUNDING_AND_PREORDER,
            content_type=ExternalContentType.REVIEW,
            version=1,
            state=ContentAnalysisResultState.COMPLETED,
            structured_response=structured_response,
            refine_persona=PersonaType.CUSTOMER_FACING_SMART_BOT,
            refined_result=refined_result
        )

        # Then
        assert doc_id == "12345_REVIEW_v1"
        mock_es_client.index.assert_called_once()
        
        # Verify the structure includes result field with V1 data
        call_args = mock_es_client.index.call_args
        document = call_args.kwargs['document']
        assert document['result']['version'] == 1
        assert document['result']['meta_data']['summary'] == "분석 요약"

    @pytest.mark.asyncio
    async def test_get_result_found(self, service, mock_es_client):
        """최신 분석 결과 조회 성공 테스트"""
        # Given
        mock_response = {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "project_id": "12345",
                            "project_type": "FUNDING",
                            "content_type": "REVIEW",
                            "version": 2,
                            "state": "COMPLETED",
                            "created_at": datetime.now(timezone.utc).isoformat(),
                            "updated_at": datetime.now(timezone.utc).isoformat()
                        }
                    }
                ]
            }
        }
        mock_es_client.search.return_value = mock_response

        # When
        result = await service.get_result("12345", ExternalContentType.REVIEW)

        # Then
        assert result is not None
        assert result.version == 2
        assert result.state == ContentAnalysisResultState.COMPLETED
        
        # Verify sort order
        call_args = mock_es_client.search.call_args
        assert call_args.kwargs['sort'] == [{"version": {"order": "desc"}}]

    @pytest.mark.asyncio
    async def test_get_result_not_found(self, service, mock_es_client):
        """분석 결과 없음 테스트"""
        # Given
        mock_es_client.search.return_value = {"hits": {"hits": []}}

        # When
        result = await service.get_result("99999", ExternalContentType.REVIEW)

        # Then
        assert result is None

    @pytest.mark.asyncio
    async def test_get_next_version(self, service, mock_es_client):
        """다음 버전 번호 생성 테스트"""
        # Case 1: Existing document (version 2)
        mock_es_client.search.return_value = {
            "hits": {
                "hits": [
                    {"_source": {"version": 2, "project_id": "1", "project_type": "F", "content_type": "C", "state": "COMPLETED"}}
                ]
            }
        }
        version = await service.get_next_version("1", ExternalContentType.REVIEW)
        assert version == 3

        # Case 2: No document
        mock_es_client.search.return_value = {"hits": {"hits": []}}
        version = await service.get_next_version("1", ExternalContentType.REVIEW)
        assert version == 1

    @pytest.mark.asyncio
    async def test_update_state(self, service, mock_es_client):
        """상태 업데이트 테스트"""
        # When
        await service.update_state(
            "12345", ExternalContentType.REVIEW, 1, 
            ContentAnalysisResultState.FAIL, "Timeout"
        )

        # Then
        mock_es_client.update.assert_called_once()
        call_args = mock_es_client.update.call_args
        assert call_args.kwargs['id'] == "12345_REVIEW_v1"
        assert call_args.kwargs['body']['doc']['state'] == ContentAnalysisResultState.FAIL
        assert call_args.kwargs['body']['doc']['reason'] == "Timeout"