# Using Antigravity and GitHub Copilot Safely

Tool features and interfaces change, so treat these as workflow instructions rather than claims about a specific button layout.

## Ground rules
- Keep `PRD.md`, `ARCHITECTURE.md`, and `API_CONTRACT.md` in the repository.
- Ask the AI to inspect existing code before proposing changes.
- Give one bounded task at a time.
- Ask it to list files it intends to change before broad edits.
- Require tests and a short explanation.
- Review every diff; do not accept code you cannot explain.
- Never paste API keys, passwords, real patient data, or private clinic credentials into prompts.
- Do not allow AI to invent clinic facts, doctor availability, ratings, or medical guidance.
- Commit working checkpoints before large AI-assisted changes.

## Antigravity workflow
1. Open the project folder and provide the project docs as context.
2. Ask for a repository summary and proposed next task; do not begin with “build everything”.
3. Give one phase-specific prompt.
4. Inspect its plan and file changes.
5. Run commands/tests yourself in the terminal.
6. Ask it to fix only the specific failing test/error.
7. Review diff, update documentation, and commit.

### Antigravity starter prompt
“Read `docs/PRD.md`, `docs/ARCHITECTURE.md`, and `docs/OPEN_QUESTIONS.md`. Do not write code yet. Summarize the confirmed requirements, unresolved decisions, risks, and the smallest next implementation step. Do not invent requirements or external data.”

## GitHub Copilot workflow
1. Use repository instructions such as `.github/copilot-instructions.md` to explain architecture, conventions, and safety rules.
2. Use inline suggestions for small functions and tests.
3. Use chat/agent mode for bounded tasks with exact acceptance criteria.
4. Ask for tests alongside implementation.
5. Inspect generated code and run tests locally.

### Copilot task prompt
“Implement only [specific feature] described in `docs/API_CONTRACT.md`. First inspect the existing code and identify the files that need changes. Do not change unrelated files. Add tests for success, invalid input, missing data, and provider failure. Do not invent clinic/doctor data. Explain how to run the tests and list any assumptions or unresolved questions.”

## Example next task
“Create the FastAPI application scaffold with `GET /health`, settings loaded from environment variables, and one pytest test. Do not add database, authentication, AI, or external APIs yet. Show the planned file tree before editing.”

## When AI returns an error fix
Provide:
- exact command,
- complete traceback,
- relevant file(s),
- expected behavior,
- what changed since the last passing state.

Prompt:
“Diagnose this error from the supplied traceback and code. State the root cause before editing. Make the smallest fix, add a regression test, and do not refactor unrelated code.”

## Human review checklist
- Is the code consistent with the architecture?
- Are user inputs validated?
- Are secrets protected?
- Is health-related text handled safely?
- Is the data source identified?
- Are missing values represented honestly?
- Are tests meaningful?
- Can I explain every changed line?
