# Sequence Diagrams — System Architecture

Convert each diagram block to a PNG and reference it in the thesis.
- `fig:seq-success` → `Sequence Success.png`
- `fig:seq-failure` → `Sequence Failure.png`

---

## Diagram 1: Successful Flow (Two Sessions)

Participants: User · LLM · System (orchestrator + tool layer + memory API) · Database

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'background': '#ffffff', 'primaryColor': '#ffffff', 'primaryBorderColor': '#000000', 'secondaryColor': '#f0f0f0', 'tertiaryColor': '#ffffff', 'lineColor': '#000000', 'textColor': '#000000', 'noteBkgColor': '#f0f0f0', 'noteBorderColor': '#000000', 'actorBkg': '#ffffff', 'actorBorder': '#000000', 'actorTextColor': '#000000', 'signalColor': '#000000', 'signalTextColor': '#000000'}}}%%
sequenceDiagram
    autonumber
    actor User
    participant LLM
    participant Sys as System
    participant DB as Database

    Note over User, DB: Session 1 — Define and compute

    User->>LLM: Define Slow-Selling Product (< 500 units)
    LLM->>Sys: "save_definition('Slow-Selling Product', formula, deps)"
    Sys-->>LLM: Saved as def_slow_selling_product v1
    LLM->>DB: "run_query(SELECT ... HAVING SUM(qty) < 500)"
    DB-->>LLM: 31 rows
    LLM-->>User: 31 products qualify

    Note over User, DB: Session 2 — Revise threshold

    User->>LLM: Update slow-selling threshold to 350 units and recheck
    LLM->>Sys: "search_memory(query='slow selling threshold')"
    Sys-->>LLM: def_slow_selling_product v1 (active)
    LLM->>Sys: "update_artifact(id, {formula: SUM(qty)<350}, reason)"
    Sys-->>LLM: Updated to v2, v1 archived
    LLM->>DB: "run_query(SELECT ... HAVING SUM(qty) < 350)"
    DB-->>LLM: 23 rows
    LLM-->>User: 23 products under revised threshold

---

## Diagram 2: Failure and Recovery Flow (Session 4)

Missing dependency edge detected; agent falls back to semantic search,
reads the base definition, repairs the graph, then answers.

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'background': '#ffffff', 'primaryColor': '#ffffff', 'primaryBorderColor': '#000000', 'secondaryColor': '#f0f0f0', 'tertiaryColor': '#ffffff', 'lineColor': '#000000', 'textColor': '#000000', 'noteBkgColor': '#f0f0f0', 'noteBorderColor': '#000000', 'actorBkg': '#ffffff', 'actorBorder': '#000000', 'actorTextColor': '#000000', 'signalColor': '#000000', 'signalTextColor': '#000000'}}}%%
sequenceDiagram
    autonumber
    actor User
    participant LLM
    participant Sys as System
    participant DB as Database

    Note over User, DB: Session 4 — Multi-hop query

    User->>LLM: Which categories are underperforming?
    LLM->>Sys: "search_memory(query='underperforming categories', type='definition')"
    Sys-->>LLM: def_underperforming_category v1

    Note over LLM, Sys: Attempt dependency traversal
    LLM->>Sys: "get_dependencies(def_underperforming_category, up)"
    Sys-->>LLM: No dependencies found

    Note over LLM, Sys: Failure — edge missing, begin recovery
    LLM->>Sys: "search_memory(query='slow selling product threshold', type='definition')"
    Sys-->>LLM: def_slow_selling_product (score 0.91)

    Note over LLM, Sys: Recovery — repair graph
    LLM->>Sys: link_artifacts(def_underperforming_category → def_slow_selling_product)
    Sys-->>LLM: Edge recorded

    LLM->>DB: run_query(SQL)
    DB-->>LLM: Confections, Grains/Cereals
    LLM-->>User: 2 underperforming categories
```
