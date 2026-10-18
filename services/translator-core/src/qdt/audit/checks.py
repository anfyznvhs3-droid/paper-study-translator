from dataclasses import dataclass
from pathlib import Path

from qdt.queue import FilledTranslationQueue


@dataclass(frozen=True)
class AuditIssue:
    code: str
    message: str


def audit_translation_output(
    queue: FilledTranslationQueue,
    output_path: str | Path | None,
) -> list[AuditIssue]:
    issues: list[AuditIssue] = []
    output_text = ""

    if output_path is None or not Path(output_path).exists():
        issues.append(AuditIssue("missing_output_path", "Output path does not exist."))
    else:
        output_text = Path(output_path).read_text(encoding="utf-8")

    if "[미번역]" in output_text:
        issues.append(AuditIssue("untranslated_marker", "Output contains [미번역]."))
    if "\ufffd" in output_text:
        issues.append(AuditIssue("replacement_character", "Output contains Unicode replacement character."))

    for item in queue.items:
        if not (item.korean or "").strip():
            issues.append(
                AuditIssue(
                    "empty_translation",
                    f"Empty translation at page {item.source.page_number} block {item.source.block_id}.",
                )
            )

    modal_text = output_text + "\n" + "\n".join(
        [item.source.text for item in queue.items] + [item.korean or "" for item in queue.items]
    )
    if "Google Translate Draft modal" in modal_text:
        issues.append(
            AuditIssue(
                "google_translate_draft_modal",
                "Google Translate Draft modal-heavy content may require review.",
            )
        )

    return issues

