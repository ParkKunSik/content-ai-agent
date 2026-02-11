# Content Analysis Viewer

ES에 저장된 콘텐츠 분석 결과를 조회하는 독립 웹 서비스입니다.

## 특징

- **독립 배포**: 메인 Agent와 분리되어 독립적으로 배포 가능
- **최소 의존성**: ES 연결 + FastAPI만 필요 (GCP SDK 불필요)
- **Lambda 지원**: AWS Lambda + API Gateway 배포 지원 (SAM)

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
| `ES_PORT` | Elasticsearch 포트 | (없음) |
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

## AWS Lambda 배포

### 사전 요구사항

- AWS CLI 설치 및 설정 (`aws configure`)
- AWS SAM CLI 설치 (`brew install aws-sam-cli`)

### 배포 (SAM)

```bash
cd viewer

# 1. samconfig.toml 설정 수정
vi deploy/samconfig.toml

# 2. 배포 스크립트 실행
chmod +x deploy/deploy.sh
./deploy/deploy.sh          # dev 환경 배포
```

### 배포 파라미터 설정

`deploy/samconfig.toml`에서 환경별 ES 설정:

```toml
[dev.deploy.parameters]
parameter_overrides = [
    "Environment=dev",
    "ESHost=https://your-es-host.com",
    "ESUsername=your-username",
    "ESPassword=your-password",
]
```

### 배포 결과

```
API URL: https://xxx.execute-api.ap-northeast-2.amazonaws.com/dev/
```

자세한 배포 가이드는 [deploy/README.md](deploy/README.md)를 참조하세요.

## 프로젝트 구조

```
viewer/
├── pyproject.toml          # 의존성 관리
├── README.md
├── .env.example
│
├── deploy/                 # AWS 배포 설정
│   ├── template.yaml       # CloudFormation/SAM 템플릿
│   ├── samconfig.toml      # SAM 환경별 설정
│   ├── deploy.sh           # 배포 스크립트
│   └── README.md           # 배포 가이드
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
    ├── streamlit/          # Streamlit 뷰어
    │   ├── app.py
    │   └── renderer.py
    └── templates/          # Jinja2 템플릿
```

## API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| GET | `/viewer/` | 프로젝트 목록 (페이징) |
| GET | `/viewer/{project_id}` | 프로젝트 상세 |
| GET | `/viewer/health` | 헬스체크 |
