(() => {
  const countdown = (seconds, target, onDone) => {
    let remaining = Math.max(0, Number.parseInt(seconds || '0', 10) || 0);
    const paint = () => {
      if (target) target.textContent = `${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, '0')}`;
      if (remaining <= 0) { if (onDone) onDone(); return; }
      remaining -= 1;
      window.setTimeout(paint, 1000);
    };
    paint();
  };

  const otpTimer = document.querySelector('[data-otp-seconds]');
  if (otpTimer) countdown(otpTimer.dataset.otpSeconds, otpTimer.querySelector('[data-otp-countdown]'), () => {
    const otpInput = document.getElementById('otp');
    const verifyButton = document.querySelector('#kc-otp-form button[name="action"][value="verify"]');
    if (otpInput) otpInput.disabled = true;
    if (verifyButton) verifyButton.disabled = true;
    const notice = document.createElement('p');
    notice.className = 'mk-otp-message mk-otp-error';
    notice.setAttribute('role', 'status');
    notice.textContent = 'زمان اعتبار کد پایان یافته است. برای دریافت کد تازه، ارسال مجدد را انتخاب کنید.';
    if (otpTimer.parentElement) otpTimer.parentElement.insertAdjacentElement('afterend', notice);
  });
  const resendButton = document.querySelector('[data-otp-cooldown]');
  if (resendButton) {
    const blockedByCaptcha = resendButton.dataset.captchaBlocked === 'true';
    resendButton.disabled = true;
    countdown(resendButton.dataset.otpCooldown, resendButton.querySelector('[data-cooldown-countdown]'), () => {
      resendButton.disabled = blockedByCaptcha;
    });
  }

  document.querySelectorAll('form[data-submit-once]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      const button = event.submitter;
      if (!button || button.disabled) return;
      button.disabled = true;
      if (button.dataset.loadingLabel) {
        if (button instanceof HTMLInputElement) button.value = button.dataset.loadingLabel;
        else button.textContent = button.dataset.loadingLabel;
      }
      button.setAttribute('aria-busy', 'true');
    });
  });

  const button = document.getElementById('mk-toggle-password');
  const password = document.getElementById('password');
  if (button && password) {
    button.addEventListener('click', () => {
      const show = password.type === 'password';
      password.type = show ? 'text' : 'password';
      button.setAttribute('aria-pressed', String(show));
      button.setAttribute('aria-label', show ? button.dataset.hideLabel : button.dataset.showLabel);
      button.textContent = show ? button.dataset.hideLabel : button.dataset.showLabel;
      password.focus();
    });
  }

  // CAPTCHA refresh uses a separate form so the password and challenge answer
  // are never sent. Carry only the permitted username into that request.
  const refreshForm = document.getElementById('kc-captcha-refresh-form');
  const recoveryForm = document.getElementById('mk-recovery-form');
  const refreshButton = document.querySelector('.mk-captcha-refresh');
  const username = document.getElementById('username');
  if (refreshForm && refreshButton && username) {
    const preservedUsername = refreshForm.querySelector('input[name="username"]') || document.createElement('input');
    preservedUsername.type = 'hidden';
    preservedUsername.name = 'username';
    refreshForm.appendChild(preservedUsername);
    refreshForm.addEventListener('submit', () => {
      preservedUsername.value = username.value;
      const preservedPhone = refreshForm.querySelector('input[name="phone"]');
      if (preservedPhone && phoneInput) preservedPhone.value = phoneInput.value;
      const mode = refreshForm.querySelector('input[name="loginMode"]');
      const smsPanel = document.querySelector('[data-login-panel="sms"]');
      if (mode && recoveryMessage && !recoveryMessage.hidden) mode.value = 'recovery';
      else if (mode) mode.value = smsPanel && !smsPanel.hidden ? 'sms' : 'password';
    });
  }

  const tabs = Array.from(document.querySelectorAll('[data-login-tab]'));
  const panels = Array.from(document.querySelectorAll('[data-login-panel]'));
  const initialMode = document.getElementById('mk-initial-login-mode')?.value;
  const passwordInput = document.getElementById('password');
  const phoneInput = document.getElementById('phone');
  const recoveryLink = document.getElementById('mk-forgot-password');
  const recoveryMessage = document.getElementById('mk-recovery-message');
  const activateTab = (mode, recovering = false) => {
    if (mode === 'sms' && document.getElementById('mk-tab-sms')?.disabled) {
      mode = 'password';
      recovering = false;
    }
    tabs.forEach((tab) => {
      const selected = tab.dataset.loginTab === mode;
      tab.setAttribute('aria-selected', String(selected));
      tab.setAttribute('tabindex', selected ? '0' : '-1');
      tab.classList.toggle('is-active', selected);
    });
    panels.forEach((panel) => {
      panel.hidden = panel.dataset.loginPanel !== mode;
    });
    if (recoveryMessage) recoveryMessage.hidden = !recovering;
    if (mode === 'sms' && phoneInput) phoneInput.focus();
    if (mode === 'password' && username) username.focus();
  };

  if (tabs.length && panels.length) {
    activateTab(initialMode === 'sms' || initialMode === 'recovery' ? 'sms' : 'password', initialMode === 'recovery');
    tabs.forEach((tab) => {
      tab.addEventListener('click', () => activateTab(tab.dataset.loginTab));
      tab.addEventListener('keydown', (event) => {
        if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
        event.preventDefault();
        const enabledTabs = tabs.filter((candidate) => !candidate.disabled);
        if (enabledTabs.length < 2) return;
        const nextMode = tab.dataset.loginTab === 'password' ? 'sms' : 'password';
        activateTab(nextMode);
        document.querySelector(`[data-login-tab="${nextMode}"]`)?.focus();
      });
    });
    document.querySelectorAll('[data-login-panel="sms"] [data-login-tab="password"]').forEach((button) => {
      button.addEventListener('click', () => activateTab('password'));
    });
  }

  if (recoveryLink && recoveryForm) {
    recoveryLink.addEventListener('click', (event) => {
      event.preventDefault();
      if (passwordInput) passwordInput.value = '';
      activateTab('sms', true);
      const recoveryPhone = recoveryForm.querySelector('input[name="phone"]');
      if (recoveryPhone && phoneInput) recoveryPhone.value = phoneInput.value;
      recoveryForm.requestSubmit();
    });
  }
})();
