# Keycloak Login UI Changes - Shekarchi Theme
# Date: 2026-10-17
# Status: IMPLEMENTED

## Changes Applied

### 1. Auth Method Switcher (Tab Navigation)
**Location**: `keycloak/themes/shekarchi/login/login.ftl` (form section)
**CSS**: `keycloak/themes/shekarchi/login/resources/css/shekarchi.css`

**Features**:
- Added glassmorphic segmented control with two tabs
- Tab 1 (Default): "ورود / ثبت‌نام سریع با پیامک (OTP)" with mobile icon
- Tab 2: "ورود با رمز عبور" with lock icon
- Active tab: Semi-transparent rose-gold background with gold text
- Inactive tab: Transparent background with dimmed gray text
- Instant switching between forms without page reload
- Smooth fade-in animation for form transitions

### 2. OTP Form (Default State)
**Fields**:
1. **Mobile Number Input**
   - Label: "شماره موبایل"
   - Placeholder: "۰۹۱۲۳۴۵۶۷۸۹"
   - Attributes: `dir="ltr"`, `inputmode="tel"`, `type="tel"`
   - Auto-converts Persian numbers to English on input

2. **OTP Code Input**
   - Label: "کد تأیید یکبار مصرف"
   - Placeholder: "- - - - - -" (centered with spacing)
   - Attributes: `inputmode="numeric"`, `maxlength="6"`, `dir="ltr"`
   - Styling: Vazirmatn font, 18px, letter-spacing: 4px

3. **Send OTP Button**
   - Text: "دریافت کد" (before sending)
   - Timer: "ارسال مجدد پس از ۰۲:۰۰" (120-second countdown in Persian numerals)
   - Button disabled during countdown
   - Glassmorphic styling matching theme

4. **CTA Button**
   - Text: "ورود / ثبت‌نام سریع ←"
   - Same gold gradient styling as original

5. **Hidden Elements**
   - "فراموشی رمز عبور" link hidden in OTP mode
   - Footer note changed to: "کد ورود اختصاصی برای شماره شما ارسال خواهد شد و اطلاعات شما نزد شکارچی محفوظ است."

### 3. Password Form
**Fields**:
1. **Username/Email Input**
   - Label: "شماره موبایل یا ایمیل" (changed from "ایمیل یا نام کاربری")
   - Same LTR and autocomplete behavior

2. **Password Input**
   - Label: "رمز عبور"
   - Eye toggle for show/hide password (preserved)

3. **Forgot Password Link**
   - Visible in password mode (below password field)
   - Hidden in OTP mode

4. **CTA Button**
   - Text: "ورود" (unchanged)

5. **Footer Note**
   - Original: "رمز عبور شما فقط در این صفحهٔ امن وارد میشود..."
   - Only shown in password mode

### 4. Professional Onboarding Gateway
**Location**: Below CTA button, above security note

**Features**:
- Separator: Dashed gold line (`rgba(229, 168, 123, 0.3)`)
- Link button: "مشاور املاک، مدیر آژانس یا همکار تجاری هستید؟ ثبت‌نام تخصصی ←"
- Color: Rose-gold (`#e5a87b`)
- Icon: Building/badge icon
- Links to registration page (`register.html`)
- Flat button styling with hover effects

### 5. CSS Additions
**New Classes**:
- `.mk-auth-switcher` - Tab container
- `.mk-auth-tab` - Individual tab buttons
- `.mk-auth-tab--active` - Active tab state
- `.mk-auth-form` - Form containers (hidden by default)
- `.mk-auth-form--active` - Visible form state
- `.mk-otp-input-wrapper` - OTP input + button wrapper
- `.mk-otp-input` - OTP code input field
- `.mk-otp-send-btn` - Send OTP button
- `.mk-otp-send-btn.mk-timer-active` - Timer countdown state
- `.mk-professional-gateway` - Professional link section
- `.mk-gateway-divider` - Separator line
- `.mk-gateway-link` - Professional link button

**Animations**:
- `mk-fade-in` - Smooth form transition (0.25s ease)
- Tab hover effects with subtle lift
- Button hover with background shift and shadow

### 6. JavaScript Functionality
**Features**:
1. **Tab Switching**
   - Instant form toggle without page reload
   - Auto-focus on first input field when switching
   - Active/inactive state management

2. **OTP Timer**
   - 120-second countdown on button click
   - Persian numeral display (۰, ۱, ۲, ...)
   - Format: "ارسال مجدد پس از MM:SS"
   - Button disabled during countdown
   - Auto-enables after timer expires

3. **Number Conversion**
   - Auto-converts Persian numbers (۰-۹) to English (0-9) on input
   - Applied to both mobile and OTP code fields
   - Prevents backend validation issues

## Files Modified

1. `/home/app/real/keycloak/themes/shekarchi/login/login.ftl`
   - Added auth method switcher UI
   - Added OTP form with timer
   - Added password form (modified)
   - Added professional gateway link
   - Added JavaScript with `<#noparse>` directive

2. `/home/app/real/keycloak/themes/shekarchi/login/resources/css/shekarchi.css`
   - Added tab switcher styles (glassmorphic)
   - Added OTP input wrapper styles
   - Added timer button styles
   - Added professional gateway styles
   - Added fade-in animation

## Design Compliance

✅ **Preserved**:
- Card geometry and shadows
- Gold gradient CTA button
- Navy background (#060b13)
- Rose-gold color palette
- Logo and branding
- Border radius and focus rings
- Vazirmatn font family

✅ **Added**:
- Tab switcher (glassmorphic)
- OTP-specific UI elements
- Professional gateway section
- Persian numeral support
- Smooth animations

## Next Steps

1. **Backend Integration**
   - Connect OTP form to actual SMS sending API
   - Implement OTP validation endpoint
   - Set up `SHEKARCHI_OTP_HMAC_SECRET` environment variable

2. **Testing**
   - Test tab switching functionality
   - Test OTP timer countdown
   - Test Persian-to-English number conversion
   - Test professional gateway link routing
   - Test mobile responsiveness

3. **Deployment**
   - Build Java Keycloak theme module
   - Deploy to Keycloak server
   - Clear theme cache in Keycloak
   - Verify production rendering

## Notes

- JavaScript wrapped in `<#noparse>` to prevent FreeMarker parsing
- Timer currently simulates countdown - replace with actual API call
- Forms use same styling patterns as original Keycloak theme
- All changes are additive - no original functionality removed
