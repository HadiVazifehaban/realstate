<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=true; section>
<#if section = "header">
  <div class="mk-brand"><img class="mk-logo" src="${url.resourcesPath}/img/logo.png" alt="شکارچی" width="72" height="72" /><div class="mk-title">ورود با پیامک</div><p class="mk-subtitle">کد ورود فقط به شماره تأییدشده ارسال می‌شود</p></div>
<#elseif section = "form">
  <form action="${url.loginAction}" method="post">
    <input type="hidden" name="action" value="submitPhone" />
    <div class="form-group"><label for="phone">شماره موبایل</label><input id="phone" class="mk-input" name="phone" type="tel" inputmode="numeric" autocomplete="tel" dir="ltr" placeholder="09xxxxxxxxx" autofocus required /></div>
    <input class="btn btn-primary mk-btn-primary btn-block" type="submit" value="ارسال کد یکبارمصرف" />
  </form>
  <div class="mk-form-link mk-form-link--center"><a href="${url.loginUrl}">بازگشت به ورود</a></div>
</#if>
</@layout.registrationLayout>
