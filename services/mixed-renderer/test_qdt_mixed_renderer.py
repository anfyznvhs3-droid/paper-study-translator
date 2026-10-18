from pathlib import Path
import unittest

import qdt_mixed_renderer as renderer


class MixedRendererTests(unittest.TestCase):
    def test_mono_outputs_use_final_pdf_translation_names(self):
        md_path, html_path, pdf_path = renderer.build_output_paths(
            Path(r"D:\input\Week 11-1 Evidence.pdf"),
            Path(r"D:\output\Week 11-1 Evidence-ko"),
            "mono",
        )

        self.assertEqual(md_path.name, "Week 11-1 Evidence-ko-mono.md")
        self.assertEqual(html_path.name, "Week 11-1 Evidence-ko-mono.html")
        self.assertEqual(pdf_path.name, "Week 11-1 Evidence-ko-mono.pdf")
        self.assertEqual(
            renderer.build_audit_path(Path(r"D:\input\Week 11-1 Evidence.pdf"), Path(r"D:\output\Week 11-1 Evidence-ko"), "mono").name,
            "Week 11-1 Evidence-ko-mono.layout-audit.json",
        )

    def test_service_spec_supports_model_suffix(self):
        self.assertEqual(renderer.parse_service_spec("bedrock:claude-4.5-sonnet"), ("bedrock", "claude-4.5-sonnet"))
        self.assertEqual(renderer.parse_service_spec("google"), ("google", None))

    def test_prompt_file_loads_as_template(self):
        prompt_path = Path(__file__).with_name("tmp_prompt_for_test.md")
        prompt_path.write_text("Translate $text", encoding="utf-8")
        try:
            prompt = renderer.load_prompt(str(prompt_path))
        finally:
            prompt_path.unlink(missing_ok=True)

        self.assertEqual(prompt.safe_substitute(text="Hello"), "Translate Hello")

    @unittest.skipIf(renderer.Kiwi is None, "kiwipiepy is not installed")
    def test_spacing_policy_repairs_korean_pdf_extraction_artifacts(self):
        spaced = renderer.polish_korean_spacing(
            "개인의경험등다양한경로로얻어진정보혹은사실",
            renderer.create_spacing_engine(require_spacing=True),
        )

        self.assertEqual(spaced, "개인의 경험 등 다양한 경로로 얻어진 정보 혹은 사실")

    def test_split_lines_merges_orphan_list_markers(self):
        lines = renderer.split_lines("•\nA general understanding\n1)\nintroducing new ways")

        self.assertEqual(lines, ["• A general understanding", "1) introducing new ways"])

    def test_split_lines_separates_label_and_embedded_definition_bullet(self):
        lines = renderer.split_lines("❖가용성휴리스틱(Availability Heuristic) • Tendency to make judgments based on information that easily comes to mind")

        self.assertEqual(
            lines,
            [
                "❖가용성휴리스틱(Availability Heuristic)",
                "• Tendency to make judgments based on information that easily comes to mind",
            ],
        )

    def test_split_lines_merges_wrapped_english_definition(self):
        lines = renderer.split_lines("•\nTendency to make judgments based on information \nthat easily comes to mind\n최근에접하거나기억에남는정보에근거해")

        self.assertEqual(
            lines,
            [
                "• Tendency to make judgments based on information that easily comes to mind",
                "최근에접하거나기억에남는정보에근거해",
            ],
        )

    def test_split_lines_repairs_wrapped_parenthetical_label(self):
        lines = renderer.split_lines(
            "❖기준점휴리스틱(Anchoring \nHeuristic )\n•\nRelying heavily on the first piece of \ninformation encountered (the “anchor”) \nwhen making decisions."
        )

        self.assertEqual(
            lines,
            [
                "❖기준점휴리스틱(Anchoring Heuristic )",
                "• Relying heavily on the first piece of information encountered (the “anchor”) when making decisions.",
            ],
        )
        self.assertEqual(renderer.translate_line(lines[0], None, {}, None), ["기준점 휴리스틱(Anchoring Heuristic)"])

    def test_fragmented_ppt_words_are_merged_before_translation(self):
        blocks = [
            (532.06, 274.22, 625.05, 315.88, "Policy Implementa", 7),
            (749.4, 284.11, 842.28, 325.77, "Policy Formulation", 5),
            (563.88, 313.68, 593.3, 335.68, "tion", 8),
        ]

        merged = renderer.merge_fragmented_text_blocks(blocks)

        self.assertIn("Policy Implementation", [block[4] for block in merged])
        self.assertNotIn("tion", [block[4] for block in merged])

    def test_block_level_terms_survive_ppt_line_breaks(self):
        self.assertEqual(renderer.translate_source_text("Policy \nImplementation", None, {}, None), ["정책 집행"])
        self.assertEqual(renderer.translate_source_text("➢ Policy Legacies (as input) Matter", None, {}, None), ["▶ 정책 유산(입력)의 중요성"])

    def test_english_double_arrow_notes_are_translated(self):
        self.assertEqual(
            renderer.translate_line(">> RECIPROCAL relationship between POLICY and POLITICS", None, {}, None),
            [">> 정책과 정치의 상호관계"],
        )

    def test_policy_theory_terms_use_domain_memory(self):
        self.assertEqual(renderer.translate_text("Focus", None, {}), "분석 초점")
        self.assertEqual(renderer.translate_text("Key factors for policy change", None, {}), "정책 변화의 핵심 요인")
        self.assertEqual(renderer.translate_text("How?", None, {}), "작동 방식")
        self.assertEqual(renderer.translate_source_text("Multiple stream\nFramework", None, {}, None), ["다중흐름모형"])
        self.assertEqual(renderer.translate_source_text("Advocacy\nCoalition\nFramework", None, {}, None), ["옹호연합모형"])
        self.assertEqual(renderer.translate_source_text("Punctuated\nEquilibrium\ntheory", None, {}, None), ["단절균형이론"])
        self.assertEqual(renderer.translate_text("Power in four theories", None, {}), "네 가지 이론에서의 권력")
        self.assertEqual(renderer.translate_text("How is their POWER rooted?", None, {}), "그들의 권력은 무엇에 기반하는가?")
        self.assertEqual(renderer.translate_text("Theory 4: Punctuated Equilibrium Theory", None, {}), "이론 4: 단절균형이론")
        self.assertEqual(renderer.translate_text("낙관적편향 (Optimism Bias)", None, {}), "낙관적 편향(Optimism Bias)")
        self.assertEqual(renderer.translate_text("Status Quo Bias", None, {}), "현상유지 편향(Status Quo Bias)")
        self.assertEqual(
            renderer.translate_text(
                "Focuses more on the enduring effects of past policies rather than ongoing group competition",
                None,
                {},
            ),
            "진행 중인 집단 경쟁보다 과거 정책의 지속적 효과에 더 초점을 둔다",
        )
        self.assertEqual(renderer.translate_text("Feedback effects", None, {}), "피드백 효과")
        self.assertEqual(renderer.translate_text("Timing & coupling", None, {}), "타이밍과 흐름의 결합")
        self.assertEqual(
            renderer.translate_text(
                'Coupling of streams during a "policy window"',
                None,
                {},
            ),
            "정책의 창이 열릴 때 흐름의 결합",
        )
        self.assertEqual(
            renderer.translate_text(
                "A set of feedback mechanisms (positive or negative feedback) followed by the policy",
                None,
                {},
            ),
            "정책에 뒤따르는 일련의 피드백 메커니즘(긍정적 또는 부정적 피드백)",
        )

    def test_policy_table_machine_translation_failures_are_reviewed(self):
        policy_window = renderer.review_flags_for_replacement(
            'Coupling of streams during a "policy window"',
            '"정책 중 스트림 결합 창문"',
            True,
        )
        residual_english = renderer.review_flags_for_replacement(
            "A set of feedback mechanisms (positive or negative feedback) followed by the policy",
            "일련의 피드백 메커니즘 followed 정책에 의해",
            True,
        )

        self.assertEqual(policy_window["status"], "needs_review")
        self.assertIn("policy window", policy_window["reason"])
        self.assertEqual(residual_english["status"], "needs_review")
        self.assertIn("영어 원문", residual_english["reason"])

    def test_source_style_detects_bold_spans(self):
        doc = renderer.fitz.open()
        page = doc.new_page(width=260, height=120)
        page.insert_text((20, 40), "Focus", fontname="helv", fontsize=16)
        page.insert_text((20, 80), "Actors", fontname="hebo", fontsize=16)

        regular = renderer.source_style_for_rect(page, renderer.fitz.Rect(18, 24, 90, 48))
        bold = renderer.source_style_for_rect(page, renderer.fitz.Rect(18, 64, 100, 88))

        self.assertFalse(regular["bold"])
        self.assertTrue(bold["bold"])

    def test_layout_replacement_targets_english_heavy_blocks_only(self):
        self.assertTrue(renderer.is_layout_replacement_candidate("Data, information, or knowledge used to support decisions."))
        self.assertFalse(renderer.is_layout_replacement_candidate(">> 전문가 의견, 개인의 경험 등 다양한 경로로 얻어진 정보"))

    def test_layout_audit_marks_unfitted_replacements_for_review(self):
        audit = renderer.summarize_layout_audit(
            [
                {"page": 1, "replacements": [{"fitted": True}, {"fitted": False}]},
                {"page": 2, "replacements": []},
            ],
            source_path="input.pdf",
            output_path="output.pdf",
        )

        self.assertEqual(audit["summary"]["replacement_count"], 2)
        self.assertEqual(audit["summary"]["needs_review_count"], 1)
        self.assertEqual(audit["summary"]["status"], "needs_review")

    def test_short_diagram_labels_are_split_into_separate_targets(self):
        words = [
            (415.87, 219.4, 553.05, 248.71, "Liberalization", 2, 0, 0),
            (153.7, 223.0, 302.13, 244.98, "Internationalization", 2, 1, 0),
            (667.73, 219.4, 832.15, 248.71, "Universalization", 2, 2, 0),
        ]

        targets = renderer.build_label_replacement_targets(
            "Liberalization\nInternationalization\nUniversalization",
            words,
        )

        self.assertEqual([target["source"] for target in targets], ["Liberalization", "Internationalization", "Universalization"])

    def test_label_targets_merge_approved_multi_line_terms(self):
        words = [
            (270.0, 331.41, 442.61, 360.72, "McDonaldization", 3, 0, 0),
            (600.38, 317.01, 660.57, 346.32, "Super", 3, 1, 0),
            (568.7, 345.81, 692.13, 375.12, "Territoriality", 3, 2, 0),
        ]

        targets = renderer.build_label_replacement_targets(
            "McDonaldization\nSuper\nTerritoriality",
            words,
        )

        self.assertEqual([target["source"] for target in targets], ["McDonaldization", "Super Territoriality"])
        self.assertEqual(renderer.translate_text("Super Territoriality", None, {}), "\ucd08\uc601\ud1a0\uc131(Super Territoriality)")

    def test_spread_multiline_blocks_are_split_by_line(self):
        words = [
            (130.1, 250.18, 147.75, 268.21, "->", 16, 0, 0),
            (151.22, 253.33, 238.8, 278.54, "Coordinated", 16, 0, 1),
            (243.36, 253.33, 292.01, 278.54, "actions", 16, 0, 2),
            (296.64, 253.33, 353.72, 278.54, "between", 16, 0, 3),
            (357.96, 253.33, 420.37, 278.54, "countries", 16, 0, 4),
            (539.93, 237.03, 561.72, 255.03, "->", 16, 1, 0),
            (559.82, 240.17, 618.54, 265.35, "Funding", 16, 1, 1),
            (622.82, 240.17, 658.51, 265.35, "flows", 16, 1, 2),
            (663.12, 240.17, 713.34, 265.35, "beyond", 16, 1, 3),
            (717.84, 240.17, 777.94, 265.35, "national", 16, 1, 4),
            (782.35, 240.17, 830.61, 265.35, "control", 16, 1, 5),
        ]

        targets = renderer.build_spread_line_replacement_targets(
            "-> Coordinated actions between countries\n-> Funding flows beyond national control",
            words,
        )

        self.assertEqual(
            [target["source"] for target in targets],
            ["-> Coordinated actions between countries", "-> Funding flows beyond national control"],
        )

    def test_large_panel_is_not_treated_as_a_label_shape(self):
        text_rect = renderer.fitz.Rect(182.78, 164.35, 433.45, 188.85)
        drawings = [
            {
                "rect": renderer.fitz.Rect(78.47, 139.39, 487.01, 487.01),
                "fill": (0.96, 0.8, 0.8),
            }
        ]

        self.assertIsNone(renderer.find_covering_filled_shape(text_rect, drawings))

    def test_card_panel_blocks_are_collected_for_redraw(self):
        panel_rect = renderer.fitz.Rect(40.9, 148.1, 458.4, 307.3)
        text_rect = renderer.fitz.Rect(48.1, 150.1, 381.1, 252.7)
        drawings = [{"rect": panel_rect, "fill": (0.973, 0.91, 0.91)}]
        blocks = [
            (48.1, 150.1, 381.1, 252.7, "❖현상유지편향(Status Quo Bias)\n• Preference for the current state of affairs", 2),
            (70.1, 254.4, 427.9, 295.9, "유익하더라도, 환자들은익숙한대형병원이용 방식에머무르려함.", 3),
            (484.0, 142.0, 916.0, 309.0, "image text", 4),
        ]

        self.assertIsNotNone(renderer.find_text_panel_shape(text_rect, drawings))
        collected = renderer.collect_panel_text(blocks, panel_rect)

        self.assertIn("Status Quo Bias", collected)
        self.assertIn("환자들은익숙한대형병원이용", collected)
        self.assertNotIn("image text", collected)

    def test_wide_definition_panel_is_detected_for_redraw(self):
        panel_rect = renderer.fitz.Rect(50.9, 139.0, 498.6, 310.5)
        text_rect = renderer.fitz.Rect(58.2, 147.2, 440.8, 175.0)
        drawings = [{"rect": panel_rect, "fill": (0.965, 0.969, 0.914)}]

        self.assertIsNotNone(renderer.find_text_panel_shape(text_rect, drawings))
        self.assertEqual(
            renderer.translate_text("Representativeness Heuristic", None, {}),
            "대표성 휴리스틱(Representativeness Heuristic)",
        )

    def test_bounded_rationality_image_text_overlays_are_detected(self):
        slide_context = (
            "Theory 4: Bounded Rationality "
            "Types of heuristics/biases associated with bounded rationality "
        )
        representativeness = renderer.bounded_rationality_image_text_overlays_for_page_text(
            slide_context + "Representativeness Heuristic"
        )
        availability = renderer.bounded_rationality_image_text_overlays_for_page_text(
            slide_context + "Availability Heuristic"
        )
        anchoring = renderer.bounded_rationality_image_text_overlays_for_page_text(
            slide_context + "Anchoring Heuristic"
        )
        confirmation = renderer.bounded_rationality_image_text_overlays_for_page_text(
            slide_context + "Optimism Bias Confirmation Bias"
        )

        self.assertEqual(representativeness[0]["source"], "Making Quick Judgments Based on Mental Prototypes")
        self.assertEqual(
            availability[0]["source"],
            "What comes to mind quickly is deemed significant--sometimes incorrectly.",
        )
        self.assertEqual([item["source"] for item in anchoring], ["That's like free money!", "MUG", "MUG"])
        self.assertIn("CONFIRMATION BIAS", [item["source"] for item in confirmation])
        self.assertIn("NEWS", [item["source"] for item in confirmation])

    def test_duplicate_korean_parenthetical_is_collapsed(self):
        self.assertEqual(renderer.collapse_duplicate_korean_parenthetical("국제화 (국제화)"), "국제화")
        self.assertEqual(renderer.collapse_duplicate_korean_parenthetical("세계화(세계화)"), "세계화")
        self.assertEqual(renderer.translate_text("Internationalization (국제화)", None, {}), "국제화")
        self.assertEqual(renderer.translate_text("Actor (행위자)", None, {}), "행위자")
        self.assertEqual(renderer.translate_text("Power (권력)", None, {}), "권력")
        self.assertEqual(renderer.translate_text("Value (가치)", None, {}), "가치")

    def test_health_policy_terms_use_reviewed_glossary(self):
        self.assertEqual(renderer.translate_text("Global health financing", None, {}), "글로벌 보건 재원 조달")
        self.assertEqual(renderer.translate_text("International Health Regulations", None, {}), "국제보건규칙(IHR)")
        self.assertEqual(renderer.translate_text("Bilateral health cooperation", None, {}), "양자 보건 협력")

    def test_ambiguous_actor_is_marked_for_review(self):
        flags = renderer.review_flags_for_replacement("Actor (행위자)", "배우 (행위자)", True)

        self.assertEqual(flags["status"], "needs_review")
        self.assertIn("다의어", flags["reason"])

    def test_rect_overlap_uses_source_area_ratio(self):
        source = renderer.fitz.Rect(10, 10, 20, 20)
        target = renderer.fitz.Rect(0, 0, 100, 100)

        self.assertTrue(renderer.rects_overlap(source, target, min_ratio=0.9))

    def test_translated_lines_drop_duplicate_korean_parenthetical_line(self):
        self.assertEqual(renderer.collapse_duplicate_translated_lines(["행위자", "(행위자)"]), ["행위자"])
        self.assertEqual(renderer.collapse_duplicate_translated_lines(["권력", "(권력)"]), ["권력"])

    def test_decorative_heading_uses_stable_square_symbol(self):
        self.assertEqual(renderer.translate_line("❑Definition", None, {}, None), ["□ 정의"])
        self.assertEqual(renderer.translate_line("❑Implications", None, {}, None), ["□ 의미"])
        self.assertEqual(renderer.translate_line("➢ Policy Legacies (as input) Matter", None, {}, None), ["▶ 정책 유산(입력)의 중요성"])

    def test_signed_pdf_span_color_converts_to_rgb(self):
        self.assertEqual(renderer.pdf_color_to_rgb(-16777216), (0, 0, 0))
        self.assertEqual(renderer.pdf_color_to_rgb(-16748352), (0, 112 / 255, 192 / 255))

    def test_default_font_prefers_bundled_pretendard(self):
        font_path = renderer.resolve_font_file()

        self.assertIsNotNone(font_path)
        self.assertTrue(font_path.endswith("Pretendard-Regular.ttf"))

    def test_page_15_health_policy_sentence_overrides(self):
        self.assertEqual(
            renderer.translate_text(
                "The government regulates premiums and benefits, while providers handle services and claims.",
                None,
                {},
            ),
            "정부는 보험료와 급여를 규제하고, 공급자는 서비스와 청구를 처리한다",
        )
        self.assertEqual(
            renderer.translate_text(
                "Government, health insurance providers, healthcare professionals, and patients.",
                None,
                {},
            ),
            "정부, 건강보험자, 보건의료 전문가, 환자",
        )

    def test_power_of_groups_is_confirmed_document_term(self):
        self.assertEqual(renderer.translate_text("Power of groups", None, {}), "집단의 권력 구성")
        self.assertEqual(renderer.translate_text("Power of groups (집단의권력구성)", None, {}), "집단의 권력 구성")

        flags = renderer.review_flags_for_replacement("Power of groups", "집단의 권력 구성", True)

        self.assertEqual(flags["status"], "candidate")
        self.assertIn("확정 용어", flags["reason"])


if __name__ == "__main__":
    unittest.main()
