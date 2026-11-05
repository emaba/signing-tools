'use strict';
const $ = id => document.getElementById(id);
const stage = $('stage'), viewport = $('viewport'), box = $('selection');
const fields = ['left', 'top', 'width', 'height'];
let info, page = 1, rect = null, gesture = null, loading = true, generation = 0;
let pageImage = null;
const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
const paper = () => info.pages[page - 1];

function showStructureWarnings(warnings) {
  const reasons = $('structureWarningReasons');
  reasons.replaceChildren();
  for (const warning of warnings) {
    const item = document.createElement('li');
    // Diagnostics are text, never HTML or raw parser exception payloads.
    item.textContent = `${warning.reader}: ${warning.message}`;
    reasons.append(item);
  }
  $('structureWarning').hidden = warnings.length === 0;
}

function update() {
  box.hidden = !rect;
  $('confirm').disabled = !rect || loading;
  $('clear').disabled = !rect || loading;
  $('addBox').disabled = loading;
  $('previous').disabled = loading || page <= 1;
  $('next').disabled = loading || page >= info.pages.length;
  $('pageNumber').disabled = loading;
  fields.forEach(id => $(id).disabled = !rect || loading);
  if (!rect) { fields.forEach(id => { $(id).value = ''; }); return; }
  box.style.left = `${rect.x * 100}%`; box.style.top = `${rect.y * 100}%`;
  box.style.width = `${rect.w * 100}%`; box.style.height = `${rect.h * 100}%`;
  const values = [rect.x * paper().width_mm, rect.y * paper().height_mm,
                  rect.w * paper().width_mm, rect.h * paper().height_mm];
  fields.forEach((id, i) => { if (document.activeElement !== $(id)) $(id).value = values[i].toFixed(1); });
}

function fit() {
  if (!info) return;
  const p = paper(), zoom = $('zoom').value;
  const availableWidth = Math.max(100, viewport.clientWidth - 64);
  const availableHeight = Math.max(100, viewport.clientHeight - 64);
  let width;
  if (zoom === 'fit') width = Math.min(availableWidth, availableHeight * p.width_mm / p.height_mm);
  else if (zoom === 'width') width = availableWidth;
  else width = p.width_mm * 96 / 25.4 * Number(zoom);
  stage.style.width = `${width}px`;
}

async function showPage(number) {
  number = Math.trunc(number);
  if (!Number.isFinite(number) || number < 1 || number > info.pages.length) {
    $('pageNumber').value = page; return;
  }
  const ticket = ++generation;
  page = number; rect = null; loading = true;
  $('pageNumber').value = page;
  $('paperSize').textContent = `${paper().width_mm.toFixed(1)} × ${paper().height_mm.toFixed(1)} mm`;
  stage.hidden = true; $('message').hidden = false; $('message').textContent = 'Loading the page…';
  update(); fit();
  try {
    const image = new Image();
    image.alt = `PDF page ${page}`; image.draggable = false;
    await new Promise((resolve, reject) => {
      image.onload = resolve; image.onerror = reject; image.src = `api/pages/${number - 1}.png`;
    });
    if (ticket !== generation) return;
    if (pageImage) pageImage.replaceWith(image); else stage.prepend(image);
    pageImage = image;
    stage.hidden = false; $('message').hidden = true; loading = false;
    viewport.scrollTop = 0; viewport.scrollLeft = 0; update();
  } catch {
    if (ticket !== generation) return;
    $('message').textContent = 'This page could not be displayed. Choose a page to try again.';
    loading = true; $('pageNumber').disabled = false;
  }
}

function defaultBox(x = .5, y = .8) {
  const w = Math.min(110 / paper().width_mm, .9), h = Math.min(27 / paper().height_mm, .9);
  return {x: clamp(x - w / 2, 0, 1 - w), y: clamp(y - h / 2, 0, 1 - h), w, h};
}

function point(event) {
  const bounds = stage.getBoundingClientRect();
  return {x: clamp((event.clientX - bounds.left) / bounds.width, 0, 1),
          y: clamp((event.clientY - bounds.top) / bounds.height, 0, 1)};
}

stage.addEventListener('pointerdown', event => {
  if (loading || event.button !== 0) return;
  event.preventDefault();
  const start = point(event), handle = event.target.closest('[data-handle]');
  const mode = handle ? handle.dataset.handle : rect && box.contains(event.target) ? 'move' : 'draw';
  gesture = {mode, start, original: rect ? {...rect} : null, clientX: event.clientX, clientY: event.clientY};
  if (mode === 'draw') rect = {x: start.x, y: start.y, w: 0, h: 0};
  stage.setPointerCapture(event.pointerId); update();
});

stage.addEventListener('pointermove', event => {
  if (!gesture) return;
  const p = point(event), g = gesture, old = g.original;
  const dx = p.x - g.start.x, dy = p.y - g.start.y;
  if (g.mode === 'draw') {
    rect = {x: Math.min(p.x, g.start.x), y: Math.min(p.y, g.start.y),
            w: Math.abs(dx), h: Math.abs(dy)};
  } else if (g.mode === 'move') {
    rect = {...old, x: clamp(old.x + dx, 0, 1 - old.w), y: clamp(old.y + dy, 0, 1 - old.h)};
  } else {
    let left = old.x, top = old.y, right = old.x + old.w, bottom = old.y + old.h;
    const minW = Math.min(.5 / paper().width_mm, old.w), minH = Math.min(.5 / paper().height_mm, old.h);
    if (g.mode.includes('w')) left = clamp(old.x + dx, 0, right - minW);
    if (g.mode.includes('e')) right = clamp(old.x + old.w + dx, left + minW, 1);
    if (g.mode.includes('n')) top = clamp(old.y + dy, 0, bottom - minH);
    if (g.mode.includes('s')) bottom = clamp(old.y + old.h + dy, top + minH, 1);
    rect = {x: left, y: top, w: right - left, h: bottom - top};
  }
  update();
});

function endGesture(event) {
  if (!gesture) return;
  if (gesture.mode === 'draw' && (Math.hypot(event.clientX - gesture.clientX, event.clientY - gesture.clientY) < 5
      || rect.w < .001 || rect.h < .001)) rect = defaultBox(gesture.start.x, gesture.start.y);
  gesture = null; update(); box.focus({preventScroll: true});
}
stage.addEventListener('pointerup', endGesture);
stage.addEventListener('pointercancel', () => { gesture = null; rect = null; update(); });

box.addEventListener('keydown', event => {
  if (!rect) return;
  const step = event.shiftKey ? 2 : .5;
  const moves = {ArrowLeft: [-step / paper().width_mm, 0], ArrowRight: [step / paper().width_mm, 0],
                 ArrowUp: [0, -step / paper().height_mm], ArrowDown: [0, step / paper().height_mm]};
  if (moves[event.key]) {
    event.preventDefault(); const [dx, dy] = moves[event.key];
    rect.x = clamp(rect.x + dx, 0, 1 - rect.w); rect.y = clamp(rect.y + dy, 0, 1 - rect.h); update();
  } else if (event.key === 'Delete' || event.key === 'Backspace' || event.key === 'Escape') {
    event.preventDefault(); rect = null; update();
  }
});

function readMeasurements(report = false) {
  if (!rect) return false;
  const values = fields.map(key => Number($(key).value));
  const [x, y, w, h] = values, p = paper();
  if (fields.some(key => $(key).value === '') || !values.every(Number.isFinite) || Math.min(x, y) < 0 || Math.min(w, h) <= 0
      || x + w > p.width_mm + .051 || y + h > p.height_mm + .051) {
    if (report) {
      $('left').setCustomValidity('Keep the rectangle inside the page, with positive width and height.');
      $('left').reportValidity(); $('left').setCustomValidity('');
    }
    $('confirm').disabled = true;
    return false;
  }
  rect = {x: x / p.width_mm, y: y / p.height_mm,
          w: Math.min(w, p.width_mm - x) / p.width_mm, h: Math.min(h, p.height_mm - y) / p.height_mm};
  update();
  return true;
}
fields.forEach(id => {
  $(id).addEventListener('input', () => readMeasurements());
  $(id).addEventListener('change', () => readMeasurements(true));
});

$('pageNumber').addEventListener('change', () => showPage(Number($('pageNumber').value)));
$('previous').addEventListener('click', () => showPage(page - 1));
$('next').addEventListener('click', () => showPage(page + 1));
$('zoom').addEventListener('change', fit);
window.addEventListener('resize', fit);
$('addBox').addEventListener('click', () => { rect = defaultBox(); update(); box.focus({preventScroll: true}); });
$('clear').addEventListener('click', () => { rect = null; update(); });

async function finish(cancel) {
  if (!cancel && (!rect || loading)) return;
  // Read the displayed controls again so autofill/automation cannot submit
  // an earlier rectangle whose change event has not fired yet.
  if (!cancel && !readMeasurements(true)) return;
  $('confirm').disabled = true; $('cancel').disabled = true;
  try {
    const payload = cancel ? {} : {page, rect: [rect.x, rect.y, Math.min(rect.w, 1 - rect.x), Math.min(rect.h, 1 - rect.y)]};
    const response = await fetch(cancel ? 'api/cancel' : 'api/select', {
      method: 'POST', headers: {'Content-Type': 'application/json', 'X-Signpdf-Request': '1'}, body: JSON.stringify(payload)
    });
    if (!response.ok) throw Error();
    $('finishedTitle').textContent = cancel ? 'Placement cancelled' : 'Position selected';
    $('finishedText').textContent = cancel ? 'No signature was requested. You can close this tab.'
      : 'Return to Terminal to continue signing. You can close this tab.';
    $('finished').hidden = false;
  } catch {
    $('message').hidden = false;
    $('message').textContent = 'The position could not be confirmed. Try again, or return to Terminal.';
    $('cancel').disabled = false; update();
  }
}
$('confirm').addEventListener('click', () => finish(false));
$('cancel').addEventListener('click', () => finish(true));

(async () => {
  try {
    const response = await fetch('api/info'); if (!response.ok) throw Error();
    info = await response.json();
    showStructureWarnings(info.warnings || []);
    $('documentName').textContent = info.title;
    $('pageCount').textContent = `of ${info.pages.length}`;
    $('pageNumber').max = info.pages.length;
    stage.classList.toggle('simple', info.style !== 'split');
    await showPage(info.initial_page);
  } catch {
    $('message').textContent = 'The document could not be opened. Return to Terminal to check the command.';
  }
})();
