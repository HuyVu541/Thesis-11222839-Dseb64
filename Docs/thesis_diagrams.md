# Thesis Diagrams

Mermaid diagrams for inclusion in the thesis. Each diagram targets a specific chapter / section.
All diagrams use shape, text, and line-style to convey meaning — no color-dependent information.

---

## 1. Overall System Architecture (Ch. 4)

High-level view of all system components and how they connect.

```mermaid
flowchart LR
    %% Actors and Interfaces
    User(" User")
    API["FastAPI Backend"]

    %% Reasoning Engine
    subgraph Agent["LangGraph Agent System"]
        Gemini["Gemini 2.5 Flash<br/>(Tool-Calling Loop)"]
    end

    %% Storage and Dependencies
    subgraph Storage["Persistent Storage"]
        FS[/"Artifact Store<br/>(JSON Filesystem)"/]
        FAISS[/"FAISS Vector Index<br/>(Semantic Graph)"/]
        PG[("PostgreSQL DB<br/>(Northwind)")]
    end

    %% Step-by-step I/O Flow
    User -->|1. Request| API
    API -->|2. Invoke| Gemini
    Gemini -->|3. Final Answer| API
    API -->|4. Output Response| User

    %% Tool and Data Access
    Gemini <-->|"SAM tools<br/>Read/Write/Link"| FS
    Gemini <-->|"search_memory tool"| FAISS
    Gemini <-->|"DB tools<br/>run_query"| PG

    %% Background Synchronizations
    FS -.->|"auto-embed (SAM)"| FAISS
    Gemini -.->|"auto-embed (RAG)"| FAISS   
```

---

## 2. Memory Mode Ablation (Ch. 4, §4.3 / Ch. 7, §7.2)

Shows which capabilities each mode provides — directly supports the ablation argument.
Uses `[Available]` and `(Missing)` node shapes to distinguish present vs absent capabilities.

```mermaid
graph LR
    subgraph RAG_Mode["RAG Mode"]
        R_Search["search_memory"]
        R_Query["run_query"]
        R_Auto["Auto-embedding"]
        R_NoStruct("No typed artifacts")
        R_NoDeps("No dependency graph")
        R_NoVer("No version history")
    end

    subgraph SAM_Mode["SAM Mode"]
        S_List["list_artifacts"]
        S_Read["read_artifact"]
        S_Save["save_definition / save_insight"]
        S_Deps["get_dependencies"]
        S_Ver["update_artifact"]
        S_Query["run_query"]
        S_NoSearch("No semantic search")
    end

    subgraph Hybrid_Mode["SAM+RAG Mode"]
        H_Search["search_memory"]
        H_List["list_artifacts"]
        H_Read["read_artifact"]
        H_Save["save_definition / save_insight"]
        H_Deps["get_dependencies"]
        H_Ver["update_artifact"]
        H_Query["run_query"]
        H_Auto["Auto-sync to FAISS"]
    end
```

---

## 3. SAM Artifact Graph Structure (Ch. 5)

Illustrates how artifacts relate to each other via typed dependency edges.
Each layer uses a distinct node shape: `[(database)]` for schema, `[[box]]` for definitions, `[/parallelogram/]` for queries, `{{hexagon}}` for insights.

```mermaid
graph TD
    subgraph Schema["Schema Layer"]
        S_Orders[("schema/orders<br>─────<br>order_id, shipped_date,<br>required_date, ship_via")]
        S_Shippers[("schema/shippers<br>─────<br>shipper_id, company_name")]
        S_Details[("schema/order_details<br>─────<br>unit_price, quantity,<br>discount")]
    end

    subgraph Definitions["Business Definition Layer"]
        M_Late[["definition/late_delivery<br>─────<br>shipped_date > required_date<br>v1 → v2"]]
        M_Rev[["definition/net_revenue<br>─────<br>qty × price × (1 - discount)<br>v1"]]
    end

    subgraph Insights["Insights Layer"]
        I1{{"insight/speedy_risk<br>─────<br>12 late deliveries<br>→ pause contract"}}
        I2{{"insight/rev_trend<br>─────<br>Revenue up 15% YoY"}}
    end

    M_Late -->|depends_on| S_Orders
    M_Rev -->|depends_on| S_Details
    I1 -->|depends_on| M_Late
    I1 -->|depends_on| S_Shippers
    I2 -->|depends_on| M_Rev
```

---

## 4. Agent Workflow per Mode (Ch. 4, §4.2)

Decision flow showing how the agent processes a user question under each mode.
Each mode's branch is labelled; terminal nodes use `([stadium])` shape.

```mermaid
flowchart TD
    Start(["User Question"]) --> Mode{Memory Mode?}

    Mode -->|RAG| R1["search_memory<br>"] 
    R1 --> R2{"Found relevant<br>context?"}
    R2 -->|Yes| R3["run_query<br>(if data needed)"]
    R2 -->|No| R1
    R3 --> R4(["Respond"])

    Mode -->|SAM| H1["search_memory<br>"]
    H1 --> H2{"Found relevant<br>context?"}
    H2 -->|Yes| H3["read_artifact<br>(get full definition)"]
    H2 -->|No| H1
    H3 --> H4["get_dependencies<br>(traverse graph)"]
    H4 --> H5["run_query<br>(if data needed)"]
    H5 --> H6["save_definition /<br>save_insight<br>(if new finding)"]
    H6 --> H7(["Respond"])
```

---

## 5. Evaluation Pipeline (Ch. 7, §7.1)

End-to-end flow of how evaluation runs are executed and scored.

```mermaid
flowchart LR
    subgraph Setup["Setup (once per mode)"]
        Reset["reset_and_seed.sh<br>─────<br>Clear DB + filesystem<br>Seed prompts + data"]
        SetMode["Set memory_mode<br>in .env"]
        Distract["generate_distractors.py<br>─────<br>20 noise sessions<br>~50 artifacts"]
        Reset --> SetMode --> Distract
    end

    subgraph Run["Eval Run (repeatable)"]
        Snapshot["Snapshot<br>memory dir"]
        ClearEval["Clear e2e_*<br>sessions from DB"]
        Fixture["Restart backend<br>with correct mode"]
        Snapshot --> ClearEval --> Fixture

        subgraph Scenarios["3 Scenarios"]
            SC1["Accurate Retrieval<br>Under Noise<br>(2 sessions)"]
            SC2["Conflict Resolution<br>(4 sessions)"]
            SC3["Multi-Hop<br>Composition<br>(3 sessions)"]
        end
        Fixture --> Scenarios
    end

    subgraph Score["Scoring"]
        EX["Execution Accuracy<br>─────<br>Strict numeric value<br>or entity list"]
        Judge["LLM Judge<br>─────<br>Validates multi-hop<br>reasoning output"]
        Tokens["Resource Usage<br>─────<br>Tokens, latency,<br>tool call count"]
    end

    Scenarios --> EX
    Scenarios --> Judge
    Scenarios --> Tokens

    subgraph Output["Results"]
        DB_Out[("eval_runs table<br>(Postgres)")]
        JSON_Out["JSON backup<br>(results/)"]
    end

    EX --> DB_Out
    Judge --> DB_Out
    Tokens --> DB_Out
    EX --> JSON_Out
```

---

## 6. Conflict Resolution Failure (Ch. 7 / Ch. 8)

Illustrates exactly why RAG fails and SAM succeeds on the conflict resolution scenario.
Uses `alt` blocks labelled with mode names; outcomes marked with `[PASS]` and `[FAIL]`.

```mermaid
sequenceDiagram
    participant U as User
    participant A as Agent
    participant M as Memory

    Note over U,M: Session 1
    U->>A: HPA = >$800 freight
    A->>M: Store definition v1

    Note over U,M: Session 2
    U->>A: HPA = >4 product categories
    A->>M: Store definition v2

    Note over U,M: Session 3
    U->>A: HPA = Germany + >10 orders
    A->>M: Store definition v3

    Note over U,M: Session 4 — "How many High Priority Accounts?"
    A->>M: Retrieve HPA definition

    alt SAM Mode — version chain lookup
        M-->>A: v3 (latest): Germany + >10 orders
        A->>U: [PASS] 4 High Priority Accounts
    end

    alt RAG Mode — similarity-ranked retrieval
        M-->>A: v1, v2, v3 mixed (no implicit ordering)
        Note right of A: Cannot determine<br/>which is "latest"
        A->>U: [FAIL] Wrong count (applies mixed criteria)
    end
```

---

## 7. Auto-Embedding Data Flow (Ch. 6, §6.1)

Shows how RAG memory is populated automatically vs SAM's explicit management.
RAG flow uses dashed lines for implicit system actions; SAM uses solid lines for agent-driven actions.

```mermaid
flowchart LR
    subgraph RAG_Flow["RAG: Implicit Memory"]
        U1["User message"] --> Agent1["Agent processes"]
        Agent1 --> Resp1["Agent response"]
        Resp1 -.->|system| Embed1["Auto-embed<br>message + response<br>into FAISS"]
        Agent1 -->|"run_query"| SQL1["SQL result"]
        SQL1 -.->|system| Embed2["Auto-embed<br>query + result<br>into FAISS"]
    end

    subgraph SAM_Flow["SAM: Explicit Memory"]
        U2["User message"] --> Agent2["Agent processes"]
        Agent2 -->|"save_definition"| Art1["Typed artifact<br>with metadata"]
        Art1 --> Graph1["System updates<br>dependency graph<br>+ index"]
        Agent2 -->|"run_query(save=True)"| Art2["Query artifact<br>with schema snapshot"]
        Art2 --> Graph1
    end
```

---

## 8. Scenario 1 — Accurate Retrieval Under Noise (Ch. 7, Appendix B)

Agent defines 3 similar shipping performance definitions in S1, then must apply the correct one in S2 under noise. Each definition has company-specific thresholds that cannot be guessed from the name.

```mermaid
sequenceDiagram
    participant U as User
    participant A as Agent
    participant M as Memory
    participant DB as PostgreSQL

    Note over U,DB: Session 1 — Store 4 shipping definitions
    U->>A: Shipping Performance Index = % shipped within 3 days
    U->>A: Shipping Cost Efficiency = avg freight (line items >$200 only)
    U->>A: Shipping Reliability Score = % on-time EU orders (1-day tolerance)
    U->>A: Order Cost Average = avg freight across all orders

    Note over U,DB: Session 2 — Apply correct formula
    U->>A: What was our Shipping Cost Efficiency in 1997?
    A->>M: Retrieve "Shipping Cost Efficiency"

    alt SAM — definition matches saved name
        M-->>A: Definition 2 only — avg freight, filter line items >$200
        A->>DB: run_query (freight avg WHERE line_item_value >$200 AND year = 1997)
        DB-->>A: Correct result
        A-->>U: PASS — Shipping Cost Efficiency 1997 = $87.17
    else RAG — semantic similarity ambiguity
        M-->>A: Similar definitions across past interactions
        A->>DB: run_query (freight avg across ALL orders, year 1997)
        DB-->>A: Inconsistent or wrong result
        A-->>U: FAIL — wrong value
    end

    Note right of A: EX check: response must<br/>match golden value exactly.<br/>Wrong formula = wrong result.
```

---

## 9. Scenario 2 — Conflict Resolution (Ch. 7, Appendix B)

High Priority Account is redefined 3 times with entirely different criteria; agent must use the latest version.

```mermaid
sequenceDiagram
    participant U as User
    participant A as Agent
    participant M as Memory
    participant DB as PostgreSQL

    Note over U,DB: Session 1
    U->>A: HPA = >$800 freight
    A->>M: Store v1 (supersedes none)

    Note over U,DB: Session 2
    U->>A: HPA = Germany + >10 orders
    A->>M: Store v2 (supersedes v1)

    Note over U,DB: Session 3
    U->>A: HPA = >4 categories
    A->>M: Store v3 (supersedes v2)

    Note over U,DB: Session 4 — must use v3
    U->>A: How many High Priority Accounts?
    A->>M: Retrieve HPA definition

    alt SAM — version chain
        M-->>A: v3 only (latest by chain)
        A->>DB: run_query (count accounts matching v3 criteria)
        DB-->>A: 50 accounts
        A-->>U: PASS — 50 HPAs (>4 categories)
    else RAG — similarity search
        M-->>A: v1 + v2 + v3 mixed (no ordering)
        A->>DB: run_query (ambiguous — which criteria to use?)
        DB-->>A: Inconsistent or wrong count
        A-->>U: FAIL — wrong count (cannot determine latest)
    end

    Note right of A: EX check: strict match<br/>response must = 50 accounts

---

## 10. Scenario 3 — Multi-Hop Composition (Ch. 7, Appendix B)

Agent must chain: business definition → dependent business rule → SQL to identify flagged suppliers.

```mermaid
sequenceDiagram
    participant U as User
    participant A as Agent
    participant M as Memory
    participant DB as PostgreSQL

    Note over U,DB: Session 1 — Define base concept
    U->>A: Underperforming Product = ordered <30 times total
    A->>M: Store definition
    A-->>U: Acknowledged

    Note over U,DB: Session 2 — Define dependent rule
    U->>A: Supplier Review rule: >2 Underperforming Products → flag supplier
    A->>M: Store rule (references Underperforming Product)
    A-->>U: Acknowledged

    Note over U,DB: Session 3 — Evaluate multi-hop
    U->>A: Which suppliers should be flagged for Supplier Review?
    A->>M: Retrieve rule

    alt SAM — follows reference chain
        M-->>A: Supplier Review rule + Underperforming Product definition (via link)
        A->>DB: run_query (join both definitions into one query)
        DB-->>A: 2 suppliers matched (New Orleans, Grandma Kelly's)
        A-->>U: PASS — 2 suppliers flagged
    else RAG — follows reference chain
        M-->>A: Supplier Review rule
        A->>M: Follow breadcrumbs to retrieve all definitions
        A->>DB: run_query
        DB-->>A: Results depend on whether agent reasons correctly
        A-->>U: FAIL — depends on underlying LLM's reasoning <br>capability to retrieve correct definitions
    end

    Note right of A: EX via LLM judge: response<br/>must name both suppliers
```
