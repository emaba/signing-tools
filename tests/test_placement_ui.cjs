// Exercise UI events and submitted coordinates without a browser or credentials.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

async function fixture(warnings = []) {
  const elements = new Map(), posts = [];
  const document = {activeElement: null};
  class Element {
    constructor(id) {
      this.id = id; this.value = ''; this.style = {}; this.dataset = {};
      this.hidden = false; this.disabled = false; this.events = new Map();
      this.children = [];
      this.clientWidth = 900; this.clientHeight = 1000;
      this.classList = {toggle() {}};
    }
    addEventListener(name, action) { this.events.set(name, action); }
    async emit(name, event = {}) {
      return this.events.get(name)?.({...event, preventDefault() {}});
    }
    focus() { document.activeElement = this; }
    prepend() {}
    replaceWith() {}
    replaceChildren(...children) { this.children = children; }
    append(...children) { this.children.push(...children); }
    setCustomValidity(message) { this.validationMessage = message; }
    reportValidity() {}
  }
  document.getElementById = id => {
    if (!elements.has(id)) elements.set(id, new Element(id));
    return elements.get(id);
  };
  document.createElement = tag => new Element(tag);
  const get = document.getElementById;
  get('zoom').value = 'fit';
  class Image extends Element {
    constructor() { super('image'); }
    set src(value) { this.url = value; queueMicrotask(() => this.onload()); }
  }
  const fetch = async (url, options) => {
    if (options) posts.push({url, body: JSON.parse(options.body)});
    return {ok: true, json: async () => ({title: 'Synthetic test.pdf', initial_page: 3,
      pages: Array.from({length: 3}, () => ({width_mm: 210, height_mm: 297})), style: 'split', warnings})};
  };
  const source = fs.readFileSync(path.join(__dirname, '../src/signing_tools/assets/placement/app.js'), 'utf8');
  vm.runInNewContext(source, {document, window: {addEventListener() {}}, Image, fetch});
  await new Promise(resolve => setImmediate(resolve));
  return {get, posts};
}

function enter(get, values) {
  ['left', 'top', 'width', 'height'].forEach((key, i) => { get(key).value = String(values[i]); });
}

function assertSelection(payload) {
  assert.equal(payload.page, 3);
  const expected = [85 / 210, 245 / 297, 110 / 210, 27 / 297];
  payload.rect.forEach((value, i) => assert.ok(Math.abs(value - expected[i]) < 1e-9));
}

test('numeric input immediately moves the box and submits the selected third page', async () => {
  const {get, posts} = await fixture();
  await get('addBox').emit('click');
  enter(get, [85, 245, 110, 27]);
  await get('top').emit('input');
  assert.ok(Math.abs(parseFloat(get('selection').style.top) - 245 / 297 * 100) < 1e-9);
  await get('confirm').emit('click');
  assert.equal(posts.length, 1);
  assertSelection(posts[0].body);
});

test('confirmation reads displayed values even when autofill emits no change event', async () => {
  const {get, posts} = await fixture();
  await get('addBox').emit('click');
  enter(get, [85, 245, 110, 27]);
  await get('confirm').emit('click');
  assert.equal(posts.length, 1);
  assertSelection(posts[0].body);
});

test('invalid numeric measurements cannot submit an older valid rectangle', async () => {
  const {get, posts} = await fixture();
  await get('addBox').emit('click');
  enter(get, [200, 245, 110, 27]);
  await get('left').emit('input');
  assert.equal(get('confirm').disabled, true);
  await get('confirm').emit('click');
  assert.equal(posts.length, 0);
  await get('cancel').emit('click');
  assert.equal(posts[0].url, 'api/cancel');
});

test('changing pages clears the selected box and prevents submitting it on another page', async () => {
  const {get, posts} = await fixture();
  await get('addBox').emit('click');
  await get('previous').emit('click');
  assert.equal(get('pageNumber').value, 2);
  assert.equal(get('selection').hidden, true);
  assert.equal(get('left').value, '');
  assert.equal(get('confirm').disabled, true);
  await get('confirm').emit('click');
  assert.equal(posts.length, 0);
});

test('well-formed documents hide the structural warning', async () => {
  const {get} = await fixture();
  assert.equal(get('structureWarning').hidden, true);
  assert.equal(get('structureWarningReasons').children.length, 0);
});

test('structural warning explains the cause and still permits placement', async () => {
  const message = 'A later PDF revision marks a free xref entry with generation 0.';
  const {get, posts} = await fixture([{reader: 'pyHanko', code: 'free-xref-generation-zero', message}]);
  assert.equal(get('structureWarning').hidden, false);
  assert.equal(get('structureWarningReasons').children[0].textContent, `pyHanko: ${message}`);
  await get('addBox').emit('click');
  enter(get, [85, 245, 110, 27]);
  await get('confirm').emit('click');
  assert.equal(posts.length, 1);
  assertSelection(posts[0].body);
});

test('warning text is rendered literally rather than inserted as HTML', async () => {
  const message = '<img src=x onerror=syntheticTest()> diagnostic';
  const {get} = await fixture([{reader: 'Test reader', message}]);
  const item = get('structureWarningReasons').children[0];
  assert.equal(item.textContent, `Test reader: ${message}`);
  assert.equal(item.innerHTML, undefined);
});
