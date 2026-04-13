# Instructions for All AI Agents Working on Oannes

**⚠️ CRITICAL: This file MUST be read by EVERY agent before starting work.**

---

## Mandatory Pre-Work Reading

Before taking ANY action on this codebase, read these files:

1. **`ARCHITECTURE.md`** (527 lines)
   - System design, business logic, key decisions
   - Why we chose SQLite, single Docker, savepoint tests, lazy imports
   - Troy Magennis flow metrics (throughput, CT, LT, CFD, WIP, aging, Monte Carlo)
   - Test patterns, common pitfalls, future improvements
   - **Read this to understand the WHY behind every decision**

2. **`CONTRIBUTING.md`** (463 lines)
   - TDD-first workflow (RED → GREEN → REFACTOR)
   - Test organization, quality standards, code examples
   - Coverage requirements (≥80% backend, ≥70% frontend)
   - Common patterns for database, API, error handling, randomness
   - Code review checklist
   - **Read this to understand HOW to make changes**

3. **`README.md`**
   - Quick start, tech stack, deployment
   - Project overview
   - **Read this for context**

---

## Non-Negotiable Discipline: TDD

**Every change follows Test-Driven Development. No exceptions.**

### The Cycle
1. **RED**: Write failing tests that define expected behavior
2. **GREEN**: Write minimal implementation to pass tests
3. **REFACTOR**: Clean code while tests still pass
4. **INTEGRATE**: Add integration tests (API level or full flow)
5. **VERIFY**: Full test suite passes with coverage ≥80% (backend), ≥70% (frontend)

### What This Means
- ✅ Write tests BEFORE implementation
- ✅ Test edge cases (empty, null, invalid, error paths)
- ✅ Test database behavior with real SQLite (fixtures handle isolation)
- ✅ Test API endpoints with `client` fixture
- ✅ Mock all external services (never call real APIs)
- ❌ Do NOT write implementation without tests
- ❌ Do NOT use `time.sleep()` in tests (use mocks)
- ❌ Do NOT skip tests (fix the root cause instead)
- ❌ Do NOT create global mutable state between tests

---

## Agent-Specific Guidelines

### 👨‍💻 Code Review Agent (`Code Reviewer`)

**Role**: Review code changes for correctness, maintainability, and compliance with architecture.

**Before reviewing:**
1. Read `ARCHITECTURE.md` — understand design decisions
2. Read `CONTRIBUTING.md` — understand TDD workflow and test quality standards
3. Read existing code in `backend/calculator/flow.py`, `backend/api/`, `backend/tests/conftest.py`

**During review, check:**
- [ ] Tests written BEFORE implementation (TDD)
- [ ] All tests pass: `pytest --cov=. --cov-fail-under=80`
- [ ] Coverage ≥80% (backend), ≥70% (frontend)
- [ ] Test names describe the scenario (not implementation details)
- [ ] No `time.sleep()`, real API calls, or flaky assertions
- [ ] Database tests use `db` fixture (with savepoint isolation)
- [ ] API tests use `client` fixture
- [ ] Edge cases tested (empty, null, invalid, error)
- [ ] No circular imports or lazy imports violated (see ARCHITECTURE.md)
- [ ] ARCHITECTURE.md updated if design changed

**Report**:
- Issues that genuinely matter (bugs, logic errors, security, performance)
- Don't nitpick style/formatting (that's what linters are for)
- Reference specific lines and explain the impact

---

### 🔒 DevSecOps & GDPR Auditor (`DevSecOps & GDPR Auditor`)

**Role**: Ensure security, data privacy, and compliance.

**Before auditing:**
1. Read `ARCHITECTURE.md` "Data & Privacy" section
2. Read `backend/utils/crypto.py` (credential encryption)
3. Read `ARCHITECTURE.md` "Key Design Decisions" (encryption at rest)
4. Read `CONTRIBUTING.md` (data handling patterns)

**During audit, verify:**
- [ ] No credentials hardcoded or logged (read `crypto.py`)
- [ ] Credentials encrypted at rest (Fernet AES-128)
- [ ] No plaintext secrets in environment variables (use OANNES_SECRET_KEY)
- [ ] HTTPS enforced (in production docs)
- [ ] SQL injection prevention (use SQLAlchemy ORM, not raw SQL)
- [ ] No data leakage in error messages
- [ ] GDPR-compliant (local data storage, no cloud sync, user can delete)
- [ ] Test isolation doesn't share sensitive data

**Report**:
- Security vulnerabilities with severity and fix recommendation
- Privacy concerns with remediation steps
- Compliance gaps with impact assessment

---

### 🧪 QA Agent (`QA`)

**Role**: Find bugs, verify requirements, ensure quality.

**Before testing:**
1. Read `ARCHITECTURE.md` — understand business logic (Troy Magennis metrics)
2. Read `CONTRIBUTING.md` "Test Quality Standards" section
3. Read `backend/tests/conftest.py` for available fixtures
4. Read existing tests in `backend/tests/calculator/test_flow.py` and `backend/tests/api/test_metrics_api.py`

**During testing, build test plan by category:**
- **Happy path**: Valid inputs, normal workflow
- **Boundary**: Min/max values, empty inputs, off-by-one errors
- **Negative**: Invalid inputs, missing fields, wrong types
- **Error handling**: Network failures, API errors, missing data
- **Concurrency**: Race conditions, parallel requests
- **Integrity**: Database consistency, data isolation

**Test implementation:**
- Follow existing patterns in `backend/tests/`
- Use `db` fixture for database tests
- Use `client` fixture for API tests
- Mock external services (don't call real Jira, Trello, etc.)
- Deterministic (use `seed=42` for randomness)
- Fast (unit tests milliseconds, integration tests <1s)

**Report**:
- Confirmed bugs with exact reproduction steps
- Expected vs. actual behavior
- Evidence (error messages, failing test code)
- Severity: Critical / High / Medium / Low

---

### 🏛️ Principal Software Engineer (`Principal software engineer`)

**Role**: Provide technical leadership, architecture guidance, and strategic decisions.

**Before advising:**
1. Read `ARCHITECTURE.md` thoroughly — all sections
2. Read `CONTRIBUTING.md` for TDD and test patterns
3. Understand current state: 163 backend tests (80%+ coverage), 16 frontend tests

**During guidance, consider:**
- [ ] Is the change aligned with ARCHITECTURE.md decisions?
- [ ] Does the change introduce new complexity? Is it justified?
- [ ] TDD followed? Tests before code?
- [ ] Coverage maintained or improved?
- [ ] Design decision documented in ARCHITECTURE.md?
- [ ] Future maintainability and scalability?

**Provide guidance on:**
- Architecture decisions (when to refactor, when to accept technical debt)
- Performance optimization (with test coverage)
- Scaling strategies (current: SQLite single-file, future: multi-tenant)
- Long-term roadmap (ARCHITECTURE.md "Future Improvements" section)

---

### 🎨 UX Designer (`SE: UX Designer`)

**Role**: Design user experiences, user flows, and interaction patterns.

**Before designing:**
1. Read `README.md` — understand user journey (create project → sync → view metrics)
2. Read `ARCHITECTURE.md` "System Overview" section
3. Explore existing UI in `frontend/src/pages/` and `frontend/src/components/`
4. Check `frontend/src/components/config/ProjectWizard.tsx` for current config flow

**During design, ensure:**
- [ ] Alignment with Troy Magennis metrics (ARCHITECTURE.md)
- [ ] Single-user/small-team context (no multi-account complexity yet)
- [ ] Local-first approach (no cloud sync, persistent SQLite)
- [ ] Mobile-friendly (Tailwind CSS baseline)
- [ ] Accessibility basics (ARIA labels, keyboard nav, contrast)

**Deliverables:**
- User flows (figma links, mockups)
- Interaction patterns (states, error messages, loading)
- Design specifications (colors, spacing, typography)
- **Each design must be testable** (QA will write tests against it)

---

## Coverage Requirements (Enforced)

| Layer | Minimum | Target | Tool |
|---|---|---|---|
| **Backend** | 80% | 85%+ | `pytest --cov=. --cov-fail-under=80` |
| **Frontend** | 70% | 75%+ | `npm test -- --coverage` |
| **Excluded** | Network connectors (Jira, Trello, Azure DevOps, GitLab, Linear, Shortcut) | 0% expected | Stubs, untestable without live credentials |

---

## Key Files by Agent Type

| Agent | Key Files | Purpose |
|---|---|---|
| **Code Reviewer** | `ARCHITECTURE.md`, `CONTRIBUTING.md`, `backend/tests/conftest.py` | Review for correctness & TDD |
| **DevSecOps** | `ARCHITECTURE.md` ("Data & Privacy"), `backend/utils/crypto.py` | Audit security & encryption |
| **QA** | `CONTRIBUTING.md` ("Common Patterns"), `backend/tests/`, `backend/calculator/flow.py` | Write tests, verify behavior |
| **Principal Eng** | `ARCHITECTURE.md` (all), `CONTRIBUTING.md` | Strategic guidance, design decisions |
| **UX Designer** | `README.md`, `ARCHITECTURE.md` ("System Overview"), `frontend/src/pages/`, `frontend/src/components/` | Design flows, mockups, specs |

---

## Common Questions by Agent Type

### Code Reviewer
- **Q**: Is this implementation correct?  
  **A**: Check if tests are written first and all tests pass
- **Q**: Should we refactor this code?  
  **A**: Check ARCHITECTURE.md "Key Design Decisions" for context; refactor if tests still pass
- **Q**: What's the test isolation pattern?  
  **A**: See ARCHITECTURE.md "Technical Details" — savepoint-based isolation in conftest.py

### DevSecOps
- **Q**: How are credentials stored?  
  **A**: See ARCHITECTURE.md "Data Model" — Fernet AES-128 encryption with OANNES_SECRET_KEY
- **Q**: Is GDPR compliant?  
  **A**: Yes, see ARCHITECTURE.md "Key Design Decisions" — local SQLite, no cloud sync, user controls data
- **Q**: Should we add user authentication?  
  **A**: See ARCHITECTURE.md "Future Improvements" — OAuth2 is planned

### QA
- **Q**: What should I test?  
  **A**: Build test plan: happy path, boundary, negative, error handling, concurrency (CONTRIBUTING.md)
- **Q**: How do I test the database?  
  **A**: Use `db` fixture from conftest.py with savepoint isolation (CONTRIBUTING.md "Testing Database Queries")
- **Q**: How do I test the API?  
  **A**: Use `client` fixture from conftest.py (CONTRIBUTING.md "Testing API Endpoints")

### Principal Engineer
- **Q**: Should we add microservices?  
  **A**: No, see ARCHITECTURE.md "Single Docker Container" — simplicity is a feature
- **Q**: Should we migrate to PostgreSQL?  
  **A**: No, see ARCHITECTURE.md "SQLite (Not PostgreSQL/MySQL)" — trade-offs documented
- **Q**: What's the next priority?  
  **A**: See ARCHITECTURE.md "Future Improvements" — auth, E2E tests, Linear/Shortcut connectors

### UX Designer
- **Q**: Should I design for multi-tenant?  
  **A**: Not yet, see ARCHITECTURE.md "Future Improvements" — currently single-user
- **Q**: What metrics matter most to users?  
  **A**: See ARCHITECTURE.md "Metrics (Troy Magennis Method)" — all 8 are equally important
- **Q**: Should I design a mobile app?  
  **A**: Web is responsive (Tailwind), mobile web first; native app is future consideration

---

## Before Starting Work: Checklist

- [ ] I have read `ARCHITECTURE.md`
- [ ] I have read `CONTRIBUTING.md`
- [ ] I have read `README.md`
- [ ] I understand the TDD workflow (RED → GREEN → REFACTOR)
- [ ] I understand the project's context (Troy Magennis metrics, single Docker, SQLite)
- [ ] I know the coverage requirements (≥80% backend, ≥70% frontend)
- [ ] I know how to run tests (`pytest`, `npm test`)
- [ ] I know how to access fixtures (`db`, `client`, `sample_project`)
- [ ] I understand this is a SINGLE-USER/SMALL-TEAM tool (not enterprise)

---

## Red Lines (Will Not Be Merged)

These changes will be rejected immediately:

- ❌ Code without tests (TDD violated)
- ❌ Tests that don't fail first (not following RED phase)
- ❌ Coverage drops below 80% (backend) or 70% (frontend)
- ❌ Tests using `time.sleep()`, real API calls, or flaky assertions
- ❌ Tests marked `@pytest.mark.skip()` (fix root cause instead)
- ❌ Hardcoded credentials or secrets in code
- ❌ Circular imports or pattern violations documented in ARCHITECTURE.md
- ❌ ARCHITECTURE.md not updated if design changed

---

## Questions?

1. **Architecture & design**: Read `ARCHITECTURE.md`
2. **How to code/test**: Read `CONTRIBUTING.md`
3. **Test patterns**: See `CONTRIBUTING.md` "Common Patterns" or `backend/tests/`
4. **Business logic**: Read `ARCHITECTURE.md` "Business Logic: Troy Magennis Flow Metrics"
5. **Why a decision was made**: Read `ARCHITECTURE.md` "Key Design Decisions"

---

## Summary

- **Read `ARCHITECTURE.md` before you do anything**
- **TDD is mandatory** (tests before code)
- **Coverage ≥80%** (backend), **≥70%** (frontend)
- **Test isolation** (use fixtures, no global state)
- **No shortcuts** (no skipped tests, no flake, no real APIs)
- **Document changes** (update ARCHITECTURE.md if design changed)

**The more you understand the WHY, the better decisions you'll make.**

---

**Last updated**: 2026-04-13  
**For**: All AI agents and human developers  
**Enforced**: Yes, red lines above will not be merged
