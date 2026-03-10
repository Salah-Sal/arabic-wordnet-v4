# خوارزمية التحليل اللغوي — نسخة واجهة البرمجة

# Algorithm Linguistic Analysis — API-Aware (Collect-then-Execute)

> هذه الخوارزمية تحوّل المراجع (سواء كان بشرياً أو ذكاءً اصطناعياً) إلى **ناقد لغوي**: يفحص اللمّات، يؤلف التعريفات، يثري الحقول، ثم يُصدّر القرارات كسجل عمليات (Action Queue) يُنفَّذ على واجهة البرمجة بعد المراجعة.

---

## الاصطلاحات — Conventions

```text
لكل X في Y نفّذ          FOR EACH X in Y DO
إذا ... فـ               IF ... THEN
وإلا إذا ... فـ          ELSE IF ... THEN
وإلا                     ELSE
نهاية                    END
⟵                        تعيين (assignment)
▸ إجراء(هدف)             ورقة — إجراء يُسجَّل في سجل العمليات (لا يُنفَّذ فوراً)
⊕ api_call()             استدعاء فعلي لواجهة البرمجة (يُنفَّذ في الخطوة ٦ فقط)
// تعليق                  ملاحظة توضيحية
┊                         مستوى التداخل (Scope Indentation)

```

---

## نموذج التنفيذ — Execution Model

```text
// ══════════════════════════════════════════════════════════════
// نمط "اجمع ثم نفّذ" (Collect-then-Execute)
// ══════════════════════════════════════════════════════════════
//
// الخطوات ٠–٥: تحليل + جمع القرارات في سجل العمليات (action_queue)
//   - كل إجراء (▸) يُسجَّل فقط، لا يُنفَّذ على قاعدة البيانات
//   - المراجع يستطيع مراجعة السجل وتعديله قبل التنفيذ
//
// الخطوة ٦: تنفيذ السجل على واجهة البرمجة
//   - ترجمة كل إجراء (▸) إلى استدعاء API (⊕)
//   - الترتيب مهم: الحذف قبل الإضافة، التعريفات قبل العلاقات
//   - كل عملية قابلة للتراجع (rollback) عند الفشل
//
// الفائدة:
//   ١. المراجع يرى كل القرارات مجتمعة قبل تطبيقها
//   ٢. يمكن تعديل/حذف/إعادة ترتيب العمليات
//   ٣. تنفيذ دُفعي (batch) أكفأ من استدعاءات متفرقة
//   ٤. سجل تدقيق (audit log) كامل لكل تغيير
// ══════════════════════════════════════════════════════════════

```

---

## المُدخلات — Inputs

```text
// ١. المجموعة الترادفية (Synset - مُدخل المرحلة الأولى)
مجموعة_ترادفية = {
    synset_id،                           // معرّف المجموعة في قاعدة البيانات
    لمّات: [{
        entry_id،                        // معرّف المدخل المعجمي
        sense_id،                        // معرّف الحاسة (الربط بالمجموعة)
        written_form،                    // الصيغة الكتابية
        pos                              // نوع الكلمة
    }]،
    تعريف_عربي، تعريف_إنجليزي،
    pos،                                 // نوع الكلمة على مستوى المجموعة
    علاقات: [{
        relation_type،                   // hypernym / hyponym / ...
        target_synset_id
    }]
}

// ٢. الملف البحثي (مُخرج المرحلة الأولى)
الملف_البحثي = {
    توثيق:           لمّة → {عدد_المعاجم، الفترات_الزمنية}
    تعريفات:         لمّة → [{مصدر، نص، مطابق، تشويش}]
    عائلة_الجذر:     {جذر، مشتقات، مرشحات}
    شواهد:           لمّة → [{نوع، نص، بالمعنى المقصود}]
    تطور_زمني:       لمّة → {تصنيف}
    مرشحات_المرادف:  [{كلمة، المصدر، ملاحظة}]
    arabterm:         [{مصطلح_عربي، مصطلح_أجنبي، المجال، تهجئة_بديلة}]
}

// ٣. سجل العمليات (يُملأ تراكمياً خلال الخطوات ٠–٥)
action_queue = []    // قائمة مرتّبة من العمليات المعلّقة

```

## المُخرج — Output

```text
١. ملف YAML نهائي جاهز للمراجعة (يحتوي سجل العمليات + التقييم)
٢. سجل عمليات (action_queue) قابل للتنفيذ على واجهة البرمجة

```

---

## الخوارزمية

```text
لكل مجموعة_ترادفية نفّذ

    // تهيئة سجل العمليات
    action_queue ⟵ []

    // ══════════════════════════════════════════════
    // الخطوة ٠: استخلاص الأدلة المعجمية (Dictionary Evidence Extraction)
    // ══════════════════════════════════════════════

    لكل لمّة في مجموعة_ترادفية.لمّات نفّذ

        // استخلص من جميع النصوص المعجمية في الملف البحثي ما يتعلق بمعنى اللمّة
        // قارن الأدلة بتعريف المجموعة الترادفية (synset definition)
        // ملاحظة: التصنيفات الثلاثة (confirm/contradicts/expands) غير حصرية —
        // نص واحد قد ينتمي لأكثر من قائمة في آن واحد

        لكل نص_معجمي في الملف_البحثي.تعريفات(لمّة) نفّذ

            إذا نص_معجمي يؤكّد المعنى الدلالي للمّة بالنسبة لتعريف المجموعة فـ
                ▸ أضف_إلى(لمّة.confirm، نص_معجمي + المصدر)
            نهاية

            إذا نص_معجمي يناقض المعنى الدلالي أو يُضيّقه أو يُبعده عن تعريف المجموعة فـ
                ▸ أضف_إلى(لمّة.contradicts، نص_معجمي + المصدر + وجه_التناقض)
            نهاية

            إذا نص_معجمي يوسّع المعنى أو يضيف بعداً دلالياً غير موجود في تعريف المجموعة فـ
                ▸ أضف_إلى(لمّة.expands، نص_معجمي + المصدر + الإضافة_الدلالية)
            نهاية

            // ── ملاحظات هامشية (Peripheral Observations) ──
            // إذا ذكر النص المعجمي معنىً مستقلاً لا ينتمي لتعريف المجموعة
            // ولا يُصنَّف ضمن confirm أو contradicts أو expands:
            إذا نص_معجمي يذكر معنىً مستقلاً تماماً عن مفهوم المجموعة فـ
                ▸ أضف_إلى(peripheral_observations، {
                    لمّة، المعنى_الملاحَظ، المصدر، رقم_الخطوة، ملاحظة
                })
            نهاية

        نهاية  // لكل نص معجمي

        // التحقق من وجود أدلة
        إذا لمّة.confirm فارغ و لمّة.contradicts فارغ و لمّة.expands فارغ فـ
            ▸ عيّن(لمّة.evidence_status، "no_material_found")
            // اللمّة بلا سند معجمي — إشارة تحذيرية للخطوات اللاحقة
        نهاية

        // سجّل النتيجة في بنية YAML
        ▸ املأ(yaml.lemmas[لمّة].confirm)
        ▸ املأ(yaml.lemmas[لمّة].contradicts)
        ▸ املأ(yaml.lemmas[لمّة].expands)
        ▸ املأ(yaml.lemmas[لمّة].evidence_status)

    نهاية  // لكل لمّة — استخلاص الأدلة


    // ══════════════════════════════════════════════
    // الخطوة ١: التحقق من اللمّات (Lemma Validation)
    // ══════════════════════════════════════════════

    لكل لمّة في مجموعة_ترادفية.لمّات نفّذ

        // ── قراءة أدلة الخطوة ٠ ──

        // حالة ١: لا سند معجمي — حكم اللغوي
        // (قرارات اللغوي تُوثَّق عبر add_nuance_note — هي آلية التوثيق المعتمدة لضمان قابلية المراجعة)
        إذا لمّة.evidence_status = "no_material_found" فـ
            // لا أدلة معجمية — يرجع القرار للمعرفة اللغوية للمراجع
            // (في التشغيل الآلي: semantic_similarity(لمّة، تعريف_المجموعة) > عتبة)
            إذا اللغوي يرى أن اللمّة مرتبطة دلالياً بتعريف المجموعة (بناءً على معرفته) فـ
                ▸ add_nuance_note(لمّة، "لا سند معجمي — مقبولة بحكم اللغوي")
                // أكمل الفحوصات أدناه
            وإلا
                ▸ reject_lemma(لمّة)
                ▸ add_nuance_note(لمّة، "لا سند معجمي ولا ارتباط دلالي بتعريف المجموعة")
                انتقل_للمّة_التالية
            نهاية
        نهاية

        // حالة ٢: يوجد تناقض — تشخيص مصدر التناقض
        إذا لمّة.contradicts غير_فارغ فـ
            إذا التناقض مصدره أن اللمّة تحمل معنى مختلفاً عن تعريف المجموعة فـ
                // اللمّة في المكان الخطأ — اختبار الإبدال سيؤكد
                ▸ add_nuance_note(لمّة، "تناقض: المعنى المعجمي يختلف عن تعريف المجموعة")
            وإلا إذا التناقض مصدره أن تعريف المجموعة ضيّق أو خاطئ فـ
                // المشكلة في التعريف لا في اللمّة — إشارة للخطوة ٣
                ▸ add_nuance_note(لمّة، "تناقض: تعريف المجموعة يحتاج مراجعة")
                ▸ flag_definition_review()
            وإلا إذا التناقض مصدره تعدد معاني اللمّة (Polysemy) فـ
                // اللمّة لها معنى مطابق ومعنى مختلف — تحتاج فصلاً
                ▸ flag_split_needed()
                ▸ add_nuance_note(لمّة، "تناقض: تعدد معانٍ — تحقق من المعنى المقصود")
            نهاية
        نهاية

        // حالة ٣: يوجد توسيع — تقييم طبيعة التوسيع
        إذا لمّة.expands غير_فارغ فـ
            إذا التوسيع يمثل معنى مستقلاً لا يندرج تحت تعريف المجموعة فـ
                ▸ flag_split_needed()
                ▸ add_nuance_note(لمّة، "توسيع: معنى إضافي قد يستحق مجموعة ترادفية مستقلة")
            وإلا
                // التوسيع فارق دقيق يُغني المجموعة
                ▸ add_nuance_note(لمّة، "توسيع: بُعد دلالي إضافي — " + الإضافة_الدلالية)
            نهاية
        نهاية

        // حالة ٤: تأكيد فقط — مسار سريع
        // (لمّة.confirm غير فارغ ولا تناقض ولا توسيع — الأدلة تدعم الانتماء)

        // ── الفحوصات الأصلية (تستفيد الآن من الأدلة أعلاه) ──

        // أ٠. التعابير متعددة الكلمات (Multi-Word Expressions)
        // بعض المفاهيم مركبة بطبيعتها (مثل: احتباس حراري، ذكاء اصطناعي)
        // تُعامَل كلمّات أساسية لا كحالات شاذة
        إذا لمّة تعبير_مركب (MWE) فـ
            إذا التركيب اصطلاحي_مستقر ويحمل معنى وحدوياً لا تركيبياً فـ
                ▸ accept_mwe(لمّة)
                // يُمرَّر لاختبار الإبدال أدناه كوحدة واحدة
            وإلا
                // تركيب عرضي — ليس وحدة معجمية
                ▸ reject_lemma(لمّة)
                ▸ add_nuance_note(لمّة، "تركيب غير اصطلاحي — ليس وحدة معجمية")
                انتقل_للمّة_التالية
            نهاية
        نهاية

        // أ٫١. كشف الألفاظ اللهجية (Dialectal Forms)
        إذا لمّة لفظ_لهجي_لا_فصيح فـ
            ▸ remove_dialectal(لمّة)
            انتقل_للمّة_التالية
        نهاية

        // أ. اختبار الإبدال (Substitution Test) ← انظر الإجراء الفرعي اختبار_الإبدال()
        إذا اختبار_الإبدال(لمّة، أخوات_المجموعة) = نجاح فـ
            مرادفة ⟵ صحيح
        وإلا
            ▸ reject_lemma(لمّة)
            انتقل_للمّة_التالية
        نهاية

        // ب. مبدأ منع الترادف التام (No Absolute Synonymy)
        ▸ add_nuance_note(لمّة، الفارق_الذي_يميزها_عن_أخواتها)   // إلزامي دائماً

        // ج. اللفظ المختص أولى
        // (اللفظ الأخصّ يجتاز اختبار الإبدال ضمنياً — الأخصية تستلزم الإبدال في سياق المفهوم المحدد)
        إذا يوجد_لفظ_أخصّ_من(لمّة) للمفهوم فـ
            ▸ remove_lemma(لمّة)
            ▸ add_lemma(اللفظ_الأخصّ)
        نهاية

        // د. كشف الترجمة الحرفية والمعرّب (Calques & Loanwords)
        إذا لمّة تركيب_أعجمي_البنية (مثل: مطر ثقيل بدل غزير) فـ
            ▸ remove_calque(لمّة)
            إذا المقابل_العربي_الأصيل غير_موجود في لمّات_المجموعة فـ
                ▸ add_lemma(المقابل_العربي_الأصيل)
            نهاية
            انتقل_للمّة_التالية
        وإلا إذا لمّة لفظ_دخيل_أو_معرّب ومُقرّ مجمعياً أو شائع علمياً فـ
            ▸ accept_loanword(لمّة)
            ▸ add_enrichment(لمّة، eloquence="neologism/loanword")
        نهاية

        // ز. القرار النهائي للمة (مُعزَّز بأدلة الخطوة ٠)
        //
        // الحالات الممكنة عند الوصول هنا:
        //   أ) confirm فقط (لا تناقض ولا توسيع)
        //   ب) confirm + contradicts (أدلة متضاربة)
        //   ج) confirm + expands أو expands فقط (معنى أوسع)
        //   د) no_material_found لكن اللغوي وافق (confirm و contradicts فارغان)
        //   هـ) contradicts فقط (وصلت رغم التناقض — نجحت في الإبدال)

        // ── أولاً: فحص الانزياح الزمني (ينطبق على كل حالة فيها أدلة) ──
        إذا لمّة.confirm غير_فارغ و يوجد انزياح_زمني (Semantic shift) فـ
            ▸ confirm(لمّة)
            ▸ nuance_note(لمّة، "period restriction")
            ▸ add_enrichment(لمّة، usage_note="المعنى تطوّر عبر العصور")
            انتقل_للمّة_التالية
        نهاية

        // ── ثانياً: فحص الكلمة المولّدة (ينطبق على كل الحالات) ──
        إذا الكلمة مولّدة بلا_أصل_كلاسيكي فـ
            ▸ confirm(لمّة)
            ▸ add_enrichment(لمّة، usage="modern")
            انتقل_للمّة_التالية
        نهاية

        // ── ثالثاً: القرار حسب حالة الأدلة ──

        // (أ) أدلة مؤكدة بلا تناقض
        إذا لمّة.confirm غير_فارغ و لمّة.contradicts فارغ فـ
            ▸ confirm(لمّة)

        // (ب) أدلة متضاربة — يعتمد على وزن الأدلة
        وإلا إذا لمّة.confirm غير_فارغ و لمّة.contradicts غير_فارغ فـ
            إذا أدلة_التأكيد أقوى (أكثر مصادر أو أحدث) فـ
                ▸ confirm(لمّة)
                ▸ nuance_note(لمّة، "تأكيد مع تحفظ — بعض المصادر تخالف")
            وإلا
                ▸ escalate()   // تعارض حقيقي يحتاج مراجعاً بشرياً
            نهاية

        // (ج) توسيع فقط بلا تأكيد صريح — الأدلة توسّع لا تؤكد
        وإلا إذا لمّة.expands غير_فارغ و لمّة.confirm فارغ و لمّة.contradicts فارغ فـ
            // المعاجم تذكر اللمّة بمعنى أوسع من تعريف المجموعة
            // اللمّة صالحة لكن تعريف المجموعة قد يحتاج توسيعاً
            ▸ confirm(لمّة)
            ▸ nuance_note(لمّة، "الأدلة المعجمية توسّع المعنى — تحقق من نطاق التعريف")

        // (د) لا أدلة معجمية لكن اللغوي وافق في حالة ١
        وإلا إذا لمّة.evidence_status = "no_material_found" فـ
            // وصلت هنا لأن اللغوي رأى ارتباطاً دلالياً ونجحت في الإبدال
            ▸ confirm(لمّة)
            ▸ nuance_note(لمّة، "مقبولة بحكم اللغوي — بلا سند معجمي مباشر")

        // (هـ) تناقض فقط بلا تأكيد — وصلت رغم ذلك (نجحت في الإبدال)
        وإلا إذا لمّة.contradicts غير_فارغ و لمّة.confirm فارغ فـ
            ▸ escalate()   // الإبدال نجح لكن المعاجم تخالف — يحتاج حسماً بشرياً

        // لم تنطبق أي حالة — رفض
        وإلا
            ▸ reject_lemma(لمّة)
        نهاية

    نهاية  // نهاية التحقق من اللمّات




    // ══════════════════════════════════════════════
    // الخطوة ٣: تدقيق وتأليف التعريف (Definition Processing)
    // ══════════════════════════════════════════════

    // ── استهلاك إشارة flag_definition_review من الخطوة ١ ──
    إذا flag_definition_review مرفوع فـ
        // أدلة الخطوة ٠ أظهرت أن التعريف ضيّق أو خاطئ — المراجعة إلزامية
        ▸ revise_definition()
    وإلا إذا تعريف_AWN يطابق المعاجم فـ
        ▸ retain_definition()
    وإلا إذا التعريف_الكلاسيكي أوسع فـ
        ▸ nuance_note("scope"، الفرق)
    وإلا إذا تعريف_AWN أدق_علمياً فـ
        ▸ retain_definition()   // إعطاء الأولوية للدقة العلمية
    وإلا
        ▸ revise_definition()
    نهاية

    // تأليف التعريفات (فقط إذا كان التعريف يحتاج مراجعة أو تأليفاً)
    إذا revise_definition تم_استدعاؤه أو لا_يوجد_تعريف_عربي فـ
        ▸ ألّف_تعريفاً_مصطلحياً()              // ← انظر الإجراء الفرعي أدناه
        إذا المفهوم بسيط_محسوس أو مجرد أو فعل فـ
            ▸ ألّف_تعريفاً_لغوياً()            // ← انظر الإجراء الفرعي أدناه
        نهاية
        إذا المفهوم حيوان أو نبات أو أداة أو مفهوم_ثقافي_معقد فـ
            ▸ ألّف_تعريفاً_موسوعياً()
        نهاية

        // فحص الجودة
        لكل تعريف في التعريفات_المؤلَّفة نفّذ
            ▸ تحقق_جودة(تعريف)                 // ← انظر الإجراء الفرعي أدناه
        نهاية
    نهاية


    // ══════════════════════════════════════════════
    // الخطوة ٤: فحص العلاقات (Relations Check)
    // ══════════════════════════════════════════════

    // ── اختبار التعميم (Hypernymy) ──
    // البحث في الشجرة الدلالية محدود بعمق ٣ مستويات لتقييد نطاق المقارنة
    إذا "X هو فعلاً نوع من Y" فـ
        ▸ relations_ok()
    وإلا إذا "X نوع من Y تقنياً لكن يوجد أعم أقرب" فـ
        ▸ flag_relation(اقتراح = الأعم_الأقرب)
    وإلا
        ▸ flag_relation(خطأ_في_التسلسل)
    نهاية

    // ── اختبار التضاد (Antonymy) ──
    // التضاد علاقة محورية خاصة في الأفعال والصفات
    لكل لمّة في اللمّات_المؤكدة نفّذ
        إذا يوجد ضد_مباشر للمّة في الملف_البحثي أو الشبكة الدلالية فـ
            إذا علاقة_التضاد مسجّلة_بالفعل في علاقات_المجموعة فـ
                ▸ relations_ok()
            وإلا
                ▸ add_relation(لمّة، "antonym"، الضد)
            نهاية
        نهاية
        // التضاد يساعد أيضاً في التحقق: إذا ضد اللمّة = مرادف آخر في نفس المجموعة
        // فهذا دليل على خلط دلالي
        إذا ضد_اللمّة موجود_في نفس_المجموعة فـ
            ▸ flag_split_needed()
            ▸ add_nuance_note(لمّة، "تضاد داخلي: اللمّة وضدها في نفس المجموعة")
        نهاية
    نهاية

    // ── فحوصات إضافية تخص الأفعال ──
    إذا لمّة.نوع = فعل فـ
        إذا الفعل يتعدى_بحرف فـ
            ▸ add_syntactic_frame(لمّة، "متعدٍ بـ " + الحرف)
        نهاية
        إذا خلط بين مصدر واسم_فاعل في نفس المجموعة فـ
            ▸ flag_split_needed()
        نهاية
    نهاية

    إذا الكلمة تتطلب فاعلاً عاقلاً/حيّاً/جماداً فـ
        ▸ add_nuance_note(لمّة، القيد_الدلالي)
    نهاية


    // ══════════════════════════════════════════════
    // الخطوة ٥: البيانات القابلة للتخزين في WordNet والملاءمة الثقافية
    // ══════════════════════════════════════════════
    // أنتج فقط الحقول التي لها مكان في بنية WN-LMF:
    //   root، figurative_relation، etymology، examples، morphology، pos_check، cultural_fit
    // لا تُنتج: usage، eloquence، connotation، literal_figurative، collocations

    لكل لمّة في اللمّات_المؤكدة_والمضافة نفّذ

        // ── الجذر ──
        ▸ أكّد_أو_صحّح(لمّة.root)

        // ── العلاقة المجازية (→ SenseRelation metaphor/metonym) ──
        // استهلك بيانات التوسيع من الخطوة ٠ + النص المعجمي
        إذا لمّة.expands غير_فارغ فـ
            لكل توسيع في لمّة.expands نفّذ
                إذا توسيع يتعلق بالمجاز فـ ▸ عيّن(لمّة.figurative_relation)
                إذا توسيع يتعلق بقيد تركيبي فـ ▸ add_syntactic_frame(لمّة، الإطار_المستخلص)
            نهاية
        نهاية

        لكل نص_معجمي في الملف_البحثي.تعريفات(لمّة) نفّذ
            إذا نص يحتوي "من المجاز" أو "يُستعار لـ" فـ ▸ عيّن(لمّة.figurative_relation)
            إذا نص يحتوي نمط "فَعَلَ كذا بكذا" فـ ▸ add_syntactic_frame(الإطار)
        نهاية

        // ── أصل الكلمة (→ metadata etymology) ──
        إذا اللمّة مقترضة (loanword) فـ ▸ عيّن(لمّة.etymology، "loanword")

        // ── الشواهد والأمثلة (→ Example elements) — إلزامي: مثال واحد على الأقل لكل لمّة ──
        // ابحث في ثلاثة مصادر بالترتيب التنازلي. لا يجوز ترك لمّة بدون مثال.

        // المصدر ١: أمثلة مهيكلة من قاعدة البيانات (examples_evidence / step6_examples)
        إذا examples_evidence[لمّة] يحتوي شواهد (result_count > 0) فـ
            اختر أفضل شاهد (الأولوية: قرآن > حديث > شعر > نثر > استعمال)
            ▸ add_example(لمّة، الشاهد، النوع، المصدر)

        // المصدر ٢: اقتباسات المعاجم من أدلة الخطوة ٠ (confirm / expands)
        وإلا إذا أدلة الخطوة ٠ (confirm أو expands) تتضمن:
             — آية قرآنية (علامة: ﴿...﴾ أو «قال تعالى»)
             — حديثاً نبوياً (علامة: «في الحديث» أو «عن النبي ﷺ»)
             — بيت شعر (علامة: وزن عروضي أو «قال الشاعر»)
             — مثالاً نثرياً يوضح الاستعمال (علامة: «يُقال:» أو جملة اصطلاحية)
        فـ
            استخلص الشاهد من النص المعجمي (النص فقط — بدون الشرح المحيط به)
            ▸ add_example(لمّة، الشاهد_المستخلص، النوع، اسم_المعجم)

        // المصدر ٣: تأليف مثال (الملاذ الأخير)
        وإلا فـ
            ▸ ألّف_مثالاً_طبيعياً(لمّة) — جملة فصيحة معاصرة تُظهر الاستعمال في سياق واضح
            ▸ add_example(لمّة، المثال_المؤلف، "usage"، "مؤلَّف")
        نهاية

        // ── التحقق الصرفي (→ SenseRelation derivation، update_lemma) ──
        إذا لمّة جمع_تكسير مدرج_كلمة_مستقلة فـ ▸ link_broken_plural(لمّة، المفرد)
        إذا الجذر_المُستنتج ≠ الشواهد فـ ▸ correct_root(لمّة، الجذر_الصحيح)

        // ── إرشادات حسب نوع الكلمة (→ partOfSpeech، SyntacticBehaviour) ──
        إذا لمّة.نوع = اسم فـ
            إذا خلط بين مَأْل ≠ مال فـ ▸ modify_lemma_form(لمّة، الصيغة_الصحيحة)
            إذا خلط مصدر باسم_ذات فـ ▸ flag_pos_mismatch()
        وإلا إذا لمّة.نوع = فعل فـ
            ▸ عيّن(لمّة.syntactic_frame)   // لازم / متعدٍ بنفسه / متعدٍ بـ حرف
            إذا حرف_الجر يغيّر المعنى فـ ▸ add_nuance_note(لمّة، الحرف + المعنى)
        وإلا إذا لمّة.نوع = صفة فـ
            إذا تركيب "صفة + جداً" فـ ▸ modify_lemma_form(لمّة، صيغة_المبالغة)
        وإلا إذا لمّة.نوع = ظرف فـ
            إذا اللمّة جار_ومجرور أو حال تؤدي معنى الظرف فـ
                ▸ accept_as_adverb(لمّة) // للحفاظ على توافق WordNet العالمي
            وإلا
                ▸ flag_pos_mismatch()
            نهاية
        نهاية

    نهاية  // لكل لمّة

    // ── الملاءمة الثقافية (→ synset metadata) ──
    إذا المفهوم لا_مقابل_مفرد في العربية فـ
        إذا يمكن التعبير بتعبير_اصطلاحي فـ
            ▸ add_phraset()
            ▸ عيّن(cultural_fit.lexical_gap_type = "phraset")
        وإلا
            ▸ flag_lexical_gap()
            ▸ عيّن(cultural_fit.lexical_gap_type = "lexical_gap")
        نهاية
    وإلا إذا المفهوم لا_صلة_بالسياق_العربي فـ
        ▸ flag_omission()
        ▸ عيّن(cultural_fit.lexical_gap_type = "omission")
    نهاية

    إذا التصنيف_الثقافي_الحالي خاطئ فـ ▸ reclassify_cultural()


    // ══════════════════════════════════════════════════════════
    // الخطوة ٦: التجميع والمراجعة والتنفيذ (Compile, Review, Execute)
    // ══════════════════════════════════════════════════════════

    // ──────────────────────────────────────────────
    // ٦.أ: تجميع YAML + التقييم (كما كان)
    // ──────────────────────────────────────────────

    ▸ املأ(yaml.analysis)
    ▸ املأ(yaml.definition)
    ▸ املأ(yaml.authored_definitions)
    ▸ املأ(yaml.lemmas)
    ▸ املأ(yaml.missing_lemmas)
    ▸ املأ(yaml.relations)
    ▸ املأ(yaml.cultural_fit)
    ▸ املأ(yaml.peripheral_observations)

    إذا لا_شواهد_حقيقية في الملف_البحثي فـ ▸ add_example()
    ▸ املأ(yaml.examples)

    // التقييم الشامل — المعايير التفصيلية (rubrics) في دليل التقييم المرفق
    ▸ قيّم(semantic_accuracy)        // 0–3
    ▸ قيّم(gloss_quality)            // 0–3
    ▸ قيّم(synonym_coherence)        // 0–2
    ▸ قيّم(completeness)             // 0–2
    ▸ قيّم(cultural_adequacy)        // direct / near_synonym / phraset / gap

    // الأعلام والتصعيد
    لكل قرار_مشكوك_فيه نفّذ ▸ أضف_علَم(العلَم_المناسب)
    إذا عدم_يقين أو تعارض_شواهد_لا_يمكن_حسمه فـ ▸ escalate()

    ▸ جمّع(yaml.actions)             // تحويل الإجراءات (▸) إلى سجل Actions
    ▸ قيّم(yaml.overall)             // excellent / good / acceptable / poor

    // ──────────────────────────────────────────────
    // ٦.ب: ترجمة سجل العمليات إلى استدعاءات API
    // ──────────────────────────────────────────────
    //
    // ترتيب التنفيذ مهم — المراحل تُنفَّذ بالتسلسل:
    //   المرحلة ١: عمليات الحذف (إزالة الحواس والمداخل)
    //   المرحلة ٢: تعديل الصيغ والتعريفات
    //   المرحلة ٣: إنشاء مجموعات ومداخل وحواس جديدة
    //   المرحلة ٤: تعديل العلاقات
    //   المرحلة ٥: الإثراء (البيانات الوصفية)
    //   المرحلة ٦: التقييم والثقة

    // ════════════════════════════════════════
    // المرحلة ١: الحذف — Removals
    // ════════════════════════════════════════

    لكل عملية في action_queue حيث عملية.نوع ∈ {reject_lemma, remove_lemma, remove_calque, remove_dialectal} نفّذ

        // reject_lemma / remove_lemma / remove_calque → إزالة الحاسة
        ⊕ remove_sense(عملية.sense_id)
        // ملاحظة: المدخل (Entry) يبقى — قد ينتمي لمجموعات أخرى

    نهاية

    // ════════════════════════════════════════
    // المرحلة ٢: التعديلات — Modifications
    // ════════════════════════════════════════

    لكل عملية في action_queue حيث عملية.نوع = modify_lemma_form نفّذ
        ⊕ update_lemma(عملية.entry_id, عملية.new_form)
    نهاية

    لكل عملية في action_queue حيث عملية.نوع = revise_definition نفّذ
        ⊕ update_definition(عملية.synset_id, 0, عملية.new_text)
    نهاية

    لكل عملية في action_queue حيث عملية.نوع = flag_pos_mismatch نفّذ
        إذا الخطأ في المدخل فـ
            ⊕ update_entry(عملية.entry_id, pos=عملية.correct_pos)
        وإلا   // الخطأ في المجموعة
            ⊕ update_synset(عملية.synset_id, pos=عملية.correct_pos)
        نهاية
    نهاية

    // ════════════════════════════════════════
    // المرحلة ٣: الإنشاء — Creations
    // ════════════════════════════════════════

    // ── إضافة لمّة (مرادف جديد) ──
    لكل عملية في action_queue حيث عملية.نوع = add_lemma نفّذ

        // الخطوة أ: أوجد أو أنشئ المدخل
        entry_id ⟵ lookup_entry(عملية.written_form, عملية.pos)
        إذا entry_id فارغ فـ
            ⊕ entry_id ⟵ create_entry(lexicon_id, عملية.written_form, عملية.pos)
        نهاية

        // الخطوة ب: اربط بالمجموعة
        ⊕ add_sense(entry_id, عملية.synset_id)

    نهاية

    // ── إضافة تهجئة بديلة ──
    لكل عملية في action_queue حيث عملية.نوع = add_variant_form نفّذ
        ⊕ add_form(عملية.parent_entry_id, عملية.written_form)
    نهاية

    // ── إنشاء مجموعة ترادفية جديدة (Synset Split / Hyponym) ──
    لكل عملية في action_queue حيث عملية.نوع = propose_new_synset نفّذ

        // الخطوة أ: أنشئ المجموعة
        ⊕ new_synset_id ⟵ create_synset(lexicon_id, عملية.pos, عملية.definition)

        // الخطوة ب: أنشئ المدخل والحاسة
        entry_id ⟵ lookup_entry(عملية.written_form, عملية.pos)
        إذا entry_id فارغ فـ
            ⊕ entry_id ⟵ create_entry(lexicon_id, عملية.written_form, عملية.pos)
        نهاية
        ⊕ add_sense(entry_id, new_synset_id)

        // الخطوة ج: اربط بالمجموعة الأم (hyponym)
        ⊕ add_synset_relation(new_synset_id, "hypernym", عملية.parent_synset_id)

        // الخطوة د: التعريف
        ⊕ add_definition(new_synset_id, عملية.definition)

        // الخطوة هـ: ربط ILI (اختياري)
        إذا يوجد ili_id مطابق فـ
            ⊕ link_ili(new_synset_id, عملية.ili_id)
        وإلا إذا يُقترح ILI جديد فـ
            ⊕ propose_ili(new_synset_id, عملية.ili_definition)
        نهاية

    نهاية

    // ── فصل المجموعة (Split) ──
    لكل عملية في action_queue حيث عملية.نوع = flag_split_needed نفّذ

        // الخطوة أ: أنشئ المجموعة الجديدة
        ⊕ new_synset_id ⟵ create_synset(lexicon_id, عملية.pos, عملية.split_definition)
        ⊕ add_definition(new_synset_id, عملية.split_definition)

        // الخطوة ب: انقل الحواس المعنية
        لكل sense_id في عملية.senses_to_move نفّذ
            ⊕ move_sense(sense_id, new_synset_id)
        نهاية

        // الخطوة ج: علاقة الأصل
        ⊕ add_synset_relation(new_synset_id, "hypernym", عملية.parent_synset_id)

    نهاية

    // ── تأليف التعريفات ──
    لكل عملية في action_queue حيث عملية.نوع = author_definition نفّذ
        ⊕ add_definition(عملية.synset_id, عملية.text)
    نهاية

    // ── إضافة تعبير اصطلاحي (Phraset) ──
    لكل عملية في action_queue حيث عملية.نوع = add_phraset نفّذ
        ⊕ entry_id ⟵ create_entry(lexicon_id, عملية.phraset_text, عملية.pos)
        ⊕ add_sense(entry_id, عملية.synset_id)
    نهاية

    // ── إضافة أمثلة ──
    لكل عملية في action_queue حيث عملية.نوع = add_example نفّذ
        إذا عملية.level = "synset" فـ
            ⊕ add_synset_example(عملية.synset_id, عملية.text)
        وإلا
            ⊕ add_sense_example(عملية.sense_id, عملية.text)
        نهاية
    نهاية

    // ════════════════════════════════════════
    // المرحلة ٤: العلاقات — Relations
    // ════════════════════════════════════════

    لكل عملية في action_queue حيث عملية.نوع = flag_relation نفّذ

        // إزالة العلاقة الخاطئة
        ⊕ remove_synset_relation(
            عملية.synset_id,
            عملية.old_relation_type,
            عملية.old_target_id
        )

        // إضافة العلاقة الصحيحة
        ⊕ add_synset_relation(
            عملية.synset_id,
            عملية.new_relation_type,
            عملية.new_target_id
        )

    نهاية

    // ربط جمع التكسير
    لكل عملية في action_queue حيث عملية.نوع = link_broken_plural نفّذ
        ⊕ add_sense_relation(
            عملية.plural_sense_id,
            "derivation",
            عملية.singular_sense_id
        )
    نهاية

    // ════════════════════════════════════════
    // المرحلة ٥: الإثراء — Metadata & Enrichment
    // ════════════════════════════════════════

    لكل عملية في action_queue حيث عملية.نوع = add_enrichment نفّذ
        // كل حقل إثراء = مفتاح metadata على الحاسة (Sense)
        لكل (مفتاح، قيمة) في عملية.fields نفّذ
            ⊕ set_metadata("sense", عملية.sense_id, مفتاح, قيمة)
        نهاية
    نهاية

    لكل عملية في action_queue حيث عملية.نوع = add_nuance_note نفّذ
        ⊕ set_metadata("sense", عملية.sense_id, "nuance", عملية.text)
    نهاية

    لكل عملية في action_queue حيث عملية.نوع = add_syntactic_frame نفّذ
        ⊕ set_metadata("sense", عملية.sense_id, "syntactic_frame", عملية.frame)
    نهاية

    لكل عملية في action_queue حيث عملية.نوع = add_collocation نفّذ
        ⊕ set_metadata("sense", عملية.sense_id, "collocation", عملية.text)
    نهاية

    لكل عملية في action_queue حيث عملية.نوع = correct_root نفّذ
        ⊕ set_metadata("entry", عملية.entry_id, "root", عملية.correct_root)
    نهاية

    لكل عملية في action_queue حيث عملية.نوع = accept_loanword نفّذ
        ⊕ set_metadata("entry", عملية.entry_id, "etymology", "loanword")
    نهاية

    // الملاءمة الثقافية
    لكل عملية في action_queue حيث عملية.نوع ∈ {flag_lexical_gap, flag_omission, reclassify_cultural} نفّذ
        ⊕ set_metadata("synset", عملية.synset_id, "cultural_fit", عملية.classification)
    نهاية

    // التصعيد
    لكل عملية في action_queue حيث عملية.نوع = escalate نفّذ
        ⊕ set_metadata("synset", عملية.synset_id, "escalation", عملية.reason)
        ⊕ set_confidence("synset", عملية.synset_id, 0.0)
    نهاية

    // ════════════════════════════════════════
    // المرحلة ٦: التقييم والثقة — Evaluation & Confidence
    // ════════════════════════════════════════

    // تخزين التقييمات التفصيلية كـ metadata
    ⊕ set_metadata("synset", synset_id, "semantic_accuracy", yaml.eval.semantic_accuracy)
    ⊕ set_metadata("synset", synset_id, "gloss_quality", yaml.eval.gloss_quality)
    ⊕ set_metadata("synset", synset_id, "synonym_coherence", yaml.eval.synonym_coherence)
    ⊕ set_metadata("synset", synset_id, "completeness", yaml.eval.completeness)
    ⊕ set_metadata("synset", synset_id, "cultural_adequacy", yaml.eval.cultural_adequacy)
    ⊕ set_metadata("synset", synset_id, "overall", yaml.eval.overall)

    // تخزين درجة الثقة الإجمالية (0.0–1.0)
    ⊕ set_confidence("synset", synset_id, normalize(yaml.eval.overall))

    // تأكيد الحواس المقبولة
    لكل عملية في action_queue حيث عملية.نوع = confirm نفّذ
        ⊕ set_confidence("sense", عملية.sense_id, 1.0)
    نهاية

نهاية  // لكل مجموعة ترادفية

```

---

## الإجراءات الفرعية (Sub-routines)

### ألّف_تعريفاً_مصطلحياً()

```text
دالة ألّف_تعريفاً_مصطلحياً():
    // البنية: [الجنس القريب] + [الفصل النوعي]
    الجنس ⟵ تعريف_المجموعة_الأعم(hypernym)
    الفصل ⟵ ما_يميّز_عن_الأشقاء(co-hyponyms)
    التعريف ⟵ الجنس + الفصل
    ▸ تحقق_جودة(التعريف)
    أعد التعريف
نهاية_الدالة

```

### ألّف_تعريفاً_لغوياً()

```text
دالة ألّف_تعريفاً_لغوياً():
    إذا يوجد مرادف مباشر في الملف_البحثي فـ النمط ⟵ "synonym"
    وإلا إذا التعريف_بالنقيض أوضح فـ النمط ⟵ "antonym"
    وإلا إذا التعريف_بالمثال أوضح فـ النمط ⟵ "example"
    وإلا إذا الاشتقاق يوضّح المعنى فـ النمط ⟵ "derivation"
    وإلا النمط ⟵ "context"
    نهاية

    التعريف ⟵ صِغ_حسب_النمط(النمط، الملف_البحثي)
    ▸ تحقق_جودة(التعريف)
    أعد التعريف
نهاية_الدالة

```

### تحقق_جودة(تعريف)

```text
دالة تحقق_جودة(تعريف):
    // شروط الجودة الخمسة
    إذا التعريف غامض فـ ▸ أعد_الصياغة(clarity)
    إذا فيه كلمات زائدة فـ ▸ احذف_الزائد(conciseness)
    إذا أوسع أو أضيق من المفهوم فـ ▸ اضبط_النطاق(equivalence)
    إذا يعرّف بالنفي فـ ▸ أعد_صياغة_إيجابية(positive)
    إذا يحتوي لفظ المعرَّف نفسه فـ ▸ أزل_الدور(no_tautology)

    // العيوب الستة
    إذا الجنس يكرّر ما فيه ضمنياً فـ ▸ احذف_الحشو()
    إذا الجنس بعيد جداً فـ ▸ استخدم_الجنس_القريب()
    إذا التعريف أغرب من المعرَّف فـ ▸ بسّط()
    إذا A يُعرَّف بـ B و B بـ A فـ ▸ عرّف_بخصائص_مستقلة()
    إذا إحالات متسلسلة فـ ▸ عرّف_مباشرة()
    إذا لفظ مشترك بلا تمييز فـ ▸ أضف_قيداً_مميزاً()
نهاية_الدالة

```

### اختبار_الإبدال(لمّة، أخوات)

```text
دالة اختبار_الإبدال(لمّة، أخوات):
    // المبدأ: اللمّة تصلح مرادفاً إذا أمكن إبدالها بأخواتها في سياقات طبيعية
    // دون تغيير جوهري في المعنى المقصود.

    // ١. نوع السياقات: نثر فصيح معاصر (لا شعر ولا نصوص متخصصة حصراً)
    // ٢. طريقة الاختبار: ضع اللمّة في جملة طبيعية، ثم أبدلها بكل أخت —
    //    هل يبقى المعنى الجوهري محفوظاً؟
    // ٣. معيار النجاح: الإبدال يحفظ المعنى الجوهري وإن اختلفت الظلال الدلالية.
    //    الفوارق في المستوى (فصيح/محايد) أو الإيحاء (إيجابي/سلبي) لا تُفشل الاختبار
    //    بل تُوثَّق في nuance_note.
    // ٤. معيار الفشل: الإبدال يُغيّر المعنى المقصود أو يُنتج جملة غير مقبولة لغوياً.

    لكل أخت في أخوات نفّذ
        إذا إبدال(لمّة، أخت) يحفظ المعنى الجوهري فـ
            استمر
        وإلا
            أعد فشل
        نهاية
    نهاية
    أعد نجاح
نهاية_الدالة

```

---

## فهرس إجراءات المرحلة الثانية (▸) → واجهة البرمجة (⊕)

### ١. أوامر التعديل (Modification)

| الإجراء | الوصف | API Call |
| --- | --- | --- |
| `▸ revise_definition()` | التعريف ركيك أو حرفي أو خاطئ البنية | `⊕ update_definition(synset_id, idx, text)` |
| `▸ modify_lemma_form()` | خطأ إملائي أو صرفي في اللمّة | `⊕ update_lemma(entry_id, new_form)` |
| `▸ add_diacritics()` | متجانسات إملائية تحتاج تمييزاً بالحركات | `⊕ update_lemma(entry_id, diacritized_form)` |
| `▸ correct_root()` | الجذر المستنتج من المرحلة 1 خاطئ | `⊕ set_metadata("entry", entry_id, "root", val)` |
| `▸ link_broken_plural()` | ربط جمع تكسير (مدرج ككلمة مستقلة) بمفرده | `⊕ add_sense_relation(plural, "derivation", singular)` |
| `▸ correct_relation()` | تصحيح علاقة hypernym/hyponym الخاطئة | `⊕ remove_synset_relation() → add_synset_relation()` |
| `▸ reclassify_cultural()` | تصنيف المحاذاة الثقافية كان خاطئاً | `⊕ set_metadata("synset", id, "cultural_fit", val)` |

### ٢. أوامر الإضافة (Addition)

| الإجراء | الوصف | API Call |
| --- | --- | --- |
| `▸ add_lemma()` | مرادف صالح غير موجود في المجموعة | `⊕ create_entry() → add_sense(entry_id, synset_id)` |
| `▸ accept_mwe()` | قبول تعبير مركب (MWE) كوحدة معجمية أساسية | `⊕ set_metadata("sense", id, "mwe", true)` |
| `▸ add_variant_form()` | تهجئة بديلة للمّة موجودة | `⊕ add_form(entry_id, written_form)` |
| `▸ add_relation()` | إضافة علاقة دلالية (antonym / hyponym) | `⊕ add_synset_relation() / add_sense_relation()` |
| `▸ accept_loanword()` | قبول كلمة معرّبة أو دخيلة متداولة | `⊕ set_metadata("entry", id, "etymology", "loanword")` |
| `▸ accept_as_adverb()` | قبول تركيب نحوي كـ "ظرف" للتوافق العالمي | `⊕ set_metadata("sense", id, "adverb_note", val)` |
| `▸ add_example()` | إضافة شاهد (عند غياب شواهد حقيقية) | `⊕ add_synset_example() / add_sense_example()` |
| `▸ author_definitions()` | تأليف تعريف (مصطلحي على الأقل) | `⊕ add_definition(synset_id, text)` |
| `▸ add_nuance_note()` | **إلزامي** — تحديد الفارق الدقيق لكل لمّة | `⊕ set_metadata("sense", id, "nuance", val)` |
| `▸ add_collocation()` | إضافة تلازم قوي يحدد أو يقيد المعنى | `⊕ set_metadata("sense", id, "collocation", val)` |
| `▸ add_syntactic_frame()` | للأفعال: تحديد حرف الجر الذي يضبط المعنى | `⊕ set_metadata("sense", id, "syntactic_frame", val)` |
| `▸ add_enrichment()` | تعبئة حقول: usage / eloquence / connotation | `⊕ set_metadata("sense", id, key, val)` per field |
| `▸ add_phraset()` | فجوة معجمية تُسدّ بتعبير اصطلاحي | `⊕ create_entry() → add_sense()` |

### ٣. أوامر الحذف (Removal)

| الإجراء | الوصف | API Call |
| --- | --- | --- |
| `▸ reject_lemma()` | اللمّة لا تحمل المعنى المقصود | `⊕ remove_sense(sense_id)` |
| `▸ remove_lemma()` | تفشل في اختبار الإبدال في كل السياقات | `⊕ remove_sense(sense_id)` |
| `▸ remove_calque()` | تركيب أعجمي البنية (ترجمة حرفية) | `⊕ remove_sense(sense_id)` |
| `▸ remove_dialectal()` | شكل لهجي بدلاً من الفصحى | `⊕ remove_sense(sense_id)` |
| `▸ flag_omission()` | مفهوم معجمي أجنبي لا صلة له بالسياق العربي | `⊕ set_metadata("synset", id, "cultural_fit", "omission")` |

### ٤. أوامر بنيوية وتقييمية (Structural & Eval)

| الإجراء | الوصف | API Call |
| --- | --- | --- |
| `▸ flag_lexical_gap()` | لا يوجد مقابل عربي مفرد لهذا المفهوم | `⊕ set_metadata("synset", id, "cultural_fit", "lexical_gap")` |
| `▸ flag_split_needed()` | المجموعة تخلط بين معاني متعددة | `⊕ create_synset() → move_sense() → add_synset_relation()` |
| `▸ flag_definition_review()` | أدلة الخطوة ٠ تشير إلى أن التعريف ضيّق أو خاطئ | إشارة داخلية — تُلزم الخطوة ٣ بالمراجعة |
| `▸ flag_pos_mismatch()` | اسم مصنّف كفعل، أو العكس | `⊕ update_entry(id, pos=) / update_synset(id, pos=)` |
| `▸ flag_relation(سبب)` | خطأ صريح في العلاقات الهرمية | `⊕ remove_synset_relation() → add_synset_relation()` |
| `▸ relations_ok()` | العلاقات الهرمية صحيحة ومنطقية | *(no-op)* |
| `▸ escalate()` | حالة معقدة يستدعي تدخل مراجع خبير | `⊕ set_metadata("synset", id, "escalation", reason)` + `⊕ set_confidence("synset", id, 0.0)` |
| `▸ confirm(لمّة)` | اللمّة صحيحة، مدعومة معجمياً | `⊕ set_confidence("sense", sense_id, 1.0)` |
| `▸ reject_candidate()` | المرشح المستخرج ليس مرادفاً حقيقياً | *(no-op — لم يُضف أصلاً)* |
| `▸ retain_definition()` | التعريف سليم ولا يحتاج تعديلاً | *(no-op)* |
| `▸ propose_new_synset()` | المرشح أخصّ دلالياً ويستحق مجموعة جديدة | `⊕ create_synset() → create_entry() → add_sense() → add_synset_relation()` |

---

## واجهة البرمجة — API Reference

### Synset (3 actions)

| # | Method | What it does |
|---|--------|--------------|
| 1 | `create_synset(lexicon_id, pos, definition, *, id, ili, ili_definition, lexicalized, metadata)` | Create a synset with its initial definition. |
| 2 | `update_synset(synset_id, *, pos, metadata)` | Update POS or metadata. |
| 3 | `delete_synset(synset_id, cascade)` | Delete a synset. With `cascade=True`, also deletes all attached senses. |

### Entry (4 actions)

| # | Method | What it does |
|---|--------|--------------|
| 4 | `create_entry(lexicon_id, lemma, pos, *, id, forms, metadata)` | Create a new lexical entry (word + POS). |
| 5 | `update_entry(entry_id, *, pos, metadata)` | Update POS or metadata. |
| 6 | `delete_entry(entry_id, cascade)` | Delete an entry. |
| 7 | `update_lemma(entry_id, new_lemma)` | Change the canonical written form of an entry. |

### Form (2 actions)

| # | Method | What it does |
|---|--------|--------------|
| 8 | `add_form(entry_id, written_form, *, id, script, tags)` | Add an inflected or variant written form. |
| 9 | `remove_form(entry_id, written_form)` | Remove a non-lemma form from an entry. |

### Sense (4 actions)

| # | Method | What it does |
|---|--------|--------------|
| 10 | `add_sense(entry_id, synset_id, *, id, lexicalized, adjposition, metadata)` | Link an entry to a synset. |
| 11 | `remove_sense(sense_id)` | Delete a sense and its relations, examples, and counts. |
| 12 | `move_sense(sense_id, target_synset_id)` | Move a sense to a different synset. |
| 13 | `reorder_senses(entry_id, sense_id_order)` | Set the ordering of senses within an entry. |

### Definition (3 actions)

| # | Method | What it does |
|---|--------|--------------|
| 14 | `add_definition(synset_id, text, *, language, source_sense, metadata)` | Add a definition to a synset. |
| 15 | `update_definition(synset_id, definition_index, text)` | Replace a definition's text by index. |
| 16 | `remove_definition(synset_id, definition_index)` | Remove a definition by index. |

### Example (4 actions)

| # | Method | What it does |
|---|--------|--------------|
| 17 | `add_synset_example(synset_id, text, *, language, metadata)` | Add a usage example to a synset. |
| 18 | `remove_synset_example(synset_id, example_index)` | Remove a synset example by index. |
| 19 | `add_sense_example(sense_id, text, *, language, metadata)` | Add a usage example to a sense. |
| 20 | `remove_sense_example(sense_id, example_index)` | Remove a sense example by index. |

### Relation (6 actions)

| # | Method | What it does |
|---|--------|--------------|
| 21 | `add_synset_relation(source_id, relation_type, target_id, *, auto_inverse, metadata)` | Add a synset-to-synset relation. |
| 22 | `remove_synset_relation(source_id, relation_type, target_id, *, auto_inverse)` | Remove a synset-to-synset relation. |
| 23 | `add_sense_relation(source_id, relation_type, target_id, *, auto_inverse, metadata)` | Add a sense-to-sense relation. |
| 24 | `remove_sense_relation(source_id, relation_type, target_id, *, auto_inverse)` | Remove a sense-to-sense relation. |
| 25 | `add_sense_synset_relation(source_sense_id, relation_type, target_synset_id, *, metadata)` | Add a sense-to-synset relation. |
| 26 | `remove_sense_synset_relation(source_sense_id, relation_type, target_synset_id)` | Remove a sense-to-synset relation. |

### ILI (3 actions)

| # | Method | What it does |
|---|--------|--------------|
| 27 | `link_ili(synset_id, ili_id)` | Link a synset to an existing ILI entry. |
| 28 | `unlink_ili(synset_id)` | Remove the ILI mapping from a synset. |
| 29 | `propose_ili(synset_id, definition, *, metadata)` | Propose a new ILI entry for a synset. |

### Metadata (2 actions)

| # | Method | What it does |
|---|--------|--------------|
| 30 | `set_metadata(entity_type, entity_id, key, value)` | Set or delete a metadata key on any entity. |
| 31 | `set_confidence(entity_type, entity_id, score)` | Set the `confidenceScore` metadata key. |


    // ══════════════════════════════════════════════
    // الخطوة ٠٫٥: توليد لمّات من التعريف (Definition-Driven Lemma Generation)
    // ══════════════════════════════════════════════

    // الهدف: توليد 2-4 لمّات عربية تمثّل دلالة التعريف — بدون الاطلاع على اللمّات الموجودة
    // هذه الخطوة تعمل بالاتجاه المعاكس: من التعريف → إلى اللمّات (بدلاً من اللمّات → إلى التحقق)
    // المصدر ١: الأدلة المعجمية (per_synset: step4_fts_keyword / step5_english_bridge / step9_specialized)
    // المصدر ٢: المعرفة اللغوية الداخلية للمراجع

    // ── المرحلة ١: فهم التعريف ──
    اقرأ تعريف_المجموعة (عربي + إنجليزي) ونوع الكلمة والمُشتمِل
    // ملاحظة: اللمّات الموجودة مخفية عمداً لتجنب التحيّز (anchoring bias)

    // ── المرحلة ٢: التنقيب في الأدلة ──
    مرشحات_الأدلة ← قائمة_فارغة

    // الجسر الإنجليزي: ما المقابلات العربية للمصطلح الإنجليزي؟
    لكل مدخل في step5_english_bridge نفّذ
        إذا headword مناسب دلالياً لتعريف المجموعة ومطابق لنوع الكلمة فـ
            أضف (headword، «اقتباس_النص» — اسم_المعجم) إلى مرشحات_الأدلة
        نهاية
    نهاية

    // البحث بالكلمات المفتاحية: ما الكلمات التي تتضمن مفردات التعريف؟
    لكل مدخل في step4_fts_keyword نفّذ
        إذا headword مرادف أو شبه مرادف لتعريف المجموعة فـ
            أضف (headword، «اقتباس_النص» — اسم_المعجم) إلى مرشحات_الأدلة
        نهاية
    نهاية

    // المتخصص: مشتقات من نفس الجذر ونوع الكلمة
    لكل مدخل في step9_specialized نفّذ
        إذا headword يحمل دلالة قريبة من تعريف المجموعة فـ
            أضف (headword، «اقتباس_النص» — اسم_المعجم) إلى مرشحات_الأدلة
        نهاية
    نهاية

    // اختر أفضل 1-2 من مرشحات_الأدلة
    evidence_candidates ← أفضل 1-2 مرشح (الأولوية: تطابق دلالي تام > تطابق جزئي)
    // شرط: |evidence_candidates| ≥ 1

    // ── المرحلة ٣: التوليد من المعرفة ──
    knowledge_candidates ← قائمة_فارغة
    لكل لمّة مقترحة من المعرفة اللغوية الداخلية نفّذ
        إذا اللمّة ليست من كلمات التعريف نفسه (تجنّب الدوران) فـ
            إذا اللمّة كلمة فصيحة مستقلة يمكن استخدامها في جملة فـ
                // اختبار السَّكّ المصطلحي: ارفض العبارات الوصفية الحرة
                // المعيار: إذا أمكن إبدال مكوّن بمرادف وبقي الوصف صالحاً → تركيب وصفي حر
                إذا اللمّة مصطلح مسكوك أو تعبير اصطلاحي ثابت (لا يقبل إبدال مكوّناته) فـ
                    أضف (لمّة، التبرير_الدلالي) إلى knowledge_candidates
                نهاية
            نهاية
        نهاية
    نهاية
    // شرط: |knowledge_candidates| ≥ 1

    // ── التحقق النهائي ──
    تأكد: |evidence_candidates| ≥ 1 و |knowledge_candidates| ≥ 1
    تأكد: المجموع الكلي 2-4 مرشحات
    // المرشحات تُمرَّر إلى الخطوة ١ للتحقق الكامل (اختبار الإبدال + فحص MWE + فحص اللهجة + اختبار السَّكّ المصطلحي)
