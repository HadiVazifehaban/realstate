<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=true; section>
<#if section = "header">
  <div class="mk-brand">
    <img class="mk-logo" src="${url.resourcesPath}/img/logo.png" alt="شکارچی" width="88" height="88" draggable="false" />
    <div class="mk-title">بازیابی رمز عبور</div>
    <p class="mk-subtitle">رمز عبور جدیدی برای حساب شکارچی خود انتخاب کنید.</p>
    <span class="mk-secure-badge"><i class="fa fa-lock" aria-hidden="true"></i>تأیید شماره موبایل انجام شد</span>
  </div>
<#elseif section = "form">
  <form id="kc-reset-password-form" action="${url.loginAction}" method="post" data-submit-once novalidate>
    <input type="hidden" name="action" value="resetPassword" />
    <div class="mk-field-note mk-recovery-phone">شماره تأییدشده: <strong dir="ltr">${phoneMasked!''}</strong></div>
    <div class="form-group">
      <label for="password">رمز عبور جدید</label>
      <div class="mk-password-field">
        <input id="password" class="mk-input" name="password" type="password" autocomplete="new-password" dir="ltr" minlength="12" maxlength="128" required />
        <button class="mk-pw-toggle" type="button" data-password-toggle="password" aria-label="نمایش رمز عبور" aria-pressed="false">نمایش</button>
      </div>
    </div>
    <div class="form-group">
      <label for="password-confirm">تکرار رمز عبور جدید</label>
      <div class="mk-password-field">
        <input id="password-confirm" class="mk-input" name="password-confirm" type="password" autocomplete="new-password" dir="ltr" minlength="12" maxlength="128" required />
        <button class="mk-pw-toggle" type="button" data-password-toggle="password-confirm" aria-label="نمایش رمز عبور" aria-pressed="false">نمایش</button>
      </div>
    </div>
    <p class="mk-field-note">حداقل ۱۲ کاراکتر. سیاست نهایی رمز عبور توسط Keycloak بررسی می‌شود.</p>
    <div class="mk-recovery-actions">
      <button class="btn btn-secondary mk-link-button" type="button" id="mk-generate-recovery-password">پیشنهاد رمز قوی</button>
      <button class="btn btn-primary mk-btn-primary btn-block" type="submit" data-loading-label="در حال ذخیره…">ذخیره و ورود</button>
    </div>
  </form>
  <script>
    (function () {
      var password = document.getElementById('password');
      var confirmation = document.getElementById('password-confirm');
      var alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%^&*_-+=';
      function index(max) {
        var range = 256 - (256 % max);
        var bytes = new Uint8Array(1);
        do { window.crypto.getRandomValues(bytes); } while (bytes[0] >= range);
        return bytes[0] % max;
      }
      document.getElementById('mk-generate-recovery-password').addEventListener('click', function () {
        var upper = 'ABCDEFGHJKLMNPQRSTUVWXYZ';
        var lower = 'abcdefghijkmnopqrstuvwxyz';
        var digits = '23456789';
        var symbols = '!@#$%^&*_-+=';
        var chars = [upper[index(upper.length)], lower[index(lower.length)], digits[index(digits.length)], symbols[index(symbols.length)]];
        while (chars.length < 20) chars.push(alphabet[index(alphabet.length)]);
        for (var i = chars.length - 1; i > 0; i--) {
          var j = index(i + 1), swap = chars[i];
          chars[i] = chars[j]; chars[j] = swap;
        }
        password.value = chars.join('');
        confirmation.value = password.value;
      });
      document.querySelectorAll('[data-password-toggle]').forEach(function (button) {
        button.addEventListener('click', function () {
          var input = document.getElementById(button.getAttribute('data-password-toggle'));
          var visible = input.type === 'password';
          input.type = visible ? 'text' : 'password';
          button.setAttribute('aria-pressed', String(visible));
          button.textContent = visible ? 'مخفی‌کردن' : 'نمایش';
        });
      });
      document.getElementById('kc-reset-password-form').addEventListener('submit', function (event) {
        if (password.value !== confirmation.value) {
          event.preventDefault();
          confirmation.setCustomValidity('رمز عبور و تکرار آن یکسان نیستند.');
          confirmation.reportValidity();
        } else confirmation.setCustomValidity('');
      });
    })();
  </script>
<#elseif section = "info">
  <div class="mk-form-link mk-form-link--center"><a href="${url.loginUrl}">بازگشت به ورود</a></div>
</#if>
</@layout.registrationLayout>
