import reflex as rx

config = rx.Config(
    app_name="fpl_strategic_dashboard_reflex",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
        rx.plugins.RadixThemesPlugin(
            theme=rx.theme(
                appearance="dark",
                accent_color="blue",
                gray_color="slate",
                radius="medium",
            )
        ),
    ]
)