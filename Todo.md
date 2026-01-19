- we need to add a way to make the setup more seamless the directory setup initially doesn't work (like work and personal directories) 
    - we need to have more support for different kind of structures 

- we need to add a guide for the user specific claude.md which instructs the CC to actually use context present otherwise it will be sitting garbage

- we also need to add some examples of the context.md 

- we need to have some mechanism for CC to recognize that subsections like architectures are missing

- better structure for monorepos 

- we also need to check and install gemini-cli via npm or bun if not present already and prompt user of the same 

- CRITICAL: Implement `hooks/gemini_stop.py` (referenced in GEMINI.md but missing)
- CRITICAL: Add validation to `core/config_loader.py` (missing schema check)
- CRITICAL: Add test coverage for `core/markdown_writer.py` (file exists but no corresponding test)
- [COMPLETED] Fix `WikiKnowledge` data loss in `core/markdown_writer.py` (was missing Key Symbols)
- [COMPLETED] Fix defensive coding in `core/wiki_parser.py`

Reviews :
[05:19]cyber_walk3r: Minor Feedback
Add more detail about what this does and how this is useful for others to adopt or try. Here (https://github.com/axatbhardwaj/cc-context-tracker-plugin?tab=readme-ov-file#claude-context-tracker) instead of directly talking about features, make them interested in scrolling below to the features
GitHub
GitHub - axatbhardwaj/cc-context-tracker-plugin: Automated context ...
Automated context tracking plugin for Claude Code - captures what changed and why in every session - axatbhardwaj/cc-context-tracker-plugin
Automated context tracking plugin for Claude Code - captures what changed and why in every session - axatbhardwaj/cc-context-tracker-plugin
[05:22]cyber_walk3r: Probably adding a working example or similar text to ensure users link to this plugins functionality
