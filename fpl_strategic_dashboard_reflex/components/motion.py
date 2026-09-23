"""Motion components powered by motion/react (motion.dev) for smooth layout gliding animations."""

import reflex as rx


class MotionDiv(rx.Component):
    """HTML div element wrapped with motion/react for smooth animations and layout transitions."""

    library = "motion/react"
    tag = "motion.div"
    lib_dependencies: list[str] = ["motion@^12.4.7"]

    # Motion animation props
    initial: rx.Var[dict]
    animate: rx.Var[dict]
    exit: rx.Var[dict]
    transition: rx.Var[dict]
    layout: rx.Var[bool | str]
    layout_id: rx.Var[str]
    while_hover: rx.Var[dict]
    while_tap: rx.Var[dict]


class AnimatePresence(rx.Component):
    """Enables exit animations for child components when they are removed from the React tree."""

    library = "motion/react"
    tag = "AnimatePresence"
    lib_dependencies: list[str] = ["motion@^12.4.7"]

    mode: rx.Var[str]
    initial: rx.Var[bool]


def motion_tab_content(*children, **props) -> rx.Component:
    """Wraps tab content panels in a smooth gliding fade-and-rise entrance animation."""
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
    """Wraps cards with smooth spring layout gliding and entry animation."""
    default_props = {
        "layout": "position",
        "initial": {"opacity": 0, "scale": 0.98},
        "animate": {"opacity": 1, "scale": 1},
        "transition": {"type": "spring", "stiffness": 400, "damping": 30},
        "width": "100%",
    }
    default_props.update(props)
    return MotionDiv.create(*children, **default_props)

