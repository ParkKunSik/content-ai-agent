from enum import IntEnum

class FinishReason(IntEnum):
    """
    Vertex AI Candidate Finish Reason Enum.
    Represents the reason why the model stopped generating tokens.
    """
    FINISH_REASON_UNSPECIFIED = 0  # 종료 이유가 지정되지 않음
    STOP = 1                      # 자연스러운 중지 지점 또는 구성된 중지 시퀀스에 도달
    MAX_TOKENS = 2                # 구성된 최대 출력 토큰(maxOutputTokens)에 도달
    SAFETY = 3                    # 콘텐츠에 잠재적인 안전 위반이 포함되어 중지됨
    RECITATION = 4                # 콘텐츠에 잠재적인 저작권 위반(암송)이 포함되어 중지됨
    OTHER = 5                     # 기타 다른 이유로 토큰 생성이 중지됨
    BLOCKLIST = 6                 # 구성된 차단 목록(Blocklist) 용어가 포함되어 중지됨
    PROHIBITED_CONTENT = 7        # 잠재적으로 금지된 콘텐츠가 포함되어 중지됨
    SPII = 8                      # 민감한 개인 식별 정보(SPII)가 포함되어 중지됨
    MALFORMED_FUNCTION_CALL = 9   # 모델이 생성한 함수 호출이 유효하지 않음
    MODEL_ARMOR = 10              # 모델 응답이 Model Armor에 의해 차단됨

    @classmethod
    def from_value(cls, value):
        try:
            return cls(int(value))
        except (ValueError, TypeError):
            return cls.FINISH_REASON_UNSPECIFIED
