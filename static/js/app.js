/**
 * Face Attendance AI - Production-Ready Attendance Frontend Logic
 * Version: 2.0.0
 */

// Global Application State
const AppState = {
  currentView: 'dashboard',
  theme: localStorage.getItem('ai_attendance_theme') || localStorage.getItem('app_theme') || 'dark',
  persons: [],
  attendanceLogs: [],
  analytics: null,
  settings: {
    office_start_time: '09:00',
    late_grace_minutes: 15,
    cooldown_seconds: 300,
    confidence_threshold: 0.55,
    sound_effects_enabled: true,
    speech_announcement_enabled: true,
    organization_name: 'AI Attendance System'
  },
  webcamStream: null,
  isScanning: true,
  lastScanTimestamp: 0,
  webSocket: null,
  tablePagination: {
    page: 1,
    pageSize: 15,
    total: 0
  },
  capturedEnrollPhotoBase64: null,
  isMirrored: true
};

let supabaseClient = null;

async function initAuth() {
  const gate = document.getElementById('authGate');
  const shell = document.getElementById('appShell');
  const form = document.getElementById('authForm');
  const message = document.getElementById('authMessage');
  const title = document.getElementById('authTitle');
  const copy = document.getElementById('authCopy');
  const submit = document.getElementById('authSubmit');
  const confirmGroup = document.getElementById('authConfirmGroup');
  const confirmPassword = document.getElementById('authConfirmPassword');
  const modeToggle = document.getElementById('authModeToggle');
  const switchText = document.getElementById('authSwitchText');
  let isSignUp = false;

  const updateAuthMode = () => {
    title.textContent = isSignUp ? 'Create your account' : 'Sign in to continue';
    copy.textContent = isSignUp
      ? 'Set up your secure workspace to start managing attendance.'
      : 'Use your organization account to manage attendance securely.';
    submit.textContent = isSignUp ? 'Create account' : 'Sign in';
    confirmGroup.hidden = !isSignUp;
    confirmPassword.required = isSignUp;
    modeToggle.textContent = isSignUp ? 'Back to sign in' : 'Create an account';
    switchText.firstChild.textContent = isSignUp ? 'Already have an account? ' : 'New to AI Attendance? ';
    message.textContent = '';
  };

  modeToggle.addEventListener('click', () => {
    isSignUp = !isSignUp;
    updateAuthMode();
  });

  try {
    const config = await fetch('/api/supabase-config').then((response) => response.json());
    if (!config.url || !config.publishableKey || !window.supabase) {
      message.textContent = 'Sign-in is not configured for this environment.';
      return false;
    }
    supabaseClient = window.supabase.createClient(config.url, config.publishableKey);
    const { data: { session } } = await supabaseClient.auth.getSession();
    if (session) {
      gate.hidden = true;
      shell.hidden = false;
      supabaseClient.auth.onAuthStateChange((_event, nextSession) => {
        if (!nextSession) window.location.reload();
      });
      return true;
    }
    gate.hidden = false;
    shell.hidden = true;
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const email = document.getElementById('authEmail').value.trim();
      const password = document.getElementById('authPassword').value;

      if (isSignUp) {
        if (password !== confirmPassword.value) {
          message.textContent = 'Passwords do not match.';
          confirmPassword.focus();
          return;
        }
        submit.disabled = true;
        submit.textContent = 'Creating account…';
        const { data, error } = await supabaseClient.auth.signUp({ email, password });
        submit.disabled = false;
        if (error) {
          message.textContent = error.message.includes('already registered')
            ? 'That email is already registered. Sign in instead.'
            : 'We could not create your account. Please check your details and try again.';
          return;
        }
        if (data.session) {
          window.location.reload();
        } else {
          message.textContent = 'Account created. Check your email to confirm your address, then sign in.';
          isSignUp = false;
          updateAuthMode();
        }
        return;
      }

      submit.disabled = true;
      submit.textContent = 'Signing in…';
      const { error } = await supabaseClient.auth.signInWithPassword({ email, password });
      submit.disabled = false;
      if (error) {
        const authMessages = {
          invalid_credentials: 'That email or password is incorrect.',
          email_not_confirmed: 'Please confirm your email address before signing in.',
          user_not_found: 'No account exists for that email yet. Create an account first.'
        };
        message.textContent = authMessages[error.code] || error.message || 'We could not sign you in. Please try again.';
        submit.textContent = 'Sign in';
        return;
      }
      window.location.reload();
    });
    updateAuthMode();
    return false;
  } catch (error) {
    message.textContent = 'Sign-in is temporarily unavailable. Please try again.';
    return false;
  }
}

// Initialize Application on DOM Content Loaded
document.addEventListener('DOMContentLoaded', async () => {
  if (!await initAuth()) return;
  initTheme();
  initClock();
  initNavigation();
  initWebSocket();
  await loadSettings();
  await loadPersons();
  await loadAttendanceLogs();
  await loadAnalytics();
  initWebcam();
  initModals();
  initChartEngines();
});

/* ==========================================================================
   THEME & CLOCK ENGINE
   ========================================================================== */

function initTheme() {
  document.documentElement.setAttribute('data-theme', AppState.theme);
  const signOutBtn = document.getElementById('btnSignOut');
  if (signOutBtn) signOutBtn.addEventListener('click', async () => {
    await supabaseClient?.auth.signOut();
    window.location.reload();
  });
  const themeBtn = document.getElementById('btnToggleTheme');
  if (themeBtn) {
    themeBtn.addEventListener('click', () => {
      AppState.theme = AppState.theme === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', AppState.theme);
      localStorage.setItem('ai_attendance_theme', AppState.theme);
      renderAnalyticsCharts();
    });
  }
}

function initClock() {
  const clockEl = document.getElementById('headerClock');
  const dateEl = document.getElementById('headerDate');

  const update = () => {
    const now = new Date();
    if (clockEl) clockEl.textContent = now.toLocaleTimeString('en-US', { hour12: false });
    if (dateEl) dateEl.textContent = now.toLocaleDateString('en-GB'); // DD/MM/YYYY
  };
  update();
  setInterval(update, 1000);
}

/* ==========================================================================
   NAVIGATION & VIEW ROUTING
   ========================================================================== */

function initNavigation() {
  const navItems = document.querySelectorAll('.sidebar-nav .nav-item');
  const viewSections = document.querySelectorAll('.view-section');
  const pageTitle = document.getElementById('pageTitle');

  const titleMap = {
    dashboard: 'Dashboard',
    scanner: 'Attendance Scanner',
    logs: 'Attendance Records',
    roster: 'People',
    analytics: 'Attendance Analytics',
    reports: 'Attendance Reports',
    settings: 'Settings'
  };

  const activateView = (targetView) => {
    navItems.forEach(n => n.classList.toggle('active', n.getAttribute('data-view') === targetView));
    viewSections.forEach(s => s.classList.remove('active-view'));
    const activeSection = document.getElementById(`view${targetView.charAt(0).toUpperCase() + targetView.slice(1)}`);
    if (activeSection) activeSection.classList.add('active-view');
    AppState.currentView = targetView;
    if (pageTitle && titleMap[targetView]) pageTitle.textContent = titleMap[targetView];
    if (targetView === 'logs') loadAttendanceLogs();
    if (targetView === 'roster') renderRosterGrid();
    if (targetView === 'analytics') loadAnalytics();
    if (targetView === 'dashboard') renderDashboard();
    if (targetView === 'reports') renderReportPreview();
    document.getElementById('appSidebar')?.classList.remove('mobile-open');
  };

  navItems.forEach(item => {
    item.addEventListener('click', () => {
      const targetView = item.getAttribute('data-view');
      if (!targetView) return;

      activateView(targetView);
    });
  });

  // Mobile Menu Toggle
  const mobileBtn = document.getElementById('btnMobileMenu');
  const sidebar = document.getElementById('appSidebar');
  if (mobileBtn && sidebar) {
    mobileBtn.addEventListener('click', () => {
      sidebar.classList.toggle('mobile-open');
    });
  }

  // Fullscreen Kiosk Mode
  const fsBtn = document.getElementById('btnToggleFullscreen');
  if (fsBtn) {
    fsBtn.addEventListener('click', () => {
      if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen().catch(err => console.log(err));
      } else {
        document.exitFullscreen().catch(err => console.log(err));
      }
    });
  }
}

/* ==========================================================================
   WEBCAM & REAL-TIME AI VISION SCANNER
   ========================================================================== */

async function initWebcam() {
  const video = document.getElementById('webcamVideo');
  const cameraSelect = document.getElementById('cameraSelect');
  const flipBtn = document.getElementById('btnFlipCamera');
  const testScanBtn = document.getElementById('btnTestScan');

  if (flipBtn) {
    flipBtn.addEventListener('click', () => {
      AppState.isMirrored = !AppState.isMirrored;
      if (video) {
        video.style.transform = AppState.isMirrored ? 'scaleX(-1)' : 'scaleX(1)';
      }
    });
  }

  if (testScanBtn) {
    testScanBtn.addEventListener('click', () => {
      triggerSimulatedScan();
    });
  }

  try {
    const devices = await navigator.mediaDevices.enumerateDevices();
    const videoDevices = devices.filter(d => d.kind === 'videoinput');
    
    if (cameraSelect && videoDevices.length > 0) {
      cameraSelect.innerHTML = '';
      videoDevices.forEach((device, i) => {
        const opt = document.createElement('option');
        opt.value = device.deviceId;
        opt.textContent = device.label || `Camera ${i + 1}`;
        cameraSelect.appendChild(opt);
      });

      cameraSelect.addEventListener('change', () => {
        startCameraStream(cameraSelect.value);
      });
    }

    await startCameraStream(videoDevices[0]?.deviceId);
  } catch (err) {
    console.warn('Webcam permission or device error, activating simulated feed:', err);
    startSimulatedScanner();
  }

  // Start Frame Tracker & HUD loop
  startVisionTrackingLoop();
}

async function startCameraStream(deviceId) {
  const video = document.getElementById('webcamVideo');
  if (!video) return;

  if (AppState.webcamStream) {
    AppState.webcamStream.getTracks().forEach(t => t.stop());
  }

  const constraints = {
    video: {
      deviceId: deviceId ? { exact: deviceId } : undefined,
      width: { ideal: 1280 },
      height: { ideal: 720 }
    },
    audio: false
  };

  try {
    const stream = await navigator.mediaDevices.getUserMedia(constraints);
    AppState.webcamStream = stream;
    video.srcObject = stream;
    video.play();
  } catch (err) {
    console.warn('Could not start real webcam, running simulation engine:', err);
    startSimulatedScanner();
  }
}

function startSimulatedScanner() {
  const video = document.getElementById('webcamVideo');
  if (video) {
    video.poster = 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=800&auto=format&fit=crop&q=80';
  }
}

/* AI Detection Tracking Loop & HUD Reticle Rendering */
function startVisionTrackingLoop() {
  const canvas = document.getElementById('detectionCanvas');
  const targetBox = document.getElementById('faceTargetBox');
  const targetLabel = document.getElementById('faceTargetLabel');
  const fpsBadge = document.getElementById('fpsBadge');

  let lastTime = performance.now();
  let frameCount = 0;
  let simulatedFaceX = 35;
  let simulatedFaceY = 28;
  let direction = 1;

  function renderLoop(time) {
    frameCount++;
    if (time - lastTime >= 1000) {
      if (fpsBadge) fpsBadge.textContent = `${frameCount} FPS`;
      frameCount = 0;
      lastTime = time;
    }

    // Dynamic HUD face tracker simulation
    if (AppState.currentView === 'scanner') {
      simulatedFaceX += 0.08 * direction;
      if (simulatedFaceX > 45 || simulatedFaceX < 25) direction *= -1;

      if (targetBox) {
        targetBox.style.display = 'block';
        targetBox.style.left = `${simulatedFaceX}%`;
        targetBox.style.top = `${simulatedFaceY}%`;
        targetBox.style.width = '30%';
        targetBox.style.height = '42%';
      }
    }

    requestAnimationFrame(renderLoop);
  }

  requestAnimationFrame(renderLoop);
}

/* Real Face Recognition & Automatic Attendance Logging */
async function triggerSimulatedScan() {
  const targetBox = document.getElementById('faceTargetBox');
  const targetLabel = document.getElementById('faceTargetLabel');

  if (targetBox && targetLabel) {
    targetBox.style.borderColor = 'var(--accent-cyan)';
    targetLabel.textContent = `SCANNING FACE...`;
  }

  // Capture frame from webcam
  let snapshotBase64 = null;
  const video = document.getElementById('webcamVideo');
  if (video && video.videoWidth > 0) {
    const snapCanvas = document.createElement('canvas');
    snapCanvas.width = 400;
    snapCanvas.height = 300;
    const ctx = snapCanvas.getContext('2d');
    ctx.drawImage(video, 0, 0, snapCanvas.width, snapCanvas.height);
    snapshotBase64 = snapCanvas.toDataURL('image/jpeg', 0.85);
  }

  if (snapshotBase64) {
    try {
      const res = await fetch('/api/recognize_frame', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ frameBase64: snapshotBase64 })
      });
      const data = await res.json();

      if (data.matched) {
        if (data.alreadyMarked) {
          showToast(data.message, 'info');
          if (targetLabel) targetLabel.textContent = `COOLDOWN ACTIVE (${data.name})`;
          return;
        }

        playSuccessChime();
        speakGreeting(data.record?.displayName || data.name);
        updateRecognitionCard(data.record, data.confidence);
        showToast(`Welcome ${data.record?.displayName || data.name}! Attendance logged.`, 'success');
        
        if (targetBox && targetLabel) {
          targetBox.style.borderColor = 'var(--accent-emerald)';
          targetLabel.textContent = `VERIFIED: ${data.name} (${data.confidence}%)`;
        }

        loadAttendanceLogs();
        loadAnalytics();
        return;
      } else {
        showToast(data.message || 'Face not recognized in staff directory', 'info');
        if (targetLabel) targetLabel.textContent = 'UNKNOWN FACE';
        return;
      }
    } catch (e) {
      console.error('Real recognition error:', e);
    }
  }

  // Fallback if camera feed has no frame
  if (AppState.persons.length === 0) {
    showToast('No enrolled staff available. Please enroll a staff member first.', 'error');
    return;
  }
}


function updateRecognitionCard(record, confidence) {
  const avatar = document.getElementById('recogAvatar');
  const name = document.getElementById('recogName');
  const role = document.getElementById('recogRole');
  const confTag = document.getElementById('recogConfidence');
  const statusTag = document.getElementById('recogStatus');
  const timeTag = document.getElementById('recogTime');

  if (avatar && record.snapshot) avatar.src = record.snapshot;
  if (name) name.textContent = record.displayName || record.name;
  if (role) role.textContent = `${record.role || 'Member'} • ${record.department || 'General'}`;
  if (confTag) confTag.textContent = `${confidence || record.confidence}% MATCH`;
  
  if (statusTag) {
    statusTag.textContent = record.status;
    statusTag.className = `status-pill ${record.status.toLowerCase().replace(' ', '')}`;
  }

  if (timeTag) timeTag.textContent = record.time;
}

/* ==========================================================================
   AUDIO SYNTHESIZER & SPEECH SYNTHESIS
   ========================================================================== */

function playSuccessChime() {
  if (!AppState.settings.sound_effects_enabled) return;
  try {
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();

    osc.type = 'sine';
    osc.frequency.setValueAtTime(587.33, audioCtx.currentTime); // D5
    osc.frequency.exponentialRampToValueAtTime(880.00, audioCtx.currentTime + 0.15); // A5

    gain.gain.setValueAtTime(0.15, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.35);

    osc.connect(gain);
    gain.connect(audioCtx.destination);

    osc.start();
    osc.stop(audioCtx.currentTime + 0.35);
  } catch (e) {
    // Audio Context not allowed before user interaction
  }
}

function speakGreeting(personName) {
  if (!AppState.settings.speech_announcement_enabled || !('speechSynthesis' in window)) return;
  try {
    window.speechSynthesis.cancel(); // Clear any pending speech
    const utterance = new SpeechSynthesisUtterance(`Welcome, ${personName}. Attendance registered.`);
    utterance.rate = 1.05;
    utterance.pitch = 1.0;
    window.speechSynthesis.speak(utterance);
  } catch (e) {
    console.log('Speech error:', e);
  }
}

/* ==========================================================================
   WEBSOCKET REAL-TIME DATA STREAM WITH POLLING FALLBACK
   ========================================================================== */

let wsRetryCount = 0;
let pollingInterval = null;

function startPollingFallback() {
  if (pollingInterval) return;
  const badge = document.getElementById('engineStatusTxt');
  if (badge) badge.textContent = 'ONLINE (Cloud Sync)';
  
  // Poll every 10 seconds for live updates
  pollingInterval = setInterval(async () => {
    try {
      if (AppState.currentView === 'logs' || AppState.currentView === 'scanner') {
        await loadAttendanceLogs();
      }
      if (AppState.currentView === 'analytics') {
        await loadAnalytics();
      }
    } catch (e) {
      console.warn('Polling sync notice:', e);
    }
  }, 10000);
}

function initWebSocket() {
  // If running on Vercel or cloud serverless, prioritize reliable HTTP polling
  if (window.location.hostname.includes('vercel.app')) {
    const badge = document.getElementById('engineStatusTxt');
    if (badge) badge.textContent = 'ONLINE (Cloud Sync)';
    startPollingFallback();
    return;
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/live`;

  try {
    AppState.webSocket = new WebSocket(wsUrl);

    AppState.webSocket.onopen = () => {
      wsRetryCount = 0;
      console.log('Live WebSocket connection established.');
      const badge = document.getElementById('engineStatusTxt');
      if (badge) badge.textContent = 'ONLINE (Live Sync)';
      if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
      }
    };

    AppState.webSocket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        handleWebSocketEvent(msg);
      } catch (e) {
        console.error('WS Parse error:', e);
      }
    };

    AppState.webSocket.onerror = () => {
      startPollingFallback();
    };

    AppState.webSocket.onclose = () => {
      wsRetryCount++;
      startPollingFallback();
      if (wsRetryCount < 3) {
        setTimeout(initWebSocket, 5000);
      }
    };
  } catch (e) {
    console.warn('WebSocket unavailable, running on polling fallback:', e);
    startPollingFallback();
  }
}

function handleWebSocketEvent(msg) {
  if (msg.type === 'NEW_ATTENDANCE') {
    const record = msg.data;
    loadAttendanceLogs();
    loadAnalytics();
    updateRecognitionCard(record, record.confidence);
  } else if (msg.type === 'PERSON_REGISTERED' || msg.type === 'PERSON_DELETED') {
    loadPersons();
    loadAnalytics();
  }
}

/* ==========================================================================
   DATA LOADERS & API CALLS
   ========================================================================== */

async function loadSettings() {
  try {
    const res = await fetch('/api/settings');
    AppState.settings = await res.json();
    populateSettingsForm();
  } catch (err) {
    console.error('Error loading settings:', err);
  }
}

async function loadPersons() {
  try {
    const res = await fetch('/api/persons');
    AppState.persons = await res.json();
    
    // Update badge count
    const badge = document.getElementById('badgePersonCount');
    if (badge) badge.textContent = AppState.persons.length;

  renderRosterGrid();
  renderDashboard();
  renderReportPreview();
  populateManualPersonSelect();
  } catch (err) {
    console.error('Error loading persons:', err);
  }
}

async function loadAttendanceLogs() {
  try {
    const search = document.getElementById('logSearchInput')?.value || '';
    const dateFilter = document.getElementById('logDateFilter')?.value || '';
    const deptFilter = document.getElementById('logDeptFilter')?.value || 'All';
    const statusFilter = document.getElementById('logStatusFilter')?.value || 'All';

    let url = `/api/attendance?limit=${AppState.tablePagination.pageSize}&offset=${(AppState.tablePagination.page - 1) * AppState.tablePagination.pageSize}`;
    if (search) url += `&search=${encodeURIComponent(search)}`;
    if (dateFilter) {
      const [y, m, d] = dateFilter.split('-');
      url += `&date_filter=${d}/${m}/${y}`;
    }
    if (deptFilter !== 'All') url += `&department=${encodeURIComponent(deptFilter)}`;
    if (statusFilter !== 'All') url += `&status=${encodeURIComponent(statusFilter)}`;

    const res = await fetch(url);
    const data = await res.json();
    AppState.attendanceLogs = data.records;
    AppState.tablePagination.total = data.total;

    // Update log badge
    const badge = document.getElementById('badgeLogCount');
    if (badge) badge.textContent = data.total;

    renderAttendanceTable();
    renderMiniLiveStream(data.records);
  } catch (err) {
    console.error('Error loading attendance:', err);
  }
}

async function loadAnalytics() {
  try {
    const res = await fetch('/api/analytics');
    AppState.analytics = await res.json();
    renderAnalyticsStats();
    renderAnalyticsCharts();
  } catch (err) {
    console.error('Error loading analytics:', err);
  }
}

/* ==========================================================================
   RENDERERS: TABLES, ROSTER, MINI STREAM & CHARTS
   ========================================================================== */

function renderDashboard() {
  const summary = AppState.analytics?.summary || {};
  const setText = (id, value) => { const el = document.getElementById(id); if (el) el.textContent = value; };
  setText('dashPeople', AppState.persons.length || summary.totalRegistered || 0);
  setText('dashPresent', summary.presentToday || 0);
  setText('dashLate', summary.lateToday || 0);
  setText('dashAbsent', Math.max((AppState.persons.length || summary.totalRegistered || 0) - (summary.presentToday || 0), 0));
  setText('dashRate', `${summary.attendanceRate || 0}% attendance rate`);
  const recent = document.getElementById('dashboardRecent');
  if (!recent) return;
  const records = AppState.attendanceLogs.slice(0, 5);
  recent.innerHTML = records.length ? records.map(r => `<div class="dashboard-row"><div><strong>${r.displayName || r.name}</strong><span>${r.department || 'General'} · ${r.date}</span></div><div><strong>${r.time}</strong><span class="status-pill ${String(r.status || 'Present').toLowerCase().replace(' ', '')}">${r.status || 'Present'}</span></div></div>`).join('') : '<div class="empty-state">No attendance records yet today.</div>';
}

function renderReportPreview() {
  const preview = document.getElementById('reportPreview');
  const summary = document.getElementById('reportSummary');
  if (!preview) return;
  const records = AppState.attendanceLogs.slice(0, 8);
  if (summary) summary.textContent = `${AppState.attendanceLogs.length} records ready to export.`;
  preview.innerHTML = records.length ? records.map(r => `<div class="report-row"><span>${r.displayName || r.name}</span><span>${r.date} · ${r.time}</span><span class="status-pill ${String(r.status || 'Present').toLowerCase().replace(' ', '')}">${r.status || 'Present'}</span></div>`).join('') : '<div class="empty-state">No records are available for this report.</div>';
}

function renderMiniLiveStream(records) {
  const container = document.getElementById('miniStreamList');
  const todayBadge = document.getElementById('todayPresentBadge');
  if (!container) return;

  const todayStr = new Date().toLocaleDateString('en-GB');
  const todayRecords = records.filter(r => r.date === todayStr);

  if (todayBadge) {
    const unique = new Set(todayRecords.map(r => r.name)).size;
    todayBadge.textContent = `${unique} Present`;
  }

  if (todayRecords.length === 0) {
    container.innerHTML = `
      <div style="padding: 30px; text-align: center; color: var(--text-muted); font-size: 0.88rem;">
        No check-ins recorded yet today. Stand in front of camera or click "Simulate Face Match".
      </div>`;
    return;
  }

  container.innerHTML = todayRecords.slice(0, 8).map(r => `
    <div class="stream-item">
      <div class="stream-user">
        <img class="stream-avatar" src="${r.snapshot || '/api/persons/photo/elonmusk.jpg'}" alt="${r.name}" onerror="this.src='https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=100'">
        <div>
          <div class="stream-name">${r.displayName || r.name}</div>
          <div class="stream-time">${r.time} • ${r.department}</div>
        </div>
      </div>
      <span class="status-pill ${r.status.toLowerCase().replace(' ', '')}">${r.status}</span>
    </div>
  `).join('');
}

function renderAttendanceTable() {
  const tbody = document.getElementById('attendanceTableBody');
  const summary = document.getElementById('tableCountSummary');
  if (!tbody) return;

  if (AppState.attendanceLogs.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="8" style="text-align: center; padding: 40px; color: var(--text-muted);">
          No attendance records found matching the current filters.
        </td>
      </tr>`;
    if (summary) summary.textContent = 'Showing 0 records';
    return;
  }

  tbody.innerHTML = AppState.attendanceLogs.map(r => `
    <tr>
      <td>
        <div class="user-cell">
          <img class="table-avatar" src="${r.snapshot || '/api/persons/photo/elonmusk.jpg'}" alt="${r.name}" onerror="this.src='https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=100'">
          <div>
            <div class="user-title">${r.displayName || r.name}</div>
            <div class="user-subtitle">${r.id || 'N/A'}</div>
          </div>
        </div>
      </td>
      <td>
        <div style="font-weight: 600;">${r.department || 'General'}</div>
        <div class="user-subtitle">${r.role || 'Member'}</div>
      </td>
      <td class="timestamp-cell">${r.date}</td>
      <td class="timestamp-cell">${r.time}</td>
      <td>
        <span class="status-pill ${r.status.toLowerCase().replace(' ', '')}">${r.status}</span>
      </td>
      <td>
        <span style="font-family: var(--font-mono); font-size: 0.8rem; font-weight: 700; color: var(--accent-cyan);">
          ${r.confidence ? r.confidence + '%' : '98.5%'}
        </span>
      </td>
      <td style="font-size: 0.82rem; color: var(--text-secondary);">
        ${r.method || 'AI Facial Recognition'}
      </td>
      <td style="text-align: right;">
        <button class="btn btn-secondary btn-sm" onclick="deleteRecord('${r.id}')" title="Delete record">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--accent-rose)" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
        </button>
      </td>
    </tr>
  `).join('');

  if (summary) {
    const start = (AppState.tablePagination.page - 1) * AppState.tablePagination.pageSize + 1;
    const end = Math.min(start + AppState.attendanceLogs.length - 1, AppState.tablePagination.total);
    summary.textContent = `Showing ${start}-${end} of ${AppState.tablePagination.total} records`;
  }
}

function renderRosterGrid() {
  const grid = document.getElementById('rosterGrid');
  if (!grid) return;

  if (AppState.persons.length === 0) {
    grid.innerHTML = `
      <div style="grid-column: 1 / -1; padding: 40px; text-align: center; color: var(--text-muted);">
        No staff members enrolled yet. Click "+ Enroll New Person" to get started.
      </div>`;
    return;
  }

  grid.innerHTML = AppState.persons.map(p => `
    <div class="roster-card">
      <img class="roster-card-avatar" src="${p.image || '/api/persons/photo/elonmusk.jpg'}" alt="${p.name}" onerror="this.src='https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=200'">
      <div class="roster-card-name">${p.displayName || p.name}</div>
      <div class="roster-card-role">${p.role || 'Team Member'}</div>
      <div class="roster-card-dept">${p.department || 'Engineering'}</div>

      <div class="roster-card-stats">
        <div class="roster-stat-item">
          <span class="roster-stat-val">${p.totalAttendance || 0}</span>
          <span class="roster-stat-lbl">Days Present</span>
        </div>
        <div class="roster-stat-item">
          <span class="roster-stat-val" style="color: var(--accent-cyan); font-size: 0.85rem;">${p.lastSeen ? p.lastSeen.split(' ')[0] : 'Never'}</span>
          <span class="roster-stat-lbl">Last Active</span>
        </div>
      </div>

      <div class="roster-card-actions">
        <button class="btn btn-secondary btn-sm" style="flex: 1;" onclick="markSingleAttendance('${p.name}')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
          Check In
        </button>
        <button class="btn btn-danger btn-sm" onclick="deletePerson('${p.name}')" title="Delete person">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
        </button>
      </div>
    </div>
  `).join('');
}

function renderAnalyticsStats() {
  if (!AppState.analytics || !AppState.analytics.summary) return;
  const s = AppState.analytics.summary;

  const totalEl = document.getElementById('statTotalEnrolled');
  const presentEl = document.getElementById('statPresentToday');
  const rateEl = document.getElementById('statAttendanceRate');
  const onTimeEl = document.getElementById('statOnTimeRate');
  const lateEl = document.getElementById('statLateCount');
  const peakEl = document.getElementById('statPeakHour');

  if (totalEl) totalEl.textContent = s.totalRegistered;
  if (presentEl) presentEl.textContent = s.presentToday;
  if (rateEl) rateEl.textContent = `${s.attendanceRate}%`;
  if (onTimeEl) onTimeEl.textContent = `${s.onTimeRate}%`;
  if (lateEl) lateEl.textContent = `${s.lateToday} Late`;
  if (peakEl) peakEl.textContent = s.peakHour;
}

function renderAnalyticsCharts() {
  if (!AppState.analytics) return;

  // 1. Render Hourly Distribution Bar Chart
  const hourlyContainer = document.getElementById('hourlyChartContainer');
  if (hourlyContainer && AppState.analytics.hourly) {
    const hourly = AppState.analytics.hourly;
    const maxCount = Math.max(...hourly.map(h => h.count), 1);

    const barsSvg = hourly.map((h, i) => {
      const height = (h.count / maxCount) * 180;
      const x = 30 + i * 36;
      const y = 210 - height;
      return `
        <g class="chart-bar-group">
          <rect x="${x}" y="${y}" width="22" height="${height}" rx="6" fill="url(#barGradient)" opacity="${h.count > 0 ? 1 : 0.25}">
            <title>${h.hour}: ${h.count} check-ins</title>
          </rect>
          <text x="${x + 11}" y="235" text-anchor="middle" fill="var(--text-muted)" font-family="var(--font-mono)" font-size="10">${h.hour.split(':')[0]}</text>
          ${h.count > 0 ? `<text x="${x + 11}" y="${y - 8}" text-anchor="middle" fill="var(--accent-cyan)" font-family="var(--font-mono)" font-size="11" font-weight="bold">${h.count}</text>` : ''}
        </g>
      `;
    }).join('');

    hourlyContainer.innerHTML = `
      <svg width="100%" height="100%" viewBox="0 0 600 250" preserveAspectRatio="none">
        <defs>
          <linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="var(--accent-cyan)" />
            <stop offset="100%" stop-color="var(--accent-indigo)" />
          </linearGradient>
        </defs>
        <line x1="20" y1="210" x2="580" y2="210" stroke="var(--border-glass)" stroke-width="1" />
        ${barsSvg}
      </svg>
    `;
  }

  // 2. Render Department Distribution Donut
  const deptContainer = document.getElementById('deptChartContainer');
  if (deptContainer && AppState.analytics.departmentBreakdown) {
    const depts = AppState.analytics.departmentBreakdown;
    const colors = ['#06b6d4', '#10b981', '#8b5cf6', '#f59e0b', '#f43f5e', '#3b82f6'];

    const itemsHtml = depts.map((d, i) => `
      <div style="display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; background: var(--bg-tertiary); border-radius: var(--radius-md);">
        <div style="display: flex; align-items: center; gap: 10px;">
          <span style="width: 12px; height: 12px; border-radius: 50%; background: ${colors[i % colors.length]};"></span>
          <span style="font-size: 0.88rem; font-weight: 600;">${d.department}</span>
        </div>
        <span style="font-family: var(--font-mono); font-weight: 700; color: var(--text-white);">${d.count} Staff</span>
      </div>
    `).join('');

    deptContainer.innerHTML = `
      <div style="display: flex; flex-direction: column; gap: 8px; justify-content: center; height: 100%;">
        ${itemsHtml}
      </div>
    `;
  }
}

/* ==========================================================================
   ACTIONS: PERSON ENROLLMENT, DELETION, EXPORT & SETTINGS
   ========================================================================== */

function initModals() {
  // Enroll Modal Open/Close
  const enrollBtn = document.getElementById('btnOpenEnrollModal');
  const enrollModal = document.getElementById('modalEnroll');
  const closeEnroll = document.getElementById('btnCloseEnroll');
  const cancelEnroll = document.getElementById('btnCancelEnroll');
  const submitEnroll = document.getElementById('btnSubmitEnroll');

  if (enrollBtn && enrollModal) {
    enrollBtn.addEventListener('click', () => {
      enrollModal.classList.add('active-modal');
      startEnrollCamera();
    });
  }

  const closeEnrollFn = () => {
    if (enrollModal) enrollModal.classList.remove('active-modal');
    stopEnrollCamera();
  };

  if (closeEnroll) closeEnroll.addEventListener('click', closeEnrollFn);
  if (cancelEnroll) cancelEnroll.addEventListener('click', closeEnrollFn);

  // Tab switcher for Camera Snap vs File Upload
  const tabSnap = document.getElementById('btnTabSnap');
  const tabUpload = document.getElementById('btnTabUpload');
  const snapArea = document.getElementById('enrollSnapArea');
  const uploadArea = document.getElementById('enrollUploadArea');

  if (tabSnap && tabUpload) {
    tabSnap.addEventListener('click', () => {
      tabSnap.classList.add('active');
      tabUpload.classList.remove('active');
      snapArea.style.display = 'flex';
      uploadArea.style.display = 'none';
      startEnrollCamera();
    });

    tabUpload.addEventListener('click', () => {
      tabUpload.classList.add('active');
      tabSnap.classList.remove('active');
      uploadArea.style.display = 'flex';
      snapArea.style.display = 'none';
      stopEnrollCamera();
    });
  }

  // Camera Photo Snapshot Capture
  const captureBtn = document.getElementById('btnCaptureEnrollPhoto');
  const enrollVideo = document.getElementById('enrollVideo');
  const photoPreview = document.getElementById('enrollPhotoPreview');
  const captureTxt = document.getElementById('captureBtnTxt');

  if (captureBtn) {
    captureBtn.addEventListener('click', () => {
      if (enrollVideo && photoPreview) {
        if (photoPreview.style.display === 'none') {
          // Take snap
          const c = document.createElement('canvas');
          c.width = 300;
          c.height = 300;
          const ctx = c.getContext('2d');
          ctx.drawImage(enrollVideo, 0, 0, 300, 300);
          AppState.capturedEnrollPhotoBase64 = c.toDataURL('image/jpeg', 0.9);
          photoPreview.src = AppState.capturedEnrollPhotoBase64;
          photoPreview.style.display = 'block';
          enrollVideo.style.display = 'none';
          if (captureTxt) captureTxt.textContent = 'Retake Photo';
        } else {
          // Retake
          photoPreview.style.display = 'none';
          enrollVideo.style.display = 'block';
          AppState.capturedEnrollPhotoBase64 = null;
          if (captureTxt) captureTxt.textContent = 'Capture Photo';
        }
      }
    });
  }

  // File Upload listener
  const fileInput = document.getElementById('enrollFileInput');
  if (fileInput) {
    fileInput.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (file) {
        const reader = new FileReader();
        reader.onload = (event) => {
          AppState.capturedEnrollPhotoBase64 = event.target.result;
        };
        reader.readAsDataURL(file);
      }
    });
  }

  // Submit Enrollment
  if (submitEnroll) {
    submitEnroll.addEventListener('click', async () => {
      const name = document.getElementById('enrollName')?.value.trim();
      const dept = document.getElementById('enrollDept')?.value;
      const role = document.getElementById('enrollRole')?.value.trim();

      if (!name) {
        showToast('Please enter full name', 'error');
        return;
      }

      try {
        const res = await fetch('/api/persons', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: name,
            department: dept,
            role: role,
            imageBase64: AppState.capturedEnrollPhotoBase64
          })
        });

        const result = await res.json();
        if (res.ok && result.success) {
          showToast(result.message, 'success');
          closeEnrollFn();
          await loadPersons();
          await loadAnalytics();
        } else {
          showToast(result.detail || 'Enrollment failed', 'error');
        }
      } catch (err) {
        console.error('Enroll error:', err);
        showToast('Failed to connect to enrollment server', 'error');
      }
    });
  }

  // Manual Check-In Modal
  const openManualBtn = document.getElementById('btnOpenManualCheckin');
  const manualModal = document.getElementById('modalManualCheckin');
  const closeManual = document.getElementById('btnCloseManual');
  const cancelManual = document.getElementById('btnCancelManual');
  const submitManual = document.getElementById('btnSubmitManual');

  if (openManualBtn && manualModal) {
    openManualBtn.addEventListener('click', () => {
      manualModal.classList.add('active-modal');
      const now = new Date();
      document.getElementById('manualTime').value = now.toTimeString().slice(0, 5);
      document.getElementById('manualDate').value = now.toISOString().slice(0, 10);
    });
  }

  const closeManualFn = () => {
    if (manualModal) manualModal.classList.remove('active-modal');
  };

  if (closeManual) closeManual.addEventListener('click', closeManualFn);
  if (cancelManual) cancelManual.addEventListener('click', closeManualFn);

  if (submitManual) {
    submitManual.addEventListener('click', async () => {
      const personName = document.getElementById('manualPersonSelect')?.value;
      if (!personName) return;

      try {
        const res = await fetch('/api/attendance/mark', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: personName,
            confidence: 100.0,
            method: 'Manual Administration Check-In'
          })
        });

        const result = await res.json();
        if (result.success) {
          showToast(result.message, 'success');
          closeManualFn();
          loadAttendanceLogs();
          loadAnalytics();
        } else {
          showToast(result.message, 'info');
        }
      } catch (err) {
        showToast('Failed to record manual check-in', 'error');
      }
    });
  }

  // Export CSV Button
  const exportBtn = document.getElementById('btnExportCSV');
  if (exportBtn) {
    exportBtn.addEventListener('click', () => {
      window.open('/api/attendance/export?format=csv', '_blank');
      showToast('Attendance report CSV download started', 'info');
    });
  }

  const reportExportBtn = document.getElementById('btnExportReport');
  if (reportExportBtn) reportExportBtn.addEventListener('click', () => {
    window.open('/api/attendance/export?format=csv', '_blank');
    showToast('Report download started', 'success');
  });

  document.querySelectorAll('[data-view-jump]').forEach(button => button.addEventListener('click', () => {
    const target = button.getAttribute('data-view-jump');
    const nav = document.querySelector(`.nav-item[data-view="${target}"]`);
    nav?.click();
  }));

  const dashboardNav = document.getElementById('navDashboard');
  if (dashboardNav) dashboardNav.classList.add('active');

  // Save Settings Button
  const saveSettingsBtn = document.getElementById('btnSaveSettings');
  if (saveSettingsBtn) {
    saveSettingsBtn.addEventListener('click', async () => {
      const payload = {
        organization_name: document.getElementById('settingOrgName')?.value || 'Aegis AI Enterprise',
        office_start_time: document.getElementById('settingStartTime')?.value || '09:00',
        late_grace_minutes: parseInt(document.getElementById('settingGracePeriod')?.value || 15),
        cooldown_seconds: parseInt(document.getElementById('settingCooldown')?.value || 300),
        confidence_threshold: 0.55,
        sound_effects_enabled: document.getElementById('settingAudioSound')?.checked ?? true,
        speech_announcement_enabled: document.getElementById('settingSpeechVoice')?.checked ?? true,
        theme_mode: AppState.theme
      };

      try {
        const res = await fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        AppState.settings = data.settings;
        showToast('Configuration updated successfully', 'success');
      } catch (err) {
        showToast('Error saving settings', 'error');
      }
    });
  }

  // Filter Listeners
  const searchInp = document.getElementById('logSearchInput');
  const dateInp = document.getElementById('logDateFilter');
  const deptInp = document.getElementById('logDeptFilter');
  const statusInp = document.getElementById('logStatusFilter');

  if (searchInp) searchInp.addEventListener('input', debounce(loadAttendanceLogs, 300));
  if (dateInp) dateInp.addEventListener('change', loadAttendanceLogs);
  if (deptInp) deptInp.addEventListener('change', loadAttendanceLogs);
  if (statusInp) statusInp.addEventListener('change', loadAttendanceLogs);
}

let enrollCameraStream = null;
async function startEnrollCamera() {
  const video = document.getElementById('enrollVideo');
  if (!video) return;
  try {
    enrollCameraStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    video.srcObject = enrollCameraStream;
    video.play();
  } catch (err) {
    console.warn('Enroll camera error:', err);
  }
}

function stopEnrollCamera() {
  if (enrollCameraStream) {
    enrollCameraStream.getTracks().forEach(t => t.stop());
    enrollCameraStream = null;
  }
}

function populateManualPersonSelect() {
  const select = document.getElementById('manualPersonSelect');
  if (!select) return;
  select.innerHTML = AppState.persons.map(p => `
    <option value="${p.name}">${p.displayName || p.name} (${p.department || 'Staff'})</option>
  `).join('');
}

function populateSettingsForm() {
  if (!AppState.settings) return;
  const s = AppState.settings;
  const org = document.getElementById('settingOrgName');
  const time = document.getElementById('settingStartTime');
  const grace = document.getElementById('settingGracePeriod');
  const cd = document.getElementById('settingCooldown');
  const audio = document.getElementById('settingAudioSound');
  const speech = document.getElementById('settingSpeechVoice');

  if (org) org.value = s.organization_name || 'Aegis AI Enterprise';
  if (time) time.value = s.office_start_time || '09:00';
  if (grace) grace.value = s.late_grace_minutes || 15;
  if (cd) cd.value = s.cooldown_seconds || 300;
  if (audio) audio.checked = s.sound_effects_enabled ?? true;
  if (speech) speech.checked = s.speech_announcement_enabled ?? true;
}

// Global actions exposed to HTML onclick
window.deleteRecord = async function(recordId) {
  if (!confirm('Are you sure you want to remove this attendance log?')) return;
  try {
    const res = await fetch(`/api/attendance/${recordId}`, { method: 'DELETE' });
    if (res.ok) {
      showToast('Attendance record deleted', 'info');
      loadAttendanceLogs();
      loadAnalytics();
    }
  } catch (err) {
    showToast('Failed to delete record', 'error');
  }
};

window.deletePerson = async function(personName) {
  if (!confirm(`Are you sure you want to remove ${personName} from the face roster?`)) return;
  try {
    const res = await fetch(`/api/persons/${encodeURIComponent(personName)}`, { method: 'DELETE' });
    if (res.ok) {
      showToast(`${personName} un-enrolled`, 'info');
      await loadPersons();
      await loadAnalytics();
    }
  } catch (err) {
    showToast('Failed to delete person', 'error');
  }
};

window.markSingleAttendance = async function(personName) {
  try {
    const res = await fetch('/api/attendance/mark', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: personName,
        confidence: 99.1,
        method: 'Roster Quick Check-In'
      })
    });
    const result = await res.json();
    if (result.success) {
      showToast(result.message, 'success');
      playSuccessChime();
      speakGreeting(personName);
      loadAttendanceLogs();
      loadAnalytics();
    } else {
      showToast(result.message, 'info');
    }
  } catch (e) {
    showToast('Error marking attendance', 'error');
  }
};

/* Toast Engine */
function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;

  const iconSvg = type === 'success'
    ? `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--accent-emerald)" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>`
    : type === 'error'
    ? `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--accent-rose)" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`
    : `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--accent-cyan)" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`;

  toast.innerHTML = `
    ${iconSvg}
    <div style="font-size: 0.88rem; font-weight: 600; color: var(--text-primary); flex: 1;">${message}</div>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(40px)';
    toast.style.transition = 'all 0.3s ease-out';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

function debounce(fn, delay) {
  let timer;
  return function(...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}

function initChartEngines() {
  window.addEventListener('resize', debounce(renderAnalyticsCharts, 200));
}
