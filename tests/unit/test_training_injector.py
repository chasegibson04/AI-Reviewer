from ai_reviewer.training.injector import build_guidance_injection
from ai_reviewer.training.schema import GlobalGuidance


def test_guidance_injection_selects_profile_categories():
    g = GlobalGuidance(
        active_file_count=3,
        category_guidance={
            "published_papers": ["Use crisp abstracts"],
            "external_guides": ["Match journal policy language"],
            "formatting_color_guides": ["Keep heading styles consistent"],
        },
        global_summary="Lab guidance",
    )
    inj = build_guidance_injection(g, "writing", max_chars=5000)
    assert inj.enabled is True
    assert "LAB TRAINING GUIDANCE" in inj.prompt_block
    assert "formatting_color_guides" in inj.categories_used

