Read @context/JARVIS_SPEC.md and @context/ARCHITECTURE.md in full before doing anything.

Your rules are in @.cursor/rules/ — follow them precisely.

Execute the JARVIS deployment in order, one phase at a time:

For each phase:
1. Generate all scripts and config files described in the spec
2. Execute the scripts in the terminal
3. Run the verify script
4. Only continue when verify passes
5. Update @DEPLOYMENT_STATUS.md

Start with Phase 1. Go.