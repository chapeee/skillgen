# Return items — by hand

Plain steps by what the page shows, for when no automated method works: follow them with ordinary clicks and typing, or give them to the user. Take every value from the user and never invent one. If a login page, CAPTCHA or two-factor prompt appears, the user has to deal with it.

1. Open the app's /orders/:orderId/return page.
2. **The form**
    - Reason: choose one (Damaged · Wrong item · No longer needed). Required.
3. **Item**, for each one the user gives (add another row if needed):
    - SKU: type it (text).
    - Quantity: type it (number, at least 1).
4. **The form**
    - Refund to: choose one (Original payment · Store credit). Required.
5. Check every value, then click "Request return", and only when the user has asked to submit.
