<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=false; section>
  <#if section = "header">
    ${kcSanitize(msg("errorTitle"))?no_esc}
  <#elseif section = "form">
    <div id="kc-error-message" role="alert">
      <p class="instruction">${kcSanitize(message.summary)?no_esc}</p>
      <#if !skipLink?? && client?? && client.baseUrl?has_content>
        <p>${msg("shekarchiRestartLoginHelp")}</p>
        <p><a id="backToApplication" class="btn btn-primary mk-btn-primary btn-block" href="${client.baseUrl}">${msg("shekarchiRestartLogin")}</a></p>
      </#if>
    </div>
  </#if>
</@layout.registrationLayout>