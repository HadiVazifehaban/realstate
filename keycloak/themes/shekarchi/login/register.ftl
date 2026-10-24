<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=true displayRequiredFields=true; section>
<#if section = "header">
  <div class="mk-brand">
    <img class="mk-logo" src="${url.resourcesPath}/img/logo.png" alt="شکارچی" width="72" height="72" draggable="false" />
    <div class="mk-title">عضویت در شبکه شکارچی</div>
    <p class="mk-subtitle">نوع حساب و اطلاعات هویتی خود را ثبت کنید</p>
  </div>
<#elseif section = "form">
  <form id="kc-register-form" action="${url.registrationAction}" method="post">
    <div class="form-group">
      <label>نوع حساب کاربری</label>
      <div class="mk-role-tabs">
        <label class="mk-role-option"><input type="radio" name="user.attributes.account_type" value="standard" checked /><span>متقاضی</span></label>
        <label class="mk-role-option"><input type="radio" name="user.attributes.account_type" value="agent" /><span>مشاور</span></label>
        <label class="mk-role-option"><input type="radio" name="user.attributes.account_type" value="agency" /><span>مدیر دفتر</span></label>
      </div>
      <p class="mk-field-note">انتخاب مشاور یا مدیر دفتر فقط درخواست دسترسی است و پس از بررسی مدیر سامانه فعال می‌شود.</p>
    </div>

    <div class="mk-field-grid">
      <div class="form-group"><label for="firstName">نام</label><input id="firstName" class="mk-input" name="firstName" value="${(register.formData.firstName!'')}" required /></div>
      <div class="form-group"><label for="lastName">نام خانوادگی</label><input id="lastName" class="mk-input" name="lastName" value="${(register.formData.lastName!'')}" required /></div>
    </div>
    <div class="form-group"><label for="username">شماره موبایل</label><input id="username" class="mk-input" name="username" type="tel" inputmode="numeric" autocomplete="tel" dir="ltr" placeholder="09xxxxxxxxx" value="${(register.formData.username!'')}" required /></div>
    <div class="form-group"><label for="email">ایمیل</label><input id="email" class="mk-input" name="email" type="email" autocomplete="email" dir="ltr" value="${(register.formData.email!'')}" required /></div>

    <div id="mk-professional-fields" class="mk-professional-fields" hidden>
      <div class="form-group"><label for="nationalCode">کد ملی</label><input id="nationalCode" class="mk-input" name="user.attributes.national_code" inputmode="numeric" dir="ltr" maxlength="10" pattern="[0-9۰-۹]{10}" /></div>
      <div class="form-group"><label for="licenseNumber">شماره پروانه یا شناسه صنفی</label><input id="licenseNumber" class="mk-input" name="user.attributes.license_number" dir="ltr" maxlength="64" /></div>
      <div class="form-group"><label for="agencyRef">نام یا شناسه دفتر همکار</label><input id="agencyRef" class="mk-input" name="user.attributes.agency_ref" maxlength="128" /></div>
      <div class="form-group"><label for="serviceArea">محدوده فعالیت</label><input id="serviceArea" class="mk-input" name="user.attributes.service_area" maxlength="128" placeholder="مثال: منطقه ۱ تهران" /></div>
    </div>

    <div class="form-group"><label for="password">کلمه عبور</label><input id="password" class="mk-input" name="password" type="password" autocomplete="new-password" dir="ltr" required /></div>
    <div class="form-group"><label for="password-confirm">تکرار کلمه عبور</label><input id="password-confirm" class="mk-input" name="password-confirm" type="password" autocomplete="new-password" dir="ltr" required /></div>
    <input class="btn btn-primary mk-btn-primary btn-block" type="submit" value="ثبت درخواست عضویت" />
    <div class="mk-form-link mk-form-link--center"><a href="${url.loginUrl}">قبلاً ثبت‌نام کرده‌اید؟ ورود</a></div>
  </form>
  <script>
    (function () {
      var box = document.getElementById('mk-professional-fields');
      var choices = document.querySelectorAll('input[name="user.attributes.account_type"]');
      function sync() {
        var selected = document.querySelector('input[name="user.attributes.account_type"]:checked');
        box.hidden = !selected || selected.value === 'standard';
      }
      choices.forEach(function (choice) { choice.addEventListener('change', sync); });
      sync();
    })();
  </script>
</#if>
</@layout.registrationLayout>
