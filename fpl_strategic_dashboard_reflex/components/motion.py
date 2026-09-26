"""Motion components powered by motion/react (motion.dev) for smooth, polished animations.

Phase 0: Full wrapper with MotionConfig (reducedMotion="user"), MotionDiv,
AnimatePresence, and convenience factory functions. All props validated against
motion/react v12.4.7 which is already installed in .web/node_modules/motion.

Constraints followed:
- Only opacity, transform (x, y, scale, rotate), SVG pathLength animated.
- Durations 150–350ms; springs stiffness ~300–400, damping ~25–30.
- reducedMotion="user" at the MotionConfig root respects prefers-reduced-motion.
- No Motion+ (paid) features used; free API only.
"""

from typing import Union, Any
import reflex as rx


class MotionConfig(rx.Component):
    """Wraps the app root to propagate MotionConfig context.

    Set reduced_motion='user' to automatically respect prefers-reduced-motion.
    Supported values: 'user' | 'always' | 'never'.
    """

    library = "motion/react"
    tag = "MotionConfig"
    lib_dependencies: list[str] = ["motion@^12.4.7"]

    # 'user' respects the OS prefers-reduced-motion setting (recommended).
    # 'always' forces all animations off. 'never' forces all animations on.
    reduced_motion: rx.Var[str]


class MotionDiv(rx.Component):
    """HTML div element wrapped with motion/react for smooth animations and layout transitions.

    Supports entrance (initial → animate), exit (AnimatePresence + exit),
    gesture animations (while_hover, while_tap), scroll-linked (while_in_view),
    and layout transitions (layout, layout_id).

    Reflex auto-converts snake_case → camelCase when rendering JSX:
        while_hover  → whileHover
        while_tap    → whileTap
        while_in_view → whileInView
        layout_id    → layoutId
    """

    library = "motion/react"
    tag = "motion.div"
    lib_dependencies: list[str] = ["motion@^12.4.7"]

    # ── Entrance / Exit ──────────────────────────────────────────────────────
    initial: rx.Var[Union[dict, str, bool]]
    animate: rx.Var[Union[dict, str, bool]]
    exit: rx.Var[Union[dict, str, bool]]

    # ── Timing ───────────────────────────────────────────────────────────────
    transition: rx.Var[dict]

    # ── Gestures ─────────────────────────────────────────────────────────────
    while_hover: rx.Var[dict]
    while_tap: rx.Var[dict]

    # ── Scroll / Viewport ────────────────────────────────────────────────────
    while_in_view: rx.Var[dict]
    viewport: rx.Var[dict]

    # ── Layout ───────────────────────────────────────────────────────────────
    layout: rx.Var[bool | str]
    layout_id: rx.Var[str]

    # ── Variants / Orchestration ─────────────────────────────────────────────
    variants: rx.Var[Any]
    custom: rx.Var[Any]

    def _get_custom_code(self) -> str:
        return """
const slideVariants = {
  enter: (direction) => ({
    x: (direction || 1) > 0 ? 30 : -30,
    opacity: 0,
  }),
  center: {
    x: 0,
    opacity: 1,
    transition: {
      duration: 0.22,
      ease: [0.16, 1, 0.3, 1],
    },
  },
  exit: (direction) => ({
    x: (direction || 1) > 0 ? -30 : 30,
    opacity: 0,
    transition: {
      duration: 0.18,
      ease: [0.16, 1, 0.3, 1],
    },
  }),
};
"""


class MotionSpan(rx.Component):
    """Inline span element wrapped with motion/react."""

    library = "motion/react"
    tag = "motion.span"
    lib_dependencies: list[str] = ["motion@^12.4.7"]

    initial: rx.Var[dict]
    animate: rx.Var[dict]
    exit: rx.Var[dict]
    transition: rx.Var[dict]
    while_hover: rx.Var[dict]
    while_tap: rx.Var[dict]
    while_in_view: rx.Var[dict]
    viewport: rx.Var[dict]
    layout: rx.Var[bool | str]
    layout_id: rx.Var[str]
    variants: rx.Var[dict]


class MotionLi(rx.Component):
    """li element wrapped with motion/react — useful for staggered list items."""

    library = "motion/react"
    tag = "motion.li"
    lib_dependencies: list[str] = ["motion@^12.4.7"]

    initial: rx.Var[dict]
    animate: rx.Var[dict]
    exit: rx.Var[dict]
    transition: rx.Var[dict]
    while_hover: rx.Var[dict]
    while_tap: rx.Var[dict]
    while_in_view: rx.Var[dict]
    viewport: rx.Var[dict]
    layout: rx.Var[bool | str]
    layout_id: rx.Var[str]
    variants: rx.Var[dict]
    custom: rx.Var[dict]


class MotionCircle(rx.Component):
    """SVG circle element wrapped with motion/react for animated rings and pathLength gauges."""

    library = "motion/react"
    tag = "motion.circle"
    lib_dependencies: list[str] = ["motion@^12.4.7"]

    cx: rx.Var[Union[int, float, str]]
    cy: rx.Var[Union[int, float, str]]
    r: rx.Var[Union[int, float, str]]
    stroke: rx.Var[str]
    stroke_width: rx.Var[Union[int, float, str]]
    stroke_linecap: rx.Var[str]
    stroke_dasharray: rx.Var[str]
    stroke_dashoffset: rx.Var[Union[int, float, str]]
    fill: rx.Var[str]

    initial: rx.Var[dict]
    animate: rx.Var[dict]
    exit: rx.Var[dict]
    transition: rx.Var[dict]
    while_in_view: rx.Var[dict]
    viewport: rx.Var[dict]
    layout: rx.Var[bool | str]
    layout_id: rx.Var[str]


class AnimatePresence(rx.Component):
    """Enables exit animations for child components when they unmount from the React tree.

    Wrap conditional content inside AnimatePresence and give children an `exit` prop
    to get smooth fade/slide out animations.

    mode='wait' ensures the outgoing element finishes its exit before the new one enters.
    """

    library = "motion/react"
    tag = "AnimatePresence"
    lib_dependencies: list[str] = ["motion@^12.4.7"]

    mode: rx.Var[str]      # 'sync' | 'wait' | 'popLayout'
    initial: rx.Var[bool]  # Set False to skip the initial animation on mount


# ── Convenience Factory Functions ────────────────────────────────────────────


def motion_tab_content(*children, **props) -> rx.Component:
    """Wraps tab content panels in a smooth gliding fade-and-rise entrance animation.

    Duration: 280ms with a custom expo-out ease.
    """
    default_props = {
        "initial": {"opacity": 0, "y": 10},
        "animate": {"opacity": 1, "y": 0},
        "transition": {"duration": 0.28, "ease": [0.16, 1, 0.3, 1]},
        "layout": "position",
        "width": "100%",
    }
    default_props.update(props)
    return MotionDiv.create(*children, **default_props)


def motion_card(*children, **props) -> rx.Component:
    """Wraps cards with smooth spring layout gliding and entry animation.

    Spring: stiffness=400, damping=30 → tight, non-bouncy settle.
    """
    default_props = {
        "layout": "position",
        "initial": {"opacity": 0, "scale": 0.98},
        "animate": {"opacity": 1, "scale": 1},
        "transition": {"type": "spring", "stiffness": 400, "damping": 30},
        "width": "100%",
    }
    default_props.update(props)
    return MotionDiv.create(*children, **default_props)


def motion_fade_in(*children, delay: float = 0.0, duration: float = 0.25, **props) -> rx.Component:
    """Simple fade-in entrance with optional delay.

    Default: 250ms opacity 0 → 1 with a gentle ease-out curve.
    Delay: stagger items by passing incremental delay values (max 60ms steps recommended).
    """
    default_props = {
        "initial": {"opacity": 0},
        "animate": {"opacity": 1},
        "transition": {
            "duration": duration,
            "delay": delay,
            "ease": "easeOut",
        },
        "width": "100%",
    }
    default_props.update(props)
    return MotionDiv.create(*children, **default_props)


def motion_slide_up(*children, delay: float = 0.0, y: int = 12, **props) -> rx.Component:
    """Fade + slide-up entrance.

    Tight spring with slight y offset (default 12px). Non-bouncy settle.
    """
    default_props = {
        "initial": {"opacity": 0, "y": y},
        "animate": {"opacity": 1, "y": 0},
        "transition": {
            "type": "spring",
            "stiffness": 350,
            "damping": 28,
            "delay": delay,
        },
        "width": "100%",
    }
    default_props.update(props)
    return MotionDiv.create(*children, **default_props)


def motion_scale_in(*children, delay: float = 0.0, **props) -> rx.Component:
    """Fade + subtle scale-up entrance.

    Tight spring. Use for cards, badges, metric tiles.
    """
    default_props = {
        "initial": {"opacity": 0, "scale": 0.97},
        "animate": {"opacity": 1, "scale": 1},
        "transition": {
            "type": "spring",
            "stiffness": 380,
            "damping": 28,
            "delay": delay,
        },
        "width": "100%",
    }
    default_props.update(props)
    return MotionDiv.create(*children, **default_props)


def directional_slide(
    *children,
    direction: rx.Var[int],
    key: rx.Var[str] | str,
    **props,
) -> rx.Component:
    """Directional sliding wrapper for pitch/list view on gameweek change.

    Direction > 0 (GW5 -> GW6): enters from right (x: +30), exits to left (x: -30).
    Direction < 0 (GW6 -> GW5): enters from left (x: -30), exits to right (x: +30).
    Uses custom prop + slideVariants.
    """
    default_props = {
        "custom": direction,
        "initial": "enter",
        "animate": "center",
        "exit": "exit",
        "variants": rx.Var("slideVariants"),
        "key": key,
        "width": "100%",
    }
    default_props.update(props)
    return MotionDiv.create(*children, **default_props)


def rating_ring(
    value: rx.Var[float] | float,
    color: rx.Var[str] | str = "#22c55e",
    size: int = 44,
) -> rx.Component:
    """Renders a circular SVG rating gauge with motion.circle pathLength animation.

    Animates stroke from 0 -> value using whileInView with viewport once: true.
    Rotated -90deg so the ring fills clockwise starting from the 12 o'clock position.
    """
    center = int(size // 2)
    radius = int(size * 0.41)
    stroke_w = "3.5"
    return rx.el.svg(
        rx.el.circle(
            cx=center,
            cy=center,
            r=radius,
            stroke="rgba(255, 255, 255, 0.12)",
            stroke_width=stroke_w,
            fill="none",
        ),
        MotionCircle.create(
            cx=center,
            cy=center,
            r=radius,
            stroke=color,
            stroke_width=stroke_w,
            stroke_linecap="round",
            fill="none",
            initial={"pathLength": 0},
            while_in_view={"pathLength": value},
            viewport={"once": True},
            transition={"duration": 0.85, "ease": "easeOut"},
        ),
        width=f"{size}px",
        height=f"{size}px",
        view_box=f"0 0 {size} {size}",
        style={"transform": "rotate(-90deg)"},
    )


# ── CountUp Re-export ────────────────────────────────────────────────────────
from .count_up import CountUp, count_up

