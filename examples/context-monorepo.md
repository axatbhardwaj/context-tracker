# Monorepo Context Example

This example demonstrates hierarchical context tracking for a typical NX monorepo similar to `autonolas-frontend-mono`.

## Directory Structure

```
~/work/autonolas-frontend-mono/
├── nx.json                              # NX configuration (monorepo marker)
├── apps/
│   ├── marketplace/                     # Marketplace application
│   │   └── src/
│   └── dashboard/                       # Dashboard application
│       └── src/
└── libs/
    ├── ui-components/                   # Shared UI library
    │   └── src/
    └── auth/                            # Shared auth library
        └── src/
```

## Context File Hierarchy

```
~/context/work/autonolas-frontend-mono/
├── context.md                           # Root context
├── apps/
│   ├── marketplace/
│   │   └── context.md                   # Marketplace workspace context
│   └── dashboard/
│       └── context.md                   # Dashboard workspace context
└── libs/
    ├── ui-components/
    │   └── context.md                   # UI Components library context
    └── auth/
        └── context.md                   # Auth library context
```

---

## Root Context (`~/context/work/autonolas-frontend-mono/context.md`)

Captures cross-cutting architecture decisions, shared patterns, and NX configuration that affect all workspaces.

```markdown
# Project Context

## Architecture

NX monorepo with apps and libs structure. Apps (marketplace, dashboard) are deployable services. Libs (ui-components, auth) are shared dependencies consumed by apps.

Build system: NX with computation caching. Affected detection ensures only modified workspaces rebuild.

Data flow: Apps depend on libs, never vice versa. Libs may depend on other libs (auth depends on ui-components for login UI).

## Decisions

- Use NX for monorepo management: superior caching vs Lerna, better TypeScript support
- Shared libs in libs/ directory: prevents code duplication, enforces consistent patterns
- Strict dependency boundaries: apps cannot import from other apps, only from libs
- Centralized ESLint config: all workspaces use same linting rules

## Patterns

- Component structure: Presentational components in ui-components, container components in apps
- API layer: Each app has own API client, shared auth logic in auth lib
- Testing: Jest for unit tests, Playwright for E2E (per app)

## Issues

None

## Recent Work

- [2024-01-08] Added NX computation caching, reduced CI build time by 60%
- [2024-01-07] Implemented strict dependency boundaries with ESLint plugin
```

---

## Workspace Context: Marketplace App (`~/context/work/autonolas-frontend-mono/apps/marketplace/context.md`)

Tracks marketplace-specific features, APIs, and UI components.

```markdown
# Project Context

## Architecture

Marketplace app for trading NFTs. React frontend with Next.js SSR for SEO.

Pages: /browse (listing), /item/:id (detail), /profile (user dashboard).

State management: Zustand for global state (user auth, cart). React Query for server state (NFT data).

## Decisions

- Next.js over Vite: SSR required for NFT metadata indexing by search engines
- Zustand over Redux: simpler API, less boilerplate, sufficient for marketplace scope
- React Query for API caching: automatic refetch, cache invalidation handled declaratively

## Patterns

- API hooks: useNFTListing, useUserProfile wrap React Query for consistent error handling
- Image optimization: next/image for NFT thumbnails, lazy loading for gallery view
- Form validation: Zod schemas, shared across client and API validation

## Issues

- NFT metadata sometimes stale: IPFS gateway caching issue, considering CDN layer

## Recent Work

- [2024-01-08] Implemented NFT search with Algolia, added filters for price/rarity
- [2024-01-07] Optimized gallery view rendering, reduced initial load by 40%
- [2024-01-06] Added shopping cart with persistent storage in localStorage
```

---

## Workspace Context: UI Components Library (`~/context/work/autonolas-frontend-mono/libs/ui-components/context.md`)

Shared design system and reusable components.

```markdown
# Project Context

## Architecture

Shared UI component library for all apps. Built with React, Tailwind CSS, and Storybook for documentation.

Components exported as named exports: Button, Card, Modal, Input, etc.

Design tokens in tokens.ts: colors, spacing, typography follow design system.

## Decisions

- Tailwind CSS over styled-components: utility-first approach reduces bundle size, easier theming
- Storybook for component docs: interactive playground, visual regression testing
- TypeScript strict mode: ensures type safety across all consuming apps

## Patterns

- Compound components: Modal.Header, Modal.Body, Modal.Footer for flexible composition
- Controlled components: all form inputs are controlled, no uncontrolled state
- Accessibility first: all components follow ARIA guidelines, keyboard navigation tested

## Issues

None

## Recent Work

- [2024-01-08] Added dark mode variants for all components using Tailwind dark: modifier
- [2024-01-07] Implemented Card component with hover effects and multiple sizes
- [2024-01-06] Set up Storybook with component documentation and examples
```

---

## Workspace Context: Auth Library (`~/context/work/autonolas-frontend-mono/libs/auth/context.md`)

Shared authentication and authorization logic.

```markdown
# Project Context

## Architecture

Shared auth library providing JWT token management, login/logout hooks, and permission checks.

Exports: useAuth hook, AuthProvider context, requireAuth HOC.

Token storage: localStorage for refresh token, memory for access token (XSS protection).

## Decisions

- JWT over session cookies: enables stateless API, easier scaling across multiple app servers
- Refresh token rotation: mitigates stolen refresh token risk
- Permission-based access control: roles (admin, user, guest) mapped to permissions (read, write, delete)

## Patterns

- useAuth hook: returns user, login, logout, isAuthenticated methods
- AuthProvider: wraps app root, manages token refresh automatically
- requireAuth HOC: protects routes, redirects to login if unauthenticated

## Issues

None

## Recent Work

- [2024-01-08] Implemented automatic token refresh 5 minutes before expiry
- [2024-01-07] Added permission checking with usePermission hook
- [2024-01-06] Refactored login flow to use React Query for API calls
```

---

## Benefits of Hierarchical Context

### Workspace Isolation
Each app/lib maintains independent history. Marketplace changes don't clutter UI Components context.

### Shared Knowledge
Root context captures NX configuration, dependency boundaries, and patterns affecting all workspaces.

### Navigation Efficiency
LLM can read workspace-specific context without scanning entire monorepo history. Query "What was the last marketplace change?" reads only `apps/marketplace/context.md`.

### Scalability
Structure scales to dozens of workspaces. Adding a new app creates its own context file, no conflict with existing workspaces.

### Example Queries

**Workspace-specific**: "Check marketplace context for the NFT search implementation"
→ LLM reads `~/context/work/autonolas-frontend-mono/apps/marketplace/context.md`

**Cross-cutting**: "What are the NX dependency boundaries?"
→ LLM reads `~/context/work/autonolas-frontend-mono/context.md`

**Library-specific**: "How does the auth library handle token refresh?"
→ LLM reads `~/context/work/autonolas-frontend-mono/libs/auth/context.md`
