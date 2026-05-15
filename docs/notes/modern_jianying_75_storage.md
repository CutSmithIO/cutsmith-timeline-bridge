# 现代版剪映(75.0.0)草稿存储格式调查

> **状态**:调查笔记,非路线图承诺。日期 2026-05-16。
> **样本**:一份在 macOS 上用现代版 PC 剪映创建的工程,版本 `new_version: 75.0.0` / `version: 360000`。
> **样本位置**:`~/Movies/JianyingPro/User Data/Projects/com.lveditor.draft/test1/`

## TL;DR

新版剪映把时间线**搬位置 + 加密**了。本笔记记录观察到的事实,**不**记录任何解密尝试。

CutSmith v0.1 **不**处理这种现代版加密草稿;v0.1 仅针对仍然产出明文 `draft_content.json` 的旧版本(legacy desktop / CapCut Desktop / Mobile)。

## 1. `draft_info.json` 内容是 base64-like 加密/混淆字符串

旧版的 `draft_content.json` 是明文 UTF-8 JSON。新版改为:

- 路径:`<项目>/Timelines/<UUID>/draft_info.json`
- 大小:本样本 7828 字节(以及同样大小的 `.bak` 副本和 `template-2.tmp` 副本——三者完全一致)
- 内容:连续单行 ASCII,字符集为 `[A-Za-z0-9+/]`,无换行,首字节即非 `{`

样本前 64 字节:

```
73aDdRX42BhDfNBAfEyp5Jb0DFBBNPca89f7iASy83aD5u3Jf8GLB/B4NjW8jF26
```

`file(1)` 报告 "ASCII text, with very long lines (7828), with no line terminators"。`json.load()` 直接抛 `JSONDecodeError: Extra data: line 1 column 3`。

**只能确认**:不是直接可读的 JSON,字符集与 base64 兼容。
**未做也不打算做**:解码、密钥发现、逆向。

## 2. `Timelines/project.json` 是 manifest

工程根 `<项目>/Timelines/project.json` 是个明文的多时间线索引:

```json
{
  "main_timeline_id": "A23E1E13-872B-42B7-9C3C-3654AB301449",
  "timelines": [{"id": "A23E1E13-...", "name": "时间线00", ...}],
  "version": 0
}
```

`main_timeline_id` 指向 `Timelines/<那个 UUID>/` 子目录——加密的 `draft_info.json` 就在里面。说明现代版支持**单工程多时间线**,这是相对旧版 schema 的结构性变化。

## 3. `template.tmp` 是空白模板,不是用户时间线

同目录里有一份明文 JSON `template.tmp`(本样本 3866 字节)。乍看像 timeline 的明文备份,**实际是新建工程的空骨架**:

- `tracks: []`
- 所有 `materials.<类别>: []`(全部 53 个类别均为空数组)
- `duration: 0`,`canvas_config.width/height: 0`
- `name: ""`,`path: ""`

跑 `cutsmith inspect` 也确认 `materials: (none)`, `tracks: (none)`, `duration=0.00s`。

**结论**:`template.tmp` 不能代替 `draft_content.json` 拿来 convert,它没有用户编辑过的内容。

(顺带:用 `template.tmp` 跑 inspect 暴露了 **29 个 reader 没读的 top-level 字段**,包括 `keyframes`, `keyframe_graph_list`, `mutable_config`, `time_marks`, `relationships`, `group_container`, `platform`, `last_modified_platform`, `color_space`, `config` 等。即使将来解决了加密,reader 也仍要处理 schema 漂移——见 `out_inspect/test1/unknown_fields.json`。)

## 4. CutSmith v0.1 不处理加密草稿

reader/inspect 的入口都假设 `json.load()` 能直接打开。当前代码碰到加密的 `draft_info.json` 会在第一行 `json.load(f)` 抛 `JSONDecodeError`,这就是预期行为——v0.1 **不**尝试自动检测、解码、绕过。

不打算给 v0.1 加任何"如果看起来像 base64 就 try ... " 的兜底。这种探测会让支持范围模糊,也会鼓励掉进解密黑洞。

## 5. v0.1 支持范围正式收敛到 legacy / plaintext drafts

明文产出已知出现在:

- 老版本 PC 剪映(把 timeline 挪进 `Timelines/<UUID>/` 加密之前)
- CapCut Desktop(海外版,macOS/Windows):`~/Movies/CapCut/User Data/Projects/com.lveditor.draft/<项目>/draft_content.json`
- CapCut Mobile(iOS/Android,工程目录里通常有明文 `draft_content.json`)

v0.1 文档化的工作流(README "真实草稿验证流程")完全适用于以上来源。本调查不改 reader 或 inspect 的代码,只调整文字定位。

需要 README 跟进的措辞(后续 PR 处理):

- 明确说明"v0.1 支持 plaintext `draft_content.json`,不支持 modern 剪映 PC ≥ 75.0.0 的加密 `draft_info.json`"
- 在"已知坑"里加一条"现代剪映加密格式"

## 6. 现代版加密格式作为独立 research track,不纳入 v0.1/v0.2

理由:

- **合规/ToS 风险**:解密第三方应用的数据存储格式有灰色地带,且字节社可以随版本更换密钥使任何方案失效。
- **黑洞工作量**:密钥位置不明、可能依赖 device-binding、可能有完整性校验。投入和收益不匹配。
- **不挡 v0.1 目标**:核心价值是"明文 timeline → FCP7 XML 搬运",这个价值在 legacy/CapCut/Mobile 样本上已经能完整证明。

未来若要支持现代加密格式:

- 必须用合规可分享样本(用户自己导出、自愿提供)
- 走独立分支或独立工具,不污染主 reader
- 至少要有一份字节社官方/半官方的格式说明,否则不动手

在那之前,这条路径**显式搁置**。

## 附:本次诊断使用的命令

```bash
# 1. 文件类型与首字节
file <path>/draft_info.json
xxd <path>/draft_info.json | head

# 2. inspect(在明文文件上才有意义,加密文件会直接抛 JSONDecodeError)
python3 -m cutsmith inspect <path>/template.tmp -o ./out_inspect/<name>

# 3. 检查同目录有没有明文 JSON 兄弟文件
for f in *.json *.tmp; do head -c 1 "$f"; echo "  $f"; done
```
