# Bench application — the fill call

Run this once with the browser's JavaScript tool, with the user's values in place of the example ones. The call checks the page itself, so do not take a screenshot or read the page first.

```js
await (async function (S, M, G, V, O) {
  var store = window["__skillgendev"] = window["__skillgendev"] || {};
  var index = {}, n;
  for (n = 0; n < M.length; n++) { index[M[n][0]] = M[n][1]; }
  function find(key) {
    try { return index[key] ? document.querySelector(index[key]) : null; }
    catch (error) { return null; }
  }
  function rectOf(el) { var r = el.getBoundingClientRect(); return r.width || r.height ? r : null; }
  function ev(el, name) { el.dispatchEvent(new Event(name, { bubbles: true })); }
  function put(el, prop, value) {
    var own = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), prop);
    if (own && own.set) { own.set.call(el, value); } else { el[prop] = value; }
  }
  function sleep(ms) { return new Promise(function (go) { setTimeout(go, ms); }); }
  function clickable(node, want) {
    var kids = node.querySelectorAll('*'), i, kid;
    for (i = 0; i < kids.length; i++) {
      kid = kids[i];
      if (kid.children.length === 0 && (kid.textContent || '').trim() === want) { return kid; }
    }
    return node;
  }
  function byText(root, want) {
    var nodes = root.querySelectorAll('[role=option],[role=treeitem],li,option'), i, node;
    for (i = 0; i < nodes.length; i++) {
      node = nodes[i];
      if ((node.textContent || '').trim().indexOf(want) !== 0) { continue; }
      if (node.tagName === 'OPTION') { put(root, 'value', node.value); ev(root, 'change'); }
      else { clickable(node, want).click(); }
      return true;
    }
    return false;
  }
  function manyByText(root, value) {
    var wants = [].concat(value), done = 0, i;
    for (i = 0; i < wants.length; i++) { if (byText(root, String(wants[i]).trim())) { done++; } }
    return done === wants.length ? 'ok' : (done ? 'partial' : 'rejected');
  }
  async function byPath(root, value) {
    var parts = String(value).split(" / "), i;
    for (i = 0; i < parts.length; i++) {
      if (!byText(root, parts[i].trim())) { return 'rejected'; }
      await sleep(60);
    }
    return 'ok';
  }
  function setChoice(selector, value) {
    var nodes = document.querySelectorAll(selector), wants = [].concat(value), done = 0, i, label;
    for (i = 0; i < nodes.length; i++) {
      label = ((nodes[i].parentNode || nodes[i]).textContent || '').trim();
      if (wants.indexOf(label) < 0 && wants.indexOf(nodes[i].value) < 0) { continue; }
      if (!nodes[i].checked) { nodes[i].click(); }
      if (nodes[i].checked) { done++; }
    }
    return done === wants.length ? 'ok' : (done ? 'partial' : 'rejected');
  }
  async function byCombobox(el, value) {
    el.focus(); put(el, 'value', String(value)); ev(el, 'input');
    await sleep(900);
    var id = el.getAttribute('aria-controls') || el.getAttribute('aria-owns');
    var list = id ? document.getElementById(id) : null;
    if (!list) { return 'escalate'; }
    return byText(list, String(value)) ? 'ok' : 'rejected';
  }
  async function one(selector, code, value) {
    if (code === 'f' || code === 'x') { return 'escalate'; }
    if (code === 'c') { return setChoice(selector, value); }
    var el = document.querySelector(selector);
    if (!el) { return 'missing'; }
    if (code === 'r') { el.textContent = String(value); ev(el, 'input'); return 'ok'; }
    if (code === 't') { return byPath(el, value); }
    if (code === 'l') { return manyByText(el, value); }
    if (code === 'b') { return byCombobox(el, value); }
    if (code === 's') {
      put(el, 'value', String(value)); ev(el, 'change');
      if (String(el.value) === String(value)) { return 'ok'; }
      return byText(el, String(value)) ? 'ok' : 'rejected';
    }
    var kind = el.type || '';
    if (kind === 'checkbox' || kind === 'radio') {
      if (el.checked !== !!value) { el.click(); }
      return el.checked === !!value ? 'ok' : 'rejected';
    }
    put(el, 'value', String(value)); ev(el, 'input'); ev(el, 'change');
    return String(el.value) === String(value) ? 'ok' : 'rejected';
  }
  function verify() {
    var vw = window.innerWidth, vh = window.innerHeight, same = Math.abs(vw - G.w) <= 8;
    var out = { state: 'changed', score: 0, viewport: [vw, vh], built: [G.w, G.h] };
    var anchor = find(G.a), base = anchor && rectOf(anchor);
    if (!base) { out.failed = [G.a + ':missing']; return out; }
    var failed = [], covered = [], seen = 0, floor = -Infinity, i, row, el, r, left, top, x, y, hit;
    for (i = 0; i < G.b.length; i++) {
      row = G.b[i]; el = find(row[0]); r = el && rectOf(el);
      if (!r) { failed.push(row[0] + (el ? ':hidden' : ':missing')); continue; }
      left = r.left - base.left; top = r.top - base.top;
      if (top < floor - Math.max(24, row[4] / 2)) { failed.push(row[0] + ':order'); continue; }
      floor = Math.max(floor, top);
      if (same && (Math.abs(left - row[1]) > Math.max(16, vw * 0.03)
          || Math.abs(top - row[2]) > Math.max(24, Math.abs(row[2]) * 0.06)
          || Math.abs(r.height - row[4]) > Math.max(10, row[4] * 0.3))) {
        failed.push(row[0] + ':moved'); continue;
      }
      x = r.left + r.width / 2; y = r.top + r.height / 2;
      if (x < 0 || y < 0 || x >= vw || y >= vh) { continue; }
      seen++; hit = document.elementFromPoint(x, y);
      if (hit && hit !== el && !el.contains(hit) && !hit.contains(el)) { covered.push(row[0]); }
    }
    out.score = Math.round(100 * (G.b.length - failed.length) / G.b.length) / 100;
    if (failed.length) { out.failed = failed; }
    if (covered.length) { out.covered = covered; }
    if (covered.length * 2 > seen && covered.length) { out.state = 'blocked'; }
    else if (out.score >= 0.85) { out.state = same ? 'match' : 'resized'; }
    return out;
  }
  function locate(key) {
    var el = find(key), r;
    if (!el) { return 'missing'; }
    el.scrollIntoView({ block: 'center', inline: 'nearest' });
    r = rectOf(el);
    return r ? [Math.round(r.left + r.width / 2), Math.round(r.top + r.height / 2)] : 'hidden';
  }
  async function fill(values) {
    var R = {}, known = {}, i, row, k;
    for (i = 0; i < M.length; i++) {
      row = M[i]; k = row[0]; known[k] = 1;
      if (!(k in values)) { continue; }
      if (row[3]) { await sleep(900); }
      try { R[k] = await one(row[1], row[2], values[k]); } catch (error) { R[k] = 'escalate'; }
    }
    for (k in values) { if (!known[k]) { R[k] = 'unknown'; } }
    return R;
  }
  async function run(values, options) {
    var report = {};
    if (!(options && options.verify === false)) {
      report.layout = verify();
      if (report.layout.state === 'changed' || report.layout.state === 'blocked') {
        return JSON.stringify(report);
      }
    }
    report.fill = await fill(values || {});
    return JSON.stringify(report);
  }
  store[S] = { run: run, locate: locate };
  return run(V, O);
})(
"bench-apply",
[["full_name","#full_name","i"],["email","#email","i"],["username","#username","i"],["birth_date","#birth_date","i"],["bio","#bio","i"],["account_type","input[name=\"account_type\"]","c"],["company_name","#company_name","i"],["registration_no","#registration_no","i"],["team_size","#team_size","s"],["country","#country","s"],["region","#region","s",1],["city","#city","b",1],["interests","input[name=\"interests\"]","c"],["department","#department","t"],["skills","#skills","l"],["newsletter","#newsletter","i"],["statement","#statement","r"],["references[].name",".reference-row input[data-field=name]","i"],["references[].email",".reference-row input[data-field=email]","i"],["id_document","#id_document","f"],["agree_terms","#agree_terms","i"]],
{"w":1280,"h":900,"a":"full_name","b":[["full_name",0,0,654,42],["username",0,160,654,42],["bio",0,347,654,90],["country",0,721,654,41],["city",0,879,654,42],["department",0,1198,654,84],["newsletter",4,1367,13,13],["agree_terms",-13,1961,13,13]]},
{"full_name":"Sample full name","email":"alex@example.com","username":"aaa","birth_date":"1990-01-15","account_type":"Individual","country":"Atlantis","department":"Engineering / Platform / Reliability","statement":"Sample text for this field.","agree_terms":true,"references[].name":"Sample reference name","references[].email":"alex@example.com"},
{}
)
```

It first checks the page against the layout this skill was built from. `layout.state`:
- `match`, or `resized` (the same form on another screen size): the form was filled.
- `blocked` (a dialog or prompt covers the form) or `changed` (not the layout expected): nothing was filled. Take a screenshot and inspect the page as usual, then fill with `await window["__skillgendev"]["bench-apply"].run({...}, {"verify": false})`, or stop and tell the user if it is the wrong page.

The check is a shortcut, never a gate: you may always inspect the page yourself and fill with that call.

Seen on the live page when this skill was made: 16 of 19 fields, in a 1280x900 window. The others come from the code and were not seen there. Every measured position is in `references/layout.json`; read it only to check the page by hand, and measure a field on the screen again before clicking it.

`fill` has one status per key:
- `ok` — set, and read back as the value given.
- `partial` — some of a multi-value field matched; the rest did not.
- `rejected` — the field would not take the value. Ask the user, do not retry blind.
- `missing` — the field is not on the page. Either it is hidden until another field is set, or the app has changed.
- `escalate` — the setter cannot do this field. Read `scripts/fill.js`, run it, and use it for those keys only; if it cannot set them either, use method 2 or 3.
- `unknown` — that key is not on this page; check the table below.

To add values the user gives later, run the short call instead of the whole block: `await window["__skillgendev"]["bench-apply"].run({...})`. If the page has reloaded since, run the whole block again.

For a field you do by hand, first run `window["__skillgendev"]["bench-apply"].locate("id_document")`: it scrolls the field into view and returns its centre `[x, y]` on this screen. Never reuse a position from an earlier screenshot or screen size.

When nothing is left, click "Submit application" and check the result as SKILL.md says under "Submit and verify".

`references` (Reference) is a repeating row: pass `references[].name`, `references[].email` for the first row. At least 1 row(s) are needed. For more than one row, read `scripts/fill.js` and use it instead; the setter fills only the first row.
