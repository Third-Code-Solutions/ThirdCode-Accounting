#!/usr/bin/env python3
"""Executable adapter for hosted_backup's synchronous delivery contract."""
from hosted_recovery_provider import main

if __name__ == "__main__":
    raise SystemExit(main("deliver"))
