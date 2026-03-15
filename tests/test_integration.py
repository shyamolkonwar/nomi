"""
Integration test for Nomi.
Tests the main workflow end-to-end.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add nomi to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_project_structure():
    """Verify project structure exists."""
    required_dirs = [
        "nomi/core",
        "nomi/core/parser",
        "nomi/core/index",
        "nomi/core/graph",
        "nomi/core/context",
        "nomi/core/compression",
        "nomi/daemon",
        "nomi/daemon/runtime",
        "nomi/daemon/scheduler",
        "nomi/daemon/lifecycle",
        "nomi/watcher",
        "nomi/discovery",
        "nomi/storage",
        "nomi/storage/sqlite",
        "nomi/storage/cache",
        "nomi/api",
        "nomi/api/routes",
        "nomi/mcp",
        "nomi/mcp/tools",
        "nomi/mcp/handlers",
        "nomi/repo_map",
        "nomi/config",
        "nomi/utils",
        "nomi/languages",
        "cli/commands",
        "tests",
    ]
    
    project_root = Path(__file__).parent.parent
    
    for dir_path in required_dirs:
        full_path = project_root / dir_path
        assert full_path.exists(), f"Missing directory: {dir_path}"
        print(f"✓ {dir_path}")
    
    print("\n✓ All required directories exist")


def test_imports():
    """Verify core modules can be imported."""
    try:
        # Storage
        from nomi.storage.models import CodeUnit, UnitKind
        print("✓ nomi.storage.models")
        
        # Discovery
        from nomi.discovery.language_detector import LanguageDetector, Language
        from nomi.discovery.repo_scanner import RepoScanner
        print("✓ nomi.discovery")
        
        # Config
        from nomi.config.schema import NomiConfig
        from nomi.config.loader import load_config
        print("✓ nomi.config")
        
        # Utils
        from nomi.utils.logger import get_logger
        from nomi.utils.paths import get_project_root
        print("✓ nomi.utils")
        
        print("\n✓ All core imports successful")
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        raise


def test_data_models():
    """Test data model creation."""
    from nomi.storage.models import CodeUnit, UnitKind, DependencyEdge, EdgeType
    
    # Create a CodeUnit
    unit = CodeUnit(
        id="test/file.py:my_function",
        unit_kind=UnitKind.FUNCTION,
        file_path="/test/file.py",
        byte_range=(0, 100),
        line_range=(1, 10),
        signature="def my_function(x: int) -> int",
        body="    return x + 1",
        dependencies=["test/file.py:other_function"],
        docstring="A test function",
        language="python"
    )
    
    assert unit.id == "test/file.py:my_function"
    assert unit.unit_kind == UnitKind.FUNCTION
    print("✓ CodeUnit model works")
    
    # Create a DependencyEdge
    edge = DependencyEdge(
        source_id="test/file.py:my_function",
        target_id="test/file.py:other_function",
        edge_type=EdgeType.CALLS
    )
    
    assert edge.edge_type == EdgeType.CALLS
    print("✓ DependencyEdge model works")
    
    print("\n✓ All data models work correctly")


def test_config():
    """Test configuration loading."""
    from nomi.config.schema import NomiConfig
    
    config = NomiConfig()
    
    assert "python" in config.languages
    assert ".git" in config.ignore_patterns
    assert config.watch is True
    
    print("✓ Default configuration valid")
    print(f"  Languages: {config.languages}")
    print(f"  Ignore patterns: {len(config.ignore_patterns)} patterns")


def test_language_detection():
    """Test language detection."""
    from nomi.discovery.language_detector import LanguageDetector, Language
    
    detector = LanguageDetector()
    
    # Test various extensions
    test_cases = [
        ("test.py", Language.PYTHON),
        ("test.ts", Language.TYPESCRIPT),
        ("test.js", Language.JAVASCRIPT),
        ("test.go", Language.GO),
        ("test.rs", Language.RUST),
        ("test.java", Language.JAVA),
        ("test.txt", Language.UNKNOWN),
    ]
    
    for file_path, expected in test_cases:
        detected = detector.detect_language(file_path)
        assert detected == expected, f"Failed for {file_path}: expected {expected}, got {detected}"
    
    print("✓ Language detection works correctly")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Nomi Integration Tests")
    print("=" * 60)
    print()
    
    test_project_structure()
    print()
    
    test_imports()
    print()
    
    test_data_models()
    print()
    
    test_config()
    print()
    
    test_language_detection()
    print()
    
    print("=" * 60)
    print("✓ All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
