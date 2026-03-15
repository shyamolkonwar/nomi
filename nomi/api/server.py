"""FastAPI server for Nomi HTTP API.

This module provides the main FastAPI application factory and server lifecycle management.
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from nomi.api.routes import context, repo, symbol
from nomi.core.context.context_builder import ContextBuilder
from nomi.core.index.lookup import SymbolLookup
from nomi.core.index.search import SymbolSearch
from nomi.core.index.symbol_index import SymbolIndex
from nomi.repo_map.map_builder import RepoMapBuilder

logger = logging.getLogger(__name__)


class APIServerState:
    """Shared state for the API server."""

    def __init__(
        self,
        context_builder: Optional[ContextBuilder] = None,
        symbol_search: Optional[SymbolSearch] = None,
        symbol_lookup: Optional[SymbolLookup] = None,
        repo_map_builder: Optional[RepoMapBuilder] = None,
        symbol_index: Optional[SymbolIndex] = None,
    ) -> None:
        self.context_builder = context_builder
        self.symbol_search = symbol_search
        self.symbol_lookup = symbol_lookup
        self.repo_map_builder = repo_map_builder
        self.symbol_index = symbol_index


# Global state instance
_api_state: Optional[APIServerState] = None


def get_api_state() -> APIServerState:
    """Get the current API server state.

    Returns:
        The current APIServerState instance.

    Raises:
        RuntimeError: If the API server state has not been initialized.
    """
    if _api_state is None:
        raise RuntimeError("API server state not initialized")
    return _api_state


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events.

    Handles startup and shutdown logic for the API server.
    """
    logger.info("Nomi API server starting up")

    yield

    logger.info("Nomi API server shutting down")


def create_api_server(
    context_builder: Optional[ContextBuilder] = None,
    symbol_search: Optional[SymbolSearch] = None,
    symbol_lookup: Optional[SymbolLookup] = None,
    repo_map_builder: Optional[RepoMapBuilder] = None,
    symbol_index: Optional[SymbolIndex] = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        context_builder: ContextBuilder instance for context operations.
        symbol_search: SymbolSearch instance for fuzzy symbol search.
        symbol_lookup: SymbolLookup instance for exact symbol lookups.
        repo_map_builder: RepoMapBuilder instance for repository maps.
        symbol_index: SymbolIndex instance for indexing operations.

    Returns:
        Configured FastAPI application instance.
    """
    global _api_state

    _api_state = APIServerState(
        context_builder=context_builder,
        symbol_search=symbol_search,
        symbol_lookup=symbol_lookup,
        repo_map_builder=repo_map_builder,
        symbol_index=symbol_index,
    )

    app = FastAPI(
        title="Nomi API",
        description="Local context engine API for AI coding agents",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:8080",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:8080",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", response_model=dict)
    async def health_check() -> dict:
        """Health check endpoint.

        Returns:
            Dictionary with health status and version info.
        """
        return {
            "status": "healthy",
            "service": "nomi-api",
            "version": "0.1.0",
        }

    @app.get("/", response_model=dict)
    async def root() -> dict:
        """Root endpoint with API information.

        Returns:
            Dictionary with API information.
        """
        return {
            "name": "Nomi API",
            "version": "0.1.0",
            "description": "Local context engine for AI coding agents",
            "endpoints": {
                "health": "/health",
                "context": {
                    "build_context": "POST /context",
                    "build_for_symbol": "POST /context/symbol",
                    "build_for_file": "POST /context/file",
                    "stats": "GET /context/stats",
                },
                "symbols": {
                    "get_by_name": "GET /symbol/{name}",
                    "search": "POST /symbol/search",
                    "get_by_file": "GET /symbol/file/{file_path}",
                    "search_by_prefix": "GET /symbol/prefix/{prefix}",
                },
                "repository": {
                    "repo_map": "GET /repo-map",
                    "status": "GET /repo/status",
                    "reindex": "POST /repo/index",
                    "stats": "GET /repo/stats",
                },
            },
        }

    _setup_dependency_injection(app)
    _register_routers(app)

    logger.info("Nomi API server created successfully")

    return app


def _setup_dependency_injection(app: FastAPI) -> None:
    """Setup dependency injection for route handlers.

    Args:
        app: The FastAPI application instance.
    """
    def get_context_builder() -> Optional[ContextBuilder]:
        return get_api_state().context_builder

    def get_symbol_search() -> Optional[SymbolSearch]:
        return get_api_state().symbol_search

    def get_symbol_lookup() -> Optional[SymbolLookup]:
        return get_api_state().symbol_lookup

    def get_repo_map_builder() -> Optional[RepoMapBuilder]:
        return get_api_state().repo_map_builder

    def get_symbol_index() -> Optional[SymbolIndex]:
        return get_api_state().symbol_index

    app.dependency_overrides = {
        ContextBuilder: get_context_builder,
        SymbolSearch: get_symbol_search,
        SymbolLookup: get_symbol_lookup,
        RepoMapBuilder: get_repo_map_builder,
        SymbolIndex: get_symbol_index,
    }


def _register_routers(app: FastAPI) -> None:
    """Register all API route handlers.

    Args:
        app: The FastAPI application instance.
    """
    app.include_router(context.router)
    app.include_router(symbol.router)
    app.include_router(repo.router)


async def start_server(
    app: FastAPI,
    host: str = "127.0.0.1",
    port: int = 8345,
) -> None:
    """Start the API server with uvicorn.

    Args:
        app: The FastAPI application instance.
        host: Host address to bind to.
        port: Port number to listen on.
    """
    import uvicorn

    logger.info(f"Starting Nomi API server on {host}:{port}")

    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="info",
    )

    server = uvicorn.Server(config)
    await server.serve()
