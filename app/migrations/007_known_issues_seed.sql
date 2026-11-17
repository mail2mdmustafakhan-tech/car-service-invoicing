-- ---------------------------------------------------------------------------
-- 007_known_issues_seed.sql  --  a starting list of German-car faults
-- ---------------------------------------------------------------------------
-- Separate from the schema on purpose. Structure and content age at different
-- rates: the tables above should not need touching again, while this list
-- will be corrected by anyone who has had the cars on a ramp.
--
-- Compiled from published engine and chassis reliability write-ups and
-- manufacturer service bulletins, then written out in plain language. These
-- are the faults that recur often enough to be worth naming before the car
-- is stripped; they are a prompt for a technician, not a diagnosis, and not
-- every car of a given year has them.
--
-- Everything here is marked is_builtin = 1, which is only a label: these
-- rows are edited and deleted exactly like any the workshop adds itself.
-- Nothing in the software treats them as more authoritative than its own.
-- ---------------------------------------------------------------------------

INSERT INTO known_issues
    (make, model, engine, year_from, year_to, title_en, title_ar,
     symptoms_en, symptoms_ar, check_en, check_ar, severity, is_builtin)
VALUES

-- -- BMW -------------------------------------------------------------------
('BMW', '3 / 5 Series, X1, X3', 'N20 / N26', 2011, 2015,
 'Timing chain guide wear',
 'تآكل مجاري جنزير التايمن',
 'Rattle or ticking from the front of the engine, worst on a cold start. May set VANOS or Valvetronic faults.',
 'صوت خبط أو طقطقة من مقدمة المحرك، أوضح عند التشغيل البارد، وقد تظهر أعطال الفانوس أو الفالفترونيك.',
 'Listen on a cold start before anything else. If the chain has stretched it must be dealt with at once — this is an interference engine and a jumped chain means valve damage.',
 'استمع عند التشغيل البارد أولاً. إذا تمدد الجنزير يجب معالجته فوراً، فالمحرك تداخلي وقفز الجنزير يعني تلف البلوف.',
 'high', 1),

('BMW', '3 / 5 Series, X1, X3', 'N20 / N55', 2011, 2018,
 'Valve cover gasket oil leak',
 'تسريب زيت من جوان غطاء البلوف',
 'Smell of burning oil, oil on the exhaust manifold, sometimes oil tracking down into wiring connectors.',
 'رائحة زيت محترق، زيت على مشعب العادم، وأحياناً وصول الزيت إلى وصلات الأسلاك.',
 'Not only a mess: oil reaching the engine control connectors causes electrical faults that get chased in the wrong place.',
 'ليست مجرد اتساخ: وصول الزيت إلى وصلات كمبيوتر المحرك يسبب أعطالاً كهربائية يُبحث عنها في المكان الخطأ.',
 'medium', 1),

('BMW', '3 / 5 Series, X3, X5', 'N20 / N55', 2011, 2018,
 'Oil filter housing gasket leak',
 'تسريب جوان بيت فلتر الزيت',
 'Oil weeping down the front of the engine, often onto the belt.',
 'تسريب زيت على مقدمة المحرك وغالباً على السير.',
 'Check the belt while it is apart. Oil on a serpentine belt ends with the belt shredding and taking other things with it.',
 'افحص السير أثناء الفك. الزيت على السير ينتهي بتقطعه وإتلاف ما حوله.',
 'medium', 1),

('BMW', 'Most petrol models', 'N20 / N55 / N63', 2010, 2019,
 'Electric water pump failure',
 'عطل طرمبة الماء الكهربائية',
 'Overheating warning with no obvious leak; pump runs intermittently or not at all.',
 'تحذير ارتفاع الحرارة دون تسريب ظاهر، والطرمبة تعمل بشكل متقطع أو لا تعمل.',
 'These fail electrically rather than by leaking, so a dry engine bay does not rule it out.',
 'العطل كهربائي وليس تسريباً، لذا نظافة حجرة المحرك لا تستبعده.',
 'high', 1),

('BMW', 'Direct-injection petrol', 'N20 / N55 / N63', 2007, 2020,
 'Carbon build-up on intake valves',
 'تراكم الكربون على بلوف السحب',
 'Rough idle, misfire on cold start, gradual loss of power and economy.',
 'عدم انتظام الرالنتي، ارتعاش عند التشغيل البارد، وضعف تدريجي في العزم والاستهلاك.',
 'Direct injection means no fuel washes the intake valves. Walnut blasting at intervals rather than a repair.',
 'الحقن المباشر لا يغسل بلوف السحب. التنظيف بالجوز دورياً وليس إصلاحاً لمرة واحدة.',
 'medium', 1),

('BMW', '5 / 7 Series, X3, X5, X6', '', 2004, 2020,
 'Water in the cabin or boot from blocked sunroof drains',
 'دخول ماء إلى المقصورة أو الشنطة بسبب انسداد تصريف فتحة السقف',
 'Damp carpets, water in the boot well, electrical faults from soaked modules under the carpet or in the boot.',
 'سجاد مبلل، ماء في أرضية الشنطة، وأعطال كهربائية بسبب غرق الوحدات تحت السجاد أو في الشنطة.',
 'Manufacturer bulletins cover drains that are blocked, kinked, or unseated at the pillar, as well as the sunroof seal itself. Clear and test the drains before suspecting the glass.',
 'نشرات الصيانة تغطي انسداد أو التواء أو انفصال خراطيم التصريف عند العمود، إضافة إلى جوان فتحة السقف. نظّف واختبر التصريف قبل الشك في الزجاج.',
 'high', 1),

('BMW', '7 Series, 5 Series, X5', '', 2005, 2018,
 'Air suspension compressor or bag failure',
 'عطل كمبروسر أو جلود المساعدات الهوائية',
 'Car sits low on one corner overnight, suspension warning on the dash, compressor running for a long time.',
 'انخفاض السيارة من إحدى الزوايا بعد الوقوف، تحذير نظام التعليق، وعمل الكمبروسر لفترة طويلة.',
 'A leaking bag burns out the compressor, so replacing only the compressor usually fails twice.',
 'الجلد المثقوب يحرق الكمبروسر، لذا تغيير الكمبروسر وحده يفشل غالباً مرتين.',
 'high', 1),

-- -- Mercedes-Benz --------------------------------------------------------
('Mercedes-Benz', 'C / E / S-Class, GLK', 'M272 / M273', 2004, 2010,
 'Balance shaft or idler gear sprocket wear',
 'تآكل ترس عمود الاتزان أو الترس الوسيط',
 'Check engine light with camshaft timing correlation faults; rough running.',
 'لمبة فحص المحرك مع أعطال تطابق توقيت الكامات، وعدم انتظام في العمل.',
 'An engine-out job on the V6, so confirm by fault code and engine number range before quoting anything.',
 'يتطلب إنزال المحرك في V6، لذا تأكد من رمز العطل ونطاق رقم المحرك قبل إعطاء أي سعر.',
 'high', 1),

('Mercedes-Benz', 'C / E / GLC-Class', 'M274', 2013, 2021,
 'Oil consumption and piston ring wear',
 'استهلاك الزيت وتآكل حلقات المكبس',
 'Needing oil between services, blue smoke under load, in bad cases bearing damage.',
 'الحاجة لإضافة زيت بين الصيانات، دخان أزرق تحت الحمل، وفي الحالات السيئة تلف السبائك.',
 'A compression and leak-down test tells you where you are before any money is spent.',
 'اختبار الضغط والتسريب يحدد الوضع قبل صرف أي مبلغ.',
 'high', 1),

('Mercedes-Benz', 'C / E / S-Class, GLC', 'M276', 2011, 2020,
 'Camshaft adjuster rattle on cold start',
 'صوت معدّل الكامات عند التشغيل البارد',
 'Brief rattle for a second or two on a cold start, from the front of the engine.',
 'صوت خبط لثانية أو اثنتين عند التشغيل البارد من مقدمة المحرك.',
 'Short and easy to dismiss. Left long enough it becomes a timing correlation fault.',
 'قصير ويسهل تجاهله، لكن إهماله يؤدي إلى عطل في تطابق التوقيت.',
 'medium', 1),

('Mercedes-Benz', 'Direct-injection petrol', 'M274 / M276', 2011, 2020,
 'High-pressure fuel pump failure',
 'عطل طرمبة الوقود عالية الضغط',
 'Long cranking, stalling, loss of power, fuel pressure codes stored.',
 'تشغيل طويل، انطفاء المحرك، ضعف العزم، وتخزين أكواد ضغط الوقود.',
 'Check the low-pressure side first. Replacing the high-pressure pump on a weak feed solves nothing.',
 'افحص الجانب منخفض الضغط أولاً، فتغيير الطرمبة العالية مع تغذية ضعيفة لا يحل شيئاً.',
 'medium', 1),

('Mercedes-Benz', 'GLK, C-Class and others', '', 2008, 2015,
 'Electronic steering lock failure — car will not start',
 'عطل قفل المقود الإلكتروني — السيارة لا تدور',
 'Key turns but nothing happens; steering stays locked; no crank.',
 'المفتاح يدور دون استجابة، والمقود يبقى مقفلاً ولا يوجد تدوير.',
 'A known failure of the lock unit rather than the starter or battery, so test before replacing either.',
 'عطل معروف في وحدة القفل وليس في السلف أو البطارية، لذا افحص قبل تغيير أي منهما.',
 'high', 1),

('Mercedes-Benz', 'CLA, GLA, A-Class', '7G-DCT', 2013, 2019,
 'Dual-clutch shudder at low speed',
 'ارتجاج القير المزدوج عند السرعات المنخفضة',
 'Juddering when pulling away and in slow traffic, hesitant engagement.',
 'ارتجاج عند الانطلاق وفي الزحام، وتعشيق متردد.',
 'Fluid and adaptation first; clutch pack only after those are ruled out.',
 'الزيت والبرمجة أولاً، ثم طقم الكلتش بعد استبعادهما.',
 'medium', 1),

-- -- Audi and Volkswagen --------------------------------------------------
('Audi', 'A4, A5, Q5 and VW equivalents', 'EA888 Gen 1-2', 2008, 2013,
 'High oil consumption from piston rings',
 'استهلاك زيت مرتفع بسبب حلقات المكابس',
 'Oil needed between services, sometimes a litre every few thousand kilometres; blue smoke.',
 'الحاجة لإضافة زيت بين الصيانات، وأحياناً لتر كل بضعة آلاف كيلومتر، مع دخان أزرق.',
 'Measure it over a known distance before quoting. The repair is pistons and rings, so the customer needs the figure, not an impression.',
 'قِس الاستهلاك على مسافة معلومة قبل التسعير. الإصلاح يشمل المكابس والحلقات، والعميل يحتاج رقماً لا انطباعاً.',
 'high', 1),

('Audi', 'A3, A4, A5, Q5 and VW equivalents', 'EA888', 2008, 2016,
 'Timing chain tensioner wear',
 'تآكل شداد جنزير التايمن',
 'Rattle for a moment on cold start; in the worst case the chain jumps and the engine is destroyed.',
 'خبط لحظي عند التشغيل البارد، وفي أسوأ الحالات يقفز الجنزير ويتلف المحرك.',
 'The updated tensioner is the fix. A cold-start rattle on this engine is urgent, not cosmetic.',
 'الشداد المطوّر هو الحل. الخبط عند التشغيل البارد في هذا المحرك أمر عاجل وليس شكلياً.',
 'high', 1),

('Volkswagen', 'Most EA888 petrol models', 'EA888', 2008, 2022,
 'Water pump and thermostat housing leak',
 'تسريب طرمبة الماء وبيت الثرموستات',
 'Coolant loss with no puddle, sweet smell, level warning, temperature creeping up.',
 'نقص سائل التبريد دون برك ظاهرة، رائحة حلوة، تحذير المستوى، وارتفاع تدريجي في الحرارة.',
 'The housing is plastic and warps with heat cycles. This is the most common fault on the family; pump and housing are usually done together.',
 'البيت بلاستيكي ويتشوه مع دورات الحرارة. أكثر أعطال هذه العائلة شيوعاً، وتُغيّر الطرمبة والبيت معاً عادة.',
 'medium', 1),

('Volkswagen', 'EA888 petrol models', 'EA888', 2008, 2022,
 'Crankcase breather (PCV) valve failure',
 'عطل صمام تهوية الكرتير',
 'Rough idle, oil consumption, whistling from the engine, sometimes a vacuum leak code.',
 'عدم انتظام الرالنتي، استهلاك زيت، صفير من المحرك، وأحياناً كود تسريب هواء.',
 'Cheap and commonly blamed for symptoms that turn out to be rings — check consumption before and after.',
 'رخيص ويُتهم كثيراً بأعراض سببها الحلقات، فقِس الاستهلاك قبل وبعد.',
 'low', 1),

('Audi', 'A4, A5, Q5, A6', '2.0 / 3.0 TFSI', 2008, 2017,
 'Carbon build-up on intake valves',
 'تراكم الكربون على بلوف السحب',
 'Misfires, rough cold running, lost power, worse on a stop-start duty cycle.',
 'ارتعاش، تشغيل بارد غير منتظم، ضعف عزم، ويزداد مع القيادة المتقطعة.',
 'Expected maintenance on direct injection rather than a defect. Quote it as a periodic clean.',
 'صيانة متوقعة في الحقن المباشر وليست عيباً. سعّرها كتنظيف دوري.',
 'medium', 1),

('Audi', 'A6, A7, A8, Q7', '', 2010, 2018,
 'Air suspension leak',
 'تسريب التعليق الهوائي',
 'One corner down after the car has stood, compressor running long, ride height warning.',
 'انخفاض إحدى الزوايا بعد الوقوف، عمل طويل للكمبروسر، وتحذير ارتفاع الهيكل.',
 'Find the leak before fitting a compressor, or the new compressor goes the same way.',
 'ابحث عن التسريب قبل تركيب كمبروسر جديد وإلا تلف مثل سابقه.',
 'high', 1),

-- -- Anything German, in this climate --------------------------------------
('All', 'All models', '', NULL, NULL,
 'Air conditioning performance in Gulf heat',
 'أداء المكيف في حرارة الخليج',
 'Cooling falls off in traffic, works better at speed, or fails after a few seasons.',
 'ضعف التبريد في الزحام، وتحسنه أثناء السير، أو تعطله بعد بضعة مواسم.',
 'Condensers block with dust and the system works far harder here than the design assumed. Check gas, condenser cleanliness and fan operation together.',
 'المكثف ينسد بالغبار والنظام يعمل بجهد أكبر مما افترضه التصميم. افحص الغاز ونظافة المكثف وعمل المراوح معاً.',
 'medium', 1),

('All', 'All models', '', NULL, NULL,
 'Battery life shortened by heat',
 'قصر عمر البطارية بسبب الحرارة',
 'Battery fails after two to three years rather than four or five; stop-start stops working first.',
 'تتلف البطارية بعد سنتين إلى ثلاث بدل أربع أو خمس، ويتوقف نظام التشغيل التلقائي أولاً.',
 'Register a replacement battery to the car where the model requires it, or charging stays set for the old one.',
 'سجّل البطارية الجديدة في كمبيوتر السيارة عند الحاجة، وإلا بقي الشحن مضبوطاً على القديمة.',
 'low', 1);
