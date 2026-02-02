from enum import Enum


class SentimentType(str, Enum):
    """
    카테고리별 감정 유형을 나타내는 Enum.
    평균 감정 점수에 따라 분류됩니다.
    """
    NEGATIVE = "negative"    # 평균 점수 < 0.45
    POSITIVE = "positive"    # 평균 점수 >= 0.55  
    NEUTRAL = "neutral"      # 0.45 <= 평균 점수 < 0.55

    @classmethod
    def from_average_score(cls, avg_score: float) -> "SentimentType":
        """
        평균 감정 점수를 기반으로 SentimentType을 결정
        
        Args:
            avg_score: 평균 감정 점수 (0.0~1.0)
            
        Returns:
            SentimentType: 해당하는 감정 유형
        """
        if avg_score < 0.45:
            return cls.NEGATIVE
        elif avg_score >= 0.55:
            return cls.POSITIVE
        else:
            return cls.NEUTRAL