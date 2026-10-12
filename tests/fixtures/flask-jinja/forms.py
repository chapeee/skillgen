"""Server-side validation for the synthetic Flask app."""

import re


def validate_feedback(form):
    errors = {}
    if len(form.get("subject", "")) < 5:
        errors["subject"] = "Subject needs at least 5 characters."
    if form.get("rating") not in {"1", "2", "3", "4", "5"}:
        errors["rating"] = "Choose a rating from 1 to 5."
    if form.get("contact_me") == "on" and not form.get("email"):
        errors["email"] = "Give an email so we can contact you."
    return errors


def validate_application(form):
    errors = {}
    if not re.fullmatch(r"[A-Z]{2}-\d{4}", form.get("vehicle_plate", "")):
        errors["vehicle_plate"] = "Plates look like AB-1234."
    if form.get("duration") not in {"3 months", "6 months", "12 months"}:
        errors["duration"] = "Choose a duration."
    return errors
