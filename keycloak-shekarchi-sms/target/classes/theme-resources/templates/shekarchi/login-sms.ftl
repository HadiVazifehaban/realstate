<#import "template.ftl" as layout>
<@layout.registrationLayout; section>
    <#if section = "header">
        <div class="mk-brand">
            <img class="mk-logo" src="${url.resourcesPath}/img/logo.png" alt="شکارچی" width="88" height="88" draggable="false" />
            <div class="mk-title">ورود با کد یکبارمصرف</div>
            <p class="mk-subtitle">شماره موبایل خود را وارد کنید</p>
        </div>
    <#elseif section = "form">
        <form id="kc-sms-form" action="${url.loginAction}" method="post" novalidate>
            <input type="hidden" name="action" value="submitPhone"/>
            <div class="form-group">
                <label for="phone" class="pf-c-form__label pf-c-form__label-text">شماره موبایل</label>
                <input tabindex="1" id="phone" class="pf-c-form-control mk-input" name="phone" type="text" dir="ltr" autocomplete="tel" placeholder="09xxxxxxxxx" autofocus />
            </div>
            <div id="kc-form-buttons" class="form-group">
                <input tabindex="2" class="btn btn-primary mk-btn-primary btn-block btn-lg" name="submit" type="submit" value="ارسال کد" />
            </div>
        </form>
        <div style="text-align:center; margin-top:12px;">
            <a href="${url.loginUrl}">بازگشت به صفحه ورود</a>
        </div>
    </#if>
</@layout.registrationLayout>
