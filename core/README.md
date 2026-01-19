# Core Modules

## Overview

Core modules implement wiki-style knowledge base with structured sections (Architecture, Decisions, Patterns, Issues, Recent Work) that merge and update rather than append session logs.

## Architecture

```
Before (session log):
SessionContext --> MarkdownWriter.append_session() --> context.md (append)
                                                        ↓
                                                   Useless logs

After (wiki):
SessionContext --> WikiParser.parse() --> WikiKnowledge
                         ↓
                   WikiMerger.merge(wiki, session)
                         ↓
                   WikiKnowledge (updated)
                         ↓
                   MarkdownWriter.write_wiki() --> context.md (structured)
```

## Data Flow

```
stop.py hook
    ↓
SessionAnalyzer.extract_session_context(changes, topics)
    ↓ returns SessionContext with category field
WikiParser.parse(context.md) or create empty WikiKnowledge
    ↓
WikiMerger.merge_session(wiki, session)
    ├─ deduplicate_decisions()
    ├─ update_patterns()
    ├─ update_issues()
    └─ rotate_recent_work(max=5)
    ↓
MarkdownWriter.write_wiki(wiki)
    ↓
context.md (structured wiki format)
```

## Monorepo Support

### Architecture

```
Session End (cwd = ~/valory/autonolas-frontend-mono/apps/marketplace/src)
        |
        v
+-------------------+
| detect_monorepo() |  <- Walk up to find nx.json
+-------------------+
        |
        v
+-------------------+
| MonorepoInfo      |  <- root=~/valory/autonolas-frontend-mono
|   type="nx"       |     workspace_relative="apps/marketplace"
|   workspace="marketplace"
+-------------------+
        |
        v
+-------------------+
| prompt_confirm()  |  <- "Detected NX monorepo. Use hierarchical context? [Y/n]"
+-------------------+
        |
        v (if confirmed)
+-------------------+
| context paths:    |
|  - root: ~/context/work/autonolas-frontend-mono/context.md
|  - workspace: ~/context/work/autonolas-frontend-mono/apps/marketplace/context.md
+-------------------+
```

### Detection Flow

```
Standard Marker Detection:
  cwd -> walk up -> find nx.json/turbo.json/lerna.json/pnpm-workspace.yaml
       -> MonorepoInfo(type="nx", ...)

Custom Pattern Detection (fallback):
  cwd -> walk up -> find subgraphs/ with nested package.json
       -> MonorepoInfo(type="subgraphs", ...)

No Monorepo:
  cwd -> walk up -> no markers, no custom patterns
       -> None (use single-repo mode)
```

### Why This Structure

**monorepo_detector.py separate from path_classifier.py**: Detection logic handles multiple marker types + custom patterns + filesystem walking. Complex enough to deserve own module with isolated testing.

**Custom patterns configurable**: `subgraphs/` is The Graph specific. Other ecosystems may have similar patterns. Config allows extension without code changes.

**NX apps/ + libs/ both detected**: Real projects like autonolas-frontend-mono use both. Apps are deployable services; libs contain shared code that also evolves. Both deserve context tracking.

**Standard markers take precedence**: Standard markers (nx.json, lerna.json) checked first. Custom patterns (subgraphs/) run as fallback to prevent false positives from coincidental directories.

**Interactive confirmation**: Prevents false positives and gives user control. Once confirmed, project cached to avoid re-prompting on subsequent sessions.

## Design Decisions

**WikiParser separate from Merger**: Single responsibility - parser only reads, merger only transforms. Parser handles all markdown parsing logic; merger contains deduplication and rotation logic.

**WikiKnowledge dataclass**: Type-safe contract between components. Provides IDE autocomplete and clear interface. All sections use empty lists (never None) to simplify merge logic.

**Merger handles all business logic**: Deduplication (0.8 similarity threshold), rotation (max 5 sessions), and categorization in one place. Centralizes decision-making for easier testing.

**Regex-based parsing**: Full markdown parser (mistune, markdown-it) would be overkill for 5 known sections. Regex pattern `## SectionName` is reliable for wiki format and faster with no dependencies.

**5 recent sessions before archiving**: Balances context window vs wiki length. Provides ~1 week of history for active projects; older sessions archived to git history.

**0.8 similarity threshold**: Exact match misses paraphrased duplicates; 0.8 cosine similarity catches semantically similar entries without false positives. Threshold tunable via config.

**LLM categorization**: File changes alone insufficient to determine if change is architectural, config, bugfix, etc. LLM determines routing to correct wiki sections based on semantic understanding.

**Graceful fallback**: Wiki parse may fail on corrupted/legacy files. Fallback to session append format preserves data; user can manually fix wiki structure later.

## Invariants

- WikiKnowledge sections are never None (use empty lists)
- Recent work list never exceeds max_recent_sessions (5)
- Decisions list contains unique entries (deduplication enforced)
- Section headers maintain exact format: `## Section Name`

## Section Format

Wiki sections follow strict markdown format for reliable parsing:

```markdown
# Project Context

## Architecture

[Text block describing system structure]

## Decisions

- Decision 1
- Decision 2

## Patterns

- Pattern 1
- Pattern 2

## Issues

- Issue 1
- Issue 2

## Recent Work

- [2024-01-07] Summary 1
- [2024-01-06] Summary 2
```

**Architecture**: Single text block (not list). Describes component relationships and data flow.

**Decisions/Patterns/Issues**: Bullet lists. Each entry is independent and deduplicated.

**Recent Work**: Bullet list with date prefixes. Rotates to maintain max 5 entries (6th session drops oldest).

## Tradeoffs

**More code vs LLM flexibility**: 300 lines of deterministic code instead of LLM handling edge cases. Provides predictable behavior and easier debugging at cost of additional maintenance.

**Fixed sections vs dynamic**: Core 5 sections hardcoded in parser. Adding sections requires code change rather than configuration. Simplifies implementation but reduces flexibility.

**Regex vs full parser**: Faster parsing with no dependencies, but may fail on unusual markdown formatting (nested headers, code blocks with ## patterns). Risk mitigated by graceful fallback to session format.
