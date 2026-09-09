"""Helper utility functions for Reflex components."""

import reflex as rx


def concat(*args):
    """Safely concatenate strings and Reflex vars into a single Var."""
    if not args:
        return rx.Var.create("")
    v = rx.Var.create(args[0]).to(str)
    for a in args[1:]:
        v = v + rx.Var.create(a).to(str)
    return v


# Attach to rx for convenience across components and pages
if not hasattr(rx, "concat"):
    rx.concat = concat

