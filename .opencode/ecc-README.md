# ECC (modo ahorrador) — reglas locales de referencia
Carpetas en `.opencode/ecc-rules/`: common + lenguaje(s) del proyecto.
Opencode las lee bajo demanda; no hay hooks globales prendidos.
Para cablearlas fijas, agregar a `opencode.json` del proyecto, ej:
{ "instructions": [".opencode/ecc-rules/common/coding-style.md"] }
Desinstalar: borrar `.opencode/ecc-rules/` y este archivo.
