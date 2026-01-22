import pytest
import asyncio
from src.schemas.enums import PersonaType

# 모든 페르소나 타입에 대해 테스트 수행
@pytest.mark.asyncio
@pytest.mark.parametrize("persona_type", [
    PersonaType.CUSTOMER_FACING_ANALYST,
    PersonaType.PRO_DATA_ANALYST,
    PersonaType.CUSTOMER_FACING_SMART_BOT
])
async def test_run_single_pass_analysis(llm_service, sample_contents, persona_type):
    """
    Single-Pass 분석 테스트
    - 각 페르소나별로 정상적인 분석 결과가 나오는지 검증
    """
    print(f"\n🧪 Testing Single-Pass with Persona: {persona_type.name}")
    
    # 테스트 간 간격 두기 (할당량 제한 방지)
    await asyncio.sleep(2.0)
    
    try:
        project_id = f"test-single-{persona_type.name.lower()}"
        # PersonaType을 직접 전달
        result = await llm_service.run_single_pass_analysis(
            sample_contents, 
            persona_type, 
            project_id
        )
        
        assert len(result) > 0, "Result should not be empty"
        assert isinstance(result, str), "Result must be a string"
        
        print(f"✅ Persona Type: {persona_type.name}")
        print(f"✅ Result:\n{result}\n")
        
    except Exception as e:
        error_msg = str(e).lower()
        if "resource exhausted" in error_msg or "429" in error_msg:
            pytest.skip("Skipping due to Quota Limit (429)")
        elif "503" in error_msg or "dns resolution failed" in error_msg:
            pytest.skip("Skipping due to temporary network/service issue (503)")
        else:
            raise e
