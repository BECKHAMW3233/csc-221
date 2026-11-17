"""The "Exit app" button shared by all three Flask apps.

Clicking Exit app in the browser posts to /exit. That tells the launcher
(through app.config["M7LAB_EXIT"], which launcher.run_web_app sets) to
stop this web app and show its menu again in the Command Prompt window.
"""

from flask import current_app, render_template

EXIT_CONFIG_KEY = "M7LAB_EXIT"


def add_exit_route(app, app_title):
    """Add a POST /exit route to app that closes it and returns to the launcher."""

    @app.post("/exit")
    def exit_app():
        notify_launcher = current_app.config.get(EXIT_CONFIG_KEY)
        if notify_launcher is not None:
            notify_launcher()
        return render_template("exit.html", app_title=app_title,
                               from_launcher=notify_launcher is not None)

    return exit_app
