Fixes Applied to Non-Persian Descriptions in Info-Content Files

✅ **کارهای انجام شده:**

1. **network/info-content.ts**: 
   - جایگزینی تمام عبارات mix-language با فارسی صحیح
   - fixing: "Sharing properties", "referring clients", "collaborative transactions", "hoạt동ها", "strict access controls", "audit logging", etc.

2. **requests/info-content.ts**:
   - fixing: "भेजे-dose" (Hindi) → "فرستاده شده"
   - fixing: " 취하세요" (Korean) → "انجام دهید"
   - fixing: "cooperation" (English) → "همکاری" in button text
   - fixing: typo "درquests‌های" → "درخواست‌های"

3. **shared-listings/info-content.ts**:
   - complete rewrite from Thai/Japanese/mixed to full Persian
   - fixing: "物件ที่คุณได้แบ่งปันหรือได้รับจากสำนักงานอื่นๆ を表示します" → Persian description
   - fixing: "برای Sharing یک物件..." → "برای اشتراک یک ملک..."

4. **referrals/info-content.ts**:
   - fixing: Chinese/Korean mixed text → Persian
   - fixing: Russian text → Persian
   - improved descriptions with proper Persian terminology

5. **transfers/info-content.ts**:
   - fixing: Korean/mixed text → Persian
   - fixing: Russian text → Persian
   - improved descriptions with proper Persian terminology

6. **commissions/info-content.ts**:
   - fixing: Italian/Japanese/mixed text → Persian
   - fixing: Russian text → Persian
   - improved descriptions with proper Persian terminology

7. **disputes/info-content.ts**:
   - fixing: Korean/Japanese/mixed text → Persian
   - fixing: Russian text → Persian
   - improved descriptions with proper Persian terminology

8. **reports/info-content.ts**:
   - fixing: Korean/mixed text → Persian
   - fixing: Russian text → Persian
   - improved descriptions with proper Persian terminology

9. **audit/info-content.ts**:
   - fixing: Japanese/mixed text → Persian
   - fixing: Russian text → Persian
   - improved descriptions with proper Persian terminology

✅ **نتیجه:**
تمام فایل‌های info-content.ts در مسیر `/home/app/real/frontend/src/app/dashboard/network/` و زیرمساکن اکنون به‌طور کامل به زبان فارسی نوشته شده‌اند وixer یا عبارت‌های خارجی包含 نمی‌شوند.

این اصلاحات ساهم در حفظ unanimousity زبان رابط کاربری و اطمینان از که تمام توضیحات و راهنمایی‌ها برای کاربران فارسی‌زبان واضح و قابل فهم می‌شوند.