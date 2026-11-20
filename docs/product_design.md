# AICR product design

## Direction and skill audit

UI/UX Pro Max was explicitly invoked for Phase 3. The initial developer query returned
an unrelated FAQ layout; it was rejected. A narrower technical-dashboard query returned
appropriate hierarchy, restrained motion and high-contrast guidance. The existing IBM
Plex Sans / JetBrains Mono pairing fits the code-heavy product better than switching fonts.
The threejs stack guidance informed reactive reduced-motion and demand rendering.

Graphite canvas #101316, sidebar #121619, panel #191e22 and raised panel #20262b establish
depth. Text #e9eef1, secondary #a1adb6; chartreuse #c2ee85 marks selected/verified states.
Critical uses red, High orange, Medium yellow, Low blue; all badges include text.
Spacing follows 4/8/12/16/24/32px, radii 5/8/12px. UI type is 12–32px; hero caps at
54px. Code uses bundled monospace fonts. No external font request or paid design assets.

Shared components include Badge, Score, Loading, ErrorState, EmptyState, SourceViewer,
PatchDialog, CommandPalette, Pipeline, IntelligenceGraph and the application Shell.
Tokens live in `polish.css` and `lib/motion.ts`; existing semantic classes are reused.

## Motion and 3D

Motion for React provides site-wide user reduced-motion policy, route fades, shared
sidebar indicator, findings layout changes/entry, pipeline layout, command dialog
entry/exit and score arrival. Fast/normal/slow timings are 120/220/360ms; press feedback
is a restrained 0.97 scale. Source markers appear once. There is no analysis delay.

The Code Intelligence Graph is a pipeline schematic: repository, file and symbol
nodes route into four specialists and validated results. It is explicitly labeled
illustrative on the landing page and schematic with actual event counters during a
review. It does not claim to show a real call graph the backend has not exported.
Pulses are scoped to the current real stage; skipped AI is shown as disabled in the trace.
The complete source workspace contains no canvas.

React Three Fiber is dynamically imported only on eligible visible desktop views.
DPR is capped at 1.25; eight semantic nodes and eleven edges require no textures,
postprocessing, physics or external assets. Demand rendering, visibility observation,
tab visibility and an explicit Pause button control activity. Mobile/coarse-pointer,
low-core devices and reduced motion get an SVG equivalent. Context loss falls back.

Implementation references: [R3F demand rendering](https://r3f.docs.pmnd.rs/advanced/scaling-performance),
[Motion accessibility](https://motion.dev/docs/react-accessibility).

## Interaction and accessibility

Desktop offers three panels with independent file/findings collapse. Tablet preserves
minimum source widths; <=800px switches to Code / Findings / Files views. Finding
selection maps the actual file and line. Jump to code transfers keyboard focus to the
source region. Search, filter and previous/next controls supplement pointer navigation.

Ctrl/Cmd+K opens a Radix dialog with searchable commands, arrow/Home/End navigation,
Enter activation, Escape dismissal and focus restoration. Patch dialogs use the same
focus-safe primitive. Score explanation is native keyboard-accessible disclosure.
Status/error messages use live semantics; source text is escaped React content.
Reduced motion disables transform/layout effects and replaces 3D with static SVG.
See product_validation.md for automated and manual checks; this is not a WCAG certification.

## Honest scope

No simulated review metrics, fabricated category scores or pretend apply/share buttons.
Category score rows display real penalty totals. Local AI remains optional; disabled
specialists never appear completed. History repositories represent reviewed sources,
not a fictitious connected GitHub App. Full production authentication, true repository
symbol topology and approved patch application are future extensions.
