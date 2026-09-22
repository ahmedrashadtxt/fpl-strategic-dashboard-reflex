"""Compatibility module re-exporting AppState from states.base."""

from fpl_strategic_dashboard_reflex.states.base import AppState

State = AppState

__all__ = ["AppState", "State"]
