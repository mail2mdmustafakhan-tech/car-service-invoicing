"""English and Arabic text for the interface.

Every piece of visible text lives in the :data:`TRANSLATIONS` table below, one
line per phrase with both languages side by side. To fix a wording or add a
language you edit this one file -- you never go hunting through templates.

The chosen language is kept in a cookie, so it survives a restart and each
person on a shared machine keeps their own choice. Arabic also flips the whole
page to right-to-left; see :func:`direction`.

Numbers and dates stay in Western digits in both languages, which is what
Saudi business documents normally use.
"""

from __future__ import annotations

#: Languages offered in the switcher: code -> native name.
LANGUAGES: dict[str, str] = {"en": "English", "ar": "العربية"}

DEFAULT_LANGUAGE = "en"

#: key -> (English, Arabic)
TRANSLATIONS: dict[str, tuple[str, str]] = {
    # -- Application chrome ------------------------------------------------
    "app.name": ("Car Service Invoicing", "فواتير خدمة السيارات"),
    "nav.dashboard": ("Dashboard", "الرئيسية"),
    "nav.invoices": ("Invoices", "الفواتير"),
    "nav.customers": ("Customers", "العملاء"),
    "nav.vehicles": ("Vehicles", "المركبات"),
    "nav.contracts": ("Repair contracts", "عقود الإصلاح"),
    "nav.catalog": ("Services & Parts", "الخدمات وقطع الغيار"),
    "nav.settings": ("Settings", "الإعدادات"),
    "nav.language": ("Language", "اللغة"),

    # -- Shared actions ----------------------------------------------------
    "action.new": ("New", "جديد"),
    "action.save": ("Save", "حفظ"),
    "action.cancel": ("Cancel", "إلغاء"),
    "action.edit": ("Edit", "تعديل"),
    "action.delete": ("Delete", "حذف"),
    "action.search": ("Search", "بحث"),
    "action.clear": ("Clear", "مسح"),
    "action.back": ("Back", "رجوع"),
    "action.print": ("Print", "طباعة"),
    "action.download_pdf": ("Download PDF", "تحميل PDF"),
    "action.add": ("Add", "إضافة"),
    "action.view": ("View", "عرض"),
    "action.confirm_delete": (
        "Are you sure? This cannot be undone.",
        "هل أنت متأكد؟ لا يمكن التراجع عن هذا.",
    ),
    "action.filters": ("Filters", "تصفية"),
    "action.apply": ("Apply", "تطبيق"),

    # -- Dashboard ---------------------------------------------------------
    "dash.title": ("Dashboard", "الرئيسية"),
    "dash.this_month": ("Invoiced this month", "فواتير هذا الشهر"),
    "dash.vat_collected": ("VAT this month", "ضريبة هذا الشهر"),
    "dash.outstanding": ("Outstanding", "مبالغ مستحقة"),
    "dash.drafts": ("Draft invoices", "فواتير مسودة"),
    "dash.customers": ("Customers", "العملاء"),
    "dash.vehicles": ("Vehicles", "المركبات"),
    "dash.recent_invoices": ("Recent invoices", "أحدث الفواتير"),
    "dash.unpaid": ("Awaiting payment", "بانتظار السداد"),
    "dash.quick_new_invoice": ("New invoice", "فاتورة جديدة"),
    "dash.revenue_by_month": ("Revenue by month", "الإيرادات حسب الشهر"),
    "dash.in_workshop": ("Cars in the workshop", "السيارات في الورشة"),
    "dash.open_contracts": ("Open contracts", "عقود مفتوحة"),
    "dash.to_invoice": ("Ready to invoice", "جاهزة للفوترة"),
    "dash.new_contract": ("Book a car in", "إدخال سيارة"),
    "dash.nothing_yet": (
        "Nothing here yet. Start by adding a customer.",
        "لا يوجد شيء بعد. ابدأ بإضافة عميل.",
    ),
    "dash.invoices_count": ("invoices", "فاتورة"),

    # -- Customers ---------------------------------------------------------
    "cust.title": ("Customers", "العملاء"),
    "cust.new": ("New customer", "عميل جديد"),
    "cust.edit": ("Edit customer", "تعديل العميل"),
    "cust.name": ("Name", "الاسم"),
    "cust.name_ar": ("Name (Arabic)", "الاسم بالعربية"),
    "cust.phone": ("Phone", "الهاتف"),
    "cust.email": ("Email", "البريد الإلكتروني"),
    "cust.address": ("Address", "العنوان"),
    "cust.vat_number": ("VAT number", "الرقم الضريبي"),
    "cust.notes": ("Notes", "ملاحظات"),
    "cust.active": ("Active", "نشط"),
    "cust.inactive": ("Inactive", "غير نشط"),
    "cust.show_inactive": ("Show inactive", "إظهار غير النشطين"),
    "cust.vehicles": ("Vehicles", "المركبات"),
    "cust.balance": ("Balance due", "الرصيد المستحق"),
    "cust.none": ("No customers yet.", "لا يوجد عملاء بعد."),
    "cust.search_hint": ("Search by name or phone", "ابحث بالاسم أو الهاتف"),
    "cust.history": ("Invoice history", "سجل الفواتير"),

    # -- Vehicles ----------------------------------------------------------
    "veh.title": ("Vehicles", "المركبات"),
    "veh.new": ("New vehicle", "مركبة جديدة"),
    "veh.edit": ("Edit vehicle", "تعديل المركبة"),
    "veh.owner": ("Owner", "المالك"),
    "veh.plate": ("Plate number", "رقم اللوحة"),
    "veh.make": ("Make", "الماركة"),
    "veh.model": ("Model", "الطراز"),
    "veh.year": ("Year", "سنة الصنع"),
    "veh.vin": ("VIN / Chassis", "رقم الهيكل"),
    "veh.colour": ("Colour", "اللون"),
    "veh.odometer": ("Odometer (km)", "عداد المسافة (كم)"),
    "veh.notes": ("Notes", "ملاحظات"),
    "veh.none": ("No vehicles yet.", "لا توجد مركبات بعد."),
    "veh.search_hint": ("Search by plate, make or VIN", "ابحث باللوحة أو الماركة أو رقم الهيكل"),
    "veh.service_history": ("Service history", "سجل الصيانة"),

    # -- Catalogue ---------------------------------------------------------
    "cat.title": ("Services & Parts", "الخدمات وقطع الغيار"),
    "cat.new": ("New item", "بند جديد"),
    "cat.edit": ("Edit item", "تعديل البند"),
    "cat.code": ("Code", "الرمز"),
    "cat.name_en": ("Name (English)", "الاسم بالإنجليزية"),
    "cat.name_ar": ("Name (Arabic)", "الاسم بالعربية"),
    "cat.kind": ("Type", "النوع"),
    "cat.kind_service": ("Service", "خدمة"),
    "cat.kind_part": ("Part", "قطعة غيار"),
    "cat.unit": ("Unit", "الوحدة"),
    "cat.unit_price": ("Unit price", "سعر الوحدة"),
    "cat.none": ("No items yet.", "لا توجد بنود بعد."),
    "cat.hint": (
        "Items added here can be picked when writing an invoice.",
        "يمكن اختيار البنود المضافة هنا عند إنشاء الفاتورة.",
    ),
    "cat.unit_pcs": ("pcs", "حبة"),
    "cat.unit_hour": ("hour", "ساعة"),
    "cat.unit_litre": ("litre", "لتر"),
    "cat.unit_set": ("set", "طقم"),
    "cat.unit_km": ("km", "كم"),

    # -- Invoices ----------------------------------------------------------
    "inv.title": ("Invoices", "الفواتير"),
    "inv.details": ("Invoice details", "تفاصيل الفاتورة"),
    "inv.new": ("New invoice", "فاتورة جديدة"),
    "inv.edit": ("Edit invoice", "تعديل الفاتورة"),
    "inv.number": ("Invoice no.", "رقم الفاتورة"),
    "inv.tax_invoice": ("TAX INVOICE", "فاتورة ضريبية"),
    "inv.simplified": ("SIMPLIFIED TAX INVOICE", "فاتورة ضريبية مبسطة"),
    "inv.date": ("Date", "التاريخ"),
    "inv.due_date": ("Due date", "تاريخ الاستحقاق"),
    "inv.customer": ("Customer", "العميل"),
    "inv.vehicle": ("Vehicle", "المركبة"),
    "inv.odometer": ("Odometer", "عداد المسافة"),
    "inv.status": ("Status", "الحالة"),
    "inv.notes": ("Notes", "ملاحظات"),
    "inv.lines": ("Items", "البنود"),
    "inv.description": ("Description", "الوصف"),
    "inv.qty": ("Qty", "الكمية"),
    "inv.unit_price": ("Unit price", "سعر الوحدة"),
    "inv.line_total": ("Amount", "المبلغ"),
    "inv.subtotal": ("Subtotal", "المجموع"),
    "inv.discount": ("Discount", "الخصم"),
    "inv.taxable": ("Taxable amount", "المبلغ الخاضع للضريبة"),
    "inv.vat": ("VAT", "ضريبة القيمة المضافة"),
    "inv.total": ("Total", "الإجمالي"),
    "inv.paid": ("Paid", "المدفوع"),
    "inv.balance": ("Balance due", "المتبقي"),
    "inv.add_line": ("Add item", "إضافة بند"),
    "inv.remove_line": ("Remove", "حذف"),
    "inv.pick_catalog": ("Pick from catalogue", "اختر من القائمة"),
    "inv.pick_custom": ("Or type your own description", "أو اكتب وصفاً خاصاً"),
    "inv.none": ("No invoices yet.", "لا توجد فواتير بعد."),
    "inv.search_hint": (
        "Search by number, customer or plate",
        "ابحث بالرقم أو العميل أو اللوحة",
    ),
    "inv.no_vehicle": ("No vehicle", "بدون مركبة"),
    "inv.select_customer": ("Select a customer", "اختر عميلاً"),
    "inv.select_vehicle": ("Select a vehicle", "اختر مركبة"),
    "inv.mark_issued": ("Issue invoice", "إصدار الفاتورة"),
    "inv.mark_void": ("Void invoice", "إلغاء الفاتورة"),
    "inv.reopen_draft": ("Back to draft", "إرجاع إلى مسودة"),
    "inv.vat_rate": ("VAT rate %", "نسبة الضريبة %"),
    "inv.prices_include_vat": ("Prices include VAT", "الأسعار تشمل الضريبة"),
    "inv.draft_warning": (
        "This is a draft. Issue it to give the customer a final invoice.",
        "هذه مسودة. قم بإصدارها لإعطاء العميل فاتورة نهائية.",
    ),
    "inv.void_warning": ("This invoice is void.", "هذه الفاتورة ملغاة."),
    "inv.needs_line": ("Add at least one item.", "أضف بنداً واحداً على الأقل."),

    # -- Repair contracts --------------------------------------------------
    "con.title": ("Repair contracts", "عقود الإصلاح"),
    "con.one": ("Repair contract", "عقد إصلاح"),
    "con.doc_title": ("CAR REPAIR CONTRACT", "عقد اصلاح سيارة"),
    "con.new": ("New contract", "عقد جديد"),
    "con.edit": ("Edit contract", "تعديل العقد"),
    "con.details": ("Contract details", "بيانات العقد"),
    "con.number": ("Contract no.", "رقم العقد"),
    "con.date_in": ("Date car came in", "تاريخ إدخال السيارة الورشة"),
    "con.date_out": ("Expected collection date", "التاريخ المتوقع لإستلام السيارة"),
    "con.odometer": ("Odometer reading", "رقم عداد السيارة"),
    "con.car_code": ("Car code", "رمز السيارة"),
    "con.technician": ("Technician", "الميكانيكي"),
    "con.technician_sig": ("Technician signature", "توقيع الميكانيكي"),
    "con.repairs": ("Repairs requested", "الاصلاحات المطلوبة"),
    "con.repairs_requested": (
        "Repairs requested by owner of car",
        "الاصلاحات المطلوبة من قبل مالك السيارة",
    ),
    "con.expenses": ("Labour cost", "تكلفة الأجور"),
    "con.remarks": ("Technician's remarks", "ملاحظات الميكانيكي"),
    "con.remarks_full": (
        "Technician's remarks who checked",
        "ملاحظات الميكانيكي الذي قام بفحص السيارة",
    ),
    "con.add_repair": ("Add repair", "إضافة إصلاح"),
    "con.parts": ("Spare parts", "قطع الغيار"),
    "con.part_number": ("Part number", "رقم القطعة الأصلي"),
    "con.part_name": ("Type of spare", "مسمى القطعة"),
    "con.add_part": ("Add part", "إضافة قطعة"),
    "con.sourced": ("Source", "المصدر"),
    "con.sourced_own": ("Own stock", "من المخزون"),
    "con.sourced_agency": ("From agency", "تأمين من الوكالة"),
    "con.markup_hint": (
        "Agency parts carry a handling charge of",
        "القطع المؤمنة من الوكالة تخضع لرسوم تأمين قدرها",
    ),
    "con.damage_notes": ("Existing damage", "الأضرار الموجودة"),
    "con.damage_hint": (
        "Note any dents, scratches or missing items before work starts.",
        "سجّل أي خدوش أو انبعاجات أو أشياء ناقصة قبل بدء العمل.",
    ),
    "con.signed": ("Signed by customer", "موقّع من العميل"),
    "con.not_signed": ("Not signed", "غير موقّع"),
    "con.mark_signed": ("Mark as signed", "تسجيل التوقيع"),
    "con.mark_unsigned": ("Mark as not signed", "إلغاء التوقيع"),
    "con.signed_on": ("Signed on", "تاريخ التوقيع"),
    "con.labour_estimate": ("Labour", "الأجور"),
    "con.parts_estimate": ("Parts", "قطع الغيار"),
    "con.estimate_total": ("Estimated total", "الإجمالي التقديري"),
    "con.estimate_note": (
        "An estimate. Nothing is owed until an invoice is raised.",
        "هذا تقدير. لا يستحق أي مبلغ حتى تصدر الفاتورة.",
    ),
    "con.none": ("No contracts yet.", "لا توجد عقود بعد."),
    "con.no_parts": ("No parts recorded.", "لم تُسجل قطع غيار."),
    "con.search_hint": (
        "Search by contract number, customer or plate",
        "ابحث برقم العقد أو العميل أو اللوحة",
    ),
    "con.to_invoice": ("Create invoice", "إنشاء فاتورة"),
    "con.invoiced_as": ("Invoiced as", "صدرت الفاتورة برقم"),
    "con.from_contract": ("From contract", "من العقد"),
    "con.mark_completed": ("Mark work complete", "إنهاء العمل"),
    "con.reopen": ("Reopen", "إعادة فتح"),
    "con.cancel_job": ("Cancel contract", "إلغاء العقد"),
    "con.days_in": ("Days in workshop", "أيام في الورشة"),
    "con.notice": ("Important notice", "ملاحظة هامة"),
    "con.authorization": ("Customer authorization", "تفويض العميل"),
    "con.name": ("Name", "الاسم"),
    "con.signature": ("Signature", "التوقيع"),
    "con.owner": ("Owner of car", "اسم مالك السيارة"),
    "con.car_type": ("Type of car", "نوع السيارة"),
    "con.locked": (
        "This contract has been invoiced and can no longer be edited.",
        "صدرت فاتورة لهذا العقد ولم يعد بالإمكان تعديله.",
    ),

    # -- Invoice statuses --------------------------------------------------
    "status.draft": ("Draft", "مسودة"),
    "status.issued": ("Issued", "مُصدرة"),
    "status.void": ("Void", "ملغاة"),
    "status.unpaid": ("Unpaid", "غير مدفوعة"),
    "status.partially_paid": ("Part paid", "مدفوعة جزئياً"),
    "status.paid": ("Paid", "مدفوعة"),
    "status.all": ("All", "الكل"),
    # Repair contract statuses
    "status.open": ("In workshop", "في الورشة"),
    "status.completed": ("Work complete", "اكتمل العمل"),
    "status.invoiced": ("Invoiced", "صدرت فاتورتها"),
    "status.cancelled": ("Cancelled", "ملغي"),

    # -- Payments ----------------------------------------------------------
    "pay.title": ("Payments", "المدفوعات"),
    "pay.record": ("Record payment", "تسجيل دفعة"),
    "pay.amount": ("Amount", "المبلغ"),
    "pay.date": ("Date", "التاريخ"),
    "pay.method": ("Method", "طريقة الدفع"),
    "pay.reference": ("Reference", "المرجع"),
    "pay.notes": ("Notes", "ملاحظات"),
    "pay.none": ("No payments recorded.", "لا توجد مدفوعات مسجلة."),
    "pay.last": ("Last payment", "آخر دفعة"),
    "pay.method_cash": ("Cash", "نقداً"),
    "pay.method_card": ("Card", "بطاقة"),
    "pay.method_transfer": ("Bank transfer", "تحويل بنكي"),
    "pay.method_cheque": ("Cheque", "شيك"),
    "pay.method_other": ("Other", "أخرى"),
    "pay.pay_full": ("Pay full balance", "سداد كامل المتبقي"),
    "pay.exceeds_balance": (
        "That is more than the outstanding balance.",
        "هذا المبلغ أكبر من الرصيد المستحق.",
    ),

    # -- Settings ----------------------------------------------------------
    "set.title": ("Settings", "الإعدادات"),
    "set.business": ("Business details", "بيانات المنشأة"),
    "set.business_name_en": ("Business name (English)", "اسم المنشأة بالإنجليزية"),
    "set.business_name_ar": ("Business name (Arabic)", "اسم المنشأة بالعربية"),
    "set.vat_number": ("VAT registration number", "الرقم الضريبي"),
    "set.cr_number": ("Commercial registration no.", "رقم السجل التجاري"),
    "set.address_en": ("Address (English)", "العنوان بالإنجليزية"),
    "set.address_ar": ("Address (Arabic)", "العنوان بالعربية"),
    "set.phone": ("Phone", "الهاتف"),
    "set.email": ("Email", "البريد الإلكتروني"),
    "set.tax": ("Tax & currency", "الضريبة والعملة"),
    "set.vat_rate": ("VAT rate (%)", "نسبة الضريبة (%)"),
    "set.prices_include_vat": (
        "Prices I enter already include VAT",
        "الأسعار التي أدخلها تشمل الضريبة",
    ),
    "set.currency": ("Currency code", "رمز العملة"),
    "set.contract": ("Repair contract", "عقد الإصلاح"),
    "set.tagline_en": ("Services line (English)", "سطر الخدمات بالإنجليزية"),
    "set.tagline_ar": ("Services line (Arabic)", "سطر الخدمات بالعربية"),
    "set.tagline_hint": (
        "Printed under the business name, e.g. Mechanical - Electrical - Denting - Painting",
        "يُطبع تحت اسم المنشأة، مثل: ميكانيكا - كهرباء - سمكرة - بوية",
    ),
    "set.terms_en": ("Important notice (English)", "الملاحظة الهامة بالإنجليزية"),
    "set.terms_ar": ("Important notice (Arabic)", "الملاحظة الهامة بالعربية"),
    "set.terms_hint": (
        "One point per line. They are numbered automatically on the printed contract.",
        "نقطة واحدة في كل سطر. يتم ترقيمها تلقائياً في العقد المطبوع.",
    ),
    "set.authorization_en": ("Authorization text (English)", "نص التفويض بالإنجليزية"),
    "set.authorization_ar": ("Authorization text (Arabic)", "نص التفويض بالعربية"),
    "set.authorization_hint": (
        "The paragraph the customer signs. Write {business} where the business name should appear.",
        "الفقرة التي يوقّع عليها العميل. اكتب {business} في موضع اسم المنشأة.",
    ),
    "set.contract_prefix": ("Contract number prefix", "بادئة رقم العقد"),
    "set.next_contract_seq": ("Next contract number", "رقم العقد القادم"),
    "set.parts_markup": ("Agency parts handling (%)", "رسوم تأمين قطع الوكالة (%)"),
    "set.parts_markup_hint": (
        "Shown as a guide when pricing a part sourced from an agency. Never applied automatically.",
        "تظهر كدليل عند تسعير قطعة مؤمنة من الوكالة. لا تُطبق تلقائياً.",
    ),
    "set.numbering": ("Invoice numbering", "ترقيم الفواتير"),
    "set.invoice_prefix": ("Number prefix", "بادئة الرقم"),
    "set.next_seq": ("Next invoice number", "رقم الفاتورة القادم"),
    "set.appearance": ("Defaults", "الإعدادات الافتراضية"),
    "set.default_language": ("Default language", "اللغة الافتراضية"),
    "set.footer_en": ("Invoice footer (English)", "تذييل الفاتورة بالإنجليزية"),
    "set.footer_ar": ("Invoice footer (Arabic)", "تذييل الفاتورة بالعربية"),
    "set.saved": ("Settings saved.", "تم حفظ الإعدادات."),
    "set.backup": ("Backup", "النسخ الاحتياطي"),
    "set.backup_hint": (
        "Download a copy of the whole database. Keep these somewhere safe.",
        "قم بتحميل نسخة من قاعدة البيانات بالكامل واحفظها في مكان آمن.",
    ),
    "set.download_backup": ("Download backup", "تحميل نسخة احتياطية"),

    # -- Messages ----------------------------------------------------------
    "msg.saved": ("Saved.", "تم الحفظ."),
    "msg.deleted": ("Deleted.", "تم الحذف."),
    "msg.created": ("Created.", "تم الإنشاء."),
    "msg.not_found": ("Not found.", "غير موجود."),
    "msg.error": ("Something went wrong.", "حدث خطأ ما."),
    "msg.required": ("This field is required.", "هذا الحقل مطلوب."),
    "msg.invoice_issued": ("Invoice issued.", "تم إصدار الفاتورة."),
    "msg.payment_recorded": ("Payment recorded.", "تم تسجيل الدفعة."),
    "msg.invoice_from_contract": (
        "Draft invoice created from the contract. Check it, then issue it.",
        "تم إنشاء مسودة فاتورة من العقد. راجعها ثم قم بإصدارها.",
    ),
    "msg.no_results": ("No results.", "لا توجد نتائج."),
    "msg.first_run": (
        "Welcome. Start by filling in your business details in Settings.",
        "مرحباً. ابدأ بإدخال بيانات منشأتك في الإعدادات.",
    ),
}


def t(key: str, lang: str = DEFAULT_LANGUAGE) -> str:
    """Look up a phrase.

    An unknown key returns the key itself rather than raising, so a typo in a
    template shows up visibly on the page instead of crashing it. An Arabic
    phrase that has not been filled in falls back to the English.
    """
    pair = TRANSLATIONS.get(key)
    if pair is None:
        return key
    english, arabic = pair
    if lang == "ar":
        return arabic or english
    return english


def normalise(lang: str | None) -> str:
    """Reduce any incoming value to a language code this app actually has."""
    if lang and lang.lower()[:2] in LANGUAGES:
        return lang.lower()[:2]
    return DEFAULT_LANGUAGE


def direction(lang: str) -> str:
    """``rtl`` for Arabic, ``ltr`` otherwise -- goes straight into ``<html dir>``."""
    return "rtl" if lang == "ar" else "ltr"


def is_rtl(lang: str) -> bool:
    return direction(lang) == "rtl"


def localised(row: object, base: str, lang: str) -> str:
    """Pick the Arabic or English variant of a database field.

    Customers and catalogue items store both a Latin and an Arabic name. This
    returns the one matching the current language and quietly falls back to
    the other when one side is blank -- so a half-translated catalogue still
    reads correctly rather than showing gaps.

    ``base`` is the English column name, e.g. ``localised(item, "name_en", "ar")``
    looks at ``name_ar`` first and ``name_en`` second.
    """
    try:
        english = row[base] or ""  # type: ignore[index]
    except (KeyError, IndexError, TypeError):
        english = ""

    arabic_col = base.replace("_en", "_ar") if base.endswith("_en") else f"{base}_ar"
    try:
        arabic = row[arabic_col] or ""  # type: ignore[index]
    except (KeyError, IndexError, TypeError):
        arabic = ""

    if lang == "ar":
        return arabic or english
    return english or arabic
