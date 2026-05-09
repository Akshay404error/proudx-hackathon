// PathForge — OTP input behavior
// Manages the 6-digit segmented input: auto-advance, paste, backspace,
// countdown timer, resend cooldown, shake-on-error.

(function () {
  const RESEND_COOLDOWN_SEC = 30;
  const EXPIRY_SEC = 600; // 10 minutes — must match backend OTP_EXPIRY_MINUTES

  let state = {
    digits: null,
    expiryTimer: null,
    resendTimer: null,
    onComplete: null,
    onResend: null,
  };

  function init({ onComplete, onResend } = {}) {
    state.onComplete = onComplete || (() => {});
    state.onResend = onResend || (() => {});
    state.digits = Array.from(document.querySelectorAll(".otp-digit"));

    if (state.digits.length === 0) return;

    // Clear any previous values
    state.digits.forEach(d => { d.value = ""; d.classList.remove("filled"); });

    // Wire up each digit
    state.digits.forEach((d, i) => {
      d.addEventListener("input", (e) => onInput(e, i));
      d.addEventListener("keydown", (e) => onKeyDown(e, i));
      d.addEventListener("paste", (e) => onPaste(e, i));
      d.addEventListener("focus", () => d.select());
    });

    // Focus first digit
    setTimeout(() => state.digits[0].focus(), 100);

    // Wire up resend link
    const resendLink = document.getElementById("resend-link");
    if (resendLink) {
      resendLink.addEventListener("click", async (e) => {
        e.preventDefault();
        if (resendLink.classList.contains("disabled")) return;
        await state.onResend();
        startResendCooldown();
      });
    }

    // Start expiry countdown
    startExpiryTimer();
  }

  function onInput(e, i) {
    const d = state.digits[i];
    // Strip non-digits
    d.value = d.value.replace(/\D/g, "");
    if (d.value) {
      d.classList.add("filled");
      // Auto-advance
      if (i < state.digits.length - 1) {
        state.digits[i + 1].focus();
      } else {
        d.blur();
      }
    } else {
      d.classList.remove("filled");
    }
    checkComplete();
  }

  function onKeyDown(e, i) {
    const d = state.digits[i];
    if (e.key === "Backspace" && !d.value && i > 0) {
      // Backspace on empty: jump back and clear that one
      state.digits[i - 1].focus();
      state.digits[i - 1].value = "";
      state.digits[i - 1].classList.remove("filled");
      e.preventDefault();
    } else if (e.key === "ArrowLeft" && i > 0) {
      state.digits[i - 1].focus();
      e.preventDefault();
    } else if (e.key === "ArrowRight" && i < state.digits.length - 1) {
      state.digits[i + 1].focus();
      e.preventDefault();
    }
  }

  function onPaste(e, i) {
    e.preventDefault();
    const text = (e.clipboardData || window.clipboardData).getData("text") || "";
    const cleaned = text.replace(/\D/g, "").slice(0, state.digits.length);
    if (!cleaned) return;
    // Fill from current position (or 0)
    cleaned.split("").forEach((ch, idx) => {
      const target = state.digits[idx]; // always start at 0 — common UX
      if (target) {
        target.value = ch;
        target.classList.add("filled");
      }
    });
    // Focus next empty or last
    const nextEmpty = state.digits.findIndex(d => !d.value);
    if (nextEmpty === -1) state.digits[state.digits.length - 1].blur();
    else state.digits[nextEmpty].focus();
    checkComplete();
  }

  function getCode() {
    return state.digits.map(d => d.value).join("");
  }

  function checkComplete() {
    const code = getCode();
    const verifyBtn = document.getElementById("verify-btn");
    const isFull = code.length === state.digits.length;
    if (verifyBtn) verifyBtn.disabled = !isFull;

    if (isFull) {
      // Auto-submit when full
      if (state.onComplete) state.onComplete(code);
    }
  }

  function shake() {
    const row = document.getElementById("otp-row");
    if (!row) return;
    row.style.animation = "none";
    void row.offsetHeight; // reflow
    row.style.animation = "shake 0.4s";
    state.digits.forEach(d => { d.value = ""; d.classList.remove("filled"); });
    setTimeout(() => state.digits[0].focus(), 100);
    const verifyBtn = document.getElementById("verify-btn");
    if (verifyBtn) verifyBtn.disabled = true;
  }

  // ----- Timers -----
  function startExpiryTimer() {
    let remaining = EXPIRY_SEC;
    const el = document.getElementById("countdown");
    const tick = () => {
      const m = Math.floor(remaining / 60);
      const s = remaining % 60;
      if (el) el.textContent = `${m}:${s.toString().padStart(2, "0")}`;
      if (remaining <= 0) {
        clearInterval(state.expiryTimer);
        if (el) el.textContent = "expired";
      }
      remaining -= 1;
    };
    if (state.expiryTimer) clearInterval(state.expiryTimer);
    tick();
    state.expiryTimer = setInterval(tick, 1000);
  }

  function resetTimer() {
    startExpiryTimer();
    state.digits.forEach(d => { d.value = ""; d.classList.remove("filled"); });
    state.digits[0].focus();
    const verifyBtn = document.getElementById("verify-btn");
    if (verifyBtn) verifyBtn.disabled = true;
  }

  function startResendCooldown() {
    const link = document.getElementById("resend-link");
    const cd = document.getElementById("resend-cooldown");
    if (!link) return;
    let remaining = RESEND_COOLDOWN_SEC;
    link.classList.add("disabled");
    link.style.pointerEvents = "none";
    link.style.opacity = "0.5";
    if (cd) cd.classList.remove("hidden");

    const tick = () => {
      if (cd) cd.textContent = ` (${remaining}s)`;
      if (remaining <= 0) {
        clearInterval(state.resendTimer);
        link.classList.remove("disabled");
        link.style.pointerEvents = "";
        link.style.opacity = "";
        if (cd) { cd.classList.add("hidden"); cd.textContent = ""; }
      }
      remaining -= 1;
    };
    tick();
    state.resendTimer = setInterval(tick, 1000);
  }

  // Inject the shake keyframe once
  if (!document.getElementById("otp-shake-style")) {
    const style = document.createElement("style");
    style.id = "otp-shake-style";
    style.textContent = `
      @keyframes shake {
        0%, 100% { transform: translateX(0); }
        20% { transform: translateX(-8px); }
        40% { transform: translateX(8px); }
        60% { transform: translateX(-6px); }
        80% { transform: translateX(6px); }
      }
    `;
    document.head.appendChild(style);
  }

  window.PathForge = window.PathForge || {};
  window.PathForge.OTP = { init, getCode, shake, resetTimer, startResendCooldown };
})();
