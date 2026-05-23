# run.py — 메인 실행 파일
# 터미널에서: python run.py
# ─────────────────────────────────────────────

import time
from config import MAX_SCENES_PER_RUN
from notion_client import (
    get_project_context,
    get_pending_scenes,
    update_scene_with_gemini_result,
    create_prompt_page
)
from gemini_client import produce_scene


def main():
    print("=" * 50)
    print("🎬 AI 영화 자동화 시스템 시작")
    print("=" * 50)

    # ① 프로젝트 컨텍스트 가져오기
    print("\n📋 프로젝트 컨텍스트 로딩 중...")
    project = get_project_context()
    if not project:
        return

    print(f"  프로젝트: {project['project_title']}")
    print(f"  모델: {project['primary_model']}")
    print(f"  목적: {project['purpose']}")

    # ② 대기중인 씬 목록 가져오기
    print(f"\n🎞  대기중 씬 조회 중... (최대 {MAX_SCENES_PER_RUN}개)")
    scenes = get_pending_scenes(max_count=MAX_SCENES_PER_RUN)

    if not scenes:
        print("✅ 처리할 씬이 없습니다.")
        return

    # ③ 씬 순서대로 처리
    prev_continuity_notes = ""

    for i, scene in enumerate(scenes, 1):
        print(f"\n{'─' * 50}")
        print(f"[{i}/{len(scenes)}] 씬 처리 중: {scene['scene']}")
        print(f"  감정: {scene['emotional_beat']} | 목적: {scene['scene_purpose']} | {scene['duration']}초")

        # Gemini 프로듀싱
        result = produce_scene(project, scene, prev_continuity_notes)

        if result is None:
            print(f"  ⚠️  {scene['scene']} 처리 실패 — 스킵")
            continue

        # ④ Notion Scene DB 업데이트
        print(f"  📝 Notion Scene 업데이트 중...")
        update_scene_with_gemini_result(
            page_id=scene["page_id"],
            producer_insight=result["producer_insight"],
            style_guide=result["style_guide"],
            continuity_notes=result["continuity_notes"]
        )

        # ⑤ Notion Prompt DB에 새 페이지 생성
        print(f"  📝 Prompt 페이지 생성 중...")
        create_prompt_page(
            scene_name=scene["scene"],
            target_model=project["primary_model"],
            runway_prompt=result["runway_prompt"],
            camera_move=result["camera_move"],
            negative_prompt=result["negative_prompt"],
            aspect_ratio="16:9",
            duration_prompt="10s"
        )

        prev_continuity_notes = result["continuity_notes"]

        print(f"  🎉 {scene['scene']} 완료!")

        if i < len(scenes):
            print("  ⏳ 3초 대기 중...")
            time.sleep(3)

    print(f"\n{'=' * 50}")
    print(f"✅ 전체 완료! {len(scenes)}개 씬 처리됨")
    print(f"📌 Notion에서 결과 확인:")
    print(f"   🎞  Scene DB → Producer-Insight, Style-Guide 확인")
    print(f"   ⚡ Prompt DB → Runway-Prompt 복사해서 사용")
    print("=" * 50)


if __name__ == "__main__":
    main()
