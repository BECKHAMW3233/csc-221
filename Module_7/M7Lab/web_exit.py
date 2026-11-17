"""The "Exit" button shared by all three Flask apps.

Every app page has an Exit button that posts to EXIT_URL. That route shows a
"this app is closed" page and then tells the launcher to stop the web server,
so the launcher goes straight back to its menu in the command prompt window.

The launcher passes in what to do on exit through app.config["ON_EXIT"].
When an app runs without the launcher (for example in the unit tests),
there is nothing to stop, so the route just shows the closed page.
"""

from flask import render_template

EXIT_URL = "/exit-app"


def add_exit_route(app, app_title):
    """Add the Exit button's route to a Flask app and make EXIT_URL usable in its templates."""
    app.jinja_env.globals["exit_url"] = EXIT_URL

    @app.post(EXIT_URL)
    def exit_app():
        response = app.make_response(render_template("exited.html", app_title=app_title))
        on_exit = app.config.get("ON_EXIT")
        if on_exit is not None:
            # Wait until the page has been sent to the browser, then stop the server.
            response.call_on_close(on_exit)
        return response

    return app
