# 템플릿 엔진 기반 Viewer 설계 문서

## 1. 개요

### 1.1 목표
- Streamlit 기반 Viewer와 FastAPI + Jinja2 템플릿 방식 **병행** 지원
- HTML/CSS/JS 분리로 유지보수성 향상
- 별도 포트 없이 기존 API 서버에서 HTML 서빙

### 1.2 현재 상태 (구현 완료)
- **Viewer 옵션 1**: Streamlit 기반 (`streamlit run src/viewer/app.py --server.port 8501`)
- **Viewer 옵션 2**: FastAPI + Jinja2 (`http://localhost:8000/viewer/`)
- **HTML 생성**: Jinja2 템플릿 파일 분리 + 기존 RefineResultRenderer 유지
- **의존성**: `streamlit>=1.30.0` (optional), Jinja2 (core)

### 1.3 사용 방법
```bash
# 옵션 1: Streamlit 뷰어 (개발/디버깅용)
streamlit run src/viewer/app.py --server.port 8501

# 옵션 2: FastAPI 뷰어 (운영/통합용)
uvicorn src.main:app --host 0.0.0.0 --port 8000
# 브라우저: http://localhost:8000/viewer/
```

---

## 2. 아키텍처 설계

### 2.1 현재 구조
```
Streamlit App (port 8501)
    ↓
ViewerDataService (ES 조회)
    ↓
RefineResultRenderer.generate_amazon_style_html()
    ↓
st.components.v1.html() (렌더링)
```

### 2.2 목표 구조
```
FastAPI (기존 API 서버)
    ↓
ViewerDataService (ES 조회) ← 재사용
    ↓
Jinja2Templates.TemplateResponse()
    ↓
templates/viewer.html (템플릿 파일)
```

---

## 3. 파일 구조

### 3.1 신규 생성 파일
```
src/
├── templates/                         # Jinja2 템플릿 디렉토리
│   ├── base.html                      # 공통 레이아웃 (head, scripts)
│   ├── viewer.html                    # 뷰어 메인 페이지
│   ├── viewer_list.html               # 프로젝트 목록 페이지
│   └── components/                    # 재사용 컴포넌트
│       ├── project_info.html          # 프로젝트 정보 섹션
│       ├── category_grid.html         # 카테고리 버튼 그리드
│       ├── category_detail.html       # 카테고리 상세 정보
│       └── modal.html                 # 원본 콘텐츠 모달
├── static/                            # 정적 파일
│   ├── css/
│   │   └── viewer.css                 # 뷰어 스타일 (기존 인라인 CSS 분리)
│   └── js/
│       └── viewer.js                  # 뷰어 스크립트 (기존 인라인 JS 분리)
└── api/
    └── viewer_routes.py               # 뷰어 전용 라우터 (신규)
```

### 3.2 수정 파일
| 파일 | 수정 내용 |
|------|----------|
| `src/main.py` | 정적 파일 마운트, 뷰어 라우터 등록 |
| `src/api/routes.py` | (선택) 뷰어 라우트 추가 또는 별도 파일로 분리 |

### 3.3 유지 파일 (호환성)
| 파일 | 설명 |
|------|------|
| `src/viewer/app.py` | Streamlit 버전 유지 (선택적 사용) |
| `src/viewer/refine_result_renderer.py` | PDF 생성 등 다른 용도로 유지 가능 |
| `src/viewer/viewer_data_service.py` | 그대로 재사용 |

---

## 4. 핵심 구현 상세

### 4.1 FastAPI 설정
```python
# src/main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()

# 정적 파일 서빙
app.mount("/static", StaticFiles(directory="src/static"), name="static")

# 템플릿 설정
templates = Jinja2Templates(directory="src/templates")
```

### 4.2 뷰어 라우터
```python
# src/api/viewer_routes.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.viewer.viewer_data_service import ViewerDataService

router = APIRouter(prefix="/viewer", tags=["viewer"])
templates = Jinja2Templates(directory="src/templates")

@router.get("/", response_class=HTMLResponse)
async def viewer_list(request: Request):
    """프로젝트 목록 페이지"""
    service = ViewerDataService()
    project_ids = service.get_project_ids()

    # 프로젝트 정보 조회
    projects = []
    for pid in project_ids[:20]:  # 최근 20개
        info = service.get_project_info(int(pid))
        content_types = service.get_content_types_by_project(pid)
        projects.append({
            "id": pid,
            "title": info.title if info else f"프로젝트 {pid}",
            "thumbnail_url": info.thumbnail_url if info else None,
            "content_types": content_types
        })

    return templates.TemplateResponse("viewer_list.html", {
        "request": request,
        "projects": projects
    })

@router.get("/{project_id}", response_class=HTMLResponse)
async def viewer_detail(
    request: Request,
    project_id: int,
    content_type: str = "REVIEW"
):
    """프로젝트 분석 결과 상세 페이지"""
    service = ViewerDataService()

    # 데이터 조회
    result_doc = service.get_result(str(project_id), content_type)
    project_info = service.get_project_info(project_id)
    content_types = service.get_content_types_by_project(str(project_id))

    if not result_doc or not result_doc.result:
        return templates.TemplateResponse("viewer_error.html", {
            "request": request,
            "error": "분석 결과가 없습니다."
        })

    return templates.TemplateResponse("viewer.html", {
        "request": request,
        "project_id": project_id,
        "project_info": project_info,
        "content_type": content_type,
        "content_types": content_types,
        "result": result_doc.result.data,
        "updated_at": str(result_doc.updated_at)[:19] if result_doc.updated_at else "N/A"
    })
```

### 4.3 템플릿 예시

#### base.html
```html
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}커뮤니티 요약 뷰어{% endblock %}</title>
    <link rel="stylesheet" href="{{ url_for('static', path='css/viewer.css') }}">
    {% block extra_css %}{% endblock %}
</head>
<body>
    {% block content %}{% endblock %}

    <script src="{{ url_for('static', path='js/viewer.js') }}"></script>
    {% block extra_js %}{% endblock %}
</body>
</html>
```

#### viewer.html
```html
{% extends "base.html" %}

{% block title %}고객 리뷰 요약 - 프로젝트 {{ project_id }}{% endblock %}

{% block content %}
<div class="header">
    <div class="meta-info">
        프로젝트 ID: {{ project_id }} |
        콘텐츠 타입: {{ content_type }} |
        생성일시: {{ updated_at }}
    </div>
</div>

{% if project_info %}
{% include "components/project_info.html" %}
{% endif %}

<h1>고객 의견: {{ content_type }}</h1>

<div class="summary-section">
    {{ result.summary }}
    <span class="ai-badge">ai</span> AI 기반 고객 리뷰 텍스트에서 생성됨
</div>

<div class="learn-more">자세히 알아보려면 선택하세요</div>

{% include "components/category_grid.html" %}

{% for category in result.categories %}
{% include "components/category_detail.html" %}
{% endfor %}

{% include "components/modal.html" %}

<div class="footer">
    Generated by Content AI Agent | Wadiz
</div>
{% endblock %}
```

---

## 5. URL 설계

| URL | 메서드 | 설명 |
|-----|--------|------|
| `/viewer/` | GET | 프로젝트 목록 페이지 |
| `/viewer/{project_id}` | GET | 분석 결과 상세 (기본: REVIEW) |
| `/viewer/{project_id}?content_type=QNA` | GET | 특정 content_type 조회 |
| `/static/css/viewer.css` | GET | CSS 파일 |
| `/static/js/viewer.js` | GET | JS 파일 |

---

## 6. 마이그레이션 계획

### Phase 1: 기반 구조 생성 (0.5일) ✅ 완료
- [x] `src/templates/` 디렉토리 생성
- [x] `src/static/css/`, `src/static/js/` 디렉토리 생성
- [x] `src/main.py`에 StaticFiles, Templates 설정 추가

### Phase 2: CSS/JS 분리 (0.5일) ✅ 완료
- [x] `RefineResultRenderer`의 인라인 CSS → `src/static/css/viewer.css`
- [x] `RefineResultRenderer`의 인라인 JS → `src/static/js/viewer.js`

### Phase 3: 템플릿 작성 (1일) ✅ 완료
- [x] `base.html` 공통 레이아웃 작성
- [x] `viewer.html` 메인 템플릿 작성
- [x] `viewer_list.html` 목록 페이지 작성
- [x] `components/*.html` 컴포넌트 분리

### Phase 4: 라우터 구현 (0.5일) ✅ 완료
- [x] `src/api/viewer_routes.py` 생성
- [x] `src/main.py`에 라우터 등록
- [x] ViewerDataService 연동 테스트

### Phase 5: 검증 및 정리 (0.5일) ✅ 완료
- [x] 기존 Streamlit 뷰어와 동일 결과 확인
- [x] 반응형 레이아웃 테스트
- [x] Streamlit 의존성 유지 (두 방식 병행 사용 가능)

---

## 7. Phase 세부 작업 문서

> **Note**: git으로 관리되는 파일 수정 시 반드시 git 명령 사용

### Phase 1 세부 작업

#### 1.1 디렉토리 생성
```bash
mkdir -p src/templates/components
mkdir -p src/static/css
mkdir -p src/static/js
```

#### 1.2 main.py 수정
```python
# 추가할 코드
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# 정적 파일 마운트 (라우터 등록 전에)
app.mount("/static", StaticFiles(directory="src/static"), name="static")

# 뷰어 라우터 등록
from src.api.viewer_routes import router as viewer_router
app.include_router(viewer_router)
```

#### 1.3 완료 조건
- [ ] `/static/` 경로로 파일 접근 가능
- [ ] 기존 API 엔드포인트 정상 동작

---

### Phase 2 세부 작업

#### 2.1 CSS 분리
- `RefineResultRenderer`의 `<style>` 블록 내용 추출
- `src/static/css/viewer.css`로 저장
- f-string 변수 (`{{`, `}}`) → 일반 중괄호 (`{`, `}`)로 변환

#### 2.2 JS 분리
- `RefineResultRenderer`의 `<script>` 블록 내용 추출
- `src/static/js/viewer.js`로 저장
- f-string 변수 변환

#### 2.3 완료 조건
- [ ] CSS 파일 단독 로드 가능 (`/static/css/viewer.css`)
- [ ] JS 파일 단독 로드 가능 (`/static/js/viewer.js`)

---

### Phase 3 세부 작업

#### 3.1 base.html 작성
| 섹션 | 내용 |
|------|------|
| `<head>` | charset, viewport, title block, CSS 링크 |
| `<body>` | content block, JS 스크립트 |

#### 3.2 viewer.html 구조
| 섹션 | 원본 위치 (RefineResultRenderer) |
|------|--------------------------------|
| header | 라인 409-413 |
| project_info | 라인 417-427 |
| summary | 라인 429-440 |
| category_grid | 라인 443-465 |
| category_detail | 라인 472-526 |
| modal | 라인 529-540 |
| footer | 라인 543-545 |

#### 3.3 Jinja2 변환 예시
```python
# Python f-string (원본)
f"""<div class="meta-info">
    프로젝트 ID: {project_id} | 콘텐츠 타입: {content_type}
</div>"""

# Jinja2 템플릿 (변환 후)
"""<div class="meta-info">
    프로젝트 ID: {{ project_id }} | 콘텐츠 타입: {{ content_type }}
</div>"""
```

#### 3.4 반복문 변환
```python
# Python (원본)
for idx, category in enumerate(categories):
    html_content += f"""<div onclick="toggleCategory({idx})">..."""

# Jinja2 (변환 후)
{% for category in categories %}
<div onclick="toggleCategory({{ loop.index0 }})">...
{% endfor %}
```

---

### Phase 4 세부 작업

#### 4.1 viewer_routes.py 생성
| 엔드포인트 | 기능 |
|-----------|------|
| `GET /viewer/` | 프로젝트 목록 |
| `GET /viewer/{project_id}` | 상세 페이지 |

#### 4.2 ViewerDataService 연동
- 기존 `src/viewer/viewer_data_service.py` 그대로 import
- ES 연결 설정은 기존과 동일 (`.env.local` 사용)

---

### Phase 5 세부 작업

#### 5.1 검증 체크리스트
- [ ] 프로젝트 목록 페이지 정상 렌더링
- [ ] 상세 페이지 정상 렌더링
- [ ] 카테고리 토글 동작
- [ ] 모달 팝업 동작
- [ ] 모바일 반응형 확인

#### 5.2 Streamlit 처리 결정
| 옵션 | 설명 |
|------|------|
| A. 유지 | 두 방식 모두 사용 가능 (개발용 Streamlit, 운영용 FastAPI) |
| B. 제거 | `pyproject.toml`에서 `[viewer]` optional 의존성 제거 |

---

## 8. 장단점 비교

| 항목 | Streamlit (현재) | FastAPI + Jinja2 (대안) |
|------|-----------------|----------------------|
| **설치 용량** | 무거움 (~100MB+) | 가벼움 (Jinja2 이미 포함) |
| **포트** | 별도 8501 필요 | 기존 API 포트 사용 |
| **배포** | 별도 프로세스 필요 | 단일 서버 |
| **HTML 관리** | Python 내 인라인 | 템플릿 파일 분리 |
| **CSS/JS** | 코드와 혼재 | 별도 파일 |
| **실시간 리로드** | 자동 지원 | uvicorn --reload |
| **학습 곡선** | 낮음 | 중간 (Jinja2 문법) |
| **확장성** | 제한적 | 높음 (커스텀 자유도) |

---

## 9. 위험 요소 및 완화

| 위험 | 영향도 | 완화 방안 |
|------|--------|----------|
| 템플릿 변환 오류 | 중간 | 단계별 검증, 원본과 비교 테스트 |
| Jinja2 문법 오류 | 낮음 | IDE Jinja2 플러그인 활용 |
| 정적 파일 경로 문제 | 낮음 | `url_for()` 헬퍼 함수 사용 |
| ES 연결 설정 차이 | 낮음 | 기존 ViewerDataService 재사용 |
