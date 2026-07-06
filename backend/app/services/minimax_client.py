"""Compatibility shim for legacy imports.

The project has migrated to DeepSeek, but some modules or historical scripts may
still import `MiniMaxClient`. Keep that import path working while the main code
uses `DeepSeekClient`.
"""

from app.services.deepseek_client import DeepSeekClient


MiniMaxClient = DeepSeekClient
