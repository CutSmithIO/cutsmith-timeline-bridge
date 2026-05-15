# CutSmith Timeline Bridge

**Version**: `v0.1.1-alpha`

**Tested against**:
- CapCut Desktop 167.0.0
- modern_plaintext schema (`schema_version = 360000`)
- Premiere Pro FCP7 XML import

把剪映 / CapCut 专业版的草稿时间线迁移到 **Premiere Pro**（通过 FCP7 XML）。

> **定位**：粗剪时间线搬运工，不是 CapCut 全工程转换器。
> 目标是让你在剪映里"切得差不多"之后，能拿到 PR 里继续精剪。

## Tested against real-world CapCut Desktop projects

v0.1.1 alpha 已在 **CapCut Desktop 167.0.0**（`schema_version=360000`,
modern_plaintext 布局）的三类真实工程上端到端跑通：

| 类型 | 样本 | 形态 |
|---|---|---|
| single-cut | `0509` | 长 take + 154 条字幕,验证长时间线稳定性 |
| multicut | `cutsmith` | V1 七刀 + V2 叠加 + BGM/SFX,0 unsupported |
| stress-test | `cutsmith2` | 多刀 + 叠加 + 字幕 + 贴纸 + 转场 + 滤镜 + 特效 + 变速,15 unsupported 分类清楚 |

三个样本登记在
[`tests/fixtures/real_world/sample_manifest.json`](tests/fixtures/real_world/sample_manifest.json)。

进入 Creator Validation 阶段前请阅:

- [`docs/creator_validation_checklist.md`](docs/creator_validation_checklist.md) — Premiere 实际导入逐项验收清单
- [`docs/supported_features_matrix.md`](docs/supported_features_matrix.md) — fully / partially / ignored / unsupported 四级矩阵
- [`docs/known_limitations.md`](docs/known_limitations.md) — 已知边界和注意事项

## v0.1 范围

支持：

1. 视频片段切点（in/out + 时间线位置）
2. 独立音频轨道（BGM、配音，以及 CapCut 自动从视频里拆出的原音轨——只要它在 draft 里以独立 audio track 存在，就会被原样搬运）
3. 多轨顺序与叠加（V1/V2/A1/A2…）
4. 素材路径解析 + 离线占位（Premiere "Link Media" 友好）
5. `compatibility_report.md` 自动列出"已迁移 / 已丢弃 / 需手工补"

**不支持**（被识别为不支持的项会写进报告，**不会**被静默丢弃）：

- FCPXML 输出（v0.2）
- 关键帧动画（位置/缩放/旋转/不透明度的曲线）
- 变速曲线（speed ramp）
- 转场、滤镜、特效、贴纸、花字
- 字幕（剪映自身导 SRT，再导 PR 的 Captions）

## 安装

只用标准库。Python ≥ 3.10。

```bash
git clone <repo>
cd cutsmith
# 暂时不需要 pip install，直接跑 demo
```

## 用法

CLI 有两个子命令：`inspect`（侦察）和 `convert`（转换）。

### inspect — 真实草稿先来一遍

任何陌生的真实草稿都**先跑 inspect**。这一步不产 XML，只产五份 schema 摘要，告诉你 reader 假设和真实 schema 之间差了多少：

```bash
python -m cutsmith inspect path/to/draft_content.json -o ./out
```

输出：

```
out/
├── schema_summary.json       ← 版本号、fps、duration、canvas、各类材料计数
├── media_summary.json        ← materials.videos/audios 字段普查 + 资源预览
├── track_summary.json        ← 按轨道类型分组的 segment 字段普查
├── unsupported_summary.json  ← reader 当前会丢弃的项的计数
├── unknown_fields.json       ← ⚠ 草稿里有、但 reader 没读的字段（最重要）
└── debug_inspect.json        ← 以上五份合并版，方便贴报告
```

CLI 总览会立刻告诉你最关键的一个数字：**"⚠ N 个字段 reader 没读"**。N 越大表示这个版本的剪映 schema 漂移越严重，reader 需要补的越多。

**隐私**：默认 `path` 字段会打码成 basename（防止泄露 `/Users/真名/项目名/`）。要原样保留加 `--raw-paths`。

### convert — 真正出 XML

```bash
python -m cutsmith convert path/to/draft_content.json \
  -o ./out \
  -s /Volumes/Footage \
  -s ~/Movies/RawFootage \
  -n my_sequence
```

也支持老的省略 `convert` 的写法：

```bash
python -m cutsmith path/to/draft_content.json -o ./out
```

- `-s / --search-root` 可以重复，按 basename 在这些目录里找缺失素材
- `-n / --name` 自定义序列名（默认用 draft 文件 stem）

输出：

```
out/
├── my_sequence.xml          ← 拖进 Premiere: File > Import
└── my_sequence.report.md    ← 务必读一遍
```

## 真实草稿验证流程（推荐顺序）

第一次拿到一个真实剪映工程时按这个顺序走：

1. **inspect 一下，先看 schema 漂移**
   ```bash
   python -m cutsmith inspect ~/Movies/JianyingPro/User\ Data/Projects/com.lveditor.draft/<项目>/draft_content.json -o ./inspect_out
   ```
2. **打开 `inspect_out/unknown_fields.json`**。如果列表是空的，reader schema 假设 OK，跳到 4。
3. **如果有未知字段**，根据字段位置（`top_level` / `canvas_config` / `video_materials` / ...）去 `cutsmith/reader/jianying_pro.py` 里加对应的解析，并在 `cutsmith/inspect/schema.py` 里把字段名加进 `KNOWN_*_FIELDS`（这样它们就不会再显示为未知）。
4. **convert 出 XML，带上 search root**：
   ```bash
   python -m cutsmith convert <同样的 draft.json> -o ./out \
     -s ~/Movies/JianyingPro/User\ Data/Projects/com.lveditor.draft/<项目>/Resources \
     -s /Volumes/外部素材
   ```
5. **在 Premiere 里 File → Import 选 `.xml`**。检查：
   - 序列的帧率、分辨率对吗
   - V1 视频片段的切点对吗（建议在剪映里同时打开，肉眼对照前 5 个 cut）
   - 视频原音是不是在自己的 A 轨上、与画面同步
   - BGM 在不在自己的 A 轨、音量水平大致正确
6. **打开 `report.md`**，看哪些已识别但丢弃的东西需要手工补回

### Python API

```python
from cutsmith import bridge

result = bridge.run(
    draft="path/to/draft_content.json",
    out_dir="./out",
    search_roots=["/Volumes/Footage"],
)

print(result.xml_path, result.report_path)
print(f"{result.resolution.unresolved} clips offline")
```

### 在 Premiere 里打开

1. `File → Import`，选 `.xml`（**不是** `Open Project`）
2. PR 会在项目面板生成一个 Sequence，文件未链接的会显示为 Offline
3. 右键任意 Offline 片段 → **Link Media** → 选一个匹配文件 → PR 会按同名规则自动把同目录其他离线片段也连上
4. **打开 `.report.md`**，按里面的提示手工补回被丢弃的关键帧/变速/字幕

## 跑 Demo

```bash
python examples/demo.py
```

会用 `tests/fixtures/mock_draft_content.json` 跑一遍流水线，产物在
`examples/out/` 下。Mock 草稿里的素材路径是虚构的，所有片段都会以离线状态导出——
这正是测试"离线占位 + 报告"路径的最佳场景。

## 跑测试

```bash
python -m unittest tests.test_pipeline
```

## 项目结构

```
cutsmith/
├── ir/              ← 典范时间线模型（reader 和 writer 的契约）
├── reader/          ← 剪映 draft_content.json → IR
├── inspect/         ← schema 侦察工具（独立于 reader，能在奇怪草稿上不崩）
├── resolver/        ← 素材路径解析（绝对路径 / search root / OFFLINE）
├── writer/          ← IR → FCP7 XML
├── report/          ← compatibility_report.md 生成
├── bridge.py        ← 流水线编排
└── __main__.py      ← CLI（inspect / convert 两个子命令）
```

每一层都独立可测，加 FCPXML writer / Resolve writer 不需要碰 reader。

**inspect 和 reader 的关系**：inspect 不调用 reader，它独立解析 JSON。这样 reader 出 bug 时 inspect 仍然能跑，且 inspect 能看到 reader 选择忽略的字段（这正是 inspect 的意义）。两者共享一份"已知字段表"（`cutsmith/inspect/schema.py` 里的 `KNOWN_*_FIELDS`），扩展 reader 时记得同步更新这份表。

## 已知坑（路过留意）

- **NTSC 帧率**：CapCut 把 29.97 有时候存成 `29.97`，有时候存成 `29.97002997`。我们用 0.05 的容差判 NTSC，应该够用。如果你的 60p NTSC 序列翻车了告诉我。
- **Windows 路径在 macOS 打开**：reader 会把 `C:\...` 路径的盘符部分丢掉，只用 basename 在 `--search-root` 里找。这意味着跨平台搬运基本一定要带 `-s`。
- **CapCut 的 speed != 1.0**：v0.1 一律按 1.0× 导出，但会按目标时长在时间线上占位（即"切点对得上，但播放速度错了"）。报告里会列出来。

## v0.2 路线

按优先级：FCPXML 输出 → 关键帧 → 变速 → DaVinci Resolve 适配。
