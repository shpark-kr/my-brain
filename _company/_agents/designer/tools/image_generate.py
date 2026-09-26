#!/usr/bin/env python3
# version: image_v1
"""Designer 에이전트 이미지 생성 도구.

Gemini Imagen 3 / Nano Banana 2 API를 통한 AI 이미지 생성과,
Pillow 기반의 고화질 비주얼 배너/인포그래픽 로컬 렌더링을 모두 지원합니다.
API 키가 없거나 네트워크 오류 시에도 텍스트 플레이스홀더가 아닌
실제 고해상도 PNG 바이너리 이미지를 100% 보장하여 생성합니다.

사용법:
  python image_generate.py --prompt "호르몬 불균형 복부비만 경고 배너" --aspect 16:9 --output banner.png
  python image_generate.py --title "4050 호르몬 대사 체크리스트" --subtitle "나잇살은 의지력 문제가 아니다" --type cta --output cta.png
"""

import os
import sys
import json
import base64
import argparse
from typing import Optional, Tuple, Dict, Any

HERE = os.path.dirname(os.path.abspath(__file__))
GEN_CONFIG = os.path.join(HERE, "image_generate.json")

def _log(msg: str, kind: str = "info"):
    prefix = {"info": "🎨", "ok": "✅", "warn": "⚠️ ", "err": "❌"}.get(kind, "•")
    print(f"{prefix} {msg}", file=sys.stderr, flush=True)

def _load_config() -> Dict[str, Any]:
    if os.path.exists(GEN_CONFIG):
        try:
            with open(GEN_CONFIG, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _find_gemini_credentials() -> Tuple[str, str]:
    """Gemini API 키 및 이미지 모델명을 다단계 경로에서 자동 탐색."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    image_model = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image").strip()

    candidate_paths = [
        os.path.join(HERE, "gemini_account.json"),
        os.path.join(HERE, "..", "business", "tools", "gemini_account.json"),
        os.path.join(os.path.expanduser("~/.connect-ai-brain"), "_company", "_agents", "designer", "tools", "gemini_account.json"),
        os.path.join(os.path.expanduser("~/.connect-ai-brain"), "_company", "_agents", "business", "tools", "gemini_account.json"),
        os.path.join(HERE, "..", "..", "..", "_company", "agents", "business", "tools", "gemini_account.json"),
    ]

    for p in candidate_paths:
        try:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    k = (data.get("API_KEY") or data.get("GEMINI_API_KEY") or "").strip()
                    m = (data.get("IMAGE_MODEL") or data.get("GEMINI_IMAGE_MODEL") or "").strip()
                    if k and not api_key:
                        api_key = k
                    if m:
                        image_model = m
                    if api_key:
                        break
        except Exception:
            pass

    return api_key, image_model

def _call_gemini_image_api(prompt: str, aspect_ratio: str, api_key: str, model: str) -> Optional[bytes]:
    """Google Gemini API (Imagen 3 / Nano Banana 2)를 호출하여 이미지 바이너리 획득."""
    try:
        import requests
    except ImportError:
        _log("requests 모듈이 없습니다.", "warn")
        return None

    _log(f"Gemini API 호출 중... (모델: {model})", "info")

    # 1. Imagen 3 predict 엔드포인트
    if "imagen" in model.lower():
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:predict?key={api_key}"
        # Imagen 종횡비 매핑
        aspect_map = {"16:9": "16:9", "1:1": "1:1", "9:16": "9:16", "4:3": "4:3", "3:4": "3:4"}
        ar = aspect_map.get(aspect_ratio, "16:9")
        payload = {
            "instances": [{"prompt": prompt}],
            "parameters": {
                "sampleCount": 1,
                "aspectRatio": ar,
                "outputMimeType": "image/png"
            }
        }
        try:
            res = requests.post(url, json=payload, timeout=60)
            if res.status_code == 200:
                data = res.json()
                preds = data.get("predictions", [])
                if preds and "bytesBase64Encoded" in preds[0]:
                    return base64.b64decode(preds[0]["bytesBase64Encoded"])
            else:
                _log(f"Imagen API 응답 코드: {res.status_code}, {res.text[:200]}", "warn")
        except Exception as e:
            _log(f"Imagen API 호출 실패: {e}", "warn")

    # 2. Gemini 3.1 Flash Image (Nano Banana) generateContent 엔드포인트
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": f"Generate a high-quality professional visual asset for: {prompt}. Aspect ratio {aspect_ratio}."}
                ]
            }
        ],
        "generationConfig": {
            "responseModalities": ["IMAGE", "TEXT"]
        }
    }
    try:
        res = requests.post(url, json=payload, timeout=60)
        if res.status_code == 200:
            data = res.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                for part in parts:
                    inline = part.get("inlineData") or part.get("inline_data")
                    if inline and "data" in inline:
                        return base64.b64decode(inline["data"])
        else:
            _log(f"Gemini generateContent 응답: {res.status_code}, {res.text[:200]}", "warn")
    except Exception as e:
        _log(f"Gemini generateContent 호출 실패: {e}", "warn")

    return None

def _render_local_graphics(
    output_path: str,
    title: str,
    subtitle: str,
    aspect_ratio: str = "16:9",
    category: str = "경고 및 체크리스트",
    theme: str = "dark_navy",
    points: Optional[list] = None,
    cta_text: str = "[무료 진단] 체크리스트 다운로드"
) -> bool:
    """Pillow를 활용하여 고품질의 브랜드 규격 그래픽 이미지를 로컬에서 직접 렌더링."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        _log("PIL(Pillow) 라이브러리를 찾을 수 없습니다.", "err")
        return False

    dim_map = {
        "16:9": (1920, 1080),
        "1:1": (1080, 1080),
        "9:16": (1080, 1920),
        "4:3": (1440, 1080),
    }
    width, height = dim_map.get(aspect_ratio, (1920, 1080))

    img = Image.new("RGBA", (width, height), (11, 19, 43, 255))
    draw = ImageDraw.Draw(img)

    # 1. 배경 그라데이션 및 질감
    top_color = (11, 19, 43)    # 다크 네이비
    bottom_color = (28, 37, 65) # 딥 인디고
    for y in range(height):
        ratio = y / height
        r = int(top_color[0] + (bottom_color[0] - top_color[0]) * ratio)
        g = int(top_color[1] + (bottom_color[1] - top_color[1]) * ratio)
        b = int(top_color[2] + (bottom_color[2] - top_color[2]) * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b, 255))

    # 2. 배경 악센트 그리드 및 글로우 효과
    grid_color = (140, 160, 200, 25)
    for x in range(0, width, 80):
        draw.line([(x, 0), (x, height)], fill=grid_color, width=1)
    for y in range(0, height, 80):
        draw.line([(0, y), (width, y)], fill=grid_color, width=1)

    # 상단 앰비언트 글로우 라인
    draw.rectangle([0, 0, width, 8], fill=(239, 68, 68, 255)) # Alert Red

    # 3. 폰트 로드 (윈도우 맑은 고딕 또는 기본 폰트)
    def get_font(size: int):
        candidates = [
            "C:\\Windows\\Fonts\\malgunbd.ttf",
            "C:\\Windows\\Fonts\\malgun.ttf",
            "C:\\Windows\\Fonts\\NanumGothicBold.ttf",
            "C:\\Windows\\Fonts\\arialbd.ttf",
            "C:\\Windows\\Fonts\\arial.ttf",
        ]
        for c in candidates:
            if os.path.exists(c):
                try:
                    return ImageFont.truetype(c, size)
                except Exception:
                    pass
        return ImageFont.load_default()

    font_badge = get_font(int(width * 0.022))
    font_title = get_font(int(width * 0.045))
    font_sub = get_font(int(width * 0.025))
    font_cta = get_font(int(width * 0.028))

    pad_x = int(width * 0.08)
    cur_y = int(height * 0.12)

    # 4. 상단 카테고리 뱃지 (이모지 대신 심볼/텍스트)
    badge_text = f"[ALERT] {category.upper()}"
    badge_box = [pad_x, cur_y, pad_x + int(width * 0.32), cur_y + int(height * 0.065)]
    draw.rounded_rectangle(badge_box, radius=12, fill=(239, 68, 68, 40), outline=(239, 68, 68, 200), width=2)
    draw.text((pad_x + 25, cur_y + 14), badge_text, fill=(255, 120, 120, 255), font=font_badge)

    cur_y += int(height * 0.11)

    # 5. 메인 타이틀 (줄바꿈 처리)
    max_char_per_line = 24 if width > 1200 else 18
    words = title.split()
    lines = []
    cur_line = ""
    for w in words:
        if len(cur_line + " " + w) > max_char_per_line:
            lines.append(cur_line.strip())
            cur_line = w
        else:
            cur_line += " " + w
    if cur_line:
        lines.append(cur_line.strip())

    for l in lines[:3]:
        draw.text((pad_x, cur_y), l, fill=(255, 255, 255, 255), font=font_title)
        cur_y += int(height * 0.09)

    cur_y += int(height * 0.02)

    # 6. 서브타이틀
    if subtitle:
        draw.text((pad_x, cur_y), subtitle, fill=(180, 195, 220, 255), font=font_sub)
        cur_y += int(height * 0.08)

    # 7. 중앙 핵심 정보/비교 박스 모듈
    card_w = int(width * 0.84)
    card_h = int(height * 0.26)
    card_box = [pad_x, cur_y, pad_x + card_w, cur_y + card_h]
    draw.rounded_rectangle(card_box, radius=20, fill=(18, 28, 56, 230), outline=(50, 75, 120, 150), width=2)

    # 카드 내부 3단계 포인트
    step_y = cur_y + int(card_h * 0.16)
    if not points:
        points = [
            ("01", "인슐린 저항성 증가", "대사 기능 저하로 복부 내장지방 집중 축적"),
            ("02", "골격근 사코페니아", "기초대사량 급감 및 칼로리 소비 불균형"),
            ("03", "시스템적 회복 솔루션", "단백질 우선 식단 + 대사 주기 회복 루틴")
        ]
    col_w = int(card_w / max(1, len(points)))
    for i, item in enumerate(points[:3]):
        num = item[0] if len(item) > 0 else f"0{i+1}"
        head = item[1] if len(item) > 1 else ""
        desc = item[2] if len(item) > 2 else ""
        cx = pad_x + 35 + (i * col_w)
        draw.text((cx, step_y), f"CHECK {num}", fill=(245, 158, 11, 255), font=font_badge) # Gold
        draw.text((cx, step_y + 40), head, fill=(255, 255, 255, 255), font=font_sub)
        # 긴 설명 축약
        draw.text((cx, step_y + 90), desc[:20] + "...", fill=(150, 170, 200, 255), font=get_font(int(width * 0.016)))

    cur_y += card_h + int(height * 0.05)

    # 8. 하단 CTA 배너/버튼 모듈 (텍스트 길이에 맞춘 동적 너비 계산)
    try:
        t_bbox = draw.textbbox((0, 0), cta_text, font=font_cta)
        text_w = t_bbox[2] - t_bbox[0]
    except Exception:
        text_w = len(cta_text) * int(width * 0.02)
    cta_w = max(int(width * 0.45), text_w + 70)
    cta_h = int(height * 0.085)
    cta_box = [pad_x, cur_y, pad_x + cta_w, cur_y + cta_h]
    draw.rounded_rectangle(cta_box, radius=14, fill=(245, 158, 11, 255)) # Gold
    draw.text((pad_x + 35, cur_y + 18), cta_text, fill=(11, 19, 43, 255), font=font_cta)

    # 우측 브랜드 워터마크
    brand_text = "CONNECT AI • HEALTH & WEALTH BLUEPRINT"
    draw.text((width - pad_x - 420, cur_y + 30), brand_text, fill=(100, 120, 160, 200), font=font_badge)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    img.save(output_path, "PNG")
    _log(f"고화질 그래픽 에셋 생성 완료: {output_path} ({width}x{height})", "ok")
    return True

def generate_image(
    prompt: str = "",
    title: str = "",
    subtitle: str = "",
    output_path: str = "output.png",
    aspect_ratio: str = "16:9",
    category: str = "건강 및 자산 사각지대",
    force_local: bool = False,
    points: Optional[list] = None,
    cta_text: str = "[무료 진단] 체크리스트 다운로드"
) -> str:
    """통합 이미지 생성 진입점: Gemini AI 우선 시도 후 로컬 렌더러 자동 Fallback."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    api_key, model = _find_gemini_credentials()

    # 1. API 키가 존재하고 force_local이 아닌 경우 Gemini AI 시도
    if api_key and not force_local and prompt:
        img_bytes = _call_gemini_image_api(prompt, aspect_ratio, api_key, model)
        if img_bytes:
            with open(output_path, "wb") as f:
                f.write(img_bytes)
            _log(f"Gemini AI 이미지 생성 성공: {output_path} ({len(img_bytes)} bytes)", "ok")
            return output_path

    # 2. 로컬 고화질 렌더링 (안전장치)
    final_title = title or prompt or "건강 & 재정 사각지대 진단 가이드"
    final_subtitle = subtitle or "호르몬 불균형과 시스템적 격차를 점검하고 안전한 노후를 준비하세요."
    success = _render_local_graphics(
        output_path=output_path,
        title=final_title,
        subtitle=final_subtitle,
        aspect_ratio=aspect_ratio,
        category=category,
        points=points,
        cta_text=cta_text
    )
    if success:
        return output_path
    else:
        raise RuntimeError("이미지 생성 파이프라인 전체 실패.")

def main():
    parser = argparse.ArgumentParser(description="Connect AI Designer 이미지 생성 도구")
    parser.add_argument("--prompt", type=str, default="", help="AI 이미지 생성 프롬프트")
    parser.add_argument("--title", type=str, default="", help="배너/인포그래픽 타이틀")
    parser.add_argument("--subtitle", type=str, default="", help="서브타이틀 설명")
    parser.add_argument("--output", type=str, default="generated_asset.png", help="저장할 파일 경로")
    parser.add_argument("--aspect", type=str, default="16:9", choices=["16:9", "1:1", "9:16", "4:3"], help="종횡비")
    parser.add_argument("--category", type=str, default="경고 및 진단", help="카테고리 뱃지 텍스트")
    parser.add_argument("--cta", type=str, default="[무료 진단] 체크리스트 다운로드", help="CTA 버튼 텍스트")
    parser.add_argument("--local", action="store_true", help="Gemini API 호출 없이 로컬 렌더링 강제")

    args = parser.parse_args()

    cfg = _load_config()
    prompt = args.prompt or cfg.get("PROMPT", "")
    title = args.title or cfg.get("TITLE", "")
    subtitle = args.subtitle or cfg.get("SUBTITLE", "")
    output = args.output or cfg.get("OUTPUT_PATH", "generated_asset.png")
    aspect = args.aspect or cfg.get("ASPECT_RATIO", "16:9")
    cta_text = args.cta or cfg.get("CTA_TEXT", "[무료 진단] 체크리스트 다운로드")

    if not prompt and not title:
        title = "나잇살은 의지력 문제가 아니다: 호르몬 불균형 자가진단"
        subtitle = "덜 먹어도 뱃살이 안 빠지는 진짜 이유와 3단계 실천 루틴"
        prompt = "Professional medical infographic showing insulin resistance and muscle sarcopenia in 40s and 50s adults, sleek dark navy and red warning aesthetic"

    try:
        res = generate_image(
            prompt=prompt,
            title=title,
            subtitle=subtitle,
            output_path=output,
            aspect_ratio=aspect,
            category=args.category,
            force_local=args.local,
            cta_text=cta_text
        )
        print(f"OUTPUT_IMAGE: {res}")
        sys.exit(0)
    except Exception as e:
        _log(f"오류 발생: {e}", "err")
        sys.exit(1)

if __name__ == "__main__":
    main()
