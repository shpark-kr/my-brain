# 🎨 image_generate — Designer 전용 이미지 생성 도구

> 버전: `image_v1`  
> 담당 에이전트: **Designer** (`designer`)

---

## 1. 개요
블로그 원고, 유튜브 썸네일, 랜딩페이지, SNS 카드뉴스에 필요한 고화질 시각 에셋(PNG)을 생성합니다.
Google Gemini의 **Imagen 3** / **Nano Banana 2 (`gemini-3.1-flash-image`)** AI 엔진을 기본 지원하며,
API 키가 없거나 오프라인 환경에서도 Pillow 그래픽 엔진을 통해 실제 유효한 고해상도 PNG 바이너리 파일을 100% 보장하여 생성합니다.

---

## 2. 사용법 (CLI)

```bash
# 기본 실행 (설정 파일 기반)
python image_generate.py

# AI 프롬프트 기반 16:9 배너 생성
python image_generate.py --prompt "Medical warning infographic about insulin resistance" --aspect 16:9 --output "결과물/03_기획_디자인/banner.png"

# 한글 타이틀/서브타이틀 지정 로컬 그래픽 렌더링
python image_generate.py --title "4050 호르몬 대사 체크리스트" --subtitle "덜 먹어도 뱃살이 안 빠지는 진짜 이유" --aspect 16:9 --output "결과물/03_기획_디자인/호르몬체크리스트_배너.png"
```

---

## 3. 매개변수 옵션

| 옵션 | 설명 | 기본값 |
|---|---|---|
| `--prompt` | AI 이미지 생성 프롬프트 (영어/한국어) | 설정 파일 참조 |
| `--title` | 배너 또는 인포그래픽 상단 메인 타이틀 | 설정 파일 참조 |
| `--subtitle` | 보조 설명 텍스트 | 설정 파일 참조 |
| `--output` | 저장할 파일 경로 (.png) | `generated_asset.png` |
| `--aspect` | 종횡비 (`16:9`, `1:1`, `9:16`, `4:3`) | `16:9` |
| `--category` | 상단 경고 뱃지 텍스트 | `경고 및 진단` |
| `--local` | Gemini API 호출 없이 로컬 렌더러 즉시 강제 | `false` |
