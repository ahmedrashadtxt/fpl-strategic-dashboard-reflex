"""CountUp animated number component powered by motion/react (motion.dev).

Animates numeric values smoothly from their previous value to new values using
animate(), useMotionValue, and useTransform over ~800ms with ease-out timing.
Supports thousands separators, prefixes (e.g. £), suffixes (e.g. pts, m, %),
and decimal precision. Respects prefers-reduced-motion.
"""

from typing import Union
import reflex as rx
from reflex.utils.imports import ImportVar, merge_imports


class CountUp(rx.Component):
    """Animated number component using motion/react free API.

    Uses `useMotionValue` + `useTransform` + `animate()`.
    Animates from previous value to new value over ~800ms ease-out.
    """

    tag = "CountUp"
    lib_dependencies: list[str] = ["motion@^12.4.7"]

    value: rx.Var[Union[int, float, str]]
    prefix: rx.Var[str]
    suffix: rx.Var[str]
    decimals: rx.Var[int]
    use_group: rx.Var[bool]
    duration: rx.Var[float]
    stagger: rx.Var[float]
    mode: rx.Var[str]

    def _get_imports(self):
        return merge_imports(
            super()._get_imports(),
            {
                "react": [ImportVar(tag="useEffect"), ImportVar(tag="useRef")],
                "motion/react": [
                    ImportVar(tag="motion"),
                    ImportVar(tag="useReducedMotion"),
                    ImportVar(tag="useMotionValue"),
                    ImportVar(tag="useTransform"),
                    ImportVar(tag="animate"),
                ],
            },
        )

    def _get_custom_code(self) -> str:
        return """
const DIGIT_CYCLE = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9];

function RouletteDigit({ digit, colIndex, duration = 0.65, stagger = 0.04, prefersReduced }) {
    const val = parseInt(digit, 10);
    const targetIndex = 10 + (isNaN(val) ? 0 : val);
    const delay = colIndex * (stagger || 0.04);

    if (prefersReduced) {
        return (
            <span style={{ display: "inline-block", height: "1em", lineHeight: "1" }}>
                {digit}
            </span>
        );
    }

    return (
        <span
            style={{
                display: "inline-block",
                height: "1em",
                overflow: "hidden",
                verticalAlign: "top",
                lineHeight: "1",
                fontVariantNumeric: "tabular-nums",
            }}
        >
            <motion.span
                style={{
                    display: "flex",
                    flexDirection: "column",
                    lineHeight: "1",
                    willChange: "transform",
                }}
                initial={{ y: "0%" }}
                animate={{ y: `-${targetIndex * 5}%` }}
                transition={{
                    duration: duration,
                    delay: delay,
                    ease: [0.16, 1, 0.3, 1],
                }}
            >
                {DIGIT_CYCLE.map((n, i) => (
                    <span
                        key={i}
                        style={{
                            height: "1em",
                            lineHeight: "1",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            fontVariantNumeric: "tabular-nums",
                        }}
                    >
                        {n}
                    </span>
                ))}
            </motion.span>
        </span>
    );
}

function CountUp({
    value = 0,
    prefix = "",
    suffix = "",
    decimals = 0,
    useGroup = false,
    duration = 0.65,
    stagger = 0.04,
    mode = "roulette",
    className = "",
    css,
    style,
}) {
    const spanRef = useRef(null);
    const prevValueRef = useRef(null);
    const count = useMotionValue(0);
    const prefersReduced = useReducedMotion();


    const parseInfo = (v, defaultPrefix, defaultSuffix, defaultDecimals) => {
        if (typeof v === "number") {
            return {
                num: isNaN(v) ? 0 : v,
                pfx: defaultPrefix || "",
                sfx: defaultSuffix || "",
                dec: defaultDecimals !== undefined && defaultDecimals !== null ? defaultDecimals : 0,
            };
        }
        if (!v) {
            return { num: 0, pfx: defaultPrefix || "", sfx: defaultSuffix || "", dec: defaultDecimals || 0 };
        }
        const str = String(v).trim();
        const m = str.replace(/,/g, "").match(/^([^\\d+-]*)([+-]?)(\\d+(?:\\.\\d+)?)(.*)$/);
        if (!m) {
            return { num: 0, pfx: defaultPrefix || str, sfx: defaultSuffix || "", dec: defaultDecimals || 0 };
        }
        const parsedNum = parseFloat(m[3]) * (m[2] === "-" ? -1 : 1);
        const autoPrefix = (defaultPrefix !== undefined && defaultPrefix !== "") ? defaultPrefix : (m[1] + (m[2] === "+" ? "+" : ""));
        const autoSuffix = (defaultSuffix !== undefined && defaultSuffix !== "") ? defaultSuffix : m[4];
        let autoDec = defaultDecimals;
        if (autoDec === undefined || autoDec === null || autoDec === 0) {
            const dot = m[3].indexOf(".");
            autoDec = dot >= 0 ? m[3].length - dot - 1 : 0;
        }
        return {
            num: parsedNum,
            pfx: autoPrefix,
            sfx: autoSuffix,
            dec: autoDec,
        };
    };

    const info = parseInfo(value, prefix, suffix, decimals);

    const format = (latest, pfx, sfx, dec, group) => {
        const val = Number(latest) || 0;
        const sign = val < 0 ? "-" : (pfx.includes("+") ? "+" : "");
        const absVal = Math.abs(val);
        const fixed = absVal.toFixed(dec);
        let [intPart, decPart] = fixed.split(".");
        if (group) {
            intPart = intPart.replace(/\\B(?=(\\d{3})+(?!\\d))/g, ",");
        }
        const cleanPfx = pfx.replace(/[+-]/g, "");
        const decStr = decPart !== undefined && dec > 0 ? "." + decPart : "";
        return `${sign}${cleanPfx}${intPart}${decStr}${sfx}`;
    };

    const display = useTransform(count, (latest) => format(latest, info.pfx, info.sfx, info.dec, useGroup));

    useEffect(() => {
        if (mode !== "count") return;
        const isFirstMount = prevValueRef.current === null;
        const fromVal = isFirstMount ? 0 : prevValueRef.current;
        prevValueRef.current = info.num;

        if (prefersReduced) {
            count.set(info.num);
            if (spanRef.current) {
                spanRef.current.textContent = format(info.num, info.pfx, info.sfx, info.dec, useGroup);
            }
            return;
        }

        if (!isFirstMount && fromVal === info.num) {
            if (spanRef.current) {
                spanRef.current.textContent = format(info.num, info.pfx, info.sfx, info.dec, useGroup);
            }
            return;
        }

        count.set(fromVal);
        const controls = animate(count, info.num, {
            duration: duration,
            ease: "easeOut",
            onUpdate: (latest) => {
                if (spanRef.current) {
                    spanRef.current.textContent = format(latest, info.pfx, info.sfx, info.dec, useGroup);
                }
            },
        });

        return () => controls.stop();
    }, [info.num, info.pfx, info.sfx, info.dec, duration, useGroup, mode, prefersReduced]);

    const formattedStr = format(info.num, info.pfx, info.sfx, info.dec, useGroup);

    if (mode === "roulette") {
        const chars = formattedStr.split("");
        let digitCol = 0;
        return (
            <span
                key={formattedStr}
                className={className}
                css={css}
                style={{
                    display: "inline-flex",
                    alignItems: "center",
                    lineHeight: "1",
                    fontVariantNumeric: "tabular-nums",
                    ...style,
                }}
            >
                {chars.map((char, idx) => {
                    if (/\\d/.test(char)) {
                        const col = digitCol++;
                        return (
                            <RouletteDigit
                                key={idx}
                                digit={char}
                                colIndex={col}
                                duration={duration}
                                stagger={stagger}
                                prefersReduced={prefersReduced}
                            />
                        );
                    }
                    return (
                        <span key={idx} style={{ display: "inline-block", lineHeight: "1" }}>
                            {char === " " ? "\\u00A0" : char}
                        </span>
                    );
                })}
            </span>
        );
    }

    return (
        <span ref={spanRef} className={className} css={css} style={style}>
            {formattedStr}
        </span>
    );
}
"""


def count_up(
    value: rx.Var[Union[int, float, str]],
    prefix: str = "",
    suffix: str = "",
    decimals: int = 0,
    use_group: bool = False,
    duration: float = 0.65,
    stagger: float = 0.04,
    mode: str = "roulette",
    class_name: str = "",
    **props,
) -> rx.Component:
    """Convenience helper to create an animated CountUp number component.

    Supports mode='roulette' (vertical rolling reels) and mode='count' (numeric count-up).
    """
    return CountUp.create(
        value=value,
        prefix=prefix,
        suffix=suffix,
        decimals=decimals,
        use_group=use_group,
        duration=duration,
        stagger=stagger,
        mode=mode,
        class_name=class_name,
        **props,
    )

