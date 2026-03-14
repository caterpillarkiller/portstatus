# Cross-Session Workflow Instructions

These instructions apply to every session, across all repositories, on all platforms.

## Session Start

At the start of every session:
1. Identify the current repository name from the working directory
2. Search Notion for a subpage whose name matches or closely resembles the repository name
3. Read that Notion subpage in full to load project context (goals, tech stack, history, abandoned approaches, changelog, etc.)
4. Search Asana for a project whose name matches or closely resembles the repository name
5. Read open Asana tasks, noting anything marked "In Progress" — these are the priority for this session
6. Briefly summarise to the user: what context was loaded from Notion and what tasks are currently in progress

## During the Session

### Code Changes & Features
When significant code changes are made (feature complete, meaningful refactor, new functionality):
1. Mark the corresponding Asana task(s) as complete if they exist
2. Append a changelog entry to the Notion subpage (see Changelog Format below)

### Bug Fixes
When a bug is identified and fixed:
1. Mark the corresponding Asana task as complete if one exists
2. Append a changelog entry to the Notion subpage tagged as a bug fix (see Changelog Format below)

### New Tasks Identified
When a task or issue is identified that will not be addressed in the current session:
1. Create it as an Asana task in the matching project
2. Set its status to "Up Next" if it should be tackled soon, or "Backlog" if lower priority
3. Confirm to the user that the task was created

## Session End

When work is wrapping up or the user signals they are done:
1. Update the Notion subpage with a summary of everything accomplished this session
2. Ensure all completed work has corresponding Asana tasks marked done
3. Ensure all identified future work has been captured in Asana with the correct status
4. Confirm to the user that Notion and Asana are up to date

## Changelog Format

Maintain a "Changelog" section in the Notion subpage. Append entries in reverse chronological order (newest first) using this format:

### [YYYY-MM-DD] — Session Summary
- **[Feature]** Short description of what was added or changed
- **[Bug Fix]** Short description of the bug and how it was resolved
- **[Refactor]** Short description of structural/code quality changes
- **[Abandoned]** Short description of approaches tried and discarded, and why

Never delete previous changelog entries. This is a permanent working history of the project.
