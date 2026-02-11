# Content Analysis Viewer

ES에 저장된 콘텐츠 분석 결과를 조회하는 독립 웹 서비스입니다.

## 특징

- **독립 배포**: 메인 Agent와 분리되어 독립적으로 배포 가능
- **최소 의존성**: ES 연결 + FastAPI만 필요 (GCP SDK 불필요)
- **Lambda 지원**: AWS Lambda + API Gateway 배포 지원

## 설치

```bash
cd viewer

# 가상환경 생성 (.venv-viewer로 구분)
python3 -m venv .venv-viewer
source .venv-viewer/bin/activate

# 로컬 개발용
pip install -e ".[server]"

# Lambda 배포용
pip install -e ".[lambda]"

# Streamlit 뷰어 포함
pip install -e ".[streamlit]"
```

## 환경 설정

```bash
cp .env.example .env
# .env 파일 편집
```

### 필수 환경변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `ES_HOST` | Elasticsearch 호스트 | localhost |
| `ES_PORT` | Elasticsearch 포트 | 9200 |
| `ES_USERNAME` | ES 인증 사용자 | (없음) |
| `ES_PASSWORD` | ES 인증 비밀번호 | (없음) |
| `ES_INDEX` | 분석 결과 인덱스 | core-content-analysis-result |

## 실행

### 로컬 개발

```bash
# FastAPI 서버 실행
uvicorn viewer.main:app --reload --port 8787

# 브라우저 접속
http://localhost:8787/

# 서버 중단
Ctrl+C
```

### Streamlit 뷰어

```bash
# Streamlit 앱 실행
streamlit run viewer/streamlit/app.py --server.port 8701

# 브라우저 접속
http://localhost:8701/

# 앱 중단
Ctrl+C
```

### Lambda 배포

```bash
# 패키지 생성
pip install . -t package/
cd package && zip -r ../deployment.zip .

# Lambda 설정
Handler: viewer.main.handler
Runtime: Python 3.10+
```

## 프로젝트 구조

```
viewer/
├── pyproject.toml          # 의존성 관리
├── README.md
├── .env.example
│
└── viewer/                 # Python 패키지
    ├── main.py             # FastAPI + Lambda handler
    ├── config.py           # 설정 (ES 연결)
    ├── api/
    │   └── routes.py       # API 라우터
    ├── services/
    │   ├── es_client.py    # ES 클라이언트
    │   └── data_service.py # 데이터 조회
    ├── schemas/
    │   ├── enums.py        # ContentType 등
    │   └── models.py       # Pydantic 모델
    └── templates/          # Jinja2 템플릿
```

## API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| GET | `/` | 프로젝트 목록 (페이징) |
| GET | `/{project_id}` | 프로젝트 상세 |
| GET | `/health` | 헬스체크 |
