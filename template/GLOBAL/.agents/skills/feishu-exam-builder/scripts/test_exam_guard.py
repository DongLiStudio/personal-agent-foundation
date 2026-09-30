"""Synthetic-only behavior tests. No Feishu requests and no persistent writes."""

import contextlib
import copy
import io
import json
import unittest
from decimal import Decimal
from unittest.mock import patch

import exam_guard as guard


def fixture():
    options = [{"key": "A", "text": "Alpha"}, {"key": "B", "text": "Beta"}, {"key": "C", "text": "Gamma"}]
    questions = [
        {"id": "Q1", "section_id": "auto", "type": "single", "stem": "Choose Alpha", "source": "synthetic fixture", "max_score": "0.1", "required": True, "options": options, "answer": "A"},
        {"id": "Q2", "section_id": "auto", "type": "multi", "stem": "Choose Alpha and Beta", "source": "synthetic fixture", "max_score": "0.2", "required": True, "options": options, "answer": ["A", "B"]},
        {"id": "Q3", "section_id": "auto", "type": "fill", "stem": "Write the approved term", "source": "synthetic fixture", "max_score": "0.7", "required": True, "accepted_answers": ["Round", "圆"]},
        {"id": "Q4", "section_id": "manual", "type": "practical", "stem": "Show evidence", "source": "synthetic fixture", "max_score": "2", "required": True, "rubric": [{"id": "r1", "description": "Working result", "max_score": "1.5"}, {"id": "r2", "description": "Evidence", "max_score": "0.5"}]},
    ]
    fields, form_questions = [], []
    for q in questions:
        fields.append({"field_id": "fld" + q["id"], "question_id": q["id"], "name": q["id"], "type": q["type"], "description": q["stem"], "options": copy.deepcopy(q.get("options", []))})
        form_questions.append({"question_id": q["id"], "field_id": "fld" + q["id"], "title": q["id"], "description": q["stem"], "type": q["type"], "options": copy.deepcopy(q.get("options", [])), "required": q["required"]})
    manifest = {"schema_version": 1, "exam_id": "fictional-demo", "version": "1.0", "total_max": "100", "rounding": {"places": 2, "mode": "HALF_UP"},
                "sections": [{"id": "auto", "raw_max": "1", "contribution_max": "40"}, {"id": "manual", "raw_max": "2", "contribution_max": "60"}],
                "questions": questions, "layout": {"fields": fields, "forms": [{"form_id": "form-demo", "question_order": [q["id"] for q in questions], "questions": form_questions}], "grid_order": [f["field_id"] for f in fields]}}
    response = {"exam_id": "fictional-demo", "version": "1.0", "submitted": True, "answers": {"Q1": "A", "Q2": ["A", "B"], "Q3": "圆"}, "manual_scores": {"Q4": "2"}}
    snapshot = copy.deepcopy(manifest["layout"])
    snapshot["evidence"] = {"source": "synthetic", "captured_at": "2000-01-01T00:00:00Z", "reference": "unit-test fixture, not live data"}
    return manifest, response, snapshot


class ExamGuardTests(unittest.TestCase):
    def setUp(self):
        self.manifest, self.response, self.snapshot = fixture()

    def score(self, qid):
        result = guard.grade(self.manifest, self.response)
        return next(row["score"] for row in result["questions"] if row["id"] == qid)

    def test_valid_manifest_and_decimal_conservation(self):
        self.assertEqual(guard.validate_manifest(self.manifest)["status"], "valid")
        self.assertEqual(guard.grade(self.manifest, self.response)["final"], "100.00")

    def test_single_wrong_declared_option_zero(self):
        self.response["answers"]["Q1"] = "B"
        self.assertEqual(self.score("Q1"), "0")

    def test_single_text_instead_of_key_rejected(self):
        self.response["answers"]["Q1"] = "Alpha"
        self.assertEqual(guard.grade(self.manifest, self.response)["status"], "invalid")

    def test_multi_order_irrelevant(self):
        self.response["answers"]["Q2"] = ["B", "A"]
        self.assertEqual(self.score("Q2"), "0.2")

    def test_multi_under_selection_zero(self):
        self.response["answers"]["Q2"] = ["A"]
        self.assertEqual(self.score("Q2"), "0")

    def test_multi_over_selection_zero(self):
        self.response["answers"]["Q2"] = ["A", "B", "C"]
        self.assertEqual(self.score("Q2"), "0")

    def test_multi_duplicate_invalid(self):
        self.response["answers"]["Q2"] = ["A", "A", "B"]
        self.assertEqual(guard.grade(self.manifest, self.response)["status"], "invalid")

    def test_fill_exact_approved_variant(self):
        self.response["answers"]["Q3"] = "Round"
        self.assertEqual(self.score("Q3"), "0.7")

    def test_fill_does_not_normalize_or_infer_semantics(self):
        for answer in ("round", "Round ", "圆形", "Ｒｏｕｎｄ"):
            with self.subTest(answer=answer):
                self.response["answers"]["Q3"] = answer
                self.assertEqual(self.score("Q3"), "0")

    def test_unconfirmed_fill_normalization_rejected(self):
        self.manifest["questions"][2]["normalization"] = "casefold"
        self.assertEqual(guard.validate_manifest(self.manifest)["status"], "invalid")

    def test_manual_missing_pending_not_zero(self):
        self.response["manual_scores"] = {}
        result = guard.grade(self.manifest, self.response)
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["pending_questions"], ["Q4"])
        self.assertIsNone(result["final"])
        self.assertIsNone(result["sections"][1]["raw_score"])

    def test_manual_explicit_zero_complete(self):
        self.response["manual_scores"]["Q4"] = 0
        result = guard.grade(self.manifest, self.response)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["final"], "40.00")

    def test_manual_numeric_limits(self):
        for score in ("-0.1", "2.1", True, "NaN", "Infinity", "not numeric"):
            with self.subTest(score=score):
                self.response["manual_scores"]["Q4"] = score
                self.assertEqual(guard.grade(self.manifest, self.response)["status"], "invalid")

    def test_manual_dynamic_and_essay_supported(self):
        del self.manifest["layout"]
        for kind in ("dynamic", "essay"):
            self.manifest["questions"][3]["type"] = kind
            self.assertEqual(guard.grade(self.manifest, self.response)["final"], "100.00")

    def test_draft_not_graded(self):
        self.response["submitted"] = False
        self.response["answers"] = {}
        result = guard.grade(self.manifest, self.response)
        self.assertEqual(result["status"], "not_submitted")
        self.assertIsNone(result["final"])
        self.assertEqual(result["questions"], [])

    def test_submitted_missing_objective_answer_zero(self):
        del self.response["answers"]["Q1"]
        result = guard.grade(self.manifest, self.response)
        self.assertEqual(result["questions"][0]["status"], "unanswered")
        self.assertEqual(result["final"], "96.00")

    def test_submitted_flag_required(self):
        del self.response["submitted"]
        self.assertEqual(guard.grade(self.manifest, self.response)["status"], "invalid")

    def test_wrong_exam_version_rejected(self):
        self.response["version"] = "2.0"
        self.assertEqual(guard.grade(self.manifest, self.response)["status"], "invalid")

    def test_unknown_answer_and_objective_override_rejected(self):
        self.response["answers"]["Q99"] = "A"
        self.response["manual_scores"]["Q1"] = "0.1"
        self.assertEqual(len(guard.grade(self.manifest, self.response)["errors"]), 2)

    def test_duplicate_question_id_invalid(self):
        self.manifest["questions"][1]["id"] = "Q1"
        self.assertEqual(guard.validate_manifest(self.manifest)["status"], "invalid")

    def test_malformed_fields_report_all_errors(self):
        self.manifest["questions"][0].update(stem="", source="", max_score=0)
        result = guard.validate_manifest(self.manifest)
        self.assertEqual(result["status"], "invalid")
        self.assertGreaterEqual(len(result["errors"]), 3)

    def test_wrong_section_and_total_maximum_invalid(self):
        self.manifest["sections"][0]["raw_max"] = "2"
        self.manifest["total_max"] = "101"
        errors = guard.validate_manifest(self.manifest)["errors"]
        self.assertTrue(any(e["path"] == "sections.auto.raw_max" for e in errors))
        self.assertTrue(any(e["path"] == "total_max" for e in errors))

    def test_rubric_conservation(self):
        self.manifest["questions"][3]["rubric"][0]["max_score"] = "1.4"
        self.assertEqual(guard.validate_manifest(self.manifest)["status"], "invalid")

    def test_duplicate_choice_text_or_unknown_standard_answer(self):
        self.manifest["questions"][0]["options"][1]["text"] = "Alpha"
        self.manifest["questions"][0]["answer"] = "D"
        result = guard.validate_manifest(self.manifest)
        self.assertTrue(any("duplicate option text" in e["message"] for e in result["errors"]))
        self.assertTrue(any(e["path"].endswith(".answer") for e in result["errors"]))

    def test_exact_rational_half_up(self):
        from fractions import Fraction
        self.assertEqual(guard.rounded(Fraction(201, 200), 2), "1.01")
        self.assertEqual(guard.rounded(Fraction(1, 3), 2), "0.33")
        self.response["manual_scores"]["Q4"] = Decimal("0.1")
        self.assertEqual(guard.grade(self.manifest, self.response)["final"], "43.00")

    def test_matching_synthetic_snapshot_is_not_live_verified(self):
        result = guard.audit(self.manifest, self.snapshot)
        self.assertEqual(result["status"], "normalized_snapshot_match")
        self.assertEqual(result["scope"], "synthetic_fixture")
        self.assertFalse(result["live_verified"])

    def test_claimed_live_readback_still_not_authenticated(self):
        self.snapshot["evidence"]["source"] = "live_readback"
        result = guard.audit(self.manifest, self.snapshot)
        self.assertFalse(result["live_verified"])
        self.assertEqual(result["scope"], "provided_readback_only")

    def test_missing_evidence_rejected(self):
        del self.snapshot["evidence"]
        self.assertEqual(guard.audit(self.manifest, self.snapshot)["status"], "invalid")

    def test_field_id_mismatch(self):
        self.snapshot["forms"][0]["questions"][0]["field_id"] = "fldQ2"
        result = guard.audit(self.manifest, self.snapshot)
        self.assertEqual(result["status"], "differences")
        self.assertTrue(any(e["path"].endswith(".field_id") for e in result["diffs"]))

    def test_title_only_sync_does_not_hide_stale_field_name(self):
        self.snapshot["fields"][0]["name"] = "E03"
        result = guard.audit(self.manifest, self.snapshot)
        self.assertTrue(any(e["path"] == "fields.fldQ1.name" for e in result["diffs"]))

    def test_wrong_canonical_field_name_rejected_even_when_snapshot_matches(self):
        self.manifest["layout"]["fields"][0]["name"] = "E03"
        self.snapshot["fields"][0]["name"] = "E03"
        result = guard.audit(self.manifest, self.snapshot)
        self.assertEqual(result["status"], "invalid")
        self.assertTrue(any(e["path"] == "fields[0].name" for e in result["errors"]))

    def test_wrong_canonical_field_description_type_options_rejected(self):
        self.manifest["layout"]["fields"][0].update(description="wrong", type="text", options=[])
        result = guard.validate_manifest(self.manifest)
        self.assertEqual(result["status"], "invalid")
        for prop in ("description", "type", "options"):
            self.assertTrue(any(e["path"] == "fields[0]." + prop for e in result["errors"]))

    def test_wrong_canonical_form_title_and_type_rejected(self):
        self.manifest["layout"]["forms"][0]["questions"][0].update(title="E03", type="text")
        result = guard.validate_manifest(self.manifest)
        self.assertEqual(result["status"], "invalid")
        for prop in ("title", "type"):
            self.assertTrue(any(e["path"] == "forms[0].questions[0]." + prop for e in result["errors"]))

    def test_explicit_presentation_preserves_level_score_material_text(self):
        q = self.manifest["questions"][0]
        q.update(field_name="Q1 - Basic choice", field_description="L1 | Choose Alpha | 0.1 points",
                 form_title="Q1（必答）", form_description="L1 | Choose Alpha | 0.1 points | See approved materials")
        field = self.manifest["layout"]["fields"][0]
        field.update(name=q["field_name"], description=q["field_description"])
        form_q = self.manifest["layout"]["forms"][0]["questions"][0]
        form_q.update(title=q["form_title"], description=q["form_description"])
        self.snapshot["fields"][0].update(name=q["field_name"], description=q["field_description"])
        self.snapshot["forms"][0]["questions"][0].update(title=q["form_title"], description=q["form_description"])
        self.assertEqual(guard.audit(self.manifest, self.snapshot)["status"], "normalized_snapshot_match")
        self.snapshot["forms"][0]["questions"][0]["description"] = q["stem"]
        self.assertEqual(guard.audit(self.manifest, self.snapshot)["status"], "differences")

    def test_secondary_primary_control_does_not_silently_pass(self):
        extra = copy.deepcopy(self.manifest["layout"]["fields"][0])
        extra["field_id"] = "fldAttachment"
        self.manifest["layout"]["fields"].append(extra)
        self.assertEqual(guard.validate_manifest(self.manifest)["status"], "invalid")

    def test_auxiliary_null_question_field_exact_comparison(self):
        extra = {"field_id": "fldAttachment", "question_id": None, "name": "Supporting attachment", "type": "attachment", "description": "Secondary control, independently audited", "options": []}
        self.manifest["layout"]["fields"].append(copy.deepcopy(extra))
        self.snapshot["fields"].append(copy.deepcopy(extra))
        self.assertEqual(guard.audit(self.manifest, self.snapshot)["status"], "normalized_snapshot_match")
        self.snapshot["fields"][-1]["name"] = "Wrong field"
        self.assertEqual(guard.audit(self.manifest, self.snapshot)["status"], "differences")

    def test_grid_order_separately_audited(self):
        self.snapshot["grid_order"].reverse()
        result = guard.audit(self.manifest, self.snapshot)
        self.assertEqual([e["path"] for e in result["diffs"]], ["grid_order"])

    def test_form_order_separately_audited(self):
        self.snapshot["forms"][0]["questions"].reverse()
        self.snapshot["forms"][0]["question_order"].reverse()
        result = guard.audit(self.manifest, self.snapshot)
        self.assertTrue(any(e["path"] == "forms.form-demo.question_order" for e in result["diffs"]))

    def test_option_required_description_all_differences_reported(self):
        q = self.snapshot["forms"][0]["questions"][0]
        q["options"][0]["text"] = "Wrong option"
        q["required"] = False
        q["description"] = "Wrong stem"
        result = guard.audit(self.manifest, self.snapshot)
        self.assertGreaterEqual(len(result["diffs"]), 3)

    def test_snapshot_duplicate_field_invalid_not_silently_overwritten(self):
        self.snapshot["fields"].append(copy.deepcopy(self.snapshot["fields"][0]))
        self.assertEqual(guard.audit(self.manifest, self.snapshot)["status"], "differences")

    def test_multiple_grids_and_table_boundaries(self):
        layout = self.manifest["layout"]
        del layout["grid_order"]
        for field in layout["fields"]:
            field["table_id"] = "answer-table"
        layout["forms"][0]["table_id"] = "answer-table"
        layout["fields"].append({"field_id": "fldTotal", "question_id": None, "name": "Total", "type": "formula", "description": "Total", "options": [], "table_id": "score-table"})
        layout["grids"] = [{"table_id": "answer-table", "view_id": "grid-answer", "field_order": ["fldQ1", "fldQ2", "fldQ3", "fldQ4"]}, {"table_id": "score-table", "view_id": "grid-score", "field_order": ["fldTotal"]}]
        self.snapshot = copy.deepcopy(layout)
        self.snapshot["evidence"] = fixture()[2]["evidence"]
        self.assertEqual(guard.audit(self.manifest, self.snapshot)["status"], "normalized_snapshot_match")
        self.snapshot["grids"][1]["field_order"] = ["fldQ1"]
        result = guard.audit(self.manifest, self.snapshot)
        self.assertEqual(result["status"], "differences")
        self.assertTrue(any(e["path"] == "grids.score-table/grid-score" for e in result["diffs"]))

    def test_cli_json_output_and_exit_statuses(self):
        cases = [("validate", [self.manifest], 0), ("grade", [self.manifest, self.response], 0), ("audit", [self.manifest, self.snapshot], 0)]
        pending = copy.deepcopy(self.response)
        pending["manual_scores"] = {}
        cases.append(("grade", [self.manifest, pending], 4))
        invalid = copy.deepcopy(self.manifest)
        invalid["total_max"] = 99
        cases.append(("validate", [invalid], 2))
        different = copy.deepcopy(self.snapshot)
        different["grid_order"].reverse()
        cases.append(("audit", [self.manifest, different], 3))
        for command, inputs, expected_exit in cases:
            with self.subTest(command=command, expected_exit=expected_exit):
                output = io.StringIO()
                with patch.object(guard, "load_json", side_effect=inputs), contextlib.redirect_stdout(output):
                    code = guard.main([command, "manifest.json"] + (["input.json"] if len(inputs) == 2 else []))
                self.assertEqual(code, expected_exit)
                self.assertIn("status", json.loads(output.getvalue()))


if __name__ == "__main__":
    unittest.main()
