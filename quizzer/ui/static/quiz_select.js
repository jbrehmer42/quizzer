// Shared selection logic for the "Create Quiz" and "Quiz by Tags" pages.
// Pages set `window.quizSelectConfig` before loading this script:
//   { checkboxName, noun, total, showTotalTime }
(function () {
  const cfg = window.quizSelectConfig || {};
  const name = cfg.checkboxName;
  const noun = cfg.noun || 'item';
  const total = cfg.total || 0;
  const showTotalTime = Boolean(cfg.showTotalTime);

  function allBoxes() {
    return document.querySelectorAll(`input[type="checkbox"][name="${name}"]`);
  }
  function checkedCount() {
    return document.querySelectorAll(`input[type="checkbox"][name="${name}"]:checked`).length;
  }

  function updateUI() {
    const checked = checkedCount();
    document.getElementById('count-label').textContent = `${checked} / ${total} selected`;
    const btn = document.getElementById('start-btn');
    const practiceBtn = document.getElementById('practice-btn');
    const lbl = document.getElementById('start-label');
    btn.disabled = checked === 0;
    practiceBtn.disabled = checked === 0;
    lbl.textContent = checked === 0
      ? `Select at least one ${noun} to start.`
      : `${checked} ${noun}${checked === 1 ? '' : 's'} selected.`;
    updateTotalTime();
  }

  function onToggle(checkbox, cardId) {
    document.getElementById(cardId).classList.toggle('selected', checkbox.checked);
    updateUI();
  }

  function selectAll() {
    allBoxes().forEach((cb) => {
      cb.checked = true;
      cb.closest('.question-card').classList.add('selected');
    });
    updateUI();
  }

  function deselectAll() {
    allBoxes().forEach((cb) => {
      cb.checked = false;
      cb.closest('.question-card').classList.remove('selected');
    });
    updateUI();
  }

  function onTimerToggle(enabled) {
    document.getElementById('timer-settings').hidden = !enabled;
    if (enabled) updateTotalTime();
  }

  function updateTotalTime() {
    if (!showTotalTime) return;
    if (!document.getElementById('enable-timer').checked) return;
    const mins = parseFloat(document.getElementById('minutes-per-question').value) || 0;
    const checked = checkedCount();
    const totalMins = Math.round(mins * checked);
    document.getElementById('timer-total').textContent = checked > 0
      ? `Total: ${totalMins} min for ${checked} ${noun}${checked === 1 ? '' : 's'}`
      : '';
  }

  window.onToggle = onToggle;
  window.selectAll = selectAll;
  window.deselectAll = deselectAll;
  window.onTimerToggle = onTimerToggle;
  window.updateTotalTime = updateTotalTime;
})();
