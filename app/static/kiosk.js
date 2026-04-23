(function () {
  'use strict';

  // --- Vy-rotation ---

  let currentPosition = 0;
  let rotationTimer = null;
  let rotationPaused = false;

  function showView(position) {
    var tr = (typeof SCREEN_TRANSITION !== 'undefined') ? SCREEN_TRANSITION : 'fade';
    var nextEl = document.getElementById('view-' + position);
    if (!nextEl) return;

    if (tr === 'slide') {
      var leavingEl = document.getElementById('view-' + currentPosition);
      document.querySelectorAll('.view').forEach(function (el) {
        el.classList.remove('active', 'view-entering', 'view-leaving');
      });
      if (leavingEl && leavingEl !== nextEl) leavingEl.classList.add('view-leaving');
      nextEl.classList.add('view-entering', 'active');
      var _lv = leavingEl;
      setTimeout(function () {
        if (_lv) _lv.classList.remove('view-leaving');
        nextEl.classList.remove('view-entering');
      }, 700);
    } else {
      document.querySelectorAll('.view').forEach(function (el) {
        el.classList.remove('active');
      });
      nextEl.classList.add('active');
    }

    currentPosition = position;
    if (window.__KIOSK_DEBUG) updateDebugView();
  }

  function nextView() {
    showView((currentPosition + 1) % VIEW_COUNT);
  }

  function prevView() {
    showView((currentPosition - 1 + VIEW_COUNT) % VIEW_COUNT);
  }

  function scheduleNext() {
    clearTimeout(rotationTimer);
    if (VIEW_COUNT <= 1 || rotationPaused) return;
    var duration = (VIEWS[currentPosition] && VIEWS[currentPosition].duration) || 30;
    rotationTimer = setTimeout(function () {
      nextView();
      scheduleNext();
    }, duration * 1000);
  }

  function pauseRotation() {
    rotationPaused = true;
    clearTimeout(rotationTimer);
  }

  function resumeRotation() {
    rotationPaused = false;
    scheduleNext();
  }

  // --- Kiosk-navigation ---

  var navOverlay = document.getElementById('kiosk-nav');
  var navHideTimer = null;
  var navPaused = false;

  function showNav() {
    if (!navOverlay) return;
    navOverlay.classList.add('visible');
    clearTimeout(navHideTimer);
    navHideTimer = setTimeout(hideNav, 3000);
  }

  function hideNav() {
    if (!navOverlay) return;
    navOverlay.classList.remove('visible');
  }

  document.addEventListener('mousemove', showNav);
  document.addEventListener('touchstart', showNav, { passive: true });

  var pauseBtn = document.getElementById('nav-pause');
  if (pauseBtn) {
    pauseBtn.addEventListener('click', function () {
      if (navPaused) {
        navPaused = false;
        pauseBtn.innerHTML = '&#9646;&#9646;';
        resumeRotation();
      } else {
        navPaused = true;
        pauseBtn.innerHTML = '&#9654;';
        pauseRotation();
      }
    });
  }

  var prevBtn = document.getElementById('nav-prev');
  if (prevBtn) {
    prevBtn.addEventListener('click', function () {
      prevView();
      if (!navPaused) scheduleNext();
    });
  }

  var nextBtn = document.getElementById('nav-next');
  if (nextBtn) {
    nextBtn.addEventListener('click', function () {
      nextView();
      if (!navPaused) scheduleNext();
    });
  }

  // --- Klocka ---

  function tickClocks() {
    var now = new Date();
    document.querySelectorAll('[data-clock-format]').forEach(function (el) {
      var fmt      = el.dataset.clockFormat || 'time_date';
      var tz       = el.dataset.clockTimezone || 'Europe/Stockholm';
      var locale   = el.dataset.clockLocale || 'sv-SE';
      var opts     = { timeZone: tz };
      var timeEl   = el.querySelector('.clock-time');
      var dateEl   = el.querySelector('.clock-date');

      if (timeEl && (fmt === 'time_only' || fmt === 'time_date' || fmt === 'day_time')) {
        timeEl.textContent = now.toLocaleTimeString(locale, Object.assign({}, opts,
          { hour: '2-digit', minute: '2-digit', second: fmt === 'day_time' ? undefined : '2-digit' }));
      }
      if (dateEl && (fmt === 'date_only' || fmt === 'time_date')) {
        dateEl.textContent = now.toLocaleDateString(locale, Object.assign({}, opts,
          { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }));
      }
      if (dateEl && fmt === 'day_time') {
        dateEl.textContent = now.toLocaleDateString(locale, Object.assign({}, opts,
          { weekday: 'long', day: 'numeric', month: 'long' }));
      }
    });
  }

  setInterval(tickClocks, 1000);
  tickClocks();

  // --- Auto-scroll (ics_list) ---

  (function () {
    var PAUSE_MS = 3000;

    document.querySelectorAll('[data-autoscroll]').forEach(function (el) {
      var speed = parseFloat(el.dataset.autoscroll) || 30; // px/s
      var userPaused = false;
      var state = 'pause-top'; // 'scrolling' | 'pause-top' | 'pause-bottom'
      var lastTs = null;
      var pauseUntil = performance.now() + PAUSE_MS;

      el.addEventListener('touchstart', function () {
        userPaused = true;
      }, { passive: true });
      el.addEventListener('touchend', function () {
        setTimeout(function () {
          userPaused = false;
          lastTs = null;
          state = 'pause-top';
          el.scrollTop = 0;
          pauseUntil = performance.now() + PAUSE_MS;
        }, 2000);
      }, { passive: true });

      function step(ts) {
        requestAnimationFrame(step);
        if (userPaused || el.scrollHeight <= el.clientHeight) return;
        if (lastTs === null) lastTs = ts;
        var dt = (ts - lastTs) / 1000;
        lastTs = ts;

        if (state === 'pause-top' || state === 'pause-bottom') {
          if (ts >= pauseUntil) state = state === 'pause-top' ? 'scrolling' : 'pause-reset';
          return;
        }
        if (state === 'pause-reset') {
          el.scrollTop = 0;
          state = 'pause-top';
          pauseUntil = ts + PAUSE_MS;
          return;
        }
        el.scrollTop += speed * dt;
        if (el.scrollTop + el.clientHeight >= el.scrollHeight - 1) {
          state = 'pause-bottom';
          pauseUntil = ts + PAUSE_MS;
        }
      }

      requestAnimationFrame(step);
    });
  })();

  // --- Tidslinje (ics_schedule) ---

  function updateNowLines() {
    var now = new Date();
    var nowMin = now.getHours() * 60 + now.getMinutes();
    document.querySelectorAll('[data-now-start]').forEach(function (col) {
      var startH = parseInt(col.dataset.nowStart, 10);
      var endH   = parseInt(col.dataset.nowEnd, 10);
      var totalMin = (endH - startH) * 60;
      var offset   = nowMin - startH * 60;
      var topPct   = (100 * offset / totalMin).toFixed(4) + '%';
      var hidden   = offset < 0 || offset > totalMin;

      var line = col.querySelector('.isch-now-line');
      var dot  = col.querySelector('.isch-now-dot');
      if (line) { line.style.display = hidden ? 'none' : ''; if (!hidden) line.style.top = topPct; }
      if (dot)  { dot.style.display  = hidden ? 'none' : ''; if (!hidden) dot.style.top  = topPct; }
    });
  }

  updateNowLines();
  setInterval(updateNowLines, 60000);

  // --- SSE ---

  var lastEventAt = Date.now();
  var reconnectCount = 0;
  var backoffMs = 1000;
  var pendingReload = false;
  var offlineBanner = document.getElementById('offline-banner');
  var eventSource = null;

  function connectSSE() {
    if (eventSource) { eventSource.close(); eventSource = null; }

    eventSource = new EventSource('/s/' + SCREEN_SLUG + '/events');

    eventSource.onopen = function () {
      lastEventAt = Date.now();
      backoffMs = 1000;
      offlineBanner.classList.remove('visible');
      if (pendingReload) {
        pendingReload = false;
        location.reload();
      } else {
        resumeRotation();
      }
    };

    eventSource.addEventListener('connected', function (e) {
      lastEventAt = Date.now();
    });

    eventSource.addEventListener('reload', function () {
      lastEventAt = Date.now();
      location.reload();
    });

    eventSource.addEventListener('goto_view', function (e) {
      lastEventAt = Date.now();
      var data = JSON.parse(e.data);
      showView(data.position);
      scheduleNext();
    });

    eventSource.addEventListener('config_changed', function () {
      lastEventAt = Date.now();
      // Ladda inte om direkt — vänta tills SSE är uppkopplad (redan är vi det)
      pendingReload = true;
      pauseRotation();
      // Reload sker vid nästa onopen om anslutningen bryts, annars omedelbart
      location.reload();
    });

    eventSource.addEventListener('widget_updated', function (e) {
      lastEventAt = Date.now();
      var data = JSON.parse(e.data);
      fetchWidgetUpdate(data.widget_id);
    });

    // Kommentarer (keepalive) räknas som aktivitet
    eventSource.onmessage = function () {
      lastEventAt = Date.now();
    };

    eventSource.onerror = function () {
      eventSource.close();
      eventSource = null;
      reconnectCount++;
      if (window.__KIOSK_DEBUG) updateDebugReconnects();
      backoffMs = Math.min(backoffMs * 2, 60000);
      setTimeout(connectSSE, backoffMs);
    };
  }

  // Offline-detektion: om ingen SSE-aktivitet på >90s
  setInterval(function () {
    if (Date.now() - lastEventAt > 90000) {
      offlineBanner.classList.add('visible');
      pauseRotation();
    }
  }, 10000);

  // --- Widget-uppdatering ---

  function fetchWidgetUpdate(widgetId) {
    fetch('/api/widget/' + widgetId + '/data')
      .then(function (r) { return r.ok ? r.text() : Promise.reject(r.status); })
      .then(function (html) {
        document.querySelectorAll('[data-widget-id="' + widgetId + '"]').forEach(function (el) {
          el.innerHTML = html;
        });
      })
      .catch(function () { /* behåll befintlig DOM vid fel */ });
  }

  // --- Debug ---

  function updateDebugView() {
    var el = document.getElementById('debug-view');
    if (el) el.textContent = 'Vy ' + (currentPosition + 1) + '/' + VIEW_COUNT;
  }

  function updateDebugReconnects() {
    var el = document.getElementById('debug-reconnects');
    if (el) el.textContent = 'Reconnects: ' + reconnectCount;
  }

  if (window.__KIOSK_DEBUG) {
    setInterval(function () {
      var el = document.getElementById('debug-sse-age');
      if (el) {
        var s = Math.round((Date.now() - lastEventAt) / 1000);
        el.textContent = 'SSE: ' + s + 's sedan';
      }
    }, 1000);
  }

  // --- Start ---

  showView(0);
  scheduleNext();
  connectSSE();
})();
