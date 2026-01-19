# Documentation MVP

## Overview

New users cannot understand the plugin's value from the current README. The intro jumps straight to features without explaining the problem being solved. There are no examples showing what context.md looks like, and no guidance on how to configure Claude Code to actually USE the captured context.

**Chosen approach**: Text-only README rewrite with inline user guide and example files. All content in README.md (no separate docs/ directory per user preference).

## Planning Context

### Decision Log

| Decision | Reasoning Chain |
|----------|-----------------|
| Text-only intro (no visuals) | User selected text-only -> faster to implement -> no external asset dependencies -> easier to maintain |
| User guide inline in README | User selected inline -> single file to read -> no navigation required -> better discoverability than separate docs/ |
| Problem-first intro structure | Current intro starts with features -> users don't know WHY they need this -> problem statement creates context -> features become solutions |
| Two example files (simple, detailed) | Simple shows first sessions -> detailed shows mature project -> covers user progression from novice to experienced |
| Examples use realistic content | Lorem ipsum provides no guidance -> real-looking decisions/patterns teach users what good looks like -> annotated examples explain choices |
| Defer technical todos to v2 | User selected Option A -> documentation is adoption blocker -> technical improvements can wait -> focus on what unblocks users now |

### Rejected Alternatives

| Alternative | Why Rejected |
|-------------|--------------|
| Separate docs/USER_GUIDE.md | User explicitly chose inline README |
| ASCII/GIF diagram in intro | User explicitly chose text-only |
| All 7 todos in one plan | Scope creep risk -> documentation is self-contained -> technical changes require separate testing |
| Auto-modify user's ~/.claude/CLAUDE.md | Too invasive -> users should control their global config -> provide copy-paste snippet instead |

### Constraints & Assumptions

- README must remain scannable (<5 min read)
- Examples must match current wiki format exactly (## Architecture, ## Decisions, etc.)
- No new dependencies or code changes
- Existing README structure preserved where possible (Features, Installation, etc.)
- `<default-conventions domain="file-creation">` applied: extend README.md rather than create new files where sensible

### Known Risks

| Risk | Mitigation | Anchor |
|------|------------|--------|
| Examples become stale if wiki format changes | Examples reference current format; format is stable (wiki_parser.py sections) | core/wiki_parser.py:L23-45 |
| README gets too long | Keep intro concise (problem + solution in <200 words); link to examples rather than inline all | N/A |
| User guide snippet outdated | Guide references stable paths (~/context/{classification}/{project}/) | N/A |

## Invisible Knowledge

### Architecture

This plan is documentation-only. No architectural changes.

### Why This Structure

README sections ordered for new user journey:
1. **Problem** - why should I care?
2. **Solution** - what does this do?
3. **How It Works** - quick mental model
4. **Features** - detailed capabilities
5. **Installation** - get started
6. **Using Context** - make it useful (NEW)
7. **Examples** - see real output (NEW)
8. **Configuration** - customize

### Tradeoffs

- **Completeness vs Brevity**: Inline user guide adds ~50 lines to README but eliminates navigation friction
- **Examples in repo vs linked**: In-repo examples are versioned with code but add maintenance burden

## Milestones

### Milestone 1: README Problem-First Introduction

**Files**: `README.md`

**Flags**: `needs-rationale`

**Requirements**:
- Replace current intro (lines 1-14) with problem-first structure
- Add "The Problem" section explaining context loss across sessions
- Add "The Solution" section explaining what plugin does
- Keep existing "How It Works" section but move after solution
- Preserve all existing sections below

**Acceptance Criteria**:
- First 3 sentences answer "why should I care?"
- Problem is concrete (not abstract "context management")
- Solution maps directly to problem
- Reading time for intro: <30 seconds

**Tests**: Documentation milestone - no tests required.

**Code Intent**:
- Replace lines 1-14 of README.md with new intro structure
- New sections: "The Problem", "The Solution"
- Move "How It Works" to follow "The Solution" (currently at line 101)
- Keep Features section after How It Works

---

### Milestone 2: Example Context Files

**Files**:
- `examples/context-simple.md` (NEW)
- `examples/context-detailed.md` (NEW)
- `examples/README.md` (NEW)

**Requirements**:
- Create simple example: 30-50 lines, shows first 2-3 sessions
- Create detailed example: 80-120 lines, shows mature project (~20 sessions)
- Create examples/README.md explaining when to reference each
- Examples must use exact wiki section format

**Acceptance Criteria**:
- Simple example has: Architecture (1 sentence), 2 decisions, 2 patterns, 2 recent work entries
- Detailed example has: Architecture (paragraph), 5+ decisions with rationale, 4+ patterns, resolved issues, 5 recent work entries
- Section headers match wiki_parser.py exactly: `## Architecture`, `## Decisions`, `## Patterns`, `## Issues`, `## Recent Work`
- Content is realistic (not Lorem ipsum)

**Tests**: Documentation milestone - no tests required.

**Code Intent**:

**examples/context-simple.md**:
- Header: `# Project Context`
- Architecture: Single sentence describing a CLI tool
- Decisions: 2 entries with brief rationale
- Patterns: 2 coding patterns
- Issues: 1 resolved issue
- Recent Work: 2 session entries with dates and topic tags

**examples/context-detailed.md**:
- Header: `# Project Context`
- Architecture: 2-3 sentences with component relationships
- Decisions: 5+ entries with Rationale/Alternatives/Context
- Key Symbols: 4-5 core modules
- Patterns: 4+ established patterns
- Learnings: 2 entries
- Issues: 3+ resolved issues
- Recent Work: 5 sessions showing progression

**examples/README.md**:
- Brief intro to examples
- When to reference simple vs detailed
- Anti-patterns section (what NOT to do)

---

### Milestone 3: User Guide Section in README

**Files**: `README.md`

**Requirements**:
- Add "Using Captured Context" section after Installation
- Include copy-paste snippet for ~/.claude/CLAUDE.md
- Explain what each context.md section contains
- Add 3-5 example queries demonstrating value
- Link to examples/ directory

**Acceptance Criteria**:
- Copy-paste snippet is complete and correct
- Snippet references correct paths: `~/context/{personal,work}/{project}/`
- Example queries reference actual section names
- Section is <100 lines

**Tests**: Documentation milestone - no tests required.

**Code Intent**:
- Add new section `## Using Captured Context` after Installation (around line 96)
- Subsections:
  - "Add to Your Claude Config" - the ~/.claude/CLAUDE.md snippet
  - "What's in context.md" - brief explanation of each section
  - "Example Queries" - 3-5 ways to ask Claude to use context
  - "See Examples" - link to examples/

---

### Milestone 4: Link Examples from README

**Files**: `README.md`

**Requirements**:
- Add "Examples" section linking to examples/
- Update existing Output Format section to reference examples
- Ensure examples are discoverable from README

**Acceptance Criteria**:
- Examples section exists with links to both example files
- Output Format section references examples for "see full example"
- Links use relative paths (examples/context-simple.md)

**Tests**: Documentation milestone - no tests required.

**Code Intent**:
- Add `## Examples` section after "Using Captured Context"
- Brief description of each example file
- Update Output Format section (around line 152) to add "See examples/ for complete files"

---

### Milestone 5: Documentation Index Update

**Delegated to**: @agent-technical-writer (mode: post-implementation)

**Source**: `## Invisible Knowledge` section of this plan

**Files**:
- `CLAUDE.md` (update root index)
- `examples/CLAUDE.md` (NEW - index for examples directory)

**Requirements**:

**CLAUDE.md** (root):
- Add `examples/` to Subdirectories table
- Entry: `examples/` | Sample context.md files | Understanding output format, learning patterns

**examples/CLAUDE.md** (new):
- Tabular index for example files
- Entries for context-simple.md, context-detailed.md, README.md

**Acceptance Criteria**:
- Root CLAUDE.md has examples/ entry
- examples/CLAUDE.md follows tabular format
- No prose sections in CLAUDE.md files

## Milestone Dependencies

```
M1 (intro) ──┐
             ├──> M3 (user guide) ──> M4 (link examples) ──> M5 (docs index)
M2 (examples)┘
```

M1 and M2 can run in parallel. M3 needs M2 complete to link examples. M4 needs M3. M5 runs last.
