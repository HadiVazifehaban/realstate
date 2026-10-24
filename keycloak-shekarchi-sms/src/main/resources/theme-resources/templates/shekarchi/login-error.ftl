<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=false; section>
    <#if section = "header">
        <div class="mk-brand">
            <div class="mk-title">خطا در احراز هویت</div>
        </div>
    <#elseif section = "form">
        <#if message??>
            <div class="alert alert-error">${message.summary}</div>
        </#if>
        <div style="text-align:center; margin-top:12px;">
            <a href="${url.loginUrl}">بازگشت به صفحه ورود</a>
        </div>
    </#if>
</@layout.registrationLayout>
