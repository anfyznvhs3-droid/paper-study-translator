from collections import defaultdict

from qdt.queue import FilledTranslationQueue, TranslationQueueItem


def render_markdown(queue: FilledTranslationQueue, output_mode: str = "mono") -> str:
    if output_mode not in {"mono", "dual"}:
        raise ValueError("output_mode must be 'mono' or 'dual'")

    pages: dict[int, list[TranslationQueueItem]] = defaultdict(list)
    for item in queue.items:
        pages[item.source.page_number].append(item)

    chunks: list[str] = []
    for page_number in sorted(pages):
        chunks.append(f"## Page {page_number}")
        if output_mode == "mono":
            chunks.extend(_translated_lines(pages[page_number]))
        else:
            chunks.append("### Original")
            chunks.extend(item.source.text for item in pages[page_number])
            chunks.append("### Korean")
            chunks.extend(_translated_lines(pages[page_number]))
    return "\n\n".join(chunks) + "\n"


def _translated_lines(items: list[TranslationQueueItem]) -> list[str]:
    return [item.korean or "" for item in items]

