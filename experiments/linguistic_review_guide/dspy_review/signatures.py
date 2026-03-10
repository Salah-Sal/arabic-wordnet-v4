#!/usr/bin/env python3
"""DSPy Signature classes for the Level 4 step-decomposed pipeline.

Each class defines the input/output schema for one step of the 6-step review
algorithm. Docstrings are written in Arabic (with English code identifiers)
to prime the LLM for Arabic-language reasoning — matching the Level 1 pattern.

Module type per step:
    Step 0 — dspy.RLM (large evidence, programmatic exploration)
    Step 1 — dspy.ChainOfThought (compact input, reasoning-heavy)
    Step 2 — dspy.RLM (large candidate evidence, programmatic exploration)
    Step 3 — dspy.ChainOfThought (compact input, definition authoring)
    Step 4 — dspy.ChainOfThought (compact input, relation checking)
    Step 5 — dspy.ChainOfThought (compact input, enrichment)
"""
from __future__ import annotations

import dspy


# ═══════════════════════════════════════════════════════════════
# Step 0: Evidence Classification (RLM)
# ═══════════════════════════════════════════════════════════════

class Step0EvidenceClassification(dspy.Signature):
    """أنت ناقد لغوي عربي خبير متخصص في المعجمية العربية.
    مهمتك: تصنيف الأدلة المعجمية لكل لمّة في المجموعة الترادفية.

    == الموارد المتاحة ==

    المتغيرات:
      - synset_info: بيانات المجموعة الترادفية (المعرّف، نوع الكلمة، اللمات، التعريفات)
      - evidence_yaml: ملف الأدلة المعجمية الكامل بصيغة YAML (كبير الحجم — استخدم الأدوات أدناه)
      - algorithm: الخوارزمية المقتطعة للخطوة ٠ فقط
      - output_schema: مخطط YAML المتوقع للخطوة ٠ فقط

    الأدوات (استدعِها مباشرة في الكود):
      - evidence_summary() ← ملخص مختصر: عدد اللمات، المداخل لكل لمّة، المعاجم، الجذور
      - get_lemma_evidence(lemma) ← الأدلة الكاملة للمّة واحدة (مداخل المعاجم، عائلة الجذر، الأمثلة، البحث العكسي)

    == إجراء إلزامي ==

    ⚠ لا تستدعِ SUBMIT() حتى تُكمل جميع المراحل أدناه.

    المرحلة 1 — الاستطلاع (التكرارات 1-2):
      1. استدعِ evidence_summary() لرؤية هيكل الأدلة.
      2. اطبع synset_info لمعرفة المعرّف واللمات والتعريف.

    المرحلة 2 — التصنيف (التكرارات 3-20):
      لكل لمّة:
        1. استدعِ get_lemma_evidence(lemma) للحصول على بيانات المعاجم.
        2. استخدم llm_query() لمقارنة كل نص معجمي بتعريف المجموعة.
        3. صنّف كل نص إلى: confirm (يؤكد) / contradicts (يناقض) / expands (يوسّع).
           ملاحظة: التصنيفات غير حصرية — نص واحد قد ينتمي لأكثر من تصنيف.
        4. إذا لم تجد أدلة للمّة: عيّن evidence_status: "no_material_found".
        5. سجّل الملاحظات الهامشية (peripheral_observations) للمعاني المستقلة تماماً.

    ⚠⚠⚠ قاعدة التوثيق — هذه الخطوة توثيقية بحتة:
      - لا تكتب رأيك أو تقييمك (مثل "يؤكد المعنى المعنوي").
      - بدلاً من ذلك، وثّق النص المعجمي الفعلي كما هو مع اسم المعجم.
      - الشكل المطلوب لكل عنصر في confirm / contradicts / expands:
          "«نص المدخل المعجمي كما ورد» — اسم_المعجم"
      - مثال صحيح: "«تعمّق في كلامه: بالغ في تدبّره» — تاج اللغة وصِحاح العربية"
      - مثال خاطئ: "تاج اللغة وصِحاح العربية: يؤكد المعنى المعنوي."

    المرحلة 3 — التحقق والإرسال (التكرارات 21-25):
      1. ابنِ YAML النهائي كقاموس Python ثم حوّله بـ yaml.dump().
      2. تأكد أن المفتاح الرئيسي هو step0_evidence وأن per_lemma يحتوي على جميع اللمات.
      3. استدعِ SUBMIT(step0_yaml=yaml_text).

    == قواعد حاسمة ==
    - لا تتخطَّ أي لمّة — يجب تصنيف أدلة كل لمّة على حدة.
    - وثّق النص المعجمي الحرفي مع مصدره — لا تكتب تلخيصاً أو رأياً.
    - الشكل الوحيد المقبول: "«نص معجمي حرفي» — اسم المعجم"
    - اكتب التحليل بالعربية. اكتب أسماء الحقول بالإنجليزية.
    - اتّبع اصطلاحات الاختصار: احذف الحقول ذات القيم null / [] / {}.
    """
    synset_info: str = dspy.InputField(
        desc="بيانات المجموعة الترادفية: المعرّف، نوع الكلمة، اللمات، التعريفات، سلسلة العلاقات"
    )
    evidence_yaml: str = dspy.InputField(
        desc="أدلة معجمية مُعالَجة بصيغة YAML (بيانات per_lemma من 107 معاجم)"
    )
    algorithm: str = dspy.InputField(
        desc="خوارزمية الخطوة ٠: تصنيف الأدلة المعجمية"
    )
    output_schema: str = dspy.InputField(
        desc="مخطط YAML المتوقع للخطوة ٠ مع أمثلة"
    )
    step0_yaml: str = dspy.OutputField(
        desc="step0_evidence بصيغة YAML: تصنيف الأدلة (confirm/contradicts/expands) لكل لمّة"
    )


# ═══════════════════════════════════════════════════════════════
# Step 1: Lemma Validation (ChainOfThought)
# ═══════════════════════════════════════════════════════════════

class Step1LemmaValidation(dspy.Signature):
    """أنت ناقد لغوي عربي خبير. مهمتك: التحقق من صحة كل لمّة في المجموعة الترادفية
    باستخدام تصنيفات الأدلة من الخطوة ٠.

    لكل لمّة يجب أن تُنفّذ:
    1. تقييم الأدلة (4 حالات: no_material_found / contradicts_only / expands_only / confirm)
    2. اختبار التعبير المركب (MWE) — اقبل فقط التعابير الاصطلاحية
    3. فحص اللهجية — احذف الأشكال غير الفصيحة
    4. اختبار الاستبدال — هل يمكن إبدال هذه اللمّة بأخواتها في السياق؟
    5. مبدأ عدم الترادف المطلق — وثّق ما يميّز كل لمّة
    6. فحص الاقتراض والترجمة الحرفية (calques)
    7. القرار النهائي: confirmed / removed / escalated

    إذا وجدت أي سبب لمراجعة التعريف (دليل يناقض أو يوسّع بشكل جوهري):
    عيّن synset_flags.definition_review_needed: true

    اكتب جميع ملاحظات التحليل بالعربية. اكتب أسماء الحقول والقرارات بالإنجليزية.
    اتّبع اصطلاحات الاختصار من مخطط المخرجات (احذف null / [] / false).
    أخرج YAML صالحاً يبدأ بالمفتاح step1_lemma_validation.
    """
    synset_info: str = dspy.InputField(
        desc="بيانات المجموعة الترادفية: المعرّف، نوع الكلمة، اللمات، التعريفات، سلسلة العلاقات"
    )
    step0_yaml: str = dspy.InputField(
        desc="مخرجات الخطوة ٠: تصنيف الأدلة (confirm/contradicts/expands) لكل لمّة"
    )
    algorithm: str = dspy.InputField(
        desc="خوارزمية الخطوة ١: التحقق من اللمات + إجراء اختبار الاستبدال"
    )
    output_schema: str = dspy.InputField(
        desc="مخطط YAML المتوقع للخطوة ١ مع أمثلة"
    )
    step1_yaml: str = dspy.OutputField(
        desc="step1_lemma_validation بصيغة YAML: قرار لكل لمّة + synset_flags + added_lemmas"
    )


# ═══════════════════════════════════════════════════════════════
# Step 2: Missing Lemmas (RLM)
# ═══════════════════════════════════════════════════════════════

class Step2MissingLemmas(dspy.Signature):
    """أنت ناقد لغوي عربي خبير. مهمتك: اكتشاف لمّات مرادفة مفقودة من بيانات البحث العكسي
    وعمليات البحث على مستوى المجموعة الترادفية.

    == الموارد المتاحة ==

    المتغيرات:
      - synset_info: بيانات المجموعة الترادفية
      - confirmed_lemmas: قائمة اللمات المؤكدة من الخطوة ١ (لاستخدامها في اختبار الاستبدال)
      - candidate_evidence_yaml: أدلة المرشحين (per_synset + step8_reverse_lookup) بصيغة YAML
      - algorithm: الخوارزمية المقتطعة للخطوة ٢
      - output_schema: مخطط YAML المتوقع للخطوة ٢

    الأدوات:
      - candidate_summary() ← ملخص مختصر: عدد المرشحين ومصادرهم
      - get_section_evidence(section) ← أدلة قسم محدد (step4_fts_keyword / step5_english_bridge / step8_reverse_lookup)

    == إجراء إلزامي ==

    ⚠ لا تستدعِ SUBMIT() حتى تُكمل جميع المراحل أدناه.

    المرحلة 1 — الاستطلاع (التكرارات 1-2):
      1. استدعِ candidate_summary() لمعرفة عدد المرشحين.
      2. اطبع synset_info و confirmed_lemmas.

    المرحلة 2 — فحص المرشحين (التكرارات 3-20):
      لكل مرشح:
        a. استخلص الأدلة (نفس منطق الخطوة ٠: confirm/contradicts/expands)
        b. بوابة الأدلة: ارفض إذا لا دليل ولا رابط دلالي
        c. اختبار الإحالة المتقاطعة: هل يُشير تعريف المرشح إلى لمات المجموعة أو العكس؟
        d. اختبار الاستبدال مع اللمات المؤكدة (إذا وُجد دليل أو إحالة)
        e. القرار: added / rejected / proposed_new_synset / alternate_spelling

    المرحلة 3 — التحقق والإرسال (التكرارات 21-25):
      1. ابنِ YAML النهائي: step2_missing_lemmas مع per_candidate.
      2. إذا لم يُضَف أي مرشح: عيّن status: "none_added".
      3. استدعِ SUBMIT(step2_yaml=yaml_text).

    == قواعد حاسمة ==
    - افحص جميع المرشحين — لا تتخطَّ أي مرشح بدون تبرير.
    - استشهد بأدلة معجمية محددة لكل قرار.
    - اكتب التحليل بالعربية. اكتب أسماء الحقول والقرارات بالإنجليزية.
    """
    synset_info: str = dspy.InputField(
        desc="بيانات المجموعة الترادفية: المعرّف، نوع الكلمة، اللمات، التعريفات"
    )
    confirmed_lemmas: str = dspy.InputField(
        desc="قائمة اللمات المؤكدة من الخطوة ١ (لاختبار الاستبدال)"
    )
    candidate_evidence_yaml: str = dspy.InputField(
        desc="أدلة المرشحين بصيغة YAML: per_synset + step8_reverse_lookup"
    )
    algorithm: str = dspy.InputField(
        desc="خوارزمية الخطوة ٢: اكتشاف لمات مفقودة + اختبار الاستبدال"
    )
    output_schema: str = dspy.InputField(
        desc="مخطط YAML المتوقع للخطوة ٢ مع 6 أمثلة لمسارات القرار"
    )
    step2_yaml: str = dspy.OutputField(
        desc="step2_missing_lemmas بصيغة YAML: قرار لكل مرشح مع الأدلة والإحالة المتقاطعة"
    )


# ═══════════════════════════════════════════════════════════════
# Step 3: Definition Processing (ChainOfThought)
# ═══════════════════════════════════════════════════════════════

class Step3Definition(dspy.Signature):
    """أنت ناقد لغوي عربي خبير متخصص في تأليف التعريفات المعجمية العربية.
    مهمتك: تقييم تعريف AWN الحالي وتأليف تعريفات جديدة عند الحاجة.

    العملية:
    1. تحقق مما إذا كانت إشارة definition_review_flag مرفوعة من الخطوة ١.
    2. قارن تعريف AWN بأدلة المعاجم (الأدلة المؤكِّدة والتوسّعية من الخطوة ٠).
    3. قرّر: retain (إبقاء) أو revise (تعديل).
    4. إذا كان القرار revise أو لا يوجد تعريف عربي:
       أ. ألّف تعريفاً مصطلحياً (جنس قريب + فصل نوعي)
       ب. ألّف تعريفاً لغوياً (للمفاهيم المجردة أو البسيطة أو الأفعال)
       ج. ألّف تعريفاً موسوعياً (للحيوانات/النباتات/الأدوات/المفاهيم الثقافية المعقدة)
    5. أجرِ فحص الجودة لكل تعريف مؤلَّف.

    اكتب التعريفات بأسلوب المعجم الوسيط — لا تترجم التعريف الإنجليزي حرفياً.
    أنشئ تعريفات أصيلة مستندة إلى المعاجم العربية.
    أخرج YAML صالحاً يبدأ بالمفتاح step3_definition.
    """
    synset_info: str = dspy.InputField(
        desc="بيانات المجموعة الترادفية مع التعريفات الحالية بالعربية والإنجليزية"
    )
    definition_review_flag: str = dspy.InputField(
        desc="هل إشارة المراجعة مرفوعة من الخطوة ١؟ (true / false)"
    )
    step0_evidence_summary: str = dspy.InputField(
        desc="ملخص أدلة الخطوة ٠: نصوص confirm/expands لكل لمّة (للمقارنة مع التعريف)"
    )
    algorithm: str = dspy.InputField(
        desc="خوارزمية الخطوة ٣: تأليف التعريفات + فحص الجودة"
    )
    output_schema: str = dspy.InputField(
        desc="مخطط YAML المتوقع للخطوة ٣ مع أمثلة"
    )
    step3_yaml: str = dspy.OutputField(
        desc="step3_definition بصيغة YAML: التقييم، التعريفات المؤلَّفة مع فحص الجودة"
    )


# ═══════════════════════════════════════════════════════════════
# Step 4: Relations Check (ChainOfThought)
# ═══════════════════════════════════════════════════════════════

class Step4Relations(dspy.Signature):
    """أنت ناقد لغوي عربي خبير. مهمتك: فحص العلاقات الدلالية للمجموعة الترادفية.

    الفحوصات المطلوبة:
    1. الاشتمال (Hypernymy): هل "X is-a Y" صحيح؟ افحص 3 مستويات صعوداً.
       إذا وُجد مُشتمِل أقرب — أشِر إليه.
    2. التضاد (Antonymy): لكل لمّة مؤكدة، حدّد المتضادات المباشرة.
       أشِر إلى التعارضات الداخلية (أزواج متضادة في نفس المجموعة = خلط دلالي).
    3. فحوصات الأفعال: التعدي، حروف الجر، الأطر التركيبية.
       أشِر إلى خلط المصدر/اسم الفاعل.
    4. القيود الاختيارية (Selectional Restrictions): هل تتطلب الكلمة فاعلاً
       عاقلاً/حياً/غير حي؟

    اكتب التحليل بالعربية. اتّبع اصطلاحات الاختصار.
    أخرج YAML صالحاً يبدأ بالمفتاح step4_relations.
    """
    synset_info: str = dspy.InputField(
        desc="بيانات المجموعة الترادفية مع العلاقات وسلسلة الاشتمال"
    )
    confirmed_lemmas: str = dspy.InputField(
        desc="اللمات المؤكدة والمضافة من الخطوتين ١ و٢"
    )
    algorithm: str = dspy.InputField(
        desc="خوارزمية الخطوة ٤: فحص العلاقات"
    )
    output_schema: str = dspy.InputField(
        desc="مخطط YAML المتوقع للخطوة ٤ مع أمثلة"
    )
    step4_yaml: str = dspy.OutputField(
        desc="step4_relations بصيغة YAML: الاشتمال، التضاد، فحوصات الأفعال، القيود الاختيارية"
    )


# ═══════════════════════════════════════════════════════════════
# Step 5: Enrichment & Cultural Fit (ChainOfThought)
# ═══════════════════════════════════════════════════════════════

class Step5Enrichment(dspy.Signature):
    """أنت ناقد لغوي عربي خبير. مهمتك: إثراء حقول اللمّات وتقييم الملاءمة الثقافية.

    لكل لمّة مؤكدة/مضافة:
    1. استهلك بيانات التوسيع من الخطوة ٠ ← حوّلها إلى حقول إثراء.
    2. عيّن حقول الإثراء: root، usage، eloquence، connotation، literal_figurative.
    3. حلّ التعارضات عند اختلاف المصادر (اسمح بقيم متعددة).
    4. استخلص المتلازمات (collocations) من أدلة المعاجم.
    5. اختر أو ألّف أمثلة (الأولوية: قرآن، حديث، شعر، ثم استعمال).
    6. فحوصات صرفية: روابط جمع التكسير، تصحيحات الصيغة.
    7. فحوصات خاصة بنوع الكلمة: تعدي الفعل، قبول الحال، تمييز الاسم/المصدر.

    على مستوى المجموعة الترادفية:
    8. الملاءمة الثقافية: native / phraset / lexical_gap / omission.

    مهم: البيانات في كتل enrichment / collocations / examples / morphology / pos_check
    هي مصدر الحقيقة. المحلل يشتق الأوامر منها تلقائياً. اكتب فقط الأوامر غير المشتقة
    في actions[] (مثل: "سجّل ملاحظة دلالية").

    أخرج YAML صالحاً يبدأ بالمفتاح step5_enrichment.
    """
    synset_info: str = dspy.InputField(
        desc="بيانات المجموعة الترادفية"
    )
    confirmed_lemmas_with_evidence: str = dspy.InputField(
        desc="اللمات المؤكدة/المضافة مع أدلة الخطوة ٠ (خاصة بيانات التوسيع expands)"
    )
    examples_evidence: str = dspy.InputField(
        desc="بيانات step6_examples لكل لمّة لاستخلاص الاقتباسات والأمثلة"
    )
    algorithm: str = dspy.InputField(
        desc="خوارزمية الخطوة ٥: الإثراء والملاءمة الثقافية"
    )
    output_schema: str = dspy.InputField(
        desc="مخطط YAML المتوقع للخطوة ٥ مع أمثلة"
    )
    step5_yaml: str = dspy.OutputField(
        desc="step5_enrichment بصيغة YAML: حقول الإثراء والمتلازمات والأمثلة والصرف والملاءمة الثقافية"
    )
