# Assistant assets

This directory contains the reusable building blocks that define how the local AI assistant behaves and which tasks it can perform.

- [Capabilities](capabilities/) — focused instruction modules that add a domain or output skill, such as programming, translation, HTML, or document writing.
- [Commands](commands/README.md) — the slash-command catalog, its generated English and Czech overviews, and the source `sc.json` definitions.
- [Models](models/README.md) — locally recorded metadata for the Ollama models used or evaluated by the project.
- [Profiles](profiles/) — reusable assistant personas, including teacher and Holly variants.
- [Tasks](tasks/) — task JSON files that compose defaults, instructions, profiles, capabilities, and model settings for a concrete workflow.

## Future ideas

- [ ] Add a short architecture guide showing how tasks, profiles, capabilities, and slash commands are combined at runtime.
- [ ] Add authoring guidelines and a template for a new task, profile, capability, or command.
- [ ] Add a language and naming convention reference for `*_cz`, `*_en`, and language-neutral files.
- [ ] Add a model-selection guide with recommended models for common tasks and available hardware.
- [ ] Add small input/output examples for the most commonly used tasks and commands.
- [ ] Add a validation command that checks cross-references, required translations, and JSON schemas in this directory.
- [ ] Add an evaluation set to track quality changes when prompts, models, or task settings evolve.
