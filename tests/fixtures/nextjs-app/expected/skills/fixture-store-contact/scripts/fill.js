/* skillgendev fill.js for skill fixture-store-contact. Generated from the page model; regenerate instead of editing. */
(function () {
  'use strict';
  var SKILL = {"name":"fixture-store-contact","host":"","engine":1};
  var SUBMIT = {"s":"button[type=submit]","url":"/contact/thanks","text":""};
  var GROUPS = [];
  var FIELDS = [
    {"k":"name","s":"input[name=name]","t":"native-input","r":1,"x":[{"ml":2,"xl":60}]},
    {"k":"email","s":"input[name=email]","t":"native-input","r":1},
    {"k":"topic","s":"select[name=topic]","t":"native-select","r":1},
    {"k":"order_number","s":"input[name=order_number]","t":"native-input","vi":{"f":"topic","o":"in","v":["Billing"]},"x":[{"p":"^(?:ORD-[0-9]{6})$"}]},
    {"k":"message","s":"textarea[name=message]","t":"native-input","r":1,"x":[{"ml":20,"xl":2000},{"ml":20,"m":"Messages need at least 20 characters."}]},
  ];
  // ---- engine: the same in every skill; only the map above changes ----
  var WAIT = 5000, TICK = 100, D = document;
  function sleep(ms) { return new Promise(function (done) { setTimeout(done, ms); }); }
  function arr(items) { return Array.prototype.slice.call(items || []); }
  function list(value) { return Array.isArray(value) ? value : [value]; }
  function norm(text) { return String(text == null ? '' : text).replace(/\s+/g, ' ').trim().toLowerCase(); }
  function cut(text) { text = String(text).replace(/\s+/g, ' ').trim(); return text.length > 80 ? text.slice(0, 77) + '...' : text; }
  function textOf(node) { return node ? (node.innerText || node.textContent || '').trim() : ''; }
  function isShown(node) { return !!node && node.getClientRects().length > 0 && getComputedStyle(node).visibility !== 'hidden'; }
  function fire(node, type) { node.dispatchEvent(new Event(type, { bubbles: true })); }
  function out(result) { var json = JSON.stringify(result); window.__fillResult = json; return json; }
  function all(root, selector) { var nodes = arr(root.querySelectorAll(selector)), shown = nodes.filter(isShown); return shown.length ? shown : nodes; }
  function one(root, selector) { return arr(root.querySelectorAll(selector)).filter(isShown)[0] || null; }
  function wrongHost() { return SKILL.host && location.hostname !== SKILL.host; }
  function isOn(value) { return value === true || ['yes', 'true', 'on', '1', 'checked'].indexOf(norm(value)) >= 0; }
  function isSelected(node) { return node.getAttribute('aria-selected') === 'true'; }
  async function until(probe, ms) { for (var end = Date.now() + (ms || WAIT), value = probe(); !value && Date.now() < end; value = probe()) { await sleep(TICK); } return value; }
  function labelOf(node) { return textOf(node.labels && node.labels[0]) || textOf(node.closest('label')) || node.getAttribute('aria-label') || node.value || ''; }
  function ownText(item) { return arr(item.childNodes).filter(function (child) { return !(child.getAttribute && child.getAttribute('role') === 'group'); }).map(function (child) { return child.textContent; }).join('').trim(); }
  function optionText(option) { return [textOf(option), option.getAttribute('data-value') || option.value || '']; }
  function inputText(input) { return [labelOf(input), input.value]; }
  // Exact match first, then a unique partial match; several partial matches are ambiguous.
  function match(candidates, wanted, read) {
    var want = norm(wanted), exact = [], partial = [], has = function (name) { return name && name.indexOf(want) >= 0; };
    candidates.forEach(function (node) { var names = read(node).map(norm); (names.indexOf(want) >= 0 ? exact : names.some(has) ? partial : []).push(node); });
    if (exact.length || partial.length === 1) { return { node: exact[0] || partial[0] }; }
    return { many: partial.length > 1, choices: (partial.length ? partial : candidates).slice(0, 12).map(function (node) { return cut(read(node)[0]); }) };
  }
  // Waits until every wanted value matches; returns {nodes} or the first failed match.
  async function choose(candidates, value, read) {
    for (var nodes = [], index = 0, wanted = list(value); index < wanted.length; index++) {
      var hit = await until(function () { var found = match(candidates(), wanted[index], read); return found.node ? found : null; }) || match(candidates(), wanted[index], read);
      if (!hit.node) { return hit; } nodes.push(hit.node);
    }
    return { nodes: nodes };
  }
  function setValue(node, value) {
    var proto = { TEXTAREA: HTMLTextAreaElement, SELECT: HTMLSelectElement }[node.tagName] || HTMLInputElement;
    // The prototype setter bypasses the wrappers frameworks install on the element itself.
    if (node.focus) { node.focus(); } Object.getOwnPropertyDescriptor(proto.prototype, 'value').set.call(node, value); fire(node, 'input'); fire(node, 'change');
  }
  function press(node) { ['pointerdown', 'mousedown', 'pointerup', 'mouseup'].forEach(function (type) { node.dispatchEvent(new MouseEvent(type, { bubbles: true })); }); node.click(); }
  var STRATEGY = {
    'native-input': async function (node, value) {
      if (node.type === 'checkbox' || node.type === 'radio') { if (node.checked !== isOn(value)) { node.click(); } return node.checked === isOn(value) ? '' : 'did not change'; }
      setValue(node, String(value)); if (node.blur) { node.blur(); }
      return node.value === String(value) ? '' : 'page did not accept this value';
    },
    'native-select': async function (node, value) {
      var hit = await choose(function () { return node.disabled ? [] : arr(node.options).filter(function (option) { return option.value !== ''; }); }, value, optionText);
      if (!hit.nodes) { return hit; }
      arr(node.options).forEach(function (option) { option.selected = hit.nodes.indexOf(option) >= 0; });
      fire(node, 'input'); fire(node, 'change'); return '';
    },
    'choice': async function (node, value, spec) {
      var inputs = all(D, spec.s), hit = await choose(function () { return inputs; }, value, inputText);
      if (!hit.nodes) { return hit; }
      inputs.forEach(function (input) { var want = hit.nodes.indexOf(input) >= 0; if (input.checked !== want && (want || input.type === 'checkbox')) { input.click(); } });
      return hit.nodes.every(function (input) { return input.checked; }) ? '' : 'did not change';
    },
    'aria-combobox': async function (node, value) {
      setValue(node, String(value));
      var box = D.getElementById(node.getAttribute('aria-controls') || '') || D;
      var hit = await choose(function () { return arr(box.querySelectorAll('[role=option]')).filter(isShown); }, value, optionText);
      if (!hit.nodes) { return hit.choices.length ? hit : 'no options appeared for this text'; }
      press(hit.nodes[0]); await sleep(TICK); return '';
    },
    'aria-tree': async function (node, value) {
      var path = Array.isArray(value) ? value : String(value).split(/\s*[/>›]\s*/), container = node, item = null;
      var children = function () { return arr(container.querySelectorAll('[role=treeitem]')).filter(function (candidate) { return candidate.parentElement.closest('[role=tree],[role=group]') === container; }); };
      for (var depth = 0; depth < path.length; depth++) {
        var hit = await choose(children, path[depth], function (candidate) { return [ownText(candidate)]; }), isLast = depth === path.length - 1;
        if (!hit.nodes) { return hit; }
        item = hit.nodes[0];
        // Clicking an open branch or a selected leaf again would close or clear it.
        if (item.getAttribute(isLast ? 'aria-selected' : 'aria-expanded') !== 'true') { press(item.firstElementChild || item); }
        if (!isLast) { container = await until(function () { return item.querySelector('[role=group]'); }) || item; }
      }
      return item && isSelected(item) ? '' : item && item.hasAttribute('aria-expanded') ? 'this is a branch; give the full path to an item' : 'item was not selected';
    },
    'aria-listbox': async function (node, value) {
      var options = all(node, '[role=option]'), hit = await choose(function () { return options; }, value, optionText);
      if (!hit.nodes) { return hit; }
      options.forEach(function (option) { if (isSelected(option) !== (hit.nodes.indexOf(option) >= 0)) { press(option); } });
      return '';
    },
    'rich-text': async function (node, value) {
      node.focus(); D.execCommand('selectAll', false);
      if (!D.execCommand('insertText', false, String(value)) || norm(textOf(node)) !== norm(value)) { node.textContent = String(value); fire(node, 'input'); }
      return norm(textOf(node)) === norm(value) ? '' : 'editor did not accept the text';
    }
  };
  // What the page holds for a field now, as "text\nvalue" strings.
  function current(spec) {
    var node = one(D, spec.s) || D.querySelector(spec.s), pair = function (text, value) { return text + '\n' + value; };
    if (!node) { return []; }
    if (spec.t === 'choice') { return all(D, spec.s).filter(function (input) { return input.checked; }).map(function (input) { return pair(labelOf(input), input.value); }); }
    if (node.tagName === 'SELECT') { return arr(node.selectedOptions).filter(function (option) { return option.value; }).map(function (option) { return pair(option.text, option.value); }); }
    if (node.type === 'checkbox') { return node.checked ? ['yes'] : []; }
    if (spec.t === 'aria-tree' || spec.t === 'aria-listbox') { return all(node, '[aria-selected=true]').map(textOf); }
    var text = node.isContentEditable ? textOf(node) : node.value; return text ? [text] : [];
  }
  function holds(condition, values) {
    var spec = FIELDS.filter(function (field) { return field.k === condition.f; })[0];
    var given = condition.f in values ? list(values[condition.f]).map(function (value) { return value === true ? 'yes' : String(value); }) : spec ? current(spec) : [];
    var seen = given.join('\n').split('\n').map(norm).filter(function (text) { return text && text !== 'no' && text !== 'false'; });
    if (condition.o === 'checked' || condition.o === 'filled') { return seen.length > 0; }
    var hit = condition.v.some(function (wanted) { return seen.indexOf(norm(wanted)) >= 0; });
    return condition.o === 'in' ? hit : !hit;
  }
  // Compiled rules: p pattern, ml/xl min/max length, mn/mx min/max (number or ISO date), nf not in the future, m message.
  function check(spec, value) {
    var text = String(value), compare = function (limit) { return typeof limit === 'number' ? Number(text) - limit : text < limit ? -1 : text > limit ? 1 : 0; };
    for (var rule of Array.isArray(value) ? [] : list(spec.x || [])) {
      var problem = rule.p && !new RegExp(rule.p).test(text) ? 'must match ' + rule.p : rule.ml != null && text.length < rule.ml ? 'at least ' + rule.ml + ' characters'
        : rule.xl != null && text.length > rule.xl ? 'at most ' + rule.xl + ' characters' : rule.mn != null && compare(rule.mn) < 0 ? 'at least ' + rule.mn
          : rule.mx != null && compare(rule.mx) > 0 ? 'at most ' + rule.mx : rule.nf && text > new Date().toISOString().slice(0, 10) ? 'cannot be in the future' : '';
      if (problem) { return rule.m || problem; }
    }
    return '';
  }
  function errors() {
    var found = {}, alerts = arr(D.querySelectorAll('[role=alert]')).filter(isShown).map(textOf).filter(Boolean);
    FIELDS.forEach(function (spec) {
      var node = D.querySelector(spec.s);
      if (!node || node.getAttribute('aria-invalid') !== 'true') { return; }
      var ids = (node.getAttribute('aria-errormessage') || node.getAttribute('aria-describedby') || '').split(/\s+/);
      found[spec.k] = cut(ids.map(function (id) { return textOf(D.getElementById(id)); }).filter(Boolean).pop() || 'invalid');
    });
    if (alerts.length) { found._page = cut(alerts.join(' ')); }
    return found;
  }
  async function fillOne(spec, value, root, result, key) {
    if (spec.t === 'file' || spec.t === 'steps') { result.manual.push(key); return; }
    var problem = check(spec, value), node = problem ? null : await until(function () { return one(root, spec.s); }, spec.vi || spec.g ? WAIT : 1500);
    if (problem || !node) { if (problem) { result.invalid[key] = cut(problem); } else { (spec.vi ? result.hidden : result.stale).push(key); } return; }
    var outcome = await STRATEGY[spec.t](node, value, spec);
    if (!outcome) { result.filled.push(key); } else if (typeof outcome === 'string') { result.invalid[key] = outcome; }
    else if (outcome.many) { result.ambiguous[key] = outcome.choices; } else { result.invalid[key] = 'not an option; choices: ' + outcome.choices.join(' | '); }
    await sleep(60);
  }
  async function fillGroup(group, rows, result) {
    var found = function () { return all(D, group.row); };
    while (found().length < rows.length) {
      var before = found().length, add = one(D, group.add);
      if (!add) { result.stale.push(group.id); return; } press(add);
      if (!await until(function () { return found().length > before; })) { result.invalid[group.id] = 'could not add a row'; return; }
    }
    for (var index = 0; index < rows.length; index++) {
      for (var spec of FIELDS.filter(function (field) { return field.g === group.id; })) {
        var name = spec.k.split('[].')[1], value = (rows[index] || {})[name];
        if (value != null && value !== '') { await fillOne(spec, value, found()[index], result, group.id + '[' + index + '].' + name); }
      }
    }
  }
  function findMissing(values, result) {
    var isRowFilled = function (row) { return arr(row.querySelectorAll('input,textarea,select')).some(function (input) { return input.value; }); };
    FIELDS.forEach(function (spec) {
      var isNeeded = !spec.g && (spec.r || (spec.ri && holds(spec.ri, values))) && (!spec.vi || holds(spec.vi, values));
      var isSettled = result.filled.indexOf(spec.k) >= 0 || result.manual.indexOf(spec.k) >= 0 || spec.k in result.invalid || spec.k in result.ambiguous || current(spec).length > 0;
      if (isNeeded && !isSettled) { (spec.t === 'file' || spec.t === 'steps' ? result.manual : result.missing).push(spec.k); }
    });
    GROUPS.forEach(function (group) { if (group.min && all(D, group.row).filter(isRowFilled).length < group.min) { result.missing.push(group.id); } });
  }
  window.__fill = async function (values) {
    values = values || {};
    if (wrongHost()) { return out({ error: 'wrong-host', expected: SKILL.host, actual: location.hostname }); }
    var result = { filled: [], missing: [], invalid: {}, ambiguous: {}, hidden: [], manual: [], stale: [] };
    var known = FIELDS.map(function (spec) { return spec.k; }).concat(GROUPS.map(function (group) { return group.id; }));
    result.unknown = Object.keys(values).filter(function (key) { return known.indexOf(key) < 0; });
    for (var spec of FIELDS) {
      var value = values[spec.k];
      if (!spec.g && value != null && value !== '' && !(Array.isArray(value) && !value.length)) { await fillOne(spec, value, D, result, spec.k); }
    }
    for (var group of GROUPS) { if (Array.isArray(values[group.id])) { await fillGroup(group, values[group.id], result); } }
    findMissing(values, result); result.errors = errors();
    Object.keys(result).forEach(function (key) { if (!Object.keys(result[key]).length) { delete result[key]; } });
    return out(result);
  };
  window.__submit = async function () {
    var capture = { status: 0, body: '' }, realFetch = window.fetch, XHR = XMLHttpRequest.prototype, realSend = XHR.send, realOpen = XHR.open;
    function record(status, body) { capture.status = status; capture.body = String(body || ''); }
    function succeeded() { return (SUBMIT.url && location.href.indexOf(SUBMIT.url) >= 0) || (SUBMIT.text && textOf(D.body).indexOf(SUBMIT.text) >= 0); }
    window.fetch = function (input, init) {
      var reply = realFetch.apply(this, arguments), method = ((init && init.method) || (input && input.method) || 'GET').toUpperCase();
      if (method !== 'GET') { reply.then(function (response) { return response.clone().text().then(function (body) { record(response.status, body); }); }, function () {}); }
      return reply;
    };
    XHR.open = function (method) { this.__method = String(method).toUpperCase(); return realOpen.apply(this, arguments); };
    XHR.send = function () { var request = this; if (request.__method !== 'GET') { request.addEventListener('loadend', function () { record(request.status, request.responseText); }); } return realSend.apply(this, arguments); };
    try {
      var button = one(D, SUBMIT.s), started = Date.now();
      if (wrongHost() || !button) { return out({ ok: false, error: wrongHost() ? 'wrong-host' : 'submit control not found' }); }
      if (button.disabled) { return out({ ok: false, error: 'submit is disabled', errors: errors() }); }
      press(button); await until(function () { return succeeded() || capture.status >= 400 || (!capture.status && Date.now() - started > 1500 && Object.keys(errors()).length); }, 15000);
      await sleep(200);
      var result = { ok: !!succeeded(), url: location.pathname, status: capture.status || undefined };
      if (!result.ok) { result.errors = errors(); result.message = capture.status >= 400 ? cut(capture.body) : undefined; }
      return out(result);
    } finally { window.fetch = realFetch; XHR.send = realSend; XHR.open = realOpen; }
  };
}());
