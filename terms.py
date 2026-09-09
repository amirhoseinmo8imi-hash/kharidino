from flask import render_template

from app import app


@app.route("/terms")
def terms():
    return render_template("terms.html")
