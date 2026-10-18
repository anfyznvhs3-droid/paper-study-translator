// Friendly labels for known domain slugs. Unknown (auto-discovered) slugs fall
// back to a title-cased version of the slug, so adding a new domain folder needs
// no code change — it just shows up with a readable name.
const KNOWN_DOMAIN_LABELS: Record<string, string> = {
  "academic": "학술·학습",
  "quality-manufacturing": "품질·제조 (Quality / Manufacturing)"
};

export function domainLabel(slug: string): string {
  if (!slug) {
    return "";
  }
  return (
    KNOWN_DOMAIN_LABELS[slug] ??
    slug
      .split(/[-_]/)
      .filter(Boolean)
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ")
  );
}
