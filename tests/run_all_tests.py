#!/usr/bin/env python3
"""
Run all tests script for the Stocks API project.

This script runs all unit tests in the tests directory and provides
a simple interface for executing the complete test suite.

Usage:
    python tests/run_all_tests.py              # Run all tests with default options
    python tests/run_all_tests.py --verbose    # Run with verbose output
    python tests/run_all_tests.py --quiet      # Run with minimal output
    python tests/run_all_tests.py --coverage   # Run with coverage report
    python tests/run_all_tests.py --help       # Show help
"""

import sys
import subprocess
import argparse
from pathlib import Path


def run_command(command: list[str]) -> int:
    """
    Run a command and return the exit code.
    
    Args:
        command: List of command parts to execute
        
    Returns:
        int: Exit code from the command
    """
    print(f"Running: {' '.join(command)}")
    print("-" * 60)
    
    try:
        result = subprocess.run(command, check=False)
        return result.returncode
    except FileNotFoundError:
        print(f"Error: Command not found: {command[0]}")
        print("Make sure pytest is installed:")
        print("  pip install -r requirements.txt")
        print("  # or install just the test dependencies:")
        print("  pip install pytest pytest-asyncio")
        return 1
    except KeyboardInterrupt:
        print("\nTest execution interrupted by user")
        return 130


def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(
        description="Run all tests for the Stocks API project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python tests/run_all_tests.py                 # Run all tests
    python tests/run_all_tests.py --verbose       # Verbose output
    python tests/run_all_tests.py --quiet         # Minimal output
    python tests/run_all_tests.py --coverage      # With coverage report
        """
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Run tests with verbose output"
    )
    
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Run tests with minimal output"
    )
    
    parser.add_argument(
        "--coverage", "-c",
        action="store_true",
        help="Run tests with coverage report (requires pytest-cov)"
    )
    
    parser.add_argument(
        "--durations", "-d",
        action="store_true",
        help="Show test durations (slowest 10 tests)"
    )
    
    parser.add_argument(
        "--tb",
        choices=["short", "long", "no"],
        default="short",
        help="Traceback format (default: short)"
    )
    
    args = parser.parse_args()
    
    # Get the project root directory (parent of tests directory)
    tests_dir = Path(__file__).parent
    project_root = tests_dir.parent
    
    # Change to project root for running tests
    import os
    os.chdir(project_root)
    
    # Verify tests directory exists
    if not tests_dir.exists():
        print("Error: tests directory not found.")
        return 1
    
    # Build pytest command
    cmd = [sys.executable, "-m", "pytest", str(tests_dir)]

    # Add output format options
    if args.quiet:
        cmd.append("-q")
    elif args.verbose:
        cmd.append("-v")
    else:
        # Default to moderate verbosity
        cmd.append("-v")
    
    # Add traceback format
    cmd.append(f"--tb={args.tb}")
    
    # Add durations if requested or if verbose
    if args.durations or args.verbose:
        cmd.extend(["--durations=10"])
    
    # Add coverage
    if args.coverage:
        cmd.extend([
            "--cov=app",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov",
            "--cov-fail-under=80"
        ])
        print("Note: Coverage report will be saved to htmlcov/ directory")
    
    # Add common options
    cmd.extend([
        "--strict-markers",
        "--strict-config",
        "--color=yes"
    ])
    
    # Run the tests
    exit_code = run_command(cmd)
    
    # Print summary
    print("-" * 60)
    if exit_code == 0:
        print("✅ All tests passed!")
        if args.coverage:
            print("📊 Coverage report available in htmlcov/index.html")
    else:
        print(f"❌ Tests failed with exit code {exit_code}")
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())