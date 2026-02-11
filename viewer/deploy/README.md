# Content Viewer - AWS Lambda 배포 가이드

## 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                        AWS Cloud                                │
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐                            │
│  │ API Gateway │───▶│   Lambda    │───────┐                    │
│  │  (REST)     │    │  (FastAPI)  │       │                    │
│  └─────────────┘    └─────────────┘       │                    │
└───────────────────────────────────────────┼────────────────────┘
                                            │
                                            ▼
                               ┌─────────────────────┐
                               │  Elasticsearch SaaS │
                               │   (Elastic Cloud)   │
                               └─────────────────────┘
```

## 배포 후 생성되는 AWS 리소스

| 리소스 | 이름 | 설명 |
|--------|------|------|
| **CloudFormation Stack** | `content-viewer-dev` | 모든 리소스를 묶어서 관리 |
| **Lambda Function** | `community-summary-viewer` | FastAPI 앱 실행 |
| **API Gateway** | `community-data` | HTTPS 엔드포인트 제공 |

**API Gateway URL 형식:**
```
https://{api-id}.execute-api.ap-northeast-2.amazonaws.com/dev/viewer/
```

---

## 사전 요구사항

1. **AWS CLI** 설치 및 설정
   ```bash
   aws configure
   ```

2. **AWS SAM CLI** 설치
   ```bash
   # macOS
   brew install aws-sam-cli

   # pip
   pip install aws-sam-cli
   ```

---

## 설정 파일 수정 항목

### samconfig.toml (필수 수정)

배포 시 **반드시 수정**해야 하는 파일입니다.

| 항목 | 수정 필요 | 설명 | 예시 |
|------|:--------:|------|------|
| `ESHost` | **필수** | Elasticsearch SaaS URL | `https://your-cluster.es.ap-northeast-2.aws.elastic-cloud.com` |
| `ESUsername` | **필수** | ES 인증 사용자명 | `elastic` |
| `ESPassword` | **필수** | ES 인증 비밀번호 | `your-password` |
| `ESIndex` | 선택 | ES 인덱스명 (기본값 사용 가능) | `core-content-analysis-result` |
| `region` | 선택 | AWS 리전 (기본값: 서울) | `ap-northeast-2` |

```toml
# deploy/samconfig.toml

[dev.deploy.parameters]
parameter_overrides = [
    "Environment=dev",
    "ESHost=https://your-cluster.es.ap-northeast-2.aws.elastic-cloud.com",  # ← 수정 필수
    "ESUsername=elastic",                                                    # ← 수정 필수
    "ESPassword=your-password",                                              # ← 수정 필수
    "ESIndex=core-content-analysis-result",                                  # ← 필요시 수정
]
```

### template.yaml (리소스 이름 확인 필요)

AWS에 생성된 **실제 리소스 이름과 일치**해야 합니다.

#### 리소스 이름 (실제 AWS 리소스와 일치 필요)

| 항목 | 현재 값 | 파일 내 위치 | 설명 |
|------|---------|-------------|------|
| `FunctionName` | `community-summary-viewer` | template.yaml (63행) | Lambda 함수 이름 |
| `Name` (API Gateway) | `community-data` | template.yaml (106행) | API Gateway 이름 |
| `stack_name` | `content-viewer-dev` | samconfig.toml (12행) | CloudFormation 스택 이름 |

```yaml
# deploy/template.yaml - 리소스 이름 (AWS와 일치 필요)

ViewerFunction:
  Properties:
    FunctionName: community-summary-viewer    # ← Lambda 함수 이름

ViewerApi:
  Properties:
    Name: community-data                      # ← API Gateway 이름
```

```toml
# deploy/samconfig.toml - 스택 이름

[dev.deploy.parameters]
stack_name = "content-viewer-dev"             # ← CloudFormation 스택 이름
```

#### 성능 설정 (필요시 조정)

| 항목 | 기본값 | 설명 | 수정 시점 |
|------|--------|------|----------|
| `Timeout` | 30초 | Lambda 최대 실행 시간 | ES 응답이 느린 경우 증가 |
| `MemorySize` | 512MB | Lambda 메모리 | 콜드 스타트 개선 필요 시 증가 |

```yaml
# deploy/template.yaml (필요시에만 수정)

Globals:
  Function:
    Timeout: 30        # ES 응답 느리면 60으로 증가
    MemorySize: 512    # 콜드 스타트 느리면 1024로 증가
```

---

## 배포 방법

```bash
cd viewer

# 배포 스크립트 실행
./deploy/deploy.sh          # dev 환경 배포
```

### 2. 배포 결과 확인

```bash
# Stack 출력값 확인
aws cloudformation describe-stacks \
    --stack-name content-viewer-dev \
    --query "Stacks[0].Outputs"

# API 테스트
curl https://xxx.execute-api.ap-northeast-2.amazonaws.com/dev/viewer/health
```

## CloudFormation 파라미터

| 파라미터 | 필수 | 기본값 | 설명 |
|---------|-----|--------|------|
| `Environment` | O | dev | 배포 환경 |
| `ESHost` | O | - | Elasticsearch SaaS URL |
| `ESUsername` | X | '' | ES 사용자명 |
| `ESPassword` | X | '' | ES 비밀번호 |
| `ESIndex` | X | core-content-analysis-result | ES 인덱스명 |

## 수동 배포 (SAM CLI)

```bash
cd viewer

# 1. requirements.txt 생성
cat > requirements.txt << 'EOF'
fastapi
jinja2
pydantic>=2.0.0
pydantic-settings
python-dotenv
elasticsearch>=8.0.0,<9.0.0
requests
mangum>=0.17.0
EOF

# 2. 빌드
sam build --template-file deploy/template.yaml

# 3. 배포
sam deploy --config-env dev

# 4. 정리
rm requirements.txt
```

## 삭제

```bash
# Stack 삭제
aws cloudformation delete-stack --stack-name content-viewer-dev

# 삭제 완료 대기
aws cloudformation wait stack-delete-complete --stack-name content-viewer-dev
```

---

## Lambda UI 배포 (SAM 없이)

S3/CloudFormation 권한이 없는 경우 **Lambda 콘솔에서 직접 배포**할 수 있습니다.

### 의존성 파일 비교

| 배포 방식 | 의존성 파일 | 이유 |
|----------|------------|------|
| **SAM** | `requirements.txt` 필요 | SAM 빌드가 requirements.txt만 인식 |
| **Lambda UI** | `pyproject.toml` 사용 | 로컬에서 pip install로 직접 패키징 |

### 1. 코드 패키징 (로컬)

```bash
cd viewer

# 패키지 디렉토리 생성
rm -rf package && mkdir package

# 의존성 설치 (pyproject.toml 기반)
pip install . --target package/           # 기본 의존성
pip install mangum --target package/      # Lambda 어댑터

# Lambda 코드 복사
cp -r viewer/* package/

# zip 파일 생성
cd package && zip -r ../lambda-package.zip . && cd ..

# 결과: lambda-package.zip (약 20-30MB)
```

> `pip install .` 명령이 `pyproject.toml`의 dependencies를 읽어서 설치합니다.

### 2. Lambda 콘솔 업로드

| 단계 | 설명 |
|------|------|
| 1 | AWS Lambda 콘솔 → `community-summary-viewer` 함수 선택 |
| 2 | **코드** 탭 → **Upload from** → `.zip file` 선택 |
| 3 | `lambda-package.zip` 업로드 |
| 4 | **런타임 설정** → 핸들러: `viewer.main.handler` 확인 |

### 3. 환경변수 설정 (Lambda 콘솔)

Lambda 콘솔 → **구성** → **환경 변수**:

| 변수 | 값 | 설명 |
|------|-----|------|
| `ES_HOST` | `https://your-es.com` | ES SaaS URL (필수) |
| `ES_USERNAME` | `elastic` | ES 사용자명 (필수) |
| `ES_PASSWORD` | `your-password` | ES 비밀번호 (필수) |
| `ES_INDEX` | `core-content-analysis-result` | ES 인덱스명 |
| `ES_USE_SSL` | `true` | SSL 사용 |
| `ES_VERIFY_CERTS` | `true` | 인증서 검증 |

### 4. API Gateway 연결 (이미 생성된 경우)

API Gateway 콘솔 → `community-data`:

| 단계 | 설명 |
|------|------|
| 1 | **리소스** → `/{proxy+}` 경로 확인 (없으면 생성) |
| 2 | **메서드** → `ANY` 선택 → Lambda 함수 연결 |
| 3 | **Lambda 프록시 통합** 체크 |
| 4 | **API 배포** → 스테이지: `dev` |

### 5. 배포 확인

```bash
# API 테스트
curl https://{api-id}.execute-api.ap-northeast-2.amazonaws.com/dev/viewer/health
```

---

## 문제 해결

### Lambda 타임아웃

ES 응답이 느린 경우 `template.yaml`에서 타임아웃 조정:
```yaml
Globals:
  Function:
    Timeout: 60  # 기본 30초에서 증가
```

### ES 연결 실패

1. ES 호스트 URL 형식 확인 (https:// 포함)
2. ES 인증 정보 확인
3. ES SaaS의 IP 화이트리스트 설정 확인 (필요시 Lambda NAT Gateway 구성)

### 콜드 스타트 개선

Lambda 콜드 스타트가 느린 경우:
- MemorySize 증가 (512MB → 1024MB)
- Provisioned Concurrency 설정
