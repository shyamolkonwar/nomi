# Nomi

A local context engine infrastructure designed to sit between developer codebases and AI coding agents. Nomi reduces token usage and latency by preventing agents from repeatedly loading full files and repositories into LLM prompts.

## Overview

Nomi operates as a background daemon that continuously indexes a repository and exposes context retrieval tools via APIs and agent tool protocols.

Instead of reading files, agents request **structured code units**. Nomi sits between:

```
Codebase
   ↓
Nomi Context Engine
   ↓
Coding Agents
   ↓
LLM
```

## Features

- **AST-based parsing** - Uses Tree-sitter for fast, error-tolerant parsing
- **Symbol indexing** - Fast symbol lookup with SQLite backend
- **Dependency graphs** - Maps relationships between code units
- **Context compression** - Reduces tokens by 10-50x through skeletonization
- **Repository maps** - PageRank-based project overview
- **MCP integration** - Model Context Protocol for agent integration
- **File watching** - Real-time incremental updates
- **Local API** - HTTP endpoints for external tools

## Quick Start

### Installation

```bash
pip install nomi
```

### Initialize Project

```bash
cd your-project
nomi init
```

This creates a `.nomi.json` configuration file.

### Start Daemon

```bash
nomi start
```

The daemon runs in the background and starts indexing your repository.

### Use with Agents

Nomi exposes tools via MCP that agents can call:

- `get_repo_map` - Get repository structure
- `search_symbol` - Find symbols by name
- `get_symbol_context` - Get full implementation
- `expand_dependencies` - Get related code
- `build_context` - Build complete context bundle

## Architecture

```
Repository
   ↓
File Watcher
   ↓
Parser (Tree-sitter)
   ↓
Symbol Index
   ↓
Dependency Graph
   ↓
Context Builder
   ↓
API / MCP Server
```

## Performance

- **Token reduction**: 10-50x compared to full file loading
- **Context retrieval**: <100ms latency
- **Indexing**: <1 second for 10k LOC repositories
- **Incremental updates**: <50ms per file change

## Configuration

`.nomi.json`:

```json
{
  "languages": ["python", "typescript"],
  "watch": true,
  "enable_mcp": true,
  "ignore_patterns": [".git", "node_modules", "dist"]
}
```

## Commands

- `nomi init` - Initialize Nomi in a repository
- `nomi start` - Start the daemon
- `nomi stop` - Stop the daemon
- `nomi status` - Check daemon status
- `nomi search <query>` - Search symbols
- `nomi context <query>` - Build context

## License

MIT
