# Mixedbread Retrieval Evaluation Report

## Overview

- **Total queries evaluated:** 76
- **Skipped (0 GT overlap):** 256
- **Errors:** 0
- **Query types:** arabic_lemma, definition_keyword

## Metrics by Query Type

| Query Type | N | Recall@10 | Recall@25 | Recall@50 | P@10 | MRR | Avg GT |
|------------|---|-----------|-----------|-----------|------|-----|--------|
| arabic_lemma | 38 | 88.8% | 93.6% | 97.1% | 17.1% | 0.830 | 2.1 |
| definition_keyword | 38 | 39.0% | 52.9% | 58.6% | 7.6% | 0.459 | 2.1 |
| **Overall** | 76 | 63.9% | 73.2% | 77.9% | 12.4% | 0.645 | — |

## Interpretation

- **Recall@K** = fraction of ground-truth entries found in top-K results.
  SQL baseline has 100% recall (evidence.json was generated from SQL).
- **Precision@10** = fraction of top-10 results that are relevant.
- **MRR** = mean reciprocal rank of first relevant result (1.0 = always first).
- **Avg GT** = average number of ground truth entries per query (filtered to entries we uploaded).

## Per-Synset Results

### awn4-00001740-n
- **arabic_lemma**: q="كيان كينونة..." | GT=0 | Retrieved=0
- **english_bridge**: q="entity..." | GT=0 | Retrieved=0
- **definition_keyword**: q="ما يُدرَك أو يُعرَف أو يُستدَلّ على وجوده المستقل،..." | GT=0 | Retrieved=0

### awn4-00002684-n
- **arabic_lemma**: q="جسم شيء مادي غرض..." | GT=4 | Retrieved=50
- **english_bridge**: q="object physical object..." | GT=0 | Retrieved=0
- **definition_keyword**: q="كيان ملموس ومرئيّ؛ كيان يمكن أن يُلقيَ ظِلًّا..." | GT=4 | Retrieved=50

### awn4-00003553-n
- **arabic_lemma**: q="كل وحدة متكاملة..." | GT=2 | Retrieved=50
- **english_bridge**: q="whole unit..." | GT=0 | Retrieved=0
- **definition_keyword**: q="تجمُّع من الأجزاء يُعَدّ كيانًا واحدًا متكاملًا..." | GT=2 | Retrieved=50

### awn4-00004475-n
- **arabic_lemma**: q="عضوية كائن حي متعض..." | GT=0 | Retrieved=0
- **english_bridge**: q="organism being..." | GT=0 | Retrieved=0
- **definition_keyword**: q="كائن حيّ قادر على الفعل أو الأداء الوظيفيّ بشكل مس..." | GT=0 | Retrieved=0

### awn4-00007347-n
- **arabic_lemma**: q="سبب عامل مسبب..." | GT=1 | Retrieved=50
- **english_bridge**: q="causal agent cause causal agency..." | GT=0 | Retrieved=0
- **definition_keyword**: q="أيّ كيان يُحدِث أثرًا أو يكون مسؤولًا عن أحداث أو ..." | GT=1 | Retrieved=50

### awn4-00023451-n
- **arabic_lemma**: q="ادراك معرفة..." | GT=0 | Retrieved=0
- **english_bridge**: q="cognition knowledge noesis..." | GT=0 | Retrieved=0
- **definition_keyword**: q="الناتج النفسيّ للإدراك الحسّيّ والتعلُّم والاستدلا..." | GT=0 | Retrieved=0

### awn4-00023953-n
- **arabic_lemma**: q="حافز دافع دافعية..." | GT=0 | Retrieved=0
- **english_bridge**: q="motivation motive need..." | GT=0 | Retrieved=0
- **definition_keyword**: q="السمة النفسية التي تثير الكائن الحي للقيام بفعل نح..." | GT=0 | Retrieved=0

### awn4-00024900-n
- **arabic_lemma**: q="حالة..." | GT=0 | Retrieved=0
- **english_bridge**: q="state..." | GT=0 | Retrieved=0
- **definition_keyword**: q="الكيفيّة التي يكون عليها الشيء من حيث صفاته الرئيس..." | GT=0 | Retrieved=0

### awn4-00027365-n
- **arabic_lemma**: q="مكان موقع..." | GT=1 | Retrieved=50
- **english_bridge**: q="location..." | GT=0 | Retrieved=0
- **definition_keyword**: q="نقطة أو حيّز في المكان..." | GT=1 | Retrieved=50

### awn4-00028005-n
- **arabic_lemma**: q="شكل هيئة..." | GT=4 | Retrieved=50
- **english_bridge**: q="shape form..." | GT=0 | Retrieved=0
- **definition_keyword**: q="الترتيب المكاني لشيء ما بشكل متميز عن مادته..." | GT=4 | Retrieved=50

### awn4-00028468-n
- **arabic_lemma**: q="زمن وقت..." | GT=4 | Retrieved=50
- **english_bridge**: q="time..." | GT=0 | Retrieved=0
- **definition_keyword**: q="تواصل التجربة الذي تمر فيه الأحداث من المستقبل عبر..." | GT=4 | Retrieved=50

### awn4-00028950-n
- **arabic_lemma**: q="فراغ فضاء لا نهائي..." | GT=1 | Retrieved=50
- **english_bridge**: q="space infinite..." | GT=0 | Retrieved=0
- **definition_keyword**: q="المدى غير المحدود الذي يقع فيه كل شيء..." | GT=1 | Retrieved=50

### awn4-00030657-n
- **arabic_lemma**: q="عمل بشري فعل نشاط انساني..." | GT=2 | Retrieved=50
- **english_bridge**: q="act deed human action human activity..." | GT=0 | Retrieved=0
- **definition_keyword**: q="شيء يفعله الناس أو يتسبّبون في حدوثه..." | GT=2 | Retrieved=50

### awn4-00032220-n
- **arabic_lemma**: q="علاقة..." | GT=0 | Retrieved=0
- **english_bridge**: q="relation..." | GT=0 | Retrieved=0
- **definition_keyword**: q="تجريد ينتمي إلى كيانَيْن أو جزأَيْن معًا أو يميّزه..." | GT=0 | Retrieved=0

### awn4-01104341-n
- **arabic_lemma**: q="اشهار نشر..." | GT=2 | Retrieved=50
- **english_bridge**: q="publication..." | GT=0 | Retrieved=0
- **definition_keyword**: q="توصيل شيء ما للجمهور؛ جعل المعلومات معروفة بشكل عا..." | GT=2 | Retrieved=50

### awn4-03154617-n
- **arabic_lemma**: q="تحفة شيء نادر طرفة..." | GT=1 | Retrieved=50
- **english_bridge**: q="curio curiosity oddity oddment peculiarity rarity..." | GT=0 | Retrieved=0
- **definition_keyword**: q="شيء غير عادي - ربما يستحق الجمع..." | GT=1 | Retrieved=50

### awn4-03343593-n
- **arabic_lemma**: q="طبقة رقيقة غشاء..." | GT=0 | Retrieved=0
- **english_bridge**: q="film..." | GT=0 | Retrieved=0
- **definition_keyword**: q="طلاء رقيق أو طبقة رقيقة..." | GT=0 | Retrieved=0

### awn4-03400581-n
- **arabic_lemma**: q="ملطف منعش..." | GT=0 | Retrieved=0
- **english_bridge**: q="freshener..." | GT=0 | Retrieved=0
- **definition_keyword**: q="أي شيء يقوم بالإنعاش أو التلطيف..." | GT=0 | Retrieved=0

### awn4-03720260-n
- **arabic_lemma**: q="تكملة حشو..." | GT=2 | Retrieved=50
- **english_bridge**: q="makeweight filler..." | GT=0 | Retrieved=0
- **definition_keyword**: q="أي شيء يضاف لإكمال الكل..." | GT=2 | Retrieved=50

### awn4-03876139-n
- **arabic_lemma**: q="مسكن مهدئ..." | GT=1 | Retrieved=50
- **english_bridge**: q="pacifier..." | GT=0 | Retrieved=0
- **definition_keyword**: q="أي شيء يعمل على التهدئة أو التسكين..." | GT=1 | Retrieved=50

### awn4-03898588-n
- **arabic_lemma**: q="جزء شق قسم..." | GT=4 | Retrieved=50
- **english_bridge**: q="part portion..." | GT=0 | Retrieved=0
- **definition_keyword**: q="شيء أقل من الكل في مصنوع بشري..." | GT=4 | Retrieved=50

### awn4-04354303-n
- **arabic_lemma**: q="غرض مصور محتوي موضوع..." | GT=0 | Retrieved=0
- **english_bridge**: q="subject content depicted object..." | GT=0 | Retrieved=0
- **definition_keyword**: q="شيء (شخص أو كائن أو مشهد) يختاره فنان أو مصور للتم..." | GT=0 | Retrieved=0

### awn4-04493701-n
- **arabic_lemma**: q="تفاهة شيء تافه..." | GT=0 | Retrieved=0
- **english_bridge**: q="triviality trivia trifle small beer..." | GT=0 | Retrieved=0
- **definition_keyword**: q="شيء قليل الأهمية..." | GT=0 | Retrieved=0

### awn4-04623416-n
- **arabic_lemma**: q="خصلة سمة صفة..." | GT=2 | Retrieved=50
- **english_bridge**: q="trait..." | GT=0 | Retrieved=0
- **definition_keyword**: q="ميزة مميزة لطبيعتك الشخصية..." | GT=2 | Retrieved=50

### awn4-04624273-n
- **arabic_lemma**: q="صفة وراثية..." | GT=0 | Retrieved=0
- **english_bridge**: q="character..." | GT=0 | Retrieved=0
- **definition_keyword**: q="(علم الوراثة) سمة (هيكلية أو وظيفية) يحددها جين أو..." | GT=0 | Retrieved=0

### awn4-04624646-n
- **arabic_lemma**: q="امر شيء..." | GT=3 | Retrieved=50
- **english_bridge**: q="thing..." | GT=0 | Retrieved=0
- **definition_keyword**: q="أي سمة أو صفة تعتبر ذات وجود مستقل..." | GT=3 | Retrieved=50

### awn4-04638655-n
- **arabic_lemma**: q="انقباض كابة..." | GT=0 | Retrieved=0
- **english_bridge**: q="uncheerfulness..." | GT=0 | Retrieved=0
- **definition_keyword**: q="غير مؤدٍ للبهجة أو الروح المعنوية الجيدة..." | GT=0 | Retrieved=0

### awn4-04699340-n
- **arabic_lemma**: q="ثبات رزانة..." | GT=0 | Retrieved=0
- **english_bridge**: q="ballast..." | GT=0 | Retrieved=0
- **definition_keyword**: q="سمة تميل لإعطاء الاستقرار في الشخصية والأخلاق؛ شيء..." | GT=0 | Retrieved=0

### awn4-04928188-n
- **arabic_lemma**: q="ارث ميراث..." | GT=2 | Retrieved=50
- **english_bridge**: q="inheritance heritage..." | GT=0 | Retrieved=0
- **definition_keyword**: q="أي سمة أو ممتلكات غير مادية موروثة من الأسلاف..." | GT=2 | Retrieved=50

### awn4-06025625-n
- **arabic_lemma**: q="فترة..." | GT=0 | Retrieved=0
- **english_bridge**: q="interval..." | GT=0 | Retrieved=0
- **definition_keyword**: q="مجموعة تحتوي على جميع النقاط (أو جميع الأعداد الحق..." | GT=0 | Retrieved=0

### awn4-06026202-n
- **arabic_lemma**: q="زمرة زمرة رياضية..." | GT=0 | Retrieved=0
- **english_bridge**: q="group mathematical group..." | GT=0 | Retrieved=0
- **definition_keyword**: q="مجموعة مغلقة وتجميعية، ولها عنصر محايد، ولكل عنصر ..." | GT=0 | Retrieved=0

### awn4-06293036-n
- **arabic_lemma**: q="سريان عدوي..." | GT=0 | Retrieved=0
- **english_bridge**: q="contagion infection..." | GT=0 | Retrieved=0
- **definition_keyword**: q="انتقال موقف أو حالة عاطفية بين عدد من الناس..." | GT=0 | Retrieved=0

### awn4-06293304-n
- **arabic_lemma**: q="تواصل لغوي لغة..." | GT=1 | Retrieved=50
- **english_bridge**: q="language linguistic communication..." | GT=0 | Retrieved=0
- **definition_keyword**: q="نظام منهجيّ للتواصل باستخدام الأصوات أو الرموز الا..." | GT=1 | Retrieved=50

### awn4-06360590-n
- **arabic_lemma**: q="تواصل كتابي لغة مكتوبة..." | GT=0 | Retrieved=0
- **english_bridge**: q="written communication written language black and w..." | GT=0 | Retrieved=0
- **definition_keyword**: q="التواصل بوساطة رموز مكتوبة، سواء أكانت مطبوعة أم م..." | GT=0 | Retrieved=0

### awn4-06611268-n
- **arabic_lemma**: q="رسالة محتوي مضمون..." | GT=0 | Retrieved=0
- **english_bridge**: q="message content subject matter substance..." | GT=0 | Retrieved=0
- **definition_keyword**: q="المحتوى الذي يُبلِّغ رسالة؛ ما يتعلّق به الشيء من ..." | GT=0 | Retrieved=0

### awn4-06810027-n
- **arabic_lemma**: q="دلالة علامة مؤشر..." | GT=0 | Retrieved=0
- **english_bridge**: q="indication indicant..." | GT=0 | Retrieved=0
- **definition_keyword**: q="شيء يخدم للدلالة أو الإيحاء..." | GT=0 | Retrieved=0

### awn4-07096217-n
- **arabic_lemma**: q="تواصل شبه لغوي لغة مصاحبة..." | GT=0 | Retrieved=0
- **english_bridge**: q="paralanguage paralinguistic communication..." | GT=0 | Retrieved=0
- **definition_keyword**: q="استخدام طريقة التحدث لتوصيل معانٍ معينة..." | GT=0 | Retrieved=0

### awn4-07123727-n
- **arabic_lemma**: q="اتصال سمعي تواصل سمعي..." | GT=0 | Retrieved=0
- **english_bridge**: q="auditory communication..." | GT=0 | Retrieved=0
- **definition_keyword**: q="تواصل يعتمد على حاسة السمع..." | GT=0 | Retrieved=0

### awn4-07298313-n
- **arabic_lemma**: q="حدث طبيعي حدوث واقعة..." | GT=0 | Retrieved=0
- **english_bridge**: q="happening occurrence occurrent natural event..." | GT=0 | Retrieved=0
- **definition_keyword**: q="حدث يقع بشكل طبيعيّ..." | GT=0 | Retrieved=0

### awn4-07303524-n
- **arabic_lemma**: q="معجزة..." | GT=0 | Retrieved=0
- **english_bridge**: q="miracle..." | GT=0 | Retrieved=0
- **definition_keyword**: q="حدث عجيب يظهر فعلاً خارقاً للطبيعة من قبل قوة إلهي..." | GT=0 | Retrieved=0

### awn4-07327429-n
- **arabic_lemma**: q="انتقال هجرة..." | GT=0 | Retrieved=0
- **english_bridge**: q="migration..." | GT=0 | Retrieved=0
- **definition_keyword**: q="(في الكيمياء) الحركة غير العشوائية لذرة أو جذور كي..." | GT=0 | Retrieved=0

### awn4-07493671-n
- **arabic_lemma**: q="سقوط الانسان..." | GT=0 | Retrieved=0
- **english_bridge**: q="Fall of man Fall..." | GT=0 | Retrieved=0
- **definition_keyword**: q="سقوط البشرية في الخطيئة بسبب خطيئة آدم وحواء..." | GT=0 | Retrieved=0

### awn4-07867030-n
- **arabic_lemma**: q="قشارة..." | GT=0 | Retrieved=0
- **english_bridge**: q="paring..." | GT=0 | Retrieved=0
- **definition_keyword**: q="(عادة بالجمع) جزء من فاكهة أو خضروات تم تقشيره أو ..." | GT=0 | Retrieved=0

### awn4-07955399-n
- **arabic_lemma**: q="شرذمة مجموعة متفرقة..." | GT=1 | Retrieved=50
- **english_bridge**: q="straggle..." | GT=0 | Retrieved=0
- **definition_keyword**: q="تجمع متجول أو غير منظم (لأشياء أو أشخاص)..." | GT=1 | Retrieved=50

### awn4-07956688-n
- **arabic_lemma**: q="مملكة..." | GT=0 | Retrieved=0
- **english_bridge**: q="kingdom..." | GT=0 | Retrieved=0
- **definition_keyword**: q="مجموعة أساسية من الكائنات الطبيعية..." | GT=0 | Retrieved=0

### awn4-07957969-n
- **arabic_lemma**: q="مجتمع حيوي..." | GT=0 | Retrieved=0
- **english_bridge**: q="community biotic community..." | GT=0 | Retrieved=0
- **definition_keyword**: q="(في علم البيئة) مجموعة من الكائنات الحية المترابطة..." | GT=0 | Retrieved=0

### awn4-07958392-n
- **arabic_lemma**: q="اشخاص بشر ناس..." | GT=3 | Retrieved=50
- **english_bridge**: q="people..." | GT=0 | Retrieved=0
- **definition_keyword**: q="مجموعة من البشر (رجال أو نساء أو أطفال) بشكل جماعي..." | GT=3 | Retrieved=50

### awn4-07984596-n
- **arabic_lemma**: q="سلالة عرق..." | GT=2 | Retrieved=50
- **english_bridge**: q="race..." | GT=0 | Retrieved=0
- **definition_keyword**: q="أشخاص يُعتقد أنهم ينتمون إلى نفس الأصل الجيني..." | GT=2 | Retrieved=50

### awn4-08017086-n
- **arabic_lemma**: q="مجموعة شاملة..." | GT=0 | Retrieved=0
- **english_bridge**: q="universal set..." | GT=0 | Retrieved=0
- **definition_keyword**: q="المجموعة التي تحتوي على جميع العناصر أو الأشياء ال..." | GT=0 | Retrieved=0

### awn4-08021702-n
- **arabic_lemma**: q="حقل..." | GT=2 | Retrieved=50
- **english_bridge**: q="field..." | GT=0 | Retrieved=0
- **definition_keyword**: q="مجموعة من العناصر يكون فيها الجمع والضرب تبادليين ..." | GT=2 | Retrieved=50

### awn4-08022396-n
- **arabic_lemma**: q="جذر حل..." | GT=3 | Retrieved=50
- **english_bridge**: q="solution root..." | GT=0 | Retrieved=0
- **definition_keyword**: q="مجموعة القيم التي تعطي عبارة صحيحة عند تعويضها في ..." | GT=3 | Retrieved=50

### awn4-08177175-n
- **arabic_lemma**: q="شعب مواطنون..." | GT=2 | Retrieved=50
- **english_bridge**: q="citizenry people..." | GT=0 | Retrieved=0
- **definition_keyword**: q="هيئة مواطني دولة أو بلد..." | GT=2 | Retrieved=50

### awn4-08195659-n
- **arabic_lemma**: q="عشيرة مجموعة سكانية..." | GT=0 | Retrieved=0
- **english_bridge**: q="population..." | GT=0 | Retrieved=0
- **definition_keyword**: q="مجموعة من الكائنات الحية من نفس النوع تسكن منطقة م..." | GT=0 | Retrieved=0

### awn4-08197108-n
- **arabic_lemma**: q="جماهير جموع دهماء..." | GT=0 | Retrieved=0
- **english_bridge**: q="multitude masses mass hoi polloi people the great ..." | GT=0 | Retrieved=0
- **definition_keyword**: q="عامة الناس بشكل عام..." | GT=0 | Retrieved=0

### awn4-08285242-n
- **arabic_lemma**: q="قطر..." | GT=1 | Retrieved=50
- **english_bridge**: q="diagonal..." | GT=0 | Retrieved=0
- **definition_keyword**: q="مجموعة من المدخلات في مصفوفة مربعة تمتد قطرياً إما..." | GT=1 | Retrieved=50

### awn4-08452398-n
- **arabic_lemma**: q="منظومة نظام..." | GT=0 | Retrieved=0
- **english_bridge**: q="system scheme..." | GT=0 | Retrieved=0
- **definition_keyword**: q="مجموعة من العناصر المستقلة ولكن المترابطة التي تشك..." | GT=0 | Retrieved=0

### awn4-09248053-n
- **arabic_lemma**: q="مسطح مائي مياه..." | GT=0 | Retrieved=0
- **english_bridge**: q="body of water water..." | GT=0 | Retrieved=0
- **definition_keyword**: q="جزء من سطح الأرض مغطى بالماء (مثل نهر أو بحيرة أو ..." | GT=0 | Retrieved=0

### awn4-09261049-n
- **arabic_lemma**: q="صيد..." | GT=1 | Retrieved=50
- **english_bridge**: q="catch..." | GT=0 | Retrieved=0
- **definition_keyword**: q="أي شيء يتم اصطياده (خاصة إذا كان يستحق الصيد)..." | GT=1 | Retrieved=50

### awn4-09274595-n
- **arabic_lemma**: q="تذكار عملة تذكارية..." | GT=0 | Retrieved=0
- **english_bridge**: q="commemorative..." | GT=0 | Retrieved=0
- **definition_keyword**: q="جسم (مثل عملة معدنية أو طابع بريد) صنع لتمييز حدث ..." | GT=0 | Retrieved=0

### awn4-09290396-n
- **arabic_lemma**: q="شيء متروك مهملات..." | GT=0 | Retrieved=0
- **english_bridge**: q="discard..." | GT=0 | Retrieved=0
- **definition_keyword**: q="أي شيء يتم طرحه جانباً أو التخلص منه..." | GT=0 | Retrieved=0

### awn4-09302364-n
- **arabic_lemma**: q="لقطة مكتشف..." | GT=0 | Retrieved=0
- **english_bridge**: q="finding..." | GT=0 | Retrieved=0
- **definition_keyword**: q="شيء تم العثور عليه..." | GT=0 | Retrieved=0

### awn4-09318244-n
- **arabic_lemma**: q="نبتة نمو..." | GT=1 | Retrieved=50
- **english_bridge**: q="growth..." | GT=0 | Retrieved=0
- **definition_keyword**: q="شيء نامٍ أو ينمو..." | GT=1 | Retrieved=50

### awn4-09335551-n
- **arabic_lemma**: q="شيء ثانوي غير ضروري كمالية..." | GT=0 | Retrieved=0
- **english_bridge**: q="inessential nonessential..." | GT=0 | Retrieved=0
- **definition_keyword**: q="أي شيء ليس أساسياً..." | GT=0 | Retrieved=0

### awn4-09357302-n
- **arabic_lemma**: q="ارض بر يابسة..." | GT=4 | Retrieved=50
- **english_bridge**: q="land dry land earth ground solid ground terra firm..." | GT=0 | Retrieved=0
- **definition_keyword**: q="الجزء الصلب من سطح الأرض..." | GT=4 | Retrieved=50

### awn4-09358146-n
- **arabic_lemma**: q="ارض تربة..." | GT=2 | Retrieved=50
- **english_bridge**: q="land ground soil..." | GT=0 | Retrieved=0
- **definition_keyword**: q="المادة الموجودة في الطبقة العليا من سطح الأرض والت..." | GT=2 | Retrieved=50

### awn4-09381447-n
- **arabic_lemma**: q="قمر..." | GT=1 | Retrieved=50
- **english_bridge**: q="moon..." | GT=0 | Retrieved=0
- **definition_keyword**: q="أي جسم يشبه القمر..." | GT=1 | Retrieved=50

### awn4-09390100-n
- **arabic_lemma**: q="حاجة ماسة شيء اساسي ضرورة مستلزم..." | GT=0 | Retrieved=0
- **english_bridge**: q="necessity essential requirement requisite necessar..." | GT=0 | Retrieved=0
- **definition_keyword**: q="أي شيء لا غنى عنه..." | GT=0 | Retrieved=0

### awn4-09391121-n
- **arabic_lemma**: q="جار مجاور..." | GT=1 | Retrieved=50
- **english_bridge**: q="neighbor neighbour..." | GT=0 | Retrieved=0
- **definition_keyword**: q="جسم قريب من نفس النوع..." | GT=1 | Retrieved=50

### awn4-09408804-n
- **arabic_lemma**: q="جزء قطعة..." | GT=3 | Retrieved=50
- **english_bridge**: q="part piece..." | GT=0 | Retrieved=0
- **definition_keyword**: q="جزء من جسم طبيعيّ..." | GT=3 | Retrieved=50

### awn4-09430224-n
- **arabic_lemma**: q="بقايا..." | GT=0 | Retrieved=0
- **english_bridge**: q="remains..." | GT=0 | Retrieved=0
- **definition_keyword**: q="أي شيء يترك غير مستخدم أو لا يزال موجوداً..." | GT=0 | Retrieved=0

### awn4-09430745-n
- **arabic_lemma**: q="خزان مستودع مصدر..." | GT=0 | Retrieved=0
- **english_bridge**: q="reservoir source..." | GT=0 | Retrieved=0
- **definition_keyword**: q="أي شيء (شخص أو حيوان أو نبات أو مادة) يعيش فيه عام..." | GT=0 | Retrieved=0

### awn4-09432081-n
- **arabic_lemma**: q="خيط شريط..." | GT=2 | Retrieved=50
- **english_bridge**: q="ribbon thread..." | GT=0 | Retrieved=0
- **definition_keyword**: q="أي جسم طويل يشبه الخط الرفيع..." | GT=2 | Retrieved=50

### awn4-09488589-n
- **arabic_lemma**: q="لبنة اساسية وحدة..." | GT=0 | Retrieved=0
- **english_bridge**: q="unit building block..." | GT=0 | Retrieved=0
- **definition_keyword**: q="شيء طبيعي مفرد غير مقسم يدخل في تكوين شيء آخر..." | GT=0 | Retrieved=0

### awn4-09491367-n
- **arabic_lemma**: q="جسم تائه شارد..." | GT=0 | Retrieved=0
- **english_bridge**: q="vagabond..." | GT=0 | Retrieved=0
- **definition_keyword**: q="أي شيء يشبه المتشرد في عدم وجود مكان ثابت له..." | GT=0 | Retrieved=0

### awn4-09492089-n
- **arabic_lemma**: q="متغير..." | GT=0 | Retrieved=0
- **english_bridge**: q="variable..." | GT=0 | Retrieved=0
- **definition_keyword**: q="شيء من المحتمل أن يتغير؛ شيء يخضع للتغيير..." | GT=0 | Retrieved=0

### awn4-09497292-n
- **arabic_lemma**: q="جدار حائط..." | GT=0 | Retrieved=0
- **english_bridge**: q="wall..." | GT=0 | Retrieved=0
- **definition_keyword**: q="أي شيء يوحي بالجدار في الهيكل أو الوظيفة أو التأثي..." | GT=0 | Retrieved=0

### awn4-09526814-n
- **arabic_lemma**: q="طبيعة..." | GT=0 | Retrieved=0
- **english_bridge**: q="nature..." | GT=0 | Retrieved=0
- **definition_keyword**: q="عامل مسبب يخلق ويتحكم في الأشياء في الكون..." | GT=0 | Retrieved=0

### awn4-09528047-n
- **arabic_lemma**: q="قدر قضاء مصير..." | GT=3 | Retrieved=50
- **english_bridge**: q="destiny fate..." | GT=0 | Retrieved=0
- **definition_keyword**: q="القوة النهائية التي يُنظر إليها على أنها تحدد مسار..." | GT=3 | Retrieved=50

### awn4-09920164-n
- **arabic_lemma**: q="عامل مساعد محفز..." | GT=0 | Retrieved=0
- **english_bridge**: q="catalyst..." | GT=0 | Retrieved=0
- **definition_keyword**: q="شيء يسبب حدوث حدث مهم..." | GT=0 | Retrieved=0

### awn4-13261412-n
- **arabic_lemma**: q="ملكية..." | GT=0 | Retrieved=0
- **english_bridge**: q="ownership..." | GT=0 | Retrieved=0
- **definition_keyword**: q="علاقة المالك بالشيء المملوك؛ الحيازة مع الحق في نق..." | GT=0 | Retrieved=0

### awn4-13434666-n
- **arabic_lemma**: q="قيمة قيمة اقتصادية..." | GT=0 | Retrieved=0
- **english_bridge**: q="value economic value..." | GT=0 | Retrieved=0
- **definition_keyword**: q="المبلغ (من المال أو البضائع أو الخدمات) الذي يعتبر..." | GT=0 | Retrieved=0

### awn4-13467145-n
- **arabic_lemma**: q="استخلاب علاج بالاستخلاب..." | GT=0 | Retrieved=0
- **english_bridge**: q="chelation..." | GT=0 | Retrieved=0
- **definition_keyword**: q="(في الطب) عملية إزالة المعادن الثقيلة من مجرى الدم..." | GT=0 | Retrieved=0

### awn4-13479774-n
- **arabic_lemma**: q="انخفاض تناقص نقصان..." | GT=0 | Retrieved=0
- **english_bridge**: q="decrease decrement..." | GT=0 | Retrieved=0
- **definition_keyword**: q="عملية التحول إلى أصغر أو أقصر..." | GT=0 | Retrieved=0

### awn4-13486023-n
- **arabic_lemma**: q="ارتقاء تطور نماء..." | GT=0 | Retrieved=0
- **english_bridge**: q="development evolution..." | GT=0 | Retrieved=0
- **definition_keyword**: q="عملية يمر فيها شيء ما بدرجات إلى مرحلة مختلفة (خاص..." | GT=0 | Retrieved=0

### awn4-13495698-n
- **arabic_lemma**: q="تغليف كبسلة..." | GT=0 | Retrieved=0
- **english_bridge**: q="encapsulation..." | GT=0 | Retrieved=0
- **definition_keyword**: q="عملية التغليف (كما في كبسولة)..." | GT=0 | Retrieved=0

### awn4-13525111-n
- **arabic_lemma**: q="تكرار حلقة تكرارية..." | GT=0 | Retrieved=0
- **english_bridge**: q="iteration looping..." | GT=0 | Retrieved=0
- **definition_keyword**: q="(في علم الحاسوب) تنفيذ نفس مجموعة التعليمات لعدد م..." | GT=0 | Retrieved=0

### awn4-13525376-n
- **arabic_lemma**: q="تكرار حلقة..." | GT=1 | Retrieved=50
- **english_bridge**: q="iteration loop..." | GT=0 | Retrieved=0
- **definition_keyword**: q="(في علم الحاسوب) تنفيذ واحد لمجموعة من التعليمات ا..." | GT=1 | Retrieved=50

### awn4-13557997-n
- **arabic_lemma**: q="تصوير تصوير فوتوغرافي..." | GT=0 | Retrieved=0
- **english_bridge**: q="photography..." | GT=0 | Retrieved=0
- **definition_keyword**: q="عملية إنتاج صور للأشياء على أسطح حساسة للضوء..." | GT=0 | Retrieved=0

### awn4-13572820-n
- **arabic_lemma**: q="عملية عكوسة..." | GT=0 | Retrieved=0
- **english_bridge**: q="reversible process..." | GT=0 | Retrieved=0
- **definition_keyword**: q="أي عملية يمكن فيها جعل النظام يمر بنفس الحالات بال..." | GT=0 | Retrieved=0

### awn4-13593527-n
- **arabic_lemma**: q="تباين تغاير..." | GT=0 | Retrieved=0
- **english_bridge**: q="variation..." | GT=0 | Retrieved=0
- **definition_keyword**: q="عملية التباين أو التنويع..." | GT=0 | Retrieved=0

### awn4-13597072-n
- **arabic_lemma**: q="كمية اساسية مقياس اساسي..." | GT=0 | Retrieved=0
- **english_bridge**: q="fundamental quantity fundamental measure..." | GT=0 | Retrieved=0
- **definition_keyword**: q="إحدى الكمّيّات الأربع التي تُشكِّل أساس أنظمة القي..." | GT=0 | Retrieved=0

### awn4-13753670-n
- **arabic_lemma**: q="جذر..." | GT=2 | Retrieved=50
- **english_bridge**: q="radical..." | GT=0 | Retrieved=0
- **definition_keyword**: q="(رياضيات) كمية معبر عنها كجذر لكمية أخرى..." | GT=2 | Retrieved=50

### awn4-13801244-n
- **arabic_lemma**: q="حجم..." | GT=2 | Retrieved=50
- **english_bridge**: q="volume..." | GT=0 | Retrieved=0
- **definition_keyword**: q="مقدار الحيز ثلاثي الأبعاد الذي يشغله جسم ما..." | GT=2 | Retrieved=50

### awn4-13802818-n
- **arabic_lemma**: q="سببية..." | GT=0 | Retrieved=0
- **english_bridge**: q="causality..." | GT=0 | Retrieved=0
- **definition_keyword**: q="العلاقة بين الأسباب والنتائج..." | GT=0 | Retrieved=0

### awn4-13804981-n
- **arabic_lemma**: q="ارتباط مصاحبة..." | GT=0 | Retrieved=0
- **english_bridge**: q="association..." | GT=0 | Retrieved=0
- **definition_keyword**: q="علاقة ناتجة عن التفاعل أو الاعتماد..." | GT=0 | Retrieved=0

### awn4-13812924-n
- **arabic_lemma**: q="اساس قاعدة..." | GT=0 | Retrieved=0
- **english_bridge**: q="foundation..." | GT=0 | Retrieved=0
- **definition_keyword**: q="الأساس الذي يستند عليه شيء ما..." | GT=0 | Retrieved=0

### awn4-13813601-n
- **arabic_lemma**: q="اتصال ترابط..." | GT=0 | Retrieved=0
- **english_bridge**: q="connection connexion connectedness..." | GT=0 | Retrieved=0
- **definition_keyword**: q="علاقة بين أشياء أو أحداث (كما في حالة تسبب أحدهما ..." | GT=0 | Retrieved=0

### awn4-13833622-n
- **arabic_lemma**: q="قرابة روحية..." | GT=0 | Retrieved=0
- **english_bridge**: q="affinity kinship..." | GT=0 | Retrieved=0
- **definition_keyword**: q="اتصال وثيق يتميز بمجتمع المصالح أو التشابه في الطب..." | GT=0 | Retrieved=0

### awn4-13834819-n
- **arabic_lemma**: q="علاقة اسرية قرابة..." | GT=0 | Retrieved=0
- **english_bridge**: q="kinship family relationship relationship..." | GT=0 | Retrieved=0
- **definition_keyword**: q="(الأنثروبولوجيا) الارتباط أو الاتصال عن طريق الدم ..." | GT=0 | Retrieved=0

### awn4-13863412-n
- **arabic_lemma**: q="تبادلية..." | GT=0 | Retrieved=0
- **english_bridge**: q="reciprocality reciprocity..." | GT=0 | Retrieved=0
- **definition_keyword**: q="علاقة اعتماد أو عمل أو تأثير متبادل..." | GT=0 | Retrieved=0

### awn4-13866409-n
- **arabic_lemma**: q="ترابط علاقة متبادلة..." | GT=0 | Retrieved=0
- **english_bridge**: q="interrelation interrelationship interrelatedness..." | GT=0 | Retrieved=0
- **definition_keyword**: q="علاقة متبادلة أو ارتباط متبادل..." | GT=0 | Retrieved=0

### awn4-13876005-n
- **arabic_lemma**: q="مقارنة..." | GT=0 | Retrieved=0
- **english_bridge**: q="comparison..." | GT=0 | Retrieved=0
- **definition_keyword**: q="علاقة قائمة على أوجه التشابه والاختلاف..." | GT=0 | Retrieved=0

### awn4-13876846-n
- **arabic_lemma**: q="تضاد تعارض..." | GT=0 | Retrieved=0
- **english_bridge**: q="opposition oppositeness..." | GT=0 | Retrieved=0
- **definition_keyword**: q="العلاقة بين الكيانات المتعارضة..." | GT=0 | Retrieved=0

### awn4-13881240-n
- **arabic_lemma**: q="تغيير..." | GT=0 | Retrieved=0
- **english_bridge**: q="change..." | GT=0 | Retrieved=0
- **definition_keyword**: q="اختلاف علائقي بين الحالات؛ وخاصة بين الحالات قبل و..." | GT=0 | Retrieved=0

### awn4-14564166-n
- **arabic_lemma**: q="سبب الوفاة قاتل..." | GT=0 | Retrieved=0
- **english_bridge**: q="cause of death killer..." | GT=0 | Retrieved=0
- **definition_keyword**: q="العامل المسبب الذي يؤدي إلى الموت..." | GT=0 | Retrieved=0

### awn4-14928812-n
- **arabic_lemma**: q="هالوجين..." | GT=0 | Retrieved=0
- **english_bridge**: q="halogen..." | GT=0 | Retrieved=0
- **definition_keyword**: q="أي من العناصر اللافلزية الخمسة المرتبطة (الفلور أو..." | GT=0 | Retrieved=0

### awn4-14980800-n
- **arabic_lemma**: q="حماة طين لزج وحل..." | GT=4 | Retrieved=50
- **english_bridge**: q="sludge slime goo goop gook guck gunk muck ooze..." | GT=0 | Retrieved=0
- **definition_keyword**: q="أي مادة سميكة ولزجة..." | GT=4 | Retrieved=50

### awn4-15072416-n
- **arabic_lemma**: q="مذاب..." | GT=0 | Retrieved=0
- **english_bridge**: q="solute..." | GT=0 | Retrieved=0
- **definition_keyword**: q="المادة المذابة في محلول؛ مكون المحلول الذي يغير حا..." | GT=0 | Retrieved=0

### awn4-15134312-n
- **arabic_lemma**: q="انبعاث..." | GT=0 | Retrieved=0
- **english_bridge**: q="emanation..." | GT=0 | Retrieved=0
- **definition_keyword**: q="شيء ينبعث أو يشع (كغاز أو رائحة أو ضوء، إلخ)..." | GT=0 | Retrieved=0

### awn4-15281726-n
- **arabic_lemma**: q="فترة اللعب لعب..." | GT=1 | Retrieved=50
- **english_bridge**: q="playing period period of play play..." | GT=0 | Retrieved=0
- **definition_keyword**: q="(في الألعاب أو المسرحيات أو العروض الأخرى) الوقت ا..." | GT=1 | Retrieved=50

### awn4-92466752-n
- **arabic_lemma**: q="جرعة التعرض..." | GT=0 | Retrieved=0
- **definition_keyword**: q="قياس للإشعاع فيما يتعلق بقدرته على إنتاج التأين..." | GT=0 | Retrieved=0
