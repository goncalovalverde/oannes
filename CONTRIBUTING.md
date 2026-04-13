# Contributing to Oannes

**All contributors and agents MUST read `ARCHITECTURE.md` before making changes.**

This guide ensures quality, consistency, and TDD-first development across all work.

---

## Required Reading (Before You Code)

1. **`ARCHITECTURE.md`** — System design, business logic, key decisions, testing patterns
2. **`README.md`** — Project overview, quick start, tech stack
3. **This file** — Development workflow and standards

---

## TDD-First Workflow (Required for All Changes)

**Test-Driven Development is non-negotiable.** Every feature, fix, and refactor follows this sequence:

### 1. Write Tests First (RED phase)

Before writing any implementation code:

- **Understand the requirement**: Read ARCHITECTURE.md to understand context
- **Write failing tests**: Tests that define the expected behavior
- **Make them concrete**: Include exact inputs, outputs, and edge cases
- **Run tests**: Confirm they fail (RED phase)

**Example:**
```python
# File: backend/tests/calculator/test_new_metric.py

def test_calculate_new_metric_with_valid_items():
    """New metric should sum values correctly."""
    items = [
        {'value': 10, 'completed_at': datetime(2026, 1, 1)},
        {'value': 20, 'completed_at': datetime(2026, 1, 2)},
    ]
    result = calculate_new_metric(items)
    assert result == 30  # Expected behavior

def test_calculate_new_metric_with_empty_list():
    """New metric should return 0 for empty input."""
    result = calculate_new_metric([])
    assert result == 0

def test_calculate_new_metric_with_missing_values():
    """New metric should skip items with missing 'value' field."""
    items = [
        {'value': 10, 'completed_at': datetime(2026, 1, 1)},
        {'completed_at': datetime(2026, 1, 2)},  # Missing 'value'
    ]
    result = calculate_new_metric(items)
    assert result == 10  # Only counts the first item
```

### 2. Implement to Pass Tests (GREEN phase)

Write minimal code to make tests pass:

```python
# File: backend/calculator/new_metric.py

def calculate_new_metric(items: list[dict]) -> float:
    """Calculate sum of item values."""
    total = 0
    for item in items:
        if 'value' in item:
            total += item['value']
    return total
```

- Don't over-engineer
- Don't add features not tested
- Just make the tests pass

**Run tests:** `pytest backend/tests/calculator/test_new_metric.py -v`

### 3. Refactor (REFACTOR phase)

Clean up code while keeping tests passing:

```python
# Refactored version
def calculate_new_metric(items: list[dict]) -> float:
    """Calculate sum of item values, skipping items with missing values."""
    return sum(item['value'] for item in items if 'value' in item)
```

**Verify tests still pass:** `pytest backend/tests/calculator/test_new_metric.py -v`

### 4. Add Integration Tests

Once unit tests pass, add integration tests (API level or full flow):

```python
# File: backend/tests/api/test_metrics_api.py

def test_new_metric_endpoint_with_valid_project(client, sample_project_with_items):
    """GET /api/metrics/{id}/new-metric should return calculated value."""
    response = client.get(f"/api/metrics/{sample_project_with_items.id}/new-metric")
    assert response.status_code == 200
    assert 'value' in response.json()
    assert response.json()['value'] == 30  # Expected from test data

def test_new_metric_endpoint_with_nonexistent_project(client):
    """GET /api/metrics/999/new-metric should return 404."""
    response = client.get("/api/metrics/999/new-metric")
    assert response.status_code == 404
```

### 5. Run Full Test Suite

Before committing, ensure **all tests pass** and **coverage stays ≥80%**:

```bash
# Backend
cd backend && pytest --cov=. --cov-fail-under=80 -v

# Frontend
cd frontend && npm test -- --coverage

# Both together
pytest && npm test
```

---

## Test Organization

### Backend (pytest)

```
backend/tests/
├── calculator/          # Pure business logic (flow metrics)
│   ├── test_flow.py
│   └── test_monte_carlo.py
├── api/                 # HTTP endpoints
│   ├── test_metrics_api.py
│   ├── test_projects_api.py
│   ├── test_sync_api.py
│   └── test_connectors_api.py
├── connectors/          # Platform integrations
│   └── test_csv_connector.py
├── services/            # Business services
│   └── test_sync_service.py
├── utils/               # Utilities
│   └── test_crypto.py
├── test_scheduler.py    # Background jobs
└── conftest.py          # Shared fixtures (critical: savepoint isolation)
```

**Naming convention**: `test_<module>.py` tests module `<module>.py`

### Frontend (Vitest)

```
frontend/src/
├── components/
│   └── config/
│       ├── ProjectWizard.tsx
│       └── ProjectWizard.test.tsx
├── api/hooks/
│   ├── useMetrics.ts
│   └── useMetrics.test.ts
└── test/
    └── setup.ts         # Test environment config
```

**Naming convention**: `<Component>.test.tsx` tests `<Component>.tsx`

---

## Test Quality Standards

### Do's ✅

- **One logical assertion per test** (multiple assertions if testing different aspects of same behavior)
  ```python
  # Good
  def test_user_creation():
      user = create_user('alice', 'alice@example.com')
      assert user.name == 'alice'
      assert user.email == 'alice@example.com'
      assert user.created_at is not None
  ```

- **Use descriptive test names** that explain the scenario and expected outcome
  ```python
  # Good
  def test_calculate_cycle_time_excludes_not_started_items()
  def test_sync_project_retries_on_network_error()
  def test_aging_wip_alert_triggers_above_85th_percentile()
  ```

- **Test edge cases and error paths**
  ```python
  def test_calculate_cycle_time_with_empty_dataframe()
  def test_api_returns_401_without_auth_token()
  def test_connector_handles_missing_api_field()
  ```

- **Isolate tests** — each test sets up and tears down its own state
  ```python
  def test_project_creation(db):  # db fixture handles setup/teardown
      project = Project(name='Test', platform='jira')
      db.add(project)
      db.commit()
      assert project.id is not None
      # Teardown happens automatically via fixture
  ```

- **Use fixtures for setup** (not global state or class methods)
  ```python
  @pytest.fixture
  def sample_project(db):
      return Project(name='Test', platform='jira')
  
  def test_project_sync(sample_project):
      # Use fixture instead of setUp()
      assert sample_project.name == 'Test'
  ```

### Don'ts ❌

- **Don't use `time.sleep()`** in tests — use mocks or fixtures instead
  ```python
  # Bad
  def test_scheduler():
      start_job()
      time.sleep(5)  # Flaky!
      assert job_completed()
  
  # Good
  def test_scheduler(monkeypatch):
      start_job()
      monkeypatch.setattr('apscheduler.scheduler.Scheduler.start', mock_start)
      # Verify behavior without waiting
  ```

- **Don't call real APIs** in tests — mock all external services
  ```python
  # Bad
  def test_jira_sync():
      items = jira.get_items(real_api_key)  # Calls real Jira!
  
  # Good
  def test_jira_sync(monkeypatch):
      monkeypatch.setattr('jira.get_items', mock_get_items)
      items = jira.get_items(fake_api_key)
  ```

- **Don't skip or mark tests as pending** — fix the root cause
  ```python
  # Bad
  @pytest.mark.skip(reason="flaky")
  def test_concurrent_sync():
      # Fix the race condition instead!
  
  # Good
  def test_concurrent_sync():
      # Use locks, mocks, or deterministic setup to eliminate flakiness
  ```

- **Don't couple tests to implementation details**
  ```python
  # Bad
  def test_calculate_cycle_time():
      # Testing private method behavior
      result = calculator._internal_compute()
      assert result._cached_value == 42
  
  # Good
  def test_calculate_cycle_time():
      # Test public API behavior
      result = calculator.get_cycle_time(items)
      assert result == 42
  ```

- **Don't write tautological tests** that always pass
  ```python
  # Bad
  def test_user_name():
      user = User(name='Alice')
      assert user.name == 'Alice'  # Just tests assignment!
  
  # Good
  def test_user_name_is_stored_and_retrieved():
      user = User(name='Alice')
      db.add(user)
      db.commit()
      reloaded = db.query(User).first()
      assert reloaded.name == 'Alice'  # Tests persistence!
  ```

---

## Coverage Requirements

| Component | Minimum | Target |
|---|---|---|
| **Backend** | 80% | 85%+ |
| **Frontend** | 70% | 75%+ |
| **Excluded** | Network connectors (Jira, Trello, etc. — untestable without live creds) | |

**Enforce coverage:**
```bash
# Backend
pytest --cov=. --cov-fail-under=80

# Frontend
npm test -- --coverage
```

**View coverage report:**
```bash
# Backend
pytest --cov=. --cov-report=html
open htmlcov/index.html
```

---

## Common Patterns

### Testing Database Queries

Use the `db` fixture from `conftest.py` — it provides transaction isolation:

```python
def test_project_retrieval(db):
    """Projects should be retrievable by ID."""
    project = Project(name='Test', platform='jira')
    db.add(project)
    db.commit()
    
    retrieved = db.query(Project).filter_by(name='Test').first()
    assert retrieved.name == 'Test'
    assert retrieved.id == project.id
    # Automatically rolled back after test
```

### Testing API Endpoints

Use the `client` fixture from `conftest.py`:

```python
def test_create_project_endpoint(client, db):
    """POST /api/projects/ should create a project."""
    response = client.post('/api/projects/', json={
        'name': 'Test Project',
        'platform': 'jira',
        'credentials': {'api_token': 'fake_token'}
    })
    assert response.status_code == 201
    assert response.json()['name'] == 'Test Project'
    
    # Verify DB was updated
    project = db.query(Project).filter_by(name='Test Project').first()
    assert project is not None
```

### Testing Error Cases

```python
def test_create_project_with_invalid_platform(client):
    """POST /api/projects/ with invalid platform should return 422."""
    response = client.post('/api/projects/', json={
        'name': 'Test',
        'platform': 'invalid_platform',
        'credentials': {}
    })
    assert response.status_code == 422
    assert 'platform' in response.json()['detail'][0]['loc']

def test_create_project_without_name(client):
    """POST /api/projects/ without name should return 422."""
    response = client.post('/api/projects/', json={
        'platform': 'jira',
        'credentials': {}
    })
    assert response.status_code == 422
```

### Testing Monte Carlo Simulation

Always use a `seed` parameter for determinism:

```python
def test_monte_carlo_with_seed():
    """Monte Carlo with same seed should produce identical results."""
    result1 = simulate_when_done(100, items, seed=42)
    result2 = simulate_when_done(100, items, seed=42)
    assert result1 == result2  # Deterministic!

def test_monte_carlo_distribution():
    """Monte Carlo should produce valid probability distribution."""
    result = simulate_how_many(4, items, seed=42)
    assert len(result) > 0
    assert all(0 <= x <= 1 for x in result)  # Probabilities
    assert abs(sum(result) - 1.0) < 0.01  # Sum to 1
```

---

## Code Review Checklist

Before committing, verify:

- [ ] Tests written BEFORE implementation (TDD)
- [ ] All tests pass: `pytest && npm test`
- [ ] Coverage ≥80% (backend), ≥70% (frontend)
- [ ] No `time.sleep()`, real API calls, or flaky assertions
- [ ] Test names describe the scenario clearly
- [ ] Edge cases tested (empty input, missing fields, errors)
- [ ] Database changes tested with real DB (SQLite) and fixtures
- [ ] API changes tested with `client` fixture
- [ ] No mutable global state between tests
- [ ] ARCHITECTURE.md updated if design changed

---

## Git Commit Message Format

```
<type>(<scope>): <description>

<body>

<footer>
```

**Types**: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `chore`

**Example:**
```
feat(calculator): add new aging-wip metric

- Calculates items in flight longer than 85th percentile
- Added aging_wip_items() function in flow.py
- Added 8 tests covering edge cases

Closes #42

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
```

---

## Questions?

- **Architecture decisions**: See `ARCHITECTURE.md`
- **Test patterns**: See `backend/tests/conftest.py` and existing tests
- **Business logic**: See `ARCHITECTURE.md` — "Business Logic: Troy Magennis Flow Metrics"

---

**All work must follow TDD. No exceptions.**

Read `ARCHITECTURE.md` before you code.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
