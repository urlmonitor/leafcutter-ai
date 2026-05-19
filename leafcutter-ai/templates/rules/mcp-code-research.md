---
trigger: model_decision
description: Use when you need to research the codebase and understand how things work. Always index and use MCP tools before grep.
---

# MCP Code Research Rule

## When to Use MCP (jcodemunch)

Before using `grep_search` or `find_by_name` for discovering how code works, **prefer MCP tools when:**
- You need to understand how a feature is implemented across multiple files
- You need to find all references to a function, class, or symbol
- You need to understand the startup flow, initialization, or lifecycle of a component
- You need to trace a configuration value through the codebase

## MCP First, Grep Second

1. **First:** Check if the repo is indexed with `mcp_jcodemunch_list_repos`
2. **If not indexed:** Index the folder with `mcp_jcodemunch_index_folder`
3. **Then:** Use these MCP tools in order of preference:
   - `mcp_jcodemunch_search_symbols` — Find functions, classes, methods by name or description
   - `mcp_jcodemunch_search_text` — Full-text search across files (like grep but smarter)
   - `mcp_jcodemunch_find_references` — Find all usages of a symbol
   - `mcp_jcodemunch_find_importers` — Find all files that import a given file
   - `mcp_jcodemunch_get_file_outline` — Understand the structure of a file
4. **Fall back to grep** only when MCP doesn't find what you need (e.g., searching inside .env files, YAML, or non-code files)

## Practical Examples

### "How does feature X work on startup?"
```
1. search_symbols(query="startup") or search_text(query="ON_STARTUP")
2. find_references(identifier="create_database")
3. get_file_outline(file_path="database/")
```

### "Where is env variable X used?"
```
1. search_text(query="REBUILD_DATABASE_ON_STARTUP")
   (Searches code, comments, and config files)
2. If not found: fall back to grep for .env, .yml files
```

### "What calls function Y?"
```
1. find_references(identifier="apply_migrations")
2. find_importers(file_path="database/")
```

## Why This Matters

MCP provides semantic understanding — it knows about function signatures, symbol types, and import graphs. Plain `grep` only matches text patterns. Using MCP first:
- Avoids missing indirect references
- Provides context (summaries, signatures)
- Is faster for cross-file understanding
