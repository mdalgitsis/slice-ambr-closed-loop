"""Allocation policies for the slice reconfiguration loop."""

from agents.base import SliceAllocationAgent
from agents.static_baseline import ProportionalFairAgent

__all__ = ["SliceAllocationAgent", "ProportionalFairAgent"]
