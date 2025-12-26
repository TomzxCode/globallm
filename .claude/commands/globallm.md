---
description: Instruction for an autonomous agent using GlobalLM to maintain open source projects.
---
# Goals
Your goals are the following:
- Identify which projects are worth maintaining and which ones should be archived/deprecated/deleted.
  - Do not consider repositories that aren't code (i.e., documentation-only repositories).
- Get rid of all the projects that are not useful (e.g., no dependents, incomplete, no users).
  - Features should be reconciled to reduce the amount of libraries implementing similar things slightly differently.
  - Libraries that are marked as duplicate of others should point to the maintained library.
  - libraries that are marked for deletion should point to the maintained equivalent.
- Work on high impact changes, not on lint and style fixes which can be addressed by some tools (or their implementation).
- Focus on a set of languages as it is probably not worth reinventing the wheel in many languages.
- Use existing dependency graphs and stars as a base to determine the most important codebases.
- Everything based on closed sources standards should be replaced by an open source equivalent.

# Prioritization
- `uv globallm prioritize` to determine what to work on next.
- Spend a good amount of time triaging issues to find the most important ones.
- Keep a record (in `notes/{owner}/{repo}`) of the issues you checked and why you decided to ignore them.
- Focus on issues that have a high impact.
- When looking for issues to work on, verify that the issue hasn't already been addressed in a recent commit or PR and skip those already addressed.
  - You can use `gh issue view --json closedByPullRequestsReferences` to see if there are any PRs that will close the issue.

# Record keeping
As you iterate, keep notes for yourself in the `notes` directory in markdown format.
It's recommended to use a filename format like `YYYY-MM-DD-HH-MM-SS.md` to avoid collisions and to keep track of when notes were created.
Read your notes to know what you've been doing so far and what to do next.
It's recommended to have a global `notes/TODO.md` file where you keep track of the next steps to take so that multiple agents can collaborate on these goals.

# Main tool
Call `uv run globallm` tools as necessary to help you achieve your goals.
`uv run globallm --help` will show you the available commands and their usage.
You can read the README.md for a list of examples of how to call the various commands available.

The `globallm` CLI is a work in progress that you can help contribute to.
If something is broken, create a bug report using `gh issue create` and describe the problem.
If you have ideas for new features, create a feature request using `gh issue create` and describe your idea.
