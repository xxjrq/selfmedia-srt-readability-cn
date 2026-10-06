#!/usr/bin/env python3
"""Conservative SRT validation and display-line wrapping for Chinese subtitles."""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

TIME_PART = r"\d{2}:\d{2}:\d{2},\d{3}"
TIME_RE = re.compile(rf"^(?P<start>{TIME_PART})[ \t]+-->[ \t]+(?P<end>{TIME_PART})$")


def millis(timestamp: str) -> int:
    h, m, s, ms = map(int, re.split(r"[:,]", timestamp))
    return ((h * 60 + m) * 60 + s) * 1000 + ms


@dataclass
class Cue:
    number: int
    number_text: str
    start: str
    end: str
    start_ms: int
    end_ms: int
    text: str


def parse_srt(raw: str, total_ms: int) -> tuple[list[Cue], list[dict]]:
    errors: list[dict] = []
    cues: list[Cue] = []
    previous_number: int | None = None
    previous_start_ms: int | None = None
    normalized = raw.removeprefix("\ufeff").replace("\r\n", "\n")
    blocks: list[tuple[int, list[str]]] = []
    current_lines: list[str] = []
    current_start = 1
    for global_line, line in enumerate(normalized.splitlines(), 1):
        if not line.strip():
            if current_lines:
                blocks.append((current_start, current_lines))
                current_lines = []
            continue
        if not current_lines:
            current_start = global_line
        current_lines.append(line)
    if current_lines:
        blocks.append((current_start, current_lines))
    if not blocks:
        errors.append({"block": 1, "line": 1, "error": "cue结构无效：文件中没有cue"})
    for block_no, (block_start, lines) in enumerate(blocks, 1):
        line_at = lambda local_line: block_start + local_line - 1
        if not lines or not lines[0].isdigit():
            errors.append({"block": block_no, "line": line_at(1), "error": "cue结构无效：需要编号、时间码和文字"})
            continue
        if len(lines) < 2:
            errors.append({"cue": lines[0], "line": line_at(2), "error": "cue结构无效：缺少时间码"})
            continue
        match = TIME_RE.match(lines[1])
        if not match:
            errors.append({"cue": lines[0], "line": line_at(2), "error": "时间码格式无效"})
            continue
        cue_no = int(lines[0])
        start, end = match.group("start"), match.group("end")
        start_ms, end_ms = millis(start), millis(end)
        start_parts = [int(x) for x in re.split(r"[:,]", start)]
        end_parts = [int(x) for x in re.split(r"[:,]", end)]
        if start_parts[1] >= 60 or start_parts[2] >= 60 or end_parts[1] >= 60 or end_parts[2] >= 60:
            errors.append({"cue": cue_no, "line": line_at(2), "error": "时间码分和秒必须小于60"})
        if previous_number is not None:
            if cue_no == previous_number:
                errors.append({"cue": cue_no, "line": line_at(1), "error": "cue编号重复"})
            elif cue_no != previous_number + 1:
                errors.append({"cue": cue_no, "line": line_at(1), "error": "cue编号必须按连续升序排列"})
        if previous_start_ms is not None and start_ms < previous_start_ms:
            errors.append({"cue": cue_no, "line": line_at(2), "error": "cue开始时间早于前一条cue"})
        if end_ms <= start_ms:
            errors.append({"cue": cue_no, "line": line_at(2), "error": "结束时间必须晚于开始时间"})
        if end_ms > total_ms:
            errors.append({"cue": cue_no, "line": line_at(2), "error": "结束时间超过视频实测总时长"})
        body_end = len(lines)
        for index in range(2, len(lines) - 1):
            if lines[index].isdigit() and TIME_RE.match(lines[index + 1]):
                errors.append({"cue": int(lines[index]), "line": line_at(index + 1), "error": "cue结构无效：下一条cue缺少空行分隔"})
                body_end = index
                break
        text = "".join(lines[2:body_end])
        if not text.strip():
            errors.append({"cue": cue_no, "line": line_at(3), "error": "字幕文字为空"})
        cues.append(Cue(cue_no, lines[0], start, end, start_ms, end_ms, text))
        previous_number, previous_start_ms = cue_no, start_ms
    return cues, errors


def units(text: str, forbidden: list[str]) -> list[str]:
    intervals: list[tuple[int, int]] = []
    for term in set(x for x in forbidden if x):
        start = 0
        while (found := text.find(term, start)) >= 0:
            intervals.append((found, found + len(term)))
            start = found + 1
    intervals.sort()
    merged: list[list[int]] = []
    for start, end in intervals:
        if merged and start < merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    out, cursor = [], 0
    for start, end in merged:
        out.extend(text[cursor:start])
        out.append(text[start:end])
        cursor = end
    out.extend(text[cursor:])
    return out


def wrap(text: str, width: int, max_lines: int, forbidden: list[str]) -> tuple[list[str], str | None]:
    pieces = units(text, forbidden)
    phrase_starts = ("提高", "保持", "让", "把", "将", "并", "但", "而", "所以", "因为", "如果", "当", "通过", "使用")
    punctuation = "，。！？；：、"
    lengths = [len(piece) for piece in pieces]
    prefix = [0]
    for length in lengths:
        prefix.append(prefix[-1] + length)

    def break_cost(index: int) -> int:
        if index >= len(pieces):
            return 0
        left = pieces[index - 1]
        right = "".join(pieces[index:index + 4])
        cost = -8 if left and left[-1] in "。！？；：" else -4 if left and left[-1] in "，、" else 0
        if right and right[0] in punctuation:
            cost += 30
        if any(right.startswith(phrase) for phrase in phrase_starts):
            cost -= 60
        return cost

    count = [None] * (len(pieces) + 1)
    score = [None] * (len(pieces) + 1)
    next_cut = [None] * (len(pieces) + 1)
    count[len(pieces)] = 0
    score[len(pieces)] = 0
    for start in range(len(pieces) - 1, -1, -1):
        for end in range(start + 1, len(pieces) + 1):
            line_width = prefix[end] - prefix[start]
            indivisible_overflow = end == start + 1 and lengths[start] > width
            if line_width > width and not indivisible_overflow:
                break
            if count[end] is None:
                continue
            candidate_count = count[end] + 1
            candidate_score = score[end] + (width - line_width) ** 2 + break_cost(end)
            if count[start] is None or (candidate_count, candidate_score) < (count[start], score[start]):
                count[start], score[start], next_cut[start] = candidate_count, candidate_score, end
    lines = []
    position = 0
    while next_cut[position] is not None:
        end = next_cut[position]
        lines.append("".join(pieces[position:end]))
        position = end
    if not lines or position != len(pieces):
        lines = ["".join(pieces)]
    longest = max(map(len, lines), default=0)
    reason = None
    reasons = []
    if len(lines) > max_lines:
        reasons.append(f"需要{len(lines)}行，超过最多{max_lines}行")
    if longest > width:
        reasons.append(f"保留禁拆词后最小不可避免超限：最长行{longest}字，超过每行{width}字")
    reason = "；".join(reasons) or None
    return lines, reason


def process(raw: str, total_seconds: float, width: int, max_lines: int, forbidden: list[str]) -> dict:
    if total_seconds <= 0 or width <= 0 or max_lines <= 0:
        raise ValueError("总时长、每行字数和最多行数必须为正数")
    if total_seconds > 600:
        return {"status": "invalid", "errors": [{"line": 0, "error": "视频实测总时长超过10分钟，请分段检查"}], "over_budget": [], "srt": None}
    cues, errors = parse_srt(raw, round(total_seconds * 1000))
    if len(cues) > 150:
        errors.append({"line": 0, "error": "cue数量超过150条，请分段检查"})
    if errors:
        return {"status": "invalid", "errors": errors, "over_budget": [], "srt": None}
    output, over = [], []
    for cue in cues:
        lines, reason = wrap(cue.text, width, max_lines, forbidden)
        if reason:
            over.append({"cue": cue.number, "lines": len(lines), "longest_line": max(map(len, lines)), "reason": reason})
        output.extend([cue.number_text, f"{cue.start} --> {cue.end}", "\n".join(lines), ""])
    if over:
        return {"status": "over_budget", "errors": [], "over_budget": over, "srt": None}
    return {"status": "ok", "errors": [], "over_budget": [], "srt": "\n".join(output).rstrip() + "\n"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and wrap Chinese SRT without changing words or times.")
    parser.add_argument("srt")
    parser.add_argument("--total-seconds", type=float, required=True)
    parser.add_argument("--line-width", type=int, required=True)
    parser.add_argument("--max-lines", type=int, required=True)
    parser.add_argument("--forbid", default="", help="comma-separated terms that must not split")
    parser.add_argument("--output")
    args = parser.parse_args()
    result = process(Path(args.srt).read_text(encoding="utf-8-sig"), args.total_seconds, args.line_width, args.max_lines, [x.strip() for x in args.forbid.split(",") if x.strip()])
    if args.output and result["status"] == "ok":
        Path(args.output).write_text(result["srt"], encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 2


if __name__ == "__main__":
    sys.exit(main())
