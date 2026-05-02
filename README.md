# Structured Artifact Memory (SAM) for BI Agents
**Bachelor's Thesis Source Code and Evaluation Pipeline**

This repository contains the official backend implementation and automated evaluation suite for Structured Artifact Memory (SAM)—a hybrid structural and semantic memory architecture designed for generative Business Intelligence (BI) agents. It accompanies the enclosed thesis document.

## Requirements
To execute the automated evaluation pipeline locally, you will need:
- Docker and Docker Compose
- An OpenAI or Gemini valid API key added to `ai-memory-backend/.env` (see `.env.example`)

## Quickstart

Start the local orchestration environment (Agent Backend + PostgreSQL Database) via Docker:
```bash
cd ai-memory-backend
docker compose up --build -d
```

Ensure the baseline system prompts and benchmark dataset (Northwind) are seeded into the database:
```bash
reset_and_seed.sh
```

## Running the Automated Memory Evaluation Scenarios
The test suite systematically executes the end-to-end memory evaluations detailed in Chapter 7 of the thesis (Accurate Retrieval under Noise, Conflict Resolution, and Multi-Hop Composition). 

If you wish to test a specific configuration (e.g. `spm` architecture) independently:
```bash
docker compose exec backend python scripts/generate_distractors.py
MEMORY_MODE=spm pytest tests/test_e2e_memory.py -v --tb=short -s
```

## Data Cleanup and Isolation
The evaluation pipeline automatically wipes the deterministic filesystem artifacts and FAISS baseline indexes before each test cycle to ensure empirical validity. To trigger a forced reset manually you can invoke the utility script:
```bash
reset_and_seed.sh
```
