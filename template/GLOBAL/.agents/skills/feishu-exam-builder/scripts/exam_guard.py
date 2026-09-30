#!/usr/bin/env python3
"""Offline exam checks; reads JSON and prints JSON. No network or file writes.

validate MANIFEST; grade MANIFEST RESPONSE; audit MANIFEST SNAPSHOT.
Exit 0: valid/complete/matching; 2: invalid input; 3: snapshot differences;
4: pending manual review or not submitted. Scores are decimal strings in output.
This is NOT a Feishu API adapter, evidence authenticator, or semantic grader.
Layout schema supports one primary form control per canonical question. Other
fields may be listed with question_id:null for exact snapshot comparison, but
secondary attachment/control mappings need a separate full-control audit.
Normalize platform types to single/multi/fill/dynamic/essay/practical before
comparison; retain raw API exports separately rather than fabricating a type.
"""

import argparse
import json
import sys
from decimal import Decimal, InvalidOperation, localcontext
from fractions import Fraction
from pathlib import Path

MANUAL_TYPES = {"dynamic", "essay", "practical"}
TYPES = {"single", "multi", "fill"} | MANUAL_TYPES


def issue(errors, path, message):
    errors.append({"path": path, "message": message})


def text_ok(value):
    return isinstance(value, str) and bool(value.strip())


def number(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError("must be a finite decimal number, not boolean/null")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("must be a finite decimal number") from exc
    if not result.is_finite():
        raise ValueError("must be finite")
    return result


def numeric(value, path, errors, positive=False):
    try:
        result = number(value)
        if result < 0 or (positive and result == 0):
            raise ValueError("must be positive" if positive else "must be nonnegative")
        return result
    except ValueError as exc:
        issue(errors, path, str(exc))
        return None


def exact_sum(values):
    # Decimal parsing plus rational arithmetic avoids context rounding on sums
    # and recurring ratios. Only the requested final decimal rounding is applied.
    return sum((Fraction(v) for v in values), Fraction(0))


def decimal_string(value):
    if isinstance(value, Fraction):
        with localcontext() as ctx:
            ctx.prec = max(50, len(str(abs(value.numerator))) + len(str(value.denominator)) + 10)
            value = Decimal(value.numerator) / Decimal(value.denominator)
    result = format(value, "f")
    return result.rstrip("0").rstrip(".") if "." in result else result


def rounded(value, places):
    # Exact half-up rounding, even if a rational contribution repeats forever.
    scaled = value * (10 ** places)
    units, remainder = divmod(scaled.numerator, scaled.denominator)
    if 2 * remainder >= scaled.denominator:
        units += 1
    return format(Decimal(units).scaleb(-places), f".{places}f")


def object_list(value, path, errors, nonempty=True):
    if not isinstance(value, list) or (nonempty and not value):
        issue(errors, path, "must be a nonempty array" if nonempty else "must be an array")
        return []
    result = []
    for i, row in enumerate(value):
        if not isinstance(row, dict):
            issue(errors, f"{path}[{i}]", "must be an object")
        else:
            result.append(row)
    return result


def indexed(rows, key, path, errors):
    result = {}
    for i, row in enumerate(rows):
        ident = row.get(key)
        if not text_ok(ident):
            issue(errors, f"{path}[{i}].{key}", "must be a nonempty string")
        elif ident in result:
            issue(errors, f"{path}[{i}].{key}", f"duplicate ID: {ident}")
        else:
            result[ident] = row
    return result


def options_check(options, path, errors, required=False):
    rows = object_list(options, path, errors, nonempty=required)
    if required and len(rows) < 2:
        issue(errors, path, "choice questions need at least two options")
    keys = indexed(rows, "key", path, errors)
    texts = set()
    for i, row in enumerate(rows):
        value = row.get("text")
        if not text_ok(value):
            issue(errors, f"{path}[{i}].text", "must be a nonempty string")
        elif value.strip() in texts:
            issue(errors, f"{path}[{i}].text", "duplicate option text")
        else:
            texts.add(value.strip())
    return keys


def validate_manifest(manifest):
    errors = []
    if not isinstance(manifest, dict):
        return {"status": "invalid", "errors": [{"path": "$", "message": "must be an object"}]}
    if type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1:
        issue(errors, "schema_version", "must be integer 1")
    for key in ("exam_id", "version"):
        if not text_ok(manifest.get(key)):
            issue(errors, key, "must be a nonempty string")
    total = numeric(manifest.get("total_max"), "total_max", errors, True)
    rounding = manifest.get("rounding", {})
    if not isinstance(rounding, dict):
        issue(errors, "rounding", "must be an object")
    else:
        places = rounding.get("places", 2)
        if type(places) is not int or not 0 <= places <= 12:
            issue(errors, "rounding.places", "must be an integer from 0 to 12")
        if rounding.get("mode", "HALF_UP") != "HALF_UP":
            issue(errors, "rounding.mode", "only HALF_UP is supported")
    sections = object_list(manifest.get("sections"), "sections", errors)
    section_map = indexed(sections, "id", "sections", errors)
    raw_values, contributions = {}, []
    for i, section in enumerate(sections):
        raw = numeric(section.get("raw_max"), f"sections[{i}].raw_max", errors, True)
        contribution = numeric(section.get("contribution_max"), f"sections[{i}].contribution_max", errors, True)
        if text_ok(section.get("id")) and raw is not None:
            raw_values[section["id"]] = raw
        if contribution is not None:
            contributions.append(contribution)
    questions = object_list(manifest.get("questions"), "questions", errors)
    question_map = indexed(questions, "id", "questions", errors)
    section_scores = {sid: [] for sid in section_map}
    for i, q in enumerate(questions):
        path = f"questions[{i}]"
        for key in ("stem", "source"):
            if not text_ok(q.get(key)):
                issue(errors, path + "." + key, "must be a nonempty string")
        # Optional presentation expectations are explicit, not inferred from
        # live data. They preserve level/score/material text in real forms.
        for key in ("field_name", "field_description", "form_title", "form_description"):
            if key in q and not text_ok(q[key]):
                issue(errors, path + "." + key, "must be a nonempty string when provided")
        if type(q.get("required")) is not bool:
            issue(errors, path + ".required", "must be an explicit boolean")
        kind = q.get("type")
        if not isinstance(kind, str) or kind not in TYPES:
            issue(errors, path + ".type", "unsupported question type")
            kind = "invalid"
        maximum = numeric(q.get("max_score"), path + ".max_score", errors, True)
        sid = q.get("section_id")
        if not isinstance(sid, str) or sid not in section_map:
            issue(errors, path + ".section_id", "unknown section")
        elif maximum is not None:
            section_scores[sid].append(maximum)
        if kind in {"single", "multi"}:
            keys = options_check(q.get("options"), path + ".options", errors, True)
            answer = q.get("answer")
            if kind == "single":
                if not isinstance(answer, str) or answer not in keys:
                    issue(errors, path + ".answer", "must be one declared option key")
            elif (not isinstance(answer, list) or not answer or
                  any(not isinstance(a, str) or a not in keys for a in answer) or
                  len(set(a for a in answer if isinstance(a, str))) != len(answer)):
                issue(errors, path + ".answer", "must be a nonempty unique array of declared option keys")
        elif kind == "fill":
            accepted = q.get("accepted_answers")
            if (not isinstance(accepted, list) or not accepted or
                    any(not text_ok(a) for a in accepted) or
                    len(set(a for a in accepted if isinstance(a, str))) != len(accepted)):
                issue(errors, path + ".accepted_answers", "must explicitly list unique approved nonempty strings")
            if q.get("normalization", "exact") != "exact":
                issue(errors, path + ".normalization", "only exact matching is supported; list approved variants explicitly")
        elif kind in MANUAL_TYPES:
            rubric = object_list(q.get("rubric"), path + ".rubric", errors)
            indexed(rubric, "id", path + ".rubric", errors)
            points = []
            for j, item in enumerate(rubric):
                if not text_ok(item.get("description")):
                    issue(errors, f"{path}.rubric[{j}].description", "must be nonempty")
                point = numeric(item.get("max_score"), f"{path}.rubric[{j}].max_score", errors, True)
                if point is not None:
                    points.append(point)
            if maximum is not None and len(points) == len(rubric) and exact_sum(points) != Fraction(maximum):
                issue(errors, path + ".rubric", "rubric points do not sum to question max_score")
    for sid, raw in raw_values.items():
        if exact_sum(section_scores.get(sid, [])) != Fraction(raw):
            issue(errors, "sections." + sid + ".raw_max", "does not equal question maximum sum")
    if total is not None and len(contributions) == len(sections) and exact_sum(contributions) != Fraction(total):
        issue(errors, "total_max", "does not equal section contribution_max sum")
    if "layout" in manifest:
        errors.extend(validate_layout(manifest["layout"], question_map))
    return {"status": "invalid" if errors else "valid", "errors": errors,
            "question_count": len(questions), "section_count": len(sections)}


def validate_layout(layout, question_map=None):
    errors = []
    if not isinstance(layout, dict):
        return [{"path": "layout", "message": "must be an object"}]
    fields = object_list(layout.get("fields"), "fields", errors)
    field_map = indexed(fields, "field_id", "fields", errors)
    primary_fields = set()
    for i, field in enumerate(fields):
        for key in ("name", "type"):
            if not text_ok(field.get(key)):
                issue(errors, f"fields[{i}].{key}", "must be nonempty")
        for key in ("question_id", "description", "options"):
            if key not in field:
                issue(errors, f"fields[{i}].{key}", "missing normalized property")
        if not isinstance(field.get("description"), str):
            issue(errors, f"fields[{i}].description", "must be a string")
        options_check(field.get("options"), f"fields[{i}].options", errors)
        qid = field.get("question_id")
        if qid is not None and (not isinstance(qid, str) or (question_map is not None and qid not in question_map)):
            issue(errors, f"fields[{i}].question_id", "unknown question ID")
        elif isinstance(qid, str):
            if qid in primary_fields:
                issue(errors, f"fields[{i}].question_id", "only one primary input field per canonical question is supported")
            primary_fields.add(qid)
            if question_map is not None and qid in question_map:
                q = question_map[qid]
                for key, expected in (("name", q.get("field_name", qid)),
                                      ("description", q.get("field_description", q.get("stem"))),
                                      ("type", q.get("type")), ("options", q.get("options", []))):
                    if field.get(key) != expected:
                        issue(errors, f"fields[{i}].{key}", "does not match canonical question")
    if question_map is not None and primary_fields != set(question_map):
        issue(errors, "fields", "must contain one primary field for every canonical question")
    if "grids" not in layout and "grid_order" not in layout:
        issue(errors, "grids", "grids or single-table grid_order is required")
    if "grid_order" in layout:
        grid = layout["grid_order"]
        if not isinstance(grid, list) or any(not isinstance(x, str) for x in grid):
            issue(errors, "grid_order", "must be an array of field IDs")
        elif len(set(grid)) != len(grid) or any(fid not in field_map for fid in grid):
            issue(errors, "grid_order", "duplicate or unknown field ID")
    if "grids" in layout:
        grids = object_list(layout["grids"], "grids", errors)
        seen = set()
        for i, grid in enumerate(grids):
            tid, vid = grid.get("table_id"), grid.get("view_id")
            if not text_ok(tid) or not text_ok(vid):
                issue(errors, f"grids[{i}]", "table_id and view_id must be nonempty strings")
            else:
                identity = (tid, vid)
                if identity in seen:
                    issue(errors, f"grids[{i}]", "duplicate table/view identity")
                seen.add(identity)
            order = grid.get("field_order")
            if not isinstance(order, list) or any(not isinstance(x, str) for x in order):
                issue(errors, f"grids[{i}].field_order", "must be an array of field IDs")
            elif len(set(order)) != len(order) or any(fid not in field_map for fid in order):
                issue(errors, f"grids[{i}].field_order", "duplicate or unknown field ID")
            else:
                for fid in order:
                    if field_map[fid].get("table_id") != tid:
                        issue(errors, f"grids[{i}].field_order", f"{fid} belongs to a different/unspecified table")
        for i, field in enumerate(fields):
            if not text_ok(field.get("table_id")):
                issue(errors, f"fields[{i}].table_id", "required with multi-table grids")
    forms = object_list(layout.get("forms"), "forms", errors)
    indexed(forms, "form_id", "forms", errors)
    represented = set()
    for i, form in enumerate(forms):
        prefix = f"forms[{i}]"
        if "grids" in layout and not text_ok(form.get("table_id")):
            issue(errors, prefix + ".table_id", "required with multi-table grids")
        items = object_list(form.get("questions"), prefix + ".questions", errors)
        indexed(items, "question_id", prefix + ".questions", errors)
        declared_order = form.get("question_order")
        actual_order = [item.get("question_id") for item in items]
        if declared_order != actual_order:
            issue(errors, prefix + ".question_order", "must match questions array order exactly")
        for j, item in enumerate(items):
            path = f"{prefix}.questions[{j}]"
            qid, fid = item.get("question_id"), item.get("field_id")
            if isinstance(qid, str):
                represented.add(qid)
            if not isinstance(fid, str) or fid not in field_map:
                issue(errors, path + ".field_id", "unknown field ID")
            elif field_map[fid].get("question_id") != qid:
                issue(errors, path + ".field_id", "field ID maps to a different question")
            elif "grids" in layout and field_map[fid].get("table_id") != form.get("table_id"):
                issue(errors, path + ".field_id", "form field belongs to a different table")
            for key in ("title", "description", "type"):
                if not text_ok(item.get(key)):
                    issue(errors, path + "." + key, "must be nonempty")
            if type(item.get("required")) is not bool:
                issue(errors, path + ".required", "must be an explicit boolean")
            options_check(item.get("options"), path + ".options", errors)
            if question_map is not None:
                q = question_map.get(qid) if isinstance(qid, str) else None
                if q is None:
                    issue(errors, path + ".question_id", "unknown question ID")
                else:
                    for key, expected in (("title", q.get("form_title", qid)),
                                          ("description", q.get("form_description", q.get("stem"))),
                                          ("type", q.get("type")), ("required", q.get("required")),
                                          ("options", q.get("options", []))):
                        if item.get(key) != expected:
                            issue(errors, path + "." + key, "does not match canonical question")
    if question_map is not None and represented != set(question_map):
        issue(errors, "forms", "must cover every canonical question; no unlisted questions")
    return errors


def grade(manifest, response):
    validation = validate_manifest(manifest)
    if validation["errors"]:
        return validation
    errors = []
    if not isinstance(response, dict):
        return {"status": "invalid", "errors": [{"path": "response", "message": "must be an object"}]}
    for key in ("exam_id", "version"):
        if response.get(key) != manifest[key]:
            issue(errors, key, "does not match manifest")
    if type(response.get("submitted")) is not bool:
        issue(errors, "submitted", "must explicitly distinguish submitted response from draft")
    answers, manual = response.get("answers", {}), response.get("manual_scores", {})
    qmap = {q["id"]: q for q in manifest["questions"]}
    for label, values in (("answers", answers), ("manual_scores", manual)):
        if not isinstance(values, dict):
            issue(errors, label, "must be an object keyed by question ID")
            continue
        for qid in values:
            if qid not in qmap:
                issue(errors, label + "." + qid, "unknown question ID")
            elif label == "manual_scores" and qmap[qid]["type"] not in MANUAL_TYPES:
                issue(errors, label + "." + qid, "cannot override an objective score")
    if errors:
        return {"status": "invalid", "errors": errors, "final": None}
    if not response["submitted"]:
        return {"status": "not_submitted", "errors": [], "questions": [], "sections": [], "final": None}
    result, by_section = [], {s["id"]: [] for s in manifest["sections"]}
    for q in manifest["questions"]:
        qid, kind, maximum = q["id"], q["type"], number(q["max_score"])
        answer = answers.get(qid)
        score, state = None, "pending_manual"
        if kind in MANUAL_TYPES:
            if manual.get(qid) is not None:
                score = numeric(manual[qid], "manual_scores." + qid, errors)
                if score is not None and score > maximum:
                    issue(errors, "manual_scores." + qid, "exceeds question maximum")
                state = "manual_scored"
        else:
            empty = answer is None or answer == "" or answer == []
            if empty:
                score, state = Decimal(0), "unanswered"
            elif kind == "single":
                if not isinstance(answer, str) or answer not in {o["key"] for o in q["options"]}:
                    issue(errors, "answers." + qid, "must be a declared option key")
                else:
                    score = maximum if answer == q["answer"] else Decimal(0)
                    state = "correct" if score else "incorrect"
            elif kind == "multi":
                keys = {o["key"] for o in q["options"]}
                if (not isinstance(answer, list) or any(not isinstance(a, str) or a not in keys for a in answer) or
                        len(set(a for a in answer if isinstance(a, str))) != len(answer)):
                    issue(errors, "answers." + qid, "must be a unique array of declared option keys")
                else:
                    score = maximum if set(answer) == set(q["answer"]) else Decimal(0)
                    state = "correct" if score else "incorrect"
            else:
                if not isinstance(answer, str):
                    issue(errors, "answers." + qid, "fill answer must be a string")
                else:
                    score = maximum if answer in q["accepted_answers"] else Decimal(0)
                    state = "exact_accepted" if score else "not_in_approved_answers"
        entry = {"id": qid, "section_id": q["section_id"], "status": state,
                 "score": decimal_string(score) if score is not None else None,
                 "max_score": decimal_string(maximum)}
        result.append(entry)
        by_section[q["section_id"]].append(score)
    if errors:
        return {"status": "invalid", "errors": errors, "questions": result, "final": None}
    sections, total, pending = [], Fraction(0), []
    for section in manifest["sections"]:
        sid, values = section["id"], by_section[section["id"]]
        raw = exact_sum(v for v in values if v is not None)
        incomplete = any(v is None for v in values)
        contribution = raw / Fraction(number(section["raw_max"])) * Fraction(number(section["contribution_max"]))
        total += contribution
        sections.append({"id": sid, "status": "pending" if incomplete else "complete",
                         "known_raw": decimal_string(raw), "raw_score": None if incomplete else decimal_string(raw),
                         "contribution_fraction": f"{contribution.numerator}/{contribution.denominator}",
                         "contribution": None if incomplete else decimal_string(contribution)})
    pending = [row["id"] for row in result if row["score"] is None]
    places = manifest.get("rounding", {}).get("places", 2)
    return {"status": "pending" if pending else "complete", "errors": [], "questions": result,
            "sections": sections, "pending_questions": pending, "known_contribution": rounded(total, places),
            "final": None if pending else rounded(total, places), "total_max": decimal_string(number(manifest["total_max"]))}


def audit(manifest, snapshot):
    checked = validate_manifest(manifest)
    if checked["errors"]:
        return checked
    if "layout" not in manifest:
        return {"status": "invalid", "errors": [{"path": "layout", "message": "required for audit"}]}
    if not isinstance(snapshot, dict):
        return {"status": "invalid", "errors": [{"path": "snapshot", "message": "must be an object"}]}
    evidence = snapshot.get("evidence", {})
    evidence_errors = []
    if not isinstance(evidence, dict):
        evidence_errors.append({"path": "evidence", "message": "must be an object"})
        evidence = {}
    if evidence.get("source") not in ("live_readback", "synthetic"):
        issue(evidence_errors, "evidence.source", "must state live_readback or synthetic")
    for key in ("captured_at", "reference"):
        if not text_ok(evidence.get(key)):
            issue(evidence_errors, "evidence." + key, "must identify source artifact/time")
    if evidence_errors:
        return {"status": "invalid", "errors": evidence_errors}
    diffs = [{"path": "snapshot." + e["path"], "message": e["message"]}
             for e in validate_layout(snapshot)]
    expected = manifest["layout"]

    def compare(path, want, got):
        if want != got:
            diffs.append({"path": path, "expected": want, "actual": got})

    def rows_by(rows, key):
        return {r[key]: r for r in rows if isinstance(r, dict) and isinstance(r.get(key), str)} if isinstance(rows, list) else {}

    def compare_rows(path, want_rows, got_rows, key, properties):
        want_map, got_map = rows_by(want_rows, key), rows_by(got_rows, key)
        for ident in sorted(set(want_map) | set(got_map)):
            if ident not in want_map or ident not in got_map:
                compare(path + "." + ident, want_map.get(ident), got_map.get(ident))
            else:
                for prop in properties:
                    compare(f"{path}.{ident}.{prop}", want_map[ident].get(prop), got_map[ident].get(prop))
        return want_map, got_map

    compare_rows("fields", expected["fields"], snapshot.get("fields"), "field_id",
                 ("table_id", "question_id", "name", "type", "description", "options"))
    if "grid_order" in expected or "grid_order" in snapshot:
        compare("grid_order", expected.get("grid_order"), snapshot.get("grid_order"))
    if "grids" in expected or "grids" in snapshot:
        def grid_map(rows):
            return {str(r.get("table_id")) + "/" + str(r.get("view_id")): r
                    for r in rows if isinstance(r, dict)} if isinstance(rows, list) else {}
        want_grids, got_grids = grid_map(expected.get("grids")), grid_map(snapshot.get("grids"))
        for identity in sorted(set(want_grids) | set(got_grids)):
            compare("grids." + identity, want_grids.get(identity), got_grids.get(identity))
    want_forms, got_forms = compare_rows("forms", expected["forms"], snapshot.get("forms"), "form_id", ("table_id", "question_order"))
    for fid in sorted(set(want_forms) & set(got_forms)):
        compare_rows("forms." + fid + ".questions", want_forms[fid]["questions"], got_forms[fid].get("questions"), "question_id",
                     ("field_id", "title", "description", "type", "options", "required"))
    return {"status": "differences" if diffs else "normalized_snapshot_match", "diffs": diffs,
            "evidence": evidence, "scope": "synthetic_fixture" if evidence["source"] == "synthetic" else "provided_readback_only",
            "live_verified": False,
            "limitations": "Offline comparison cannot authenticate provenance or verify UI, permissions, formulas, or live server state. One primary form control per canonical question only; secondary controls/attachments require a separate complete control audit."}


def load_json(path):
    def reject_constant(value):
        raise ValueError("non-finite JSON constant: " + value)
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON property: " + key)
            result[key] = value
        return result
    with Path(path).open("r", encoding="utf-8-sig") as stream:
        return json.load(stream, parse_float=Decimal, parse_constant=reject_constant, object_pairs_hook=unique_object)


def exit_code(result):
    return {"invalid": 2, "differences": 3, "pending": 4, "not_submitted": 4}.get(result["status"], 0)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "grade", "audit"):
        child = sub.add_parser(command)
        child.add_argument("manifest")
        if command != "validate":
            child.add_argument("input", help="response JSON" if command == "grade" else "normalized snapshot JSON")
    args = parser.parse_args(argv)
    try:
        manifest = load_json(args.manifest)
        result = validate_manifest(manifest) if args.command == "validate" else (
            grade(manifest, load_json(args.input)) if args.command == "grade" else audit(manifest, load_json(args.input)))
    except (OSError, ValueError, InvalidOperation) as exc:
        result = {"status": "invalid", "errors": [{"path": "input", "message": str(exc)}]}
    print(json.dumps(result, ensure_ascii=False, indent=2, default=decimal_string))
    return exit_code(result)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
