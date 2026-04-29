# Oannes — UML Diagrams

All diagrams use [Mermaid](https://mermaid.js.org/) syntax and render natively in GitHub, GitLab, and VS Code (with the Mermaid Preview extension).

## Index

### Structural

| Diagram | Type | Description |
|---|---|---|
| [System Components](system-component.md) | C4 Component | Full component map: browser, Docker container layers, SQLite, external platforms |
| [Data Model (ERD)](data-model.md) | ER Diagram | All DB tables: Project, WorkflowStep, CachedItem, ItemTransition, SyncJob |
| [Connector Classes](connector-classes.md) | Class Diagram | `BaseConnector` abstract class and all platform connector implementations |
| [Connector Config Models](connector-config-models.md) | Class Diagram | Pydantic validation models for each connector type |

### Behavioural

| Diagram | Type | Description |
|---|---|---|
| [Sync Flow](sync-flow-sequence.md) | Sequence | User or APScheduler trigger → SyncService → Connector → DB write |
| [Metrics Request](metrics-request-sequence.md) | Sequence | Browser navigates to metric → API → Calculator → Plotly chart |
| [Project Creation](project-creation-sequence.md) | Sequence | Wizard fill → test connection → save → first sync |
| [Credential Encryption](encryption-flow.md) | Sequence | Key loading on startup, encrypt on save, decrypt on sync |

### State

| Diagram | Type | Description |
|---|---|---|
| [Work Item Stages](work-item-stage-state.md) | State Machine | Stage transitions (queue → in_flight → review → done) with metric annotations |

## Maintenance

Update the relevant diagram(s) whenever you:

- Add a new API route → update `system-component.md`
- Add a DB column or table → update `data-model.md`
- Add a new connector → update `connector-classes.md` and `connector-config-models.md`
- Change the sync or creation flow → update the relevant sequence diagram
- Change stage names or transitions → update `work-item-stage-state.md`
