# Danko TV — Roadmap

Base: fork 1.1g (motor libmpv embebido + keep-open/eof cascade, probado).

## 0.1 (actual)
- Shell nuevo en `dankotv/`: Mis listas, layout declarativo, 12 skins, logo propio.
- Reutiliza motor base `usr/lib/dankoiptv/` (M3UParser, XTream, mpv binding).

## 0.2+ (futuro)
- Migrar a **mpv externo + IPC JSON** (mismo wid, mismos observers, crash-aislado).
- Investigar salidas de video modernas post-Qt (render API OpenGL/Vulkan,
  compositor propio, overlays GPU) sin perder keep-open + eof-reached +
  cascade. Si no existe, inventarlo.
