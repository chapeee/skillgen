# Bench application — by hand

Plain steps by what the page shows, for when no automated method works: follow them with ordinary clicks and typing, or give them to the user. Take every value from the user and never invent one. If a login page, CAPTCHA or two-factor prompt appears, the user has to deal with it.

1. Open http://localhost:8765/apply.
2. **Applicant**
    - Full name: type it (text, 3–80 chars). Required.
    - Email: type it (email address). Required.
    - Username: type it (text, 3–20 lowercase letters, digits or underscores). Required.
    - Date of birth: type it (date, YYYY-MM-DD). Required.
    - Short bio: type it (text, up to 500 chars).
3. **Organisation**
    - Account type: choose one (Individual · Company). Required.
    - Company name: type it (text). Required if Account type is Company. Shown only when Account type is Company.
    - Registration number: type it (text, two capital letters then six digits, like AB123456). Required if Account type is Company. Shown only when Account type is Company.
    - Team size: choose one (1–10 · 11–50 · 51–200 · 201 or more). Shown only when Account type is Company.
4. **Location**
    - Country: choose one (Atlantis · Borduria · Freedonia · Genovia). Required.
    - Region: choose one (option from the list). Required. Its list fills in after Country.
    - City: type it, then pick it from the list that opens (option from the list). Required.
5. **Preferences**
    - Interests: tick each one wanted (one or more of: Design · Engineering · Research · Sales · Support).
    - Department: open the list and pick each level in turn (Engineering / Platform / Reliability · Engineering / Platform / Tooling · Engineering / Product / Web · Engineering / Product / Mobile · Operations / Finance · Operations / People · Research). Required.
    - Skills: tick each one wanted (one or more of: Python · JavaScript · SQL · Go · Rust).
    - Send me the newsletter: tick it for yes, leave it clear for no.
6. **Statement**
    - Why are you applying?: click inside the editor and type it (formatted text). Required.
7. **Reference**, for each one the user gives (add another row if needed):
    - Reference name: type it (text).
    - Reference email: type it (email address).
8. **Documents**
    - Identity document (PDF or JPG, up to 2 MB): upload the file the user gives (file, .pdf .jpg .jpeg, 2 MB).
9. **Declaration**
    - I confirm the details above are correct: tick it for yes, leave it clear for no. Required.
10. Check every value, then click "Submit application", and only when the user has asked to submit. It worked if the URL contains /apply/done and the page shows "Application received".

## Watch out
- Region stays empty until Country is chosen; its list loads from the server.
- City is a search box: type the city and pick it from the list, or it is not saved.
- Submit stays disabled until the declaration checkbox is ticked.
