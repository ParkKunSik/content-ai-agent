# 콘텐츠 분석 AI Agent (Content Analysis AI Agent)

**Content Analysis AI Agent**는 프로젝트 단위로 전달된 대량의 콘텐츠를 분석하고, 선택한 **페르소나(Persona)**의 관점에서 심층적인 요약 및 인사이트를 제공하는 지능형 서비스입니다.

Google Vertex AI의 **Gemini 2.5 Pro**와 **Gemini 2.5 Flash** 모델을 활용하여, 효율적인 단일 패스(Single-Pass) 분석과 대용량 처리를 위한 맵-리듀스(Map-Reduce) 전략을 자동으로 수행합니다.

---

## 🚀 주요 기능 (Key Features)

*   **프로젝트 단위 통합 분석:** 개별 문서가 아닌 프로젝트 전체의 맥락을 이해하는 통합 요약 및 리포트를 생성합니다.
*   **페르소나 기반 관점 제공 (Role-Playing):**
    *   `CUSTOMER_FACING_ANALYST`: 고객의 관점에서 제품의 가치를 발견하고 정중하게 전달하는 전문가.
    *   `PRO_DATA_ANALYST`: 사실과 수치에 기반하여 패턴을 도출하는 냉철한 데이터 분석가.
    *   `CUSTOMER_FACING_SMART_BOT`: 방대한 리뷰의 핵심을 절제된 표현으로 스마트하게 요약하는 봇.
*   **하이브리드 오케스트레이션 (Hybrid Strategy):**
    *   **Single-Pass:** 데이터가 적을 경우 고성능 모델(Pro)을 사용하여 즉시 분석합니다.
    *   **Map-Reduce:** 데이터가 방대할 경우(500k 토큰 이상) 고속 모델(Flash)로 청킹 요약 후 Pro 모델로 최종 통합합니다.
*   **프롬프트 템플릿 엔진 & Controlled Generation:**
    *   `Jinja2`를 활용한 동적 프롬프트 생성과 함께, Vertex AI의 `response_schema` 기능을 도입하여 100% 유효한 JSON 출력을 보장합니다.
    *   Pydantic 모델을 통해 데이터 구조와 지침을 일원화하여 관리합니다.
*   **엔터프라이즈급 안정성:**
    *   **Tenacity Retry:** API 할당량 초과(429) 및 일시적 서버 오류에 대한 자동 재시도 로직이 적용되어 있습니다.
    *   **Validation:** 10MB 파일 크기 제한 및 사전 검증을 통해 안정적인 리소스 관리를 지원합니다.

---

## 🛠 기술 스택 (Tech Stack)

*   **Language:** Python 3.10+
*   **AI Platform:** Google Vertex AI (Gemini 2.5 Pro / 2.5 Flash)
*   **Framework:** FastAPI (비동기 API 서버)
*   **Data Store:** Redis, Elasticsearch SaaS
*   **Infrastructure:** Docker, Docker Compose
*   **Testing:** pytest (Asyncio 기반 통합 테스트)

---

## 🏗 프로젝트 구조 (Directory Structure)

```
src/
├── agent/          # Agent 진입점 및 코어 클래스 정의
├── api/            # API 라우터 및 엔드포인트 정의
├── core/           # 설정(Config), 모델 팩토리(ModelFactory), 상수
├── loaders/        # 데이터 수집 (GCS, Local File)
├── prompts/        # Jinja2 템플릿 (System, Task)
├── schemas/        # Pydantic 모델 및 Enum (PersonaType, AnalysisMode)
├── services/       # 핵심 로직 (Orchestrator, LLMService)
└── utils/          # 공통 유틸리티 (PromptManager, PromptRenderer)
```

---

## 📦 의존성 관리 (Dependency Management)

프로젝트는 용도에 따라 두 가지 의존성 파일을 제공합니다.

*   **`requirements.txt`**: 운영 환경 및 배포용 필수 패키지 목록. (Vertex AI SDK, Pydantic, Redis, Elasticsearch, FastAPI 등)
*   **`requirements-dev.txt`**: 로컬 개발 및 테스트를 위한 추가 패키지 포함. (pytest, ruff, black 등)

---

## 🚦 시작하기 (Getting Started)

### 1. 환경 설정
프로젝트 루트에 `.env.local` 파일을 생성하고 필요한 GCP 및 인프라 설정을 입력합니다.

```bash
cp .env.local.example .env.local
```

### 2. 인프라 실행 (선택 사항)
필요한 경우 도커를 통해 추가 인프라를 실행합니다. (현재 핵심 기능은 외부 인프라 의존성 없음)

```bash
docker-compose up -d
```

### 3. 서버 실행 (로컬 개발 모드)
가상환경을 구축하고 **개발용 의존성**을 설치한 후 FastAPI 서버를 가동합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate

# 개발용 패키지 포함 설치
pip install -r requirements-dev.txt

# 서버 실행
uvicorn src.main:app --reload
```

---

## 🧪 테스트 (Testing)

분리된 테스트 파일을 통해 각 페르소나별 동작과 Map-Reduce 로직을 검증할 수 있습니다.

```bash
# 전체 테스트 실행 (실행 시간 포함)
pytest

# Single-Pass 분석 단독 테스트
pytest tests/test_single_pass.py

# Map-Reduce 분산 처리 테스트
pytest tests/test_map_reduce.py
```
