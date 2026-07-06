# 可复制的 curl 流程

这个文件给能执行命令的 Agent 或人类用户使用。把示例中的 BV 号替换成目标视频即可。

## 0. 先确定目标语言

读取字幕前，先明确用户要哪种语言：中文、英文、双语，还是原语言。

字幕选择顺序：

1. 目标语言的人工字幕 / UP 主字幕。
2. 目标语言的 B站 AI 字幕，例如 `ai-zh`。
3. 如果没有目标语言字幕，但有原语言字幕，并且用户明确需要翻译，再读取原语言字幕后翻译。

不要看到 `ai-zh` 就直接使用。很多转载视频、翻译视频或用心制作的视频，可能已经有更好的人工字幕或翻译字幕。

## 1. 获取视频信息

```bash
BV_ID="BV1SA7B6iEJg"

curl -s "https://api.bilibili.com/x/web-interface/view?bvid=${BV_ID}" \
  -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' \
  -o video-info.json
```

从 `video-info.json` 里读取：

```text
data.cid
data.title
data.desc
data.duration
data.pages
```

如果安装了 `jq`，可以这样查看：

```bash
cat video-info.json | jq '.data | {aid, cid, title, desc, duration, pages}'
```

## 2. 获取字幕列表

把上一步得到的 CID 填进去：

```bash
CID="PUT_CID_HERE"

curl -s "https://api.bilibili.com/x/v2/dm/view?oid=${CID}&type=1" \
  -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' \
  -H 'Referer: https://www.bilibili.com/' \
  -o dm-view.json
```

查看字幕条目：

```bash
cat dm-view.json | jq '.data.subtitle.subtitles'
```

每个字幕条目一般需要关注：

```text
lan
lan_doc
subtitle_url
```

选择目标语言时，优先选择非 AI 的人工字幕 / UP 主字幕；没有人工字幕时，再选择目标语言的 AI 字幕。

## 3. 下载字幕 JSON

取出选中字幕的 `subtitle_url`。

如果 URL 以 `//` 开头，补成 `https://`。

```bash
SUBTITLE_URL="PUT_SUBTITLE_URL_HERE"

curl -s "${SUBTITLE_URL}" \
  -H 'Referer: https://www.bilibili.com/' \
  -o subtitle.json
```

查看字幕正文：

```bash
cat subtitle.json | jq -r '.body[].content'
```

## 4. 合并为粗略文本

如果只是快速查看，可以先这样合并：

```bash
cat subtitle.json | jq -r '.body[].content' > subtitle-raw.txt
```

但正式给用户时，不建议直接输出 `subtitle-raw.txt`。

应该继续整理：

- 合并短句
- 补标点
- 每 200 到 300 字分段
- 结合视频简介中的章节
- 修正明显错字；人工字幕不要过度改写
- 保留关键数据和专有名词
- 标明目标语言和字幕来源

## 5. 最小 Python 整理脚本

```python
import json
from pathlib import Path

with open("subtitle.json", "r", encoding="utf-8") as f:
    data = json.load(f)

items = data.get("body", [])
paragraphs = []
current = []
last_to = None
char_count = 0

for item in items:
    text = (item.get("content") or "").strip()
    if not text:
        continue

    start = float(item.get("from", 0))
    end = float(item.get("to", start))
    gap = start - last_to if last_to is not None else 0

    if current and (gap > 1.5 or char_count >= 260):
        paragraphs.append("".join(current).strip())
        current = []
        char_count = 0

    current.append(text)
    char_count += len(text)
    last_to = end

if current:
    paragraphs.append("".join(current).strip())

# 简单补句号，复杂润色应由 Agent 根据语义处理
cleaned = []
for p in paragraphs:
    if p and p[-1] not in "。！？!?":
        p += "。"
    cleaned.append(p)

Path("subtitle-cleaned.txt").write_text("\n\n".join(cleaned), encoding="utf-8")
print("Saved to subtitle-cleaned.txt")
```

## 6. PowerShell 提醒

Windows PowerShell 也能执行 curl，但有些环境里 `curl` 可能是别名。必要时使用：

```powershell
curl.exe -s "https://api.bilibili.com/x/web-interface/view?bvid=BV1SA7B6iEJg" `
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" `
  -o video-info.json
```

## 输出建议

给用户的最终结果不要只是文件路径，应至少包含：

1. 视频标题
2. 简介或章节
3. 目标语言
4. 字幕来源说明：人工字幕 / UP 主字幕 / Bilibili AI 字幕
5. 字幕正文
6. 如果字幕不完整，说明限制