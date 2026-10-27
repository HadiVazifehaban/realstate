<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=!messagesPerField.existsError('username','password') displayInfo=realm.password && realm.registrationAllowed && !registrationDisabled??; section>
<#if section = "header">
  <div class="mk-brand">
    <img class="mk-logo" src="${url.resourcesPath}/img/logo.png" alt="شکارچی" width="88" height="88" draggable="false" />
    <div class="mk-title">سامانه هوشمند املاک شکارچی</div>
    <p class="mk-subtitle">ورود امن به کارتابل تخصصی املاک</p>
    <span class="mk-secure-badge"><i class="fa fa-lock" aria-hidden="true"></i>ارتباط امن و ثبت رویدادهای ورود</span>
  </div>
<#elseif section = "form">
  <#if unifiedLogin?? && unifiedLogin>
    <div class="mk-login-tabs" role="tablist" aria-label="روش ورود">
      <button type="button" class="mk-login-tab" id="mk-tab-password" role="tab" aria-controls="mk-panel-password" data-login-tab="password">ورود با رمز عبور</button>
      <button type="button" class="mk-login-tab" id="mk-tab-sms" role="tab" aria-controls="mk-panel-sms" data-login-tab="sms">ورود با پیامک</button>
    </div>
    <#if !(smsDeliveryConfigured?? && smsDeliveryConfigured)><p class="mk-sms-unavailable" role="status">ورود با پیامک فعال است، اما سرویس ارسال پیامک هنوز پیکربندی نشده است. پس از ثبت شماره، OTP معتبر برای ورود لازم است.</p></#if>
    <input type="hidden" id="mk-initial-login-mode" value="${loginMode!'password'}" />
    <section id="mk-panel-password" role="tabpanel" aria-labelledby="mk-tab-password" data-login-panel="password">
      <form id="kc-form-login" action="${url.loginAction}" method="post" novalidate data-submit-once>
        <input type="hidden" name="loginMode" value="password" />
        <div class="form-group">
          <label for="username" class="pf-c-form__label pf-c-form__label-text">نام کاربری یا شماره موبایل</label>
          <input id="username" class="pf-c-form-control mk-input" name="username" value="${(login.username)!''}" type="text" autocomplete="username" dir="ltr" />
        </div>
        <div class="form-group">
          <label for="password" class="pf-c-form__label pf-c-form__label-text">${msg('password')}</label>
          <div class="mk-password-field">
            <input id="password" class="pf-c-form-control mk-input" name="password" type="password" autocomplete="current-password" dir="ltr" />
            <button class="mk-pw-toggle" type="button" id="mk-toggle-password" data-show-label="${msg('showPassword')}" data-hide-label="${msg('hidePassword')}" aria-controls="password" aria-pressed="false" aria-label="${msg('showPassword')}">${msg('showPassword')}</button>
          </div>
          <#if realm.resetPasswordAllowed><div class="mk-form-link"><a href="${url.loginResetCredentialsUrl}">${msg('doForgotPassword')}</a></div></#if>
        </div>
        <#if captchaAvailable?? && captchaAvailable>
          <fieldset class="mk-captcha" aria-describedby="mk-captcha-question-password">
            <legend class="mk-captcha-title">تأیید انسانی</legend>
            <span class="mk-captcha-sr-only" id="mk-captcha-question-password">${captchaQuestion!''}</span>
            <div class="mk-captcha-challenge"><img class="mk-captcha-image" src="${captchaImage!''}" alt="${captchaQuestion!''}" width="240" height="76" /><button class="mk-captcha-refresh" type="submit" form="kc-captcha-refresh-form" aria-label="تولید تصویر کپچای تازه" title="تصویر تازه"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 7v5h-5M4 17v-5h5"/><path d="M5.5 9a7 7 0 0 1 11.6-2L20 12M4 12l2.9 5a7 7 0 0 0 11.6-2"/></svg></button></div>
            <label for="captchaAnswerPassword" class="pf-c-form__label pf-c-form__label-text">حروف تصویر را وارد کنید</label>
            <input id="captchaAnswerPassword" class="pf-c-form-control mk-input" name="captchaAnswer" type="text" inputmode="text" autocomplete="off" autocapitalize="characters" maxlength="6" dir="ltr" required aria-describedby="mk-captcha-question-password" />
          </fieldset>
        </#if>
        <input type="hidden" name="credentialId" <#if auth.selectedCredential?has_content>value="${auth.selectedCredential}"</#if>/>
        <input class="btn btn-primary mk-btn-primary btn-block" name="login" id="kc-login" type="submit" value="${msg('doLogIn')}" data-loading-label="در حال ورود…" <#if (captchaRequired?? && captchaRequired) && !(captchaAvailable?? && captchaAvailable)>disabled</#if> />
      </form>
    </section>
    <section id="mk-panel-sms" role="tabpanel" aria-labelledby="mk-tab-sms" data-login-panel="sms" hidden>
      <p class="mk-subtitle" id="mk-recovery-message" hidden>برای ورود به حساب خود، شماره موبایل ثبت‌شده را وارد کنید تا کد تأیید برای شما ارسال شود.</p>
      <form id="mk-form-sms" action="${url.loginAction}" method="post" data-submit-once>
        <input type="hidden" name="action" value="submitPhone" />
        <input type="hidden" name="loginMode" value="sms" />
        <div class="form-group">
          <label for="phone" class="pf-c-form__label pf-c-form__label-text">شماره موبایل</label>
          <input id="phone" class="pf-c-form-control mk-input" name="phone" value="${phone!''}" type="tel" inputmode="numeric" autocomplete="tel" dir="ltr" placeholder="09123456789" aria-describedby="mk-phone-help" required />
          <p id="mk-phone-help" class="mk-field-note">شماره ۱۱ رقمی ایران را با ارقام فارسی یا انگلیسی وارد کنید.</p>
        </div>
        <#if captchaAvailable?? && captchaAvailable>
          <fieldset class="mk-captcha" aria-describedby="mk-captcha-question-sms">
            <legend class="mk-captcha-title">تأیید انسانی</legend>
            <span class="mk-captcha-sr-only" id="mk-captcha-question-sms">${captchaQuestion!''}</span>
            <div class="mk-captcha-challenge"><img class="mk-captcha-image" src="${captchaImage!''}" alt="${captchaQuestion!''}" width="240" height="76" /><button class="mk-captcha-refresh" type="submit" form="kc-captcha-refresh-form" aria-label="تولید تصویر کپچای تازه" title="تصویر تازه"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 7v5h-5M4 17v-5h5"/><path d="M5.5 9a7 7 0 0 1 11.6-2L20 12M4 12l2.9 5a7 7 0 0 0 11.6-2"/></svg></button></div>
            <label for="captchaAnswerSms" class="pf-c-form__label pf-c-form__label-text">حروف تصویر را وارد کنید</label>
            <input id="captchaAnswerSms" class="pf-c-form-control mk-input" name="captchaAnswer" type="text" inputmode="text" autocomplete="off" autocapitalize="characters" maxlength="6" dir="ltr" required aria-describedby="mk-captcha-question-sms" />
          </fieldset>
        </#if>
        <button class="btn btn-primary mk-btn-primary btn-block" type="submit" data-loading-label="در حال ثبت درخواست…" <#if (captchaRequired?? && captchaRequired) && !(captchaAvailable?? && captchaAvailable)>disabled</#if>>ارسال کد تأیید</button>
      </form>
      <div class="mk-form-link mk-form-link--center"><button type="button" class="mk-link-button" data-login-tab="password">بازگشت به ورود با رمز عبور</button></div>
    </section>
    <form id="kc-captcha-refresh-form" action="${url.loginAction}" method="post" hidden>
      <input type="hidden" name="action" value="captchaRefresh" />
      <input type="hidden" name="captchaRefresh" value="1" />
      <input type="hidden" name="username" id="mk-captcha-refresh-username" value="${(login.username)!''}" />
      <input type="hidden" name="phone" value="" />
      <input type="hidden" name="loginMode" value="password" />
    </form>
    <#if captchaRequired?? && captchaRequired && !(captchaAvailable?? && captchaAvailable)><p class="mk-sms-unavailable" role="alert">سرویس کپچا موقتاً در دسترس نیست؛ برای حفظ امنیت ورود، تلاش دوباره بعداً امکان‌پذیر است.</p></#if>
  <#else>
  <#if realm.password>
    <form id="kc-form-login" onsubmit="login.disabled = true; return true;" action="${url.loginAction}" method="post" novalidate>
      <#if !usernameHidden??>
        <div class="form-group">
          <label for="username" class="pf-c-form__label pf-c-form__label-text">شماره موبایل یا ایمیل</label>
          <input id="username" class="pf-c-form-control mk-input" name="username" value="${(login.username!'')}" type="text" autofocus autocomplete="username" dir="ltr" aria-invalid="<#if messagesPerField.existsError('username','password')>true</#if>" />
          <#if messagesPerField.existsError('username','password')><span class="mk-error" aria-live="polite">${kcSanitize(messagesPerField.getFirstError('username','password'))?no_esc}</span></#if>
        </div>
      </#if>
      <div class="form-group">
        <label for="password" class="pf-c-form__label pf-c-form__label-text">${msg('password')}</label>
        <div class="mk-password-field">
          <input id="password" class="pf-c-form-control mk-input" name="password" type="password" autocomplete="current-password" dir="ltr" />
          <button class="mk-pw-toggle" type="button" id="mk-toggle-password" data-show-label="${msg('showPassword')}" data-hide-label="${msg('hidePassword')}" aria-controls="password" aria-pressed="false" aria-label="${msg('showPassword')}">${msg('showPassword')}</button>
        </div>
      </div>
      <#if captchaAvailable?? && captchaAvailable>
        <fieldset class="mk-captcha" aria-describedby="mk-captcha-question">
          <legend class="mk-captcha-title">تأیید انسانی</legend>
          <span class="mk-captcha-sr-only" id="mk-captcha-question">${captchaQuestion!''}</span>
          <div class="mk-captcha-challenge"><img class="mk-captcha-image" src="${captchaImage!''}" alt="${captchaQuestion!''}" width="240" height="76" /><button class="mk-captcha-refresh" type="submit" form="kc-captcha-refresh-form" aria-label="تولید تصویر کپچای تازه" title="تصویر تازه"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 7v5h-5M4 17v-5h5"/><path d="M5.5 9a7 7 0 0 1 11.6-2L20 12M4 12l2.9 5a7 7 0 0 0 11.6-2"/></svg></button></div>
          <label for="captchaAnswer" class="pf-c-form__label pf-c-form__label-text">حروف تصویر را وارد کنید</label>
          <input id="captchaAnswer" class="pf-c-form-control mk-input" name="captchaAnswer" type="text" inputmode="text" autocomplete="off" autocapitalize="characters" maxlength="6" dir="ltr" aria-required="true" aria-describedby="mk-captcha-question" />
        </fieldset>
      </#if>
      <#if realm.resetPasswordAllowed><div class="mk-form-link"><a href="${url.loginResetCredentialsUrl}">${msg('doForgotPassword')}</a></div></#if>
      <input type="hidden" name="credentialId" <#if auth.selectedCredential?has_content>value="${auth.selectedCredential}"</#if>/>
      <input class="btn btn-primary mk-btn-primary btn-block" name="login" id="kc-login" type="submit" value="${msg('doLogIn')}" <#if (captchaRequired?? && captchaRequired) && !(captchaAvailable?? && captchaAvailable)>disabled</#if> />
    </form>
    <#if captchaAvailable?? && captchaAvailable>
      <form id="kc-captcha-refresh-form" action="${url.loginAction}" method="post" hidden><input type="hidden" name="captchaRefresh" value="1" /></form>
    </#if>
  </#if>
  </#if>
  <script src="${url.resourcesPath}/js/login.js" defer></script>
<#elseif section = "info">
  <#if realm.registrationAllowed && !registrationDisabled??>
    <div class="mk-professional-gateway"><div class="mk-gateway-divider"></div><a class="mk-gateway-link" href="${url.registrationUrl}">ایجاد حساب کاربری و ثبت‌نام حرفه‌ای</a></div>
  </#if>
<#elseif section = "socialProviders">
</#if>
</@layout.registrationLayout>
