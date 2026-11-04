# Knovex frontend spec

## How to work
- Read this file and the frontend rules file at the start of every session. Do not re-read the whole repo; open only the files you need.
- One milestone per session. Plan first (max 40 lines: files, components, stores), wait for my OK, then build. Show diffs before applying.
- Pin exact dependency versions. Tailwind must be v3.4.x (not v4). TypeScript strict, no `any`.
- Reference design files (static prototype): frontend/reference/index.html, styles.css, app.js. Port the design, don't copy blindly.

## Stack (approved, nothing else without asking)
Vite, React 18, TypeScript, Tailwind 3.4, Zustand, react-markdown (no rehype-raw, no raw HTML), lucide-react (max 6 icons, stroke 1.5, only where an icon carries meaning: upload, close, theme, delete, pin, copy), @fontsource packages (latin subset, weights 400/600/700 only, no CDN).
Forbidden: shadcn, MUI, Chakra, Radix, Headless UI, framer-motion, shiki, prismjs, any UI kit or component library.

## Identity: "the marked-up printout"
Yellow highlighter appears ONLY where an answer is backed by a source. Highlighted claim + citation chip = grounded. Plain text = unsupported. No highlight at all = nothing on file. Yellow is used nowhere else.

## Tokens (override Tailwind theme completely: colors, spacing, fontSize; map colors to CSS variables)
Light: bg #DCE3DD, panel #E8EEE9, ink #15231D, muted #4D6157, line #B7C3BA, mark #F2D230, mark-bg rgba(242,210,48,.55), danger #A63A28
Dark:  bg #0F1713, panel #16211C, ink #E3EBE5, muted #8CA095, line #2A3A32, mark #E8C928, mark-bg rgba(232,201,40,.26), danger #E0715E
Contrast is pre-verified. Do not change the hex values. `line` is for decorative dividers only; text and control borders use ink or muted.
Theme: prefers-color-scheme by default, manual toggle persisted in localStorage.
Spacing scale (px): 4, 8, 12, 16, 24, 32, 48, 64. Type scale (px): 12, 14, 16, 19, 24, 32. No arbitrary values (no w-[283px], no text-[17px]).
Fonts: Schibsted Grotesk (UI), Spectral (answer text), JetBrains Mono (scores, filenames, ids, timings only).
Radii by role: inputs 2px, buttons 4px, chips 3px, panels 0. No shadows. No gradients (the hatched "nothing on file" pattern is the only repeating-linear-gradient).
Motion: inspector open 150 ms and chip press only. Respect prefers-reduced-motion.

## Layout
App is 100dvh. Three panes scroll independently; the question input is pinned to the bottom of the desk.
Left "shelf" 250px: workspace name and role, threads, documents with real ingestion states, upload drop zone (label + input, keyboard accessible), signed-in user and sign out.
Center "desk": top bar with two segmented controls (passages 3/5/8, search mode Meaning / Hybrid / Hybrid + rerank) and theme toggle; the thread; the input.
Right "source" 370px: the inspector. Below 980px the panes stack and the inspector becomes a bottom sheet (Esc closes, focus moves in, returns to the chip on close).

## Components
- Answers are memos, not chat bubbles. Question = heading. Answer = Spectral 19px, line-height 1.75, max 46rem. No avatars, no typing dots.
- Claim sentences with citations: highlight (mark-bg) plus a small numbered chip. Numbers are per answer; chips of the same chunk share a number. Hover shows the first 120 chars. Chip has aria-label ("Citation 1, <file>, page <n>") and aria-pressed; active chip turns mark-yellow.
- Sentence text renders as inline markdown only (strong, em, code, links). Links: http(s) only, rel="noopener noreferrer". Block markdown (lists/tables) is deferred.
- Inspector order: "The claim" (highlighted sentence), "What the source says" (chunk text), then filename, page, characters, indexed time (only if provided), three gauges (meaning, keywords, rerank, 0-1) with numbers, button "Copy passage".
- Under each answer: one timing line ("Retrieval 42 ms, rerank 210 ms, model 890 ms") plus one thin bar split into three ink-toned segments proportional to those times. No emoji, no pills, no lightning icons.
- "Nothing on file" block: hatched background, sentence "Nothing on file for this question." plus the API's reason.
- Segmented controls use role="radiogroup" with radio semantics. Status is never conveyed by color alone (always text).
- Threads (M2): grouped Today / Yesterday / Earlier; rename inline (double-click); delete with inline "Delete? Yes / No" (no modal); pin moves to top; "Answer only from" with plain checkboxes.
- Empty, loading and error states are written: "Searching your documents…", "No documents yet. Drop a PDF or TXT to start.". Errors say what failed and what to do. No "Oops", no apology.

## Auth
Access token in memory + sessionStorage (never localStorage). Any 401 clears the session and shows sign in. Register/login field names live as constants at the top of api.ts. (Refresh-token flow is out of scope for M1.)

## State (Zustand, small separate stores, selectors only, no prop drilling)
authStore, docsStore (polls only while a document is not indexed/failed), threadsStore, uiStore (theme, topK, mode, inspectorOpen), citationStore (activeChunk, activeClaim).
In M1 messages live in memory only (one local thread). Persistence arrives in M2.
Pure logic lives in src/lib as plain functions with no React: groupThreadsByDate, numberChunks, timelineSegments.

## API contract (types.ts must match; add parseAnswer() that validates the shape and throws a readable error)
POST /api/v1/chat/query  {question, top_k, mode}   (mode: dense | hybrid | rerank)
-> {sentences:[{text, citations:[chunkId]}], chunks:{id:{doc_id, filename, page, char_count, text, indexed_at?, scores:{dense,sparse,rerank}}}, timings:{retrieval_ms, rerank_ms, llm_ms}, abstained, reason}
M2 adds: thread_id?, document_ids? and endpoints GET/POST /threads, PATCH /threads/{id} {title, pinned, document_ids}, DELETE /threads/{id}, GET /threads/{id}/messages.
All fetches go through api.ts. Non-200 shows the API's detail message. Render all text as text, never dangerouslySetInnerHTML.
Mock mode: VITE_MOCK=1 makes api.ts return fixtures from src/mocks (one answered, one abstained, one error), so the UI can be built before the backend is ready.

## Milestones (stop and show me after each)
M1: sign in/register, documents with upload and live states, ask, memo answer with highlights, citations, inspector, controls, theme, mock mode.
M2: threads and document scope (only after I confirm the backend endpoints exist).
M3: multi-stage Dockerfile (node build, copy dist into the API image), FastAPI serves frontend/dist at "/" after the API routers with SPA fallback, remove the old static files, README screenshots, build size report.

## Before finishing any milestone, run and report
- grep src for default Tailwind color classes (slate, gray, zinc, orange, emerald, etc.) and arbitrary values (`-[`).
- grep for dangerouslySetInnerHTML, localStorage use for tokens, and any dependency not on the approved list.
- `npm run build` result and bundle size.
