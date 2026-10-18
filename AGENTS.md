# Paper Study Translator

- Preserve the English/Korean side-by-side PDF workflow, OCR and user review records.
- UI controls share the contracts in apps/desktop/src/styles/README.md.
- Keep runtime data, API keys, local environments, agent transcripts and user documents out of Git and release archives.
- Do not add machine-specific paths. Resolve bundled resources relative to the executable and store writable data in the current user's application data directory.
- Run scripts/check-all.ps1 for release changes. Use an isolated runtime directory and synthetic/offline translations for packaging checks; never make billable API calls as part of tests.
- Stage explicit reviewed paths. Do not rewrite history or make remote changes without the user's instruction.

