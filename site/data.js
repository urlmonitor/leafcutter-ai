/* leafcutter pipeline data — all content lives here so app.js can render both views.
   A later step can swap these in-page objects for fetched JSON without touching markup logic. */

window.LEAFCUTTER_DATA = {

  /* ── PIPELINE STAGES ──────────────────────────────────────────── */
  pipelineStages: [
    {
      num: '01',
      id: 'plan',
      stage: 'Plan',
      command: '/plan-feature',
      engine: 'scripts/workflows/plan-feature.js',
      inputs: 'Natural-language feature request',
      outputs: 'AC YAML files in docs/acceptance-criteria/ only (no tickets)',
      gate: 'User confirmation gate after each authoring stage; user sets priority and readiness: approved at the final gate',
      agents: ['ac-triage', 'product-owner', 'business-analyst', 'it-po'],
      color: 'leaf'
    },
    {
      num: '02',
      id: 'select',
      stage: 'Select & Generate',
      command: '/build-ac',
      engine: 'ac-scanner skill (scan_ac_store.py + generate_ticket_from_ac.py)',
      inputs: 'AC store (readiness: approved leaf ACs only)',
      outputs: 'One ticket .md (or epic folder) with implemented_by back-link written to the AC',
      gate: 'User prompt: "Build this ticket now? (yes / review / skip)" — then hands off to /build-feature',
      agents: ['ac-scanner'],
      color: 'soil'
    },
    {
      num: '03',
      id: 'build',
      stage: 'Build',
      command: '/build-feature',
      engine: 'build-feature Workflow (batching inline; ticket-supervisor at depth 0)',
      inputs: 'Epic name / epic folder path / single ticket path',
      outputs: 'Committed code on feature branch; ticket agents: map fully signed off',
      gate: 'Per-phase gates inside the drive: test-writer → coders → pr-reviewer → ac-validator → commit; PR opened',
      agents: ['ticket-supervisor', 'test-writer', 'python-coder', 'sql-coder', 'frontend-coder', 'pr-reviewer', 'ac-validator', 'commit', 'pull-request'],
      color: 'amber'
    },
    {
      num: '04',
      id: 'finalize',
      stage: 'Finalize',
      command: '/finalize-feature',
      engine: 'templates/workflows-js/finalize-feature.js (Workflow, leaf)',
      inputs: 'Epic/branch name',
      outputs: 'Merged PR to main, synced local main, tickets closed, epic archived to 99_done, worktree removed',
      gate: 'HALT on merge conflict or test regression; confirmation gate on PR merge and worktree removal',
      agents: ['changelog-agent', 'retrospective-agent'],
      color: 'terracotta'
    }
  ],

  quickFix: {
    command: '/quick-fix',
    description: 'Fast-lane in-place bug-fix pipeline. Runs the full red→green TDD cycle in the current worktree with no new branch or worktree (ADR-006 addendum, BP-600*). Forbidden from creating any worktree (BP-600a-2).'
  },

  /* ── AC STORE ─────────────────────────────────────────────────── */
  flightLevels: [
    { level: 'L0', meaning: 'Customer value proposition (root goal)', agent: 'product-owner', type: 'composite' },
    { level: 'L1', meaning: 'Feature benefit statement (sub-goal)', agent: 'product-owner', type: 'composite' },
    { level: 'L2', meaning: 'Testable Gherkin behaviour (Given/When/Then)', agent: 'business-analyst', type: 'leaf' },
    { level: 'L3', meaning: 'Edge-case / failure-mode specification', agent: 'business-analyst', type: 'leaf' },
    { level: 'enrichment', meaning: 'Technical fields added to L2/L3 ACs', agent: 'it-po', type: 'enrichment' }
  ],

  readiness: [
    { state: 'draft', setBy: 'product-owner-v3 / business-analyst-v3', pickedUp: false, description: 'Newly authored, not yet reviewed' },
    { state: 'reviewed', setBy: 'it-po-v3 (after technical enrichment)', pickedUp: false, description: 'Technically enriched, awaiting PO approval' },
    { state: 'approved', setBy: 'User (via /build-ac or manual edit)', pickedUp: true, description: 'Scanner picks this up — gates ticket generation' }
  ],

  acComponents: [
    'finalize (FIN)', 'ticket-creation (TKT)', 'build-pipeline (BP)',
    'build-orchestration (BO)', 'infrastructure (INF)', 'ux-prototyping (UXP)',
    'persona-management (PER)', 'ac-store (ACS)', 'guardrail-engine (GE)',
    'knowledge-management (KM)', 'testing-quality (TQ)', 'stakeholder-delivery (SD)',
    'ac-driven-dev (ACD)'
  ],

  acYamlSnippet: `id: ACD-1100b-3-i
components:
  - ac-driven-dev
readiness: approved    # draft | reviewed | approved
priority: high         # critical | high | medium | low
title: "Edge case: no agent in the entire registry carries any version suffix"
component: ac-driven-dev
level: L3              # L0 | L1 | L2 | L3
status: active
criteria: |            # Gherkin Given/When/Then — BA-owned, write-locked
  Given the agent registry contains entries with no version suffix
  When the scanner processes the registry
  Then it returns an empty suffix list without error
depends_on:
  - ACD-1100b-3
assigned_agent: python-coder   # IT-PO enrichment
estimated_complexity: S        # S | M | L | XL
delivers_to: null
expects_from:
  ac_id: ACD-1100b-3
  contract: "..."
origin_agent: BrainCandy
created: 2026-06-05
implemented_by: []             # written by /build-ac`,

  /* ── AGENTS & SUPERVISOR MODEL ───────────────────────────────── */
  depthModel: [
    { depth: 0, label: '/build-feature (slash command)', note: 'batching inline', indent: 0 },
    { depth: 0, label: 'ticket-supervisor', note: 'executing context, NOT a spawned sub-agent', indent: 1 },
    { depth: 1, label: 'test-writer', note: 'Agent tool', indent: 2 },
    { depth: 1, label: 'python-coder', note: 'Agent tool', indent: 2 },
    { depth: 1, label: 'pr-reviewer', note: 'Agent tool', indent: 2 },
    { depth: 1, label: 'ac-validator', note: 'Agent tool', indent: 2 },
    { depth: 1, label: 'commit', note: 'Agent tool', indent: 2 },
    { depth: 1, label: 'pull-request', note: 'Agent tool', indent: 2 }
  ],

  phaseOrder: [
    { priority: '1', agent: 'status-checker', group: 'git' },
    { priority: '2', agent: 'adr-author', group: 'docs' },
    { priority: '3', agent: 'architecture-diagram-author', group: 'docs' },
    { priority: '3.5', agent: 'it-po', group: 'authoring' },
    { priority: '4', agent: 'architect-review', group: 'review' },
    { priority: '5', agent: 'test-writer', group: 'tdd', highlight: true, note: 'writes failing tests BEFORE coders' },
    { priority: '6', agent: 'python-coder / llm-expert', group: 'implementation' },
    { priority: '7', agent: 'sql-coder / sql-query', group: 'implementation' },
    { priority: '8', agent: 'frontend-coder', group: 'implementation' },
    { priority: '9', agent: 'test-runner', group: 'tdd' },
    { priority: '10', agent: 'change-scope-reviewer / documentation-expert', group: 'docs' },
    { priority: '11', agent: 'pr-reviewer', group: 'review', highlight: true, note: 'final quality gate' },
    { priority: '11.5', agent: 'ac-validator + user-surface-smoker', group: 'review', highlight: true, note: 'AC coverage gate (concurrent)' },
    { priority: '11.7', agent: 'ac-fulfillment-gate', group: 'review', highlight: true, note: 'AC store fulfilment' },
    { priority: '12', agent: 'commit', group: 'git', highlight: true, note: 'atomic commit' },
    { priority: '13', agent: 'pull-request', group: 'git', note: 'push + open PR' }
  ],

  agentFamilies: [
    {
      family: 'Authoring',
      color: 'leaf',
      agents: ['product-owner', 'business-analyst', 'it-po', 'ac-triage']
    },
    {
      family: 'Implementation',
      color: 'soil',
      agents: ['python-coder', 'sql-coder', 'frontend-coder', 'llm-expert']
    },
    {
      family: 'Test / TDD',
      color: 'amber',
      agents: ['test-writer', 'test-runner', 'test-failure-triage']
    },
    {
      family: 'Review / Gates',
      color: 'terracotta',
      agents: ['pr-reviewer', 'architect-review', 'change-scope-reviewer', 'ac-validator', 'ac-fulfillment-gate', 'user-surface-smoker']
    },
    {
      family: 'Git',
      color: 'ink',
      agents: ['commit', 'pull-request', 'worktree-agent', 'status-checker', 'conflict-resolver']
    },
    {
      family: 'Docs / Knowledge',
      color: 'sage',
      agents: ['documentation-expert', 'how-to-author', 'reference-author', 'explanation-author', 'adr-author', 'architecture-diagram-author', 'knowledge-harvester', 'glossary-triage']
    },
    {
      family: 'Escalation',
      color: 'amber',
      agents: ['brainstorm-lead', 'brainstorm-worker', 'research-agent']
    },
    {
      family: 'Meta / Package',
      color: 'leaf',
      agents: ['workflow-architect', 'onboard', 'onboard-config-section', 'changelog-agent', 'retrospective-agent', 'feedback-analyst']
    }
  ],

  /* ── TICKETS, EPICS & WORKTREES ──────────────────────────────── */
  ticketLifecycle: [
    { folder: '00_inbox/', label: 'Inbox', icon: 'inbox', description: 'Proposed work; epic sub-folders (EPIC-Name/) for multi-ticket work', color: 'soil' },
    { folder: '01_todo/', label: 'In-flight', icon: 'build', description: 'Actively being driven; one git worktree per epic; sub-folder done/ for completed sub-tickets', color: 'amber' },
    { folder: '99_done/', label: 'Archived', icon: 'done', description: 'Finished epics and single tickets; full sign-off required', color: 'leaf' },
    { folder: '99_rejected/', label: 'Rejected', icon: 'reject', description: 'Decided-against work, kept for history and context', color: 'terracotta' }
  ],

  ticketFrontmatterSnippet: `advances_current_outcome: true
agents:
  commit: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  pull-request: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  test-writer: needed
components:
- ac-driven-dev
created: '2026-06-10'
depends_on:
- ACD-1100b-3
files_touched:
- docs/reference/agent-template-frontmatter.md
priority: high
requires_adr: false
requires_diagram: false
roadmap_phase: phase_1
source_ac: ACD-1100b-3-i
status: todo
title: 'Edge case: no agent in registry carries any version suffix'`,

  /* ── GATES ───────────────────────────────────────────────────── */
  gates: [
    {
      name: 'Sign-off three-place parity',
      icon: 'signoff',
      description: 'Enforced by check_ticket_signoff_parity.py. An agent must atomically: (1) set agents.<name>: signed_off in frontmatter, (2) tick the Sign-offs checkbox with em-dash + timestamp, (3) tick all its Implementation Tasks checkboxes — in one commit.'
    },
    {
      name: 'Test-first TDD',
      icon: 'tdd',
      description: 'test-writer (priority 5) runs before any coder and writes failing tests. Coders make the red baseline green. test-runner (priority 9) validates. check-contract-shrinking blocks test deletion or weakening at commit time. Docs-only/config-only tickets auto-skip.'
    },
    {
      name: 'Commit Guardian hooks',
      icon: 'hooks',
      description: 'Pre-commit manifest enforces: sign-off parity · AC schema + governance (write-locks criteria field) · AC tree limits + circular deps · TDD contract-shrinking · error handling (E722/BLE001/TRY) · docs/arch integrity · quality (cyclomatic ≤ 15, file-size limits) · package integrity (build-drift, output-drift).'
    },
    {
      name: 'PR-only main + Ruff gate',
      icon: 'pr',
      description: 'Direct push to main is rejected by branch protection. Ruff (E722, BLE001, TRY families + lint) is the required CI status check. A non-required pytest job also runs with a known pre-existing baseline failure.'
    },
    {
      name: '/finalize-feature HALT steps',
      icon: 'halt',
      description: 'Step 2: merge origin/main → HALT on conflict. Step 3: post-merge tests + failure-triage → HALT on regressions (baseline-diffed). Step 4: PR merge is confirmation-gated. Step 3.5: pre-merge AC closure on the feature branch.'
    }
  ],

  /* ── PACKAGE MODEL ───────────────────────────────────────────── */
  packageModel: {
    buildScript: 'scripts/build.py',
    outputRoot: '.leafcutter (bridged to .claude via shims — ADR-004)',
    platforms: 'Claude + Antigravity (dual-platform compilation — ADR-002)',
    config: 'skills_config.json — per-adopter, generated by /onboard',
    selfHosting: 'build-self.sh = build.py --target-dir . from workspace parent (ADR-001)',
    roadmapPhase: 'phase_1',
    roadmapOutcome: 'Stable MVP that installs into any project and helps the user build good software — portable, self-onboarding, and reliable enough to use across multiple repos.',
    exitCriteria: [
      'Clean install on a blank project with only skills_config.json',
      'build.py --validate-only returns 0',
      'Consecutive builds produce zero git diff (idempotent)',
      'Self-hosting parity'
    ]
  },

  /* ── HAPPY PATH JOURNEY ──────────────────────────────────────── */
  happyPath: [
    { step: 1, actor: 'User', text: 'States a feature intent → runs /plan-feature "<request>".' },
    { step: 2, actor: 'ac-triage', text: 'Haiku agent classifies the request: strategic / behavioral / technical / covered.' },
    { step: 3, actor: 'product-owner', text: 'Authors L0/L1 ACs (customer value propositions) → user confirmation gate.' },
    { step: 4, actor: 'business-analyst', text: 'Decomposes into L2/L3 Gherkin ACs (Given/When/Then) → user confirmation gate.' },
    { step: 5, actor: 'it-po', text: 'Adds technical enrichment (assigned_agent, contracts, complexity estimates) → user gate.' },
    { step: 6, actor: 'User', text: 'Sets priority + readiness: approved; AC YAML files land in docs/acceptance-criteria/.' },
    { step: 7, actor: '/build-ac', text: 'Ranks ready leaf ACs by priority → complexity, generates a ticket, writes implemented_by back-link, prompts yes / review / skip.' },
    { step: 8, actor: '/build-feature', text: 'Resolves the target and creates/reuses a git worktree off origin/main (bootstraps .leafcutter + pre-commit config).' },
    { step: 9, actor: 'ticket-supervisor', text: 'Depth-0 orchestrator drives the ticket: test-writer (5) writes failing tests → python/sql/frontend-coder (6-8) implement → test-runner (9) greens them.' },
    { step: 10, actor: 'Review gates', text: 'pr-reviewer (11) self-reviews the diff; ac-validator (11.5) + user-surface-smoker confirm AC coverage; ac-fulfillment-gate (11.7) updates the AC store.' },
    { step: 11, actor: 'commit (12)', text: 'Stages + commits (pre-commit hooks fire: signoff parity, AC governance, exception handling, contract-shrinking, secrets, etc.). Each phase signs off via the signoff skill.' },
    { step: 12, actor: 'pull-request (13)', text: 'Pushes the branch and opens one PR per epic. Ruff CI is the required gate on main.' },
    { step: 13, actor: '/finalize-feature', text: 'Captures baseline, merges origin/main (HALT on conflict), post-merge tests + triage (HALT on regression), closes tickets + marks source ACs done (step 3.5), merges PR (confirmation-gated), syncs main, archives epic to 99_done, removes worktree.' },
    { step: 14, actor: 'changelog + retro', text: 'changelog-agent + retrospective-agent produce the changelog and epic retrospective.' }
  ],

  /* ── FUTURE VIEW ─────────────────────────────────────────────── */
  future: {
    thesis: 'Every product rests on baseline business information — the things that exist, the journeys people take, and the screens they see.',
    tagline: 'Agents read the JSON. The Product Owner reviews the picture. They are the same artifact.',
    surfaces: [
      {
        id: 'flows',
        label: 'Flows',
        icon: 'flow',
        description: 'A visual journey map: ordered steps with decision branches. The PO reviews the journey itself — "is this how it should go?" — before any AC or ticket exists.',
        consumedBy: ['business-analyst derives L2/L3 Gherkin ACs from the flow', 'frontend-coder knows which screens each step needs']
      },
      {
        id: 'mock-data',
        label: 'Mock Data',
        icon: 'data',
        description: 'The canonical sample dataset the product cannot exist without. One source of truth with two jobs: populates mockups so they look real, seeds test fixtures so tests run against the same data the PO reviewed.',
        consumedBy: ['frontend-coder renders mockups from it', 'test-writer builds fixtures from it — no more synthetic fixtures that hide bugs']
      },
      {
        id: 'mockups',
        label: 'Mockups',
        icon: 'mockup',
        description: 'Visual proposals for each screen in a flow, populated with approved mock data. The PO reviews look, feel, and layout — approve, or request changes with a note.',
        consumedBy: ['frontend-coder implements to match the approved mockup', 'the mockup becomes the visual acceptance target']
      }
    ],

    acPipeline: {
      youSay: '“I want customers to browse our plants and buy one.”',
      youSayNote: 'Plain words — no tickets, no jargon.',
      triage: { title: 'The system reads and sorts your request', sub: 'Checks existing plans first, so nothing gets built twice.' },
      existsQ: 'Already planned?',
      coveredEnd: 'Reuse what already exists — nothing new to write.',
      kindQ: 'What kind of change?',
      authors: [
        { branch: 'A brand-new idea', node: 'It shapes the goal', sub: 'Captures the value and the benefit, in plain customer language.' },
        { branch: 'New behaviour', node: 'It writes the behaviours', sub: 'Turns the goal into clear, testable if-this-then-that rules.' },
        { branch: 'A new rule or limit', node: 'It adds the details', sub: 'Notes constraints, effort, and how the pieces hand off.' }
      ],
      draft: { title: 'The system drafts three things for you to review', sub: 'Populated with real sample data, so they look like the real product.', artifacts: ['Flow', 'Mock Data', 'Mockups'] },
      reviewQ: 'You approve?',
      reviewNote: '← this is where you come in',
      reviewLoop: 'Not right yet → the system revises and shows you again.',
      generate: { title: 'The rules the build must meet are written', sub: 'Generated straight from the flow and data you approved — testable and unambiguous.' },
      gateQ: 'All three approved?',
      gateNote: 'Flow · Mock Data · Mockups',
      gateLoop: 'Not yet → it stays with you.',
      end: 'Approved — the build starts automatically'
    },

    needsGraph: {
      start: 'A new request or acceptance criterion',
      decisions: [
        {
          q: 'A journey across several screens or steps?',
          yesLabel: 'yes ↳',
          noLabel: 'no',
          outcome: {
            tone: 'trio', title: 'Draft the full set',
            artifacts: ['Flow', 'Mock Data', 'Mockups'],
            sub: 'A guided journey — every screen gets a mockup, all sharing one dataset.',
            handoff: 'built by frontend-coder, screen by screen'
          }
        },
        {
          q: 'A single screen or UI component?',
          yesLabel: 'yes ↳',
          noLabel: 'no',
          outcome: {
            tone: 'ui', title: 'Draft a Mockup + Mock Data',
            artifacts: ['Mock Data', 'Mockup'],
            sub: 'One screen, built to match the approved mockup and filled with the sample data.',
            handoff: 'built by frontend-coder'
          }
        },
        {
          q: 'Does it read or write real business data?',
          yesLabel: 'yes ↳',
          noLabel: 'no',
          outcome: {
            tone: 'data', title: 'Draft Mock Data only',
            artifacts: ['Mock Data'],
            sub: 'No screen, but real records — the sample data becomes the test fixtures.',
            handoff: 'built by python-coder / sql-coder · test-writer reuses the fixtures'
          }
        }
      ],
      terminal: {
        tone: 'none', title: 'No mocks needed',
        sub: 'Logic, config, or docs — straight to the behaviour rules and tests.',
        handoff: 'built by python-coder · documented as usual'
      }
    },

    flow: {
      name: 'Customer buys a plant',
      product: 'Fern & Fig',
      steps: [
        { id: 'browse', label: 'Browse plants', order: 1 },
        { id: 'detail', label: 'Plant detail', order: 2 },
        { id: 'cart', label: 'Add to cart', order: 3 },
        { id: 'checkout', label: 'Checkout', order: 4 },
        { id: 'confirmed', label: 'Order confirmed', order: 5 }
      ],
      branch: { id: 'notify', label: 'Notify me', fromStep: 'detail', condition: 'out of stock' },
      reviewState: 'in-review'
    },

    mockData: {
      plants: [
        { name: 'Monstera Deliciosa', price: 34, currency: '€', stock: 12, status: 'in-stock', statusLabel: 'In Stock' },
        { name: 'Fiddle-leaf Fig', price: 59, currency: '€', stock: 3, status: 'low-stock', statusLabel: 'Low Stock' },
        { name: 'Snake Plant', price: 22, currency: '€', stock: 0, status: 'out-of-stock', statusLabel: 'Out of Stock' }
      ],
      customers: [
        { name: 'Alex Green', email: 'alex@fernfig.shop', orders: 3 }
      ],
      orders: [
        { id: '1042', customer: 'Alex Green', item: 'Monstera Deliciosa', qty: 1, total: 34, currency: '€', status: 'paid' }
      ]
    },

    mockups: [
      { id: 'listing', title: 'Plant Listing', reviewState: 'approved' },
      { id: 'detail', title: 'Plant Detail', reviewState: 'in-review' },
      { id: 'checkout', title: 'Checkout', reviewState: 'changes-requested' }
    ],

    reviewStates: [
      { state: 'draft', label: 'Draft', description: 'Created, not yet submitted' },
      { state: 'in-review', label: 'In Review', description: 'Waiting on Product Owner' },
      { state: 'approved', label: 'Approved', description: 'PO approved — gates the build' },
      { state: 'changes-requested', label: 'Changes Requested', description: 'PO requests revisions' }
    ]
  }
};
