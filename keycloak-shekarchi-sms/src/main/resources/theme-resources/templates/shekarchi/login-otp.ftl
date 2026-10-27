<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=true; section>
  <#if section = "header">
    <div class="mk-brand">
      <img class="mk-logo" src="${url.resourcesPath}/img/logo.png" alt="شکارچی" width="76" height="76" draggable="false" />
      <div class="mk-title">تأیید شماره موبایل</div>
      <p class="mk-subtitle">کد ورود برای شماره ${phoneMasked!''}</p>
    </div>
  <#elseif section = "form">
    <#if otpDeliveryMessage??>
      <p class="mk-otp-message mk-otp-delivery-note" role="status" aria-live="polite">${otpDeliveryMessage}</p>
    </#if>
    <#if otpMessage??>
      <p class="mk-otp-message" role="status" aria-live="polite">${otpMessage}</p>
    </#if>

    <form id="kc-otp-form" action="${url.loginAction}" method="post" novalidate data-submit-once>
      <div class="form-group">
        <label for="otp" class="pf-c-form__label pf-c-form__label-text">کد شش‌رقمی تأیید</label>
        <input tabindex="1" id="otp" class="pf-c-form-control mk-input mk-otp-cell-input" name="otp" type="text" dir="ltr" inputmode="numeric" autocomplete="one-time-code" placeholder="••••••" maxlength="6" pattern="[0-9۰-۹٠-٩]{6}" autofocus aria-describedby="mk-otp-time" />
      </div>

      <div class="mk-otp-meta" id="mk-otp-time" data-otp-seconds="${otpSecondsRemaining!0}">
        <span>اعتبار کد</span>
        <span aria-live="off" data-otp-countdown>۰:۰۰</span>
      </div>

      <#if captchaRequired?? && captchaRequired>
        <#if captchaAvailable?? && captchaAvailable>
          <fieldset class="mk-captcha" aria-describedby="mk-otp-captcha-question">
            <legend class="mk-captcha-title">تأیید انسانی</legend>
            <span class="mk-captcha-sr-only" id="mk-otp-captcha-question">${captchaQuestion!''}</span>
            <div class="mk-captcha-challenge">
              <img class="mk-captcha-image" src="${captchaImage!''}" alt="${captchaQuestion!''}" width="240" height="76" />
              <button class="mk-captcha-refresh" type="submit" form="kc-captcha-refresh-form" aria-label="تولید تصویر کپچای تازه" title="تصویر تازه"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 7v5h-5M4 17v-5h5"/><path d="M5.5 9a7 7 0 0 1 11.6-2L20 12M4 12l2.9 5a7 7 0 0 0 11.6-2"/></svg></button>
            </div>
            <label for="otpCaptchaAnswer" class="pf-c-form__label pf-c-form__label-text">حروف تصویر را وارد کنید</label>
            <input id="otpCaptchaAnswer" class="pf-c-form-control mk-input" name="captchaAnswer" type="text" autocomplete="off" autocapitalize="characters" maxlength="6" dir="ltr" required aria-describedby="mk-otp-captcha-question" />
          </fieldset>
        <#else>
          <p class="mk-otp-message mk-otp-error" role="alert">${msg('captchaServiceUnavailable')}</p>
        </#if>
      </#if>

      <button tabindex="2" class="btn btn-primary mk-btn-primary btn-block btn-lg" name="action" value="verify" type="submit" data-loading-label="در حال بررسی…" <#if (otpSecondsRemaining!0) lte 0 || ((captchaRequired?? && captchaRequired) && !(captchaAvailable?? && captchaAvailable))>disabled</#if>>تأیید و ورود</button>

      <div class="mk-otp-actions">
        <span class="mk-otp-meta" data-otp-seconds="${otpCooldownRemaining!0}" style="margin:0">
          <span>ارسال مجدد</span>
          <span data-cooldown-countdown>۰:۰۰</span>
        </span>
        <button tabindex="3" class="mk-link-button mk-otp-resend" name="action" value="resend" type="submit" data-otp-cooldown="${otpCooldownRemaining!0}" data-captcha-blocked="<#if (captchaRequired?? && captchaRequired) && !(captchaAvailable?? && captchaAvailable)>true<#else>false</#if>" data-loading-label="در حال ارسال…" <#if (otpCooldownRemaining!0) gt 0 || ((captchaRequired?? && captchaRequired) && !(captchaAvailable?? && captchaAvailable))>disabled</#if>>ارسال مجدد کد</button>
      </div>
    </form>

    <form id="kc-captcha-refresh-form" action="${url.loginAction}" method="post" hidden>
      <input type="hidden" name="action" value="captchaRefresh" />
      <input type="hidden" name="captchaRefresh" value="1" />
    </form>

    <div class="mk-otp-actions">
      <form action="${url.loginAction}" method="post">
        <input type="hidden" name="action" value="returnToLogin" />
        <input type="hidden" name="loginMode" value="sms" />
        <button tabindex="4" class="mk-link-button" type="submit">اصلاح شماره موبایل</button>
      </form>
      <form action="${url.loginAction}" method="post">
        <input type="hidden" name="action" value="returnToLogin" />
        <input type="hidden" name="loginMode" value="password" />
        <button tabindex="5" class="mk-link-button" type="submit">بازگشت به ورود با رمز عبور</button>
      </form>
    </div>
    <script src="${url.resourcesPath}/js/login.js" defer></script>
  </#if>
</@layout.registrationLayout>
