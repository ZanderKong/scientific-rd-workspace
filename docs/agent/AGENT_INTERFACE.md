# External Agent Interface

External agents own natural-language interpretation, image/handwriting extraction, literature reasoning and conversational UX. The workspace owns validation, scientific structure, provenance, deterministic comparison, revisions and transactions.

Recommended sequence:

1. Call capabilities and schema discovery.
2. Read Project Context or search the project.
3. Read the relevant Sample, Experiment or Data Record and retain its hash.
4. Propose a ChangeSet for mutations, including the base hash for updates.
5. Let a human or trusted workflow review and apply the ChangeSet.
6. Re-read the resulting record and record hash.

Do not use generic graph mutation for aggregate writes. Do not infer membership from `related_to`; use the Experiment aggregate API and `includes` semantics.
