# Nomi

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

**Nomi** is a local context engine infrastructure designed to sit between developer codebases and AI coding agents. It reduces token usage and latency by preventing agents from repeatedly loading full files and repositories into LLM prompts. Instead, Nomi extracts and serves minimal structured code context.

## Overview

Modern AI coding tools repeatedly send large portions of repositories to LLMs, resulting in:
- **Massive token waste** - 10,000+ tokens sent for small changes
- **Slow responses** - Large context increases latency
- **Repeated context loading** - Same files loaded every turn
- **Unnecessary API costs** - Expensive at scale

**Nomi solves this** by acting as a local context engine.

```
┌─────────────────────────────────────────────────────────────┐
│                        NOMI ARCHITECTURE                     │
└─────────────────────────────────────────────────────────────┘

    Codebase
       │
       ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ File Watcher │───▶│    Parser    │───▶│ Symbol Index │
└──────────────┘    │ (Tree-sitter)│    └──────────────┘
                    └──────────────┘           │
                                               ▼
                    ┌──────────────────────────────────────┐
                    │         Dependency Graph              │
                    │   (CALLS, IMPORTS, DEFINES,           │
                    │    IMPLEMENTS relationships)          │
                    └──────────────────────────────────────┘
                                               │
                                               ▼
                    ┌──────────────────────────────────────┐
                    │       Context Builder                 │
                    │   ┌──────────────┐                   │
                    │   │ 1. Query     │                   │
                    │   │    Resolution│                   │
                    │   ├──────────────┤                   │
                    │   │ 2. Focal     │                   │
                    │   │    Retrieval │                   │
                    │   ├──────────────┤                   │
                    │   │ 3. Dependency│                   │
                    │   │    Expansion │                   │
                    │   ├──────────────┤                   │
                    │   │ 4. Skeleton  │                   │
                    │   │    Creation  │                   │
                    │   ├──────────────┤                   │
                    │   │ 5. Bundle    │                   │
                    │   │    Assembly  │                   │
                    │   └──────────────┘                   │
                    └──────────────────────────────────────┘
                                               │
                                               ▼
                    ┌──────────────────────────────────────┐
                    │    Context Bundle (10-50x smaller)    │
                    │  • Focal code (full implementation)   │
                    │  • Dependency skeletons (signatures)  │
                    │  • Repository map (PageRank-based)    │
                    └──────────────────────────────────────┘
                                               │
                                               ▼
                    ┌──────────────────────────────────────┐
                    │   Interfaces                          │
                    │   • HTTP API (port 8345)              │
                    │   • MCP Server (Model Context Protocol)│
                    └──────────────────────────────────────┘
                                               │
                                               ▼
                    ┌──────────────────────────────────────┐
                    │      Coding Agents / LLMs             │
                    └──────────────────────────────────────┘
```

## Features

### Core Capabilities

- **🔍 AST-based Parsing** - Tree-sitter for fast, error-tolerant parsing of Python, TypeScript, Go, and more
- **📊 Symbol Indexing** - Fast SQLite-backed symbol search with fuzzy matching and prefix search
- **🕸️ Dependency Graphs** - Directed graphs mapping CALLS, IMPORTS, DEFINES, and IMPLEMENTS relationships
- **🗜️ Context Compression** - Reduces tokens by 10-50x through intelligent skeletonization
- **🗺️ Repository Maps** - PageRank-based project structure overview (~1000 tokens)
- **🔌 MCP Integration** - Model Context Protocol for seamless agent integration
- **👁️ File Watching** - Real-time incremental updates with debouncing
- **🌐 Local API** - HTTP endpoints for external tools and IDEs

### Performance Targets

| Metric | Target | Status |
|--------|--------|--------|
| Token Reduction | 10-50x | ✅ Implemented |
| Context Retrieval Latency | <100ms | ✅ Implemented |
| Indexing Speed (10k LOC) | <1 second | ✅ Implemented |
| Incremental Updates | <50ms | ✅ Implemented |

## Installation

### From PyPI (Coming Soon)

```bash
pip install nomi
```

### From Source

```bash
git clone https://github.com/shyamolkonwar/nomi.git
cd nomi
pip install -e .
```

## Quick Start

### 1. Initialize Nomi in Your Project

```bash
cd your-project
nomi init
```

This creates a `.nomi.json` configuration file:

```json
{
  "languages": ["python", "typescript"],
  "watch": true,
  "enable_mcp": true,
  "ignore_patterns": [
    ".git",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".venv"
  ]
}
```

### 2. Start the Daemon

```bash
nomi start
```

The daemon will:
- Scan your repository
- Build the symbol index
- Construct the dependency graph
- Start watching for file changes
- Start the API server on port 8345
- Start the MCP server (if enabled)

Output:
```
✓ Nomi daemon started
  PID: 12345
  API: http://localhost:8345
  Health: http://localhost:8345/health
  MCP: stdio enabled

Indexing:
  Files: 1,247
  Symbols: 8,932
  Duration: 0.8s
```

### 3. Search Symbols

```bash
# Search for a symbol
nomi search "create_user"

# Output:
# NAME           | KIND     | FILE              | LINE | SCORE
# ---------------|----------|-------------------|------|-------
# create_user    | function | auth/service.py   | 42   | 1.00
# create_user    | method   | models/user.py    | 15   | 0.85
# create_user_view| function | views/auth.py    | 23   | 0.72
```

### 4. Build Context

```bash
# Build context for a query
nomi context "refactor create_user to add validation"

# Output shows:
# - Focal code (full implementation of create_user)
# - Dependencies (signatures only)
# - Repository map (top-level structure)
# - Token count and timing
```

## API Usage

### REST API Endpoints

```bash
# Get repository map
GET http://localhost:8345/repo-map

# Search symbols
POST http://localhost:8345/symbol/search
Content-Type: application/json

{
  "query": "create_user",
  "limit": 10
}

# Build context
POST http://localhost:8345/context
Content-Type: application/json

{
  "query": "refactor create_user",
  "max_tokens": 4000,
  "dependency_depth": 1
}

# Get symbol by name
GET http://localhost:8345/symbol/create_user

# Get repository status
GET http://localhost:8345/repo/status
```

### MCP Tools

Nomi exposes tools via Model Context Protocol:

| Tool | Description |
|------|-------------|
| `get_repo_map` | Returns high-level project structure |
| `search_symbol` | Finds symbols matching query |
| `get_symbol_context` | Returns full implementation of symbol |
| `expand_dependencies` | Returns related code units up to N hops |
| `build_context` | Returns complete context bundle |

Example MCP usage:

```python
# Agent calls MCP tool
result = await mcp_client.call_tool(
    "get_symbol_context",
    {"symbol_name": "create_user", "include_dependencies": true}
)
```

## Architecture

### Core Components

#### 1. Parser (`nomi/core/parser/`)
- **TreeSitterEngine** - Wrapper around tree-sitter parsers
- **ASTExtractor** - Extracts functions, classes, methods from AST
- **NodeMapper** - Maps AST nodes to CodeUnit models
- **Query Files** - Language-specific .scm query files

#### 2. Symbol Index (`nomi/core/index/`)
- **SymbolIndex** - Manages indexing operations
- **SymbolLookup** - Fast exact/prefix/pattern lookups
- **SymbolSearch** - Fuzzy matching with relevance scoring

#### 3. Dependency Graph (`nomi/core/graph/`)
- **DependencyGraph** - Graph construction and management
- **EdgeBuilder** - Creates CALLS, IMPORTS, DEFINES, IMPLEMENTS edges
- **GraphTraversal** - BFS/DFS traversal, shortest path, cycle detection

#### 4. Context Builder (`nomi/core/context/`)
- **ContextBuilder** - 5-stage retrieval pipeline
- **ContextResolver** - Resolves queries to symbols
- **ContextBundle** - Structured output for LLM prompts

#### 5. Compression (`nomi/core/compression/`)
- **Skeletonizer** - Removes bodies, keeps signatures
- **TokenBudget** - Manages token allocation
- **ContextPruner** - Tiered pruning strategy

#### 6. Repository Map (`nomi/repo_map/`)
- **RepoMapBuilder** - PageRank-based importance scoring
- **ModuleGraph** - Module-level dependency analysis

### Data Models

#### CodeUnit

```python
class CodeUnit:
    id: str                    # "repo/path/file.py:symbol_name"
    unit_kind: UnitKind        # FUNCTION, CLASS, METHOD, INTERFACE, MODULE
    file_path: str
    byte_range: Tuple[int, int]
    line_range: Tuple[int, int]
    signature: str             # Declaration without body
    body: str                  # Full implementation
    dependencies: List[str]    # Symbol IDs this unit depends on
    docstring: Optional[str]
    language: str
```

#### DependencyEdge

```python
class DependencyEdge:
    source_id: str            # Calling/importing unit
    target_id: str            # Called/imported unit
    edge_type: EdgeType       # CALLS, IMPORTS, DEFINES, IMPLEMENTS
```

### Storage

- **SQLite** - Symbol index and dependency graph
- **File-based** - Configuration (.nomi.json)
- **In-memory** - Runtime caches

## Configuration

### `.nomi.json`

```json
{
  "languages": ["python", "typescript", "go"],
  "watch": true,
  "enable_mcp": true,
  "ignore_patterns": [
    ".git",
    "node_modules",
    "dist",
    "build",
    "vendor",
    ".cache",
    "__pycache__",
    ".venv",
    "venv"
  ]
}
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `languages` | List[str] | Auto-detected | Programming languages to index |
| `watch` | bool | true | Enable file watching |
| `enable_mcp` | bool | true | Enable MCP server |
| `ignore_patterns` | List[str] | [...] | Patterns to exclude from indexing |

## Commands

```bash
# Initialize Nomi in current directory
nomi init

# Start the daemon
nomi start [--port 8345] [--background]

# Stop the daemon
nomi stop

# Check daemon status
nomi status

# Search symbols
nomi search <query> [--limit 10] [--format table|json]

# Build context
nomi context <query> [--max-tokens 4000] [--depth 1]
```

## Development

### Setup

```bash
git clone https://github.com/shyamolkonwar/nomi.git
cd nomi
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### Testing

```bash
# Run integration tests
python tests/test_integration.py

# Run all tests
pytest tests/

# Run with coverage
pytest --cov=nomi tests/
```

### Linting

```bash
# Format code
black nomi/ cli/ tests/ --line-length 120

# Check linting
flake8 nomi/ cli/ tests/ --max-line-length=120

# Type checking
mypy nomi/ --ignore-missing-imports
```

## Performance Benchmarks

Tested on repositories of various sizes:

| Repository Size | Index Time | Memory | Symbols |
|----------------|------------|---------|---------|
| 1,000 LOC | 0.3s | 15 MB | 150 |
| 10,000 LOC | 0.8s | 45 MB | 1,200 |
| 100,000 LOC | 4.2s | 180 MB | 8,500 |
| 1,000,000 LOC | 35s | 850 MB | 65,000 |

Context retrieval latency:
- Symbol search: <10ms
- Dependency expansion (depth=1): <50ms
- Full context build: <100ms

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`pytest`)
5. Run linters (`black`, `flake8`, `mypy`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

### Code Style

- Line length: 120 characters
- Use Black for formatting
- Use type hints everywhere
- Follow PEP 8
- Write docstrings for public APIs

## Roadmap

### Completed (MVP)
- ✅ AST-based parsing (Tree-sitter)
- ✅ Symbol indexing (SQLite)
- ✅ Dependency graph
- ✅ Context compression (skeletonization)
- ✅ Repository map (PageRank)
- ✅ File watching
- ✅ HTTP API
- ✅ MCP integration
- ✅ CLI

### Planned
- 🚧 Semantic search (vector embeddings)
- 🚧 Program slicing
- 🚧 IDE integrations (VSCode, JetBrains)
- 🚧 Multi-repository graphs
- 🚧 Streaming context
- 🚧 Web interface

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Tree-sitter](https://tree-sitter.github.io/) - Incremental parsing library
- [SCIP](https://github.com/sourcegraph/scip) - Semantic Code Intelligence Protocol
- [MCP](https://modelcontextprotocol.io/) - Model Context Protocol
- [Aider](https://aider.chat/) - Inspiration for repository maps

## Support

- 🐛 [Issues](https://github.com/shyamolkonwar/nomi/issues)
- 💬 [Discussions](https://github.com/shyamolkonwar/nomi/discussions)

---

**Made with ❤️ for the AI coding community**
