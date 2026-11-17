"""
MODULE: scripts/evals/agent_launch/__init__.py
GOAL: The one place the eval harness starts the claude CLI, finds it, and stops a run whose agent cannot start.
BUSINESS CONTEXT: TQ-200d-5. A live run died with 0/8 on Windows because the test writer's 67,700-character
    template went on the command line (WinError 206), and a launcher that is only a claude.cmd could not
    be started at all (WinError 2). A launch failure also looked like a quality score of 0%.
ARCHITECTURE: ``command`` builds and starts the agent (instructions in a prompt file, input on stdin)
    and raises ``AgentLaunchError`` when the operating system refuses; ``locate`` finds the program;
    ``harness_failure`` turns the first launch failure into a stopped run. scripts/evals/ is at its
    folder file limit, so this is a sub-package like designer_eval.
"""
