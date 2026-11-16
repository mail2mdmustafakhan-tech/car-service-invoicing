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
    "nav.estimates": ("Estimates", "عروض الأسعار"),
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
    "dash.new_estimate": ("New estimate", "عرض سعر جديد"),
    "dash.estimates_waiting": ("Estimates awaiting a decision", "عروض بانتظار الرد"),
    "dash.open_estimates": ("Open estimates", "عروض مفتوحة"),
    "dash.tax_vs_plain": ("Tax / plain", "ضريبية / عادية"),
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
    "inv.doc_type": ("Invoice type", "نوع الفاتورة"),
    "inv.doc_tax": ("Tax invoice (with VAT)", "فاتورة ضريبية (شاملة الضريبة)"),
    "inv.doc_plain": ("Plain invoice (no VAT)", "فاتورة عادية (بدون ضريبة)"),
    "inv.plain_invoice": ("INVOICE", "فاتورة"),
    "inv.doc_type_hint": (
        "A tax invoice charges VAT and prints the tax-invoice wording. "
        "A plain invoice is a simple bill with no VAT line. Both are recorded here "
        "and both appear in your reports.",
        "الفاتورة الضريبية تحتسب ضريبة القيمة المضافة وتُطبع بصيغة الفاتورة الضريبية. "
        "الفاتورة العادية فاتورة بسيطة بدون سطر ضريبة. كلاهما مسجل هنا ويظهر في التقارير.",
    ),

    # -- Customer attachments ----------------------------------------------
    "att.title": ("Documents", "المستندات"),
    "att.add": ("Attach a document", "إرفاق مستند"),
    "att.none": ("No documents attached.", "لا توجد مستندات مرفقة."),
    "att.hint": (
        "Scans of older invoices and paperwork, so everything for this customer "
        "is in one place. PDF, JPEG or PNG, up to 10 MB each.",
        "صور الفواتير والمستندات القديمة، ليكون كل ما يخص العميل في مكان واحد. "
        "صيغة PDF أو JPEG أو PNG، وبحد أقصى ١٠ ميجابايت لكل ملف.",
    ),
    "att.file": ("File", "الملف"),
    "att.kind": ("Type", "النوع"),
    "att.kind_invoice": ("Old invoice", "فاتورة قديمة"),
    "att.kind_document": ("Document", "مستند"),
    "att.kind_photo": ("Photo", "صورة"),
    "att.kind_other": ("Other", "أخرى"),
    "att.description": ("Description", "الوصف"),
    "att.date": ("Date on the document", "تاريخ المستند"),
    "att.size": ("Size", "الحجم"),
    "att.uploaded": ("Added", "تاريخ الإضافة"),
    "att.view": ("View", "عرض"),
    "att.download": ("Download", "تحميل"),

    # -- Importing customers -----------------------------------------------
    "imp.title": ("Import customers", "استيراد العملاء"),
    "imp.hint": (
        "Upload an Excel or CSV file of your existing customers. "
        "Nothing is saved until you have seen what it will do.",
        "ارفع ملف Excel أو CSV يحتوي على عملائك الحاليين. "
        "لن يُحفظ شيء قبل أن ترى ما سيتم تنفيذه.",
    ),
    "imp.choose": ("Choose a file", "اختر ملفاً"),
    "imp.upload": ("Upload and preview", "رفع ومعاينة"),
    "imp.template": ("Download the template", "تحميل النموذج"),
    "imp.template_hint": (
        "Not sure of the column headings? Start from the template.",
        "غير متأكد من عناوين الأعمدة؟ ابدأ من النموذج.",
    ),
    "imp.preview": ("Preview", "معاينة"),
    "imp.will_import": ("Will be added", "سيتم إضافتهم"),
    "imp.will_skip": ("Will be skipped", "سيتم تجاهلهم"),
    "imp.total_rows": ("Rows in the file", "عدد الصفوف في الملف"),
    "imp.line": ("Row", "الصف"),
    "imp.note": ("Reason", "السبب"),
    "imp.unmapped": (
        "Columns that were not recognised and will be ignored",
        "أعمدة غير معروفة وسيتم تجاهلها",
    ),
    "imp.confirm": ("Import these customers", "استيراد هؤلاء العملاء"),
    "imp.cancel": ("Cancel", "إلغاء"),
    "imp.nothing": (
        "Nothing in this file would be added. Every row is already on file or has no name.",
        "لا يوجد في هذا الملف ما يمكن إضافته. كل الصفوف موجودة مسبقاً أو بدون اسم.",
    ),

    # -- Estimates ---------------------------------------------------------
    "est.title": ("Estimates", "عروض الأسعار"),
    "est.one": ("Estimate", "عرض سعر"),
    "est.doc_title": ("ESTIMATE", "عرض سعر"),
    "est.new": ("New estimate", "عرض سعر جديد"),
    "est.edit": ("Edit estimate", "تعديل عرض السعر"),
    "est.details": ("Estimate details", "بيانات عرض السعر"),
    "est.number": ("Estimate no.", "رقم عرض السعر"),
    "est.date": ("Date", "التاريخ"),
    "est.valid_until": ("Valid until", "صالح حتى"),
    "est.validity_note": (
        "After this date the prices are no longer guaranteed.",
        "بعد هذا التاريخ لم تعد الأسعار مضمونة.",
    ),
    "est.expired": ("Expired", "منتهي الصلاحية"),
    "est.none": ("No estimates yet.", "لا توجد عروض أسعار بعد."),
    "est.search_hint": (
        "Search by number, customer or plate",
        "ابحث بالرقم أو العميل أو اللوحة",
    ),
    "est.mark_sent": ("Mark as sent", "تسجيل الإرسال"),
    "est.approve": ("Mark approved", "اعتماد العرض"),
    "est.decline": ("Mark declined", "تسجيل الرفض"),
    "est.reopen": ("Back to draft", "إرجاع إلى مسودة"),
    "est.approved_by": ("Approved by", "تمت الموافقة من"),
    "est.approved_by_hint": (
        "Who at the customer agreed to it. Optional, but useful later.",
        "من وافق عليه لدى العميل. اختياري، لكنه مفيد لاحقاً.",
    ),
    "est.approved_on": ("Approved on", "تاريخ الموافقة"),
    "est.sent_on": ("Sent on", "تاريخ الإرسال"),
    "est.to_invoice": ("Create invoice", "إنشاء فاتورة"),
    "est.invoiced_as": ("Invoiced as", "صدرت الفاتورة برقم"),
    "est.from_estimate": ("From estimate", "من عرض السعر"),
    "est.not_approved_yet": (
        "Mark the estimate approved once the customer agrees, then it can be invoiced.",
        "قم باعتماد العرض بعد موافقة العميل، عندها يمكن إصدار الفاتورة.",
    ),
    "est.send": ("Send to customer", "إرسال للعميل"),
    "est.whatsapp": ("Send on WhatsApp", "إرسال عبر واتساب"),
    "est.sms": ("Send by SMS", "إرسال رسالة نصية"),
    "est.copy_message": ("Copy message", "نسخ الرسالة"),
    "est.copied": ("Copied", "تم النسخ"),
    "est.message": ("Message", "الرسالة"),
    "est.no_phone": (
        "This customer has no phone number on file.",
        "لا يوجد رقم هاتف مسجل لهذا العميل.",
    ),

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
    # Estimate statuses
    "status.sent": ("Sent", "مُرسل"),
    "status.approved": ("Approved", "معتمد"),
    "status.declined": ("Declined", "مرفوض"),
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
    "set.logo": ("Logo", "الشعار"),
    "set.logo_hint": (
        "Printed on contracts and invoices. PNG, JPEG, GIF or WebP, under 1 MB. "
        "A square image with a transparent or white background works best.",
        "يُطبع على العقود والفواتير. صيغة PNG أو JPEG أو GIF أو WebP وبحجم أقل من ١ ميجابايت. "
        "يُفضل صورة مربعة بخلفية شفافة أو بيضاء.",
    ),
    "set.logo_choose": ("Choose an image", "اختر صورة"),
    "set.logo_upload": ("Upload logo", "رفع الشعار"),
    "set.logo_replace": ("Replace logo", "استبدال الشعار"),
    "set.logo_remove": ("Remove logo", "إزالة الشعار"),
    "set.logo_none": ("No logo set.", "لم يتم تعيين شعار."),
    "set.logo_saved": ("Logo saved.", "تم حفظ الشعار."),
    "set.estimates": ("Estimates", "عروض الأسعار"),
    "set.estimate_prefix": ("Estimate number prefix", "بادئة رقم عرض السعر"),
    "set.next_estimate_seq": ("Next estimate number", "رقم عرض السعر القادم"),
    "set.validity_days": ("Estimates valid for (days)", "مدة صلاحية العرض (أيام)"),
    "set.validity_hint": (
        "Used to fill in the valid-until date on a new estimate. Set 0 for no expiry.",
        "تُستخدم لتعبئة تاريخ انتهاء الصلاحية في العرض الجديد. اضبطها على 0 لعدم انتهاء الصلاحية.",
    ),
    "set.messaging": ("WhatsApp & SMS", "واتساب والرسائل النصية"),
    "set.country_code": ("Country dialling code", "رمز الدولة"),
    "set.country_code_hint": (
        "Used to turn a local number such as 0551234567 into the international "
        "form WhatsApp needs. 966 is Saudi Arabia.",
        "يُستخدم لتحويل رقم محلي مثل 0551234567 إلى الصيغة الدولية التي يحتاجها واتساب. "
        "966 هو رمز السعودية.",
    ),
    "set.message_en": ("Message template (English)", "نص الرسالة بالإنجليزية"),
    "set.message_ar": ("Message template (Arabic)", "نص الرسالة بالعربية"),
    "set.message_hint": (
        "Filled in when you send an estimate. Available placeholders: "
        "{customer} {business} {number} {total} {valid_until} {items}",
        "تُعبأ عند إرسال عرض السعر. العناصر المتاحة: "
        "{customer} {business} {number} {total} {valid_until} {items}",
    ),
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
    "msg.attached": ("Document attached.", "تم إرفاق المستند."),
    "msg.imported": ("Customers imported.", "تم استيراد العملاء."),
    "msg.nothing_imported": (
        "Nothing was imported — every row was already on file.",
        "لم يتم استيراد أي شيء — جميع الصفوف موجودة مسبقاً.",
    ),
    "msg.estimate_sent": ("Marked as sent.", "تم تسجيل الإرسال."),
    "msg.estimate_approved": (
        "Approved. You can now raise the invoice.",
        "تم الاعتماد. يمكنك الآن إصدار الفاتورة.",
    ),
    "msg.invoice_from_estimate": (
        "Draft invoice created from the estimate. Check it, then issue it.",
        "تم إنشاء مسودة فاتورة من عرض السعر. راجعها ثم قم بإصدارها.",
    ),
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
