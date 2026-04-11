// ══════════════════════════════════════════════
// DASHBOARD.JS - Lógica del dashboard principal
// ══════════════════════════════════════════════

// Auto-cerrar flash messages
document.addEventListener('DOMContentLoaded', () => {
  const flashes = document.querySelectorAll('.flash');
  flashes.forEach(f => {
    setTimeout(() => {
      f.style.animation = 'slideIn 0.3s ease reverse';
      setTimeout(() => f.remove(), 300);
    }, 4000);
  });

  // Marcar nav-item activo
  const currentPath = window.location.pathname;
  document.querySelectorAll('.nav-item').forEach(item => {
    const href = item.getAttribute('href');
    if (href && (currentPath === href || (href !== '/' && currentPath.startsWith(href)))) {
      item.classList.add('active');
    }
  });

  // Init donut chart si existe
  if (document.getElementById('ocupacionChart')) {
    initOcupacionChart();
  }

  if (document.getElementById('turnosChart')) {
    initTurnosChart();
  }

  // Auto-actualizar métricas cada 60s
  if (document.querySelector('[data-auto-refresh]')) {
    setInterval(refreshDashboard, 60000);
  }
});

// ── CHARTS ─────────────────────────────────────
function initOcupacionChart() {
  const canvas = document.getElementById('ocupacionChart');
  if (!canvas) return;

  const ocupadas   = parseInt(canvas.dataset.ocupadas   || 0);
  const disponibles= parseInt(canvas.dataset.disponibles|| 0);
  const mant       = parseInt(canvas.dataset.mant       || 0);

  const ctx = canvas.getContext('2d');
  new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Ocupadas', 'Disponibles', 'Mantenimiento'],
      datasets: [{
        data: [ocupadas, disponibles, mant],
        backgroundColor: ['#ef4444','#22c55e','#f59e0b'],
        borderColor: ['#111827'],
        borderWidth: 3,
        hoverOffset: 8,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '72%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            color: '#94a3b8',
            font: { family: 'Inter', size: 11 },
            padding: 16,
            boxWidth: 10,
            borderRadius: 4,
          }
        },
        tooltip: {
          callbacks: {
            label: ctx => ` ${ctx.label}: ${ctx.raw} (${Math.round(ctx.raw / (ocupadas + disponibles + mant) * 100)}%)`,
          }
        }
      }
    }
  });
}

function initTurnosChart() {
  const canvas = document.getElementById('turnosChart');
  if (!canvas) return;

  const raw = JSON.parse(canvas.dataset.turnos || '[]');
  const labels = raw.map(r => r.turno || '—');
  const totales = raw.map(r => r.total);
  const enFaena = raw.map(r => r.en_faena);

  const ctx = canvas.getContext('2d');
  new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'Total',
          data: totales,
          backgroundColor: 'rgba(59,130,246,0.3)',
          borderColor: '#3b82f6',
          borderWidth: 2,
          borderRadius: 6,
        },
        {
          label: 'En Faena',
          data: enFaena,
          backgroundColor: 'rgba(34,197,94,0.3)',
          borderColor: '#22c55e',
          borderWidth: 2,
          borderRadius: 6,
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          labels: { color: '#94a3b8', font: { family: 'Inter', size: 11 } }
        }
      },
      scales: {
        x: { ticks: { color: '#64748b' }, grid: { color: 'rgba(255,255,255,0.04)' } },
        y: { ticks: { color: '#64748b' }, grid: { color: 'rgba(255,255,255,0.04)' }, beginAtZero: true },
      }
    }
  });
}

// ── REFRESH ─────────────────────────────────────
async function refreshDashboard() {
  try {
    const res = await fetch('/api/dashboard');
    const data = await res.json();

    // Actualizar KPIs
    setKpi('kpi-campamento', data.en_campamento);
    setKpi('kpi-descanso', data.en_descanso);
    setKpi('kpi-licencia', data.con_licencia);
    setKpi('kpi-ocupacion', data.pct_ocupacion + '%');
    setKpi('kpi-disponibles', data.disponibles);

    // Timestamp
    const el = document.getElementById('last-refresh');
    if (el) el.textContent = new Date().toLocaleTimeString('es-CL');
  } catch (e) {
    console.warn('No se pudo refrescar el dashboard:', e);
  }
}

function setKpi(id, value) {
  const el = document.getElementById(id);
  if (el) {
    el.textContent = value;
    el.classList.add('pulse');
    setTimeout(() => el.classList.remove('pulse'), 600);
  }
}

// ── MODALES ─────────────────────────────────────
function openModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.classList.add('open');
}

function closeModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.classList.remove('open');
}

// Cerrar modal al hacer clic fuera
document.addEventListener('click', e => {
  if (e.target.classList.contains('modal-backdrop')) {
    e.target.classList.remove('open');
  }
});

// Cerrar modal con Escape
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-backdrop.open').forEach(m => m.classList.remove('open'));
  }
});

// ── CONFIRMACIONES ─────────────────────────────
function confirmar(mensaje, callback) {
  if (confirm(mensaje)) callback();
}

// ── PIEZA TOOLTIP ─────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.pieza[data-info]').forEach(p => {
    p.title = p.dataset.info;
  });
});
