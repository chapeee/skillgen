# Give feedback — the fill call

Run this once with the browser's JavaScript tool, with the user's values in place of the example ones. Everything the call needs is here; do not read any other file first.

```js
await (async function (S, M, G, V, O) {
  var store = window["__skillgendev"] = window["__skillgendev"] || {};
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
  async function run(values) {
    return JSON.stringify({ fill: await fill(values || {}) });
  }
  store[S] = { run: run };
  return run(V, O);
})(
"fixture-council-feedback",
[["department","#department","s"],["subject","#subject","i"],["rating","input[name=rating]","c"],["details","#details","i"],["contact_me","#contact_me","i"],["email","#email","i"]],
null,
{"department":"Library","subject":"Sample subject","rating":"1"},
{}
)
```

`fill` has one status per key:
- `ok` — set, and read back as the value given.
- `partial` — some of a multi-value field matched; the rest did not.
- `rejected` — the field would not take the value. Ask the user, do not retry blind.
- `missing` — the field is not on the page. Either it is hidden until another field is set, or the app has changed.
- `escalate` — the setter cannot do this field. Read `scripts/fill.js`, run it, and use it for those keys only; if it cannot set them either, use method 2 or 3.
- `unknown` — that key is not on this page; check the table below.

To add values the user gives later, run the short call instead of the whole block: `await window["__skillgendev"]["fixture-council-feedback"].run({...})`. If the page has reloaded since, run the whole block again.

When nothing is left, click "Send feedback" and check the result as SKILL.md says under "Submit and verify".
