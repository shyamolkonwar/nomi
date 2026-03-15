# Agent Instructions

## Build/Lint/Test Commands

### Python/FastAPI Backend
```bash
# Run all tests
cd backend && python -m pytest tests/ -v --tb=short

# Run specific test file
cd backend && python -m pytest tests/cto/test_cto_agent.py -v

# Run single test
cd backend && python -m pytest tests/cto/test_cto_agent.py::TestCTOAgent::test_reason_about_task -v

# Linting & Formatting
cd backend && python -m flake8 app/ tests/ --max-line-length=120
cd backend && black app/ tests/ --line-length 120 --check
cd backend && black app/ tests/ --line-length 120  # Format
cd backend && mypy app/ --ignore-missing-imports  # Type check
```

### TypeScript/Next.js Frontend
```bash
cd frontend
npm run dev          # Start dev server
npm run build       # Production build
npm run lint        # ESLint
npx tsc --noEmit    # Type check
```

### Monorepo Packages
```bash
cd packages/<package-name>
npm run build       # Build
npm run test        # Run tests
npm run lint        # ESLint
npm run type-check  # TypeScript check
```

### Using Make
```bash
make test           # Run all tests
make test-backend   # Backend tests only
make lint           # Run all linters
make format         # Format code
make dev-local      # Start backend locally
```

## Code Style Guidelines

### Python

**Imports** (order matters):
```python
# 1. Standard library
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

# 2. Third-party
from pydantic import BaseModel, Field
from fastapi import FastAPI

# 3. Internal (absolute imports)
from app.core.config import get_settings
```

**Formatting**:
- Line length: 120 characters
- Use double quotes for strings
- Black formatter with `--line-length 120`
- Trailing commas in multi-line structures

**Types**:
```python
# Explicit types
async def process_data(self, text: str) -> Result:
    ...

# Optional for nullable
task_id: Optional[str] = None

# Field for Pydantic defaults
confidence: float = Field(default=0.5, ge=0.0, le=1.0)
```

**Naming**:
- Classes: `PascalCase` (e.g., `CTOAgent`)
- Functions/variables: `snake_case` (e.g., `get_settings`)
- Constants: `SCREAMING_SNAKE_CASE` (e.g., `MAX_RETRIES`)
- Private: `_leading_underscore` (e.g., `_internal_method`)

**Error Handling**:
```python
# Custom exceptions over generic
from app.agent_os.exceptions import StateConflictError

# Raise with context
raise TaskGraphError(
    graph_id=graph_id,
    reason=f"Cannot execute graph in status: {graph.status}"
)

# Log before raising
logger.error("Task failed", task_id=str(task.id), error=str(e))
```

### TypeScript/React

**Imports**:
```typescript
// 1. React/Next.js
import { useState, useEffect } from "react";

// 2. External libraries
import { useRouter } from "next/navigation";

// 3. Internal (use path aliases)
import { MyComponent } from "@/components/MyComponent";
```

**Naming**:
- Components: `PascalCase` (e.g., `DashboardPage`)
- Hooks: `camelCase` with `use` prefix (e.g., `useAuth`)
- Types/Interfaces: `PascalCase` (e.g., `UserData`)
- Constants: `SCREAMING_SNAKE_CASE`

**Types**:
```typescript
// Prefer interfaces for objects
interface User {
  id: string;
  name: string;
}

// Type for unions
type Status = "active" | "inactive";

// Explicit return types
const formatName = (user: User): string => {
  return user.name;
};
```

**Formatting**:
- 2 spaces indentation
- Single quotes for strings
- Semicolons required
- Trailing commas in multi-line

### SQL
- Uppercase keywords (`CREATE`, `SELECT`)
- Lowercase identifiers
- snake_case for table/column names
- Include `IF NOT EXISTS` or `IF EXISTS`

## Testing Guidelines

**Test Structure**:
```python
class TestMyClass:
    """Test suite for MyClass."""
    
    @pytest.fixture
    def my_instance(self):
        return MyClass()
    
    def test_feature(self, my_instance):
        # Arrange
        input_data = ...
        
        # Act
        result = my_instance.process(input_data)
        
        # Assert
        assert result.expected_value == actual_value
```

**Test Markers**:
- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.asyncio` - Async tests

## Project Structure

```
rivtor/
├── frontend/          # Next.js + React
├── backend/           # FastAPI + Python
│   ├── app/
│   │   ├── api/routes/    # API endpoints
│   │   ├── services/      # Business logic
│   │   ├── agent_os/      # Multi-agent system
│   │   └── cto/           # CTO Agent
│   └── tests/
├── packages/          # Monorepo packages
└── docs/              # Documentation
```

## Agent Rules

1. **Verify state first** - Inspect files before modifying
2. **Small changes** - Prefer modular edits over large refactors
3. **Run checks** - Always run lint/build/test after changes
4. **No assumptions** - Never guess; ask if unclear
5. **Clean commits** - Commit only when all checks pass
6. **No force push** - Never use `--force` on shared branches
7. **Remove debug code** - No console.log, prints, or temp code
8. **Documentation** - Only when needed (APIs, complex logic)

## Environment Variables

```bash
# Backend
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
OPENAI_API_KEY=
REDIS_URL=

# Frontend
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
```
