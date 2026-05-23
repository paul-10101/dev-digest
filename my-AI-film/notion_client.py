# notion_client.py — Notion 읽기 / 쓰기 담당
# ─────────────────────────────────────────────

import os
from notion_client import Client
from dotenv import load_dotenv
from config import PROJECT_DB_ID, SCENE_DB_ID, PROMPT_DB_ID

load_dotenv()

notion = Client(auth=os.environ["NOTION_TOKEN"])


# ─────────────────────────────────────────────
# 헬퍼: Notion 속성값 안전하게 추출
# ─────────────────────────────────────────────

def get_text(props, key):
    try:
        return props[key]["rich_text"][0]["plain_text"]
    except (KeyError, IndexError):
        return ""

def get_title(props, key):
    try:
        return props[key]["title"][0]["plain_text"]
    except (KeyError, IndexError):
        return ""

def get_select(props, key):
    try:
        return props[key]["select"]["name"]
    except (KeyError, TypeError):
        return ""

def get_number(props, key):
    try:
        return props[key]["number"] or 0
    except (KeyError, TypeError):
        return 0


# ─────────────────────────────────────────────
# Project DB: 컨텍스트 가져오기
# ─────────────────────────────────────────────

def get_project_context():
    result = notion.databases.query(
        database_id=PROJECT_DB_ID,
        sorts=[{"timestamp": "created_time", "direction": "descending"}],
        page_size=1
    )

    if not result["results"]:
        print("⚠️  Project DB가 비어있습니다. 먼저 프로젝트를 생성하세요.")
        return None

    page = result["results"][0]
    props = page["properties"]

    return {
        "project_title":   get_title(props, "Project-Title"),
        "purpose":         get_select(props, "Purpose"),
        "primary_model":   get_select(props, "Primary-Model"),
        "genre_tone":      str(props.get("Genre-Tone", {}).get("multi_select", [])),
        "logline":         get_text(props, "Logline"),
        "visual_identity": get_text(props, "Visual-Identity"),
        "target_audience": get_select(props, "Target-Audience"),
        "duration_total":  get_number(props, "Duration-Total"),
    }


# ─────────────────────────────────────────────
# Scene DB: "대기중" 씬 목록 가져오기
# ─────────────────────────────────────────────

def get_pending_scenes(max_count=5):
    result = notion.databases.query(
        database_id=SCENE_DB_ID,
        filter={
            "property": "Generation-Status",
            "select": {"equals": "대기중"}
        },
        sorts=[{"property": "Scene-Order", "direction": "ascending"}],
        page_size=max_count
    )

    scenes = []
    for page in result["results"]:
        props = page["properties"]
        scenes.append({
            "page_id":        page["id"],
            "scene":          get_title(props, "Scene"),
            "content":        get_text(props, "Content"),
            "scene_purpose":  get_select(props, "Scene-Purpose"),
            "emotional_beat": get_select(props, "Emotional-Beat"),
            "duration":       get_number(props, "Duration-Scene"),
            "scene_order":    get_number(props, "Scene-Order"),
            "notes":          get_text(props, "Notes"),
        })

    print(f"✅ 대기중 씬 {len(scenes)}개 발견")
    return scenes


# ─────────────────────────────────────────────
# Scene DB: Gemini 결과 자동 업데이트
# ─────────────────────────────────────────────

def update_scene_with_gemini_result(page_id, producer_insight, style_guide, continuity_notes):
    notion.pages.update(
        page_id=page_id,
        properties={
            "Producer-Insight": {
                "rich_text": [{"type": "text", "text": {"content": producer_insight}}]
            },
            "Style-Guide": {
                "rich_text": [{"type": "text", "text": {"content": style_guide}}]
            },
            "Continuity-Notes": {
                "rich_text": [{"type": "text", "text": {"content": continuity_notes}}]
            },
            "Generation-Status": {
                "select": {"name": "생성완료"}
            }
        }
    )
    print(f"  ✅ Scene 업데이트 완료")


# ─────────────────────────────────────────────
# Prompt DB: 새 프롬프트 페이지 생성
# ─────────────────────────────────────────────

def create_prompt_page(scene_name, target_model, runway_prompt,
                        camera_move, negative_prompt,
                        aspect_ratio="16:9", duration_prompt="10s"):
    prompt_id = f"{scene_name}-{target_model.replace(' ', '')}"

    valid_camera_moves = [
        "static", "slow dolly-in", "slow dolly-out",
        "pan left", "pan right", "tilt up", "tilt down",
        "arc shot", "handheld", "crane up"
    ]
    if camera_move not in valid_camera_moves:
        camera_move = "static"

    notion.pages.create(
        parent={"database_id": PROMPT_DB_ID},
        properties={
            "Prompt-ID": {
                "title": [{"type": "text", "text": {"content": prompt_id}}]
            },
            "Target-Model": {
                "select": {"name": target_model}
            },
            "Runway-Prompt": {
                "rich_text": [{"type": "text", "text": {"content": runway_prompt}}]
            },
            "Camera-Move": {
                "select": {"name": camera_move}
            },
            "Negative-Prompt": {
                "rich_text": [{"type": "text", "text": {"content": negative_prompt}}]
            },
            "Aspect-Ratio": {
                "select": {"name": aspect_ratio}
            },
            "Duration-Prompt": {
                "select": {"name": duration_prompt}
            },
            "Version": {
                "number": 1
            },
            "Prompt-Status": {
                "select": {"name": "생성완료"}
            }
        }
    )
    print(f"  ✅ Prompt 페이지 생성: {prompt_id}")
