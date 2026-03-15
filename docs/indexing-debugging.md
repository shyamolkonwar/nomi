# Why Nomi MCP Tools Return Empty Results

## Summary

When running Nomi MCP tools against a project, you may encounter empty results or "Symbol not found" errors. This happens because **the project has not been indexed yet**.

## Root Cause

The Nomi daemon requires an explicit indexing step to scan source files and store symbol information in the database. The MCP tools query this database, but if no indexing has occurred, the database is empty.

## Code Flow Analysis

### 1. Database Creation (No Data)

When `nomi start` runs, it creates an empty SQLite database:

```
nomi/daemon/runtime/daemon.py:117-127
def _initialize_database(self) -> None:
    """Initialize database connections and schema."""
    db_path = self.storage_dir / "nomi.db"
    self._symbol_store = SymbolStore(db_path)
    self._graph_store = GraphStore(db_path)
```

This creates the database schema but does NOT populate it with any data.

### 2. Indexing Scheduler is Created but Not Triggered

The IndexingScheduler is initialized in:

```
nomi/daemon/runtime/daemon.py:241-250
def _start_schedulers(self) -> None:
    if self._symbol_index is not None and self._repo_scanner is not None:
        self._indexing_scheduler = IndexingScheduler(
            symbol_index=self._symbol_index,
            repo_scanner=self._repo_scanner,
        )
```

**Problem**: The scheduler is created but `schedule_full_index()` is never called to actually start indexing.

### 3. IndexingScheduler Has the Method But It's Not Called

The IndexingScheduler has a method to trigger full indexing:

```
nomi/daemon/scheduler/indexing.py:156-160
def schedule_full_index(self) -> None:
    """Queue a full repository scan and index operation."""
    task = {"type": "full_index"}
    self._queue.put(task)
```

This method exists but is never invoked by the daemon.

### 4. MCP Tools Query Empty Database

When MCP tools run, they query the SymbolStore which has no data:

```
nomi/mcp/tools/symbol_lookup.py:50-76
async def search_symbol_tool(
    request: SearchSymbolRequest,
    symbol_search: SymbolSearch,
    **kwargs: Any,
) -> SearchSymbolResponse:
    # Perform the search
    search_results = symbol_search.search(
        query=request.query,
        limit=request.limit or 10,
    )
    # Returns empty list if no symbols indexed
```

## The Indexing Pipeline

For data to appear in the tools, the following pipeline must execute:

1. **RepoScanner.scan()** - Discovers all source files in the project
2. **SymbolIndex.index_files()** - Parses each file and extracts code symbols
3. **SymbolStore.insert_code_unit()** - Stores symbols in SQLite database

Only after this pipeline runs will MCP tools return results.

## Current Workaround

To index a project currently, you would need to manually trigger indexing. This can be done by:

1. Running a search or context command via CLI (which may trigger indexing)
2. Or modifying the code to call `schedule_full_index()` on daemon startup

## Solution

The daemon should automatically trigger a full index on startup. This requires modifying:

```
nomi/daemon/runtime/daemon.py:241-256
def _start_schedulers(self) -> None:
    # ... existing code ...
    
    # ADD THIS LINE to trigger initial indexing:
    if self._indexing_scheduler:
        self._indexing_scheduler.schedule_full_index()
```

## Verification

To verify if your project has been indexed:

1. Check if the database has data:
   ```bash
   sqlite3 .nomi/cache/nomi.db "SELECT COUNT(*) FROM code_units;"
   ```
   If this returns 0, no indexing has occurred.

2. Check daemon logs for indexing messages:
   - "Starting full repository index..." - indexing triggered
   - "Full index complete: indexed_count=X" - indexing finished

## Related Files

- `nomi/daemon/runtime/daemon.py` - Main daemon, creates schedulers
- `nomi/daemon/scheduler/indexing.py` - Indexing scheduler with queue
- `nomi/core/index/symbol_index.py` - Core indexing logic
- `nomi/discovery/repo_scanner.py` - File discovery
- `nomi/storage/sqlite/symbol_store.py` - Database storage
- `nomi/mcp/tools/*.py` - MCP tool implementations
