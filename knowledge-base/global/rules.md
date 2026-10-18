# Global rules (domain-agnostic)

Applied to every domain. Never duplicated per-domain.

## Never translate (preserve verbatim)
- URLs (http/https), DOIs (`10.xxxx/...`), ORCID, email addresses, domain names.
- Citation markers: `[1]`, `[2, 3]`, `[12-15]`.
- Numeric values, units, clause references, figure/table labels, document IDs, revision markers.

Detection of these spans is implemented in `qdt.protect.find_protected_spans` (task T2.8).
