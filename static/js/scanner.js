// ══════════════════════════════════════════════
// SCANNER.JS - Escáner QR por cámara (Portería)
// Usa jsQR desde CDN para decodificar QR en tiempo real
// ══════════════════════════════════════════════

let stream = null;
let scanActive = false;
let lastScanned = null;
let cooldown = false;
let modoCenso = false;

const video      = document.getElementById('qr-video');
const canvas     = document.getElementById('qr-canvas');
const ctx        = canvas ? canvas.getContext('2d') : null;
const resultBox  = document.getElementById('scan-result');
const statusText = document.getElementById('scan-status');

async function startScanner() {
  if (stream) return;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'environment', width: 640, height: 480 }
    });
    video.srcObject = stream;
    video.setAttribute('playsinline', true);
    await video.play();
    scanActive = true;
    setStatus('📷 Cámara activa — apunte el QR al recuadro', 'info');
    requestAnimationFrame(scanLoop);
  } catch (err) {
    console.error('Error cámara:', err);
    setStatus('❌ No se pudo acceder a la cámara. Verifica los permisos del navegador.', 'error');
  }
}

function stopScanner() {
  scanActive = false;
  if (stream) {
    stream.getTracks().forEach(t => t.stop());
    stream = null;
  }
  if (video) video.srcObject = null;
  setStatus('Cámara detenida.', 'info');
}

function scanLoop() {
  if (!scanActive) return;

  if (video.readyState === video.HAVE_ENOUGH_DATA) {
    canvas.height = video.videoHeight;
    canvas.width  = video.videoWidth;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const code = jsQR(imageData.data, imageData.width, imageData.height, {
      inversionAttempts: 'dontInvert',
    });

    if (code && code.data && code.data.trim() && !cooldown && code.data !== lastScanned) {
      lastScanned = code.data;
      cooldown = true;
      console.log('[QR] Datos leídos:', code.data.substring(0, 40) + '...');
      procesarQR(code.data.trim());
      setTimeout(() => { cooldown = false; }, 3000);  // 3s entre escaneos
    }
  }

  requestAnimationFrame(scanLoop);
}

function toggleCenso() {
  modoCenso = !modoCenso;
  const btn    = document.getElementById('btn-censo');
  const banner = document.getElementById('censo-banner');
  if (modoCenso) {
    btn.textContent  = '🔴 Salir Censo';
    btn.style.background    = 'rgba(251,191,36,0.2)';
    btn.style.borderColor   = 'rgba(251,191,36,0.5)';
    btn.style.color         = '#fbbf24';
    banner.style.display = 'flex';
    lastScanned = null;  // permitir re-escanear mismos QR al cambiar modo
  } else {
    btn.textContent  = '📋 Modo Censo';
    btn.style.background = '';
    btn.style.borderColor = '';
    btn.style.color = '';
    banner.style.display = 'none';
    lastScanned = null;
  }
}

async function procesarQR(token) {
  const endpoint = modoCenso ? '/api/qr/censo' : '/api/qr/validar';
  setStatus('⏳ Verificando QR...', 'info');
  playBeep();

  try {
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token }),
    });

    const data = await res.json();
    if (modoCenso) {
      mostrarResultadoCenso(data);
    } else {
      mostrarResultado(data);
    }
  } catch (err) {
    setStatus('❌ Error de red al validar QR', 'error');
    console.error(err);
  }
}

function mostrarResultado(data) {
  if (!resultBox) return;
  resultBox.innerHTML = '';
  resultBox.className = 'scan-result';

  if (data.ok) {
    const t = data.trabajador;
    const tipo = data.tipo;
    const colorClass = tipo === 'Entrada' ? 'success' : 'info';
    const emoji = tipo === 'Entrada' ? '✅' : '🔵';

    resultBox.classList.add(colorClass);
    resultBox.innerHTML = `
      <div style="font-size:32px;margin-bottom:8px;">${emoji}</div>
      <div style="font-size:20px;font-weight:800;color:${tipo === 'Entrada' ? '#22c55e' : '#60a5fa'}">
        ${tipo} Registrada
      </div>
      <div style="font-size:22px;font-weight:700;margin:10px 0 4px;">${t.nombre}</div>
      <div style="font-size:13px;color:#94a3b8;margin-bottom:12px;">${t.cargo} · Turno ${t.turno}</div>
      <div style="display:flex;justify-content:center;gap:20px;font-size:13px;">
        <span>📦 Módulo <strong>${t.modulo || '—'}</strong></span>
        <span>🏢 Piso <strong>${t.piso || '—'}</strong></span>
        <span>🚪 Pieza <strong>${t.pieza || '—'}</strong></span>
      </div>
      <div style="font-size:11px;color:#64748b;margin-top:12px;">${new Date().toLocaleTimeString('es-CL')}</div>
    `;
    setStatus('Listo para el siguiente escaneo...', 'ok');
  } else {
    resultBox.classList.add('error');
    resultBox.innerHTML = `
      <div style="font-size:40px;margin-bottom:8px;">🚫</div>
      <div style="font-size:18px;font-weight:700;color:#ef4444;">Acceso Denegado</div>
      <div style="font-size:13px;color:#94a3b8;margin-top:8px;">${data.error || 'QR inválido'}</div>
    `;
    setStatus('❌ QR rechazado. Intente nuevamente.', 'error');
  }
}

function mostrarResultadoCenso(data) {
  if (!resultBox) return;
  resultBox.innerHTML = '';
  resultBox.className = 'scan-result';

  if (data.ok) {
    const t = data.trabajador;
    const tieneP = data.tiene_pieza;
    resultBox.classList.add('success');
    resultBox.innerHTML = `
      <div style="font-size:32px;margin-bottom:8px;">📋</div>
      <div style="font-size:20px;font-weight:800;color:#fbbf24;">Presencia Verificada</div>
      <div style="font-size:22px;font-weight:700;margin:10px 0 4px;">${t.nombre}</div>
      <div style="font-size:13px;color:#94a3b8;margin-bottom:12px;">${t.cargo || '—'} · Turno ${t.turno || '—'}</div>
      <div style="display:flex;justify-content:center;gap:16px;font-size:13px;">
        ${tieneP
          ? `<span>📦 <strong>${t.modulo}</strong> · P${t.piso} · Pieza <strong>${t.pieza}</strong></span>`
          : `<span style="color:#f87171;">⚠️ Sin habitación asignada</span>`}
      </div>
      <div style="font-size:11px;color:#64748b;margin-top:10px;">${new Date().toLocaleTimeString('es-CL')}</div>
    `;
    setStatus('✅ Censo registrado — siguiente trabajador...', 'ok');
  } else {
    resultBox.classList.add('error');
    resultBox.innerHTML = `
      <div style="font-size:40px;margin-bottom:8px;">🚫</div>
      <div style="font-size:18px;font-weight:700;color:#ef4444;">QR no reconocido</div>
      <div style="font-size:13px;color:#94a3b8;margin-top:8px;">${data.error || 'QR inválido'}</div>
    `;
    setStatus('❌ QR rechazado. Intente nuevamente.', 'error');
  }
}

function setStatus(msg, type) {
  if (!statusText) return;
  statusText.textContent = msg;
  statusText.className = 'scan-status-text';
  if (type === 'error') statusText.style.color = '#ef4444';
  else if (type === 'ok') statusText.style.color = '#22c55e';
  else statusText.style.color = '#94a3b8';
}

// Beep sonoro al escanear
function playBeep() {
  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  if (!AudioCtx) return;
  const ac = new AudioCtx();
  const osc = ac.createOscillator();
  const gain = ac.createGain();
  osc.connect(gain);
  gain.connect(ac.destination);
  osc.frequency.value = 880;
  gain.gain.setValueAtTime(0.3, ac.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.2);
  osc.start();
  osc.stop(ac.currentTime + 0.2);
}

// Iniciar al cargar la página
document.addEventListener('DOMContentLoaded', () => {
  startScanner();

  const btnStart = document.getElementById('btn-start-scan');
  const btnStop  = document.getElementById('btn-stop-scan');

  if (btnStart) btnStart.addEventListener('click', startScanner);
  if (btnStop)  btnStop.addEventListener('click', stopScanner);
});
