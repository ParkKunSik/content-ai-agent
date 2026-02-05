# 콘텐츠 분석 AI Agent (Content Analysis AI Agent)

**Content Analysis AI Agent**는 프로젝트 단위로 전달된 대량의 콘텐츠를 분석하고, 선택한 **페르소나(Persona)**의 관점에서 심층적인 요약 및 인사이트를 제공하는 지능형 서비스입니다.

Google Vertex AI의 **Gemini 2.5/3.0** 모델을 활용하여, 효율적인 단일 패스(Single-Pass) 분석과 대용량 처리를 위한 맵-리듀스(Map-Reduce) 전략을 자동으로 수행합니다.

---

## 🚀 주요 기능 (Key Features)

*   **프로젝트 단위 통합 분석:** 개별 문서가 아닌 프로젝트 전체의 맥락을 이해하는 통합 요약 및 리포트를 생성합니다.
*   **페르소나 기반 관점 제공 (Role-Playing):**
    *   `PRO_DATA_ANALYST`: 사실과 수치에 기반하여 패턴을 도출하는 냉철한 데이터 분석가.
    *   `CUSTOMER_FACING_SMART_BOT`: 방대한 리뷰의 핵심을 절제된 표현으로 스마트하게 요약하는 봇.
*   **고급 시각화 보고서:** 아마존 스타일의 인터랙티브 HTML 보고서를 생성하며, 모달 창을 통해 하이라이트의 원본 콘텐츠를 즉시 확인할 수 있습니다.
*   **2단계 심층 분석 프로세스 (2-Step Analysis):**
    *   **Step 1. 구조화 및 추출 (Structuring):** 비정형 데이터를 카테고리, 감정, 하이라이트 등 정형 구조로 변환.
    *   **Step 2. 요약 정제 (Refinement):** 생성된 분석 데이터를 바탕으로 페르소나별 최적의 요약문 생성.
*   **프롬프트 템플릿 엔진 & Controlled Generation:**
    *   `Jinja2`를 활용한 동적 프롬프트 생성과 함께, Vertex AI의 `response_schema` 기능을 도입하여 100% 유효한 JSON 출력을 보장합니다.
    *   Pydantic 모델을 통해 데이터 구조와 지침을 일원화하여 관리합니다.
*   **Elasticsearch 통합:** 기존 와디즈 데이터를 조회하고 분석 결과를 영구 저장하여 버전별 관리가 가능합니다.

---

## 🛠 기술 스택 (Tech Stack)

*   **Language:** Python 3.10+
*   **AI Platform:** Google Vertex AI (Gemini 2.5 / 3.0 Pro & Flash)
*   **Framework:** FastAPI (비동기 API 서버)
*   **Data Store:** Redis, Elasticsearch
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

프로젝트는 **`pyproject.toml`**을 사용하여 의존성을 표준화된 방식으로 관리합니다.

*   **운영 의존성 (`dependencies`)**: 배포 및 실행에 필수적인 패키지 (Vertex AI SDK, Pydantic, FastAPI 등).
*   **개발 의존성 (`dev`)**: 로컬 개발, 테스트, 린팅을 위한 추가 패키지 (pytest, ruff, black 등).

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
가상환경을 구축하고 **개발용 의존성**을 포함하여 패키지를 설치한 후 FastAPI 서버를 가동합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate

# 개발용 패키지 포함 설치 (Editable 모드 권장)
pip install -e ".[dev]"

# 운영용 필수 패키지만 설치할 경우
pip install .

# 서버 실행 (.venv 환경에서)
source .venv/bin/activate
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. API 문서 확인
서버 실행 후 다음 URL에서 API 문서를 확인할 수 있습니다.

```bash
# 서버 Health Check
curl http://localhost:8000/health

# Swagger UI (Interactive API Documentation)
http://localhost:8000/docs

# ReDoc (Alternative API Documentation)
http://localhost:8000/redoc
```

#### 주요 API 엔드포인트

| Method | Endpoint | 설명 |
|--------|----------|------|
| `GET` | `/health` | 서버 상태 확인 |
| `POST` | `/analysis` | 콘텐츠 직접 분석 (파일 업로드) |
| `POST` | `/project-analysis` | 프로젝트 기반 분석 (ES 조회) |

**프로젝트 분석 예제:**
```json
{
  "project_id": 365330,
  "project_type": "FUNDING",
  "content_type": "REVIEW",
  "analysis_mode": "REVIEW_BOT",
  "force_refresh": false
}
```

---

## 🧪 테스트 (Testing)

분리된 테스트 파일을 통해 각 단계별 동작과 통합 플로우를 검증할 수 있습니다.

```bash
# 전체 테스트 실행 (실행 시간 포함)
pytest

# 콘텐츠 분석 통합 플로우 테스트
pytest tests/integration/test_content_analysis_flow.py

# HTML/PDF 생성 결과물 검증 테스트
pytest tests/integration/test_html_generation.py
```
