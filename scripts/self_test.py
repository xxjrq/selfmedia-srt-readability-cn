#!/usr/bin/env python3
"""Independent, portable fixtures for the SRT readability helper."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "srt_readability.py"
sys.path.insert(0, str(ROOT / "scripts"))
from srt_readability import process, wrap  # noqa: E402


def run_cli(raw: str, width: int, max_lines: int, forbidden: str = "", output_path: Path | None = None) -> tuple[int, dict]:
    with tempfile.TemporaryDirectory(prefix="srt-readability-") as directory:
        path = Path(directory) / "input.srt"
        path.write_text(raw, encoding="utf-8")
        args = [sys.executable, str(SCRIPT), str(path), "--total-seconds", "10", "--line-width", str(width), "--max-lines", str(max_lines)]
        if output_path is not None:
            args.extend(["--output", str(output_path)])
        if forbidden:
            args.extend(["--forbid", forbidden])
        result = subprocess.run(args, text=True, capture_output=True, check=False)
        return result.returncode, json.loads(result.stdout)


def main() -> int:
    success = ROOT / "fixtures" / "success"
    result = process((success / "input.srt").read_text(), 10, 20, 2, ["人工智能"])
    assert result["status"] == "ok", result
    assert result["srt"] == (success / "expected.srt").read_text(), result["srt"]
    source = "".join(line for line in (success / "input.srt").read_text().splitlines() if line and not line.isdigit() and "-->" not in line)
    wrapped = "".join(line for line in result["srt"].splitlines() if line and not line.isdigit() and "-->" not in line)
    assert source == wrapped, "文字不应变化"
    failure = ROOT / "fixtures" / "failure"
    bad = process((failure / "input.srt").read_text(), 10, 20, 2, [])
    assert bad == json.loads((failure / "expected.json").read_text()), bad
    duplicate = process("1\n00:00:00,000 --> 00:00:01,000\n甲\n\n1\n00:00:00,500 --> 00:00:02,000\n乙", 10, 20, 2, [])
    assert duplicate["status"] == "invalid" and any(x["error"] == "cue编号重复" for x in duplicate["errors"]), duplicate
    reverse = process("1\n00:00:03,000 --> 00:00:04,000\n甲\n\n2\n00:00:02,000 --> 00:00:05,000\n乙", 10, 20, 2, [])
    assert reverse["status"] == "invalid" and any(x["error"] == "cue开始时间早于前一条cue" for x in reverse["errors"]), reverse
    joined_cues = process("1\n00:00:00,000 --> 00:00:01,000\n甲\n2\n00:00:01,000 --> 00:00:02,000\n乙", 10, 20, 2, [])
    joined_expected = json.loads((failure / "missing-blank-line.expected.json").read_text())
    assert joined_cues == joined_expected, joined_cues
    second_bad_time = process("1\n00:00:00,000 --> 00:00:01,000\n甲\n\n2\n不是时间码\n乙", 10, 20, 2, [])
    assert any(x.get("cue") == "2" and x["line"] == 6 for x in second_bad_time["errors"]), second_bad_time
    second_empty_body = process("1\n00:00:00,000 --> 00:00:01,000\n甲\n\n2\n00:00:01,000 --> 00:00:02,000", 10, 20, 2, [])
    assert any(x.get("cue") == 2 and x["line"] == 7 and x["error"] == "字幕文字为空" for x in second_empty_body["errors"]), second_empty_body
    bad_clock = process("1\n00:00:60,000 --> 00:01:01,000\n甲", 100, 20, 2, [])
    assert bad_clock["status"] == "invalid" and any(x["error"] == "时间码分和秒必须小于60" for x in bad_clock["errors"]), bad_clock
    tab_arrow = process("1\n00:00:00,000\t-->\t00:00:01,000\n甲", 10, 20, 2, [])
    assert tab_arrow["status"] == "ok", tab_arrow
    code, feasible = run_cli("1\n00:00:00,000 --> 00:00:01,000\n甲，甲甲甲甲", 3, 2)
    assert code == 0 and feasible["status"] == "ok", feasible
    lines = feasible["srt"].splitlines()[2:]
    assert lines == ["甲，甲", "甲甲甲"] and max(map(len, lines)) <= 3, feasible
    code, overlap = run_cli("001\n00:00:00,000 --> 00:00:01,000\n人工智能工具可用", 6, 2, "人工智能,智能工具")
    assert code == 0 and overlap["status"] == "ok", overlap
    assert overlap["srt"].startswith("001\n") and overlap["srt"].splitlines()[2:4] == ["人工智能工具", "可用"], overlap
    code, empty_body = run_cli("001\n00:00:00,000 --> 00:00:01,000\n", 20, 2)
    assert code == 2 and empty_body["status"] == "invalid", empty_body
    assert any(error.get("cue") == 1 and error.get("line") == 3 and error["error"] == "字幕文字为空" for error in empty_body["errors"]), empty_body
    code, empty_file = run_cli("", 20, 2)
    assert code == 2 and empty_file["status"] == "invalid" and empty_file["errors"][0]["line"] == 1, empty_file
    code, bom_srt = run_cli((success / "input-bom.srt").read_text(encoding="utf-8"), 20, 2)
    assert code == 0 and bom_srt["status"] == "ok" and bom_srt["srt"].startswith("1\n"), bom_srt
    with tempfile.TemporaryDirectory(prefix="srt-output-guard-") as directory:
        output_path = Path(directory) / "out.srt"
        output_path.write_text("keep old artifact", encoding="utf-8")
        code, too_many_lines = run_cli("1\n00:00:00,000 --> 00:00:01,000\n甲乙丙丁戊己庚", 3, 2, output_path=output_path)
        assert code != 0 and too_many_lines["status"] == "over_budget" and too_many_lines["srt"] is None, too_many_lines
        assert too_many_lines["over_budget"][0]["lines"] == 3 and output_path.read_text() == "keep old artifact", too_many_lines
        missing_output = Path(directory) / "must-not-exist.srt"
        code, overrun = run_cli("1\n00:00:00,000 --> 00:00:01,000\n甲乙丙丁戊己庚", 3, 2, output_path=missing_output)
        assert code != 0 and overrun["status"] == "over_budget" and not missing_output.exists(), overrun
    code, indivisible = run_cli("1\n00:00:00,000 --> 00:00:01,000\n甲人工智能乙", 3, 3, "人工智能")
    assert code != 0 and indivisible["status"] == "over_budget" and indivisible["over_budget"][0]["longest_line"] == 4, indivisible
    assert "最小不可避免超限" in indivisible["over_budget"][0]["reason"] and indivisible["srt"] is None, indivisible
    wrapped_lines, wrapped_reason = wrap("甲人工智能乙", 3, 3, ["人工智能"])
    assert wrapped_lines == ["甲", "人工智能", "乙"] and "最小不可避免超限" in wrapped_reason, (wrapped_lines, wrapped_reason)
    print("PASS: actual CLI DP, overlap-merged forbidden terms, failed/no-write budget gate, minimum unavoidable overrun, cue numbering, and precise empty-text errors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
