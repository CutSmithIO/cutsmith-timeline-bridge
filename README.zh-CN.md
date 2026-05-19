[English README →](README.md)

# CutSmith Timeline Bridge

**Version**: `v0.3.5`

**Tested against**:
- CapCut Desktop 167.0.0
- modern_plaintext schema (`schema_version = 360000`)
- Premiere Pro FCP7 XML import

把剪映 / CapCut 专业版的草稿时间线迁移到 **Premiere Pro**（通过 FCP7 XML），并将用户素材打包收集到可交付的 Portable Package。

> **定位**：粗剪时间线搬运工 + 素材打包工具，不是 CapCut 全工程转换器。
> 目标是让你在剪映里"切得差不多"之后，能拿到 PR 里继续精剪，或者把整个包交给协作剪辑师继续工作。

## Tested against real-world CapCut Desktop projects

v0.3-alpha 已在 **CapCut Desktop 167.0.0**（`schema_version=360000`,
modern_plaintext 布局）的多类真实工程上端到端跑通：

| 类型 | 样本 | 形态 |
|---|---|---|
| single-cut | `0509` | 长 take + 154 条字幕，验证长时间线稳定性 |
| multicut | `cutsmith` | V1 七刀 + V2 叠加 + BGM/SFX，0 unsupported |
| stress-test | `cutsmith2` | 多刀 + 叠加 + 字幕 + 贴纸 + 转场 + 滤镜 + 特效 + 变速，15 unsupported 分类清楚 |
| 竖屏全压力 | `0519V` | 1080×1920，7 视频轨，0.5× + 2.0× 变速片段，speed_curve，贴纸，转场，特效，滤镜，8 条字幕（Pattern B），Premiere 实测导入通过 |
| 竖屏多变速 | `0519V2` | 1080×1920，30fps NDF，2.0×/0.5×/0.5× 变速片段，33 条自动字幕，10 个贴纸，collect dedup 修复验证 |

collect 已验证：`0509` / `cutsmith` / `0519V` / `0519V2`。

样本登记在
[`tests/fixtures/real_world/sample_manifest.json`](tests/fixtures/real_world/sample_manifest.json)。

进入 Creator Validation 阶段前请阅:

- [`docs/creator_validation_checklist.md`](docs/creator_validation_checklist.md) — Premiere 实际导入逐项验收清单
- [`docs/supported_features_matrix.md`](docs/supported_features_matrix.md) — fully / partially / ignored / unsupported 四级矩阵
- [`docs/known_limitations.md`](docs/known_limitations.md) — 已知边界和注意事项

## v0.3.3 支持范围

**已完整支持：**

1. 视频片段切点（in/out + 时间线位置）
2. 独立音频轨道（BGM、配音，以及 CapCut 自动从视频里拆出的原音轨）
3. 多轨顺序与叠加（V1/V2/A1/A2…）
4. 素材路径解析 + 离线占位（Premiere "Link Media" 友好）
5. **Premiere Project 面板素材条目** — 每个素材生成 `<clip id="masterclip-…">` root clip，Project Browser 有完整 source items；支持"选父目录 relink"
6. **常量变速重建** — FCP7 `timeremap` filter，Premiere 导入后直接显示 200%、49.91% 等正确速度，Effect Controls 即可确认
7. `compatibility_report.md` 自动列出"已迁移 / 已丢弃 / 需手工补"
8. `collect` 打包：所有用户素材复制到 `media/`，XML 路径重写，Premiere 免 `Link Media` 直接打开

**仍不支持（报告可见，不静默丢弃）：**

- 关键帧动画（位置/缩放/旋转/不透明度）
- 变速曲线（speed ramp / speed_curve — 播放时为 1.0×，Premiere 中用 Time Remapping 手工补）
- 转场、滤镜、特效、贴纸
- 字幕（剪映自身导 SRT，再导 PR 的 Captions）
- FCPXML 输出（Final Cut Pro X / 11）

## 安装

只用标准库。Python ≥ 3.10。

```bash
git clone <repo>
cd cutsmith
# 暂时不需要 pip install，直接跑 demo
```

## 用法

CLI 子命令：`detect`（侦测）、`inspect`（侦察）、`convert`（转换）、`scan-assets`（素材扫描）、`export-srt`（字幕导出）、`collect`（打包）。

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
- **变速片段（speed ≠ 1.0）**：时间线 slot 按 CapCut 的 target duration 占位（下游片段不漂移），源素材 in/out 保留。**Premiere 实测确认（2026-05-19）：导入后片段显示 100% 速度，Premiere 不会自动解析 FCP7 XML 的隐式速度编码。** 需手工右键 → Speed/Duration 按报告里的速度值修改。变速曲线（speed_curve）仅报告、不导出，片段按 1.0× 播放。

## v0.2 / v0.3 已完成 / 后续路线

- **v0.2 ✅**：素材扫描（`scan-assets`）、字幕提取（`export-srt`）、Pattern A + B 字幕支持、108 单元测试通过
- **v0.3 ✅**：`collect` — 把用户素材收集到 `media/` 子目录，XML `<pathurl>` 重写指向收集后的文件，同步产出 manifest + offline.md。已在 `0509` / `cutsmith` / `0519V` 验证通过。
- **v0.3.5 ✅**：`collect` UX 增强 — `<name>.package_summary.txt`（一目了然的打包摘要）；rich CLI 输出（绝对路径、所有产出文件、dedup/ext-norm 统计）；`-o` 现在是可选的（默认 `out_collect/<project_name>/`）；`--open` 完成后自动打开 Finder（macOS）。

### v0.3 collect CLI

```bash
# -o 可省略，默认输出到 out_collect/<project_name>/
python3 -m cutsmith collect "/path/to/CapCut/project" \
  [-o ./collected] \
  [-s "/path/to/extra/footage"] \
  [--open]   # macOS：完成后自动在 Finder 打开输出目录
```

**重要区分**：`collect` 是 CutSmith 把素材 **物理复制** 到 `media/`，
XML `<pathurl>` 指向复制后的绝对路径。
Premiere 导入 XML 时读取这些路径生成 Project panel source items，
Premiere 本身不复制素材。
整个输出目录可以移动到另一台机器后通过 `relink_guide.md` 里的路径重连。

输出结构：

```
out_collect/<project_name>/
├── <name>.xml                 ← pathurl 已重写到 media/
├── <name>.report.md           ← 兼容性报告 + 打包摘要
├── <name>.manifest.json       ← collected_root, relink_root_hint 等
├── <name>.package_summary.txt ← 人类可读的一目了然摘要
├── <name>.relink_guide.md     ← Premiere 导入 + relink 指引
├── <name>.offline.md          ← 仅在有未解析素材时生成
└── media/
    ├── video/
    ├── audio/
    ├── images/
    ├── music/                ← 剪映音乐库（注意版权）
    ├── sfx/
    └── stickers/
```

**CapCut 专有资产**（特效、转场、滤镜、贴纸）**无法移植**——它们只写入 report 和 offline.md，不可脱离 CapCut 提取。在 Premiere 里用原生等效效果重建。

- **Research track**：Premiere native 变速重建（显式 Time Remap filter 节点）。FCP7 隐式编码已确认不被 Premiere 自动识别。
- **后续**：FCPXML 输出、DaVinci Resolve XML、关键帧动画、CapCut Mobile 样本覆盖
