/* leafcutter flow-site render engine — vanilla JS, zero dependencies.
   Reads window.LEAFCUTTER_DATA and renders both views into index.html.
   A later step can swap the in-page data object for fetched JSON without
   touching this render logic. */
(function () {
  'use strict';

  var D = window.LEAFCUTTER_DATA || {};

  /* ── helpers ──────────────────────────────────────────────────────── */
  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
  var reduceMotion = window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  var CHIP_FOR_COLOR = {
    leaf: 'chip-leaf', soil: 'chip-soil', amber: 'chip-amber',
    terracotta: 'chip-terra', ink: 'chip-ink', sage: 'chip-sage'
  };

  function stateChip(state) {
    var map = {
      'approved': ['chip-approved', 'Approved', '✓'],
      'in-review': ['chip-review', 'In Review', '◷'],
      'changes-requested': ['chip-changes', 'Changes requested', '↩'],
      'draft': ['chip-sage', 'Draft', '○']
    };
    var m = map[state] || ['chip-sage', state, '•'];
    return '<span class="chip ' + m[0] + '"><span aria-hidden="true">' + m[2] +
      '</span> ' + esc(m[1]) + '</span>';
  }

  function stockChip(status, label) {
    var cls = status === 'in-stock' ? 'chip-leaf'
      : status === 'low-stock' ? 'chip-amber' : 'chip-terra';
    return '<span class="chip ' + cls + '">' + esc(label) + '</span>';
  }

  /* dashed "ant-trail" connector between horizontal cards */
  function trailH(color) {
    var arrow = color === 'flow' ? '#4E7A3E' : '#4E7A3E';
    var line = '#C8D4B8';
    return '<div class="' + (color === 'flow' ? 'flow-connector-h' : 'trail-connector-h') +
      '" aria-hidden="true">' +
      '<svg viewBox="0 0 48 32" width="48" height="32" role="presentation" focusable="false">' +
      '<path d="M2 16 C 16 6, 32 26, 44 16" fill="none" stroke="' + line +
      '" stroke-width="2" stroke-dasharray="3 4" stroke-linecap="round"/>' +
      '<path d="M40 11 L46 16 L40 21" fill="none" stroke="' + arrow +
      '" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>' +
      '<ellipse cx="23" cy="15" rx="3.2" ry="2" fill="#8FBF6B" transform="rotate(-20 23 15)"/>' +
      '</svg></div>';
  }

  function section(eyebrow, title, lead, inner) {
    return '<section class="section">' +
      '<span class="eyebrow">' + esc(eyebrow) + '</span>' +
      '<h2 class="section-title">' + esc(title) + '</h2>' +
      (lead ? '<p class="section-lead">' + lead + '</p>' : '') +
      inner + '</section>';
  }

  /* ── TODAY VIEW ───────────────────────────────────────────────────── */
  function renderToday() {
    var html = '';

    /* Hero */
    html += '<section class="hero">' +
      '<h1 class="hero-title">A portable, self-hosting ' +
      '<em>agentic delivery pipeline</em>.</h1>' +
      '<p class="hero-lead">leafcutter turns a plain-language intent into merged, ' +
      'reviewed code — through a chain of slash commands, a supervisor loop, ' +
      'specialised phase agents, and mechanical gates. The ' +
      '<strong>acceptance-criteria store is the authoritative backlog</strong>; ' +
      'tickets are derived from it, never authored directly.</p></section>';

    /* 1 — Pipeline */
    var stages = D.pipelineStages || [];
    var flow = '<div class="pipeline-flow">';
    stages.forEach(function (s, i) {
      flow += '<div class="stage-card">' +
        '<div class="stage-num">STAGE ' + esc(s.num) + '</div>' +
        '<div class="stage-name">' + esc(s.stage) + '</div>' +
        '<span class="stage-cmd">' + esc(s.command) + '</span>' +
        '<div class="stage-row"><span class="stage-label">In</span>' +
        '<span class="stage-val">' + esc(s.inputs) + '</span></div>' +
        '<div class="stage-row"><span class="stage-label">Out</span>' +
        '<span class="stage-val">' + esc(s.outputs) + '</span></div>' +
        '<div class="stage-row"><span class="stage-label">Gate</span>' +
        '<span class="stage-val">' + esc(s.gate) + '</span></div>' +
        '</div>';
      if (i < stages.length - 1) flow += trailH();
    });
    flow += '</div>';
    if (D.quickFix) {
      flow += '<div class="quickfix-lane">' +
        '<span class="quickfix-badge">' + esc(D.quickFix.command) + '</span>' +
        '<span class="quickfix-desc">' + esc(D.quickFix.description) + '</span></div>';
    }
    html += section('The pipeline', 'Four stages, idea to shipped',
      'Each stage has one driver command, explicit inputs and outputs, and a gate that must pass before the next begins. <code>/quick-fix</code> is a fast lane for single-file bug fixes.',
      flow);

    /* 2 — AC store */
    var fl = '<div class="table-wrap"><table><thead><tr>' +
      '<th>Level</th><th>Meaning</th><th>Author</th><th>Type</th></tr></thead><tbody>';
    (D.flightLevels || []).forEach(function (l) {
      fl += '<tr><td><strong>' + esc(l.level) + '</strong></td><td>' + esc(l.meaning) +
        '</td><td><span class="agent-tag">' + esc(l.agent) + '</span></td><td>' +
        esc(l.type) + '</td></tr>';
    });
    fl += '</tbody></table></div>';

    var rd = '<div class="readiness-row">';
    (D.readiness || []).forEach(function (r, i) {
      rd += '<div class="readiness-item">' +
        '<span class="chip ' + (r.pickedUp ? 'chip-approved' : 'chip-sage') + '">' +
        esc(r.state) + (r.pickedUp ? ' ✓' : '') + '</span>' +
        '<span class="readiness-label">' + esc(r.description) + '</span></div>';
      if (i < (D.readiness.length - 1)) rd += '<span class="readiness-arrow">→</span>';
    });
    rd += '</div>';

    var comps = '<div class="family-agents" style="margin:1rem 0;">';
    (D.acComponents || []).forEach(function (c) {
      comps += '<span class="chip chip-sage">' + esc(c) + '</span>';
    });
    comps += '</div>';

    var yaml = '<div class="code-card"><pre>' + esc(D.acYamlSnippet) + '</pre></div>';

    html += section('The acceptance-criteria store',
      'Flight levels & the readiness ladder',
      'The AC store is the canonical backlog. Product Owner authors intent (L0/L1); Business Analyst decomposes it into testable behaviour (L2/L3); IT-PO adds technical enrichment. Only <code>approved</code> ACs are picked up for build.',
      fl +
      '<h3 class="card-title" style="margin-top:1.5rem;">Readiness lifecycle</h3>' + rd +
      '<h3 class="card-title" style="margin-top:1.5rem;">Component namespaces</h3>' + comps +
      '<h3 class="card-title" style="margin-top:1.5rem;">A real AC record</h3>' + yaml);

    /* 3 — Agents & supervisor */
    var depth = '<div class="depth-tree">';
    (D.depthModel || []).forEach(function (d) {
      depth += '<div class="depth-line depth-' + d.depth + '" style="padding-left:' +
        (d.indent * 1.4) + 'rem;">' +
        '<span class="depth-badge">D' + d.depth + '</span>' +
        '<span class="depth-text">' + esc(d.label) + '</span>' +
        '<span class="depth-note">' + esc(d.note) + '</span></div>';
    });
    depth += '</div>';

    var po = '<div class="table-wrap"><table><thead><tr>' +
      '<th>Priority</th><th>Agent</th><th>Group</th><th></th></tr></thead><tbody>';
    (D.phaseOrder || []).forEach(function (p) {
      po += '<tr class="' + (p.highlight ? 'phase-highlight' : '') + '">' +
        '<td>' + esc(p.priority) + '</td>' +
        '<td><span class="agent-tag">' + esc(p.agent) + '</span></td>' +
        '<td><span class="chip chip-sage">' + esc(p.group) + '</span></td>' +
        '<td>' + (p.note ? esc(p.note) : '') + '</td></tr>';
    });
    po += '</tbody></table></div>';

    var fam = '<div class="family-grid">';
    (D.agentFamilies || []).forEach(function (f) {
      var tags = '';
      (f.agents || []).forEach(function (a) {
        tags += '<span class="agent-tag">' + esc(a) + '</span>';
      });
      fam += '<div class="family-card">' +
        '<div class="family-name">' +
        '<span class="chip ' + (CHIP_FOR_COLOR[f.color] || 'chip-sage') +
        '" style="margin-right:.4rem;">&nbsp;</span>' + esc(f.family) + '</div>' +
        '<div class="family-agents">' + tags + '</div></div>';
    });
    fam += '</div>';

    html += section('Agents & the supervisor model',
      'One depth-0 supervisor, phase agents at depth 1',
      'Claude Code enforces a hard depth-1 limit on agent nesting (ADR-006). The <code>ticket-supervisor</code> runs as the depth-0 context and dispatches each phase agent in a fixed priority order — test-writer first (TDD), commit and PR last.',
      depth +
      '<h3 class="card-title" style="margin-top:1.5rem;">Canonical phase ordering</h3>' + po +
      '<h3 class="card-title" style="margin-top:1.5rem;">The roster, by family</h3>' + fam);

    /* 4 — Tickets, epics & worktrees */
    var life = '<div class="lifecycle-flow">';
    var lc = D.ticketLifecycle || [];
    lc.forEach(function (t, i) {
      life += '<div class="lifecycle-card">' +
        '<div class="lifecycle-folder">' + esc(t.folder) + '</div>' +
        '<div class="lifecycle-label">' + esc(t.label) + '</div>' +
        '<div class="lifecycle-desc">' + esc(t.description) + '</div></div>';
      if (i < lc.length - 1) life += '<span class="lifecycle-arrow" aria-hidden="true">→</span>';
    });
    life += '</div>';
    var tf = '<div class="code-card"><pre>' + esc(D.ticketFrontmatterSnippet) + '</pre></div>';

    html += section('Tickets, epics & worktrees',
      'Status is the signal; the worktree is the workspace',
      'A ticket\'s <code>status</code> frontmatter — not its folder — is the authoritative lifecycle signal. Every epic runs in one isolated git worktree branched off <code>origin/main</code>, shared across its tickets and one PR.',
      life +
      '<h3 class="card-title" style="margin-top:1.5rem;">A real ticket\'s frontmatter</h3>' + tf);

    /* 5 — Gates */
    var g = '<div class="gates-grid">';
    (D.gates || []).forEach(function (gate) {
      g += '<div class="gate-card">' +
        '<div class="gate-name">' + esc(gate.name) + '</div>' +
        '<div class="gate-desc">' + esc(gate.description) + '</div></div>';
    });
    g += '</div>';
    html += section('The gates',
      'Nothing ships unreviewed',
      'Quality is enforced mechanically, not by good intentions: three-place sign-off parity, test-first TDD, a large pre-commit "commit guardian" manifest, a PR-only <code>main</code> behind a required Ruff check, and a finalize workflow that HALTs on merge conflict or test regression.',
      g);

    /* 6 — Package model */
    var pm = D.packageModel || {};
    var pmItems = [
      ['Build script', pm.buildScript, true],
      ['Output root', pm.outputRoot, false],
      ['Platforms', pm.platforms, false],
      ['Adopter config', pm.config, false],
      ['Self-hosting', pm.selfHosting, true],
      ['Roadmap phase', pm.roadmapPhase, false]
    ];
    var pkg = '<div class="package-grid">';
    pmItems.forEach(function (it) {
      pkg += '<div class="package-item"><div class="package-label">' + esc(it[0]) +
        '</div><div class="package-value ' + (it[2] ? '' : 'plain') + '">' +
        esc(it[1]) + '</div></div>';
    });
    pkg += '</div>';
    var exit = '';
    if (pm.roadmapOutcome) {
      exit += '<div class="card" style="margin-top:1.25rem;">' +
        '<div class="card-title">Current outcome — ' + esc(pm.roadmapPhase) + '</div>' +
        '<div class="card-body">' + esc(pm.roadmapOutcome) + '</div>';
      if (pm.exitCriteria) {
        exit += '<ul class="exit-criteria">';
        pm.exitCriteria.forEach(function (c) { exit += '<li>' + esc(c) + '</li>'; });
        exit += '</ul>';
      }
      exit += '</div>';
    }
    html += section('The package model',
      'One build.py, deployed into any project',
      'leafcutter compiles its <code>templates/</code> tree into a target project\'s <code>.leafcutter</code> (bridged to <code>.claude</code> via shims), driven by a per-adopter <code>skills_config.json</code>. It builds itself the same way.',
      pkg + exit);

    /* 7 — Happy path */
    var hp = '<div class="journey-trail">';
    (D.happyPath || []).forEach(function (h) {
      hp += '<div class="journey-item">' +
        '<span class="journey-step">' + esc(h.step) + '</span>' +
        '<div class="journey-actor">' + esc(h.actor) + '</div>' +
        '<div class="journey-text">' + esc(h.text) + '</div></div>';
    });
    hp += '</div>';
    html += section('The happy path',
      'One intent, fourteen steps, all the way down',
      'The full journey a feature travels — from a plain-language request to an archived epic and its retrospective.',
      hp);

    return html;
  }

  /* ── FUTURE VIEW ──────────────────────────────────────────────────── */
  function renderFuture() {
    var F = D.future || {};
    var html = '';

    html += '<div class="vision-badge"><span aria-hidden="true">◆</span> Vision preview</div>';
    html += '<section class="hero">' +
      '<h1 class="hero-title">' + esc(F.thesis) + '</h1>' +
      '<p class="future-tagline">' + esc(F.tagline) + '</p></section>';

    /* Cockpit — three surfaces */
    var cg = '<div class="cockpit-grid">';
    (F.surfaces || []).forEach(function (s) {
      var used = '';
      (s.consumedBy || []).forEach(function (u) {
        used += '<li style="font-size:.82rem;color:var(--ink-mid);padding:.2rem 0 .2rem 1.1rem;position:relative;">' +
          '<span style="position:absolute;left:0;color:var(--leaf);">↳</span>' + esc(u) + '</li>';
      });
      cg += '<div class="card">' +
        '<div class="card-title">' + esc(s.label) + '</div>' +
        '<div class="card-body">' + esc(s.description) + '</div>' +
        '<div class="mock-used-by"><span class="chip chip-leaf">consumed by agents</span></div>' +
        '<ul style="list-style:none;margin-top:.6rem;">' + used + '</ul></div>';
    });
    cg += '</div>';
    html += section('The Product Owner cockpit',
      'Three surfaces you review — before any code',
      'Today the PO approves behaviour they can\'t see. Tomorrow they review three concrete artifacts: the journeys, the data, and the screens. Each is real JSON the agents consume — always rendered as a picture for the human.',
      cg);

    /* Under the hood — decision flow that produces the ACs */
    html += section('Under the hood',
      'You say it once. Here is what happens next.',
      'Everything in <span style="color:var(--leaf-deep);font-weight:700;">green is you</span>; everything in muted tones the system does on its own. Diamonds are decisions — follow the labelled branch to see where each one leads. You only act twice: say what you want, and approve what comes back.',
      renderAcFlow(F));

    /* The bridge — what artifacts a given request actually needs */
    html += section('The bridge',
      'What does a request actually need?',
      'This is where the future mocks meet today’s pipeline. Not every request needs all three artifacts — the system decides <em>per request</em> which to draft, then hands the result to the same agents, tickets and build you saw in “How it works today.”',
      renderNeedsGraph(F));

    /* Flow diagram */
    var fl = F.flow || {};
    var steps = fl.steps || [];
    var fd = '<div class="flow-diagram"><div class="flow-steps">';
    steps.forEach(function (st, i) {
      fd += '<div class="flow-step-wrap"><div class="flow-node">' +
        '<span class="flow-num">STEP ' + esc(st.order) + '</span>' + esc(st.label) + '</div>';
      if (fl.branch && fl.branch.fromStep === st.id) {
        fd += '<div class="flow-branch-wrap">' +
          '<div class="flow-branch-edge"></div>' +
          '<div class="flow-branch-label">' + esc(fl.branch.condition) + '</div>' +
          '<div class="flow-branch-node">' + esc(fl.branch.label) + '</div></div>';
      }
      fd += '</div>';
      if (i < steps.length - 1) fd += trailH('flow');
    });
    fd += '</div></div>';
    html += section('Flow · ' + (fl.product || ''),
      fl.name || 'Journey',
      'The Product Owner reviews the journey itself — "is this how it should go?" — before a single acceptance criterion exists. ' +
      stateChip(fl.reviewState),
      fd);

    /* Mock data */
    var md = F.mockData || {};
    var tabs = [
      ['plants', 'Plants', ['Name', 'Price', 'Stock', 'State'], (md.plants || []).map(function (p) {
        return '<td><strong>' + esc(p.name) + '</strong></td><td>' + esc(p.currency + p.price) +
          '</td><td>' + esc(p.stock) + '</td><td>' + stockChip(p.status, p.statusLabel) + '</td>';
      })],
      ['customers', 'Customers', ['Name', 'Email', 'Orders'], (md.customers || []).map(function (c) {
        return '<td><strong>' + esc(c.name) + '</strong></td><td>' + esc(c.email) +
          '</td><td>' + esc(c.orders) + '</td>';
      })],
      ['orders', 'Orders', ['Order', 'Customer', 'Item', 'Total', 'State'], (md.orders || []).map(function (o) {
        return '<td>#' + esc(o.id) + '</td><td>' + esc(o.customer) + '</td><td>' + esc(o.item) +
          ' ×' + esc(o.qty) + '</td><td>' + esc(o.currency + o.total) +
          '</td><td><span class="chip chip-leaf">' + esc(o.status) + '</span></td>';
      })]
    ];
    var mdBtns = '<div class="mockdata-tabs" role="tablist">';
    var mdPanels = '';
    tabs.forEach(function (t, i) {
      mdBtns += '<button class="mockdata-tab-btn' + (i === 0 ? ' active' : '') +
        '" role="tab" data-mdtab="' + t[0] + '" aria-selected="' + (i === 0) + '">' +
        esc(t[1]) + '</button>';
      var head = '<tr>';
      t[2].forEach(function (h) { head += '<th>' + esc(h) + '</th>'; });
      head += '</tr>';
      var rows = '';
      t[3].forEach(function (r) { rows += '<tr>' + r + '</tr>'; });
      mdPanels += '<div class="mockdata-panel" data-mdpanel="' + t[0] + '"' +
        (i === 0 ? '' : ' hidden') + '>' +
        '<div class="table-wrap"><table><thead>' + head + '</thead><tbody>' + rows +
        '</tbody></table></div></div>';
    });
    mdBtns += '</div>';
    html += section('Mock data · the baseline business truth',
      'One dataset. Two jobs.',
      'The canonical sample records the product cannot exist without. The same data populates the mockups <em>and</em> seeds the test fixtures — so tests run against exactly what the PO reviewed. ' +
      '<span class="mock-used-by" style="display:inline-flex;"><span class="chip chip-leaf">used by: mockup · tests</span><span class="chip chip-sage">viewed as a table · stored as JSON</span></span>',
      mdBtns + mdPanels);

    /* Mockups */
    var mk = '<div class="mockups-row">';
    (F.mockups || []).forEach(function (m) {
      mk += '<div class="mockup-wrap">' +
        '<div class="mockup-state-chip">' + stateChip(m.reviewState) + '</div>' +
        '<div class="browser-frame">' +
        '<div class="browser-chrome"><span class="browser-dot"></span>' +
        '<span class="browser-dot"></span><span class="browser-dot"></span>' +
        '<span class="browser-title">' + esc(m.title) + '</span></div>' +
        '<div class="browser-body">' + mockupBody(m.id, md) + '</div></div></div>';
    });
    mk += '</div>';
    html += section('Mockups · the screens, shown',
      'What the customer will actually see',
      'Low-fidelity but real: each screen is populated with the approved mock data and carries a review state. Approve it, and it becomes the frontend-coder\'s visual acceptance target.',
      mk);

    /* Review loop */
    var rs = '<div class="review-states">';
    var order = ['draft', 'in-review', 'approved', 'changes-requested'];
    order.forEach(function (s, i) {
      rs += stateChip(s);
      if (i === 1) rs += '<span class="review-arrow">→</span>';
      else if (i === 2) rs += '<span class="review-arrow">/</span>';
      else if (i === 0) rs += '<span class="review-arrow">→</span>';
    });
    rs += '</div>';
    var loop = rs +
      '<div class="po-inbox"><div class="po-inbox-title">Waiting on you</div>' +
      '<div class="po-inbox-desc">2 artifacts need your review: the <strong>Plant Detail</strong> mockup (In Review) and the <strong>Customer buys a plant</strong> flow (In Review).</div></div>' +
      '<div class="gate-band"><span class="gate-band-icon" aria-hidden="true">🔒</span>' +
      '<span class="gate-band-text"><strong>Approval gates the build.</strong> A ticket cannot enter <code>/build-feature</code> until its Flow, Mock Data, and Mockup are all Approved. Business truth first — code second. Everything downstream (the AC store, tickets, worktrees, and quality gates from the “today” view) stays exactly as it is; this layer sits in front of it.</span></div>';
    html += section('The review loop',
      'You are a true Product Owner',
      'You don\'t write code — you review and approve business truth. Every artifact moves through the same legible states, and your approval is what unlocks the pipeline.',
      loop);

    return html;
  }

  /* decision flowchart — how the system turns your words into ACs.
     Every node is colour-coded by actor: YOU vs the SYSTEM. */
  function renderAcFlow(F) {
    var P = F.acPipeline || {};

    function actorTag(a) {
      return '<span class="fc-actor fc-actor-' + a + '">' +
        (a === 'you' ? 'YOU' : 'SYSTEM') + '</span>';
    }
    function link(branch) {
      return '<div class="fc-link">' +
        (branch ? '<span class="fc-branch">' + esc(branch) + '</span>' : '') +
        '<div class="fc-arrow"></div></div>';
    }
    function pnode(actor, title, sub, extra) {
      return '<div class="fc-node fc-process' + (actor === 'you' ? ' fc-you' : '') + '">' +
        actorTag(actor) +
        '<div class="fc-title">' + esc(title) + '</div>' +
        (sub ? '<div class="fc-sub">' + esc(sub) + '</div>' : '') +
        (extra || '') + '</div>';
    }
    function diamond(q, actor, note) {
      return '<div class="fc-diamond-block">' +
        '<div class="fc-diamond-outer' + (actor === 'you' ? ' fc-dyou' : '') + '">' +
        '<div class="fc-diamond-inner"><span>' + esc(q) + '</span></div></div>' +
        (note ? '<span class="fc-you-note">' + esc(note) + '</span>' : '') + '</div>';
    }
    function offshoot(label, text) {
      return '<div class="fc-offshoot"><span class="fc-branch-alt">' + esc(label) +
        '</span><div class="fc-node fc-terminal-muted">' + esc(text) + '</div></div>';
    }

    var legend = '<div class="fc-legend">' +
      '<span class="fc-legend-item"><span class="fc-swatch fc-sw-you"></span>You decide / act</span>' +
      '<span class="fc-legend-item"><span class="fc-swatch fc-sw-system"></span>The system does it automatically</span>' +
      '<span class="fc-legend-item"><span class="fc-di fc-di-system"></span>Amber diamond = the system decides</span>' +
      '<span class="fc-legend-item"><span class="fc-di fc-di-you"></span>Green diamond = you decide</span></div>';

    var speech = '<div class="fc-speech">' + actorTag('you') +
      '<p class="fc-speech-text">' + esc(P.youSay) + '</p>' +
      '<span class="fc-speech-note">' + esc(P.youSayNote) + '</span></div>';

    var split = '<div class="fc-split">';
    (P.authors || []).forEach(function (a) {
      split += '<div class="fc-col"><span class="fc-branch">' + esc(a.branch) + '</span>' +
        '<div class="fc-mini-arrow"></div>' +
        pnode('system', a.node, a.sub) +
        '</div>';
    });
    split += '</div>';

    var draft = P.draft || {};
    var artifacts = '<div class="fc-artifacts">' +
      (draft.artifacts || []).map(function (x) {
        return '<span class="fc-artifact">' + esc(x) + '</span>';
      }).join('') + '</div>';

    return legend + '<div class="fc">' +
      speech + link() +
      pnode('system', P.triage.title, P.triage.sub) + link() +
      diamond(P.existsQ, 'system') + offshoot('yes ↳', P.coveredEnd) + link('no') +
      diamond(P.kindQ, 'system') + link() + split + link() +
      pnode('system', draft.title, draft.sub, artifacts) + link() +
      diamond(P.reviewQ, 'you', P.reviewNote) + offshoot('changes ↩', P.reviewLoop) + link('approved') +
      pnode('system', P.generate.title, P.generate.sub) + link() +
      diamond(P.gateQ, 'you', P.gateNote) + offshoot('no ↩', P.gateLoop) + link('yes') +
      '<div class="fc-node fc-end">' + esc(P.end) + '</div>' +
      '</div>';
  }

  /* decision graph — what artifacts (Flow / Mock Data / Mockup) a request needs */
  function renderNeedsGraph(F) {
    var N = F.needsGraph || {};
    function link(branch) {
      return '<div class="fc-link">' +
        (branch ? '<span class="fc-branch">' + esc(branch) + '</span>' : '') +
        '<div class="fc-arrow"></div></div>';
    }
    function diamond(q) {
      return '<div class="fc-diamond-block"><div class="fc-diamond-outer">' +
        '<div class="fc-diamond-inner"><span>' + esc(q) + '</span></div></div></div>';
    }
    function outcome(o) {
      var chips = (o.artifacts || []).map(function (a) {
        return '<span class="fc-artifact">' + esc(a) + '</span>';
      }).join('');
      return '<div class="fc-outcome ' + (o.tone || '') + '">' +
        '<div class="fc-outcome-title">' + esc(o.title) + '</div>' +
        (chips ? '<div class="fc-artifacts">' + chips + '</div>'
               : '<div class="fc-none-tag">no mocks</div>') +
        (o.sub ? '<div class="fc-sub">' + esc(o.sub) + '</div>' : '') +
        (o.handoff ? '<span class="fc-handoff">' + esc(o.handoff) + '</span>' : '') +
        '</div>';
    }
    function branchOut(label, o) {
      return '<div class="fc-offshoot fc-offshoot-wide"><span class="fc-branch-alt">' +
        esc(label) + '</span>' + outcome(o) + '</div>';
    }

    var legend = '<div class="fc-legend">' +
      '<span class="fc-legend-item"><span class="fc-di fc-di-system"></span>a decision the system makes</span>' +
      '<span class="fc-legend-item"><span class="fc-artifact">chip</span> = an artifact it drafts</span></div>';

    var body = '<div class="fc">' +
      '<div class="fc-node fc-process"><div class="fc-title">' + esc(N.start) + '</div></div>' + link();
    (N.decisions || []).forEach(function (d) {
      body += diamond(d.q) + branchOut(d.yesLabel, d.outcome) + link(d.noLabel);
    });
    body += outcome(N.terminal) + '</div>';
    return legend + body;
  }

  function mockupBody(id, md) {
    var plants = (md && md.plants) || [];
    if (id === 'listing') {
      var cards = '';
      plants.forEach(function (p) {
        cards += '<div class="plant-card-mini"><div class="plant-photo"></div>' +
          '<div class="plant-name-mini">' + esc(p.name) + '</div>' +
          '<div class="plant-price-mini">' + esc(p.currency + p.price) + '</div>' +
          stockChip(p.status, p.statusLabel) + '</div>';
      });
      return '<div class="mockup-nav"><span>Fern &amp; Fig</span><span>🛒 Cart</span></div>' +
        '<div class="plant-grid">' + cards + '</div>';
    }
    if (id === 'detail') {
      var p0 = plants[0] || {};
      return '<div class="detail-photo">' + esc(p0.name || 'plant') + '</div>' +
        '<div class="detail-title">' + esc(p0.name) + '</div>' +
        '<div class="detail-price">' + esc((p0.currency || '') + (p0.price || '')) + '</div>' +
        stockChip(p0.status, p0.statusLabel) +
        '<button class="btn-add" type="button" tabindex="-1" aria-hidden="true">Add to cart</button>';
    }
    if (id === 'checkout') {
      var order = (md.orders && md.orders[0]) || {};
      return '<div class="checkout-row"><span>' + esc(order.item) + ' ×' + esc(order.qty) +
        '</span><span>' + esc((order.currency || '') + (order.total || '')) + '</span></div>' +
        '<div class="checkout-row checkout-total"><span>Total</span><span>' +
        esc((order.currency || '') + (order.total || '')) + '</span></div>' +
        '<div class="checkout-field">Ship to: ' + esc(order.customer) + '</div>' +
        '<button class="btn-pay" type="button" tabindex="-1" aria-hidden="true">Pay now</button>';
    }
    return '';
  }

  /* ── mock-data tab interactions ───────────────────────────────────── */
  function initMockDataTabs(root) {
    var btns = root.querySelectorAll('.mockdata-tab-btn');
    btns.forEach(function (btn) {
      btn.addEventListener('click', function () {
        var key = btn.getAttribute('data-mdtab');
        btns.forEach(function (b) {
          var on = b === btn;
          b.classList.toggle('active', on);
          b.setAttribute('aria-selected', on ? 'true' : 'false');
        });
        root.querySelectorAll('.mockdata-panel').forEach(function (p) {
          p.hidden = p.getAttribute('data-mdpanel') !== key;
        });
      });
    });
  }

  /* ── view toggle ──────────────────────────────────────────────────── */
  function initToggle() {
    var btnToday = document.getElementById('btn-today');
    var btnFuture = document.getElementById('btn-future');
    var viewToday = document.getElementById('view-today');
    var viewFuture = document.getElementById('view-future');
    var indicator = document.getElementById('toggle-indicator');
    if (!btnToday || !btnFuture) return;

    function moveIndicator(btn) {
      if (!indicator) return;
      indicator.style.left = btn.offsetLeft + 'px';
      indicator.style.width = btn.offsetWidth + 'px';
    }

    function setView(view, focus) {
      var isToday = view === 'today';
      btnToday.setAttribute('aria-pressed', isToday ? 'true' : 'false');
      btnFuture.setAttribute('aria-pressed', isToday ? 'false' : 'true');
      viewToday.classList.toggle('is-hidden', !isToday);
      viewFuture.classList.toggle('is-hidden', isToday);
      var active = isToday ? viewToday : viewFuture;
      if (!reduceMotion) {
        active.classList.remove('view-enter');
        /* force reflow so the animation restarts */
        void active.offsetWidth;
        active.classList.add('view-enter');
      }
      moveIndicator(isToday ? btnToday : btnFuture);
      try { localStorage.setItem('leafcutter-view', view); } catch (e) { /* ignore */ }
      if (focus) window.scrollTo({ top: 0, behavior: reduceMotion ? 'auto' : 'smooth' });
    }

    btnToday.addEventListener('click', function () { setView('today', true); });
    btnFuture.addEventListener('click', function () { setView('future', true); });

    var saved = 'today';
    try { saved = localStorage.getItem('leafcutter-view') || 'today'; } catch (e) { /* ignore */ }
    setView(saved, false);
    /* position indicator once layout is settled */
    requestAnimationFrame(function () {
      moveIndicator(saved === 'today' ? btnToday : btnFuture);
    });
    window.addEventListener('resize', function () {
      moveIndicator(btnToday.getAttribute('aria-pressed') === 'true' ? btnToday : btnFuture);
    });
  }

  /* ── boot ─────────────────────────────────────────────────────────── */
  /* Note: entrance motion is handled by the `.view-enter` cross-fade in
     setView(). We deliberately do NOT hide sections behind a scroll
     observer — on an informational page content must never depend on
     scrolling (or a firing observer) to become visible. */
  function boot() {
    var today = document.getElementById('view-today');
    var future = document.getElementById('view-future');
    if (today) today.innerHTML = renderToday();
    if (future) future.innerHTML = renderFuture();
    if (future) initMockDataTabs(future);
    initToggle();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
