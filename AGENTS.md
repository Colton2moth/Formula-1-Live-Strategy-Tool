# Agent Instructions

The main goal is to help the developer understand the system.

## Behaviour

- Be concise and direct.
- Explain the purpose of a change before writing code.
- Work on one small task at a time.
- Do not create several files in one step.
- Do not generate large files without explicit approval.
- Keep new code under about 50 lines unless asked otherwise.
- Stop after each meaningful change so the developer can review it.
- Do not continue into the next phase automatically.
- Inspect the current repository files before changing frontend code.

## Source of truth

- Follow the existing structure, naming, scripts, linting, formatting, and component patterns unless there is a clear reason to improve them.
- Use the repo for current implementation details and the design doc for product intent.
- Do not invent backend capabilities that are not currently available.
- Do not add mock backend behavior into production code unless it is clearly separated as development or demo data.
- Do not commit secrets, API keys, tokens, or private URLs.
- Use environment variables for configurable API URLs. In Vite, client-exposed variables must use the `VITE_` prefix.

## Commit messages

- Use a concise conventional-commit subject: `tag(scope): short summary`.
- Pick the subject tag from the primary reason for the commit.
- Use these main tags:
  - `feat`: for new user-visible functionality, such as dashboard sections, strategy panel behavior, map interactions, or new controls.
  - `fix`: for correcting broken, inaccurate, or unintended behavior in the app, data handling, layout, or tooling.
  - `style`: for visual-only changes such as spacing, colors, Tailwind classes, responsive layout, or formatting that does not change logic.
  - `refactor`: for restructuring existing code without changing what the user sees or how the feature behaves.
  - `chore`: for maintenance work such as cleanup, project housekeeping, dependency metadata, or non-feature setup.
  - `docs`: for README, markdown, planning notes, comments, or agent instruction updates.
  - `test`: for adding, updating, or repairing tests and test fixtures.
  - `perf`: for measured performance improvements, such as reducing expensive live-update work or unnecessary rendering.
  - `build`: for build tooling, bundling, Vite config, package build scripts, or deployment build setup.
  - `ci`: for GitHub Actions, automated checks, deployment workflows, or other continuous-integration changes.
  - `revert`: for intentionally undoing a previous commit or change set.
  - `wip`: for temporary work-in-progress commits only when unavoidable; clean them up before merging when possible.
- Expect to use `feat`, `fix`, `style`, `refactor`, `chore`, `docs`, and `test` most often in this project.
- Use project-area body tags when a mixed commit also changes a specific layer:
  - `api`: for backend endpoints, client fetch logic, request/response handling, API validation, or live data connection changes.
  - `types`: for TypeScript domain types, API response types, literal unions, or view-model shape changes.
  - `data`: for static race, driver, team, circuit, mock, fixture, or demo data changes.
  - `state`: for selected-driver state, shared UI state, stores, context, or live connection state changes.
  - `assets`: for images, icons, flags, logos, track SVGs, and other visual files.
- Use scopes when helpful: `layout`, `header`, `toolbar`, `map`, `driver-table`, `strategy-panel`, `api`, `types`, `data`, `components`, `tailwind`, `assets`, `routing`, `state`, `responsive`, `animations`, `deps`, and `config`.
- When a commit contains multiple meaningful changes, add a body that groups every change under separate tag headings, using main tags and project-area tags such as `api`, `types`, `data`, `state`, or `assets`.
- Put all visible new functionality under `feat`, but also add project-area sections such as `api`, `types`, `data`, or `state` when those parts changed.
- Keep each grouped bullet specific enough that the developer can see what changed without reading the diff.
- Do not create empty sections or list tags that did not change.
- When making commit messages make sure to use past tense since you will be talking about changes that have already been implemented.
- You may look through previous commits for more examples.

## Simplicity rules

- Prefer plain functions and simple data structures.
- Avoid classes unless they clearly improve state management.
- Avoid abstractions created for possible future needs.
- Do not add dependency injection, repositories, factories, plugins, queues, caching, or microservices without discussion.
- Do not handle extremely unlikely edge cases.
- Handle only realistic failures relevant to the current task.
- Do not optimize before there is a measured problem.
- Do not refactor unrelated code.
- Do not introduce a library when the standard library is sufficient.
- Ask before adding new production dependencies.
- Do not write duplicate historical and live feature logic.

## Frontend guidance

- The current repo is a Python backend package, but the planned frontend is a live Formula 1 race strategy dashboard.
- The design doc defines four main UI areas: race header, track map, live driver table, and AI strategy panel.
- Make the AI strategy panel visually prominent because it is the main selling point.
- Use React, TypeScript, Vite, Tailwind CSS, and CSS variables for the MVP unless the repo already uses something different.
- Use TanStack Query for server data, Zustand only for shared UI state, local React state for component-only state, and Zod at API boundaries.
- Use native WebSocket for live updates when live streaming is needed.
- Use SVG for the circuit map and driver markers.
- Add Motion, ECharts, React Router, Vitest, and Playwright only when the feature needs them.
- Avoid Next.js, Redux, Bootstrap, Mapbox, and large animation/charting/state libraries before the MVP needs them.
- Build the real dashboard first, not a marketing landing page.
- Keep the layout dense, clean, high-contrast, data-heavy, and broadcast-like.
- Let the selected driver connect the map, table, and strategy panel.
- Fetch one shared race snapshot instead of making every component poll.
- Organize frontend code by feature, such as `track-map`, `leaderboard`, `strategy-panel`, and `race-header`.
- Create reusable UI elements for repeated patterns like panels, buttons, status chips, tables, and probability bars when it makes the app easier to understand. Keep them simple and named by visible purpose.
- Add routing only when the app gains multiple pages.
- Whenever a user interaction feature is added, such as hover states, click states, selected states, toggles, expandable panels, tooltips, focus states, or any other visual change triggered by user input, include a subtle accompanying animation or transition. Prefer short, consistent transitions for opacity, transform, colour, shadow, border, background, scale, or position changes so the UI feels cohesive without becoming distracting.


## Text and typography rules

- When adding visible text to the website, avoid raw semantic text tags such as `p`, `h1`, `h2`, `h3`, `h4`, `h5`, and `h6` in app UI components.
- Use `span` for inline text, labels, values, chips, table cells, and short fragments.
- Use `div` for block-level text, section titles, panel headings, empty-state copy, helper text, and paragraph-style copy.
- Apply text appearance through explicit Tailwind classes, CSS variables, or a small reusable text component rather than relying on browser default heading or paragraph styles.
- Every text `span` or `div` should include clear formatting intent, such as size, weight, colour/token, line-height, tracking, casing, or spacing when relevant.
- For heading-like text built with `div`, add accessibility metadata when it improves navigation, such as `role="heading"` and the appropriate `aria-level`.
- Do not create generic unstyled text wrappers. Keep typography consistent with the dense, high-contrast, broadcast-style dashboard.

## TypeScript and data rules

- Avoid `any`; use `unknown` plus narrowing or validation for external data.
- Define domain types for F1 concepts instead of passing unstructured objects around.
- Keep API response types separate from UI view-model types when their shapes differ.
- Use literal unions for known values such as flag status and tyre compounds.
- Avoid unsafe non-null assertions. Prefer guards, defaults, or fallback UI.
- Normalize driver data by stable driver ID or driver code before rendering.
- Keep server state and UI state separate. TanStack Query should own server state unless there is a clear reason not to.
- Use Zustand only for shared state that distant components need, such as selected driver, timing mode, live connection status, or normalized live driver snapshot.

## UI and UX priorities

- The header should show Grand Prix name, track name, current weather, flag status, session status, and lap count when available.
- Flag status should use clear labels as well as colour.
- Driver dots should support hover and keyboard focus details, and selecting a dot should update the strategy panel when that interaction exists.
- The leaderboard should show position, driver, team indicator, last lap, interval or gap, tyre compound, and country flag when available.
- Support a toggle between interval/gap-to-next-driver and gap-to-leader when data is available.
- Do not hide important race data behind hover-only interactions.
- Strategy predictions should show pit probabilities, likely next tyre compound, compound probability breakdown, model/data freshness, and unavailable states when relevant.
- Do not make predictions sound certain. Use wording such as `probability` or `model estimate`.
- Weather-aware visuals are optional polish, not an MVP blocker. If added, use theme tokens or classes rather than scattered hard-coded styles.
- When no race is live, show a useful non-race state instead of fake live data.

## Accessibility and performance

- Interactive driver dots, rows, toggles, and selects must be keyboard reachable and visibly focused.
- Do not communicate flag status, tyre compound, or warnings by colour alone.
- Provide labels for toggles, selects, and probability visualizations.
- Keep table rows compact but readable.
- Use stable keys for live driver data.
- Keep WebSocket parsing and normalization outside presentation components.
- Avoid expensive sorting, SVG recalculation, or layout work on every live tick unless the data actually changed.

## Verification

- Before finishing frontend work, run only the relevant scripts that exist in `package.json`.
- Do not invent missing commands. If a check does not exist, mention that it was unavailable.
- For frontend changes, verify relevant loading, empty, API error, reconnecting, missing selected driver, missing prediction, timing-mode, flag-status, wet-tyre, race-not-live, and narrow-desktop states.

## Before coding

State briefly:

1. The problem being solved.
2. The input and output.
3. Where it fits in the system.
4. Why the proposed design is the simplest reasonable choice.

## After coding

State briefly:

1. What changed.
2. How to run it.
3. How to verify it.
4. What the next small step would be.

Do not write the next step unless explicitly asked.
