# SRT 字幕断行修整

这是一个用于成片前校对的中文字幕 SRT 断行工具：输入已有 SRT、视频实测总时长、每行字数、最多行数和禁拆词表，得到保留原句、编号和时间码的易读断行 SRT，以及超限条目和格式错误定位。

使用时安装 Skill 后直接提供上述限制和 SRT 内容；若缺少总时长或行数限制，它会请求补充，而不会猜测时间或修改原句。

把已有中文字幕修成观众更容易读的断行，同时守住原句、编号与时间码。输入有效 SRT、视频**实测**总时长、每行字数、最多行数和禁拆词表；结果是可直接替换的断行 SRT、阅读预算超限条目和格式错误定位。它不转录、翻译、配音，也不会臆测或重排时间。

![SRT字幕断行修整推广图](assets/promo-1600x900.png)

## 安装

```bash
npx skills add xxjrq/selfmedia-srt-readability-cn
```

## 适用边界

适合成片前的中文 SRT 展示校对：最多 150 条 cue、视频总时长最多 10 分钟。超过范围请分段检查。缺少总时长、每行字数或最多行数时，Skill 会先请求补充；时间逆序、结束超总时长或时间码结构错误会指出 cue 与行号，绝不假装已修复。

## 输入与结果

输入示例：视频总时长 10 秒、每行最多 20 字、每条最多 2 行、禁拆词为“人工智能”，加上一份 SRT。

```text
1
00:00:00,000 --> 00:00:04,000
今天我们用人工智能工具整理字幕断行提高观看舒适度
```

输出会保持时间和文字不变，仅变为更易读的行：

```text
1
00:00:00,000 --> 00:00:04,000
今天我们用人工智能工具整理字幕断行
提高观看舒适度
```

如禁拆词本身超过行宽，或文字需要超过允许行数，结果会列出 cue 编号、实际行数、最长行和超限原因；此时不交付 SRT，命令以非零状态退出，也不会写入或覆盖 `--output`。

## 本地工具与样例

无第三方依赖，Python 3 即可运行：

```bash
python3 scripts/srt_readability.py fixtures/success/input.srt \
  --total-seconds 10 --line-width 20 --max-lines 2 --forbid 人工智能
python3 scripts/self_test.py
```

- [成功样例输入](fixtures/success/input.srt) 与 [可复制交付 SRT](fixtures/success/expected.srt)
- [失败样例输入](fixtures/failure/input.srt) 与 [预期错误交付](fixtures/failure/expected.json)

来源与许可证核对见 [SOURCES.md](SOURCES.md)。英文说明见 [README.en.md](README.en.md)。
