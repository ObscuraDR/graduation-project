"""
Pipeline Package
IDS pipeline coordination and background task management
"""

from backend.pipeline.coordinator import PipelineCoordinator, get_coordinator

__all__ = ['PipelineCoordinator', 'get_coordinator']
