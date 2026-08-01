# zeroi Architecture

zeroi implements an autonomous AI operating system around the Qwen-UI-Agent research philosophy:

## Core principles

1. Hybrid execution
   - GUI for visually grounded interaction
   - CLI for structured operations
   - API when official services exist
   - Browser for web interaction
   - DeepSearch for evidence and target resolution

2. Agent Harness
   - Receives every request
   - Maintains persistent session state
   - Coordinates planning, execution, verification, recovery, and final response

3. Dependency-aware planning
   - Planner decomposes goals into subtasks
   - Tasks declare dependencies
   - Independent tasks execute in parallel
   - Sequential order preserved inside each task pipeline

4. Batch execution
   - GUI actions are batched when compatible
   - Reduces reasoning latency
   - High-risk actions are isolated for approval

5. Shared execution state
   - Sessions, plans, artifacts, observations, memory, and logs persist
   - Executors share context through the Harness

6. Recovery
   - Failure categories include loops, UI misreading, CAPTCHA, popups, network errors, expired sessions, blank pages, and crashes
   - Recovery strategies include retry, replan, executor switch, and human approval

7. Proactive assistance
   - Notifications and events become structured events
   - Events associate with persistent affairs
   - Low-risk preparation can execute automatically
   - Irreversible actions require explicit approval

8. Qwen-UI-Agent integration
   - Qwen is used as the GUI execution engine
   - zeroi does not reimplement Qwen
   - The GUI adapter is replaceable for future Qwen releases
