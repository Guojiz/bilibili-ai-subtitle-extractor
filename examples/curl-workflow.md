# 可复制的 curl 流程

这个文件给能执行命令的 Agent 或人类用户使用。把示例中的 BV 号替换成目标视频即可。

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

优先寻找 `lan` 为 `ai-zh` 的条目。

## 3. 下载字幕 JSON

取出 `subtitle_url`。

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
- 修正明显错字
- 保留关键数据和专有名词

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
3. 字幕正文
4. 字幕来源说明
5. 如果字幕不完整，说明限制