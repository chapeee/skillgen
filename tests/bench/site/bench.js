/*
 * Bench page behaviour. It works like a framework app on purpose: values live in a
 * state object updated only by input/change/click events, never read from the DOM at
 * submit time. A fill that sets .value without firing events will not be saved.
 */
(function () {
  'use strict';

  var state = {
    full_name: '', email: '', username: '', birth_date: '', bio: '',
    account_type: '', company_name: '', registration_no: '', team_size: '',
    country: '', region: '', city: '',
    interests: [], department: '', skills: [], newsletter: false,
    statement: '', references: [], id_document: '', agree_terms: false
  };

  var DEPARTMENTS = [
    { label: 'Engineering', children: [
      { label: 'Platform', children: [{ label: 'Reliability' }, { label: 'Tooling' }] },
      { label: 'Product', children: [{ label: 'Web' }, { label: 'Mobile' }] }
    ] },
    { label: 'Operations', children: [{ label: 'Finance' }, { label: 'People' }] },
    { label: 'Research' }
  ];

  function $(selector) { return document.querySelector(selector); }
  function on(node, type, handler) { node.addEventListener(type, handler); }

  function bindText(key) {
    var input = document.getElementById(key);
    on(input, 'input', function () { state[key] = input.value; clearError(key); });
  }

  ['full_name', 'email', 'username', 'birth_date', 'bio', 'company_name', 'registration_no']
    .forEach(bindText);

  on($('#team_size'), 'change', function (event) { state.team_size = event.target.value; });

  document.querySelectorAll('input[name=account_type]').forEach(function (radio) {
    on(radio, 'change', function () {
      state.account_type = radio.value;
      $('#company-fields').hidden = radio.value !== 'Company';
      clearError('account_type');
    });
  });

  // Country → region: options load from the server after the country changes.
  on($('#country'), 'change', function (event) {
    state.country = event.target.value;
    state.region = '';
    var region = $('#region');
    region.disabled = true;
    region.innerHTML = '<option value="">Loading…</option>';
    if (!state.country) { return; }
    fetch('/api/regions?country=' + encodeURIComponent(state.country))
      .then(function (response) { return response.json(); })
      .then(function (regions) {
        region.innerHTML = '<option value="">Choose…</option>' + regions.map(function (name) {
          return '<option value="' + name + '">' + name + '</option>';
        }).join('');
        region.disabled = false;
      });
  });
  on($('#region'), 'change', function (event) { state.region = event.target.value; clearError('region'); });

  document.querySelectorAll('input[name=interests]').forEach(function (box) {
    on(box, 'change', function () {
      state.interests = Array.prototype.filter.call(
        document.querySelectorAll('input[name=interests]'),
        function (other) { return other.checked; }
      ).map(function (other) { return other.value; });
    });
  });

  setupCombobox();
  setupTree();
  setupChips();

  on($('#newsletter'), 'change', function (event) { state.newsletter = event.target.checked; });
  on($('#statement'), 'input', function (event) {
    state.statement = event.target.innerText.trim();
    clearError('statement');
  });
  on($('#id_document'), 'change', function (event) {
    var file = event.target.files[0];
    state.id_document = file ? file.name : '';
  });
  on($('#agree_terms'), 'change', function (event) {
    state.agree_terms = event.target.checked;
    // The submit button stays disabled until the declaration is ticked.
    $('#submit').disabled = !state.agree_terms;
  });

  setupReferences();
  on($('#application'), 'submit', submitForm);
  on($('#again'), 'click', function (event) {
    event.preventDefault();
    window.location.href = '/apply';
  });
  if (window.location.pathname === '/apply/done') { window.location.replace('/apply'); }

  function setupCombobox() {
    var input = $('#city');
    var list = $('#city-options');
    var timer = null;
    on(input, 'input', function () {
      state.city = '';
      clearTimeout(timer);
      timer = setTimeout(function () {
        if (!input.value.trim()) { list.hidden = true; return; }
        fetch('/api/cities?q=' + encodeURIComponent(input.value))
          .then(function (response) { return response.json(); })
          .then(function (cities) { showCities(cities); });
      }, 150);
    });
    function showCities(cities) {
      list.innerHTML = '';
      cities.forEach(function (city, index) {
        var item = document.createElement('li');
        item.setAttribute('role', 'option');
        item.id = 'city-option-' + index;
        item.textContent = city;
        on(item, 'mousedown', function (event) { event.preventDefault(); });
        on(item, 'click', function () {
          state.city = city;
          input.value = city;
          list.hidden = true;
          input.setAttribute('aria-expanded', 'false');
          clearError('city');
        });
        list.appendChild(item);
      });
      list.hidden = cities.length === 0;
      input.setAttribute('aria-expanded', String(cities.length > 0));
    }
  }

  function setupTree() {
    var tree = $('#department');
    DEPARTMENTS.forEach(function (node) { tree.appendChild(makeTreeItem(node, [])); });
  }

  function makeTreeItem(node, parents) {
    var path = parents.concat([node.label]);
    var item = document.createElement('li');
    item.setAttribute('role', 'treeitem');
    item.setAttribute('aria-selected', 'false');
    var label = document.createElement('span');
    label.className = 'tree-label';
    label.textContent = node.label;
    item.appendChild(label);
    if (node.children) {
      item.setAttribute('aria-expanded', 'false');
      on(label, 'click', function () {
        var isOpen = item.getAttribute('aria-expanded') === 'true';
        item.setAttribute('aria-expanded', String(!isOpen));
        var group = item.querySelector('[role=group]');
        // Children are rendered only when first opened, like lazy tree widgets.
        if (!group) {
          group = document.createElement('ul');
          group.setAttribute('role', 'group');
          node.children.forEach(function (child) { group.appendChild(makeTreeItem(child, path)); });
          item.appendChild(group);
        }
        group.hidden = isOpen;
      });
    } else {
      on(label, 'click', function () {
        document.querySelectorAll('#department [aria-selected=true]').forEach(function (other) {
          other.setAttribute('aria-selected', 'false');
        });
        item.setAttribute('aria-selected', 'true');
        state.department = path.join(' / ');
        clearError('department');
      });
    }
    return item;
  }

  function setupChips() {
    document.querySelectorAll('#skills [role=option]').forEach(function (chip) {
      on(chip, 'click', function () {
        var isSelected = chip.getAttribute('aria-selected') === 'true';
        chip.setAttribute('aria-selected', String(!isSelected));
        state.skills = Array.prototype.map.call(
          document.querySelectorAll('#skills [aria-selected=true]'),
          function (selected) { return selected.textContent; }
        );
      });
    });
  }

  function setupReferences() {
    on($('#add-reference'), 'click', addReference);
    addReference();
  }

  function addReference() {
    var index = state.references.length;
    state.references.push({ name: '', email: '' });
    var row = document.createElement('div');
    row.className = 'reference-row';
    row.innerHTML =
      '<div class="field"><label>Reference name <input type="text" name="references[' + index +
      '][name]" data-field="name"></label></div>' +
      '<div class="field"><label>Reference email <input type="email" name="references[' + index +
      '][email]" data-field="email"></label></div>';
    row.querySelectorAll('input').forEach(function (input) {
      on(input, 'input', function () {
        state.references[index][input.getAttribute('data-field')] = input.value;
      });
    });
    $('#references').appendChild(row);
  }

  function setError(key, message) {
    var target = document.getElementById(key);
    if (target) { target.setAttribute('aria-invalid', 'true'); }
    var error = document.getElementById('err-' + key);
    if (error) { error.textContent = message; }
  }

  function clearError(key) {
    var target = document.getElementById(key);
    if (target) { target.removeAttribute('aria-invalid'); }
    var error = document.getElementById('err-' + key);
    if (error) { error.textContent = ''; }
  }

  function validate() {
    var errors = {};
    var required = ['full_name', 'email', 'username', 'birth_date', 'account_type', 'country',
      'region', 'city', 'department', 'statement'];
    if (state.account_type === 'Company') { required.push('company_name', 'registration_no'); }
    required.forEach(function (key) { if (!state[key]) { errors[key] = 'This field is required.'; } });
    if (state.full_name && state.full_name.length < 3) { errors.full_name = 'Use at least 3 characters.'; }
    if (state.email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(state.email)) { errors.email = 'Enter a valid email address.'; }
    if (state.username && !/^[a-z0-9_]{3,20}$/.test(state.username)) {
      errors.username = 'Use 3–20 lowercase letters, digits or underscores.';
    }
    if (state.birth_date && state.birth_date > new Date().toISOString().slice(0, 10)) {
      errors.birth_date = 'Date of birth cannot be in the future.';
    }
    if (state.registration_no && !/^[A-Z]{2}[0-9]{6}$/.test(state.registration_no)) {
      errors.registration_no = 'Use two capital letters then six digits.';
    }
    var references = state.references.filter(function (row) { return row.name || row.email; });
    if (references.length === 0) { errors.references = 'Add at least one reference.'; }
    return errors;
  }

  function submitForm(event) {
    event.preventDefault();
    var alert = $('#form-alert');
    alert.hidden = true;
    var errors = validate();
    if (Object.keys(errors).length) {
      Object.keys(errors).forEach(function (key) { setError(key, errors[key]); });
      alert.textContent = 'Please fix the highlighted fields.';
      alert.hidden = false;
      return;
    }
    var payload = JSON.parse(JSON.stringify(state));
    payload.references = state.references.filter(function (row) { return row.name || row.email; });
    fetch('/api/applications', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(function (response) {
      return response.json().then(function (body) { return { status: response.status, body: body }; });
    }).then(function (result) {
      if (result.status === 201) { showDone(result.body.id, payload); return; }
      var serverErrors = result.body.errors || {};
      Object.keys(serverErrors).forEach(function (key) { setError(key, serverErrors[key]); });
      alert.textContent = result.body.message || 'The server rejected the application.';
      alert.hidden = false;
    });
  }

  function showDone(id, payload) {
    window.history.pushState({}, '', '/apply/done');
    $('#form-view').hidden = true;
    $('#done-view').hidden = false;
    $('#done-id').textContent = id;
    $('#done-payload').textContent = JSON.stringify(payload, null, 2);
  }
}());
