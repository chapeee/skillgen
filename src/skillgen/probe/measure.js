// Runs in the page for `generate --xy`. Measures each of a skill's own selectors, the
// way the skill's layout check reads them back, so the two can never disagree about
// which element a box belongs to. Must measure exactly as boxFor in extract.js does.
// ES2019.
(selectors) => {
  var D = document;
  function shown(node) { return !!node && node.getClientRects().length > 0 && getComputedStyle(node).visibility !== 'hidden'; }
  function boxFor(selector) {
    var node;
    try { node = D.querySelector(selector); } catch (error) { return null; }
    if (!node || !shown(node)) { return null; }
    var rect = node.getBoundingClientRect();
    if (!rect.width && !rect.height) { return null; }
    return [Math.round(rect.left + window.scrollX), Math.round(rect.top + window.scrollY),
      Math.round(rect.width), Math.round(rect.height)];
  }
  var passwords = D.querySelectorAll('input[type=password]');
  return {
    viewport: [window.innerWidth, window.innerHeight],
    boxes: selectors.map(function (selector) { return [selector, boxFor(selector)]; }),
    path: location.pathname,
    password: Array.prototype.some.call(passwords, shown)
  };
}
