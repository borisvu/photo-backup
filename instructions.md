---
aliases:
tags:
  - instructions
  - implementation
  - backup
  - project
creation_date: 2025-06-21
---

# Photo Backup Implementation Instructions

## Overview

You're an engineer building a photo backup system. You've been given architecture.md and tasks.md which define the complete system design and implementation steps.

## Your Mission

- Read both architecture.md and tasks.md carefully. There should be no ambiguity about what we're building
- Follow tasks.md and complete one task at a time
- After each task, stop. I'll test it. If it works, commit to GitHub and move to the next

## Project Context

This is a personal photo backup system that:

- Monitors a 4TB external SSD with ~1.2TB of photos
- Backs up to Wasabi S3 storage
- Runs automatically on macOS when the drive is connected
- Provides integrity verification and auto-repair
- Uses Minio for local testing to avoid Wasabi costs during development

## Coding Protocol

### Core Rules

- Write the absolute minimum code required
- No sweeping changes
- No unrelated edits
- Focus on just the task you're on
- Make code precise, modular, testable
- Don't break existing functionality
- If I need to do anything (e.g. Wasabi config), tell me clearly

### Testing Approach

- For testing: create functional tests that execute via main.py
- Use Minio (S3-compatible) to simulate Wasabi for backup tests
- Test code should live alongside implementation (not separate test files)
- Use pytest for testing.
- Every feature should be testable in test mode without real credentials or external services

### Test Mode

The system has a built-in test mode that:

- Uses Minio instead of Wasabi (localhost:9000)
- Uses hardcoded test credentials (minioadmin/minioadmin)
- Operates on test directories (/tmp/photo-backup-test/)
- Runs with accelerated timers (minutes instead of hours)
- Skips 1Password integration
- Provides verbose logging

### Code Style

- Use clear, descriptive names
- Add docstrings to classes and major functions
- Keep functions small and focused
- Use type hints where helpful
- Follow PEP 8
- Add inline comments only where logic isn't obvious

### Error Handling

- Catch specific exceptions, not broad Exception
- Provide helpful error messages
- Log errors appropriately
- In test mode, be extra verbose about what went wrong

### File Organization

- Follow the structure defined in architecture.md
- Each module should have a single, clear purpose
- Keep related functionality together
- Don't create files not specified in the tasks

## Implementation Flow

### Starting a Task

1. Read the task description carefully
2. Check if any previous tasks need updates
3. Implement only what's specified
4. Add any necessary imports
5. Include a simple way to test the functionality

### Testing a Task

1. If the task has a **Test** section, implement that exact test
2. For features that interact with S3, always use test mode with Minio
3. Make tests runnable from command line
4. Ensure tests clean up after themselves
5. Ensure that all other tests pass.

### Completing a Task

1. Verify the test passes
2. Check you haven't broken previous functionality
3. Ensure code follows the protocol
4. Wait for my confirmation before proceeding

## Special Considerations

### Minio Testing

- Assume Minio will be running at localhost:9000
- Use bucket name: my-photo-backup-bucket-test
- If Minio isn't running, provide clear error message with setup instructions

### Configuration

- Test mode should override production settings automatically
- Never hardcode production credentials
- Always validate configuration before use

### State Management

- Use JSON for simple state files
- SQLite for history/log data
- Always use test directories in test mode

### Platform-Specific Code

- This is for macOS only
- Use macOS-specific paths (~/Library/...)
- Assume launchd for service management

## What I'll Do

- Run tests after each task
- Verify functionality works as expected
- Commit to GitHub when task is complete
- Provide feedback if adjustments needed
- Handle any external configuration (Wasabi setup, etc.)

## What You Should Tell Me

- If a task seems too large or unclear
- If you discover missing dependencies
- If previous code needs refactoring to support new features
- If you need me to perform any manual steps
- If you find conflicts between tasks and architecture

## Example Task Implementation

For a task like "Create Logger Module":

```python
# photo_backup/logger.py
"""Logging configuration for photo backup system."""

import logging
import sys

def setup_logger(name="photo_backup", level=logging.INFO):
    """Set up logger with console output.

    Args:
        name: Logger name
        level: Logging level

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Console handler
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger

# Quick test
if __name__ == "__main__":
    log = setup_logger()
    log.info("Test message")
```

## Remember

- One task at a time
- Minimum viable implementation
- Test mode for everything S3-related
- Stop after each task for testing
- Keep it simple and working
