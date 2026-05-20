CutSmith Timeline Bridge — Product Messaging / Legal Boundary / UI Copy General Rules

Please audit and adjust all project wording across:
- README.md
- README.zh-CN.md
- CHANGELOG.md
- docs/
- GUI copy
- package_summary.txt
- relink_guide.md
- compatibility reports
- website / landing page copy
- release notes
- Reddit / social copy templates if any

Core positioning:

CutSmith Timeline Bridge is an interoperability and workflow portability tool.

It helps users move their own rough-cut timeline structure and user-owned media from CapCut Desktop / Jianying projects into professional post-production workflows such as Premiere Pro.

It is NOT:
- a CapCut unlock tool
- a Pro bypass tool
- an asset extraction tool
- a downloader
- a DRM bypass tool
- a CapCut clone
- a rendering engine
- a replacement for CapCut effects

Preferred product narrative:

“Take your timeline with you.”

“CutSmith moves your rough-cut structure. You bring the grade.”

“CapCut rough cut → professional finishing workflow.”

“Portable handoff packages for editors.”

“Project interoperability for post-production workflows.”

━━━━━━━━━━━━━━━━━━
1. Safe wording to use
━━━━━━━━━━━━━━━━━━

Use these terms:

- interoperability
- workflow portability
- project handoff
- rough-cut migration
- timeline reconstruction
- user-owned media
- portable package
- media relink
- source items
- project readiness
- migration report
- finishing workflow
- archive / handoff
- compatibility report
- professional post-production workflow

Examples:

“Move your CapCut Desktop rough cut into Premiere Pro for finishing.”

“Create a portable package containing your timeline structure, user-owned media, reports, and relink guide.”

“CutSmith reconstructs the edit structure; it does not recreate CapCut’s proprietary effects.”

“Platform assets are detected and reported, but not copied by default.”

━━━━━━━━━━━━━━━━━━
2. Words / phrases to avoid
━━━━━━━━━━━━━━━━━━

Avoid these words unless explicitly discussing what CutSmith does NOT do:

- unlock
- bypass
- crack
- rip
- extract Pro assets
- export paid assets
- remove restrictions
- free CapCut Pro
- download CapCut assets
- recover locked assets
- defeat encryption
- workaround subscription
- get paid assets for free
- convert CapCut Pro assets
- steal / scrape / dump assets
- hidden cache extraction

Do NOT market the tool as:
- “CapCut Pro exporter”
- “CapCut asset extractor”
- “CapCut music/SFX extractor”
- “CapCut paid feature unlocker”
- “bypass CapCut export limits”

━━━━━━━━━━━━━━━━━━
3. CapCut / Jianying naming rule
━━━━━━━━━━━━━━━━━━

It is okay to mention CapCut / Jianying as supported source applications.

Use:
- “CapCut Desktop project interoperability”
- “CapCut Desktop → Premiere Pro handoff”
- “Supports plaintext CapCut Desktop drafts”
- “Jianying plaintext drafts are detected where supported”

Do NOT use CapCut or Jianying logos as primary branding.

Add disclaimer wherever appropriate:

“CapCut and Jianying are trademarks of their respective owners. CutSmith is an independent interoperability tool and is not affiliated with, endorsed by, or sponsored by ByteDance, CapCut, or Jianying.”

━━━━━━━━━━━━━━━━━━
4. Asset handling policy wording
━━━━━━━━━━━━━━━━━━

Default policy:

CutSmith copies user-owned media by default.

Default included:
- user video
- user audio
- user images
- embedded audio references that reuse user video files
- subtitle sidecars
- XML / reports / manifest / relink guide

Default excluded:
- CapCut / TikTok music library assets
- CapCut SFX library assets
- stickers
- effects
- transitions
- filters
- fonts
- app runtime assets
- encrypted or protected resources

Correct wording:

“CapCut library music/SFX detected — not copied by default.”

“Replace with licensed audio in Premiere if needed.”

“Cached platform assets, if explicitly included, are copied as-is. CutSmith does not modify, transcode, decrypt, or repair platform assets.”

“Compatibility with external NLEs is not guaranteed for platform assets.”

Do NOT say:
- “fixed CapCut music”
- “repaired CapCut MP3”
- “converted CapCut SFX”
- “made CapCut music importable”
- “unlocked cached audio”

━━━━━━━━━━━━━━━━━━
5. Extension normalization policy wording
━━━━━━━━━━━━━━━━━━

For user-owned media:

Allowed wording:
“CutSmith normalizes incorrect file extensions for user-owned media when the file signature clearly identifies the format.”

For platform assets:

Required wording:
“Platform assets are not normalized, transcoded, decrypted, or repaired.”

If an optional advanced setting exists:

Label:
“Include cached platform audio assets”

Subtext:
“Copied as-is from local cache. External compatibility and usage rights are not guaranteed. Only enable if you have rights to use these assets outside CapCut/TikTok.”

Default:
OFF.

Do not remember this as a permanent default.

━━━━━━━━━━━━━━━━━━
6. Encrypted draft stance
━━━━━━━━━━━━━━━━━━

Always state clearly:

- encrypted drafts are detected
- encrypted drafts are refused gracefully
- CutSmith does not attempt decryption
- CutSmith does not bypass DRM or app protection

Preferred wording:

“Encrypted drafts are detected and refused. CutSmith does not decrypt or bypass protected project formats.”

━━━━━━━━━━━━━━━━━━
7. Effects / stickers / transitions wording
━━━━━━━━━━━━━━━━━━

Do not imply full visual parity.

Use:

“CapCut effects, transitions, stickers, filters, and template animations are proprietary rendering features and are report-only.”

“Rebuild these manually in Premiere using native effects or third-party assets.”

“CutSmith prioritizes timeline structure, media handoff, and project portability, not CapCut effect recreation.”

Avoid:

“recover effects”
“extract effects”
“convert all stickers”
“full CapCut visual clone”
“100% project recreation”

━━━━━━━━━━━━━━━━━━
8. Speed wording
━━━━━━━━━━━━━━━━━━

For constant speed:

“Constant speed changes are reconstructed with Premiere-native timeremap where supported.”

For speed curves:

“Variable speed ramps / speed curves are detected and reported, but not reconstructed yet.”

Avoid:

“all speed effects supported”

Also mention:

“Speed clips may show a blank trim area if extended beyond available source frames. This is a source-boundary behavior.”

━━━━━━━━━━━━━━━━━━
9. Subtitle wording
━━━━━━━━━━━━━━━━━━

Safe:

“Extract subtitle timing and text from supported plaintext drafts.”

“Export SRT sidecar files for use in Premiere or other NLEs.”

Avoid:

“bypass paid caption export”

Do not frame subtitle extraction as defeating CapCut subscription limits.

Frame it as:
“project interoperability” and “user-owned timeline text export.”

━━━━━━━━━━━━━━━━━━
10. GUI copy principles
━━━━━━━━━━━━━━━━━━

The GUI should feel like:

“Project Handoff Assistant”

Not:
“CapCut extractor”

Preferred panel names:
- Project Discovery
- Project Readiness
- Export Decision
- Migration Report
- Portable Package
- Relink Guide

Preferred button:
“Collect Premiere Package”

Acceptable:
“Export XML”
“Export SRT”
“Open Package”
“Reveal XML”

Avoid:
“Extract Assets”
“Export CapCut Assets”
“Unlock Music”
“Dump Cache”

Readiness states:
- Portable Package Ready
- Ready with Notes
- Partial Support
- Encrypted / Unsupported
- Project Could Not Be Read

━━━━━━━━━━━━━━━━━━
11. Website / landing page positioning
━━━━━━━━━━━━━━━━━━

Homepage headline direction:

“Take your timeline with you.”

Subheadline:

“CutSmith Timeline Bridge helps editors move CapCut Desktop rough cuts into professional post-production workflows with portable Premiere packages, user-owned media collection, subtitles, reports, and relink guides.”

CTA:
“Try the alpha”
“View on GitHub”
“Join creator beta”

Do NOT lead with:
“Extract CapCut assets”
“Bypass CapCut Pro”
“Export paid CapCut music”
“Unlock CapCut timelines”

━━━━━━━━━━━━━━━━━━
12. Open-source / commercial positioning
━━━━━━━━━━━━━━━━━━

Core can be described as:
“open interoperability core”

Future paid/pro features should be described as:
- GUI workflow
- batch project processing
- archive validation
- studio handoff
- project diagnostics
- timeline QA
- advanced reporting

Do NOT describe paid features as:
- unlocking platform content
- bypassing subscription restrictions
- premium asset extraction

━━━━━━━━━━━━━━━━━━
13. Standard legal / interoperability notice
━━━━━━━━━━━━━━━━━━

Add this or a close version to README / website / GUI About:

“CutSmith Timeline Bridge is an independent interoperability tool for migrating your own editing projects and user-owned media between post-production workflows. It does not modify CapCut or Jianying, bypass encryption, decrypt protected drafts, download platform assets, or unlock paid features. CapCut, Jianying, and related trademarks are the property of their respective owners. Users are responsible for complying with the license terms of any third-party media, music, sound effects, fonts, stickers, or templates used in their projects.”

━━━━━━━━━━━━━━━━━━
14. Final rule
━━━━━━━━━━━━━━━━━━

Every user-facing sentence should reinforce this boundary:

CutSmith helps users migrate their own edit structure and user-owned media.

CutSmith does not help users bypass platform licensing, extract protected assets, or clone CapCut’s proprietary rendering system.