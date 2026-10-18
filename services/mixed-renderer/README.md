# Mixed-language PDF Renderer

This service handles PDF files that already contain both English/Latin text and Korean/CJK text.
It avoids overlay-based translation because overlaying new Korean text on top of existing Korean text
can cause unreadable collisions.

## Output

For mono output, the renderer writes final translation artifacts into the document output folder:

- `<source>-ko-mono.pdf`
- `<source>-ko-mono.md`
- `<source>-ko-mono.html`

The PDF is the primary app result. MD and HTML are generated for review, correction, and future
translation-memory workflows.

## Quality Policy

- Translate English-heavy lines into Korean.
- Preserve existing Korean/CJK text.
- Normalize Korean spacing with `kiwipiepy`.
- Merge orphan list markers such as `•` and `1)` into the following text line.
- Apply confirmed glossary and spacing overrides before rendering.

## Runtime Dependencies

Install the local service dependencies:

```powershell
python -m pip install -r services\mixed-renderer\requirements.txt
```

The desktop app invokes this renderer with `--require-spacing`, so missing `kiwipiepy` should fail
early instead of silently producing lower-quality spacing.
