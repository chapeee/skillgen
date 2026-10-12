"""Synthetic test app: Flask with Jinja templates. Never run by the tests."""

from flask import Flask, redirect, render_template, request

from forms import validate_application, validate_feedback

app = Flask(__name__)

DEPARTMENTS = ["Library", "Parks", "Transport", "Waste"]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/feedback", methods=["GET", "POST"])
def feedback():
    errors = {}
    if request.method == "POST":
        errors = validate_feedback(request.form)
        if not errors:
            return redirect("/feedback/sent")
    return render_template("feedback.html", departments=DEPARTMENTS, errors=errors)


@app.route("/permits/<int:permit_id>/renew", methods=["GET", "POST"])
def renew_permit(permit_id):
    errors = {}
    if request.method == "POST":
        errors = validate_application(request.form)
        if not errors:
            return redirect(f"/permits/{permit_id}")
    return render_template("renew.html", errors=errors)
