\documentclass[12pt]{report}

\usepackage{graphicx}
\usepackage{amsmath}
\usepackage{hyperref}
\usepackage{listings}
\usepackage{booktabs}
\usepackage{array}
\usepackage{geometry}
\usepackage{longtable}
\usepackage{tabularx}
\usepackage{ragged2e}
\usepackage{svg}
\usepackage{tcolorbox}
\usepackage{float}
\usepackage{enumitem}
\usepackage{array}
\newcolumntype{L}{>{\raggedright\arraybackslash}l}
\tcbuselibrary{breakable}

% Running example callout box
\newenvironment{runningex}[1]{%
  \begin{tcolorbox}[
    breakable,
    title={\small Example\,---\,\textit{#1}},
    colback=gray!5,
    colframe=gray!35,
    coltitle=black,
    fonttitle=\small\bfseries,
    left=8pt, right=8pt, top=6pt, bottom=6pt
  ]
}{%
  \end{tcolorbox}
}

\usepackage{setspace}   
\usepackage{amssymb}
\usepackage{nomencl}
\usepackage{siunitx}
\usepackage{tikz}
\usetikzlibrary{positioning,arrows.meta}

\sisetup{
  table-format=3.1,
  detect-weight=true,
  detect-inline-weight=math
}

\makenomenclature

\geometry{margin=1in}

% ADD DIAGRAMS
% - Memory design
% - Test case process

% Define JSON as a listings language
\lstdefinelanguage{json}{
  basicstyle=\ttfamily\small,
  morestring=[b]",
  showstringspaces=false
}

% Compact listing style
\lstset{
  basicstyle=\ttfamily\small,
  breaklines=true,
  frame=single,
  xleftmargin=1em,
  xrightmargin=1em
}

\begin{document}

%========================
% Front Matter
%========================

\begin{titlepage}
    \centering
    
    {\large\textbf{NATIONAL ECONOMICS UNIVERSITY}\par}
    {\large\textbf{FACULTY OF MATHEMATICS IN ECONOMICS}\par} % Usually standard translation for Khoa Toán Kinh Tế
    
    \vspace{1.5cm}
    
    \includegraphics[width=4cm]{logo.png}
    
    \vspace{2.5cm}
    
    {\Large\textbf{Bachelor Thesis}\par}
    
    \vspace{2cm}
    
    {\LARGE\textbf{PERSISTENT MEMORY FOR MULTI-SESSION \\ BUSINESS INTELLIGENCE AGENTS}\par}
    
    \vspace{2.5cm}
    
    \begin{center}
    \large
    \renewcommand{\arraystretch}{1.5}
    \begin{tabular}{ll}
    \textbf{Student:} & Vu Quoc Huy \\
    \textbf{Student ID:} & 11222839 \\
    \textbf{Class:} & DSEB64 \\
    \textbf{Instructor:} & Dr. Hung Tran
    \end{tabular}
    \end{center}
    
    \vfill
    
    {\large Ha Noi, May 2025\par}
\end{titlepage}
\pagenumbering{roman}

\chapter*{Abstract}
\addcontentsline{toc}{chapter}{Abstract}

Large language model (LLM) based agents have demonstrated strong potential for automating business intelligence (BI) tasks, including natural language querying, data computation, and exploratory data analysis. However, existing generative BI systems treat each session as an isolated interaction, relying on conversational context or vector-based retrieval to supply relevant background. This design is adequate for single-turn or short-session tasks but breaks down in realistic multi-session BI workflows, where an analyst builds incrementally on prior work: refining business definitions, tracking schema changes, etc.

This thesis proposes and evaluates a Structured Artifact Memory (SAM) architecture for BI agents, designed to mirror the artifact-oriented nature of real BI work. SAM organises memory as a typed, versioned artifact graph with explicit dependency relationships, and can be combined with semantic retrieval for efficient artifact discovery. Agents interact with memory through a structured tool interface that supports deterministic graph navigation, including dependency resolution, provenance tracing, and artifact versioning.

The proposed architecture is evaluated via 600 simulated multi-session analytical workflows, executed against a realistic BI database populated with seeded distractor noise. The system is compared against a retrieval-augmented generation (RAG) baseline that shares the identical semantic embedding mechanism but lacks structural memory. Results demonstrate that while the two architectures perform comparably on tasks requiring only flat semantic retrieval, the hybrid SAM architecture yields highly significant improvements on tasks requiring conflict resolution and multi-hop dependency traversal. Overall, SAM achieved an 88.7\% execution accuracy across complex BI tasks compared to the RAG baseline's 63.0\%, showing that structural memory capabilities greatly improve agent performance in multi-session BI environments.

\tableofcontents
\listoffigures
\listoftables

%========================
% List of Abbreviations
%========================

\newpage
\chapter*{List of Abbreviations}
\addcontentsline{toc}{chapter}{List of Abbreviations}

\begin{longtable}{@{} p{3cm} p{10cm} @{}}
\toprule
\textbf{Abbreviation} & \textbf{Definition} \\
\midrule
\endhead
AST   & Abstract Syntax Tree \\
BI    & Business Intelligence \\
EX    & Execution Accuracy \\
FAISS & Facebook AI Similarity Search \\
JSON  & JavaScript Object Notation \\
LLM   & Large Language Model \\
RAG   & Retrieval-Augmented Generation \\
SAM   & Structured Artifact Memory \\
SQL   & Structured Query Language \\
TOC   & Table of Contents \\
\bottomrule
\end{longtable}

\newpage
\pagenumbering{arabic}

%========================
% Main Chapters
%========================

\chapter{Introduction}

\section{Background}

Business intelligence (BI) encompasses the processes, tools, and systems that organisations use to collect, analyse, and act on data. Traditional BI workflows are carried out by human analysts who iteratively construct analytical artifacts, such as data models, business definitions (e.g., KPI formulas), and recorded insights (e.g., data-quality notes), over extended periods and across multiple working sessions. These artifacts are not isolated products; they form a web of dependencies, where a dashboard relies on specific SQL views, queries depend on particular schema definitions, and business definitions encode business logic that evolves over time.

The emergence of large language models capable of generating SQL, interpreting query results, and reasoning over structured data has created a new class of systems: generative BI agents. These agents accept natural language instructions and autonomously execute analytical tasks, including schema exploration, query generation, and result interpretation. Early systems in this space, such as Wren AI \cite{WrenAI2024}, demonstrate that LLM-based agents can handle a broad range of BI tasks without requiring users to write code or SQL directly.

Despite this progress, generative BI agents remain fundamentally limited in how they manage knowledge over time. Most systems treat each user session as a fresh context, with no structured record of prior analytical work. Even systems that incorporate memory do so through general-purpose mechanisms, most commonly vector-based retrieval-augmented generation (RAG) \cite{Lewis2020RetrievalAugmentedGF}, which are not designed around the artifact-oriented, dependency-rich structure of BI workflows.

\section{Motivation}

The limitations of current memory approaches become apparent when BI agents are deployed in realistic multi-session settings. Consider an analyst who, over several sessions, defines a revenue business definition, writes queries to compute it, discovers a data quality issue, and updates the definition accordingly. A stateless agent has no record of this history. An agent with a sliding context window (which drops older messages when the allowed text limit is reached) may lose this history over time. A RAG-based agent may retrieve fragments of prior work by similarity, but it cannot determine which query implements which definition, whether the definition has been updated since the query was written, or which downstream artifacts are affected by a schema change.

These cases reflect the core structure of BI work: artifacts depend on one another, schemas change, and analytical conclusions are built incrementally. A memory architecture that cannot represent these structural properties forces agents to rediscover context that should have been retained, produce results inconsistent with prior work, and fail to propagate updates through dependent artifacts.

At the same time, purely structural navigation without semantic retrieval scales poorly. As the number of stored artifacts grows, an agent that must browse flat indexes and read artifacts one by one will exhaust its tool budget before reaching the relevant information. Semantic retrieval excels at surfacing relevant content under noise, but lacks the structural awareness to resolve dependencies, manage version conflicts, or trace history chains. This thesis argues that effective BI agent memory requires both capabilities: semantic retrieval for efficient artifact discovery, and structural memory for dependency-sensitive operations that retrieval alone cannot support.

\section{Problem Statement}

This thesis addresses the following problem: \textit{existing generative BI agents lack a persistent memory layer that combines efficient retrieval with structural awareness of analytical artifacts, their interdependencies, and their version histories, limiting their ability to maintain analytical continuity across sessions.}

More specifically, the problem has three components:

\begin{enumerate}
    \item \textbf{Session isolation:} Agent memory does not persist across sessions in a structured form, requiring users to re-supply context that the agent should retain.
    \item \textbf{Retrieval without structure:} Semantic retrieval can surface relevant artifacts, but cannot represent artifact types, dependency relationships, or version history. This leads to failures on tasks requiring dependency resolution or conflict-free version management.
    \item \textbf{Structure without retrieval:} Purely index-based navigation scales poorly as artifacts accumulate. Without semantic search, agents exhaust their tool budget browsing and reading artifacts to find relevant information.
\end{enumerate}

To systematically investigate these challenges, this thesis is guided by three primary research questions:

\begin{itemize}
    \item \textbf{RQ1:} To what extent does a hybrid memory architecture—combining semantic retrieval with structured artifact management—improve a generative BI agent's ability to maintain analytical continuity across multi-session workflows?
    \item \textbf{RQ2:} How does explicit structural memory address the limitations of pure semantic retrieval (RAG) when managing evolving business logic and interrelated analytical artifacts?
    \item \textbf{RQ3:} What are the trade-offs between execution accuracy and operational cost and latency when shifting from flat vector retrieval to a structured memory system?
\end{itemize}

\section{Research Objectives}

This thesis pursues the following objectives:

\begin{enumerate}
    \item Design a persistent memory architecture for BI agents that combines semantic retrieval with structured artifact management. The design is considered complete when it formally specifies (a) an artifact schema covering business definitions, schema artifacts and insights; (b) a bidirectional dependency graph model supporting upstream and downstream traversal; and (c) a versioning scheme that allows prior artifact states to be recovered and updates to be audited.

    \item Implement a working prototype that integrates the designed memory architecture with an LLM-based BI agent. The prototype is considered complete when five components are operational and tested: (a) a \textit{storage layer} that persists typed JSON artifact documents in a hierarchical file-system structure; (b) an \textit{API/tools layer} exposing tools to the agent; (c) a \textit{retrieval module} that embeds artifacts into a FAISS vector store and supports semantic similarity search; (d) an \textit{agent loop} implemented on LangGraph that executes multi-session BI tasks using either the SAM or RAG tool set according to the configured mode; and (e) \textit{evaluation scripts} that automate multi-session scenario execution, collect per-turn latency and execution-accuracy metrics, and invoke an LLM-as-a-judge for qualitative scoring.

    \item Evaluate the proposed SAM architecture against a RAG baseline in controlled multi-session analytical scenarios, measuring execution accuracy (EX), per-session latency, and qualitative rubric scores (analytical continuity, memory utilisation, reasoning quality, and tool efficiency) across three scenario types: accurate retrieval under noise, conflict resolution, and multi-hop dependency composition. The evaluation is considered complete when each scenario has been run 100 times per mode and the results demonstrate whether structural memory provides a statistically and practically meaningful improvement over pure semantic retrieval.
\end{enumerate}

\section{Contributions}

The main contributions of this thesis are:

\begin{itemize}
    \item A \textbf{hybrid memory architecture} for BI agents that combines semantic retrieval with a typed artifact graph, including dependency tracking and version history.
    \item A \textbf{small controlled test suite} consisting of three synthetic multi-session scenarios designed to probe memory-dependent capabilities: accurate retrieval under noise, conflict resolution, and multi-hop dependency composition, implemented as automated evaluation scripts.
    \item An \textbf{empirical comparison} between the proposed SAM architecture and a RAG baseline across the three scenarios, providing initial evidence that structural memory capabilities offer advantages over pure semantic retrieval on dependency-sensitive tasks in a synthetic single-database setting.
\end{itemize}

\section{Scope and Assumptions}

This thesis focuses on BI tasks that involve translating natural language into SQL for data retrieval, metric calculation, and exploratory analysis over structured data. The research and evaluation are constrained to single-user, single-project tabular relational database scenarios. Unstructured data analysis and distributed NoSQL databases are not covered. Furthermore, the developed system serves as a research prototype to validate the proposed memory architecture; full-scale production deployment concerns such as multi-user collaboration, real-time streaming data integration, enterprise security enforcement, and cross-database query execution are outside the scope of this thesis.

\section{Thesis Structure}

The remainder of this thesis is organised as follows. Chapter~2 surveys related work on generative BI agents and agent memory architectures. Chapter~3 analyses the requirements for persistent memory in BI settings. Chapter~4 describes the overall system architecture. Chapter~5 details the persistent memory design. Chapter~6 covers the implementation. Chapter~7 presents the experimental evaluation. Chapter~8 discusses the results and their implications. Chapter~9 concludes and outlines future directions.

%------------------------

\chapter{Related Work}

\section{Foundational Concepts}

Before surveying related work, this section defines two foundational concepts that underpin the thesis: \textit{agents} and \textit{memory} in the context of large language models.

\subsection{LLM-Based Agents}

A large language model (LLM) is a neural network trained on large corpora of text, capable of generating coherent natural language and reasoning over structured information. On its own, an LLM is a passive system: it receives a text prompt and produces a text response, with no ability to take actions in the world or observe their effects.

An \textit{LLM-based agent} extends this passive model into an autonomous actor by equipping it with \textit{tools}: executable functions that the agent can invoke to interact with external systems. A tool might execute a SQL query against a database, read a file, call an API, or store information in a memory system. The agent operates in a loop: it receives an instruction, then the underlying language model itself generates a structured text command requesting to use a specific tool. The orchestration framework running the agent intercepts this command, executes the actual code (e.g., querying the database), and appends the result to the conversation for the LLM to "observe". The LLM reads this new text, reasons about the results, and may request further tools until it determines the task is complete and outputs a final response to the user. This observe--reason--act cycle distinguishes agents from plain LLMs (which only generate text) and from chatbots (which maintain conversation but do not take actions).

In the context of this thesis, the agent is a tool-using LLM that performs business intelligence tasks: it explores database schemas, generates and executes SQL queries, interprets results, and manages analytical artifacts, all through tool invocations mediated by an orchestration framework.

\subsection{Agent Memory}

\textit{Memory}, in the context of an LLM-based agent, refers to any mechanism that allows the agent to retain and access information beyond its immediate input. Without memory, every interaction starts from zero: the agent has no knowledge of prior sessions, previously defined concepts, or past analytical work.

Agent memory can be categorised along two dimensions. \textit{Short-term memory} corresponds to the information available within the current conversation context: the user's messages, the agent's prior responses, and any tool outputs from the current session. This memory is bounded by the LLM's context window (the strict limit on the number of words or underlying "tokens" the model can ingest and process at any one time) and is discarded when the session ends. \textit{Long-term memory} refers to information that persists across session boundaries, stored in an external system and retrieved when needed.

The simplest form of long-term memory is retrieval-augmented generation (RAG), where past information is embedded as vectors that map the underlying meaning of the text. Because concepts with similar meanings produce closely clustered vectors, the system can surface related knowledge by measuring the mathematical distance between these values, solving what we call semantic similarity. More structured forms of long-term memory organise stored information with explicit types, relationships, and version histories, enabling deterministic navigation in addition to similarity-based retrieval. The central question of this thesis is how to design the long-term memory layer for a BI agent so that analytical work persists meaningfully across sessions.

\section{Generative BI Agents}

Generative BI refers to systems that use large language models to automate analytical tasks traditionally performed by human analysts. Early work in this area focused on zero-shot text-to-SQL generation (asking the model to perform the task without providing it any prior examples of correct solutions), translating natural language questions into executable SQL queries, pioneered by benchmarks such as Spider~\cite{Yu2019SpiderAL}. More recent systems extend this simple translation paradigm to full, autonomous analytical pipelines, incorporating schema introspection, query generation, result interpretation, and tool utilisation.

Wren AI represents a contemporary example of an open-source generative BI platform, combining LLM-based query generation with a semantic layer that exposes database schemas in business-friendly terms~\cite{WrenAI2024}. State-of-the-art text-to-SQL systems such as DIN-SQL~\cite{Pourreza2023DINSQL} improve accuracy on complex queries through specialised decomposition and self-correction modules. More recently, multi-turn evaluation benchmarks such as BIRD-INTERACT~\cite{BirdInteract2025} highlight that real-world database workflows require iterative interaction, error recovery, and knowledge retrieval, which are much more complex than single-turn query generation.

However, existing generative BI systems share a critical structural limitation: they are predominantly designed for single-session, single-question interactions. While they excel at retrieving data from complex schemas, the analytical context produced in one session is rarely retained in any structured form for subsequent sessions. This renders them unsuitable for the highly iterative, multi-session workflows characteristic of real enterprise BI work.

Table~\ref{tab:related-work-comparison} summarises the systems and benchmarks reviewed in this section.

\begin{table}[h]
\centering
\caption{Generative BI systems and benchmarks: capabilities, memory type, and limitations.}
\label{tab:related-work-comparison}
\footnotesize
\begin{tabularx}{\textwidth}{p{2.3cm} p{3.2cm} p{2.0cm} p{3.2cm} X}
\toprule
\textbf{System / Benchmark} & \textbf{Main Capability} & \textbf{Memory Type} & \textbf{Key Limitation} & \textbf{Relevance} \\
\midrule
Spider~\cite{Yu2019SpiderAL}
  & Cross-domain NL-to-SQL benchmark
  & None
  & Single-turn; no session continuity
  & Establishes SQL generation as core BI task \\
\midrule
BIRD~\cite{Li2023BIRD}
  & Large-scale text-to-SQL; execution accuracy metric
  & None
  & Single-session; no artifact retention
  & Source of EX metric used in evaluation \\
\midrule
DIN-SQL~\cite{Pourreza2023DINSQL}
  & Decomposed in-context SQL generation
  & None
  & Stateless; no cross-request persistence
  & Strong single-session pipeline; shows memory layer is needed on top \\
\midrule
Wren AI~\cite{WrenAI2024}
  & Generative BI with semantic layer
  & Shallow (instruction rules, feedback)
  & No dependency graph or artifact versioning
  & Motivates structured memory beyond a semantic layer \\
\midrule
BIRD-INTERACT~\cite{BirdInteract2025}
  & Multi-turn interactive tasks
  & In-context only
  & No cross-session persistence
  & Shows per-session context is insufficient for continuous BI \\
\midrule
MemoryAgent-Bench~\cite{MemoryAgentBench2025}
  & Evaluates long-horizon memory: retrieval, contradiction resolution, semantic constraints
  & External (general-purpose)
  & Domain-agnostic; no BI artifact types or SQL execution
  & Provides conflict resolution test adopted in this thesis \\
\midrule
MemoryArena~\cite{MemoryArena2026}
  & Interdependent multi-session task benchmark
  & External (general-purpose)
  & Conversational; no structured artifact dependencies
  & Provides multi-hop composition test adopted in this thesis \\
\bottomrule
\end{tabularx}
\end{table}

\section{Agent Memory Architectures}

The question of how autonomous agents should store, track, and retrieve information over long horizons has become a highly active research area. Zhang et al.\ provide a comprehensive survey of memory mechanisms in LLM-based agents, identifying four principal paradigms: in-context memory, external retrieval memory, parametric memory, and hybrid approaches~\cite{Zhang2024AgentMemory}.

\textbf{In-context memory} stores information directly within the active context window. While modern LLMs support very large context windows, this approach remains functionally stateless across sessions: context is not persistently structured between conversations. Moreover, research indicates that large context windows behave largely as recency buffers, with retrieval fidelity degrading for information located in the middle of the context~\cite{MemoryAgentBench2025}. This makes in-context memory computationally unscalable as accumulated schemas and artifact histories grow.

\textbf{Retrieval-augmented generation (RAG)} augments the agent's context by retrieving relevant information from an external vector store at query time~\cite{Lewis2020RetrievalAugmentedGF,Gao2024RAGSurvey}. RAG has been applied to a wide range of analytical memory tasks and forms the primary baseline for this thesis. Its central limitation in the BI setting is that retrieval is purely similarity-based: it surfaces passages semantically related to a query, but cannot guarantee finding the correct info and has difficulty navigating conflicting or outdated entries. Even with improvements such as re-ranking and self-reflection, RAG systems remain susceptible to hallucination (confidently generating false or fabricated information) when overlapping or contradictory content competes in the retrieval window~\cite{AyalaBechard2024RAGHallucination}.

\textbf{Episodic and structured memory} approaches give agents more organised representations of their past experiences. MemGPT~\cite{Packer2023MemGPTTL} introduces a hierarchical memory architecture in which agents manage their own context by paging information in and out of a fixed-size window, analogous to virtual memory in operating systems. Generative Agents~\cite{Park2023GenerativeAgents} maintain a chronological memory stream of natural-language observations and synthesise higher-level reflections over time. More recently, A-MEM~\cite{Xu2025AMem} proposes an agentic memory system that dynamically organises memories into interconnected knowledge networks, following principles from the Zettelkasten method. While these approaches demonstrate the value of structured memory management, they are optimised for conversational or general-purpose task execution and are not designed around the artifact types and graph-dependency requirements of SQL-based BI workflows.

Figure \ref{fig:memory-paradign} shows the agent memory landscape as SAM's position in it.

\begin{figure}
    \centering
    \includegraphics[width=0.95\linewidth]{Memory Paradigm.png}
    \caption{Memory Architectures}
    \label{fig:memory-paradign}
\end{figure}

\section{Text-to-SQL and BI Evaluation Benchmarks}

Benchmark methodology has evolved considerably, shifting focus from evaluating SQL correctness towards multi-step reasoning and execution accuracy. The Spider benchmark~\cite{Yu2019SpiderAL} established cross-domain generalisation as a core challenge. BIRD~\cite{Li2023BIRD} extended this to large-scale, real-world databases spanning 37 professional domains, introducing Execution Accuracy (EX) as the primary metric: the predicted SQL is executed against the database and its result set compared directly to the ground truth, without credit for partial matches. Even state-of-the-art systems fall substantially short of the 92.96\% human-level EX on BIRD, with leading models reaching approximately 75\% on the test set~\cite{Li2023BIRD}.

Beyond factual retrieval, the CORGI benchmark~\cite{Corgi2024} evaluates agents on MBA-level strategic tasks, revealing that while LLMs excel at descriptive SQL, they struggle with explanatory and predictive causal reasoning. EvoSchema~\cite{EvoSchema2024} evaluates robustness under simulated schema drift, reflecting the volatile nature of real production databases.

On the memory side, benchmarks such as MemoryArena~\cite{MemoryArena2026} evaluate interdependent multi-session tasks, while MemoryAgentBench~\cite{MemoryAgentBench2025} assesses competence in retrieving historical states, resolving contradictions, and recognising semantic constraints over long intervals. However, a gap remains: current long-term memory benchmarks are largely conversational or domain-agnostic, while robust text-to-SQL benchmarks are fundamentally single-session and stateless. This thesis bridges that divide by synthesising the strict execution methodology with the interdependent multi-session structure from both sides.

\section{Limitations of Existing Approaches}

Three gaps emerge from the reviewed literature. First, general-purpose agent memory architectures are not designed around the artifact types and dependency relationships characteristic of BI work. Second, systems that rely solely on semantic retrieval lack the structural awareness to manage versioned, interdependent artifacts. Third, evaluation of agent memory has largely focused on single-session or knowledge-retrieval tasks; there is no established benchmark for multi-session BI analytical continuity. This thesis addresses all three gaps by proposing a hybrid architecture that combines semantic retrieval with structural memory and evaluating it in multi-session BI scenarios.

%------------------------

\chapter{Problem Analysis and Requirements}

\section{Analytical Workflow Analysis}

To motivate the memory architecture, it is useful to examine the structure of real BI workflows. A typical workflow proceeds roughly as follows:

\begin{enumerate}
    \item \textbf{Schema exploration:} The analyst familiarises themselves with available tables, columns, and relationships.
    \item \textbf{Business definition:} Key business concepts (metrics, classification rules, and analytical criteria, etc.) are defined in terms of the underlying schema. For example, net revenue may be defined as the sum of completed orders minus returns, or a ``high-priority account'' may be defined as customers meeting certain threshold conditions.
    \item \textbf{Query development:} SQL queries are written and validated to compute the defined business concepts.
    \item \textbf{Analysis and insight generation:} Query results are interpreted and findings are recorded.
    \item \textbf{Refinement:} Business definitions are updated in response to new business requirements or discovered data quality issues; dependent queries are revised accordingly.
\end{enumerate}

This workflow is iterative and produces multiple artifacts. Each step creates or modifies a different artifact: a schema understanding, a business definition, or an insight, and artifacts depend on each other in structured ways. A change to a schema definition has downstream consequences for every query that references it. A revised business definition may invalidate prior query results. Critically, this workflow occurs across multiple sessions: an analyst likely does not complete the full cycle in a single sitting. Any memory architecture for a BI agent must support this pattern.

\begin{runningex}{Category Performance Analysis --- Workflow Overview}
The following four-session scenario is used as a concrete illustration throughout this thesis. All artifacts, tool calls, and design decisions referenced in later chapters refer back to this example.

\textbf{Context.} An analyst at Northwind Traders is investigating product category performance across multiple working sessions.

\begin{itemize}
  \item \textbf{Session~1.} The analyst defines \textit{Slow-Selling Product} as any product with fewer than 500 total units sold. She saves this as a definition artifact (\texttt{def\_slow\_selling\_product}, v1) and executes a query that lists all slow-selling products by category.
  \item \textbf{Session~2.} After a product review, the threshold is revised to 350 units. She updates the definition, creating \texttt{def\_slow\_selling\_product} v2 and archiving v1.
  \item \textbf{Session~3.} The analyst defines \textit{Underperforming Category} as any product category containing more than two slow-selling products. This definition explicitly depends on \textit{Slow-Selling Product}, establishing a dependency edge in the artifact graph.
  \item \textbf{Session~4.} A category manager asks: \textit{``Which categories are underperforming?''} The agent must retrieve \textit{Underperforming Category}, traverse the dependency edge to \textit{Slow-Selling Product}, use v2 (350 units, not the archived v1), and compose and execute the two-definition SQL query.
\end{itemize}

Using v1 instead of v2 would return a larger, incorrect set of categories. Failing to traverse the dependency edge would force the agent to guess or assume the base threshold.
\end{runningex}

\section{Memory Requirements}

Based on the workflow analysis above, we identify the memory requirements for a BI agent memory system, separated into functional and non-functional categories.

\subsection{Functional Requirements}

The following functional requirements define the specific operations the memory system must be able to perform.

\begin{itemize}
    \item \textbf{Create artifact:} The system must allow the agent to persist typed analytical artifacts with structured metadata across session boundaries.
    \item \textbf{Update version:} Artifacts must support version history, so that prior states can be recovered, changes audited, and the current version  identified even when multiple revisions exist.
    \item \textbf{Resolve dependency:} The system must record and expose dependency relationships between artifacts (both upstream and downstream), enabling the agent to identify all artifacts affected by a change through deterministic graph traversal.
    \item \textbf{Trace history:} The agent must be able to determine the origin of any artifact: when it was created, which prior definition it supersedes (if any), and what its version history is, etc., without relying on similarity-based retrieval.
    \item \textbf{Browse by type:} The agent must be able to navigate the memory layer by artifact type and status.
    \item \textbf{Semantic retrieval:} As the number of stored artifacts grows, the agent must be able to search memory by meaning, efficiently locating relevant artifacts under noise without exhausting its token budget through exhaustive index browsing.
\end{itemize}

\subsection{Non-Functional Requirements}

Non-functional requirements define the quality attributes the memory system must satisfy.

\begin{itemize}
    \item \textbf{Latency:} Memory read and write operations must not introduce prohibitive overhead to the agent's response time. \item \textbf{Consistency:} The artifact store, dependency graph, and vector index must remain mutually consistent at all times. Any write, update, or deprecation must be reflected atomically across all three representations.
    \item \textbf{Reproducibility:} Given the same session history, the memory system must return the same artifacts and dependency chains, ensuring that evaluation results are stable and comparable across runs.
    \item \textbf{Modularity:} The memory layer must be cleanly separable from the query execution and agent orchestration layers, allowing either component to be replaced or upgraded independently.
\end{itemize}

Table~\ref{tab:req-traceability} shows how each functional requirement is derived from an observable BI workflow problem and how it is realised by a specific SAM feature.

\begin{runningex}{Category Performance Analysis --- Requirements Triggered}
Each functional requirement maps to a concrete failure that would occur in the analyst's workflow without it.

\begin{itemize}
  \item Without \textbf{Create artifact}, Session~4 begins with no knowledge of either definition; the agent cannot compose the query at all.
  \item Without \textbf{Update version}, the \$500 and \$350 thresholds coexist in memory with equal status; the agent cannot determine which is current and may apply the wrong one.
  \item Without \textbf{Resolve dependency}, updating \textit{Slow-Selling Product} in Session~2 does not propagate to \textit{Underperforming Category}, which would silently depend on a superseded base definition.
  \item Without \textbf{Trace history}, there is no way to determine when \textit{Slow-Selling Product} was revised or which session introduced the change, making auditing and debugging harder.
  \item Without \textbf{Browse by type}, the agent must search all stored items to find definition artifacts, exhausting its token budget in a large workspace.
  \item Without \textbf{Semantic retrieval}, the agent cannot surface \textit{Slow-Selling Product} if the user's query uses different but synonymous phrasing.
\end{itemize}
\end{runningex}

\begin{table}[h]
\centering
\caption{Requirement-to-feature mapping.}
\label{tab:req-traceability}
\small
\renewcommand{\arraystretch}{1.5}
\begin{tabularx}{\textwidth}{p{4.2cm} p{3.2cm} X}
\toprule
\textbf{BI Workflow Problem} & \textbf{Functional\newline Requirement} & \textbf{SAM Feature} \\
\midrule
Analytical context lost between sessions; users must re-supply definitions and schema understanding each conversation.
  & \textbf{Create artifact}
  & Typed JSON artifact documents (\texttt{definition}, \texttt{insight}, \texttt{schema}) persisted in a hierarchical file store via \texttt{save\_definition} / \texttt{save\_insight}; available in all future sessions. \\[4pt]
\midrule
Business definitions are redefined across sessions, leaving conflicting versions with no signal of which is current.
  & \textbf{Update version}
  & \texttt{version} counter and \texttt{history} list on every artifact; \texttt{update\_artifact} snapshots the prior state before applying changes; the latest version is always the canonical document. \\[4pt]
\midrule
Schema or metric changes invalidate downstream insights and dependent definitions, but the agent has no way to identify affected artifacts.
  & \textbf{Resolve \newline dependency}
  & Bidirectional \texttt{dependencies}/\texttt{dependents} fields; \texttt{\_graph.json} adjacency list; \texttt{get\_dependencies} tool for deterministic graph traversal; \texttt{deprecate\_artifact} cascades to dependents. \\[4pt]
\midrule
The origin, creation time, and revision chain of an artifact cannot be determined without browsing unstructured history logs.
  & \textbf{Trace \newline history}
  & \texttt{created\_at}, \texttt{updated\_at}, \texttt{session\_id}, and \texttt{history} fields recorded on every artifact; \texttt{read\_artifact} returns the full provenance chain without similarity-based lookup. \\[4pt]
\midrule
As the artifact store grows, the agent cannot efficiently identify which artifacts are relevant without reading every document.
  & \textbf{Browse by type}
  & \texttt{list\_artifacts} returns the enriched \texttt{\_index.json} for a given type and status filter; index entries include inline summaries so relevance can be assessed without individual reads. \\[4pt]
\midrule
Overlapping vocabulary across multiple definitions (e.g., several shipping-cost metrics) defeats exact-match lookup and exhausts token budgets through exhaustive browsing.
  & \textbf{Semantic \newline retrieval}
  & All artifacts embedded into a FAISS vector store on save/update; \texttt{search\_memory} surfaces relevant artifacts by semantic similarity without exhaustive index traversal. \\
\bottomrule
\end{tabularx}
\end{table}

\section{System Constraints}

The scope of this thesis is limited to single-user, single-project, single-database BI agent settings. A \textit{project} is the natural unit of analytical work in BI: a bounded investigation with a defined database connection, a set of relevant business definitions, and a history of sessions. Multi-project support, multi-user collaboration, distributed databases, and real-time streaming data are out of scope and are identified as directions for future work.

Session management is handled at the application layer, not by the agent. A session corresponds to a single user conversation. This boundary is enforced by the system, ensuring consistent and predictable session structure across evaluation scenarios.

The agent is assumed to operate with a fixed LLM backend. The memory architecture is designed to be model-agnostic, but evaluation is conducted with a specific model configuration.

\section{Design Goals}

Four primary design goals guide the memory architecture:

\begin{itemize}
    \item \textbf{Transparency:} The structure of agent memory should be inspectable by both the agent and the user.
    \item \textbf{Persistence:} Artifacts and their relationships must survive session boundaries without degradation.
    \item \textbf{Modularity:} The memory layer must be cleanly separable from the query execution and agent orchestration layers.
    \item \textbf{Reproducibility:} Given the same session history, the agent should produce consistent results.
\end{itemize}

%------------------------

\chapter{System Architecture}

\section{Overall System Overview}

\subsection{Component Boundaries}

The system is composed of six distinct execution environments, each with a clearly defined responsibility boundary. No component may access the internals of another except through its designated interface.

\begin{table}[h]
\centering
\caption{System component boundaries.}
\label{tab:component-boundaries}
\small
\renewcommand{\arraystretch}{1.4}
\begin{tabularx}{\textwidth}{p{4.0cm} X}
\toprule
\textbf{Component}  & \textbf{Responsibility} \\
\midrule
\textbf{LLM} \newline(Gemini 2.5 Flash)
  & Generates reasoning, tool requests, and final answers.\\
\midrule
\textbf{Orchestrator} \newline (LangGraph, Python)
  & Manages the agent loop: receives LLM output, executes the requested tool, appends the tool result to the conversation, and re-invokes the LLM. Controls session lifecycle and logging. \\
\midrule
\textbf{Tool Interface Layer} (Python)
  & Validates inputs, dispatches to either the structural store or vector index, and formats responses for LLM consumption. Enforces error cases and type constraints. \\
\midrule
\textbf{Structural Store} \newline(JSON files on disk)
  & Persists typed artifact documents, per-type index files, and the global dependency graph (\texttt{\_graph.json}) as UTF-8 JSON. \\
\midrule
\textbf{Vector Index}\newline (FAISS)
  & Stores dense vector representations of artifact text. Supports approximate nearest-neighbour search. Updated synchronously on every write, update, or deprecation. \\
\midrule
\textbf{SQL Engine} \newline(PostgreSQL)
  & Executes read-only analytical queries against the Northwind schema. Returns result sets as formatted text; never writes to the database. \\
\bottomrule
\end{tabularx}
\end{table}

\subsection{Implementation Technology Stack}

Table~\ref{tab:tech-stack} lists the concrete technologies used in this prototype. All choices are fixed for the evaluation; the architecture is designed to be substitutable at each boundary.

\begin{table}[h]
\centering
\caption{Implementation technology stack.}
\label{tab:tech-stack}
\small
\renewcommand{\arraystretch}{1.3}
\begin{tabularx}{\textwidth}{p{3.5cm} X}
\toprule
\textbf{Concern} & \textbf{Technology} \\
\midrule
Programming language & Python 3.12 \\
Agent orchestration framework & LangGraph 1.0.10 \\
Within-session state persistence & LangGraph \texttt{AsyncPostgresSaver} (PostgreSQL-backed checkpointer, keyed by \texttt{thread\_id}) \\
LLM provider and model & Gemini API --- \texttt{gemini-2.5-flash} \\
Embedding model & Gemini API --- \texttt{gemini-embedding-001} \\
Vector index & FAISS \texttt{IndexFlatL2} (in-process, serialised to disk) \\
Structural memory store & UTF-8 JSON files on local file system; no external database \\
SQL database engine & PostgreSQL 16 \\
Database schema & Northwind (orders, customers, products, categories, shippers, employees) \\
Runtime environment & Single-machine Ubuntu 22.04; no GPU; 16 GB RAM \\
\bottomrule
\end{tabularx}
\end{table}

\subsection{High-Level Data Flow}

The system consists of four main components connected through these boundary-defined interfaces: an LLM-based agent, a tool interface layer, a persistent memory store, and a query execution backend. The agent receives natural language instructions from the user and produces analytical outputs by invoking tools. The tool interface layer mediates all interactions between the agent and both the memory store and the query execution backend. The memory store is configurable: it can be a pure vector store (RAG mode) or a structured artifact graph with vector search (SAM mode). The query execution backend handles SQL execution against the target database.

Figure~\ref{fig:architecture} shows the static component diagram. Figures~\ref{fig:seq-success} and~\ref{fig:seq-failure} show dynamic flows: a successful two-session save-and-retrieve scenario, and a failure-and-recovery case where a missing dependency edge is detected and repaired at runtime. The flows follow sessions in our running example.

\begin{figure}
    \centering
    \includegraphics[width=1.05\linewidth]{Architecture.png}
    \label{fig:architecture}
    \caption{System Architecture: component layout and data-flow boundaries.}
\end{figure}

\begin{figure}
    \centering
    \includegraphics[width=1.1\linewidth]{Success Flow.png}
    \caption{Successful flow: agent saves a definition in Session~1 and retrieves and updates it in Session~2.}
    \label{fig:seq-success}
\end{figure}

\begin{figure}
    \centering
    \includegraphics[width=1.1\linewidth]{Failure & Recovery Flow.png}
    \caption{Failure and recovery: missing dependency edge detected in Session~4; agent falls back to \texttt{search\_memory}, recovers the base definition, and repairs the graph via \texttt{link\_artifacts} before answering.}
    \label{fig:seq-failure}
\end{figure}

\section{Agent Workflow}

Sessions are managed by the application layer, not the agent. When a user initiates a conversation, the system assigns a session ID and begins logging all tool calls and artifact interactions.

Within a session, the agent follows a structured operating procedure:

\begin{enumerate}
    \item \textbf{Orientation:} At the start of each session, the agent searches or browses memory to orient itself.
    \item \textbf{Active analysis:} The agent executes queries, creates or updates artifacts (if structural tools are available), and responds to the user. All tool calls are logged automatically.
\end{enumerate}


This design enforces a clean separation of concerns: the agent manages \textit{analytical work}; the system manages \textit{sessions}. Session boundaries are always consistent and predictable, which is important for both correct agent behaviour and reliable evaluation.

\begin{runningex}{Category Performance Analysis --- Session Lifecycle}
\begin{itemize}
  \item \textbf{Session~1 (orientation):} The agent saves \texttt{def\_slow\_selling\_product} (v1, threshold 500)
  \item \textbf{Session~2 (orientation):} The agent calls \texttt{search\_artifacts}, finds \texttt{def\_slow\_selling\_product} v1, and reads it. In the analysis step it calls \texttt{update\_artifact} with the revised threshold (350), producing v2 and archiving v1.
  \item \textbf{Session~3 (orientation):} The agent calls \texttt{search\_artifacts}, reads \texttt{def\_slow\_selling\_product} v2. In the analysis step it saves \texttt{def\_underperforming\_category} with a \texttt{dependencies} field pointing to \texttt{def\_slow\_selling\_product}.
  \item \textbf{Session~4 (orientation):} The agent calls \texttt{search\_artifacts}, reads \texttt{def\_underperforming\_category}. It then calls \texttt{get\_dependencies} to find \texttt{def\_slow\_selling\_product}. In the analysis step it composes and executes the query.
\end{itemize}
At each session boundary the application layer resets the conversation context; the agent re-orients purely from memory --- not from prior chat context.
\end{runningex}

\section{Tool Interface Layer}
\label{sec:tool-ref}

\subsection{Mode Availability}

Each memory mode exposes a different tool set, enabling a controlled comparison. In RAG mode only \texttt{search\_memory} and \texttt{run\_query} are available; memory is populated automatically by the orchestration layer. In SAM mode the full structural tool set is available in addition to semantic search.

\begin{table}[h]
\centering
\caption{Tool availability by memory mode.}
\label{tab:tool-comparison}
\small
\begin{tabularx}{\textwidth}{Xlccc}
\toprule
\textbf{Tool} & \textbf{Purpose} & \textbf{RAG} & \textbf{SAM} \\
\midrule
\texttt{search\_memory} & Semantic similarity search & \checkmark & \checkmark \\
\midrule
\texttt{list\_artifacts} & Browse artifacts by type & & \checkmark \\
\texttt{read\_artifact} & Read full artifact by ID & & \checkmark \\
\texttt{save\_definition} & Create typed business definition & & \checkmark \\
\texttt{save\_insight} & Create analytical insight & & \checkmark \\
\texttt{get\_dependencies} & Traverse dependency graph & & \checkmark \\
\texttt{update\_artifact} & Version-bump with history & & \checkmark \\
\texttt{deprecate\_artifact} & Deprecate with cascade flagging & & \checkmark \\
\texttt{link\_artifacts} & Add semantic relationship between artifacts & & \checkmark \\
\midrule
\texttt{run\_query} & Execute SQL against database & \checkmark & \checkmark \\
\bottomrule
\end{tabularx}
\end{table}

\subsection{Tool Reference}
\label{sec:tool-reference}

The following tables document every tool with its input parameters, output format, error cases, and a representative example call. This specification is derived directly from the Python tool implementations and serves as the interface contract between the LLM and the rest of the system.

\newline
\bigskip
\noindent\textbf{\texttt{search\_memory}}
\begin{table}[H]
\centering\small\renewcommand{\arraystretch}{1.3}
\begin{tabularx}{\textwidth}{p{2.8cm} p{1.4cm} X}
\toprule
\textbf{Parameter} & \textbf{Type} & \textbf{Description} \\
\midrule
\texttt{query} & str & Natural-language search string. \\
\texttt{k} & int & Number of results (default: 5). \\
\texttt{artifact\_type} & str? & Optional type filter: \texttt{schema}, \texttt{metric}, \texttt{insight}. \\
\midrule
\textbf{Output} & \multicolumn{2}{p{10cm}}{Ranked list of matches with ID, type, similarity score, and 120-char content preview.} \\
\textbf{Error cases} & \multicolumn{2}{p{10cm}}{Returns ``No results found'' if the index is empty.} \\
\midrule
\textbf{Example} & \multicolumn{2}{p{10cm}}{\texttt{search\_memory(query="slow selling product", k=3, artifact\_type="metric")}} \\
\bottomrule
\end{tabularx}
\end{table}

\bigskip
\noindent\textbf{\texttt{list\_artifacts}}
\begin{table}[H]
\centering\small\renewcommand{\arraystretch}{1.3}
\begin{tabularx}{\textwidth}{p{2.8cm} p{1.4cm} X}
\toprule
\textbf{Parameter} & \textbf{Type} & \textbf{Description} \\
\midrule
\texttt{artifact\_type} & str & Required. One of: \texttt{schema}, \texttt{metric}, \texttt{insight}. \\
\texttt{status} & str? & Optional filter: \texttt{active}, \texttt{deprecated}, \texttt{superseded}. \\
\midrule
\textbf{Output} & \multicolumn{2}{p{10cm}}{Formatted index listing: ID, name, version, status, and inline summary for each entry.} \\
\textbf{Error cases} & \multicolumn{2}{p{10cm}}{Returns error string if \texttt{artifact\_type} is unrecognised.} \\
\midrule
\textbf{Example} & \multicolumn{2}{p{10cm}}{\texttt{list\_artifacts(artifact\_type="metric", status="active")}} \\
\bottomrule
\end{tabularx}
\end{table}

\bigskip
\noindent\textbf{\texttt{read\_artifact}}
\begin{table}[H]
\centering\small\renewcommand{\arraystretch}{1.3}
\begin{tabularx}{\textwidth}{p{2.8cm} p{1.4cm} X}
\toprule
\textbf{Parameter} & \textbf{Type} & \textbf{Description} \\
\midrule
\texttt{artifact\_id} & str & Unique artifact ID (e.g., \texttt{def\_slow\_selling\_product}). \\
\midrule
\textbf{Output} & \multicolumn{2}{p{10cm}}{Full artifact JSON including all metadata, type-specific fields, dependencies, and version history.} \\
\textbf{Error cases} & \multicolumn{2}{p{10cm}}{Returns \texttt{❌ Artifact not found} if ID does not exist.} \\
\midrule
\textbf{Example} & \multicolumn{2}{p{10cm}}{\texttt{read\_artifact(artifact\_id="def\_slow\_selling\_product")}} \\
\bottomrule
\end{tabularx}
\end{table}

\bigskip
\noindent\textbf{\texttt{save\_definition}}
\begin{table}[H]
\centering\small\renewcommand{\arraystretch}{1.3}
\begin{tabularx}{\textwidth}{p{2.8cm} p{1.4cm} X}
\toprule
\textbf{Parameter} & \textbf{Type} & \textbf{Description} \\
\midrule
\texttt{name} & str & Human-readable name; used to derive the artifact ID. \\
\texttt{description} & str & What the definition measures or classifies. \\
\texttt{formula} & str & SQL expression or rule. \\
\texttt{dependencies} & list[str]? & IDs of schema or definition artifacts this depends on. \\
\texttt{unit} & str? & Optional measurement unit (e.g., \texttt{USD}, \texttt{\%}). \\
\midrule
\textbf{Output} & \multicolumn{2}{p{10cm}}{Confirmation string with the assigned ID and number of registered dependencies.} \\
\textbf{Error cases} & \multicolumn{2}{p{10cm}}{Returns info string if an identical definition already exists (idempotency check). Emits a warning if no dependencies are specified.} \\
\midrule
\textbf{Example} & \multicolumn{2}{p{10cm}}{\texttt{save\_definition(name="Slow-Selling Product", description="...", formula="SUM(quantity)<350", dependencies=["schema/order\_details"])}} \\
\bottomrule
\end{tabularx}
\end{table}

\bigskip
\noindent\textbf{\texttt{save\_insight}}
\begin{table}[H]
\centering\small\renewcommand{\arraystretch}{1.3}
\begin{tabularx}{\textwidth}{p{2.8cm} p{1.4cm} X}
\toprule
\textbf{Parameter} & \textbf{Type} & \textbf{Description} \\
\midrule
\texttt{finding} & str & The analytical observation or conclusion. \\
\texttt{supporting\_\newline artifact\_ids} & list[str]? & IDs of definitions or schema artifacts that support this finding. \\
\texttt{confidence} & str & \texttt{high}, \texttt{medium}, or \texttt{low} (default: \texttt{medium}). \\
\midrule
\textbf{Output} & \multicolumn{2}{p{10cm}}{Confirmation string with the auto-generated insight ID.} \\
\textbf{Error cases} & \multicolumn{2}{p{10cm}}{Returns error string if \texttt{confidence} value is not one of the accepted values.} \\
\midrule
\textbf{Example} & \multicolumn{2}{p{10cm}}{\texttt{save\_insight(finding="31 products are slow-selling under the 350-unit threshold.", supporting\_artifact\_ids=["def\_slow\_selling\_product"], confidence="high")}} \\
\bottomrule
\end{tabularx}
\end{table}

\bigskip
\noindent\textbf{\texttt{get\_dependencies}}
\begin{table}[H]
\centering\small\renewcommand{\arraystretch}{1.3}
\begin{tabularx}{\textwidth}{p{2.8cm} p{1.4cm} X}
\toprule
\textbf{Parameter} & \textbf{Type} & \textbf{Description} \\
\midrule
\texttt{artifact\_id} & str & ID of the artifact to inspect. \\
\texttt{direction} & str & \texttt{up} (dependencies), \texttt{down} (dependents), or \texttt{both} (default). \\
\midrule
\textbf{Output} & \multicolumn{2}{p{10cm}}{Upstream and/or downstream dependency lists with relationship types.} \\
\textbf{Error cases} & \multicolumn{2}{p{10cm}}{Returns error string if \texttt{direction} is not one of the three accepted values.} \\
\midrule
\textbf{Example} & \multicolumn{2}{p{10cm}}{\texttt{get\_dependencies(artifact\_id="def\_underperforming\_category", direction="up")}} \\
\bottomrule
\end{tabularx}
\end{table}

\bigskip
\noindent\textbf{\texttt{update\_artifact}}
\begin{table}[H]
\centering\small\renewcommand{\arraystretch}{1.3}
\begin{tabularx}{\textwidth}{p{2.8cm} p{1.4cm} X}
\toprule
\textbf{Parameter} & \textbf{Type} & \textbf{Description} \\
\midrule
\texttt{artifact\_id} & str & ID of the artifact to update. \\
\texttt{payload\_changes} & dict & Key-value pairs of fields to overwrite in the artifact. \\
\texttt{reason} & str? & Human-readable reason for the update. \\
\midrule
\textbf{Output} & \multicolumn{2}{p{10cm}}{Confirmation string with new version number. The prior version is archived as \texttt{\{id\}\_v\{n\}.json}.} \\
\textbf{Error cases} & \multicolumn{2}{p{10cm}}{Returns error string if artifact ID does not exist.} \\
\midrule
\textbf{Example} & \multicolumn{2}{p{10cm}}{\texttt{update\_artifact(artifact\_id="def\_slow\_selling\_product", payload\_changes=\{"formula": "SUM(quantity)<350"\}, reason="Threshold revised after product review")}} \\
\bottomrule
\end{tabularx}
\end{table}

\bigskip
\noindent\textbf{\texttt{deprecate\_artifact}}
\begin{table}[H]
\centering\small\renewcommand{\arraystretch}{1.3}
\begin{tabularx}{\textwidth}{p{2.8cm} p{1.4cm} X}
\toprule
\textbf{Parameter} & \textbf{Type} & \textbf{Description} \\
\midrule
\texttt{artifact\_id} & str & ID of the artifact to deprecate. \\
\texttt{reason} & str? & Why it is being deprecated. \\
\texttt{replaced\_by} & str? & Optional ID of the successor artifact. \\
\midrule
\textbf{Output} & \multicolumn{2}{p{10cm}}{Confirmation string; reports how many downstream dependents received drift warnings.} \\
\textbf{Error cases} & \multicolumn{2}{p{10cm}}{Returns error string if artifact ID does not exist.} \\
\midrule
\textbf{Example} & \multicolumn{2}{p{10cm}}{\texttt{deprecate\_artifact(artifact\_id="def\_slow\_selling\_product\_v1", reason="Superseded by v2 threshold", replaced\_by="def\_slow\_selling\_product")}} \\
\bottomrule
\end{tabularx}
\end{table}

\bigskip
\noindent\textbf{\texttt{link\_artifacts}}
\begin{table}[H]
\centering\small\renewcommand{\arraystretch}{1.3}
\begin{tabularx}{\textwidth}{p{2.8cm} p{1.4cm} X}
\toprule
\textbf{Parameter} & \textbf{Type} & \textbf{Description} \\
\midrule
\texttt{from\_id} & str & Source artifact ID. \\
\texttt{to\_id} & str & Target artifact ID. \\
\texttt{relationship} & str & One of: \texttt{refines}, \texttt{contradicts}, \texttt{validates}. \\
\midrule
\textbf{Output} & \multicolumn{2}{p{10cm}}{Confirmation string with the recorded edge.} \\
\textbf{Error cases} & \multicolumn{2}{p{10cm}}{Returns error string if \texttt{relationship} is not one of the accepted values.} \\
\midrule
\textbf{Example} & \multicolumn{2}{p{10cm}}{\texttt{link\_artifacts(from\_id="def\_underperforming\_category", to\_id="def\_slow\_selling\_product", relationship="refines")}} \\
\bottomrule
\end{tabularx}
\end{table}

\bigskip
\noindent\textbf{\texttt{run\_query}}
\begin{table}[H]
\centering\small\renewcommand{\arraystretch}{1.3}
\begin{tabularx}{\textwidth}{p{2.8cm} p{1.4cm} X}
\toprule
\textbf{Parameter} & \textbf{Type} & \textbf{Description} \\
\midrule
\texttt{sql} & str & SQL statement to execute against the PostgreSQL database. \\
\midrule
\textbf{Output} & \multicolumn{2}{p{10cm}}{Formatted result table (column headers + rows) as a string. Empty result sets return a ``0 rows returned'' message.} \\
\textbf{Error cases} & \multicolumn{2}{p{10cm}}{SQL syntax errors and connection failures are caught and returned as error strings; the agent can retry with corrected SQL.} \\
\midrule
\textbf{Example} & \multicolumn{2}{p{10cm}}{\texttt{run\_query(sql="SELECT category\_name FROM categories WHERE category\_id IN (SELECT ...)")}} \\
\bottomrule
\end{tabularx}
\end{table}

\section{Orchestration Framework}

The agent loop is implemented in Python using LangGraph. Each agent step is a deterministic node in a directed graph: the LLM node generates a response (which may be a tool call or a final answer), the tool dispatcher node executes the requested tool via the tool interface layer, and the result is appended to the conversation state before the LLM node is re-invoked.

The system maintains two distinct layers of memory with different scopes:

\begin{itemize}
  \item \textbf{Within-session rolling context.} A PostgreSQL-backed LangGraph checkpointer (\texttt{AsyncPostgresSaver}) persists the full LangGraph state, keyed by the session's \texttt{thread\_id}. The agent state tracks two message lists: a complete tool-execution trace (used for debugging and streaming) and a compact \texttt{chat\_messages} list from which the next-turn LLM input is constructed. The latter is capped at a sliding window of 80 messages to bound token cost as sessions grow. This rolling-window approach is relatively standard in agent systems.
  \item \textbf{Cross-session analytical memory.} When a new session begins, a new \texttt{thread\_id} is assigned and the LangGraph state resets; the agent has no access to prior conversations through the checkpointer. Analytical artifacts written to the SAM file store and FAISS index survive this reset and are the exclusive mechanism through which the agent carries knowledge across session boundaries.
\end{itemize}

This separation is by design: the checkpointer handles episodic, within-session continuity (so the agent can follow a multi-turn conversation coherently); SAM or RAG handles semantic, cross-session analytical continuity (so definitions, insights, and dependency relationships persist between work sessions). The evaluation scenarios each span multiple sessions, meaning the agent must rely entirely on the memory layer to answer correctly.

%------------------------

\chapter{Persistent Memory Design}

% Add memory definition + role

\section{Key Terms}
\label{sec:formal-defs}

The following terms are used consistently throughout this chapter. They are defined here to establish a shared vocabulary rather than to provide formal proofs.

\textbf{Artifact.} An artifact is a named, typed JSON document that the agent explicitly saves to the filesystem. Every artifact carries a unique identifier, a type, a lifecycle status (\texttt{active}, \texttt{deprecated}, or \texttt{superseded}), a version number, a set of type-specific fields, bidirectional dependency links (what it depends on and what depends on it), and an ordered history of prior-version snapshot filenames. The full structure is described in Section~\ref{sec:artifact-rep}.

\textbf{Artifact type.} The system recognises three artifact types: \texttt{schema}, \texttt{definition}, and \texttt{insight}. The type determines which type-specific fields the document contains and which subdirectory it is stored in.

\textbf{Version.} A version is a monotonically increasing integer attached to an artifact. Each call to \texttt{update\_artifact} copies the current document to a snapshot file before applying changes and incrementing the counter. The document with the highest version number and status \texttt{active} is always the canonical reference.

\textbf{Dependency edge.} A dependency edge is a directed link from one artifact to another recorded in \texttt{\_graph.json}. Edges can be created automatically when an artifact lists another in its \texttt{dependencies} field; or declared explicitly by the agent via \texttt{link\_artifacts}.

\textbf{Artifact graph and acyclicity.} All artifacts and their dependency edges form a directed graph stored as a flat adjacency list in \texttt{\_graph.json}. Under the intended usage pattern this graph is acyclic (a DAG): structural edges always point from an upstream dependency toward the artifact that uses it, so they cannot form cycles by construction. Agent-declared edges via \texttt{link\_artifacts} are not validated for acyclicity at write time, so a cycle is theoretically possible if the agent creates a back-edge. In practice the evaluation scenarios produce no cycles. Because \texttt{get\_dependencies} performs a single-hop scan rather than recursive traversal, no infinite loop occurs within a single tool call even if a cycle exists.

\textbf{Provenance path.} The provenance path of an artifact is the ordered sequence of its past versions, reconstructed by reading the snapshot filenames recorded in its \texttt{history} field. It exposes the complete revision chain: when each version was created, the reason for each update, and the session in which the change was made.

\textbf{Retrieval result.} A retrieval result is the ranked list of artifacts returned by \texttt{search\_memory}. Each entry carries the artifact ID, type, a similarity score (L2 distance from FAISS — lower is more similar), and a short content preview. Retrieval results are candidates for subsequent status filtering and graph expansion before being used to construct analytical context.

\section{Memory Model}
\label{sec:memory-model}

The SAM layer is organized as a typed artifact graph. All analytical artifacts produced or consumed by the agent are stored as typed JSON documents in a hierarchical file structure:

\begin{lstlisting}[language=bash]
memory/
  schema/
    {table_name}.json
    _index.json
  definitions/
    {definition_name}.json
    _index.json
  insights/
    {insight_id}.json
    _index.json
  _graph.json
\end{lstlisting}

The \texttt{\_index.json} file in each directory is a lightweight registry of all artifacts of that type, containing IDs, names, statuses, versions, timestamps, and an inline summary preview (formula for business definitions, finding for insights, truncated to 120 characters). This enriched index allows the agent to assess artifact relevance directly from \texttt{list\_artifacts} output without issuing individual \texttt{read\_artifact} calls for every entry, substantially reducing tool call overhead. The \texttt{\_graph.json} file records dependency edges across all artifact types, enabling efficient traversal of the dependency graph without loading individual artifact documents.
Aside from the index, the artifacts are also saved into FAISS to enable semantic search.

\begin{runningex}{Category Performance Analysis --- File-Store Layout}
After Session~3, SAM contains the following structure:

\begin{itemize}
  \item \texttt{definitions/def\_slow\_selling\_product.json} --- active, v2 (threshold 350); v1 snapshot archived as \texttt{def\_slow\_selling\_product\_v1.json}.
  \item \texttt{definitions/def\_underperforming\_category.json} --- active, v1; \texttt{dependencies} field contains \texttt{["def\_slow\_selling\_product"]}.
  \item \texttt{insights/ins\_slow\_product\_summary.json} --- an insight recorded by the analyst from the Session~1 analysis, with \texttt{dependencies} pointing to \texttt{["def\_slow\_selling\_product"]}.
  \item \texttt{definitions/\_index.json} --- lightweight registry listing both definitions with their current version, status, and a 120-character summary of their formula.
  \item \texttt{\_graph.json} --- records two edges: \texttt{ins\_slow\_product\_summary} $\to$ \texttt{def\_slow\_selling\_product} and \texttt{def\_underperforming\_category} $\to$ \texttt{def\_slow\_selling\_product}.
\end{itemize}

In Session~4, the agent calls \texttt{list\_artifacts(type=definition)} to read the index (no full-document reads required), then issues a single \texttt{get\_dependencies} call to confirm the version of the base definition before composing the query.
\end{runningex}

\section{Artifact Representation}
\label{sec:artifact-rep}

All artifacts share a common base structure defined by the fields in Definition~\ref{sec:formal-defs}. 

Type-specific fields are fixed by the Pydantic model schema for each artifact type and stored flat at the top level of the JSON document alongside the base metadata fields --- the agent cannot add arbitrary fields outside the defined schema. For a business definition, the fixed fields are \texttt{name}, \texttt{description}, \texttt{formula}, and optionally \texttt{unit}. For an insight, they are \texttt{finding}, \texttt{supporting\_artifact\_ids}, and \texttt{confidence}. For a schema, they are \texttt{table\_name}, \texttt{columns}, \texttt{foreign\_keys}, and \texttt{row\_count\_estimate}.

The \texttt{dependencies} and \texttt{dependents} fields are maintained bidirectionally and updated whenever an artifact is created, modified, or deprecated. This enables efficient impact analysis: when a schema changes, all dependent definitions and insights can be identified in a single graph traversal.

\subsection*{Schema Artifact}

Schema artifacts are the only artifact type not created by the agent. They are populated by a system-level schema introspector (\texttt{sync\_schema}) exposed as the \texttt{POST /schemas/sync} API endpoint. The operator calls this endpoint manually --- typically once before an evaluation run or whenever the database schema changes. The endpoint queries \texttt{information\_schema.columns}, creates a \texttt{SchemaArtifact} for each table, updates it if the column structure has changed since the last sync, and deprecates it if a table is dropped. The agent reads schema artifacts but never writes them.

\begin{lstlisting}[language=json]
{
  "id": "schema/order_details",
  "type": "schema",
  "status": "active",
  "version": 1,
  "session_id": "system_sync",
  "created_at": "2025-01-10T08:55:00",
  "updated_at": "2025-01-10T08:55:00",
  "dependencies": [],
  "dependents": ["def_slow_selling_product"],
  "history": [],
  "table_name": "order_details",
  "row_count_estimate": 2155,
  "columns": [
    {"name": "order_id",   "data_type": "integer", "nullable": false, "is_primary_key": true},
    {"name": "product_id", "data_type": "integer", "nullable": false, "is_primary_key": true},
    {"name": "unit_price", "data_type": "real",    "nullable": false, "is_primary_key": false},
    {"name": "quantity",   "data_type": "smallint","nullable": false, "is_primary_key": false},
    {"name": "discount",   "data_type": "real",    "nullable": false, "is_primary_key": false}
  ],
  "foreign_keys": [
    {"column": "order_id",   "references_table": "orders",   "references_column": "order_id"},
    {"column": "product_id", "references_table": "products", "references_column": "product_id"}
  ]
}
\end{lstlisting}

\subsection*{Definition Artifact}

\begin{lstlisting}[language=json]
{
  "id": "def_slow_selling_product",
  "type": "definition",
  "status": "active",
  "version": 2,
  "session_id": "session_002",
  "created_at": "2025-01-10T09:00:00",
  "updated_at": "2025-01-14T11:30:00",
  "dependencies": ["schema/order_details", "schema/products"],
  "dependents": ["def_underperforming_category"],
  "history": ["def_slow_selling_product_v1"],
  "tags": {"last_update_reason": "Threshold revised to 350 after product review"},
  "name": "Slow-Selling Product",
  "description": "A product with fewer than 350 total units sold across all orders.",
  "formula": "SELECT product_id FROM order_details GROUP BY product_id HAVING SUM(quantity) < 350",
  "unit": null
}
\end{lstlisting}

\subsection*{Insight Artifact}

\begin{lstlisting}[language=json]
{
  "id": "ins_a3f7c1b2",
  "type": "insight",
  "status": "active",
  "version": 1,
  "session_id": "session_001",
  "created_at": "2025-01-10T09:45:00",
  "updated_at": "2025-01-10T09:45:00",
  "dependencies": ["def_slow_selling_product"],
  "dependents": [],
  "history": [],
  "tags": {},
  "finding": "Under the 500-unit threshold, 31 of 77 products qualify as slow-selling. The Seafood and Confections categories account for 58% of these products.",
  "supporting_artifact_ids": ["def_slow_selling_product"],
  "confidence": "high"
}
\end{lstlisting}


\begin{runningex}{Category Performance Analysis --- Artifact Document (v2)}
After Session~2, \texttt{def\_slow\_selling\_product.json} has the following structure:

\begin{lstlisting}[language=json, frame=none, xleftmargin=0em, xrightmargin=0em]
{
  "id": "def_slow_selling_product",
  "type": "definition",
  "status": "active",
  "version": 2,
  "history": ["def_slow_selling_product_v1"],
  "created_at": "2025-01-10T09:00:00",
  "updated_at": "2025-01-14T11:30:00",
  "session_id": "session_002",
  "dependencies": ["schema/order_details", "schema/products"],
  "dependents": ["def_underperforming_category"],
  "description": "Products with fewer than 350 total units sold.",
  "formula": "SUM(order_details.quantity) < 350 GROUP BY product_id"
}
\end{lstlisting}

The \texttt{history} field preserves the filename of the v1 snapshot (threshold 500). The \texttt{dependents} field links forward to \texttt{def\_underperforming\_category} from Session~3, enabling SAM to flag it as built on a now-updated base when \texttt{update\_artifact} was called in Session~2.
\end{runningex}

\begin{figure}
    \centering
    \includegraphics[width=0.7\linewidth]{Artifact.png}
    \caption{Artifact Dependency Structure}
    \label{fig:artifact}
\end{figure}


\section{Memory API}
\label{sec:memory-api}

The SAM API is the set of tools through which the agent interacts with the memory layer. A key design principle is the system automatically records everything it can, such that the agent's tool responsibilities are limited to operations that require judgment or interpretation.


The following pseudocode describes the core operations. All file I/O uses atomic write (write to a temporary file, then rename) to prevent partial-write corruption.

\paragraph{Create.} Invoked via \texttt{save\_definition} or \texttt{save\_insight}.

\begin{lstlisting}[language=python, caption={Pseudocode: create artifact}]
def create(name, type, payload, dependencies=[]):
    id = normalise(name)          # lowercase, spaces to underscores
    if store.exists(id) and store.read(id).payload == payload:
        return ALREADY_EXISTS     # idempotency check
    a = Artifact(id, type, status=ACTIVE, version=1,
                 payload=payload, dependencies=dependencies)
    store.write_json(path(type, id), a)  # atomic write
    index[type].upsert(id, summary(a))   # update lightweight index
    for dep_id in dependencies:
        graph.add_edge(dep_id, id, STRUCTURAL)  # upstream -> this
        store.read(dep_id).dependents.append(id) # backlink
    faiss.upsert(id, embed(text(a)))     # update vector index
    return id
\end{lstlisting}

\paragraph{Retrieve.} Invoked via \texttt{read\_artifact}.

\begin{lstlisting}[language=python, caption={Pseudocode: retrieve artifact by ID}]
def retrieve(id):
    for type in [SCHEMA, METRIC, INSIGHT]:
        path = path(type, id)
        if exists(path):
            return deserialise(read_json(path))  # O(1) lookup
    return NOT_FOUND
\end{lstlisting}

\paragraph{Update version.} Invoked via \texttt{update\_artifact}.

\begin{lstlisting}[language=python, caption={Pseudocode: version-bump update}]
def update_version(id, changes, reason=""):
    a = retrieve(id)          # load current document
    snapshot_id = f"{id}_v{a.version}"
    store.write_json(path(a.type, snapshot_id), a)  # archive old version
    a.history.append(snapshot_id)
    for key, val in changes.items():
        setattr(a, key, val)  # apply field-level changes
    a.version += 1
    a.tags["last_update_reason"] = reason
    store.write_json(path(a.type, id), a)  # overwrite live document
    index[a.type].upsert(id, summary(a))
    faiss.upsert(id, embed(text(a)))  # re-embed at new version
    return a.version
\end{lstlisting}

\paragraph{Resolve dependencies.} Invoked via \texttt{get\_dependencies}.

\begin{lstlisting}[language=python, caption={Pseudocode: single-hop dependency resolution}]
def resolve_dependencies(id, direction="both"):
    edges = graph.read_all_edges()   # read _graph.json once
    result = {"upstream": [], "downstream": []}
    if direction in ("up", "both"):
        result["upstream"]   = [e for e in edges if e.to_id == id]
    if direction in ("down", "both"):
        result["downstream"] = [e for e in edges if e.from_id == id]
    return result
\end{lstlisting}

\noindent Note that this is a single-hop scan: it returns direct neighbours only. Multi-hop traversal requires the agent to issue successive \texttt{get\_dependencies} calls, once per hop. This is intentional: it keeps the operation transparent and auditable, and avoids unbounded traversal in the event that a cycle is introduced by an agent-declared edge.

\paragraph{Trace history.} Invoked via \texttt{read\_artifact} applied to each entry in \texttt{history}.

\begin{lstlisting}[language=python, caption={Pseudocode: trace full provenance chain}]
def trace_provenance(id):
    current = retrieve(id)     # load live document
    chain   = [current]
    for snapshot_id in current.history:  # ordered oldest -> newest-1
        snap = retrieve(snapshot_id)
        chain.insert(0, snap)  # prepend to get chronological order
    return chain
    # chain[0] = v1 (original), chain[-1] = current live version
\end{lstlisting}

\section{Memory Retrieval Strategy}
\label{sec:retrieval-pipeline}

The SAM mode can be understood as RAG extended with a structural layer. Both use the same embedding model for semantic search. What SAM adds is a typed artifact graph with three capabilities that semantic retrieval cannot replicate:

\begin{enumerate}
    \item \textbf{Dependency graph:} Bidirectional edges between artifacts. Enables deterministic traversal: ``what definitions use this schema?'' or ``what depends on this definition?''
    \item \textbf{Version history:} Each artifact maintains an ordered version chain, allowing the agent to identify the canonical (latest, active) version without relying on similarity ranking.
    \item \textbf{Status filtering:} Deprecated or superseded artifacts can be excluded by status field, removing them from consideration without any embedding-distance comparison.
\end{enumerate}

\subsection*{Retrieval Pipeline (Step by Step)}

When the agent issues a \texttt{search\_memory} call, the following pipeline executes:

\begin{enumerate}

  \item \textbf{Query embedding.} The natural-language query string $q$ is encoded into a dense vector $\mathbf{q} \in \mathbb{R}^d$ using \texttt{gemini-embedding-001}. This model produces 768-dimensional embeddings. The encoding is performed synchronously; no caching of query vectors is used.

  \item \textbf{Top-$k$ semantic search.} The FAISS index (\texttt{IndexFlatL2}) is searched for the $k$ stored artifact vectors nearest to $\mathbf{q}$ under L2 distance:
  \[
    \mathcal{R} = \underset{a_i \in V}{\operatorname{argtop-}k}\; \|\mathbf{q} - \mathbf{v}_i\|_2
  \]
  where $\mathbf{v}_i$ is the embedding of artifact $a_i$. The default value is $k = 5$. This value was chosen to balance recall against context length: in evaluation workspaces of up to 200 artifacts (100 analytical plus 100 noise items), $k = 5$ is sufficient to surface the relevant definition while keeping the serialised results short enough for the LLM to process without truncation. Increasing $k$ to 10 in pilot experiments did not improve accuracy and visibly increased token consumption.

  \item \textbf{Candidate filtering.} If an \texttt{artifact\_type} filter is supplied, results whose stored \texttt{type} metadata does not match are removed from $\mathcal{R}$ before returning to the caller. This filtering is applied post-search in Python (not inside FAISS), using the metadata stored alongside each document at write time.

  \item \textbf{Graph expansion (SAM only).} After \texttt{search\_memory} returns candidate IDs, the agent may follow up with \texttt{get\_dependencies} to expand the result set along dependency edges. For example, retrieving \texttt{def\_underperforming\_category} and then calling \texttt{get\_dependencies(direction=``up'')} surfaces \texttt{def\_slow\_selling\_product} without requiring a second semantic search. This one-hop graph expansion is the primary mechanism through which SAM resolves multi-hop composition tasks.

  \item \textbf{Version selection.} Before reading any retrieved artifact, the agent (or the \texttt{list\_artifacts} tool) may filter by \texttt{status=active} to exclude deprecated and superseded documents. When the agent calls \texttt{read\_artifact} with an ID, it receives the live document (highest version, active status). Archived prior versions (e.g., \texttt{def\_slow\_selling\_product\_v1}) are accessible by ID but are not returned by \texttt{list\_artifacts} unless explicitly requested.

  \item \textbf{Final context construction.} The agent assembles its analytical context from the retrieved and graph-expanded artifacts. In SAM mode, this context is structured (typed artifact documents with explicit fields). In RAG mode, the context is a flat concatenation of the top-$k$ serialised text chunks along with timestamp, with no structural filtering or graph expansion available.

\end{enumerate}


\begin{runningex}{Category Performance Analysis --- Retrieval in Session~4}
In Session~4, the agent answers \textit{``Which categories are underperforming?''} The two architectures diverge here:

\begin{itemize}
  \item \textbf{RAG.} \texttt{search\_memory} returns \texttt{def\_underperforming\_category} and, with another \texttt{search\_memory} call, both the v1 and v2 snapshots of \texttt{def\_slow\_selling\_product}. The agent must then infer recency from the timestamp. In practice, because multiple versions of the same definition exist alongside distractor artifacts, the newest definition might not appear in the search results, leading to frequent misapplication of the old threshold.
  \item \textbf{SAM.} \texttt{search\_memory(type=definition)} returns only active documents: \texttt{def\_underperforming\_category} (v1) and \texttt{def\_slow\_selling\_product} (v2). The archived v1 snapshot is excluded by its \texttt{status} field. A single \texttt{get\_dependencies} call on \texttt{def\_underperforming\_category} confirms the dependency and the version in use, allowing the agent to compose the correct query without ambiguity.
\end{itemize}

The divergence here is structural, not retrieval quality: both systems use the same FAISS embeddings. The advantage comes mostly from SAM's ability to filter by status and traverse the dependency graph deterministically.
\end{runningex}

%------------------------

\chapter{Implementation}

\section{Development Environment}
\label{sec:dev-env}

The technology stack is listed in Table~\ref{tab:tech-stack} in Chapter~4. This section records the package version constraints and the steps required to reproduce the environment.

\subsection*{Package Version Constraints}

Dependencies are declared in \texttt{pyproject.toml} using minimum-version lower bounds. The constraints for the components most relevant to reproducibility are:

\begin{lstlisting}[language=bash]
python                        3.12
langgraph                    >=1.0.0
langgraph-checkpoint-postgres>=2.0.0
langchain-google-genai       >=2.1.0   # LLM + embedding client
faiss-cpu                    >=1.7.4   # vector index
psycopg[binary]              >=3.2.0   # PostgreSQL driver
fastapi                      >=0.100.0
pydantic                     >=2.0.0
\end{lstlisting}

\noindent The LLM (\texttt{gemini-2.5-flash}) and embedding model (\texttt{gemini-embedding-001}) are accessed via the Gemini API. PostgreSQL 16 runs in a Docker container defined in \texttt{docker-compose.yml}.

\subsection*{Configuration}

All runtime configuration is loaded from a \texttt{.env} file via \texttt{pydantic-settings}. The following variables must be set before any evaluation run:

\begin{lstlisting}[language=bash]
GOOGLE_API_KEY=<Gemini API key>
DATABASE_URL=postgresql://user:password@localhost:5432/langgraph
MEMORY_MODE=rag          # rag | sam
MEMORY_BASE_PATH=memory  # root path of the JSON artifact store
\end{lstlisting}

\noindent \texttt{MEMORY\_MODE} is the primary experiment control: it selects the tool list (Table~\ref{tab:tool-comparison}) and the system prompt injected at the start of each session without requiring any code change.

\subsection*{Installation}

\begin{lstlisting}[language=bash]
git clone <repo> && cd ai-memory-backend
pip install -e .
# fill in GOOGLE_API_KEY and DATABASE_URL
docker compose up -d
# one-time schema sync before the first evaluation run:
curl -X POST http://localhost:8000/schemas/sync
\end{lstlisting}

\section{Project Structure}

The backend source is organized under \texttt{src/} by responsibility:

\begin{lstlisting}[language=bash]
src/
  agents/
    base_agent.py       # LangGraph graph, agent state, tool
  api/
    routes.py           # HTTP endpoints (chat, sessions, schema sync)
    db.py               # session persistence via PostgreSQL
  config/
    settings.py         # environment config (pydantic-settings)
  memory/
    artifact_store.py   # file I/O, indexing, graph, versioning
    models.py           # Pydantic artifact models
    rag_baseline.py     # FAISS vector store wrapper
  tools/
    registry.py         # maps MEMORY_MODE to tool list
    database/
      sql_executor.py          # execute_sql(), row cap, timeout
      schema_introspector.py   # sync_schema()
    memory/
      memory_tools.py   # SAM tools (save_definition, read_artifact...)
      sam_rag_tools.py  # search_memory for hybrid mode
      rag_tools.py      # RAG-only tools and auto-embed logic
\end{lstlisting}

\section{Agent Implementation}
\label{sec:agent-impl}

Both memory modes share the \texttt{BaseAgent} class. The only differences per mode are the tool list bound to the LLM and the system prompt retrieved from the database at the start of each new session.

\paragraph{Agent loop.} The LangGraph graph has two nodes: \texttt{call\_llm} and \texttt{execute\_tools}, connected by a conditional edge \texttt{should\_continue}. If the last message is an \texttt{AIMessage} containing \texttt{tool\_calls}, control passes to \texttt{execute\_tools}; otherwise the graph exits to \texttt{END}. A \texttt{recursion\_limit} of 50 (approximately 25 full tool-call-and-response cycles) is enforced by LangGraph; exceeding it raises a \texttt{GraphRecursionError} which the API returns as an HTTP 500 error. In practice, evaluation scenarios require at most 8--12 tool calls per session.

\paragraph{Tool-calling format.} Tools are registered with the LLM via \texttt{llm.bind\_tools(tools)}, which exposes each tool's name, description, and typed parameter schema to the model. The LLM emits a JSON \texttt{tool\_calls} list embedded in its \texttt{AIMessage}; \texttt{execute\_tools} iterates the list, dispatches each call by name, and wraps the result in a \texttt{ToolMessage} with the original \texttt{tool\_call\_id}. Both success and error outcomes are returned as plain strings, so the LLM always receives a parseable response and can reason about it on the next step.

\paragraph{Error handling.} Tool-level errors (artifact not found, invalid SQL, unrecognised argument values) are caught inside each tool function and returned as descriptive error strings rather than raised Python exceptions. This prevents a single tool failure from terminating the loop: the agent receives the error message as a \texttt{ToolMessage} and can decide to retry, adjust its approach, or report failure to the user. Unhandled exceptions in the API layer are caught by FastAPI's exception handler and returned as HTTP 500 responses.

\paragraph{SQL execution safety.} The \texttt{execute\_sql} function applies three safeguards independently of the system prompt:
\begin{itemize}[noitemsep]
  \item \textbf{Statement timeout.} Every connection sets \texttt{statement\_timeout = 30\,000\,ms}; queries exceeding this are cancelled by PostgreSQL automatically.
  \item \textbf{Row cap.} Any \texttt{SELECT} without an explicit \texttt{LIMIT} clause has \texttt{LIMIT 1000} appended before execution, preventing accidental full-table scans from filling the LLM context window.
  \item \textbf{Error wrapping.} All \texttt{psycopg} exceptions are caught and returned as a formatted error string containing the PostgreSQL error message, allowing the agent to self-correct its SQL.
\end{itemize}
\noindent The connection does not use a PostgreSQL read-only role; write prevention is enforced at the prompt level by instructing the agent to issue only \texttt{SELECT} statements.

\paragraph{Final answer generation.} When the graph exits, the API iterates the \texttt{messages} list in reverse to find the last \texttt{AIMessage} with non-empty text content. If the final step was a pure tool-call message with no subsequent text reply, it falls back to the most recent \texttt{AIMessage} of any kind. The \texttt{content} field of this message is returned to the client as the assistant's reply.

\section{SAM Implementation}
\label{sec:sam-impl}

The file-system layout and artifact JSON formats are described in Chapter~5 (Sections~\ref{sec:memory-model}--\ref{sec:artifact-rep}); pseudocode for all core operations is given in Section~\ref{sec:memory-api}. This section covers the implementation-specific details: corruption recovery, version file naming, and FAISS synchronisation.

\paragraph{Atomic writes.} All JSON writes use a write-to-temp-then-rename pattern (\texttt{tempfile.mkstemp} followed by \texttt{os.replace}). Because \texttt{os.replace} is atomic on POSIX file systems, a crash during a write always leaves either the old complete file or the new complete file --- never a partial document.

\paragraph{Missing artifact and corruption handling.} When \texttt{read\_artifact} is called for an ID that does not exist in any type directory, \texttt{\_find\_artifact} returns \texttt{None}; the tool layer converts this to the human-readable string \texttt{Artifact not found}, which the LLM receives as a \texttt{ToolMessage} and can act on (e.g. by calling \texttt{search\_memory} to locate the correct ID). A malformed JSON file raises \texttt{json.JSONDecodeError} on read; this propagates as a tool error string and does not crash the agent loop.

\paragraph{Version history storage.} When \texttt{update\_artifact} is called, the current live document is copied atomically to \texttt{\{id\}\_v\{n\}.json} (e.g. \texttt{def\_slow\_selling\_product\_v1.json}) before any changes are applied, and the snapshot filename is appended to the live document's \texttt{history} list. Snapshots reside in the same type subdirectory as the live document but are not registered in \texttt{\_index.json}, so \texttt{list\_artifacts} never surfaces them. They are accessible by explicit ID via \texttt{read\_artifact}.

\paragraph{FAISS synchronisation.} The FAISS index is updated synchronously on every write, update, and deprecation: the old document vector is deleted by artifact ID, and the new version is re-embedded and inserted. Index state is persisted to disk after every write via \texttt{FAISS.save\_local}, so the vector store survives process restarts without reindexing.

\section{Performance Considerations}

Index files are kept small by design: they contain only per-artifact metadata and short summaries of at most 120 characters, not full documents, so \texttt{list\_artifacts} completes in a single file read regardless of the number of stored artifacts. Full documents are only read on explicit \texttt{read\_artifact} calls. The dependency graph is a flat edge list in \texttt{\_graph.json}, supporting O(n) single-hop traversal where $n$ is the number of edges --- acceptable for the small artifact scales seen in evaluation.

%------------------------

\chapter{Experimental Evaluation}

\section{Experimental Setup}

Evaluation is conducted on synthetically generated multi-session analytical scenarios over a fixed relational database. The database schema is drawn from the Northwind domain, containing tables for orders, customers, products, shippers, and employees.

Multi-session scenarios simulate the iterative workflow described in Chapter~3: an initial session (or sessions) establishes schema understanding and defines core business definitions; subsequent sessions extend, refine, or debug prior work. Three scenario types are used, each targeting a specific memory capability mapped to an established benchmark dimension.

\begin{enumerate}
    \item \textbf{Accurate retrieval under noise (MemoryAgentBench AR):} The agent must apply a business definition in session~2 that was defined in session~1 alongside three confusingly similar definitions.
    \item \textbf{Conflict resolution (MemoryAgentBench CR):} A business definition is redefined three times across sessions using completely unrelated criteria. The agent must determine which definition is current.
    \item \textbf{Multi-hop composition (MemoryArena):} The agent must answer a question whose answer requires chaining two independently-defined business concepts from different sessions.
\end{enumerate}

\subsection{Experimental Protocol}
\label{sec:protocol}

\textbf{Runs.} Each scenario is executed 100 independent times per memory mode (SAM and RAG), yielding 300 total evaluation runs per mode. Each run uses a freshly constructed session chain with no shared conversation state.

\textbf{Randomisation and reproducibility.} The distractor generation script uses a fixed random seed (\texttt{random.seed(42)}) to ensure that all 100 distractor conversation prompts are identical across SAM and RAG evaluation runs. Both systems therefore face the same noise artifacts in every run. The evaluation scenarios themselves are deterministic (fixed prompts, no sampling variation in the harness).

\textbf{Isolation.} Before each full evaluation run, the framework snapshots the distractor artifact store, clears only the evaluation-specific session data (sessions prefixed \texttt{e2e\_}) from PostgreSQL, and restores the snapshot after the run completes. This ensures distractor artifacts persist across evaluation runs while evaluation artifacts do not bleed into subsequent runs.

\textbf{Failure criteria.} A run is counted as a failure (execution accuracy = 0) if the agent's response does not contain the golden value (Scenarios 1 and 2) or does not identify the correct entities (Scenario 3, assessed by LLM judge).
API timeout or HTTP error runs are not counted in the results.

\textbf{Result storage.} All run records (latency, token counts, executed tool names, execution accuracy, qualitative scores) are persisted to the \texttt{eval\_runs} PostgreSQL table after each scenario run. A JSON backup is also written to \texttt{tests/results/} after each evaluation module completes.

\textbf{Distractor generation.} The distractor artifacts are generated by sending 100 LLM-generated conversation prompts to the live agent API before the evaluation run begins. Prompts are instantiated from 24 Northwind-domain templates using \texttt{random.seed(42)}, covering revenue metrics, product classifications, customer tiers, shipping rules, and employee performance. The templates contain definition instructions (e.g., ``call this metric X'') that cause the agent to save or update artifacts. The resulting artifacts are thematically related to the evaluation scenarios (same domain, similar vocabulary) but use different names and threshold values, creating a realistic noise baseline. No adversarial name-collision distractors (exact same name, wrong definition) are used in this evaluation.

\subsection{Experimental Variables}

Table~\ref{tab:exp-vars} lists all controlled variables.

\begin{table}[h]
\centering
\caption{Experimental variables and their values.}
\label{tab:exp-vars}
\small
\begin{tabularx}{\textwidth}{lX}
\toprule
\textbf{Variable} & \textbf{Value} \\
\midrule
LLM model          & \texttt{gemini-2.5-flash} \\
LLM temperature    & 0.7 \\
Embedding model    & \texttt{gemini-embedding-001} (768-dim) \\
Semantic retrieval top-$k$ & 5 \\
Distractor prompts & 100 (generated from 24 templates, seed 42) \\
Trials per scenario per mode & 100 \\
Evaluation turn timeout & 600s (\texttt{requests.post} timeout) \\
SQL statement timeout & 30s (server-side PostgreSQL) \\
Database & Northwind schema, PostgreSQL 16 (Docker) \\
Random seed & 42 (for distractor generation) \\
Operating System & Ubuntu 22.04 LTS \\
Hardware & 16 GB RAM, x86-64 CPU \\
\bottomrule
\end{tabularx}
\end{table}

\section{Detailed Test Scenarios}

This section provides the full specifications for each evaluation scenario. The custom multi-session testing framework is aligned with the dataset construction methodologies of MemoryArena~\cite{MemoryArena2026} and MemoryAgentBench~\cite{MemoryAgentBench2025}, which focus on interdependent multi-session tasks and incremental multi-turn evaluation, respectively. Each scenario uses neutral, unbiased prompt wording that does not hint at any specific memory architecture, ensuring that any performance difference reflects genuine architectural capability rather than prompt engineering.

\subsection{Scenario 1: Accurate Retrieval Under Noise}

\textbf{Benchmark alignment.} MemoryAgentBench Accurate Retrieval (AR) dimension.

\textbf{Purpose.} This scenario tests whether the agent can correctly identify and apply a specific business definition from memory when multiple semantically similar definitions exist alongside noise. It isolates the agent's ability to disambiguate between overlapping concepts.

\textbf{Why this is challenging.} All four definitions share overlapping vocabulary (``average freight per order''). RAG's autosaving fills up memory more, making it harder to retrieve the correct definition. SAM's more selective saving process means that only relevant information is saved and retrieved.

\textbf{Session structure.}

\begin{enumerate}
    \item \textbf{Session 1: Acquisition.} The user defines four shipping performance business definitions:
    \begin{itemize}
        \item \textit{Shipping Performance Index}: the percentage of orders shipped within 3 days of the order date.
        \item \textit{Shipping Cost Efficiency}: the average freight, but only for orders where the total line item value (\texttt{unit\_price $\times$ quantity}) exceeds \$200.
        \item \textit{Shipping Reliability Score}: the percentage of on-time deliveries for orders shipped to Germany, France, or the UK, where on-time means \texttt{shipped\_date} is at most 1 day after \texttt{required\_date}.
        \item \textit{Order Cost Average}: the average freight across all orders.
    \end{itemize}
    All four definitions use similar phrasing (``shipping performance'') but impose different company-specific thresholds and filters. The exact criteria are business definitions that an LLM cannot infer from the names alone.

    \item \textbf{Session 2: Retrieval.} The user asks: ``We're doing a logistics review for 1997. How efficient was our shipping cost that year? Recall the definition and calculate.'' The agent must:
    \begin{enumerate}
        \item Retrieve the correct definition from among four similarly-worded entries and the distractor artifacts.
        \item Apply the \$200 line item value filter (\texttt{unit\_price $\times$ quantity > 200}).
        \item Filter to the year 1997.
        \item Execute the query and report the result.
    \end{enumerate}
\end{enumerate}
 
\textbf{Golden SQL.}
\begin{verbatim}
SELECT ROUND(AVG(o.freight)::numeric, 2) 
FROM orders o
WHERE EXTRACT(YEAR FROM o.order_date) = 1997 
AND o.order_id IN (
  SELECT od.order_id 
  FROM order_details od 
  GROUP BY od.order_id
  HAVING SUM(od.unit_price * od.quantity) > 200
);
\end{verbatim}
\textbf{Expected value.} The golden SQL computes the average freight for 1997 orders containing line items valued above \$200: \$87.17.

\begin{figure}[h]
    \centering
    \includegraphics[width= \linewidth]{Scenario 1.png}
    \caption{Scenario 1: Accurate Retrieval Under Noise --- session flow and memory interactions.}
    \label{fig:scenario1}
\end{figure}

\subsection{Scenario 2: Conflict Resolution}

\textbf{Benchmark alignment.} MemoryAgentBench Conflict Resolution (CR) dimension.

\textbf{Purpose.} This scenario tests whether the agent can determine the current version of a business definition that has been redefined multiple times with contradictory criteria, without any explicit versioning cues. It isolates the memory system's ability to manage version conflicts.

\textbf{Why this is challenging.} The three definitions for ``High Priority Account'' are completely unrelated. They use different columns, different aggregations, and different thresholds. No semantic similarity signal indicates which is ``most recent''; all three are equally relevant to the query ``How many High Priority Accounts exist?'' SAM's version history provides deterministic access to the latest version. The RAG agent retrieves all three by similarity and must infer recency from context, which it has no reliable mechanism to do.

\textbf{Session structure.}

\begin{enumerate}
    \item \textbf{Session 1: First definition.} The user defines ``High Priority Account'' as customers whose total freight exceeds \$800:
    \begin{quote}
        \texttt{SUM(freight) > 800}
    \end{quote}

    \item \textbf{Session 2: Contradictory redefinition.} The user redefines ``High Priority Account'' as customers located in Germany with more than 10 total orders:
    \begin{quote}
        \texttt{country = 'Germany' AND COUNT(order\_id) > 10}
    \end{quote}
    No explicit instruction is given to forget or supersede the prior definition.

    \item \textbf{Session 3: Second contradictory redefinition.} The user redefines ``High Priority Account'' again as customers who have ordered from more than 4 distinct product categories:
    \begin{quote}
        \texttt{COUNT(DISTINCT category\_id) > 4}
    \end{quote}
    Again, no versioning cue is provided.

    \item \textbf{Session 4: Retrieval.} The user asks: ``How many High Priority Accounts are there?'' The agent must:
    \begin{enumerate}
        \item Determine that the third (most recent) definition is the current one.
        \item Ignore the two prior contradictory definitions.
        \item Execute a query using the correct definition.
    \end{enumerate}
\end{enumerate}

\textbf{Golden SQL.}
\begin{verbatim}
SELECT COUNT(*) FROM (
  SELECT o.customer_id
  FROM orders o
  JOIN order_details od ON o.order_id = od.order_id
  JOIN products p ON od.product_id = p.product_id
  GROUP BY o.customer_id
  HAVING COUNT(DISTINCT p.category_id) > 4
) subquery;
\end{verbatim}

\textbf{Version conflict example.} Table~\ref{tab:hpa-versions} shows the three contradictory definitions and the SQL each one implies. The latest version (v3) is the correct answer in session~4.

\begin{table}[h]
\centering
\caption{Three contradictory versions of ``High Priority Account'' across sessions.}
\label{tab:hpa-versions}
\small
\begin{tabularx}{\textwidth}{llX}
\toprule
\textbf{Session} & \textbf{Version} & \textbf{Definition \& implied SQL} \\
\midrule
Session 1 & v1 (superseded) &
  Total freight $>$ \$800.\newline
  \texttt{SELECT COUNT(DISTINCT customer\_id) FROM orders}
  \texttt{GROUP BY customer\_id HAVING SUM(freight) > 800} \\
\addlinespace
Session 2 & v2 (superseded) &
  Germany customer, $>$10 total orders.\newline
  \texttt{SELECT COUNT(*) FROM customers WHERE country='Germany'}
  \texttt{... HAVING COUNT(order\_id) > 10} \\
\addlinespace
Session 3 & v3 (\textbf{current}) &
  Orders from $>$4 distinct product categories.\newline
  \texttt{SELECT COUNT(*) FROM ... HAVING COUNT(DISTINCT category\_id) > 4}
  $\rightarrow$ \textbf{82 customers} \\
\bottomrule
\end{tabularx}
\end{table}

\textbf{Why the latest version is correct.} Session 4 asks ``How many High Priority Accounts are there?'' with no version cue. The most recent session defines the current business policy: in practice, each redefinition supersedes the prior one because the user is updating a standing rule, not creating a new parallel metric. SAM encodes this by calling \texttt{update\_artifact} on each redefinition, tagging the prior version as historical. The \texttt{version} field in the live artifact always points to the latest definition, so the agent reads v3 directly. RAG retrieves all three by semantic similarity and must infer recency from context alone --- a task for which it has no reliable mechanism.

\begin{figure}[h]
    \centering
    \includegraphics[width=\linewidth]{Scenario 2.png}
    \caption{Scenario 2: Conflict Resolution --- contradictory definitions across sessions.}
    \label{fig:scenario2}
\end{figure}

\subsection{Scenario 3: Multi-Hop Composition}

\textbf{Benchmark alignment.} MemoryArena interdependent multi-session tasks.

\textbf{Purpose.} This scenario tests whether the agent can answer a question that requires chaining two independently-defined business concepts from different sessions into a single query. It isolates the memory system's ability to resolve cross-artifact dependencies.

\textbf{Why this is challenging.} The two definitions are created in separate sessions and use different vocabulary. ``Supplier Review'' in session~2 references ``Underperforming Products'' from session~1, but the query in session~3 asks only about ``Supplier Review''. The agent must recognise the dependency and retrieve both definitions. SAM can traverse the dependency edge from ``Supplier Review'' to ``Underperforming Product''; the RAG agent must retrieve and manually connect two semantically distant fragments (``Supplier Review'' in session~2 does not share vocabulary with the threshold definition in session~1). While possible, this is harder for the agent using RAG, and depends heavily on the underlying LLM's reasoning capability.

\textbf{Session structure.}

\begin{enumerate}
    \item \textbf{Session 1: Base definition.} The user defines ``Underperforming Product'' as any product ordered fewer than 30 times total:
    \begin{quote}
        \texttt{COUNT(order\_id) < 30}
    \end{quote}

    \item \textbf{Session 2: Dependent definition.} The user defines a review policy that depends on the previous definition: if a supplier has more than 2 Underperforming Products, flag them for ``Supplier Review'':
    \begin{quote}
        \texttt{COUNT(underperforming\_products) > 2 $\rightarrow$ Supplier Review}
    \end{quote}

    \item \textbf{Session 3: Retrieval.} The user asks: ``Which suppliers should be flagged for Supplier Review?'' The agent must:
    \begin{enumerate}
        \item Retrieve the ``Supplier Review'' definition from session~2.
        \item Recognise its dependency on ``Underperforming Product'' and retrieve that definition from session~1.
        \item Compose a single SQL query that identifies products ordered fewer than 30 times, groups them by supplier, and filters for suppliers with more than 2 such products.
    \end{enumerate}
\end{enumerate}

\textbf{Golden SQL.}
\begin{verbatim}
SELECT s.company_name, COUNT(p.product_id) as underperforming_count
FROM suppliers s
JOIN products p ON s.supplier_id = p.supplier_id
JOIN (
  SELECT product_id
  FROM order_details
  GROUP BY product_id
  HAVING COUNT(DISTINCT order_id) < 30
) oc ON p.product_id = oc.product_id
GROUP BY s.supplier_id, s.company_name
HAVING COUNT(p.product_id) > 2;
\end{verbatim}

\textbf{Expected value.} The correct answer is 2 suppliers: New Orleans Cajun Delights and Grandma Kelly's Homestead. Execution accuracy is assessed via LLM-as-a-judge, evaluating whether the agent correctly identified the expected entities.

\textbf{Dependency chain.} Figure~\ref{fig:dep-chain} illustrates the artifact graph SAM constructs across the two setup sessions. The agent must traverse the directed edge from \texttt{def\_supplier\_review} to \texttt{def\_underperforming\_product} to access the threshold value (30 orders). Without this edge, the agent in session~3 sees only the top-level ``Supplier Review'' definition and must guess or re-ask for the underlying threshold --- which is what RAG agents do, with high failure rate. Each hop in the chain corresponds to one \texttt{read\_artifact} call; a two-hop path requires exactly two reads.

\begin{figure}[h]
    \centering
    \includegraphics[width=1.1\linewidth]{Dependency Chain.png}
    \caption{Dependency chain in Scenario 3}
    \label{fig:scenario3chain}
\end{figure}

\section{Metrics}
\label{sec:metrics}


\begin{figure}[h]
    \centering
    \includegraphics[width=1.1\linewidth]{Scenario 3.png}
    \caption{Scenario 3: Multi-Hop Composition --- chaining definitions across sessions.}
    \label{fig:scenario3}
\end{figure}

\section{Metrics}
\label{sec:metrics}

The evaluation employs a multi-metric framework, combining quantitative execution checks with qualitative analysis.

\textbf{Execution Accuracy (EX)} is adopted from the BIRD benchmark~\cite{Li2023BIRD}: a golden SQL query is executed against the live database and the agent's numerical output is compared to the ground-truth result within a 5\% tolerance (Scenarios 1 and 2). For Scenario 3, where the output is a set of entity names rather than a number, an LLM judge (\texttt{gemini-3.1-pro-preview}) assesses whether the agent's response correctly identifies both expected suppliers.

\textbf{Latency} is wall-clock time from HTTP request dispatch to full response receipt, measured by the test harness on the host machine. It encompasses LLM inference, all tool executions (including SQL), and any internal retry delays.

\textbf{Token usage} (input + output tokens) is accumulated across all LLM calls within a scenario run and reported from the API's \texttt{usage\_metadata} fields.

\textbf{Qualitative analysis} is performed automatically using \texttt{Gemini 3.1 Pro Preview} as the LLM judge. The judge receives the full reasoning chain across all sessions in a scenario and scores the agent on four rubric dimensions (each 1--5): \textit{analytical continuity}, \textit{memory utilisation}, \textit{reasoning quality}, and \textit{tool efficiency}. Scores are averaged across all 100 runs per mode.

\textbf{Statistical testing.} Accuracy differences between SAM and RAG are assessed using a two-proportion $z$-test (two-sided, $\alpha = 0.05$). Latency and token distributions are compared using the Mann--Whitney $U$ test (two-sided), which makes no normality assumption. Confidence intervals for proportions use the Wilson score method.

\begin{figure}
    \centering
    \includegraphics[width=1.1\linewidth]{Eval.png}
    \caption{Evaluation Flow}
    \label{fig:placeholder}
\end{figure}

\section{Quantitative Results}

\begin{table}[h]
\centering
\caption{Execution accuracy and mean latency per scenario (n=100 runs per mode).}
\label{tab:quantitative-results}
\small
\begin{tabularx}{\textwidth}{
  L
  S[table-format=2.1]
  S[table-format=2.1]
  S[table-format=2.1]
  S[table-format=2.1]
}
\toprule
\textbf{Scenario}
  & {\textbf{RAG EX (\%)}}
  & {\textbf{RAG Lat. (s)}}
  & {\textbf{SAM EX (\%)}}
  & {\textbf{SAM Lat. (s)}} \\
\midrule
Accurate Retrieval    & 91.1 & 17.1 & 94.1 & 34.0 \\
Conflict Resolution   & 69.7 & 37.7 & 86.9 & 66.6 \\
Multi-hop Composition & 28.0 & 26.4 & 85.1 & 41.1 \\
\midrule
\textbf{Overall}      & \textbf{63.0} & \textbf{27.0} & \textbf{88.7} & 47.1 \\
\bottomrule
\end{tabularx}
\end{table}

Latency standard deviations: RAG ranged from 4.0s (Scenario~1) to 8.0s (Scenario~3); SAM ranged from 17.5s (Scenario~1) to 19.8s (Scenario~2). SAM's higher variance reflects occasional multi-step tool chains; RAG's tight distribution reflects its simpler one-shot retrieval path.

\begin{table}[h]
\centering
\caption{Statistical significance of SAM vs.\ RAG accuracy differences (two-proportion $z$-test, $\alpha=0.05$). Wilson 95\% CIs: SAM overall [84.6\%, 91.8\%]; RAG overall [57.4\%, 68.3\%].}
\label{tab:significance}
\small
\begin{tabularx}{\textwidth}{L X X X X X}
\toprule
\textbf{Scenario}
  & {\textbf{SAM (\%)}}
  & {\textbf{RAG (\%)}}
  & {$\boldsymbol{\Delta}$ \textbf{(pp)}}
  & {$\boldsymbol{z}$}
  & \textbf{$p$-value} \\
\midrule
Accurate Retrieval    & 94.1 & 91.1 & {$+3.0$}  & 0.805 & 0.42 \\
Conflict Resolution   & 86.9 & 69.7 & {$+17.2$} & 2.930 & 0.003 \\
Multi-hop Composition & 85.1 & 28.0 & {$+57.1$} & 8.176 & \textless 0.001 \\
\midrule
\textbf{Overall}      & \textbf{88.7} & \textbf{63.0} & {$\mathbf{+25.7}$} & 7.364 & \textless 0.001 \\
\bottomrule
\end{tabularx}
\end{table}

Table~\ref{tab:quantitative-results} summarises accuracy and latency; Table~\ref{tab:significance} shows the statistical test results. The overall SAM advantage is highly significant ($p < 0.001$). Scenario~1 is the exception: the 3.0 pp gap is not significant ($p = 0.42$), consistent with both systems using the same FAISS retrieval layer.

\section{Qualitative Analysis}

In addition to execution accuracy, each scenario is scored by an automated LLM judge on four qualitative dimensions: analytical continuity (1--5), memory utilisation (1--5), reasoning quality (1--5), and tool efficiency (1--5). The judge receives the full reasoning chain: all user prompts, agent responses, and tool invocations across every session in the scenario, ensuring that the assessment captures cross-session behaviour rather than isolated turn quality.

Table~\ref{tab:qualitative-results} summarises the qualitative scores.

\begin{table}[h]
\centering
\caption{Qualitative rubric scores (1--5) from automated LLM-as-a-judge evaluation.}
\label{tab:qualitative-results}
\small
\begin{tabularx}{\textwidth}{Xccc}
\toprule
\textbf{Dimension} & \textbf{RAG} & \textbf{SAM} & \\
\midrule
Analytical Continuity & 3.68 & {4.60}  \\
Memory Utilisation & 3.61 & {4.17} \\
Reasoning Quality & 3.60 & {4.62} \\
Tool Efficiency & 3.47 & {3.83} \\
\midrule
\textbf{Average} & \textbf{3.59} & \textbf{4.31} \\
\bottomrule
\end{tabularx}
\end{table}

\subsection{Reasoning Trace Examples}
\label{sec:traces}

The following excerpts illustrate representative agent reasoning chains. They are drawn from actual evaluation runs and abridged for readability.

\paragraph{SAM --- success (Scenario 3: Multi-Hop Composition).}
In session~3, the SAM agent receives the question ``Which suppliers should be flagged for Supplier Review?'' and proceeds as follows:

\begin{enumerate}[noitemsep]
  \item \texttt{search\_memory(``Supplier Review'')} → returns \texttt{def\_supplier\_review}: ``flag if $>$2 Underperforming Products; depends on \texttt{def\_underperforming\_product}''.
  \item \texttt{read\_artifact(``def\_underperforming\_product'', ``definition'')} → returns: ``ordered fewer than 30 times total''.
  \item \texttt{run\_query(...)}: executes the composed query (products with $<$30 orders grouped by supplier; those with $>$2 such products).
  \item Final answer: ``Based on your definitions, \textbf{New Orleans Cajun Delights} (3 underperforming products) and \textbf{Grandma Kelly's Homestead} (3 underperforming products) should be flagged for Supplier Review.''
\end{enumerate}

\noindent The agent resolved the two-hop chain in three tool calls. The dependency edge traversal in step 2 is structural --- no second similarity search was needed.

\paragraph{RAG --- failure (Scenario 3: Multi-Hop Composition).}
In the same scenario, a typical RAG failure follows this pattern:

\begin{enumerate}[noitemsep]
  \item \texttt{search\_memory(``Supplier Review'')} → returns several distractor artifacts about ``At-Risk Suppliers'' and a fragment of the session~2 conversation turn. The ``Underperforming Product'' definition is not retrieved because the session~1 text uses different vocabulary.
  \item \texttt{run\_query(...)}: the agent constructs a query using an assumed threshold (e.g., ``fewer than 50 orders'') inferred from the ``Supplier Review'' text.
  \item Final answer: lists suppliers using the wrong threshold (4--6 suppliers instead of 2), or answers ``I could not find a stored definition --- please clarify the threshold for an Underperforming Product.''
\end{enumerate}

\noindent This failure mode accounts for the majority of the 72\% RAG failure rate on Scenario~3. The root cause is architectural: RAG has no edge to traverse and relies entirely on whether the first retrieval call happens to surface the upstream definition.

\paragraph{RAG --- success (Scenario 2: Conflict Resolution).}
In the 69.7\% of runs where RAG succeeds on Scenario~2, the agent receives the question ``How many High Priority Accounts are there?'' and proceeds as follows:

\begin{enumerate}[noitemsep]
  \item \texttt{search\_memory(``High Priority Account'')} → returns three contradictory definition chunks, each tagged with its creation timestamp.
  \item The agent reads all three chunks, compares their timestamps within its context window, and infers that the chunk containing the $>4$ categories filter is the most recent.
  \item \texttt{run\_query(...)}: executes the query using the correct $>4$ categories threshold.
  \item Final answer: returns the correct count of exactly 82 customers.
\end{enumerate}

\noindent This approach may fail when the memory index is cluttered and the newest definition is pushed out of the top-$k$ results, or when the LLM prioritises the chunk with the highest embedding similarity over the chunk with the most recent timestamp.

\paragraph{SAM --- failure (Scenario 2: Conflict Resolution).}
In the 13.1\% of runs where SAM fails on Scenario~2, the failure is almost entirely behavioural rather than architectural. The agent proceeds as follows:

\begin{enumerate}[noitemsep]
  \item During the session 2 or 3 redefinition, the agent mistakenly calls \texttt{create\_artifact} with a new name (e.g., ``High Priority Account V2'') instead of calling \texttt{update\_artifact} to explicitly supersede the prior version.
  \item Both versions now persist in the graph with an \texttt{active} status.
  \item In session~4, \texttt{search\_memory(``High Priority Account'')} returns the old definition along with the distractor definitions.
  \item The agent, with no way to know another, newer definition exists, works with the old, degraded definition.
\end{enumerate}

\noindent This failure highlights the system's reliance on the LLM's adherence to the operating procedure: structural memory only provides an advantage if the agent faithfully maintains the graph during encoding.


%------------------------

\chapter{Discussion}

\section{Results Analysis}

The experimental results across three multi-session scenarios demonstrate a consistent pattern: SAM outperforms the RAG baseline on all tasks, with the performance gap widening substantially as task complexity shifts from retrieval to dependency-sensitive reasoning. While these findings are drawn from three synthetic scenarios and should not be over-generalised to all possible BI workflows, they provide controlled empirical support for the thesis's design expectation: semantic retrieval, while necessary, is insufficient for analytical continuity in multi-session BI operations.

\subsection{Accurate Retrieval Under Noise}

The smallest performance gap between SAM and RAG is observed in Scenario~1 (94.1\% vs.\ 91.1\% execution accuracy, $\Delta = +3.0$ pp, $p = 0.42$, not statistically significant). This result is expected: the task primarily tests retrieval quality, and both systems share the same underlying FAISS embedding model. The narrow gap in favour of SAM is attributable to the selectivity of SAM's memory population. In RAG mode, the orchestration layer automatically embeds every conversation turn and query result, causing memory to accumulate noise entries that share vocabulary with the target definition. In SAM mode, the agent saves only explicitly created artifacts, resulting in a lower-noise retrieval pool. This selectivity also manifests in SAM's higher latency on this scenario (34.0s vs.\ 17.1s): structured artifact operations (read, search, dependency traversal) add overhead that a simple vector-store lookup does not incur --- a real cost when structural memory provides no accuracy benefit.

\subsection{Conflict Resolution}

Scenario~2 reveals a pronounced limitation of semantic retrieval: a 17.2-point gap in execution accuracy (69.7\% RAG vs.\ 86.9\% SAM, $z = 2.93$, $p = 0.003$). The task requires determining which of three contradictory definitions is current. While RAG incorporates timestamps into retrieved chunks as a recency cue, this mechanism is probabilistic rather than deterministic. All three definitions embed with similar distances to the retrieval query. If the index contains distractor documents, the most recent version may be pushed out of the top-$k$ retrieval results entirely. Even when all versions are successfully retrieved in the context window, the agent must manually parse and sequence the timestamps to deduce recency --- a task the LLM frequently fails, instead attempting to synthesise the definitions or erroneously prioritising the chunk with the highest embedding similarity.

SAM's version history provides a deterministic solution: the agent calls \texttt{list\_artifacts} or \texttt{read\_artifact} on the ``High Priority Account'' entry and reads the current version field directly. This operation requires no reasoning about recency; the answer is encoded structurally. The residual 13\% failure rate in SAM mode reflects cases where the agent failed to call \texttt{update\_artifact} when redefining the concept in session~3, leaving the prior version as the current entry. This represents an agent instruction-following failure rather than a memory architecture limitation, suggesting that future work should explore prompting strategies or automated triggers to enforce versioning discipline.

\subsection{Multi-Hop Composition}

Scenario~3 shows the most significant divergence: 28.0\% RAG vs.\ 85.1\% SAM ($\Delta = +57.1$ pp, $z = 8.18$, $p < 0.001$). The task requires composing two definitions from separate sessions with no shared vocabulary. Semantic retrieval alone cannot reliably bridge this gap: retrieving ``Supplier Review'' by similarity returns the session~2 definition, but does not surface the ``Underperforming Product'' definition from session~1 unless an additional query explicitly targets it. Even when both definitions are retrieved, RAG agents frequently failed to recognise the dependency relationship and composed queries using an assumed threshold rather than the defined one.

SAM's bidirectional dependency edges provide a direct structural solution: traversing the edge from ``Supplier Review'' to ``Underperforming Product'' surfaces the dependency deterministically, without requiring an additional retrieval call. The agent can then read both definitions and compose the multi-hop SQL in a single pass. The 15\% failure rate in SAM mode is partially explained by cases where the dependency edge was not recorded during session~2 due to agent omission. As with Scenario~2, this reflects instruction-following variability rather than an architectural gap, and motivates future work on automatic dependency detection and enforcement.

\subsection{Latency}

SAM incurs higher mean latency than RAG across all scenarios (overall 47.1s vs.\ 27.0s). This is expected: SAM's structured operations (artifact reads, dependency traversal, FAISS sync on every write) add overhead that a simple vector-store lookup does not incur. The latency cost is the primary practical trade-off of the SAM architecture. It is partially mitigated on tasks that RAG fails --- a 66.6s SAM turn that produces a correct answer is preferable to a 37.7s RAG turn that does not --- but on Scenario~1, where both systems succeed, SAM's higher latency represents a real efficiency cost with no offsetting accuracy gain.

\subsection{Qualitative Scores}

The qualitative rubric scores corroborate the quantitative findings. SAM scores substantially higher on analytical continuity (4.60 vs.\ 3.68) and reasoning quality (4.62 vs.\ 3.60), reflecting its ability to build consistently on prior sessions and construct logically coherent, dependency-aware queries. The memory utilisation gap (4.17 vs.\ 3.61) is also pronounced: RAG agents frequently retrieved irrelevant or outdated artifacts, inflating context without contributing to the task. The tool efficiency gap (3.83 vs.\ 3.47) is the smallest of the four dimensions, consistent with the observation that both systems use similar total tool calls on Scenario~1; the efficiency advantage materialises primarily in Scenarios~2 and~3, where RAG agents issue redundant retrieval calls in failed attempts at conflict resolution.

\section{Failure Cases}

Despite SAM's overall superiority, qualitative inspection reveals systematic failure modes across both architectures. To better understand the boundaries of the evaluated systems, Table~\ref{tab:failure-taxonomy} establishes a taxonomy of observed failures.

\begin{table}[h]
\centering
\caption{Taxonomy of observed evaluation failures.}
\label{tab:failure-taxonomy}
\small
\begin{tabularx}{\textwidth}{L X l}
\toprule
\textbf{Failure Category} & \textbf{Description} & \textbf{Architecture} \\
\midrule
\textbf{Retrieval Failure} & The target artifact is not returned by the vector search, often due to vocabulary mismatch or distractor noise pushing it out of the top-$k$ results. & RAG (primarily) \\
\textbf{Version-selection} & The agent receives multiple contradictory definitions but chooses the wrong one (e.g., misinterpreting timestamps or trusting higher similarity). & RAG \\
\textbf{Dependency-recording} & The agent fails to record a directed edge linking a new metric to its underlying dependencies during an encoding session. & SAM \\
\textbf{LLM Failure} & The underlying LLM fails to adhere to the system prompt (e.g., creating a new artifact instead of updating an existing one, leading to structural duplicates). & Both \\
\textbf{SQL Execution} & The agent retrieves the correct context but writes syntactically invalid SQL, references non-existent columns, or times out. & Both \\
\textbf{Judge/Evaluation} & The agent returns the correct answer, but formatting unpredictability causes the regex or automated LLM judge to mark it as a failure. & Neither (Eval artifact) \\
\bottomrule
\end{tabularx}
\end{table}

The taxonomy highlights a key distinction: RAG failures are predominantly architectural (retrieval and version-selection limits), while SAM failures are predominantly behavioural (LLM instruction-followed and dependency-recording misses). Two specific SAM failure patterns warrant closer examination.

\textbf{Failure to follow workflow} The most common failure mode in SAM is the agent's failure to call \texttt{update\_artifact} when a business definition is redefined by the user. If the agent saves a new definition without versioning the prior one, both entries persist in memory with identical status, replicating the conflict-resolution challenge that SAM is designed to avoid. This failure is not architectural but behavioural: it reflects sensitivity to system prompt adherence and LLM instruction-following reliability. Mitigation strategies include automatic versioning triggers at the orchestration layer (e.g., flagging new saves with duplicate names) and explicit memory audit steps in the agent's operating procedure.


\textbf{Dependency edge omission} In Scenario~3, SAM agents occasionally failed to record the dependency from ``Supplier Review'' to ``Underperforming Product'' in session~2. When this occurred, the agent in session~3 had no structural path to retrieve the base definition, effectively degrading to RAG behaviour. This again depends on the underlying model's performance, though steps could be taken to mitigate the issue.

\section{Scalability}

The file-system implementation used in this evaluation is not designed for large-scale deployments. As the number of artifacts grows, index files grow correspondingly and graph traversal may slow for deep dependency chains. For production use, the SAM backend would be replaced with a proper graph database (e.g., Neo4j), enabling indexed traversal, transactional writes, and concurrent access. However, for the evaluation scale of this thesis (tens to hundreds of artifacts per project), the file-system implementation is adequate. Crucially, the semantic retrieval layer can scale independently of the structural layer. While the prototype evaluation uses FAISS's exact \texttt{IndexFlatL2} (which has $O(N)$ linear search complexity), a real-world deployment would substitute an approximate index (e.g., \texttt{IndexIVFFlat}) to provide sublinear, logarithmic search time as the artifact count grows.

A related scalability concern is context window pressure. As SAM accumulates a large number of artifacts, \texttt{list\_artifacts} responses may grow long enough to approach model context limits. The enriched index design mitigates this by surfacing summaries rather than full payloads, but at very large scale, pagination or hierarchical indexing strategies would be required.

\section{Comparison with Existing Systems}

SAM differs from existing generative BI systems and agent memory architectures in its combination of semantic retrieval with typed structural memory. Systems such as Wren AI~\cite{WrenAI2024} provide semantic layers that improve schema understanding but do not persist analytical artifacts across sessions. RAG-based agent memory systems~\cite{Lewis2020RetrievalAugmentedGF,Gao2024RAGSurvey} provide retrieval but lack the structural capabilities to manage versioned, interdependent artifacts. General-purpose structured memory architectures such as MemGPT~\cite{Packer2023MemGPTTL} and A-MEM~\cite{Xu2025AMem} support richer memory organisation but are not designed around the artifact types and dependency relationships characteristic of BI work.

The results support the thesis's positioning: SAM is not a general improvement over RAG, but a domain-adapted complement to it. On Scenario~1, the retrieval-dominated task, the two systems perform comparably. The structural advantage of SAM is concentrated on tasks that semantic retrieval cannot inherently solve: conflict resolution and multi-hop dependency composition. This finding is consistent with the broader argument in Zhang et al.\ \cite{Zhang2024AgentMemory} that effective agent memory architectures should combine general-purpose retrieval with domain-specific structural organisation.

\section{Threats to Validity}

\subsection{External Construct Validity}

\textbf{Synthetic evaluation scenarios.} The primary threat to external validity is that the three evaluation scenarios are synthetically constructed to stress-test specific memory capabilities. While this design enables controlled comparison, it may not capture the full diversity of real enterprise BI workflows, which involve more heterogeneous schema environments, greater definitional ambiguity, and longer analytical chains than the scenarios used here. Future work should validate the findings against human-authored BI tasks.

\textbf{Single LLM backend.} All experiments use Gemini 2.5 Flash as the underlying model. Results may vary across model families and sizes, and a stronger model may follow versioning and dependency-recording instructions more reliably, increasing SAM performance. A better model would also be able to trace relationships between artifacts more reliably in RAG mode, reducing the gap.

\subsection{Internal Validity}

Several internal validity threats were identified and mitigated during the evaluation protocol design:

\textbf{Prompt sensitivity.} LLM agents are highly sensitive to prompt wording, which could artificially favour one architecture. \textit{Mitigation:} The shared system prompt and the evaluation scenarios use neutral vocabulary (e.g., ``remember this'' rather than ``create a definition''), ensuring performance differences stem from tool availability rather than prompt bias.

\textbf{API nondeterminism.} Commercial LLMs exhibit latent nondeterminism even at low temperatures, introducing variance into execution and latency metrics. \textit{Mitigation:} Each scenario is executed 100 times per mode, providing sufficient sample size to smooth variance and achieve rigorous statistical significance.

\textbf{LLM version changes.} Silent model updates during the evaluation period could invalidate comparisons across architectures. \textit{Mitigation:} All experiments were executed within a compressed window using the frozen \texttt{gemini-2.5-flash} release, ensuring the underlying model weights remained constant.

\textbf{Judge bias.} The LLM-as-a-judge could exhibit bias towards longer reasoning traces (verbosity bias) or specific formatting. \textit{Mitigation:} The judge uses a stricter, more capable model (\texttt{gemini-3.1-pro-preview}) guided by a rigid, four-dimension rubric. 

\textbf{Experimental leakage.} The distractor artifacts could inadvertently overlap with or bias the evaluation scenarios if not carefully isolated. \textit{Mitigation:} Distractor artifacts were generated separately using a fixed seed (\texttt{random.seed(42)}) and pre-populated into the database snapshot before any evaluation runs commenced, guaranteeing identical, zero-leakage noise distribution for every trial.

%------------------------

\chapter{Conclusion and Future Work}

\section{Summary of Contributions}

This thesis proposed and evaluated the Structured Artifact Memory (SAM) architecture for generative business intelligence agents. By testing SAM against a semantic retrieval (RAG) baseline across three multi-session scenarios, the evaluation directly addresses the thesis's three core research questions:

\textbf{RQ1: Analytical Continuity.} The hybrid SAM architecture substantially improves a generative BI agent's ability to maintain analytical continuity. Overall, SAM achieved an 88.7\% execution accuracy compared to the RAG baseline's 63.0\%, representing a statistically significant 25.7 percentage point improvement ($z = 7.36$, $p < 0.001$). Qualitative LLM-as-a-judge scores corroborate this finding, with SAM outperforming RAG in analytical continuity (4.60 vs.\ 3.68) and reasoning quality (4.62 vs.\ 3.60).

\textbf{RQ2: Addressing Semantic Retrieval Limitations.} The evaluation revealed that structural memory addresses RAG's limitations primarily by enabling deterministic versioning and explicit dependency traversal. On tasks requiring conflict resolution between evolving definitions (Scenario~2), SAM's version history eliminated the probabilistic timestamp-parsing required by RAG, improving accuracy from 69.7\% to 86.9\% ($p = 0.003$). On tasks requiring multi-hop composition (Scenario~3), SAM's bidirectional dependency graph allowed the agent to retrieve interconnected definitions deterministically, avoiding the vocabulary mismatch failures common to standalone vector retrieval and increasing accuracy from 28.0\% to 85.1\% ($p < 0.001$).

\textbf{RQ3: Accuracy vs.\ Cost Trade-offs.} The accuracy gains of structural memory come with measurable operational costs. Executing explicit tool calls for artifact reading, updating, and dependency traversal significantly increases text generation volume, resulting in longer mean latency (47.1s vs.\ 27.0s), and consequently, higher token consumption. Furthermore, on simple retrieval tasks with low structural requirements (Scenario~1), SAM's operational overhead provided only a marginal, non-significant accuracy benefit (94.1\% vs.\ 91.1\%, $p = 0.42$).

In summary, the primary contribution of this work is the design and empirical validation of a domain-adapted hybrid memory architecture. The results confirm that structural memory capabilities provide measurable improvements over pure semantic retrieval, concentrated specifically on the complex dependency and versioning operations that characterise real enterprise BI workflows.

\section{Implications}

The findings carry implications for the design of AI agent memory systems 
more broadly. Memory architecture should be treated as a first-class design 
concern rather than an afterthought addressed by general-purpose retrieval. 

Other agentic domains with similarly 
artifact-oriented workflows, such as software engineering, scientific research, 
legal document analysis, may benefit from analogous hybrid architectures 
that combine general-purpose retrieval with a typed dependency graph tailored 
to their artifact structure. The results also speak to the importance of 
benchmark design: the performance gap between SAM and RAG is invisible on 
retrieval-dominated tasks and only becomes apparent in scenarios that require 
BI-specific operations.

Finally, the failure analysis reveals that architectural capability alone is 
not sufficient: agent instruction-following reliability plays a significant 
role in whether structural tools are used correctly. This points to a 
productive research direction at the intersection of memory architecture and 
agent prompting, where orchestration-layer safeguards can enforce structural 
discipline independently of model behaviour.

\section{Future Work}

Several directions for future work are identified based on the limitations 
and open questions raised by this thesis.

\textbf{Larger and more diverse evaluation.} The three scenarios used in 
this thesis are synthetically constructed to isolate specific memory 
capabilities. Expanding the evaluation to include human-authored BI tasks, 
more heterogeneous schema environments, and longer analytical chains would 
strengthen the external validity of the findings. Running additional trials 
per scenario would also provide tighter confidence intervals on the smaller 
performance differences, such as the 3-point gap in Scenario~1.

\textbf{Production-scale memory store.} The file-system backend used in 
this evaluation is adequate for tens to hundreds of artifacts but is not 
designed for large-scale deployments. Replacing it with a graph database 
such as Neo4j would enable indexed traversal, transactional writes, and 
concurrent access, making SAM viable for production BI environments.

\textbf{Multi-project and multi-user support.} The current implementation 
is scoped to single-user, single-project settings. Extending SAM to support 
multiple concurrent analytical projects sharing a definition namespace, and 
collaborative settings where multiple analysts contribute to a shared 
artifact graph, would require conflict resolution and attribution tracking 
mechanisms beyond the current design.

\textbf{Cross-domain generalisation.} The hybrid retrieval-plus-structure 
pattern may generalise to other agentic domains with similar workflow 
structure. Investigating SAM-style architectures in software engineering 
agents (where code artifacts, test suites, and documentation form analogous 
dependency graphs) or scientific research agents (where hypotheses, 
experiments, and findings compose into chains) would test whether the design 
principles transfer beyond the BI setting.

%========================
% Back Matter
%========================

\appendix




%========================
% Back Matter
%========================

\appendix

\chapter{Artifacts and Instrumentation}

\section{System Prompts}

\subsection{RAG Baseline Prompt}
\begin{lstlisting}[basicstyle=\ttfamily\scriptsize, breaklines=true, frame=single]
You are an expert Business Intelligence analyst agent. You have access to a PostgreSQL database (the Northwind dataset) and a semantic memory system.

## Database
- The database is PostgreSQL. Always use PostgreSQL syntax:
  - Date extraction: EXTRACT(YEAR FROM date_col), not strftime()
  - String functions: LENGTH(), UPPER(), LOWER()
  - Casting: column::numeric, column::text
  - Boolean: TRUE/FALSE, not 1/0
- All table and column names are lowercase snake_case.
- NEVER guess column names. If unsure, introspect the schema first.

## Workflow
Follow this order to answer questions:
1. Search memory - call `search_memory` to find relevant past work (definitions, queries, findings).
2. Query the database - write SQL via `run_query` if fresh data is needed.
3. Respond - always end with a clear, complete response to the user.

Your memory is automatically populated from past conversations. You do not need to explicitly save anything - all your responses and query results are automatically stored for future retrieval.

## Search Discipline
- Call `search_memory` at most 2 times per user question. If your first search does not return useful results, try ONE more search with different keywords.
- If two searches fail to find what you need, stop searching and proceed - query the database directly or state what you know.
- NEVER call `search_memory` more than 2 times in a single turn. Repeated searching will not produce better results.

## Response Contract
- You MUST produce a final text response. Tool calls alone are never acceptable.
- Be concise but thorough. Show your reasoning.
\end{lstlisting}

\subsection{SAM Prompt}
\begin{lstlisting}[basicstyle=\ttfamily\scriptsize, breaklines=true, frame=single]
You are an expert Business Intelligence analyst agent. You have access to a PostgreSQL database (the Northwind dataset) and a hybrid memory system combining semantic search with structured artifact management.

## Database
- The database is PostgreSQL. Always use PostgreSQL syntax:
  - Date extraction: EXTRACT(YEAR FROM date_col), not strftime()
  - String functions: LENGTH(), UPPER(), LOWER()
  - Casting: column::numeric, column::text
  - Boolean: TRUE/FALSE, not 1/0
- All table and column names are lowercase snake_case (e.g., order_details, unit_price, shipped_date, company_name).
- NEVER guess column names. If unsure, introspect the schema first.

## Workflow
Follow this order to answer questions:
1. Search memory - call `search_memory` to find relevant past work by meaning. Results include full content - you do NOT need to call `read_artifact` unless you need version history.
2. Navigate dependencies - if you need to trace how artifacts relate, call `get_dependencies`.
3. Query the database - write SQL via `run_query` only if fresh data is needed.
4. Save findings - use `save_definition` or `save_insight` only when the user defines something new.
5. Respond - always end with a clear, complete response to the user.

## Search Discipline
- Call `search_memory` at most 2 times per user question. If your first search does not return useful results, try ONE more search with different keywords.
- If two searches fail, stop searching and proceed - use `list_artifacts` or query the database directly.
- NEVER call `search_memory` more than 2 times in a single turn.

## Saving Artifacts
- When the user defines a business metric, save it with `save_definition`.
- When you derive an analytical finding, save it with `save_insight`.
- When updating an existing definition, use `update_artifact` (creates a version bump).
- Do NOT re-save definitions that already exist unchanged.

## Response Contract
- You MUST produce a final text response. Tool calls alone are never acceptable.
- Do not re-save information that already exists.
- Be concise but thorough. Show your reasoning.
\end{lstlisting}

\subsection{LLM-as-a-Judge Prompt}
\begin{lstlisting}[basicstyle=\ttfamily\scriptsize, breaklines=true, frame=single]
You are an impartial evaluator assessing an AI agent's response against specific criteria.

QUESTION ASKED TO THE AGENT:
{question}

AGENT'S RESPONSE:
{agent_response}

EVALUATION CRITERIA:
{criteria}

Did the agent successfully meet all the criteria? 
You must respond with valid JSON in exactly this format:
{
  "passed": true/false,
  "reasoning": "brief explanation of why the criteria was or was not met"
}
\end{lstlisting}

\section{Sample Artifact JSON}
The following is an example of a serialized SAM artifact stored on the backend filesystem, illustrating the typed representation, version tracking, dependency mapping, and metadata encapsulation.
\begin{lstlisting}[language=json, basicstyle=\ttfamily\scriptsize, breaklines=true, frame=single]
{
  "id": "def_supplier_review",
  "type": "definition",
  "name": "Supplier Review threshold",
  "summary": "Policy for flagging suppliers based on underperforming products",
  "content": "A supplier is flagged for Supplier Review if they have more than 2 Underperforming Products.",
  "sql_logic": "COUNT(underperforming_products) > 2 -> Supplier Review",
  "dependencies": [
    "def_underperforming_product"
  ],
  "version": 1,
  "is_superseded": false,
  "created_at": "2025-05-01T10:15:30.123456Z"
}
\end{lstlisting}

\section{Code Repository}
The complete source code for the memory backend API, the SAM and RAG agent orchestrations built on LangGraph, the deterministic memory tool implementations, and the automated evaluation pipeline with seeded scenario data are available in the project repository:

\begin{center}
\url{https://github.com/vhy/thesis-bi-agent}
\end{center}
\textit{(Note: Please contact the author directly if the repository is private and access is needed for verification.)}

\section{Additional Evaluation Results}
The raw, trial-level dataset exported from the \texttt{eval\_runs} PostgreSQL table containing every individual turn's latency, token consumption, executing tools trace, and exact LLM-judge breakdown has been omitted from this printed document for brevity. It is provided as a supplementary \texttt{results.csv} dataset alongside the source code repository.


\bibliographystyle{plain}
\bibliography{references}

\end{document}  