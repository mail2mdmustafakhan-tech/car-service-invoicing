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
    "nav.issues": ("Known issues", "الأعطال المعروفة"),
    "iss.title": ("Known issues", "الأعطال المعروفة"),
    "iss.intro": (
        "Faults that come through the door often enough to be worth naming. "
        "Attach one to a job instead of describing it again. Everything here "
        "is yours to correct, retire or add to.",
        "الأعطال التي تتكرر بما يكفي لتسميتها. أرفق العطل بالعمل بدل وصفه كل مرة. "
        "كل ما هنا قابل للتعديل أو الإيقاف أو الإضافة عليه.",
    ),
    "iss.new": ("Add a fault", "إضافة عطل"),
    "iss.edit": ("Edit fault", "تعديل العطل"),
    "iss.none": ("Nothing listed yet.", "لا توجد أعطال مدرجة بعد."),
    "iss.all_makes": ("All makes", "كل الماركات"),
    "iss.show_retired": ("Include retired", "إظهار الموقوفة"),
    "iss.make": ("Make", "الماركة"),
    "iss.model": ("Model", "الموديل"),
    "iss.engine": ("Engine", "المحرك"),
    "iss.year_from": ("From year", "من سنة"),
    "iss.year_to": ("To year", "إلى سنة"),
    "iss.fault": ("Fault", "العطل"),
    "iss.which_car": ("Which cars", "أي السيارات"),
    "iss.the_fault": ("The fault", "العطل"),
    "iss.title_en": ("Title (English)", "العنوان (إنجليزي)"),
    "iss.title_ar": ("Title (Arabic)", "العنوان (عربي)"),
    "iss.symptoms_en": ("Symptoms (English)", "الأعراض (إنجليزي)"),
    "iss.symptoms_ar": ("Symptoms (Arabic)", "الأعراض (عربي)"),
    "iss.check_en": ("What to check first (English)", "ما يُفحص أولاً (إنجليزي)"),
    "iss.check_ar": ("What to check first (Arabic)", "ما يُفحص أولاً (عربي)"),
    "iss.check_hint": (
        "The one thing worth doing before the car is stripped.",
        "الخطوة التي تستحق القيام بها قبل فك السيارة.",
    ),
    "iss.check": ("Check", "الفحص"),
    "iss.severity": ("Severity", "الخطورة"),
    "iss.sev_low": ("Low", "منخفضة"),
    "iss.sev_medium": ("Medium", "متوسطة"),
    "iss.sev_high": ("High", "عالية"),
    "iss.seen": ("Seen", "تكرر"),
    "iss.notes": ("Notes", "ملاحظات"),
    "iss.in_use": ("In use", "قيد الاستخدام"),
    "iss.attach": ("Record a known fault", "تسجيل عطل معروف"),
    "iss.attached": ("Known faults on this job", "الأعطال المعروفة في هذا العمل"),
    "iss.outcome": ("Finding", "النتيجة"),
    "iss.out_suspected": ("Suspected", "مشتبه به"),
    "iss.out_confirmed": ("Confirmed", "مؤكد"),
    "iss.out_ruled_out": ("Ruled out", "مستبعد"),
    "iss.out_repaired": ("Repaired", "تم إصلاحه"),
    "iss.show_on_print": ("Show on the printed contract", "إظهاره في العقد المطبوع"),
    "iss.note": ("Note", "ملاحظة"),
    "iss.none_attached": ("No known faults recorded on this job.", "لم تُسجل أعطال معروفة في هذا العمل."),
    "nav.catalog": ("Services & Parts", "الخدمات وقطع الغيار"),
    "nav.settings": ("Settings", "الإعدادات"),
    "nav.language": ("Language", "اللغة"),
    "nav.theme": ("Light or dark", "فاتح أو داكن"),

    # Settings -> the dropdown lists
    "lists.title": ("Dropdown lists", "قوائم الاختيار"),
    "lists.intro": (
        "The choices offered by every dropdown in the application. Switch one "
        "off to stop offering it; documents that already use it keep their "
        "wording.",
        "الخيارات التي تظهر في قوائم البرنامج. أوقف أي خيار لإخفائه من القوائم، "
        "وتبقى المستندات السابقة كما هي.",
    ),
    "lists.back": ("Back to settings", "رجوع للإعدادات"),
    "lists.sources": ("Part sources", "مصادر القطع"),
    "lists.manufacturers": ("Manufacturers", "الشركات المصنعة"),
    "lists.units": ("Units", "الوحدات"),
    "lists.payment_methods": ("Payment methods", "طرق الدفع"),
    "lists.customer_types": ("Customer types", "أنواع العملاء"),
    "lists.marques": ("Marques serviced", "الماركات التي نخدمها"),
    "lists.stored": ("Stored as", "القيمة المخزنة"),
    "lists.stored_hint": (
        "What is written into the record. It cannot be changed later, because "
        "documents already saved refer to it.",
        "ما يُسجَّل في البيانات. لا يمكن تغييره لاحقاً لأن المستندات المحفوظة تشير إليه.",
    ),
    "lists.label_en": ("English", "الإنجليزية"),
    "lists.label_ar": ("Arabic", "العربية"),
    "lists.order": ("Order", "الترتيب"),
    "lists.shown": ("Offered", "يظهر"),
    "lists.builtin": ("Built in", "أساسي"),
    "lists.add": ("Add a value", "إضافة قيمة"),
    "lists.yes": ("Yes", "نعم"),
    "lists.no": ("No", "لا"),

    # The count line under each list heading, and the dashboard tiles.
    # Plural nouns: these always follow a number, so the singular form is
    # never needed -- "1 invoices" reads badly but is only ever seen for one
    # second of a workshop's first day, and getting Arabic duals and plurals
    # right for both languages is not worth that second.
    "count.invoices": ("invoices", "فواتير"),
    "count.estimates": ("estimates", "عروض سعر"),
    "count.contracts": ("repair contracts", "عقود إصلاح"),
    "count.inspections": ("inspections", "فحوصات"),
    "count.customers": ("customers", "عملاء"),
    "count.vehicles": ("vehicles", "مركبات"),
    "count.catalog": ("services and parts", "خدمات وقطع"),
    "count.issues": ("known faults", "أعطال معروفة"),
    "count.active": ("active", "نشط"),
    "count.retired": ("retired", "موقوف"),
    "dash.whats_on": ("What is on the books", "ما لدينا"),
    "foot.marques": ("We service", "نخدم"),
    "dash.make_share": ("Share of the fleet", "نسبة كل ماركة"),
    "dash.make_share_hint": (
        "Every car on file, by make. Makes past the sixth are grouped.",
        "كل السيارات المسجلة حسب الماركة. ما بعد السادسة يُجمع معاً.",
    ),
    "dash.other": ("Other makes", "ماركات أخرى"),
    "dash.no_model_note": (
        "more cars have no model recorded, so they are not counted above.",
        "سيارة أخرى بدون موديل مسجل، لذلك لم تُحتسب أعلاه.",
    ),
    "dash.see_flagged": ("See the warning list", "عرض قائمة التنبيهات"),
    "dash.by_age": ("Cars by age", "السيارات حسب سنة الصنع"),
    "dash.by_age_hint": (
        "Model year, in five-year bands. Cars with no year recorded are left out.",
        "سنة الصنع ضمن فترات خمس سنوات. السيارات بدون سنة مسجلة غير محتسبة.",
    ),
    "dash.by_colour": ("Cars by colour", "السيارات حسب اللون"),
    "dash.other_colours": ("Other colours", "ألوان أخرى"),
    "dash.filter_make": ("Show", "عرض"),
    "dash.all_makes": ("All makes", "كل الماركات"),
    "dash.showing_only": ("Showing", "المعروض"),
    "dash.odd_colours": (
        "cars have something other than a colour recorded there — usually a "
        "model code. Worth tidying up.",
        "سيارة مسجّل في خانة اللون شيء آخر، غالباً رمز الموديل. يُستحسن تصحيحها.",
    ),

    # Warnings on a customer's file. The wording is the point: these are
    # read at a counter with a customer standing there, so they say what to
    # do rather than describing a state.
    "alert.refuse": ("Do not accept", "لا تستقبل"),
    "alert.check": ("Ask before accepting", "راجع قبل الاستلام"),
    "alert.note": ("Note on file", "ملاحظة"),
    "alert.understood": ("Understood", "مفهوم"),
    "alert.set_on": ("Marked", "سُجّلت"),
    "alert.no_reason": ("No reason was recorded.", "لم يُسجَّل سبب."),
    "alert.title": ("Warning on this file", "تنبيه على الملف"),
    "alert.none": ("No warning", "بدون تنبيه"),
    "alert.reason": ("Reason", "السبب"),
    "alert.reason_hint": (
        "Shown to whoever books the car in. Say what to do, not just that "
        "something is wrong.",
        "تظهر لمن يستلم السيارة. اذكر ما يجب فعله، لا مجرد وجود مشكلة.",
    ),
    "alert.flagged": ("flagged customers", "عملاء بتنبيه"),
    "alert.flagged_title": ("Flagged customers", "العملاء المنبّه عليهم"),

    # Bringing a car register in from a spreadsheet.
    "reg.title": ("Import a car register", "استيراد سجل السيارات"),
    "reg.intro": (
        "A spreadsheet with one row per car: make, plate, chassis number, "
        "owner and mobile. Rows marked in red are read as warnings on the "
        "owner's file. Nothing is saved until you have looked at what it found.",
        "ملف فيه سطر لكل سيارة: النوع واللوحة والهيكل واسم المالك وجواله. "
        "الأسطر المظللة بالأحمر تُقرأ كتنبيهات على ملف المالك. لا يُحفظ شيء "
        "قبل أن تراجع النتيجة.",
    ),
    "reg.file": ("Spreadsheet", "الملف"),
    "reg.file_hint": (".xlsx, with a heading row", "صيغة xlsx مع سطر عناوين"),
    "reg.read": ("Read the file", "اقرأ الملف"),
    "reg.what_it_found": ("What it found", "ما تم العثور عليه"),
    "reg.rows": ("rows read", "سطر"),
    "reg.unnamed": ("with no name", "بدون اسم"),
    "reg.merged": ("merged", "مدمج"),
    "reg.skipped": ("left out", "مستبعد"),
    "reg.skipped_hint": ("no plate, or a repeat", "بدون لوحة أو مكرر"),
    "reg.makes": ("Makes found", "الماركات"),
    "reg.ignored": ("Columns not read", "أعمدة لم تُقرأ"),
    "reg.will_flag": ("Customers this will flag", "عملاء سيوضع عليهم تنبيه"),
    "reg.will_flag_hint": (
        "Read these before continuing. They come from the rows marked in "
        "red, and they are what the front desk will be shown.",
        "راجع هذه القائمة قبل المتابعة. مصدرها الأسطر الحمراء، وهي ما سيظهر "
        "عند الاستقبال.",
    ),
    "reg.left_out": ("Rows left out", "أسطر مستبعدة"),
    "reg.why": ("Why", "السبب"),
    "reg.line": ("Line", "السطر"),
    "reg.first_rows": ("The first few cars", "أول السيارات"),
    "reg.commit": ("Import it", "استيراد"),
    "reg.template": ("Download a blank template", "تنزيل نموذج فارغ"),

    # Colour and model written in each other's boxes.
    "tidy.title": ("Tidy up colour and model", "ترتيب اللون والموديل"),
    "tidy.intro": (
        "Some cars have the model written where the colour goes, or the "
        "colour where the model goes. Only the clear cases are listed: a "
        "value is moved when the box it is in cannot be right and the box "
        "it belongs in is empty, or when the two are plainly swapped. "
        "Nothing changes until you say so.",
        "بعض السيارات مسجَّل فيها الموديل مكان اللون أو العكس. تظهر هنا "
        "الحالات الواضحة فقط، ولا يتغير شيء حتى توافق.",
    ),
    "tidy.nothing": ("Nothing needs moving.", "لا يوجد ما يحتاج تعديلاً."),
    "tidy.cars": ("cars would change", "سيارة ستتغير"),
    "tidy.now": ("Recorded now", "المسجَّل الآن"),
    "tidy.after": ("Would become", "سيصبح"),
    "tidy.apply": ("Move them", "نفّذ التعديل"),
    "msg.nothing_to_do": ("Nothing needed changing.", "لا يوجد ما يحتاج تعديلاً."),
    "tidy.swapped": ("swapped round", "متبادلة"),
    "tidy.moved": ("moved across", "منقولة"),
    "alert.none_flagged": (
        "No customer carries a warning.",
        "لا يوجد عميل عليه تنبيه.",
    ),
    "nav.sections": ("Sections", "الأقسام"),

    # -- Shared actions ----------------------------------------------------
    "action.new": ("New", "جديد"),
    "action.save": ("Save", "حفظ"),
    "action.cancel": ("Cancel", "إلغاء"),
    "action.edit": ("Edit", "تعديل"),
    "action.delete": ("Delete", "حذف"),
    "action.search": ("Search", "بحث"),
    "action.clear": ("Clear", "مسح"),
    "action.back": ("Back", "رجوع"),

    # The pager under a list. "Showing 51-100 of 4,312" is the important one:
    # it is what distinguishes a page of fifty rows from a list of fifty rows.
    # The performance page. Under Settings, for the day something feels
    # wrong -- not on the dashboard, which is about the business.
    "perf.title": ("Performance", "\u0627\u0644\u0623\u062f\u0627\u0621"),
    "perf.lede": (
        "How the application is behaving on this computer. Here so that "
        "\u201cit has got slower\u201d can be answered rather than argued about.",
        "\u0623\u062f\u0627\u0621 \u0627\u0644\u062a\u0637\u0628\u064a\u0642 \u0639\u0644\u0649 \u0647\u0630\u0627 \u0627\u0644\u062c\u0647\u0627\u0632\u060c \u0644\u0645\u0639\u0631\u0641\u0629 \u0633\u0628\u0628 \u0623\u064a \u0628\u0637\u0621 \u0628\u062f\u0644 \u0627\u0644\u062a\u062e\u0645\u064a\u0646.",
    ),
    # Uptime, said in words. Four separate strings because Arabic does not
    # abbreviate these the way English does.
    "perf.up_new": ("just started", "بدأ الآن"),
    "perf.up_min": ("{n} min", "{n} دقيقة"),
    "perf.up_hour": ("{h}h {m}m", "{h} ساعة {m} دقيقة"),
    "perf.up_day": ("{d}d {h}h", "{d} يوم {h} ساعة"),
    "perf.since": ("Counting since", "\u0627\u0644\u0642\u064a\u0627\u0633 \u0645\u0646\u0630"),
    "perf.resets": (
        "These figures are kept in memory and start again when the "
        "application is restarted.",
        "\u062a\u064f\u062d\u0641\u0638 \u0647\u0630\u0647 \u0627\u0644\u0623\u0631\u0642\u0627\u0645 \u0641\u064a \u0627\u0644\u0630\u0627\u0643\u0631\u0629 \u0648\u062a\u0628\u062f\u0623 \u0645\u0646 \u062c\u062f\u064a\u062f \u0639\u0646\u062f \u0625\u0639\u0627\u062f\u0629 \u062a\u0634\u063a\u064a\u0644 \u0627\u0644\u062a\u0637\u0628\u064a\u0642.",
    ),
    "perf.requests": ("Pages served", "\u0627\u0644\u0635\u0641\u062d\u0627\u062a \u0627\u0644\u0645\u0642\u062f\u0645\u0629"),
    "perf.errors": ("Failed", "\u0623\u062e\u0637\u0627\u0621"),
    "perf.memory": ("Memory in use", "\u0627\u0644\u0630\u0627\u0643\u0631\u0629 \u0627\u0644\u0645\u0633\u062a\u062e\u062f\u0645\u0629"),
    "perf.database": ("Database", "\u0642\u0627\u0639\u062f\u0629 \u0627\u0644\u0628\u064a\u0627\u0646\u0627\u062a"),
    "perf.by_page": ("Each page", "\u0643\u0644 \u0635\u0641\u062d\u0629"),
    "perf.by_page_hint": (
        "Grouped by page rather than by address, so one invoice screen is "
        "one row and not five thousand. Ordered by total time spent, which "
        "is where tuning pays.",
        "\u0645\u062c\u0645\u0639\u0629 \u062d\u0633\u0628 \u0627\u0644\u0635\u0641\u062d\u0629 \u0644\u0627 \u062d\u0633\u0628 \u0627\u0644\u0639\u0646\u0648\u0627\u0646\u060c \u0648\u0645\u0631\u062a\u0628\u0629 \u062d\u0633\u0628 \u0625\u062c\u0645\u0627\u0644\u064a \u0627\u0644\u0648\u0642\u062a \u0627\u0644\u0645\u0633\u062a\u063a\u0631\u0642.",
    ),
    "perf.page": ("Page", "\u0627\u0644\u0635\u0641\u062d\u0629"),
    "perf.hits": ("Opened", "\u0645\u0631\u0627\u062a \u0627\u0644\u0641\u062a\u062d"),
    "perf.median": ("Typical", "\u0627\u0644\u0645\u0639\u062a\u0627\u062f"),
    "perf.p95": ("Slow runs", "\u0627\u0644\u0628\u0637\u064a\u0621"),
    "perf.worst": ("Worst", "\u0627\u0644\u0623\u0633\u0648\u0623"),
    "perf.queries": ("Queries", "\u0627\u0644\u0627\u0633\u062a\u0639\u0644\u0627\u0645\u0627\u062a"),
    "perf.share": ("Share of time", "\u062d\u0635\u0629 \u0627\u0644\u0648\u0642\u062a"),
    "perf.failed": ("failed", "\u0641\u0634\u0644"),
    "perf.ms_note": (
        "Times in milliseconds. \u201cTypical\u201d is the middle of recent "
        "visits; \u201cslow runs\u201d is the slowest one in twenty, which is "
        "what people actually notice. Under 100 is instant; over 500 is felt.",
        "\u0627\u0644\u0623\u0648\u0642\u0627\u062a \u0628\u0627\u0644\u0645\u0644\u064a \u062b\u0627\u0646\u064a\u0629. \u0623\u0642\u0644 \u0645\u0646 100 \u0641\u0648\u0631\u064a\u060c \u0648\u0623\u0643\u062b\u0631 \u0645\u0646 500 \u0645\u0644\u0645\u0648\u0633.",
    ),
    "perf.nothing_yet": ("Nothing measured yet.", "\u0644\u0627 \u064a\u0648\u062c\u062f \u0642\u064a\u0627\u0633 \u0628\u0639\u062f."),
    "perf.slowest": ("The slowest visits", "\u0623\u0628\u0637\u0623 \u0627\u0644\u0632\u064a\u0627\u0631\u0627\u062a"),
    "perf.slowest_hint": (
        "Individual ones, with the exact address. An average says a page is "
        "slow; one of these says which one, and what was on it.",
        "\u0632\u064a\u0627\u0631\u0627\u062a \u0645\u0641\u0631\u062f\u0629 \u0645\u0639 \u0627\u0644\u0639\u0646\u0648\u0627\u0646 \u0628\u0627\u0644\u0636\u0628\u0637.",
    ),
    "perf.when": ("When", "\u0627\u0644\u0648\u0642\u062a"),
    "perf.address": ("Address", "\u0627\u0644\u0639\u0646\u0648\u0627\u0646"),
    "perf.took": ("Took", "\u0627\u0633\u062a\u063a\u0631\u0642"),
    "perf.memory_over_time": ("Memory over time", "\u0627\u0644\u0630\u0627\u0643\u0631\u0629 \u0639\u0628\u0631 \u0627\u0644\u0648\u0642\u062a"),
    "perf.memory_started": ("Started at", "\u0628\u062f\u0623\u062a \u0639\u0646\u062f"),
    "perf.memory_now_is": ("now", "\u0648\u0627\u0644\u0622\u0646"),
    "perf.memory_hint": (
        "A reading every ten minutes. What matters is the shape, not the "
        "number: a line that climbs all day and never comes back down is a "
        "leak. Rising and falling is normal \u2014 building a report or an "
        "export is supposed to cost memory and then give it back.",
        "\u0642\u0631\u0627\u0621\u0629 \u0643\u0644 \u0639\u0634\u0631 \u062f\u0642\u0627\u0626\u0642. \u0627\u0644\u0645\u0647\u0645 \u0647\u0648 \u0627\u0644\u0634\u0643\u0644 \u0644\u0627 \u0627\u0644\u0631\u0642\u0645: "
        "\u0627\u0644\u062e\u0637 \u0627\u0644\u0630\u064a \u064a\u0631\u062a\u0641\u0639 \u0637\u0648\u0627\u0644 \u0627\u0644\u064a\u0648\u0645 \u0648\u0644\u0627 \u064a\u0639\u0648\u062f \u064a\u0639\u0646\u064a \u062a\u0633\u0631\u064a\u0628\u0627\u064b.",
    ),
    "perf.memory_wait": (
        "A reading is taken every ten minutes. Come back once the "
        "application has been open for a while.",
        "\u062a\u064f\u0624\u062e\u0630 \u0642\u0631\u0627\u0621\u0629 \u0643\u0644 \u0639\u0634\u0631 \u062f\u0642\u0627\u0626\u0642. \u0639\u062f \u0628\u0639\u062f \u0641\u062a\u0631\u0629 \u0645\u0646 \u0627\u0644\u062a\u0634\u063a\u064a\u0644.",
    ),
    "perf.storage": ("What is being stored", "\u0627\u0644\u0645\u0633\u0627\u062d\u0629 \u0627\u0644\u0645\u0633\u062a\u062e\u062f\u0645\u0629"),
    "perf.attachments": ("Scans and photos", "\u0627\u0644\u0645\u0631\u0641\u0642\u0627\u062a"),
    "perf.rows": ("Records", "\u0627\u0644\u0633\u062c\u0644\u0627\u062a"),
    "perf.table": ("Table", "\u0627\u0644\u062c\u062f\u0648\u0644"),
    "perf.row_count": ("Rows", "\u0639\u062f\u062f \u0627\u0644\u0635\u0641\u0648\u0641"),
    "perf.reset": ("Start counting again", "\u0627\u0628\u062f\u0623 \u0627\u0644\u0642\u064a\u0627\u0633 \u0645\u0646 \u062c\u062f\u064a\u062f"),
    "perf.reset_hint": (
        "Clears the figures above. Useful after a change, to see whether it "
        "helped without the old numbers dragging the average.",
        "\u064a\u0645\u0633\u062d \u0627\u0644\u0623\u0631\u0642\u0627\u0645 \u0623\u0639\u0644\u0627\u0647\u060c \u0644\u0645\u0639\u0631\u0641\u0629 \u0623\u062b\u0631 \u0623\u064a \u062a\u063a\u064a\u064a\u0631.",
    ),
    "perf.reset_done": ("Counting started again.", "\u0628\u062f\u0623 \u0627\u0644\u0642\u064a\u0627\u0633 \u0645\u0646 \u062c\u062f\u064a\u062f."),
    "pager.nav": ("Pages", "الصفحات"),
    "pager.showing": ("Showing", "المعروض"),
    "pager.of": ("of", "من"),
    "pager.page": ("Page", "صفحة"),
    "pager.previous": ("Previous", "السابق"),
    "pager.next": ("Next", "التالي"),
    "pager.first": ("First page", "الصفحة الأولى"),
    "pager.last": ("Last page", "الصفحة الأخيرة"),
    "pager.per_page": ("Per page", "لكل صفحة"),

    # The search box above a customer dropdown. The hint has to say plainly
    # that the list is not everybody, or somebody will conclude a customer
    # has been deleted when they are simply not in the recent fifty.
    "pick.search_customer": ("Search customers by name or phone\u2026",
                             "\u0627\u0628\u062d\u062b \u0628\u0627\u0644\u0627\u0633\u0645 \u0623\u0648 \u0631\u0642\u0645 \u0627\u0644\u062c\u0648\u0627\u0644\u2026"),
    # The automatic daily backup.
    "set.auto_backup": ("Automatic daily backup", "\u0646\u0633\u062e \u0627\u062d\u062a\u064a\u0627\u0637\u064a \u064a\u0648\u0645\u064a \u062a\u0644\u0642\u0627\u0626\u064a"),
    "set.auto_backup_hint": (
        "A backup is taken when this program starts, if the day does not "
        "already have one, and once an hour while it is open. The last "
        "fourteen days are kept, then one a month for a year.",
        "\u062a\u064f\u0624\u062e\u0630 \u0646\u0633\u062e\u0629 \u0639\u0646\u062f \u062a\u0634\u063a\u064a\u0644 \u0627\u0644\u0628\u0631\u0646\u0627\u0645\u062c \u0625\u0630\u0627 \u0644\u0645 \u062a\u0648\u062c\u062f \u0646\u0633\u062e\u0629 \u0644\u0647\u0630\u0627 \u0627\u0644\u064a\u0648\u0645\u060c "
        "\u0648\u0645\u0631\u0629 \u0643\u0644 \u0633\u0627\u0639\u0629 \u0623\u062b\u0646\u0627\u0621 \u0641\u062a\u062d\u0647. \u064a\u064f\u062d\u062a\u0641\u0638 \u0628\u0622\u062e\u0631 \u0623\u0631\u0628\u0639\u0629 \u0639\u0634\u0631 \u064a\u0648\u0645\u0627\u064b\u060c \u062b\u0645 \u0646\u0633\u062e\u0629 \u0634\u0647\u0631\u064a\u0629 \u0644\u0645\u062f\u0629 \u0633\u0646\u0629.",
    ),
    "set.backup_last": ("Last backup", "\u0622\u062e\u0631 \u0646\u0633\u062e\u0629"),
    "set.backup_today": ("taken today", "\u0623\u064f\u062e\u0630\u062a \u0627\u0644\u064a\u0648\u0645"),
    "set.backup_none_yet": ("None yet", "\u0644\u0627 \u062a\u0648\u062c\u062f \u0628\u0639\u062f"),
    "set.backup_kept": ("Backups kept", "\u0627\u0644\u0646\u0633\u062e \u0627\u0644\u0645\u062d\u0641\u0648\u0638\u0629"),
    "set.backup_folder": ("Folder", "\u0627\u0644\u0645\u062c\u0644\u062f"),
    "set.backup_now": ("Back up now", "\u0627\u0646\u0633\u062e \u0627\u0644\u0622\u0646"),
    "set.backup_done": ("Backup saved to the backups folder.",
                        "\u062a\u0645 \u062d\u0641\u0638 \u0627\u0644\u0646\u0633\u062e\u0629 \u0641\u064a \u0645\u062c\u0644\u062f \u0627\u0644\u0646\u0633\u062e \u0627\u0644\u0627\u062d\u062a\u064a\u0627\u0637\u064a\u0629."),
    "set.backup_stale": (
        "No backup has been taken for more than two days. If this program "
        "has not been opened, that is why \u2014 otherwise check the folder "
        "below is writable.",
        "\u0644\u0645 \u062a\u064f\u0624\u062e\u0630 \u0646\u0633\u062e\u0629 \u0645\u0646\u0630 \u0623\u0643\u062b\u0631 \u0645\u0646 \u064a\u0648\u0645\u064a\u0646. \u0625\u0646 \u0644\u0645 \u064a\u064f\u0641\u062a\u062d \u0627\u0644\u0628\u0631\u0646\u0627\u0645\u062c \u0641\u0647\u0630\u0627 \u0627\u0644\u0633\u0628\u0628\u060c "
        "\u0648\u0625\u0644\u0627 \u0641\u062a\u0623\u0643\u062f \u0645\u0646 \u0625\u0645\u0643\u0627\u0646\u064a\u0629 \u0627\u0644\u0643\u062a\u0627\u0628\u0629 \u0641\u064a \u0627\u0644\u0645\u062c\u0644\u062f \u0623\u062f\u0646\u0627\u0647.",
    ),
    "set.backup_offsite": (
        "These sit on the same disk as your data \u2014 if the disk fails it "
        "takes both. Copy this folder to a USB stick or cloud drive now and "
        "then.",
        "\u0647\u0630\u0647 \u0627\u0644\u0646\u0633\u062e \u0639\u0644\u0649 \u0646\u0641\u0633 \u0627\u0644\u0642\u0631\u0635 \u0645\u0639 \u0628\u064a\u0627\u0646\u0627\u062a\u0643 \u2014 \u0648\u0625\u0646 \u062a\u0639\u0637\u0651\u0644 \u0627\u0644\u0642\u0631\u0635 \u0636\u0627\u0639 \u0627\u0644\u0627\u062b\u0646\u0627\u0646. "
        "\u0627\u0646\u0633\u062e \u0647\u0630\u0627 \u0627\u0644\u0645\u062c\u0644\u062f \u0625\u0644\u0649 \u0630\u0627\u0643\u0631\u0629 USB \u0623\u0648 \u0633\u062d\u0627\u0628\u0629 \u0645\u0646 \u062d\u064a\u0646 \u0644\u0622\u062e\u0631.",
    ),
    "set.logo_opaque": (
        "This logo has a solid background, so it is not used as the faint "
        "watermark behind the pages \u2014 only in the top bar and on printed "
        "documents. For the watermark as well, upload a version with a "
        "transparent background (a PNG saved without a background colour).",
        "\u0647\u0630\u0627 \u0627\u0644\u0634\u0639\u0627\u0631 \u0628\u062e\u0644\u0641\u064a\u0629 \u0645\u0635\u0645\u062a\u0629\u060c \u0644\u0630\u0644\u0643 \u0644\u0627 \u064a\u064f\u0633\u062a\u062e\u062f\u0645 \u0643\u0639\u0644\u0627\u0645\u0629 \u0645\u0627\u0626\u064a\u0629 "
        "\u062e\u0644\u0641 \u0627\u0644\u0635\u0641\u062d\u0627\u062a \u2014 \u0641\u0642\u0637 \u0641\u064a \u0627\u0644\u0634\u0631\u064a\u0637 \u0627\u0644\u0639\u0644\u0648\u064a \u0648\u0639\u0644\u0649 \u0627\u0644\u0645\u0633\u062a\u0646\u062f\u0627\u062a \u0627\u0644\u0645\u0637\u0628\u0648\u0639\u0629. "
        "\u0644\u0627\u0633\u062a\u062e\u062f\u0627\u0645\u0647 \u0643\u0639\u0644\u0627\u0645\u0629 \u0645\u0627\u0626\u064a\u0629 \u0623\u064a\u0636\u0627\u064b\u060c \u0627\u0631\u0641\u0639 \u0646\u0633\u062e\u0629 \u0628\u062e\u0644\u0641\u064a\u0629 \u0634\u0641\u0627\u0641\u0629.",
    ),
    "pick.customer_hint": ("Recent customers are listed below \u2014 search here for anyone else.",
                           "\u0627\u0644\u0642\u0627\u0626\u0645\u0629 \u0623\u062f\u0646\u0627\u0647 \u062a\u0639\u0631\u0636 \u0627\u0644\u0639\u0645\u0644\u0627\u0621 \u0627\u0644\u0623\u062d\u062f\u062b \u2014 \u0627\u0628\u062d\u062b \u0647\u0646\u0627 \u0639\u0646 \u063a\u064a\u0631\u0647\u0645."),
    "action.print": ("Print", "طباعة"),
    "action.download_pdf": ("Download PDF", "تحميل PDF"),
    "action.remove": ("Remove", "إزالة"),
    "action.add": ("Add", "إضافة"),
    "action.view": ("View", "عرض"),
    "action.upload": ("Upload", "رفع"),
    "action.confirm_delete": (
        "Are you sure? This cannot be undone.",
        "هل أنت متأكد؟ لا يمكن التراجع عن هذا.",
    ),
    "action.filters": ("Filters", "تصفية"),
    "action.apply": ("Apply", "تطبيق"),

    # -- Dashboard ---------------------------------------------------------
    "dash.advanced": ("Advanced analytics", "تحليلات متقدمة"),
    "dash.advanced_hint": (
        "Trends, customers and recurring faults",
        "الاتجاهات والعملاء والأعطال المتكررة",
    ),
    "dash.customers_total": ("Customers on the books", "العملاء المسجلون"),
    "dash.customers_active": ("Seen in the last year", "زاروا خلال سنة"),
    "dash.customers_dormant": ("Not seen in a year", "لم يزوروا منذ سنة"),
    "dash.owed_trend": ("What you are owed", "المستحق لكم"),
    "dash.owed_trend_hint": (
        "Everything issued up to each month, less everything paid up to it.",
        "كل ما صدر حتى نهاية كل شهر ناقص كل ما حُصّل حتى ذلك الحين.",
    ),
    "dash.invoiced_trend": ("Invoiced each month", "المفوتر شهرياً"),
    "dash.invoiced_trend_hint": (
        "Issued invoices only. Drafts are not counted.",
        "الفواتير الصادرة فقط، دون المسودات.",
    ),
    "dash.by_make": ("Cars by make", "السيارات حسب الماركة"),
    "dash.by_model": ("Cars by model", "السيارات حسب الموديل"),
    "dash.by_category": ("Customers by type", "العملاء حسب النوع"),
    "dash.by_category_hint": (
        "Set on each customer. It changes nothing about how they are billed.",
        "يُحدد لكل عميل، ولا يغيّر شيئاً في طريقة الفوترة.",
    ),
    "dash.known_faults": ("Faults seen most often", "الأعطال الأكثر تكراراً"),
    "dash.known_faults_hint": (
        "Counted from the faults recorded against repair contracts.",
        "محسوبة من الأعطال المسجلة على عقود الإصلاح.",
    ),
    "dash.top_customers": ("Biggest customers", "أكبر العملاء"),
    "dash.invoice_count": ("Invoices", "عدد الفواتير"),
    "dash.not_enough": ("Not enough history yet.", "لا يوجد سجل كافٍ بعد."),
    "dash.no_cars": ("No cars recorded yet.", "لا توجد سيارات مسجلة بعد."),
    "dash.no_customers": ("No customers yet.", "لا يوجد عملاء بعد."),
    "dash.no_faults": (
        "No known faults recorded on a job yet.",
        "لم تُسجل أعطال معروفة على أي عمل بعد.",
    ),
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
    "cust.category": ("Customer type", "نوع العميل"),
    "cust.category_hint": (
        "Only changes how they are grouped in your figures. "
        "Everyone is billed the same way.",
        "يؤثر فقط على تجميعهم في التقارير. طريقة الفوترة واحدة للجميع.",
    ),
    "cust.cat_regular": ("Regular", "عادي"),
    "cust.cat_vip": ("VIP", "عميل مميز"),
    "cust.cat_family": ("Family and friends", "أهل وأصدقاء"),
    "cust.cat_fleet": ("Fleet or business", "أسطول أو منشأة"),
    "cust.active": ("Active", "نشط"),
    "cust.inactive": ("Inactive", "غير نشط"),
    "cust.vat": ("VAT", "\u0627\u0644\u0636\u0631\u064a\u0628\u0629"),
    "cust.no_vat": ("Never charge VAT to this customer",
                    "\u0644\u0627 \u062a\u064f\u062d\u062a\u0633\u0628 \u0636\u0631\u064a\u0628\u0629 \u0627\u0644\u0642\u064a\u0645\u0629 \u0627\u0644\u0645\u0636\u0627\u0641\u0629 \u0644\u0647\u0630\u0627 \u0627\u0644\u0639\u0645\u064a\u0644"),
    "cust.no_vat_hint": (
        "Their invoices and estimates will start with \u201cexcluding VAT\u201d "
        "already ticked. You can still change it on any one of them, and "
        "nothing already issued is affected.",
        "\u0633\u062a\u0628\u062f\u0623 \u0641\u0648\u0627\u062a\u064a\u0631\u0647 \u0648\u0639\u0631\u0648\u0636 \u0627\u0644\u0623\u0633\u0639\u0627\u0631 \u0648\u062e\u064a\u0627\u0631 \u00ab\u0628\u062f\u0648\u0646 \u0636\u0631\u064a\u0628\u0629\u00bb \u0645\u062d\u062f\u062f\u0627\u064b. "
        "\u0648\u064a\u0645\u0643\u0646\u0643 \u062a\u063a\u064a\u064a\u0631\u0647 \u0641\u064a \u0623\u064a \u0645\u0646\u0647\u0627\u060c \u0648\u0644\u0627 \u064a\u062a\u0623\u062b\u0631 \u0645\u0627 \u0635\u062f\u0631 \u0645\u0646 \u0642\u0628\u0644.",
    ),
    "cust.no_vat_applied": (
        "This customer is never charged VAT.",
        "\u0647\u0630\u0627 \u0627\u0644\u0639\u0645\u064a\u0644 \u0644\u0627 \u062a\u064f\u062d\u062a\u0633\u0628 \u0639\u0644\u064a\u0647 \u0627\u0644\u0636\u0631\u064a\u0628\u0629.",
    ),
    "cust.no_vat_badge": ("No VAT", "\u0628\u062f\u0648\u0646 \u0636\u0631\u064a\u0628\u0629"),
    "cust.type": ("Customer type", "\u0646\u0648\u0639 \u0627\u0644\u0639\u0645\u064a\u0644"),
    "cust.any_type": ("Any type", "\u0643\u0644 \u0627\u0644\u0623\u0646\u0648\u0627\u0639"),
    "cust.alert": ("Warning", "\u062a\u0646\u0628\u064a\u0647"),
    "cust.any_alert": ("Any warning", "\u0643\u0644 \u0627\u0644\u062a\u0646\u0628\u064a\u0647\u0627\u062a"),
    "cust.show_inactive": ("Show inactive", "إظهار غير النشطين"),
    "cust.vehicles": ("Vehicles", "المركبات"),
    "cust.balance": ("Balance due", "الرصيد المستحق"),
    "cust.none": ("No customers yet.", "لا يوجد عملاء بعد."),
    "cust.search_hint": (
        "Search by name, phone, or plate",
        "ابحث بالاسم أو الهاتف أو رقم اللوحة",
    ),
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
    "cat.images": ("Photographs", "الصور"),
    "cat.images_empty": (
        "No photographs yet. A picture of the part answers \u201cis this the one?\u201d at the counter.",
        "لا توجد صور بعد. صورة القطعة تجيب على سؤال \u201cهل هذه هي؟\u201d عند الاستلام.",
    ),
    "cat.add_image": ("Add a photograph", "إضافة صورة"),
    "cat.image_caption": ("Caption", "وصف الصورة"),
    "cat.images_hint": (
        "JPEG or PNG, up to 10 MB each.",
        "صيغة JPEG أو PNG، بحد أقصى ١٠ ميجابايت للصورة.",
    ),
    "cat.manufacturer": ("Manufacturer", "الصانع"),
    "cat.manufacturer_hint": (
        "Who made the part. Pick one or type your own.",
        "من صنع القطعة. اختر من القائمة أو اكتب اسماً آخر.",
    ),
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
    # -- The quick invoice: a wiper blade, a bulb, a litre of oil ----------
    "quick.title": ("Quick invoice", "فاتورة سريعة"),
    "quick.nav": ("Quick invoice", "فاتورة سريعة"),
    "quick.intro": (
        "For small counter sales. Who, what, how much — issued and printed "
        "in one go. Use the full invoice for anything with a car attached.",
        "لعمليات البيع الصغيرة. العميل والبند والمبلغ، ثم الإصدار والطباعة مباشرة. "
        "استخدم الفاتورة الكاملة لأي عمل مرتبط بمركبة.",
    ),
    "quick.new_customer": ("New customer — type the name below", "عميل جديد — اكتب الاسم أدناه"),
    "quick.customer_name": ("Customer name", "اسم العميل"),
    "quick.phone_hint": (
        "Optional, but it is how you find them again.",
        "اختياري، لكنه وسيلتك للعثور عليه لاحقاً.",
    ),
    "quick.what": ("What was sold", "البنود المباعة"),
    "quick.paid_now": ("Paid now, in full", "مدفوعة بالكامل الآن"),
    "quick.issue": ("Issue and print", "إصدار وطباعة"),
    "quick.issue_hint": (
        "This issues the invoice straight away and opens it for printing.",
        "يصدر الفاتورة مباشرة ويفتحها للطباعة.",
    ),
    "quick.full_invoice": ("Full invoice instead", "الفاتورة الكاملة بدلاً من ذلك"),
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
    "inv.discount_mode": ("Discount is in", "الخصم بـ"),
    "inv.discount_hint": (
        "A fixed amount, or a percentage of the subtotal.",
        "مبلغ ثابت أو نسبة مئوية من المجموع.",
    ),
    "inv.taxable": ("Taxable amount", "المبلغ الخاضع للضريبة"),
    "inv.vat": ("VAT", "ضريبة القيمة المضافة"),
    "inv.total": ("Total", "الإجمالي"),
    "inv.paid": ("Paid", "المدفوع"),
    "inv.balance": ("Balance due", "المتبقي"),
    "inv.add_line": ("Add item", "إضافة بند"),
    "inv.remove_line": ("Remove", "حذف"),
    # One box per line now: it suggests the catalogue as you type and accepts
    # anything you write instead, so the wording has to invite both.
    "inv.pick_custom": (
        "Type a description, or pick from the catalogue",
        "اكتب وصفاً أو اختر من القائمة",
    ),
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
    "inv.doc_plain": (
        "No VAT — cash sale, not a tax invoice",
        "بدون ضريبة — بيع نقدي، ليست فاتورة ضريبية",
    ),
    "inv.plain_invoice": ("INVOICE", "فاتورة"),
    "inv.exclude_vat": ("Excluding VAT \u2014 do not charge tax on this",
                        "\u0628\u062f\u0648\u0646 \u0636\u0631\u064a\u0628\u0629 \u0627\u0644\u0642\u064a\u0645\u0629 \u0627\u0644\u0645\u0636\u0627\u0641\u0629 \u2014 \u0644\u0627 \u062a\u064f\u062d\u062a\u0633\u0628 \u0627\u0644\u0636\u0631\u064a\u0628\u0629"),
    "inv.exclude_vat_hint": (
        "Leave this unticked for a normal tax invoice. Ticked, no VAT is "
        "added and the document does not carry the tax wording.",
        "\u0627\u062a\u0631\u0643\u0647 \u062f\u0648\u0646 \u062a\u062d\u062f\u064a\u062f \u0644\u0641\u0627\u062a\u0648\u0631\u0629 \u0636\u0631\u064a\u0628\u064a\u0629 \u0639\u0627\u062f\u064a\u0629. \u0639\u0646\u062f \u062a\u062d\u062f\u064a\u062f\u0647 \u0644\u0627 \u062a\u064f\u0636\u0627\u0641 \u0627\u0644\u0636\u0631\u064a\u0628\u0629 "
        "\u0648\u0644\u0627 \u062a\u062d\u0645\u0644 \u0627\u0644\u0648\u062b\u064a\u0642\u0629 \u0635\u064a\u0627\u063a\u0629 \u0627\u0644\u0641\u0627\u062a\u0648\u0631\u0629 \u0627\u0644\u0636\u0631\u064a\u0628\u064a\u0629.",
    ),
    "inv.doc_type_hint": (
        "A tax invoice charges VAT and prints the tax-invoice wording. "
        "The no-VAT option adds no tax at all and prints as a plain bill — "
        "for cash sales and people you deal with directly. Both are recorded "
        "and kept apart in your figures, so your VAT total covers tax "
        "invoices only. Which sales may legally be billed without a tax "
        "invoice is a question for your accountant.",
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
    # Importing a price list. Its own keys rather than sharing the
    # customer import's, because every sentence differs: codes,
    # duplicates and missing prices are the things that go wrong here.
    "iimp.title": ("Import items", "\u0627\u0633\u062a\u064a\u0631\u0627\u062f \u0627\u0644\u0628\u0646\u0648\u062f"),
    "iimp.hint": (
        "Add services and parts from a spreadsheet. Nothing is saved "
        "until you have seen what it would do.",
        "\u0623\u0636\u0641 \u0627\u0644\u062e\u062f\u0645\u0627\u062a \u0648\u0642\u0637\u0639 \u0627\u0644\u063a\u064a\u0627\u0631 \u0645\u0646 \u0645\u0644\u0641 \u062c\u062f\u0648\u0644. \u0644\u0646 \u064a\u064f\u062d\u0641\u0638 \u0634\u064a\u0621 "
        "\u062d\u062a\u0649 \u062a\u0631\u0649 \u0645\u0627 \u0633\u064a\u062d\u062f\u062b.",
    ),
    "iimp.choose": ("Spreadsheet (.xlsx or .csv)", "\u0645\u0644\u0641 \u062c\u062f\u0648\u0644 (xlsx \u0623\u0648 csv)"),
    "iimp.template_hint": (
        "A file with the right headings and two example rows, if you "
        "would rather start from one.",
        "\u0645\u0644\u0641 \u0628\u0627\u0644\u0639\u0646\u0627\u0648\u064a\u0646 \u0627\u0644\u0635\u062d\u064a\u062d\u0629 \u0648\u0645\u062b\u0627\u0644\u064a\u0646\u060c \u0625\u0646 \u0623\u0631\u062f\u062a \u0627\u0644\u0628\u062f\u0621 \u0645\u0646\u0647.",
    ),
    "iimp.headings": (
        "Recognised headings, in English or Arabic: code (or item no), "
        "description, Arabic description, type, unit, price. Any other "
        "column is ignored.",
        "\u0627\u0644\u0639\u0646\u0627\u0648\u064a\u0646 \u0627\u0644\u0645\u0639\u0631\u0648\u0641\u0629 \u0628\u0627\u0644\u0639\u0631\u0628\u064a\u0629 \u0623\u0648 \u0627\u0644\u0625\u0646\u062c\u0644\u064a\u0632\u064a\u0629: \u0627\u0644\u0631\u0645\u0632 \u0623\u0648 \u0631\u0642\u0645 \u0627\u0644\u0635\u0646\u0641\u060c "
        "\u0627\u0644\u0648\u0635\u0641\u060c \u0627\u0644\u0648\u0635\u0641 \u0628\u0627\u0644\u0639\u0631\u0628\u064a\u0629\u060c \u0627\u0644\u0646\u0648\u0639\u060c \u0627\u0644\u0648\u062d\u062f\u0629\u060c \u0627\u0644\u0633\u0639\u0631. "
        "\u0648\u0623\u064a \u0639\u0645\u0648\u062f \u0622\u062e\u0631 \u064a\u064f\u062a\u062c\u0627\u0647\u0644.",
    ),
    "iimp.codes_note": (
        "Codes are kept exactly as written, so a code like 0123 keeps "
        "its leading zero.",
        "\u062a\u064f\u062d\u0641\u0638 \u0627\u0644\u0631\u0645\u0648\u0632 \u0643\u0645\u0627 \u0647\u064a\u060c \u0641\u0631\u0645\u0632 \u0645\u062b\u0644 0123 \u064a\u062d\u062a\u0641\u0638 \u0628\u0627\u0644\u0635\u0641\u0631 \u0627\u0644\u0630\u064a \u0623\u0645\u0627\u0645\u0647.",
    ),
    # The item import gets its own wording wherever a string names what
    # is being imported. Sharing the customer importer's was wrong twice
    # over: in English the button read "Import these customers" on the
    # items page, and in Arabic the shared strings use the human plural
    # (\u0625\u0636\u0627\u0641\u062a\u0647\u0645), which is not how you talk about parts.
    # Why a row will not be imported. Keys with a {code} placeholder,
    # so the preview reads in whichever language the page is in.
    "iimp.skip_no_description": ("No description", "\u0644\u0627 \u064a\u0648\u062c\u062f \u0648\u0635\u0641"),
    "iimp.skip_code_exists": (
        "Code {code} is already in the catalogue",
        "\u0627\u0644\u0631\u0645\u0632 {code} \u0645\u0648\u062c\u0648\u062f \u0645\u0633\u0628\u0642\u0627\u064b \u0641\u064a \u0627\u0644\u0642\u0627\u0626\u0645\u0629",
    ),
    "iimp.skip_code_repeated": (
        "Code {code} appears earlier in this file",
        "\u0627\u0644\u0631\u0645\u0632 {code} \u0645\u0643\u0631\u0631 \u0641\u064a \u0647\u0630\u0627 \u0627\u0644\u0645\u0644\u0641",
    ),
    "iimp.skip_exists": ("Already in the catalogue", "\u0645\u0648\u062c\u0648\u062f \u0645\u0633\u0628\u0642\u0627\u064b \u0641\u064a \u0627\u0644\u0642\u0627\u0626\u0645\u0629"),
    "iimp.skip_repeated": ("Appears earlier in this file", "\u0645\u0643\u0631\u0631 \u0641\u064a \u0647\u0630\u0627 \u0627\u0644\u0645\u0644\u0641"),
    "iimp.confirm": ("Import these items", "\u0627\u0633\u062a\u064a\u0631\u0627\u062f \u0647\u0630\u0647 \u0627\u0644\u0628\u0646\u0648\u062f"),
    "iimp.will_import": ("Will be added", "\u0633\u062a\u064f\u0636\u0627\u0641"),
    "iimp.will_skip": ("Will be skipped", "\u0633\u064a\u062a\u0645 \u062a\u062c\u0627\u0647\u0644\u0647\u0627"),
    "iimp.imported": ("Items imported.", "\u062a\u0645 \u0627\u0633\u062a\u064a\u0631\u0627\u062f \u0627\u0644\u0628\u0646\u0648\u062f."),
    "iimp.no_prices": (
        "None of these rows has a price. They will be added at zero, and "
        "a price can be set on each one in the catalogue afterwards.",
        "\u0644\u0627 \u064a\u0648\u062c\u062f \u0633\u0639\u0631 \u0641\u064a \u0623\u064a \u0645\u0646 \u0647\u0630\u0647 \u0627\u0644\u0635\u0641\u0648\u0641\u060c \u0648\u0633\u062a\u064f\u0636\u0627\u0641 \u0628\u0633\u0639\u0631 \u0635\u0641\u0631\u060c "
        "\u0648\u064a\u0645\u0643\u0646 \u062a\u062d\u062f\u064a\u062f \u0627\u0644\u0633\u0639\u0631 \u0644\u0643\u0644 \u0628\u0646\u062f \u0644\u0627\u062d\u0642\u0627\u064b.",
    ),
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
    # -- Inspections: the check that happens before anyone quotes -----------
    "nav.inspections": ("Inspections", "الفحوصات"),
    "ins.title": ("Inspections", "الفحوصات"),
    "ins.nav": ("Inspections", "الفحوصات"),
    "ins.new": ("New inspection", "فحص جديد"),
    "ins.search_hint": (
        "Search by sheet number, customer or car",
        "ابحث برقم الفحص أو العميل أو السيارة",
    ),
    "ins.number": ("Inspection no.", "رقم الفحص"),
    "ins.date": ("Checked on", "تاريخ الفحص"),
    "ins.details": ("Inspection details", "بيانات الفحص"),
    "ins.checklist": ("What was inspected", "البنود المفحوصة"),
    "ins.checklist_hint": (
        "The standard walk-round is filled in for you. Change the condition "
        "where something is not right, and remove any row that does not apply.",
        "تم تعبئة الفحص المعتاد مسبقاً. غيّر الحالة عند وجود ملاحظة، واحذف أي بند لا ينطبق.",
    ),
    "ins.area": ("Item", "البند"),
    "ins.condition": ("Condition", "الحالة"),
    "ins.finding": ("Finding", "الملاحظة"),
    "ins.known_issue": ("Known fault", "عطل معروف"),
    "ins.matches": ("Matches", "يطابق"),
    "ins.est_price": ("Estimated", "التقدير"),
    "ins.quote_it": ("Quote it", "إدراجه بالعرض"),
    "ins.quote_yes": ("Quote", "يُدرج"),
    "ins.quote_no": ("No", "لا"),
    "ins.add_row": ("Add a row", "إضافة بند"),
    "ins.cond_ok": ("OK", "سليم"),
    "ins.cond_attention": ("Advisory", "يحتاج متابعة"),
    "ins.cond_urgent": ("Urgent", "عاجل"),
    "ins.cond_na": ("Not checked", "لم يُفحص"),
    "ins.urgent": ("urgent", "عاجل"),
    "ins.attention": ("advisory", "متابعة"),
    "ins.all_ok": ("All clear", "الكل سليم"),
    "ins.findings": ("Findings", "الملاحظات"),
    "ins.quotable": ("To quote", "قيمة العرض"),
    "ins.summary": ("Summary for the customer", "ملخص للعميل"),
    "ins.summary_hint": (
        "Carried onto the estimate if you make one from this check.",
        "يُنقل إلى عرض السعر إذا أنشأته من هذا الفحص.",
    ),
    "ins.make_estimate": ("Make an estimate", "إنشاء عرض سعر"),
    "ins.view_estimate": ("Estimate", "عرض السعر"),
    "ins.none": ("No inspections recorded yet.", "لا توجد فحوصات بعد."),
    "ins.none_hint": (
        "An inspection records what you found before anyone talks about price.",
        "الفحص يسجل ما وجدته قبل الحديث عن السعر.",
    ),
    "status.checked": ("Checked", "تم الفحص"),
    "status.quoted": ("Quoted", "تم التسعير"),
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
    "est.msg_language": ("Message language", "لغة الرسالة"),
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
        "A square image with a transparent background works best \u2014 that is "
        "what lets it be used as the faint watermark behind the pages too.",
        "يُطبع على العقود والفواتير. صيغة PNG أو JPEG أو GIF أو WebP وبحجم أقل من ١ ميجابايت. "
        "يُفضل صورة مربعة بخلفية شفافة — فهي ما يُتيح استخدامه كعلامة مائية خلف الصفحات أيضاً.",
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
        "{customer} {business} {number} {items} {subtotal} {discount} "
        "{discount_rate} {vat} {total} {valid_until}. {items} lists each "
        "item with its price. A line whose placeholders are all empty is "
        "left out entirely, so a discount line only appears when there is "
        "a discount.",
        "تُعبأ عند إرسال عرض السعر. العناصر المتاحة: "
        "{customer} {business} {number} {items} {subtotal} {discount} "
        "{discount_rate} {vat} {total} {valid_until}. العنصر {items} يعرض "
        "كل بند مع سعره. ويُحذف السطر بالكامل إذا كانت عناصره فارغة، "
        "فلا يظهر سطر الخصم إلا عند وجود خصم.",
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
        "A zip holding the database and every scanned attachment. "
        "This is the one to restore from. Keep it somewhere safe.",
        "ملف مضغوط يحتوي على قاعدة البيانات وجميع المرفقات الممسوحة. "
        "هذا هو الملف المستخدم للاستعادة. احفظه في مكان آمن.",
    ),
    "set.download_backup": ("Download backup (.zip)", "تحميل نسخة احتياطية (zip)"),
    "set.download_excel": ("Download as Excel (.xlsx)", "تحميل كملف إكسل (xlsx)"),
    "set.excel_hint": (
        "Every record in a workbook anyone can open. Readable without this "
        "software — but it cannot be restored from, so keep the zip as well.",
        "جميع السجلات في ملف إكسل يمكن لأي شخص فتحه. يمكن قراءته دون هذا "
        "البرنامج، لكن لا يمكن الاستعادة منه، لذا احتفظ بالملف المضغوط أيضاً.",
    ),
    "set.excel_unavailable": (
        "The Excel export needs the openpyxl package, which is not installed. "
        "The zip backup still works.",
        "يتطلب تصدير إكسل حزمة openpyxl غير المثبتة. "
        "لا يزال بإمكانك تحميل النسخة الاحتياطية المضغوطة.",
    ),

    # -- Messages ----------------------------------------------------------
    "msg.saved": ("Saved.", "تم الحفظ."),
    "msg.no_change": ("Nothing changed.", "\u0644\u0645 \u064a\u062a\u063a\u064a\u0631 \u0634\u064a\u0621."),
    # Selecting rows and acting on them together.
    "cat.select_all": ("Select all on this page", "\u062a\u062d\u062f\u064a\u062f \u0627\u0644\u0643\u0644 \u0641\u064a \u0647\u0630\u0647 \u0627\u0644\u0635\u0641\u062d\u0629"),
    "cat.select_row": ("Select this item", "\u062a\u062d\u062f\u064a\u062f \u0647\u0630\u0627 \u0627\u0644\u0628\u0646\u062f"),
    "cat.none_selected": (
        "Nothing was selected, so nothing was changed.",
        "\u0644\u0645 \u064a\u062a\u0645 \u062a\u062d\u062f\u064a\u062f \u0623\u064a \u0628\u0646\u062f\u060c \u0648\u0644\u0645 \u064a\u062a\u063a\u064a\u0631 \u0634\u064a\u0621.",
    ),
    "cat.selected_n": ("{n} selected", "\u062a\u0645 \u062a\u062d\u062f\u064a\u062f {n}"),
    # The count goes in the confirmation, because "Delete 37 items?" is a
    # different question from "Delete this item?" and deserves to look it.
    "cat.confirm_delete_n": (
        "Delete the selected items? Invoices already raised keep their "
        "own wording and prices and are not affected.",
        "\u062d\u0630\u0641 \u0627\u0644\u0628\u0646\u0648\u062f \u0627\u0644\u0645\u062d\u062f\u062f\u0629\u061f \u0627\u0644\u0641\u0648\u0627\u062a\u064a\u0631 \u0627\u0644\u0635\u0627\u062f\u0631\u0629 "
        "\u062a\u062d\u062a\u0641\u0638 \u0628\u0628\u064a\u0627\u0646\u0627\u062a\u0647\u0627 \u0648\u0644\u0646 \u062a\u062a\u0623\u062b\u0631.",
    ),
    "cat.confirm_retire_n": (
        "Mark the selected items inactive? They drop out of the lists; "
        "nothing is lost.",
        "\u0648\u0636\u0639 \u0627\u0644\u0628\u0646\u0648\u062f \u0627\u0644\u0645\u062d\u062f\u062f\u0629 \u063a\u064a\u0631 \u0646\u0634\u0637\u0629\u061f \u0633\u062a\u062e\u062a\u0641\u064a \u0645\u0646 \u0627\u0644\u0642\u0648\u0627\u0626\u0645 \u0648\u0644\u0646 \u064a\u064f\u0641\u0642\u062f \u0634\u064a\u0621.",
    ),
    "msg.deleted": ("Deleted.", "تم الحذف."),
    # What the delete button does once records are protected. Worded as
    # the outcome rather than as a refusal: the user asked for the record
    # to go away, and it has gone away from the lists.
    "msg.retired": (
        "Marked inactive. It is out of the lists, and its history is kept.",
        "تم وضعه غير نشط. لم يعد يظهر في القوائم، وسجلّه محفوظ.",
    ),
    "msg.voided": (
        "Voided. The invoice stays on record and is out of the totals.",
        "تم الإلغاء. تبقى الفاتورة في السجل وخارج الإجماليات.",
    ),
    # The switch itself, in Settings.
    "set.protect": ("Never delete records", "عدم حذف السجلات"),
    "set.protect_hint": (
        "With this on, the Delete buttons on customers, vehicles and "
        "invoices mark the record inactive instead of removing it. Nothing "
        "is lost, and inactive records stay out of the lists. Leave it off "
        "while you are still importing and tidying up, so a mistyped row "
        "can simply be removed.",
        "عند تفعيل هذا الخيار، تقوم أزرار الحذف في العملاء والمركبات "
        "والفواتير بوضع السجل غير نشط بدلاً من إزالته. لا يُفقد أي شيء، "
        "ولا تظهر السجلات غير النشطة في القوائم. اتركه معطّلاً أثناء "
        "الاستيراد والترتيب حتى يمكن حذف أي صف مكتوب بالخطأ.",
    ),
    "act.retire": ("Make inactive", "وضع غير نشط"),
    "action.confirm_retire": (
        "Mark this inactive? It will drop out of the lists; nothing is lost.",
        "وضعه غير نشط؟ سيختفي من القوائم ولن يُفقد أي شيء.",
    ),
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
