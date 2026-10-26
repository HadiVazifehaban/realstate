<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=true displayRequiredFields=true; section>
<#if section = "header">
  <div class="mk-register-brand">
    <div class="mk-title">ثبت‌نام</div>
    <p class="mk-subtitle">برای دریافت کد تأیید، اطلاعات زیر را وارد کنید.</p>
  </div>
<#elseif section = "form">
  <form id="kc-register-form" action="${url.registrationAction}" method="post" data-submit-once>
    <div class="mk-register-field-grid">
      <div class="form-group">
        <label for="firstName">نام</label>
        <input id="firstName" class="mk-input" name="firstName" value="${(register.formData.firstName!'')}" autocomplete="given-name" maxlength="128" required />
      </div>
      <div class="form-group">
        <label for="lastName">نام خانوادگی</label>
        <input id="lastName" class="mk-input" name="lastName" value="${(register.formData.lastName!'')}" autocomplete="family-name" maxlength="128" required />
      </div>
    </div>
    <div class="form-group">
      <label for="username">نام کاربری</label>
      <input id="username" class="mk-input" name="username" autocomplete="username" autocapitalize="none" spellcheck="false" dir="ltr" minlength="3" maxlength="64" value="${(register.formData.username!'')}" required />
    </div>
    <div class="form-group">
      <label for="phone">شماره موبایل</label>
      <input id="phone" class="mk-input" name="user.attributes.phone" type="tel" inputmode="tel" autocomplete="tel" dir="ltr" placeholder="۰۹۱۲۳۴۵۶۷۸۹" maxlength="16" value="${(register.formData['user.attributes.phone']!'')}" required />
    </div>
    <input class="btn btn-primary mk-btn-primary btn-block" name="register" type="submit" value="ادامه و دریافت کد پیامک" data-loading-label="در حال ثبت اطلاعات…" />
    <div class="mk-form-link mk-form-link--center"><a href="${url.loginUrl}">حساب کاربری دارید؟ ورود</a></div>
  </form>
  <script src="${url.resourcesPath}/js/login.js" defer></script>
</#if>
</@layout.registrationLayout>