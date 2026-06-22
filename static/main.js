// static/js/main.js — STARX AI Career Assistant
// Shared utilities: theme toggle, sidebar, toasts, API key, loading

// ── Theme ────────────────────────────────────────────────────────────
const ThemeManager = {
  init() {
    const saved = localStorage.getItem('starx-theme') || 'dark';
    this.apply(saved);
    document.querySelectorAll('.theme-toggle').forEach(btn => {
      btn.addEventListener('click', () => this.toggle());
    });
  },
  apply(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('starx-theme', theme);
    document.querySelectorAll('.theme-toggle').forEach(btn => {
      btn.textContent = theme === 'dark' ? '☀️' : '🌙';
    });
  },
  toggle() {
    const current = document.documentElement.getAttribute('data-theme') || 'dark';
    this.apply(current === 'dark' ? 'light' : 'dark');
  }
};

// ── Sidebar ──────────────────────────────────────────────────────────
const SidebarManager = {
  init() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    const hamburger = document.getElementById('hamburger');

    if (hamburger) {
      hamburger.addEventListener('click', () => this.toggle());
    }
    if (overlay) {
      overlay.addEventListener('click', () => this.close());
    }

    // Highlight active nav item
    const currentPath = window.location.pathname;
    document.querySelectorAll('.nav-item').forEach(item => {
      const href = item.getAttribute('href');
      if (href && (currentPath === href || (href !== '/' && currentPath.startsWith(href)))) {
        item.classList.add('active');
      }
    });
  },
  toggle() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    sidebar?.classList.toggle('open');
    overlay?.classList.toggle('active');
  },
  close() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    sidebar?.classList.remove('open');
    overlay?.classList.remove('active');
  }
};

// ── Toast Notifications ───────────────────────────────────────────────
const Toast = {
  container: null,
  init() {
    this.container = document.querySelector('.toast-container');
    if (!this.container) {
      this.container = document.createElement('div');
      this.container.className = 'toast-container';
      document.body.appendChild(this.container);
    }
  },
  show(message, type = 'info', duration = 3500) {
    const icons = { success: '✅', error: '❌', info: 'ℹ️' };
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span>${icons[type] || 'ℹ️'}</span><span>${message}</span>`;
    this.container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(100%)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, duration);
  }
};

// ── Loading Overlay ───────────────────────────────────────────────────
const Loader = {
  el: null,
  init() {
    this.el = document.getElementById('loadingOverlay');
  },
  show(text = 'Processing with AI...', sub = 'This may take a moment') {
    if (!this.el) return;
    this.el.querySelector('.loading-text').textContent = text;
    this.el.querySelector('.loading-sub').textContent = sub;
    this.el.classList.add('active');
  },
  hide() {
    this.el?.classList.remove('active');
  }
};

// ── API Key Manager ───────────────────────────────────────────────────
const ApiKey = {
  async save(key) {
    try {
      const res = await fetch('/api/set-key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: key })
      });
      const data = await res.json();
      if (data.success) {
        Toast.show('API key saved for this session', 'success');
        // Update all key inputs
        document.querySelectorAll('.api-key-input').forEach(inp => {
          if (!inp.value) inp.placeholder = '••••••••••••••••••••••••••';
        });
      } else {
        Toast.show(data.error || 'Failed to save key', 'error');
      }
    } catch (e) {
      Toast.show('Network error saving API key', 'error');
    }
  },
  init() {
    document.querySelectorAll('.btn-save-key').forEach(btn => {
      btn.addEventListener('click', () => {
        const inp = btn.closest('.api-key-widget')?.querySelector('.api-key-input');
        const key = inp?.value.trim();
        if (!key) {
          Toast.show('Please enter your Gemini API key', 'error');
          return;
        }
        this.save(key);
      });
    });
  }
};

// ── Progress Bar Helper ───────────────────────────────────────────────
function setProgress(barId, pct, labelId, labelText) {
  const bar = document.getElementById(barId);
  if (bar) bar.style.width = pct + '%';
  const label = document.getElementById(labelId);
  if (label) label.textContent = labelText || pct + '%';
}

// ── Score Ring Builder ────────────────────────────────────────────────
function buildScoreRing(score, color = '#c4a03c') {
  const radius = 34;
  const circ = 2 * Math.PI * radius;
  const fill = (score / 100) * circ;
  return `
    <div class="score-ring">
      <svg width="90" height="90" viewBox="0 0 90 90">
        <circle cx="45" cy="45" r="${radius}" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="5"/>
        <circle cx="45" cy="45" r="${radius}" fill="none" stroke="${color}"
          stroke-width="5" stroke-dasharray="${fill} ${circ}"
          stroke-linecap="round" style="transition:stroke-dasharray 1s ease"/>
      </svg>
      <span class="score-ring-value">${score}</span>
    </div>
  `;
}

// ── Copy to Clipboard ─────────────────────────────────────────────────
function copyText(text, label = 'Copied!') {
  navigator.clipboard.writeText(text).then(() => {
    Toast.show(label, 'success', 2000);
  }).catch(() => Toast.show('Copy failed', 'error'));
}

// ── Initialize All ────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  ThemeManager.init();
  SidebarManager.init();
  Toast.init();
  Loader.init();
  ApiKey.init();
});
