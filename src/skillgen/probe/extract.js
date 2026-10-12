// Runs in the page during probing. Lists every editable control with its accessible
// name, constraints, options, section, visibility, a unique selector and where it sat
// on load. ES2019.
() => {
  var D = document;
  var CLICKABLE = 'button,[role=button],a[href],summary,[role=tab],[role=menuitem],'
    + 'input[type=button],input[type=reset],input[type=submit]';
  var CHROME = 'nav,header,footer,aside,[role=navigation],[role=banner],'
    + '[role=contentinfo],[role=menu],[role=menubar]';
  // A page's chrome can hold dozens of links; a form's own controls are far fewer, and
  // a reader only needs enough to find what opens the next part.
  var MAX_CLICKABLES = 60;
  function arr(items) { return Array.prototype.slice.call(items || []); }
  function text(node) { return node ? (node.innerText || node.textContent || '').replace(/\s+/g, ' ').trim() : ''; }
  function shown(node) { return !!node && node.getClientRects().length > 0 && getComputedStyle(node).visibility !== 'hidden'; }
  function esc(value) { return window.CSS && CSS.escape ? CSS.escape(value) : value.replace(/[^\w-]/g, '\\$&'); }
  function count(selector) { try { return D.querySelectorAll(selector).length; } catch (error) { return 0; } }
  function byIds(ids) { return (ids || '').split(/\s+/).map(function (id) { return text(D.getElementById(id)); }).filter(Boolean).join(' '); }
  function labelOf(node) {
    if (node.getAttribute('aria-labelledby')) { return byIds(node.getAttribute('aria-labelledby')); }
    if (node.getAttribute('aria-label')) { return node.getAttribute('aria-label').trim(); }
    if (node.labels && node.labels.length) { return text(node.labels[0]); }
    var wrap = node.closest('label');
    return wrap ? text(wrap) : node.getAttribute('placeholder') || node.name || node.id || '';
  }
  function selectorFor(node, group) {
    var tag = node.tagName.toLowerCase(), testid = node.getAttribute('data-testid'), candidates = [];
    if (testid) { candidates.push('[data-testid="' + testid + '"]'); }
    if (node.id) { candidates.push('#' + esc(node.id)); }
    if (node.name) { candidates.push(tag + '[name="' + node.name + '"]'); }
    if (node.getAttribute('aria-label')) { candidates.push(tag + '[aria-label="' + node.getAttribute('aria-label') + '"]'); }
    for (var index = 0; index < candidates.length; index++) {
      var found = count(candidates[index]);
      if (group ? found === group : found === 1) { return { selector: candidates[index], count: found }; }
    }
    return { selector: candidates[0] || tag, count: candidates[0] ? count(candidates[0]) : 0 };
  }
  function sectionOf(node) {
    var box = node.closest('fieldset,[role=group],[role=region],section,[role=tabpanel]');
    while (box) {
      var legend = box.tagName === 'FIELDSET' ? box.querySelector('legend') : null;
      var name = legend ? text(legend) : box.getAttribute('aria-label') || byIds(box.getAttribute('aria-labelledby'));
      if (name && !(box.tagName === 'FIELDSET' && box.querySelectorAll('input[type=radio],input[type=checkbox]').length === box.querySelectorAll('input,select,textarea').length)) { return name; }
      box = box.parentElement && box.parentElement.closest('fieldset,[role=group],[role=region],section,[role=tabpanel]');
    }
    return '';
  }
  function limits(node) {
    var out = {}, read = function (name) { return node.getAttribute(name); };
    if (read('minlength')) { out.min_length = Number(read('minlength')); }
    if (read('maxlength') && Number(read('maxlength')) > 0) { out.max_length = Number(read('maxlength')); }
    if (read('min')) { out.minimum = read('min'); }
    if (read('max')) { out.maximum = read('max'); }
    if (read('pattern')) { out.pattern = read('pattern'); }
    if (read('accept')) { out.accept = read('accept'); }
    return out;
  }
  var controls = [], seenGroups = {};
  function add(node, info) {
    var hit = selectorFor(node, info.group);
    controls.push(Object.assign({
      tag: node.tagName.toLowerCase(), name: node.name || node.getAttribute('name') || '', id: node.id || '',
      label: labelOf(node), required: node.required || node.getAttribute('aria-required') === 'true',
      limits: limits(node), section: sectionOf(node), visible: shown(node), selector: hit.selector,
      selector_count: hit.count, options: [], repeated: /\[\d+\]|\.\d+\.|_\d+_/.test(node.name || '')
    }, info));
  }
  arr(D.querySelectorAll('input,select,textarea,[contenteditable=true],[role=combobox],[role=tree],[role=listbox]')).forEach(function (node) {
    var type = (node.getAttribute('type') || '').toLowerCase(), role = node.getAttribute('role');
    if (['hidden', 'submit', 'button', 'reset', 'image', 'password', 'search'].indexOf(type) >= 0 || node.closest('[aria-hidden=true]')) { return; }
    if (role === 'listbox' && D.querySelector('[aria-controls="' + node.id + '"]')) { return; }
    if (node.tagName !== 'SELECT' && node.closest('[role=listbox],[role=tree]') && node.closest('[role=listbox],[role=tree]') !== node) { return; }
    if ((type === 'radio' || type === 'checkbox') && node.name) {
      var peers = arr(D.querySelectorAll('input[name="' + node.name + '"]'));
      if (peers.length > 1 || type === 'radio') {
        if (seenGroups[node.name]) { return; }
        seenGroups[node.name] = true;
        var box = node.closest('fieldset,[role=radiogroup],[role=group]');
        var groupLabel = box ? (box.tagName === 'FIELDSET' && box.querySelector('legend') ? text(box.querySelector('legend')) : byIds(box.getAttribute('aria-labelledby')) || box.getAttribute('aria-label')) : '';
        add(node, { kind: 'choice', type: type, group: peers.length, options: peers.map(function (peer) { return labelOf(peer); }) });
        controls[controls.length - 1].label = groupLabel || node.name;
        controls[controls.length - 1].selector = 'input[name="' + node.name + '"]';
        controls[controls.length - 1].visible = peers.some(shown);
        controls[controls.length - 1].required = peers.some(function (peer) { return peer.required; });
        return;
      }
    }
    if (node.tagName === 'SELECT') { add(node, { kind: 'select', type: node.multiple ? 'multiple' : 'single', options: arr(node.options).filter(function (o) { return o.value !== ''; }).map(function (o) { return o.text.trim(); }) }); return; }
    if (role === 'combobox') { add(node, { kind: 'combobox', type: type || 'text' }); return; }
    if (role === 'tree') { add(node, { kind: 'tree', type: 'tree', options: arr(node.querySelectorAll(':scope > [role=treeitem]')).map(function (item) { return text(item.firstElementChild || item); }) }); return; }
    if (role === 'listbox') { add(node, { kind: 'listbox', type: node.getAttribute('aria-multiselectable') === 'true' ? 'multiple' : 'single', options: arr(node.querySelectorAll('[role=option]')).map(text) }); return; }
    if (node.isContentEditable && node.tagName !== 'INPUT' && node.tagName !== 'TEXTAREA') { add(node, { kind: 'rich-text', type: 'rich-text' }); return; }
    add(node, { kind: type === 'file' ? 'file' : type === 'checkbox' ? 'checkbox' : 'input', type: node.tagName === 'TEXTAREA' ? 'textarea' : type || 'text' });
  });
  // Measured from each control's final selector, the way a skill reads it back later,
  // so the two never disagree about which element a box belongs to. Document
  // coordinates make a box independent of the scroll position.
  function boxFor(selector) {
    var node;
    try { node = D.querySelector(selector); } catch (error) { return null; }
    if (!node || !shown(node)) { return null; }
    var rect = node.getBoundingClientRect();
    if (!rect.width && !rect.height) { return null; }
    return [Math.round(rect.left + window.scrollX), Math.round(rect.top + window.scrollY),
      Math.round(rect.width), Math.round(rect.height)];
  }
  // A selector that names several elements would measure only the first, so such a
  // control gets no box rather than another element's.
  controls.forEach(function (control) {
    control.box = control.kind === 'choice' || control.selector_count === 1
      ? boxFor(control.selector) : null;
  });
  // Everything a person can click, named by what it says. A reader uses this to work
  // out what opens a part of the form that is not on screen yet, so a control that
  // would save, submit or leave the page is marked rather than left to be guessed at.
  var RISKY = /\b(submit|save|delete|remove|discard|reset|clear|start over|sign out|log out|logout|pay|order|confirm|publish|send|cancel|close account)\b/i;
  function leavesPage(href) {
    if (!href || href.charAt(0) === '#' || href.indexOf('javascript:') === 0) { return false; }
    try {
      var target = new URL(href, location.href);
      return target.origin !== location.origin || target.pathname !== location.pathname;
    } catch (error) {
      // No base to resolve against (a page built in memory, a srcdoc frame): a path or
      // a scheme still names somewhere other than here.
      return href.charAt(0) === '/' || href.indexOf('//') >= 0;
    }
  }
  var clickables = [];
  arr(D.querySelectorAll(CLICKABLE)).forEach(function (node) {
    if (clickables.length >= MAX_CLICKABLES || node.closest('[aria-hidden=true]')) { return; }
    var label = (text(node) || node.getAttribute('aria-label') || node.value || '').slice(0, 80);
    if (!label) { return; }
    var hit = selectorFor(node, 0);
    var href = node.getAttribute('href') || '';
    clickables.push({
      label: label,
      role: node.getAttribute('role') || node.tagName.toLowerCase(),
      // What to pass as an open step: a selector when it names this one element,
      // else the label, which is the other form a step may take.
      step: hit.count === 1 ? hit.selector : 'text:' + label,
      selector_count: hit.count,
      visible: shown(node),
      disabled: !!node.disabled || node.getAttribute('aria-disabled') === 'true',
      collapsed: node.getAttribute('aria-expanded') === 'false' || node.tagName === 'SUMMARY',
      opens: node.getAttribute('aria-controls') || '',
      // The page's own menus and headings hold most of the clickable things on a page
      // and open none of its form, so they are named rather than tried.
      chrome: !!node.closest(CHROME),
      // A link to another page cannot open part of this form; following one collects
      // another page's fields as if they belonged here.
      leaves: leavesPage(href),
      risky: RISKY.test(label)
    });
  });
  var submit = arr(D.querySelectorAll('button[type=submit],input[type=submit],form button:not([type])')).filter(shown)[0];
  var heading = D.querySelector('h1');
  return {
    title: text(heading) || D.title,
    controls: controls,
    clickables: clickables,
    viewport: [window.innerWidth, window.innerHeight],
    submit: submit ? { selector: selectorFor(submit, 0).selector, label: text(submit) || submit.value || '' } : null
  };
}
