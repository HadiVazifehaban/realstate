#!/usr/bin/env python3
"""
اسکریپت برای افزودن توضیحات فارسی به نقاط پایانی API.
این اسکریپت الگوی کلی برای افزودن توضیحات فارسی با حفظ عبارات انگلیسی ایجاد می‌کند.
"""

import os
import re
from pathlib import Path

# دیکشنری اصطلاحات برای افزودن به نقاط پایانی
TERM_TRANSLATIONS = {
    "create": "ایجاد",
    "update": "به‌روزرسانی",
    "delete": "حذف",
    "list": "لیست",
    "get": "دریافت",
    "register": "ثبت",
    "submit": "ارسال",
    "verify": "تایید",
    "validate": "اعتبارسنجی",
    "authenticate": "احراز هویت",
    "authorize": "مجوزدهی",
    "search": "جستجو",
    "filter": "فیلتر",
    "sort": "مرتب‌سازی",
    "paginate": "صفحه‌بندی",
    "export": "خروجی",
    "import": "وارد کردن",
    "sync": "همگام‌سازی",
    "backup": "پشتیبان‌گیری",
    "restore": "بازیابی",
    "users": "کاربران",
    "properties": "املاک",
    "crm": "مدیریت ارتباط با مشتریان",
    "gis": "سیستم اطلاعات جغرافیایی",
    "network": "شبکه",
    "license": "مجوز",
    "scraper": "جمع‌آوری‌کننده داده",
    "preferences": "ترجیحات",
    "health": "سلامت",
    "auth": "احراز هویت",
    "matching": "تطبیق",
}

# الگوهای مختلف برای شناسایی نقاط پایانی
ROUTE_PATTERNS = [
    r'@router\.(get|post|patch|put|delete)\s*\(\s*["\']([^"\']+)["\']',
    r'@router\.(get|post|patch|put|delete)\s*\([^)]*summary\s*=\s*["\']([^"\']+)["\']',
]

def add_persian_to_summary(summary: str) -> str:
    """افزودن ترجمه فارسی به summary انگلیسی."""
    # اگر از قبل دارای ترجمه فارسی است، تغییر نده
    if " - " in summary and any(char in summary for char in "ابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهی"):
        return summary
    
    # ترجمه کلمات کلیدی
    translated = summary
    for eng, per in TERM_TRANSLATIONS.items():
        if eng.lower() in translated.lower():
            # جایگزینی هوشمندانه
            translated = re.sub(
                rf'\b{eng}\b', 
                f'{eng} ({per})', 
                translated, 
                flags=re.IGNORECASE
            )
    
    # اگر هیچ ترجمه‌ای اضافه نشده، ترجمه کلی اضافه کن
    if translated == summary:
        # پیدا کردن کلمه کلیدی اصلی
        main_word = None
        for eng in TERM_TRANSLATIONS:
            if eng.lower() in summary.lower():
                main_word = eng
                break
        
        if main_word:
            per = TERM_TRANSLATIONS[main_word]
            translated = f"{summary} - {per}"
        else:
            translated = f"{summary} - فارسی"
    
    return translated

def process_file(filepath: Path):
    """پردازش یک فایل endpoints و افزودن توضیحات فارسی."""
    print(f"Processing: {filepath}")
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # پیدا کردن تمام نقاط پایانی
        endpoints = []
        for pattern in ROUTE_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if len(match) == 2:
                    method, route_or_summary = match
                    endpoints.append((method, route_or_summary))
        
        if not endpoints:
            print(f"  No endpoints found in {filepath.name}")
            return
        
        # پیدا کردن و به‌روزرسانی توابع endpoint
        function_pattern = r'async def (\w+)\([^)]*\):'
        functions = re.findall(function_pattern, content)
        
        # به‌روزرسانی توضیحات docstring
        updated_content = content
        
        # الگو برای پیدا کردن docstring
        docstring_pattern = r'(async def \w+\([^)]*\):\s*\n\s*"""[^"]*""")'
        
        for func_name in functions:
            # پیدا کردن docstring فعلی
            func_pattern = rf'(async def {func_name}\(.*?\):\s*\n\s*"""[^"]*""")'
            match = re.search(func_pattern, updated_content, re.DOTALL)
            
            if match:
                docstring = match.group(1)
                
                # اگر docstring فقط انگلیسی دارد، فارسی اضافه کن
                if '"""' in docstring and not any(char in docstring for char in "ابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهی"):
                    # اضافه کردن توضیحات فارسی استاندارد
                    persian_doc = (
                        '\n    '
                        '**فارسی**: این نقطه پایانی برای مدیریت عملیات مرتبط است.\n    '
                        'توضیحات فارسی کامل در این بخش اضافه می‌شود.\n    '
                    )
                    
                    new_docstring = docstring.replace('"""', f'"""{persian_doc}')
                    updated_content = updated_content.replace(docstring, new_docstring)
        
        # به‌روزرسانی summary در decorator
        summary_pattern = r'summary\s*=\s*["\']([^"\']+)["\']'
        
        def replace_summary(match):
            old_summary = match.group(1)
            new_summary = add_persian_to_summary(old_summary)
            return f'summary="{new_summary}"'
        
        updated_content = re.sub(summary_pattern, replace_summary, updated_content)
        
        # ذخیره فایل اگر تغییری ایجاد شده باشد
        if updated_content != content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            print(f"  Updated {len(endpoints)} endpoints in {filepath.name}")
        else:
            print(f"  No changes needed for {filepath.name}")
            
    except Exception as e:
        print(f"  Error processing {filepath}: {e}")

def main():
    """تابع اصلی اجرای اسکریپت."""
    endpoints_dir = Path("/home/app/real/app/api/v1/endpoints")
    
    if not endpoints_dir.exists():
        print(f"Directory not found: {endpoints_dir}")
        return
    
    # پردازش تمام فایل‌های endpoints
    for filepath in endpoints_dir.glob("*.py"):
        if filepath.name != "__init__.py":
            process_file(filepath)
    
    print("\nProcessing completed!")

if __name__ == "__main__":
    main()