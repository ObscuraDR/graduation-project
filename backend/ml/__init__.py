"""
Backward compatibility layer mapping backend.ml to top-level ai module.
"""
import sys
import ai

sys.modules['backend.ml'] = ai
