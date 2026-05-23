# gemini_client.py — Gemini AI 프로듀서 담당
# ─────────────────────────────────────────────

import os
import json
import re
import google.generativeai as genai
from dotenv import load_dotenv
from config import GEMINI_MODEL

load_dotenv()

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel(GEMINI_MODEL)


SYSTEM_PROMPT = """
당신은 세계 최고의 AI 영화 프로듀서입니다.
주어진 프로젝트 컨텍스트와 씬 정보를 분석하여
각 씬에 최적화된 영상 제작 기획과 프롬프트를 생성합니다.

## 모델별 특성 (반드시 반영)
- Seedance 2.0: 안정적인 피사체, 자연스러운 움직임, 사실적 질감에 강함.
  카메라 무브는 반드시 1개만 사용. 프롬프트는 영문 2,200자 이내.
  형식: (0s-Xs): 설명 형태의 타임코드 블록 사용.
- Gen-4 Turbo: 역동적 움직임, 드라마틱한 액션, 빠른 컷에 강함.
  카메라 연출이 자유롭고 표현적.
- Gen-3 Alpha: 예술적 스타일, 추상적 비주얼, 독창적 표현에 강함.

## 출력 형식 (반드시 JSON으로만 응답, 다른 텍스트 절대 금지)
{
  "producer_insight": "제작 의도 및 성공 전략 (한국어, 200자 이내)",
  "style_guide": "핵심 스타일 키워드 (영문, 쉼표 구분, 10개 이내)",
  "runway_prompt": "최종 영문 프롬프트 (2,200자 이내, 모델 규칙 준수)",
  "camera_move": "static / slow dolly-in / slow dolly-out / pan left / pan right / tilt up / tilt down / arc shot / handheld / crane up 중 1개만",
  "negative_prompt": "제외할 요소 (영문, 쉼표 구분)",
  "continuity_notes": "다음 씬에 전달할 시각적 연속성 메모 (한국어, 100자 이내)"
}
"""


def produce_scene(project_context, scene, prev_continuity_notes=""):
    """
    프로젝트 컨텍스트 + 씬 정보를 Gemini에 넘겨
    Producer-Insight, Runway-Prompt 등을 생성.
    """
    user_message = f"""
## 프로젝트 컨텍스트
- 프로젝트명: {project_context['project_title']}
- 제작 목적: {project_context['purpose']}
- 주력 모델: {project_context['primary_model']}
- 장르/톤: {project_context['genre_tone']}
- 로그라인: {project_context['logline']}
- 비주얼 아이덴티티: {project_context['visual_identity']}
- 타겟 관객: {project_context['target_audience']}
- 전체 길이: {project_context['duration_total']}초

## 이전 씬 연속성 메모
{prev_continuity_notes if prev_continuity_notes else "첫 번째 씬 (없음)"}

## 현재 씬 정보
- 씬 번호: {scene['scene']}
- 편집 순서: {scene['scene_order']}번째
- 씬 목적: {scene['scene_purpose']}
- 핵심 감정: {scene['emotional_beat']}
- 목표 길이: {scene['duration']}초
- 내용 (한국어):
{scene['content']}
{f"- 감독 코멘트: {scene['notes']}" if scene['notes'] else ""}

JSON 형식으로만 응답하세요.
"""

    print(f"  🤖 Gemini 호출 중... (씬: {scene['scene']})")

    try:
        response = model.generate_content(
            [SYSTEM_PROMPT, user_message],
            generation_config=genai.GenerationConfig(
                temperature=0.7,
                max_output_tokens=2048
            )
        )

        raw = response.text.strip()
        raw = re.sub(r"```json\s*", "", raw)
        raw = re.sub(r"```\s*", "", raw)
        result = json.loads(raw)

        # 필수 키 검증
        required_keys = [
            "producer_insight", "style_guide", "runway_prompt",
            "camera_move", "negative_prompt", "continuity_notes"
        ]
        for key in required_keys:
            if key not in result:
                result[key] = ""

        # Seedance 2,200자 초과 경고 및 자동 요약
        if project_context['primary_model'] == "Seedance 2.0":
            char_count = len(result.get("runway_prompt", ""))
            if char_count > 2200:
                print(f"  ⚠️  프롬프트 {char_count}자 — 2,200자 초과! 자동 요약 시도...")
                result = _shorten_prompt(result)

        print(f"  ✅ Gemini 응답 완료")
        return result

    except json.JSONDecodeError as e:
        print(f"  ❌ JSON 파싱 실패: {e}")
        print(f"     원본 응답: {raw[:200]}...")
        return None
    except Exception as e:
        print(f"  ❌ Gemini 호출 실패: {e}")
        return None


def _shorten_prompt(result):
    """프롬프트가 2,200자 초과 시 Gemini에게 재요약 요청"""
    shorten_msg = f"""
다음 프롬프트가 2,200자를 초과했습니다.
핵심 내용을 유지하면서 2,000자 이내로 줄여주세요.
runway_prompt만 수정해서 같은 JSON 형식으로 응답하세요.

원본 프롬프트:
{result['runway_prompt']}
"""
    try:
        response = model.generate_content(shorten_msg)
        raw = re.sub(r"```json\s*|```\s*", "", response.text.strip())
        shortened = json.loads(raw)
        result["runway_prompt"] = shortened.get("runway_prompt", result["runway_prompt"])
        print(f"  ✅ 프롬프트 요약 완료 ({len(result['runway_prompt'])}자)")
    except Exception:
        print("  ⚠️  자동 요약 실패. 원본 프롬프트 사용.")
    return result
