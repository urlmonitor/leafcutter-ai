---
description: Triggers when you put a .txt, .log, .json, or .xml file into the main folder
globs:
  - "*.txt"
  - "*.log"
  - "*.json"
  - "*.xml"
---

# Main Folder Clutter Prevention

When you create or place a `.txt`, `.log`, `.json`, or `.xml` file into the main folder (root directory of the project), you MUST:

1. Pause and ask the user to move it to the proper location, OR
2. If the purpose is clear (like debugging logs), automatically move it to the appropriate directory (e.g., `/debugging/logs/`) and inform the user that you did so to avoid clutter.

Do not leave output, log, or data files in the root folder.
