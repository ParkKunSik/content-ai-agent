import pytest
from src.schemas.enums import PersonaType

# Map-Reduce는 시간이 오래 걸리므로 주요 모드만 테스트하거나 필요시 전체 확장
@pytest.mark.asyncio
@pytest.mark.slow
@pytest.mark.parametrize("persona_type", [
    PersonaType.CUSTOMER_FACING_ANALYST,
    PersonaType.CUSTOMER_FACING_SMART_BOT
])
async def test_run_map_reduce_analysis(llm_service, sample_contents, persona_type):
    """
    Map-Reduce 분석 테스트
    - 대량 데이터 처리를 가정한 파이프라인 검증
    """
    print(f"\n🧪 Testing Map-Reduce with Persona: {persona_type.name}")
    
    try:
        project_id = f"test-mr-{persona_type.name.lower()}"
        # PersonaType을 직접 전달
        result = await llm_service.run_map_reduce_analysis(
            sample_contents, 
            persona_type, 
            project_id
        )
        
        assert len(result) > 0, "Result should not be empty"
        assert isinstance(result, str), "Result must be a string"
        
        print(f"✅ Result Length: {len(result)}")
        print(f"✅ Result Preview:\n{result}\n")
        
    except Exception as e:
        if "resource exhausted" in str(e).lower():
            pytest.skip("Skipping due to Quota Limit")
        raise e