"""Interactive spotlight walkthrough tour component powered by driver.js.

Phase 2: Reflex wrapper for driver.js with custom Apple HIG dark styling,
zero-latency client-side step progression, and resilient DOM selector resolution.
"""

from typing import Any
import reflex as rx
from reflex.utils.imports import ImportVar, merge_imports

from .tour_config import TOUR_STEPS_BY_TAB


class TourDriver(rx.Component):
    """Client-side React component initializing and driving driver.js tours."""

    tag = "TourDriver"
    lib_dependencies: list[str] = ["driver.js@^1.8.0"]

    steps_data: rx.Var[dict[str, Any]]

    def _get_imports(self):
        return merge_imports(
            super()._get_imports(),
            {
                "react": [ImportVar(tag="useEffect")],
                "driver.js": [ImportVar(tag="driver")],
                "driver.js/dist/driver.css": [],
            },
        )

    def _get_custom_code(self) -> str:
        return """
function TourDriver({ stepsData }) {
    useEffect(() => {
        if (typeof window === "undefined") return;

        window.fplTourSteps = stepsData || {};
        let activeDriver = null;

        window.fplStartTour = function(tabKey) {
            const rawSteps = (window.fplTourSteps && window.fplTourSteps[tabKey]) || [];
            if (!rawSteps.length) {
                console.warn("[TourDriver] No steps configured for tab:", tabKey);
                return;
            }

            // Filter to target elements that actually exist in the current DOM
            const validSteps = [];
            for (const step of rawSteps) {
                const targetId = step.target_id;
                const el = document.getElementById(targetId) ||
                           document.querySelector(`[data-tour-id="${targetId}"]`) ||
                           document.querySelector(targetId.startsWith("#") || targetId.startsWith(".") ? targetId : `#${targetId}`);
                if (el) {
                    validSteps.push({
                        element: el,
                        popover: {
                            title: step.title,
                            description: step.body,
                            side: step.placement || "bottom",
                            align: "start",
                            showButtons: ["next", "previous", "close"],
                            showProgress: true,
                            progressText: "{{current}} of {{total}}",
                            nextBtnText: "Next →",
                            prevBtnText: "← Back",
                            doneBtnText: "Done",
                        }
                    });
                }
            }

            if (!validSteps.length) {
                console.warn("[TourDriver] No targets currently present in DOM for tab:", tabKey);
                return;
            }

            if (activeDriver) {
                try { activeDriver.destroy(); } catch (e) {}
            }

            activeDriver = driver({
                animate: true,
                duration: 350,
                allowClose: true,
                showButtons: ["next", "previous", "close"],
                showProgress: true,
                progressText: "{{current}} of {{total}}",
                stagePadding: 8,
                stageRadius: 10,
                smoothScroll: true,
                skipMissingElement: true,
                steps: validSteps,
                nextBtnText: "Next →",
                prevBtnText: "← Back",
                doneBtnText: "Done",
                // Backdrop click does NOT advance or dismiss the tour
                overlayClickBehavior: () => {},
                onDestroyStarted: () => {
                    try {
                        localStorage.setItem("tour-dismissed-" + tabKey, "true");
                    } catch (e) {}
                    if (activeDriver) {
                        activeDriver.destroy();
                    }
                },
                onDestroyed: () => {
                    try {
                        localStorage.setItem("tour-dismissed-" + tabKey, "true");
                    } catch (e) {}
                }
            });

            activeDriver.drive();
        };

        return () => {
            if (activeDriver) {
                try { activeDriver.destroy(); } catch (e) {}
            }
        };
    }, [stepsData]);

    return null;
}
"""


def tour_driver() -> rx.Component:
    """Mounts the TourDriver singleton with full central step configuration."""
    return TourDriver.create(steps_data=TOUR_STEPS_BY_TAB)


def tour_button(tab_key: str) -> rx.Component:
    """Renders the 'Take a Tour' primary action button for the active tab."""
    return rx.button(
        rx.hstack(
            rx.icon("compass", size=15, color="var(--color-interactive, #38bdf8)"),
            rx.text(
                "Take a Tour",
                font_weight="600",
                font_size="0.82rem",
                color="var(--color-interactive, #38bdf8)",
            ),
            align="center",
            spacing="2",
        ),
        variant="surface",
        color_scheme="blue",
        size="2",
        radius="full",
        cursor="pointer",
        on_click=rx.call_script(f"window.fplStartTour && window.fplStartTour('{tab_key}')"),
        class_name="take-tour-button",
    )
