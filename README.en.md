# SRT Subtitle Line-Break Repair

Make Chinese SRT subtitles easier to read while preserving every original character, cue number, and timestamp. Provide valid SRT, measured video duration, maximum characters per line, maximum lines per cue, and protected terms. The result contains wrapped SRT, reading-budget exceptions, and precise format errors. This skill does not transcribe, translate, dub, or infer new timings.

![SRT subtitle line-break repair](assets/promo-1600x900.png)

## Install

```bash
npx skills add xxjrq/selfmedia-srt-readability-cn
```

## Inputs and outputs

This is for final subtitle display checks: up to 150 cues and a measured duration of up to 10 minutes. Missing duration, line width, or line limit must be requested. Reversed times, malformed timecodes, empty cue text, or cues ending beyond the measured duration are reported by cue and line; timestamps and cue-number spelling are preserved. Overlapping protected terms are merged into one unbreakable span, then dynamic programming searches for a feasible line layout.

Run locally with Python 3 and no external dependency:

```bash
python3 scripts/srt_readability.py fixtures/success/input.txt \
  --total-seconds 10 --line-width 20 --max-lines 2 --forbid 人工智能
python3 scripts/self_test.py
```

See the [successful input](fixtures/success/input.txt), its [copyable SRT delivery](fixtures/success/expected.txt), and the [failure delivery](fixtures/failure/expected.json).
