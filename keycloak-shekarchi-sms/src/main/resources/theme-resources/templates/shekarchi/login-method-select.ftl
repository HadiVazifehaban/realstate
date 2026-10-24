<#import "template.ftl" as layout>
<@layout.registrationLayout; section>
    <#if section = "header">
        <div class="mk-brand">
            <img class="mk-logo" src="${url.resourcesPath}/img/logo.png" alt="شکارچی" width="88" height="88" draggable="false" />
            <div class="mk-title">انتخاب روش ورود</div>
            <p class="mk-subtitle">لطفاً روش ورود مورد نظر خود را انتخاب کنید</p>
        </div>
    <#elseif section = "form">
        <div class="form-group">
            <a href="${url.loginUrl}?login_method=password" class="btn btn-primary mk-btn-primary btn-block btn-lg">ورود با رمز عبور</a>
        </div>
        <div class="form-group">
            <a href="${url.loginUrl}?login_method=sms" class="btn btn-block btn-lg" style="background:transparent; border:1px solid rgba(229,168,123,0.5); color:#f0efe9;">ورود با کد یکبارمصرف SMS</a>
        </div>
    </#if>
</@layout.registrationLayout>
