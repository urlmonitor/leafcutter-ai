# Leafcutter — Future State Vision Brief (Product-Owner Cockpit)

> This is a **visionary mockup brief**. It illustrates the *experience and feel* of
> where we want leafcutter to go. It is intentionally NOT a schema/mechanics spec —
> render the vision, don't over-specify the plumbing.

## The thesis: baseline business information

Every website, app, or product rests on a small set of **business truths** it cannot
function without:

- **The things that exist** — the entities and the real sample records (a product, a
  customer, an order; an account, a message, an invoice).
- **The journeys people take** — the flows that move a person from intent to outcome.
- **The screens they see** — the interface where those journeys happen.

Today, leafcutter's Product Owner reviews these truths only *abstractly* — as
Gherkin text inside AC YAML files (`Given/When/Then`), and by setting `readiness` and
`priority`. There is no picture, no sample dataset, no journey map to sign off on. The
PO is asked to approve behaviour they can't *see*.

**The future:** the PO reviews three concrete, visual, agent-consumed artifacts —
**Flows, Mock Data, and Mockups** — *before* code is written. They are real JSON that
agents actually consume, but they are always **rendered for the human** to review. This
is the new "business information" layer that grounds the existing plan → build → ship
pipeline in reviewable truth.

> One line to carry through the whole future view:
> **"Agents read the JSON. The Product Owner reviews the picture. They are the same artifact."**

---

## The Product Owner's three review surfaces

Present these as the heart of the future view — a **PO review cockpit** where the human
is a true product owner: they don't write code, they *review and approve business truth*.

### 1. Flows — the journeys, mapped
- A visual journey map: ordered steps with decision branches (happy path + edge cases).
- Each flow is linked to the acceptance criteria it will generate.
- The PO reviews the *journey itself* — "is this how it should go?" — before any AC or
  ticket exists.
- **Consumed by agents:** the business-analyst derives L2/L3 Gherkin ACs from the flow;
  frontend-coder knows which screens each step needs.

### 2. Mock Data — the baseline business truth
- The canonical sample dataset the product cannot exist without: the entities and a
  handful of real-feeling sample records.
- **One source of truth with two jobs:** it (a) populates the mockups so they look real,
  and (b) seeds the test fixtures so tests run against the same data the PO reviewed.
- The PO reviews the *shape and the sample values* — "are these the right things, with
  believable data?"
- **Consumed by agents:** frontend-coder renders mockups from it; test-writer builds
  fixtures from it. No more synthetic fixtures that hide bugs (a real leafcutter pain).

### 3. Mockups — the screens, shown
- Visual proposals for each screen in a flow, populated with the approved mock data.
- The PO reviews *look, feel, and layout* — approve, or request changes with a note.
- **Consumed by agents:** frontend-coder implements to match the approved mockup; the
  mockup becomes the visual acceptance target.

---

## The review loop (the feel to convey)

Every artifact moves through simple, legible states the PO controls:

`Draft` → `In Review` (waiting on the PO) → `Approved` ✓  /  `Changes requested` ↩

- The cockpit surfaces **"what's waiting on you"** — the PO's inbox of business decisions.
- **Approval gates the build:** a ticket cannot enter the existing `/build-feature`
  pipeline until its Flow, Mock Data, and Mockup are all `Approved`. Business truth first,
  code second.
- Nothing else about the downstream pipeline changes — same AC store, tickets, worktrees,
  and quality gates from the Current view. This new layer sits *in front* of it.

Show this as a small "before the pipeline" band that connects into the existing
plan → build → ship flow the Current view documents.

---

## Sample product to make it tangible: **"Fern & Fig" — a small plant shop**

To make the mockup/mock-data/flow trio instantly legible (and on-brand with our leaf
identity), the future view demonstrates the cockpit reviewing a friendly sample product:
an online plant shop. This shows the *universal* "baseline business information" idea on a
domain anyone understands.

**Sample FLOW — "Customer buys a plant":**
1. Browse plants  → 2. View a plant's detail  → 3. Add to cart  → 4. Checkout  →
5. Order confirmed. *(edge branch: out of stock → notify-me)*

**Sample MOCK DATA (the baseline business truth) — show as reviewable tables/cards:**
- `Plants`: e.g. *Monstera Deliciosa — €34, in stock 12*; *Fiddle-leaf Fig — €59, in
  stock 3*; *Snake Plant — €22, in stock 0 (out of stock)*.
- `Customers`: e.g. *Alex Green — alex@…, orders: 3*.
- `Orders`: e.g. *#1042 — Alex Green — Monstera ×1 — €34 — paid*.
- Tag each dataset with **"used by: mockup · tests"** to show the dual role.

**Sample MOCKUPS (screens, populated with the mock data above):**
- *Plant listing* (grid of plant cards with price + stock badge).
- *Plant detail* (photo, price, "Add to cart", stock state).
- *Checkout* (cart summary, customer, pay button).
- Each mockup shows a state chip: `Approved ✓` / `In Review` / `Changes requested`.

Keep the mockups as tasteful, low-fidelity rendered UI *inside* the page (HTML/CSS
"screens" framed like device/browser windows) — enough to feel real, clearly a proposal.

**The point the sample proves:** these three artifacts ARE the plant shop's baseline
business information. Approve them and the agents have everything they need — believable
data, the journey, and the target screens — to build and test the real thing.

---

## Automation note (design for it, don't build it yet)

Static for now, but structure the content so it can later be driven from real JSON:
render the current-pipeline data and the future sample (flows/data/mockups) from
in-page JS data objects, so a later step can swap them for fetched
`flows.json` / `mock-data.json` / `mockups.json`. Do not add a build step or external
dependencies — the page must open as a plain static file.
