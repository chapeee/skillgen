# Create your account — by hand

Plain steps by what the page shows, for when no automated method works: follow them with ordinary clicks and typing, or give them to the user. Take every value from the user and never invent one. If a login page, CAPTCHA or two-factor prompt appears, the user has to deal with it.

1. Open the app's /signup page.
2. **The form**
    - Full name: type it (text, up to 80 chars). Required.
    - Work email: type it (email address). Required.
    - Password: set it as the page shows, or ask the user to (text, at least 12 characters). Required.
    - Plan: choose one (Starter · Team · Enterprise). Required.
    - Number of seats: type it (number). Required if Plan is Enterprise. Shown only when Plan is Enterprise.
    - I accept the terms: tick it for yes, leave it clear for no. Required.
3. Check every value, then click "Create account", and only when the user has asked to submit. It worked if the URL contains /welcome.

## Watch out
- Number of seats appears only after choosing the Enterprise plan.
