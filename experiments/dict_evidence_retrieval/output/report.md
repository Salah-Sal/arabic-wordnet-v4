# Dictionary Evidence Retrieval Report

**Date:** 2026-03-03T00:32:24.511565+00:00  
**Synsets:** 10  
**Total time:** 68.7s  
**Strategies:** A (Headword), B (Root Family), C (FTS5), D (ColBERT), E (Translation)

---

## 1. `awn4-13271441-n` — مال, نقود

- **POS:** n
- **Lemmas (2):** مال ، نقود
- **Definition:** الثروة المحسوبة من حيث المال
- **Examples:** كل ماله في العقارات

### Strategy A — Headword Match (SQL Tier 1)
*Query: مال, نقود (5ms, 17 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | مَال | hawramani_35 | hawramani | lemma_match | (مَال)مولا وموولا كثر مَاله فَهُوَ مَال وَهِي مالة وَفُلَانً |
| 2 | مَال | hawramani_35 | hawramani | lemma_match | (مَال)ميلًا وميلانا زَالَ عَن استوائه يُقَال مَال الْحَائِط  |
| 3 | مأل | hawramani_36 | hawramani | lemma_match | مأل: المَأْلَةُ: الرَّوْضَةُ. والرَّحى، وجَمْعُها مِثَالٌ. و |
| 4 | مالَ | hawramani_19 | hawramani | lemma_match | مالَ إليه مَيْلاً ومَمالاً ومَمِيلاً وتَمْيَالاً ومَيَلاَناً |
| 5 | مَأَلَ  | hawramani_7 | hawramani | lemma_match | (مَأَلَ) الْمِيمُ وَالْهَمْزَةُ وَاللَّامُ. قَدْ ذَكَرُوا فِ |
| 6 | مأل | hawramani_1 | hawramani | lemma_match | مأل: رجل مَأْلٌ ومَئِلٌ: ضَخم كثير اللحم تارّ، والأُنثى مَأْ |
| 7 | مأل | hawramani_8 | hawramani | lemma_match | [م أل] رَجُلٌ مَأْلٌ وَمَثِلٌ ضَخْمٌ كَثِيرُ اللَّحْمِ والأُ |
| 8 | مَأَلَ | hawramani_11 | hawramani | lemma_match | (مَأَلَ)- فِي حَدِيثِ عَمْرِو بْنِ الْعَاصِ «إِنِّي واللهِ م |
| 9 | مأل | hawramani_25 | hawramani | lemma_match | مأل} المَأْلُ، بالفَتْح (و) {المَئِل، ككَتِفٍ أَهْمَلَه الجَ |
| 10 | مأل | hawramani_21 | hawramani | lemma_match | [مأل] نه: في ح ابن العاص: ما تأبطتني الإماء ولا حملتني البغا |

### Strategy B — Root Family (SQL Tier 2)
*Query: root=قد,مأل,مل,مول,ميل (140ms, 200 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | مول | Kitab_Al_Ayn | ocr | morphological_kin | المال: الأنعام عند العرب وما يملك من متاع المولة: اسم العنكب |
| 2 | مول | Maqayis_Lugha | ocr | definition_support, morphologi | اتخاذ المال وكثرته |
| 3 | مول | Mujmal_Lugha | ocr | definition_support, morphologi | المال معروف |
| 4 | قودي ألاسكا | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 5 | فقد في المحصول | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 6 | قادة | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 7 | فقد من التربة | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 8 | قيود الحركة | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 9 | قيود | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 10 | فقد بسبب التخزين | arabterm_agrovoc | arabterm | morphological_kin, translation |  |

### Strategy C — Definition Search (FTS5 BM25)
*Query: الثروة OR المحسوبة OR حيث OR المال (170ms, 50 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | الثَّرْوَة | Al_Waseet | ocr | definition_support, morphologi | الكثير من المال والناس (فى الاقتصاد): الأموالُ القابلة للتمل |
| 2 | الثَّرْوَةُ | Al_Mujam_Al_Kabeer | ocr | definition_support, morphologi | كثرة المال |
| 3 | الثَّرْوَة | Al_Mujam_Al_Kabeer | ocr | morphological_kin | المالُ الكَثِيرُ ثَرْوَةٌ من رجالٍ: عَدَدٌ كَثِيرٌ منهم |
| 4 | الثَّرْوَة | Al_Mujam_Al_Kabeer | ocr | morphological_kin | (في الفَلَك): اللَّيْلَةُ التي يَلْتَقِي فيها القَمَرُ والثُ |
| 5 | ثَرْو | Kitab_Al_Ayn | ocr | definition_support, morphologi | الثروة: كثرة العدد من الرجال أو المال الثراء: عدد المال نفسه |
| 6 | مؤسسة | arabterm_arabterm_cl | arabterm | definition_support, morphologi | مفهوم يختلف في جزئياته من بلد إلى آخر. عموما هي هيئة أنشأت ل |
| 7 | فائدة | arabterm_arabterm_cl | arabterm | definition_support, morphologi | الأرباح السنوية التي يضحى بها عندما يتم استثمار هذه الثروة ف |
| 8 | ترفيه | arabterm_arabterm_cl | arabterm | definition_support, morphologi | جميع استخدامات الوقت حيث الأنشطة الخدمات المبذولة لا تنجز مق |
| 9 | إنتاج متكامل | arabterm_arabterm_cl | arabterm | morphological_kin, translation | نظام يمزج بين ما يتم إنتاجه بالتوازي من الثروة النباتية، وال |
| 10 | صيد غير قانوني، دون  | arabterm_arabterm_cl | arabterm | definition_support, morphologi | عمليات الصيد في المياه الوطنية وأعالي البحار التي تتعارض مع  |

### Strategy D — ColBERT Semantic Search
*Query: D1:'مال; نقود' | D2:def | D3:combined (5850ms, 48 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | مال | hawramani_48 | hawramani | lemma_match | مَال من (م و ل) كل ما يملكه الفرد أو الجماعة من متاع أو تجار |
| 2 | المال | hawramani_24 | hawramani | contextual | المال: [في الانكليزية] Money ،property ،possessions  [ في ال |
| 3 | المال | hawramani_35 | hawramani | contextual | (المَال) كل مَا يملكهُ الْفَرد أَو تملكه الْجَمَاعَة من مَتَ |
| 4 | مويلي | hawramani_48 | hawramani | contextual | مُوَيْليّ من (م و ل) نسبة إلى مويل: تصغير مال بمعنى كل ما يم |
| 5 | مول | hawramani_36 | hawramani | contextual | مول: المُوْلَةُ: العَنْكَبُوْتُ. واسْمُ عَيْنِ تَبُوْكَ. وال |
| 6 | نكب | hawramani_31 | hawramani | contextual | نكب نَكَبَ عن كذا. أي: مَالَ. قال تعالى: عَنِ الصِّراطِ لَنا |
| 7 | فاد | hawramani_19 | hawramani | contextual | فادَ يفيدُ: تَبَخْتَرَ،كفَيَّدَ، وماتَ،وـ المالُ: ثَبَتَ أو  |
| 8 | الدثر | hawramani_19 | hawramani | contextual | الدَّثْرُ: المالُ الكثيرُ، مالٌ ومالانَ وأموالٌ دَثْرٌ، وبال |
| 9 | مول | hawramani_14 | hawramani | contextual | م و ل: (الْمَالُ) مَعْرُوفٌ وَرَجُلٌ (مَالٌ) أَيْ كَثِيرُ ال |
| 10 | دلف | Al_Mujam_Al_Kabeer | ocr | contextual | المالُ (الإِبلُ): رَزَمَ مِنَ الهُزَالِ. (كَأَنَّه ضِدٌّ) ال |

### Strategy E — Translation Cross-reference
*Query: EN: money (49ms, 24 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | مال بائر | arabterm_arabterm_ec | arabterm | morphological_kin, translation |  |
| 2 | نقد عائم، عملة متأرج | arabterm_arabterm_ec | arabterm | morphological_kin, translation |  |
| 3 | رؤوس أموال متنقلة، أ | arabterm_arabterm_ec | arabterm | morphological_kin, translation |  |
| 4 | عملة أساسية | arabterm_arabterm_ec | arabterm | morphological_kin, translation |  |
| 5 | نقد قانوني | arabterm_arabterm_ec | arabterm | morphological_kin, translation |  |
| 6 | نقد سائل | arabterm_arabterm_ec | arabterm | morphological_kin, translation |  |
| 7 | رأسمال نقدي | arabterm_arabterm_ec | arabterm | morphological_kin, translation |  |
| 8 | تمويل نقدي | arabterm_arabterm_ec | arabterm | morphological_kin, translation |  |
| 9 | تدفق نقدي | arabterm_arabterm_ec | arabterm | morphological_kin, translation |  |
| 10 | توهم نقدي | arabterm_arabterm_ec | arabterm | morphological_kin, translation | عند الزيادة في القيمة الاسمية للنقود دون القيمة الفعلية، يتو |

### Summary
- **Total unique entries:** 336
- **Unique contributions:** A=15, B=200, C=49, D=45, E=24
- **Sources:** arabterm: 263, hawramani: 61, ocr: 15
- **Time:** 6216ms

---

## 2. `awn4-00534261-n` — غافوت

- **POS:** n
- **Lemmas (1):** غافوت
- **Definition:** رقصة فرنسية رسمية قديمة بإيقاع رباعي

### Strategy A — Headword Match (SQL Tier 1)
*Query: غافوت (1ms, 0 results)*

*No results*

### Strategy B — Root Family (SQL Tier 2)
*Query: (no root found) (0ms, 0 results)*

*No results*

### Strategy C — Definition Search (FTS5 BM25)
*Query: رقصة OR فرنسية OR رسمية OR قديمة OR بإيقاع OR رباعي (32ms, 50 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | بطانة فرنسية | arabterm_arabterm_te | arabterm | morphological_kin, translation | تبطين جزئي للملابس الرياضية (تبطين ما بين الكتف وأسفل الظهر  |
| 2 | رقصة ألمانية | arabterm_arabterm_ar | arabterm | morphological_kin, translation |  |
| 3 | رقصة غنائية قديمة | arabterm_arabterm_ar | arabterm | morphological_kin, translation |  |
| 4 | كافوت | arabterm_arabterm_ar | arabterm | synonym_candidate, translation | رقصة فرنسية |
| 5 | بوريه | arabterm_arabterm_ar | arabterm | synonym_candidate, translation | رقصة فرنسية |
| 6 | شاكون | arabterm_arabterm_ar | arabterm | synonym_candidate, morphologic | صيغة رقصة قديمة |
| 7 | فاراندول | arabterm_arabterm_ar | arabterm | synonym_candidate, translation | رقصة اسبانية فرنسية |
| 8 | لوريه | arabterm_arabterm_ar | arabterm | synonym_candidate, translation | رقصة قديمة |
| 9 | منويت | arabterm_arabterm_ar | arabterm | synonym_candidate, translation | رقصة قديمة |
| 10 | ريجودون | arabterm_arabterm_ar | arabterm | synonym_candidate, translation | رقصة فرنسية |

### Strategy D — ColBERT Semantic Search
*Query: D1:'غافوت' | D2:def | D3:combined (8576ms, 54 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | جفت | hawramani_34 | hawramani | contextual | جفتجِفْت [مفرد]: ج جُفُوت:1 - (طب) آلة جراحيَّة يستخدمها الط |
| 2 | جحف | hawramani_37 | hawramani | contextual | جحفابن دريد: جحف الشيء برجله: إذا رفسه بها حتى يرمي به.وقال  |
| 3 | ترهلة | hawramani_32 | hawramani | contextual | تَرهْلة: نبات كان يستعمل في المغرب مكان غافت قبل أن يعرفوا ه |
| 4 | خفت | hawramani_19 | hawramani | contextual | خَفَتَ خُفوتاً: سَكَنَ وسَكَتَ،وـ خُفاتاً: مات فَجْأَةً.والخ |
| 5 | غفا | hawramani_21 | hawramani | contextual | [غفا] نه: فيه: "فغفوت غفوة"، أي نمت نومة خفيفة، أغفى إغفاء و |
| 6 | غفا | hawramani_6 | hawramani | contextual | [غفا] أغْفَيْتُ إغْفاءً، أي نمت. قال ابن السكيت: ولا تقل غَف |
| 7 | خفت | hawramani_8 | hawramani | contextual | (خَ ف ت) الخَفْتُ، والخُفات: الضَّعف من الجُوع وَنَحْوه، وَق |
| 8 | فوط | hawramani_34 | hawramani | contextual | فوطفُوطة [مفرد]: ج فُوطات وفُوَط:1 - إزار يُلبس فوق الثياب ل |
| 9 | غفا | hawramani_1 | hawramani | contextual | غفا: الأَزهري: غَفَا الرجل وغيره غفوة إِذا نامَ نومَةً خَفيف |
| 10 | علفت | hawramani_1 | hawramani | contextual | علفت: في الرباعي: العِلْفِتانُ الضَّخْم مِن الرجال الشديد؛ و |

### Strategy E — Translation Cross-reference
*Query: EN: gavotte (6ms, 1 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | الغافوتيّة: «أ» رقصة | arabterm_al_mawrid_a | arabterm | translation_bridge | الغافوتيّة: «أ» رقصة ذات أصل فرنسيّ ريفيّ تتميَّز برفع القدم |

### Summary
- **Total unique entries:** 105
- **Unique contributions:** A=0, B=0, C=50, D=54, E=1
- **Sources:** arabterm: 50, hawramani: 53, ocr: 2
- **Time:** 8615ms

---

## 3. `awn4-11537927-n` — شفط, مص

- **POS:** n
- **Lemmas (2):** شفط ، مص
- **Definition:** قوة على مساحة ناتجة عن فرق الضغط

### Strategy A — Headword Match (SQL Tier 1)
*Query: شفط, مص (4ms, 12 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | شفط | hawramani_34 | hawramani | lemma_match | شفطشفَطَ يَشفِط، شَفْطًا، فهو شافط، والمفعول مشفوط• شفَط الم |
| 2 | شَفَطَ | Al_Mujam_Al_Kabeer | ocr | lemma_match | فلانٌ السائلَ ـِ شَفْطًا: امتصَّه وسَحَبَه المالَ ونَحْوه: أ |
| 3 | مَصّ | arabterm_unified_med | arabterm | lemma_match, translation_bridg |  |
| 4 | مص | hawramani_35 | hawramani | lemma_match | (مص)الْقصب وَنَحْوه مصا شربه شربا رَفِيقًا وَيُقَال مص من ال |
| 5 | مص | hawramani_36 | hawramani | lemma_match | مصمَصِصْتُ الشيْءَ وامْتَصَصْتُه. ومُصَاصُه: ما امْتَصَصْتَ  |
| 6 | مص | hawramani_49 | hawramani | lemma_match | مص 1 مَصَّهُ, (A, Msb,) first Pers\. مَصِصْتُ, (S, M, Msb, K |
| 7 | مَصَّ  | hawramani_7 | hawramani | lemma_match | (مَصَّ) الْمِيمُ وَالصَّادُ أَصْلٌ صَحِيحٌ يَدُلُّ عَلَى شِب |
| 8 | مص | hawramani_32 | hawramani | lemma_match | مص: امتص: جف، يبس، قسا (للشجرة) (فوك). ورق المص: ورق نشاف (ب |
| 9 | مَصَّ | Al_Waseet | ocr | lemma_match | القَصَبَ ونحوه: شربه شربًا رفيقًا من الدُّنيا: نال القليل من |
| 10 | مَصَّ | Kitab_Al_Ayn | ocr | lemma_match | شرب الشيء بجذب النفس |

### Strategy B — Root Family (SQL Tier 2)
*Query: root=شفط,مصص (42ms, 200 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | الامتصاص | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 2 | إمتصاص | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 3 | امتصاص | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 4 | إمتصاص هضمي | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 5 | امتصاص الماء | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 6 | ممتص الصدمات | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 7 | امتصاص الصوت | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 8 | (1) مص abate
(2) الت | arabterm_al_mawrid_a | arabterm | morphological_kin, translation | (1) مص abate (2) التخفيض: مبلغ يُلغى من الضريبة. plea in aba |
| 9 | (1) مص abide
(2) الت | arabterm_al_mawrid_a | arabterm | morphological_kin, translation | (1) مص abide (2) التزام؛ تقيُّدٌ. |
| 10 | (1) امتصاص
(2) استغر | arabterm_al_mawrid_a | arabterm | morphological_kin, translation | (1) امتصاص (2) استغراق؛ انهماك. |

### Strategy C — Definition Search (FTS5 BM25)
*Query: قوة OR مساحة OR ناتجة OR فرق OR الضغط (58ms, 50 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | لا مركزية | arabterm_arabterm_ci | arabterm | definition_support, morphologi | وهي المسافة بين نقطة تطبيق قوة على مقطع العمود ومركز مساحة م |
| 2 | إجهاد القصّ | arabterm_arabterm_ci | arabterm | definition_support, morphologi | وهو قوة القص المطبّقة على واحدة مساحة المقطع |
| 3 | إجهاد الشد الأقصى | arabterm_arabterm_ci | arabterm | definition_support, morphologi | حاصل قسمة قوة الشد التي يحدث عندها انهيار العينة على مساحة م |
| 4 | فَقْد الضغط | arabterm_arabterm_ci | arabterm | morphological_kin, translation | فرق منسوب الماء بين الطرف العلوي و السفلي من عملية معالجة بس |
| 5 | فرق الإجهادين الرئيس | arabterm_arabterm_ci | arabterm | definition_support, morphologi | فرق الإجهادين الرئيسين الأعظمي والأصغري المطبق على عينة تربة |
| 6 | قوة ضغط | arabterm_arabterm_tr | arabterm | morphological_kin, translation | مقاومة الضغط يتم من ضغط خارجي من دون كسر |
| 7 | درجة الضغط | arabterm_arabterm_tr | arabterm | definition_support, morphologi | على العكس من المحركات ذات القبة حيث مساحة اليانات على الضاغط |
| 8 | إيرادات ناتجة عن إعا | arabterm_arabterm_tr | arabterm | morphological_kin, translation |  |
| 9 | أضرار ناتجة عن الميك | arabterm_arabterm_te | arabterm | morphological_kin, translation | تعتبر المنسوجات من الألياف السليلوزية،  السليلوز المتحلل بال |
| 10 | حلقة ضغط | arabterm_arabterm_au | arabterm | morphological_kin, translation | هي حلقة معدنية توجد في الوصلات الطرفية لتثبيتات المواسير وال |

### Strategy D — ColBERT Semantic Search
*Query: D1:'شفط; مص' | D2:def | D3:combined (3681ms, 56 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | سفط | hawramani_34 | hawramani | contextual | سفطسَفَط [مفرد]: ج أسْفاط:1 - قُفّة، وعاء مصنوع من أغصان الش |
| 2 | رشف | hawramani_6 | hawramani | contextual | [رشف] الرَشْفُ: المصُّ. وقد رَشَفَهُ يَرْشُفُه ويَرْشِفُه ،  |
| 3 | مصمص | hawramani_32 | hawramani | contextual | مصمص: مصمص: (مضاعفة كلمة مص) ارتشف، رشف، رضع أو رضع (وبالأسب |
| 4 | مسفق | hawramani_32 | hawramani | contextual | مسفق: مسفق أو مصفق (جاءت من مسفقة أو مصفقة وجذرها سفق أو صفق |
| 5 | صطب | hawramani_34 | hawramani | contextual | صطبمَصْطَبة/ مِصْطَبة [مفرد]: ج مَصْطبات ومَصاطِبُ:1 - مسْطب |
| 6 | رشيف | hawramani_48 | hawramani | contextual | رَشِيف من (ر ش ف) مص الماء ونحوه بالشفاه، واستقصاء ما في الإ |
| 7 | مصت | hawramani_51 | hawramani | contextual | مصت  مَصَتَ(n. ac. مَصْت) a. Squeezed.  b. Compressed.  c. P |
| 8 | مصص | hawramani_18 | hawramani | contextual | المص: عبارة عن عمل الشفة خاصة. |
| 9 | شفط | hawramani_34 | hawramani | lemma_match | شفطشفَطَ يَشفِط، شَفْطًا، فهو شافط، والمفعول مشفوط• شفَط الم |
| 10 | رشف | hawramani_37 | hawramani | contextual | رشفالليث: الرشف - بالتحريك -: الماء القليل يبقى ف الحوض؛ وهو |

### Strategy E — Translation Cross-reference
*Query: EN: suction (12ms, 28 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | ضاغِط المصّ | arabterm_arabterm_ci | arabterm | morphological_kin, translation | الضاغط الكائن بين محور المضخة ومنسوب الماء عند طرف سحب المضخ |
| 2 | امتصاص ريحي | arabterm_arabterm_re | arabterm | morphological_kin, translation | ist die Kraftwirkung einer Windströmung an Oberflächen infol |
| 3 | ارتفاع الامتصاص | arabterm_arabterm_wa | arabterm | morphological_kin, translation | رمز المُعادلات: S |
| 4 | صَمَام شَفْط | arabterm_arabterm_wa | arabterm | morphological_kin, translation | صمام تكسح بواسطته المياه المُتسخة والهواء عن طريق وصلة صرف م |
| 5 | أنبوب سحْب | arabterm_arabterm_wa | arabterm | morphological_kin, translation | أنبوب من الصُلب أو الخرسانة المُسلحة، تتمثل وظيفته في سحب (ش |
| 6 | فِعْل تحاتّ بالمص | arabterm_arabterm_wa | arabterm | morphological_kin, translation |  |
| 7 | ثَعب | arabterm_arabterm_ph | arabterm | morphological_kin, translation |  |
| 8 | جهاز ماص، جهاز مص | arabterm_arabterm_ph | arabterm | morphological_kin, translation |  |
| 9 | مضخة ماصّة | arabterm_arabterm_ph | arabterm | morphological_kin, translation |  |
| 10 | شرّاقة، مروحة، ماصة | arabterm_arabterm_ch | arabterm | translation_bridge |  |

### Summary
- **Total unique entries:** 343
- **Unique contributions:** A=9, B=200, C=50, D=53, E=28
- **Sources:** arabterm: 278, hawramani: 56, ocr: 12
- **Time:** 3800ms

---

## 4. `awn4-00912746-n` — بناء, تشييد, عمارة

- **POS:** n
- **Lemmas (3):** بناء ، تشييد ، عمارة
- **Definition:** فعل بناء أو إنشاء شيء ما
- **Examples:** اضطررنا لاتخاذ تحويلة أثناء البناء | كانت هوايته بناء القوارب

### Strategy A — Headword Match (SQL Tier 1)
*Query: بناء, تشييد, عمارة (5ms, 23 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | بناء | arabterm_agrovoc | arabterm | lemma_match, translation_bridg |  |
| 2 | بناء | arabterm_arabterm_ar | arabterm | lemma_match, translation_bridg |  |
| 3 | بناء | arabterm_arabterm_ed | arabterm | lemma_match, translation_bridg |  |
| 4 | بناء | arabterm_arabterm_el | arabterm | lemma_match, translation_bridg | علم البناء الصحيح للجملة (العبارة). وهو جزءٌ من النحو ويختّص |
| 5 | بناء | arabterm_arabterm_ge | arabterm | lemma_match, translation_bridg |  |
| 6 | بناء | arabterm_arabterm_ge | arabterm | lemma_match, translation_bridg |  |
| 7 | بناء | arabterm_arabterm_ge | arabterm | lemma_match, translation_bridg |  |
| 8 | بناء | arabterm_arabterm_hy | arabterm | lemma_match, translation_bridg |  |
| 9 | بِناء | arabterm_arabterm_la | arabterm | lemma_match, translation_bridg | كل مجموعة ملائمة من الكلمات التي تدخل في تركيب أوسع. |
| 10 | بِناء | arabterm_arabterm_la | arabterm | lemma_match, translation_bridg | بناء يرتبط بالفعل وبالفعل المساعد ويشير إلى العلاقة النحوية  |

### Strategy B — Root Family (SQL Tier 2)
*Query: root=بن,بنى,عمر (172ms, 200 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | بنات وردان | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 2 | بنت الربان | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 3 | بنية زراعية | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 4 | البنية التحتية الزرق | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 5 | البنية التحتية الزرق | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 6 | بنية خلوية | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 7 | البنية الفوقية للخلي | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 8 | بنات | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 9 | البنية التحتية الاقت | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 10 | بنية إقتصادية | arabterm_agrovoc | arabterm | morphological_kin, translation |  |

### Strategy C — Definition Search (FTS5 BM25)
*Query: فعل OR بناء OR إنشاء OR شيء (47ms, 50 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | فَعَلَ | Maqayis_Lugha | ocr | definition_support, morphologi | إحداث شيء من عمل وغيره |
| 2 | إنشاء قاعِدي | arabterm_arabterm_ci | arabterm | morphological_kin, translation | الجزء الواقع تحت الأرض من المنشإ وخاصة الأساسات |
| 3 | ضبط الفيضانات | arabterm_arabterm_cl | arabterm | definition_support, morphologi | مجموع التقنيات والأساليب والإجراءات المستخدمة للحد من أو منع |
| 4 | إنشاء خزانات للتزود  | arabterm_arabterm_tr | arabterm | morphological_kin, translation |  |
| 5 | إنشاء محطة | arabterm_arabterm_tr | arabterm | morphological_kin, translation |  |
| 6 | إنشاء بحِزم القش | arabterm_arabterm_re | arabterm | morphological_kin, translation | طريقة معمارية تُستخدّم فيها حزم (بالات) القش - التي تنتج من  |
| 7 | سَعَة إنشاء المبنى | arabterm_arabterm_wa | arabterm | morphological_kin, translation |  |
| 8 | إنشاء بالخْرَسانة | arabterm_arabterm_wa | arabterm | morphological_kin, translation |  |
| 9 | وصلات إنشاء | arabterm_arabterm_wa | arabterm | morphological_kin, translation |  |
| 10 | إنشاء خط أنابيب | arabterm_arabterm_wa | arabterm | morphological_kin, translation |  |

### Strategy D — ColBERT Semantic Search
*Query: D1:'بناء; تشييد; عمارة' | D2:def | D3:combined (3894ms, 46 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | البناء | hawramani_24 | hawramani | contextual | البناء:[في الانكليزية] Construction [ في الفرنسية] Construct |
| 2 | إنشاء | hawramani_18 | hawramani | contextual | الإنشاء: قد يقال على الكلام الذي ليس لنسبته خارجٌ تطابقه أو  |
| 3 | تعمير | hawramani_33 | hawramani | contextual | تعميرالجذر: ع م ر مثال: وزارة الإسكان والتعميرالرأي: مرفوضةا |
| 4 | العمارة | hawramani_35 | hawramani | contextual | (الْعِمَارَة) كل شَيْء على الرَّأْس من عِمَامَة وقلنسوة وَنَ |
| 5 | شيد | hawramani_1 | hawramani | contextual | شيد: الشِّيدُ، بالكسر: كلُّ ما طُليَ به الحائطُ من جِصٍّ أَو |
| 6 | شاد | Al_Mujam_Al_Kabeer | ocr | contextual | البناءَ: رفعه وأحكمه المَجْدَ: بناه وأقامه بالعَقْل مَجْدَه: |
| 7 | الإنشاء | hawramani_22 | hawramani | contextual | الإنشاء: لغة إيجاد الشيء وترتيبه، وأكثر ما يقال في الحيوان.  |
| 8 | نعمار | hawramani_48 | hawramani | contextual | نِعْمَار صورة كتابية صوتية من معمار بمعنى الطويل العمر، والك |
| 9 | بنى | Al_Mujam_Al_Kabeer | ocr | contextual | البناء ضمُّ الشيء بعضه إلى بعض فلانٌ على فلانة - بناءً: دخل  |
| 10 | تعميرات | hawramani_48 | hawramani | contextual | تَعْمِيرات من (ع م ر) جمع تَعْمِير: طول المر، والبناء على ال |

### Strategy E — Translation Cross-reference
*Query: EN: construction, building (20ms, 29 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | كود البناء | arabterm_arabterm_ci | arabterm | morphological_kin, translation | تعليمات تحكم تصميم وإشادة الأبنية |
| 2 | مُخطَّط عام للبناء | arabterm_arabterm_ci | arabterm | morphological_kin, translation | رسم تخطيطي مبسّط يبين مساحات البناء الرئيسة |
| 3 | مواد البناء | arabterm_arabterm_ci | arabterm | morphological_kin, translation | إجمالاً كل المواد التي تستعمل في تنفيذ هيكل وإكساء الأبنية |
| 4 | جِير | arabterm_arabterm_tr | arabterm | morphological_kin, translation | ناتج الحجر الجيري والدولوميت أو رابط الحجر الجيري |
| 5 | رخصة بناء | arabterm_arabterm_re | arabterm | morphological_kin, translation |  |
| 6 | مبنى أخضر | arabterm_arabterm_re | arabterm | morphological_kin, translation | مصطلح شائع يشير إلى طريقة تصميم في تكنولوجيا البناء تُستخدم  |
| 7 | هندسة معمارية | arabterm_arabterm_wa | arabterm | morphological_kin, translation |  |
| 8 | مشروع بناء | arabterm_arabterm_wa | arabterm | morphological_kin, translation |  |
| 9 | مَوْقِع البناء | arabterm_arabterm_wa | arabterm | morphological_kin, translation |  |
| 10 | مِنطَقة مُكتظَّة بال | arabterm_arabterm_wa | arabterm | morphological_kin, translation |  |

### Summary
- **Total unique entries:** 346
- **Unique contributions:** A=22, B=200, C=49, D=44, E=29
- **Sources:** arabterm: 293, hawramani: 46, ocr: 9
- **Time:** 4138ms

---

## 5. `awn4-00493346-v` — دنس, لوث

- **POS:** v
- **Lemmas (2):** دنس ، لوث
- **Definition:** تدنيس شيء مقدس أو تلويث بيئة نقية
- **Examples:** دنس سكان البلدة النهر بإفراغ مياه الصرف الصحي الخام فيه

### Strategy A — Headword Match (SQL Tier 1)
*Query: دنس, لوث (11ms, 45 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | دنس | hawramani_35 | hawramani | lemma_match | (دنس)ثَوْبه دنسا ودناسة توسخ وتلطخ وَيُقَال دنس عرضه وخلقه ف |
| 2 | دنس | hawramani_34 | hawramani | lemma_match | دنسدنِسَ يَدنَس، دَنَسًا ودَناسةً، فهو دَنِس• دنِس ثوبُه/ دن |
| 3 | دنس | hawramani_9 | hawramani | lemma_match | د ن س دنس الثوب دنساً، وتدنّس، ودنسته. ومن المجاز: تدنس عرضه |
| 4 | دنس | hawramani_37 | hawramani | lemma_match | دنسالدَّنَس: الوَسَخ. ودَنِسَ الثَّوبُ يَدْنَسُ دَنَساً ودَن |
| 5 | دنس | hawramani_36 | hawramani | lemma_match | دنسالدنَسُ: لَطْخُ الوَسَخِ ونَحْوِه. ورَجُلٌ دَنِس المُرُوْ |
| 6 | دنس | hawramani_49 | hawramani | lemma_match | دنس 1 دَنِسَ, aor. ـَ inf. n. دَنَسٌ (S, A, K) and دَنَاسَةٌ |
| 7 | دنس | hawramani_51 | hawramani | lemma_match | دنس  دَنِسَ(n. ac. دَنَس  دَنَاْسَة) a.  Was dirty, filthy,  |
| 8 | دَنَسَ  | hawramani_7 | hawramani | lemma_match | (دَنَسَ) الدَّالُ وَالنُّونُ وَالسِّينُ كَلِمَةٌ وَاحِدَةٌ،  |
| 9 | دنس | hawramani_1 | hawramani | lemma_match | دنس: الدَّنَسُ في الثياب: لَطْخُ الوسخ ونحوه حتى في الأَخلاق |
| 10 | دنس | hawramani_8 | hawramani | lemma_match | د ن س الدَّنَسُ لَطْخُ الوَسَخِ والجمع أَدْناسٌ دَنِسَ دَنَس |

### Strategy B — Root Family (SQL Tier 2)
*Query: root=دنس,لث,لوث (29ms, 200 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | (1) يُدنِّس [المقدَّ | arabterm_al_mawrid_a | arabterm | morphological_kin, translation | (1) يُدنِّس [المقدَّسات] (2) يُلوِّث [الماء إلخ]. |
| 2 | (1) تدنيس المقدَّسات | arabterm_al_mawrid_a | arabterm | synonym_candidate, morphologic | (1) تدنيس المقدَّسات [أو المعابد أو انتهاك حُرماتها أو سرقتُ |
| 3 | تدنيس طقوسي | arabterm_arabterm_so | arabterm | morphological_kin, translation |  |
| 4 | تَدَنُّسٌ نَهارِيّ ( | arabterm_unified_med | arabterm | morphological_kin, translation |  |
| 5 | تَدَنُّسٌ لَيْلِيّ ( | arabterm_unified_med | arabterm | morphological_kin, translation |  |
| 6 | تَدَنُّسٌ يَوْمِيّّ  | arabterm_unified_med | arabterm | morphological_kin, translation |  |
| 7 | الدنس | hawramani_35 | hawramani | morphological_kin | (الدنس) الْوَسخ (ج) أدناس |
| 8 | تدنس | hawramani_35 | hawramani | morphological_kin | (تدنس) الثَّوْب اتسخ |
| 9 | الدَّنَسُ | hawramani_19 | hawramani | morphological_kin | الدَّنَسُ، محركةً: الوسخُ.دَنِسَ الثَّوْبُ والعِرْضُ، كفرِحَ |
| 10 | أَدْنَسَ | Al_Mujam_Al_Kabeer | ocr | morphological_kin | الشَّيْءَ: وَسَّخَه |

### Strategy C — Definition Search (FTS5 BM25)
*Query: تدنيس OR شيء OR مقدس OR تلويث OR بيئة OR نقية (26ms, 46 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | موقع طبيعي مقدس | arabterm_arabterm_cl | arabterm | morphological_kin, translation | مساحات من الأراضي أو المياه لها أهمية روحية خاصة لشعوب ولمجت |
| 2 | موقع مقدس | arabterm_arabterm_cl | arabterm | morphological_kin, translation | منطقة ذات أهمية روحية خاصة لشعوب ولمجتمعات. |
| 3 | مياه نقية | arabterm_arabterm_re | arabterm | translation_bridge | عموما المياه التي تمت معالجتها وأصبحت مياه نقية، وعلى سبيل ا |
| 4 | حق تلويث | arabterm_arabterm_re | arabterm | morphological_kin, translation | (انظر: [حق إطلاق انبعاثات](http://www.arabterm.org/index.php |
| 5 | رخصة تلويث | arabterm_arabterm_re | arabterm | morphological_kin, translation | شهادة تعطي الحق في إطلاق انبعاثات. |
| 6 | مياه نقية | arabterm_arabterm_wa | arabterm | translation_bridge |  |
| 7 | خَزّان مياه نقية | arabterm_arabterm_wa | arabterm | morphological_kin, translation |  |
| 8 | تَنقية (الغاز) | arabterm_arabterm_wa | arabterm | morphological_kin, translation |  |
| 9 | مقدس | arabterm_arabterm_so | arabterm | morphological_kin, translation |  |
| 10 | مُقَدَّس | arabterm_arabterm_la | arabterm | morphological_kin, translation |  |

### Strategy D — ColBERT Semantic Search
*Query: D1:'دنس; لوث' | D2:def | D3:combined (6949ms, 46 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | طنف | hawramani_32 | hawramani | contextual | طنف: طنَّف (بالتشديد): وسَّخ، دنَّس، لطّخ. لوث (باين سميث 14 |
| 2 | لوث | hawramani_12 | hawramani | lemma_match | (ل و ث) : (لَوَّثَ) الْمَاءَ كَدَّرَهُ (وَلَوَّثَ) ثِيَابَهُ |
| 3 | سخمط | hawramani_32 | hawramani | contextual | سخمط: سَخْمطَ: لوَّث، دنسَّ. وسّخ، لخبط أساء الرسم، أساء الع |
| 4 | دنس | hawramani_51 | hawramani | lemma_match | دنس  دَنِسَ(n. ac. دَنَس  دَنَاْسَة) a.  Was dirty, filthy,  |
| 5 | ندس | Al_Waseet | ocr | contextual | فلاناً بشيءٍ: طعنه به خفيفاً بفلان الأرضَ: صرَعَه الشيءَ عن  |
| 6 | لوث | hawramani_25 | hawramani | lemma_match | لوث: ( {اللَّوْثُ: القُوَّةُ) والشِّدّة، قَالَ الأَعْشَي:بِذ |
| 7 | دنس | hawramani_49 | hawramani | lemma_match | دنس 1 دَنِسَ, aor. ـَ inf. n. دَنَسٌ (S, A, K) and دَنَاسَةٌ |
| 8 | خرطش | hawramani_32 | hawramani | contextual | خرطش: خَرطش: شطب، ضرب على الكتابة، محا (بوشر). تخرطش: بعد أن |
| 9 | دنس  | hawramani_7 | hawramani | lemma_match | (دَنَسَ) الدَّالُ وَالنُّونُ وَالسِّينُ كَلِمَةٌ وَاحِدَةٌ،  |
| 10 | ندس | hawramani_32 | hawramani | contextual | ندس: ندس: هي باللاتينية inclinare ( فوك) وفي (فوك) أيضا ندس  |

### Strategy E — Translation Cross-reference
*Query: EN: foul, befoul, defile, maculate (16ms, 28 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | المنصة | arabterm_arabterm_te | arabterm | morphological_kin, translation | الممر المخصص لمرور عارضات وعارضي الأزياء |
| 2 | عرض الموضة | arabterm_arabterm_te | arabterm | morphological_kin, translation | تنظم هذه العروض، منذ الثمانينيات، من طرف دور العرض ووكالات و |
| 3 | رائحة كريهة | arabterm_arabterm_wa | arabterm | morphological_kin, translation |  |
| 4 | مَجْرَى، ممر ضَيِّق | arabterm_arabterm_ge | arabterm | translation_bridge |  |
| 5 | مجرى، ممر ضيق | arabterm_arabterm_se | arabterm | translation_bridge |  |
| 6 | مرساة مشتبكة | arabterm_arabterm_oc | arabterm | morphological_kin, translation |  |
| 7 | سند مشروط | arabterm_arabterm_oc | arabterm | morphological_kin, translation |  |
| 8 | مياه خطرة | arabterm_arabterm_oc | arabterm | translation_bridge |  |
| 9 | ارتطم، تصادم | arabterm_arabterm_oc | arabterm | translation_bridge |  |
| 10 | مصرف للهواء الملوث | arabterm_arabterm_ma | arabterm | morphological_kin, translation |  |

### Summary
- **Total unique entries:** 350
- **Unique contributions:** A=31, B=199, C=46, D=31, E=28
- **Sources:** arabterm: 209, hawramani: 138, ocr: 18
- **Time:** 7034ms

---

## 6. `awn4-01663142-v` — شكّل, صاغ, قولب

- **POS:** v
- **Lemmas (3):** شكّل ، صاغ ، قولب
- **Definition:** صنع شيء ما، عادة لوظيفة معينة
- **Examples:** شكلت كرات الأرز بعناية | شكّل أسطوانات من العجين | شكّل تمثالاً

### Strategy A — Headword Match (SQL Tier 1)
*Query: شكّل, صاغ, قولب (13ms, 67 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | شكل | arabterm_agrovoc | arabterm | lemma_match, translation_bridg |  |
| 2 | شكْل | arabterm_arabterm_ch | arabterm | lemma_match, translation_bridg |  |
| 3 | شكل | arabterm_arabterm_ed | arabterm | lemma_match, translation_bridg |  |
| 4 | شكل | arabterm_arabterm_ge | arabterm | lemma_match, translation_bridg |  |
| 5 | شَكْل | arabterm_arabterm_ge | arabterm | lemma_match, translation_bridg |  |
| 6 | شَكْل | arabterm_arabterm_ge | arabterm | lemma_match, translation_bridg |  |
| 7 | شَكْل | arabterm_arabterm_gr | arabterm | lemma_match, translation_bridg |  |
| 8 | شَكْل | arabterm_arabterm_in | arabterm | lemma_match, translation_bridg |  |
| 9 | شَكْـل | arabterm_arabterm_la | arabterm | lemma_match, translation_bridg | شكل وظيفي مختصر بغاية إبداع الفن للفن، لأن الأدب ليس مجرد شك |
| 10 | شَكْل | arabterm_arabterm_la | arabterm | lemma_match, translation_bridg |  |

### Strategy B — Root Family (SQL Tier 2)
*Query: root=شكل,صغ,صوغ,قلب (112ms, 200 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | يُصغي بتلهّف إلى كلّ | arabterm_al_mawrid_a | arabterm | morphological_kin, translation | يُصغي بتلهّف إلى كلّ كلمة يقولها. |
| 2 | (1) يُصغي
(2) يُوْلي | arabterm_al_mawrid_a | arabterm | morphological_kin, translation | (1) يُصغي (2) يُوْلي أذنًا صاغية. |
| 3 | (1) يصوغ
(2) يحرِّر؛ | arabterm_al_mawrid_a | arabterm | morphological_kin, translation | (1) يصوغ (2) يحرِّر؛ ينقّح؛ يُعِدّ للطباعة. |
| 4 | يَصُوغ أو يُصيِّغ ثا | arabterm_al_mawrid_a | arabterm | morphological_kin, translation | يَصُوغ أو يُصيِّغ ثانيةً. |
| 5 | مَصَاغَةُ معطياتٍ تَ | arabterm_scs_informa | arabterm | morphological_kin, translation | مختصره: HDF. مَصَاغَةُ ملفاتٍ لتخزين أنواع متعددة من معطيات  |
| 6 | مَصَاغَةٌ ذاتُ محتوى | arabterm_scs_informa | arabterm | morphological_kin, translation | مختصره: MCF. مَصَاغَةٌ مفتوحةٌ لوصفِ معلومات عن محتوى متْنٍ  |
| 7 | مصاغة نص غني | arabterm_scs_informa | arabterm | morphological_kin, translation | مختصره: RTF. مواءَمةٌ لبنيانِ مضمون الوثيقة DCA، تُستخدَمُ ل |
| 8 | مَصَاغَةُ معطيات | arabterm_scs_informa | arabterm | morphological_kin, translation | بنيةٌ تُطبَّق على المعطيات بواسطة برنامجٍ تطبيقي، لتوفير سيا |
| 9 | مَصَاغَةُ التبادل ال | arabterm_scs_informa | arabterm | morphological_kin, translation | مَصَاغَةٌ مؤلفةٌ من ترميز ASCII، يمكِن باستخدامها وضعُ بنية  |
| 10 | مَصاغةٌ منخفضةُ المس | arabterm_scs_informa | arabterm | morphological_kin, translation | إصاغةُ وسيطةِ تخزينٍ فارغة بغية إنشاء مسالك وقطاعات على الوس |

### Strategy C — Definition Search (FTS5 BM25)
*Query: صنع OR شيء OR ما، OR عادة OR لوظيفة OR معينة (73ms, 50 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | مركّبات من صنع الإنس | arabterm_arabterm_ci | arabterm | morphological_kin, translation | تكون عادة مقاومة للتفكك البيولوجي |
| 2 | اصْطِنَاعِيّ | arabterm_arabterm_in | arabterm | morphological_kin, translation | لفظ عام يطلق عادة على لغات البرمجة أو الذكاء في مقابل اللغات |
| 3 | تقييم | arabterm_arabterm_cl | arabterm | definition_support, morphologi | عملية تعبير عن قيمة سلعة أو خدمة معينة في سياق معين (على سبي |
| 4 | إجمالي الصيد المسموح | arabterm_arabterm_cl | arabterm | definition_support, morphologi | مجموع الصيد المسموح به والذي يتم صيده من الموارد خلال فترة ز |
| 5 | فاصل (البطارية) | arabterm_arabterm_re | arabterm | morphological_kin, translation | يُقصد بالفاصل في البطاريات، الطبقة الفاصلة الموجودة بين الأن |
| 6 | مقابلة تقييم | arabterm_arabterm_in | arabterm | definition_support, morphologi | مقابلة تتعلق بتقييم مؤهلات شخص مرشح لوظيفة معينة. |
| 7 | مُصنِّع معدّات أصلي | arabterm_scs_informa | arabterm | morphological_kin, translation | مختصره: OEM. الصانعُ لمعدّةٍ ما. في صناعة الحواسيب والمعدّات |
| 8 | اخْتِبارُ التَّنَدُّ | arabterm_unified_med | arabterm | morphological_kin, translation |  |
| 9 | اخْتِبارُ ليويس وبيك | arabterm_unified_med | arabterm | morphological_kin, translation |  |
| 10 | اخْتِبارُ التَّدْوير | arabterm_unified_med | arabterm | morphological_kin, translation |  |

### Strategy D — ColBERT Semantic Search
*Query: D1:'شكّل; صاغ; قولب' | D2:def | D3:combined (5121ms, 52 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | صنع | hawramani_32 | hawramani | contextual | صنع: صنع. ما أصنع ب: ما العمل؟ ماذا أعمل (كليلة ودمنة ص251). |
| 2 | معتاد | hawramani_48 | hawramani | contextual | مُعْتَاد من (ع و د) من يجعل الشيء عادة له. |
| 3 | صنع | Maqayis_Lugha | ocr | contextual | أصل صحيح واحد وهو عمل الشيء صنعا |
| 4 | كلح | hawramani_51 | hawramani | contextual | كلح  كَلَحَ(n. ac. كُلَاْح  كُلُوْح) a.  Frowned; was forbid |
| 5 | ترج | hawramani_19 | hawramani | contextual | تَرَجَ: اسْتَتَرَ، وكفَرِحَ: أشْكَلَ عليه شيءٌ مِن علْمٍ أو  |
| 6 | شقل | hawramani_51 | hawramani | contextual | شقل  شَقَلَ(n. ac. شَقْل) a.  Weighed (money).  b. Raised, l |
| 7 | سقل | hawramani_51 | hawramani | contextual | سقل  سَقَلَ(n. ac. سَقْل) a. Polished.  سُقْلa. Waist.  سَقْ |
| 8 | حسكل | hawramani_7 | hawramani | contextual | (الْحِسْكِلُ) : الصِّغَارُ مِنْ كُلِّ شَيْءٍ. وَهَذَا مِمَّا |
| 9 | جعل | hawramani_18 | hawramani | contextual | الجعل: ما يجعل للعامل على عمله. |
| 10 | شقء | hawramani_51 | hawramani | contextual | شقء  شَقَأَ(n. ac. شَقْء) a.  Came through, appeared (tooth) |

### Strategy E — Translation Cross-reference
*Query: EN: shape, form, work, mold, mould (28ms, 26 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | قَالَبٌ | arabterm_arabterm_ci | arabterm | morphological_kin, translation | قالب مؤقت ينفذ لاحتواء الخرسانة خلال الصب، وبضعة أيام بعده ل |
| 2 | قَالَبٌ | arabterm_arabterm_ci | arabterm | morphological_kin, translation | قالب خشبي يستعمل غالباً بشكل مؤقت لتصب الخرسانة فيه حتى تتصل |
| 3 | فطر خيطي | arabterm_arabterm_cl | arabterm | morphological_kin, translation | فطريات خيطية متعددة الخلايا. |
| 4 | هَيْئَة | arabterm_arabterm_te | arabterm | morphological_kin, translation | الهيئة أو الشكل العام لقطعة من الملابس. |
| 5 | قوة السحب الشكلية | arabterm_arabterm_wa | arabterm | morphological_kin, translation |  |
| 6 | شكل حرف L | arabterm_arabterm_ch | arabterm | morphological_kin, translation |  |
| 7 | قالب | arabterm_arabterm_ch | arabterm | morphological_kin, translation |  |
| 8 | انطباع | arabterm_arabterm_ge | arabterm | morphological_kin, translation | الانطباع الذي تتركه صَدَفَة أو قوقعة على الصخر الذي يحتويها  |
| 9 | انطباع | arabterm_arabterm_se | arabterm | morphological_kin, translation | الانطباع الذي تتركه صدفة أو قوقعة على الصخر الذي يحتويها وقد |
| 10 | علامة ثنائية المخروط | arabterm_arabterm_oc | arabterm | morphological_kin, translation |  |

### Summary
- **Total unique entries:** 395
- **Unique contributions:** A=67, B=200, C=50, D=52, E=26
- **Sources:** arabterm: 199, hawramani: 171, ocr: 25
- **Time:** 5350ms

---

## 7. `awn4-00865514-a` — نظري

- **POS:** a
- **Lemmas (1):** نظري
- **Definition:** يهتم بالنظريات بدلاً من تطبيقاتها العملية
- **Examples:** فيزياء نظرية

### Strategy A — Headword Match (SQL Tier 1)
*Query: نظري (2ms, 7 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | نظري | arabterm_arabterm_ed | arabterm | lemma_match, translation_bridg |  |
| 2 | نظري | arabterm_arabterm_ge | arabterm | lemma_match, translation_bridg |  |
| 3 | نظري | arabterm_arabterm_ma | arabterm | lemma_match, translation_bridg |  |
| 4 | نظري | arabterm_arabterm_ph | arabterm | lemma_match, translation_bridg |  |
| 5 | نظري | arabterm_arabterm_ph | arabterm | lemma_match, translation_bridg |  |
| 6 | نظري | arabterm_arabterm_se | arabterm | lemma_match, translation_bridg |  |
| 7 | نظري | hawramani_18 | hawramani | lemma_match | النظري: هو الذي يتوقف حصوله على نظر وكسب، كتصور النفس والعقل |

### Strategy B — Root Family (SQL Tier 2)
*Query: root=نظر (89ms, 200 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | نظرية بايزي | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 2 | نظير الكروية السمراء | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 3 | نظيرات الرمحيات العق | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 4 | نظائر الأمريسيوم | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 5 | نظائر الأنتيموان | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 6 | نظائر الأرغون | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 7 | نظائر الباريوم | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 8 | نظائر البريليوم | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 9 | نظائر البزموت | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 10 | نظائر البورون | arabterm_agrovoc | arabterm | morphological_kin, translation |  |

### Strategy C — Definition Search (FTS5 BM25)
*Query: يهتم OR بالنظريات OR بدلا OR تطبيقاتها OR العملية (12ms, 50 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | العَمَلِيَّةُ | Al_Waseet | ocr | morphological_kin | جملة أعمال تُحدث أثراً خاصّاً مثل عملية جراحية |
| 2 | ﺔﻳﻮﻀﻋ ﺔﻗﺎﻄﺑ | arabterm_arabterm_cl | arabterm | definition_support, translatio | بطاقة 'عضوي' تعلن للمستهلك أن السلعة قد تم إنتاجها باستخدام  |
| 3 | خدمات لوجستيكية عكسي | arabterm_arabterm_cl | arabterm | definition_support, morphologi | عملية جمع المنتجات والمواد المستخدمة من الزبائن والمستعملين  |
| 4 | اضطراب العملية | arabterm_arabterm_tr | arabterm | morphological_kin, translation |  |
| 5 | تقسيم العملية | arabterm_arabterm_tr | arabterm | morphological_kin, translation | حيث يتم القيام بعملية تشغيل على وظيفتين أو أكثر، ومن خلال ال |
| 6 | مُتَغِّير العملية | arabterm_arabterm_re | arabterm | morphological_kin, translation | كمية تصف عملية مؤثرة على النظام وصفاً دقيقاً. وتختلف عن مُتَ |
| 7 | عائد العملية | arabterm_arabterm_re | arabterm | morphological_kin, translation | الطاقة العائدة من [منشأة صناعية](http://www.arabterm.org/ind |
| 8 | حرارة العملية الصناع | arabterm_arabterm_re | arabterm | morphological_kin, translation | طاقة في صورة هواء أو بخار ساخن ، وهي الطاقة اللازمة لإجراء ع |
| 9 | مُواصفات العملية | arabterm_arabterm_wa | arabterm | morphological_kin, translation |  |
| 10 | علامة العملية | arabterm_arabterm_ma | arabterm | morphological_kin, translation |  |

### Strategy D — ColBERT Semantic Search
*Query: D1:'نظري' | D2:def | D3:combined (2003ms, 48 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | النظري | hawramani_35 | hawramani | contextual | (النظري) يُقَال أَمر نَظَرِي وَسَائِل بَحثه الْفِكر والتخيل  |
| 2 | النظري | Al_Waseet | ocr | contextual | أمر نَظَرِيٌّ: وسائلُ بحثِه الفكر والتخيُّل علوم نظَرِيَّة:  |
| 3 | نظري | hawramani_18 | hawramani | lemma_match | النظري: هو الذي يتوقف حصوله على نظر وكسب، كتصور النفس والعقل |
| 4 | آريي | hawramani_34 | hawramani | contextual | أارييآريّ [مفرد]:1 - جنس تجمعه بعض الخصائص اللُّغويَّة والجن |
| 5 | النظري | hawramani_23 | hawramani | contextual | النظري: يسْتَعْمل فِي معَان: أَحدهَا: علم بأحوال مَا لَا يكو |
| 6 | رأى | hawramani_6 | hawramani | contextual | [رأى] الرؤية بالعين تتعدى إلى مفعول واحد، وبمعنى العلم تتعدى |
| 7 | اقراباذين | hawramani_32 | hawramani | contextual | اقراباذين: أو قراباذين. وهي كلمة يونانية في رأي حاجي خليفة ( |
| 8 | رءي | hawramani_51 | hawramani | contextual | رءي  رَأَى  يَرَى (n. ac.  رَأْي رَأْيَة []   رُؤْيَة []   ر |
| 9 | الفن | hawramani_35 | hawramani | contextual | (الْفَنّ) هُوَ التطبيق العملي للنظريات العلمية بالوسائل الَّ |
| 10 | النظري | hawramani_24 | hawramani | contextual | النّظري:[في الانكليزية] Probable ،contingent ،speculative [  |

### Strategy E — Translation Cross-reference
*Query: EN: theoretical (5ms, 19 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | إجمالي نظري للطاقة ا | arabterm_arabterm_re | arabterm | morphological_kin, translation | إجمالي الطاقة الحرارية الأرضية المُتاحة، والتي يُمكن الاستفا |
| 2 | الإجمالي النظري للطا | arabterm_arabterm_re | arabterm | morphological_kin, translation | إجمالي الطاقة الحرارية الأرضية المُتاحة في طبقات المياه الجو |
| 3 | ‌مَجْرى مائيّ معياري | arabterm_arabterm_wa | arabterm | translation_bridge |  |
| 4 | مَجْرى مائيّ عاديّ | arabterm_arabterm_wa | arabterm | morphological_kin, translation |  |
| 5 | درجة التحلّل النظرية | arabterm_arabterm_wa | arabterm | morphological_kin, translation | درجة التحلّل التي يمكن تحقيقها نظرياً. وهي تُمثّل نسبة الموا |
| 6 | مُدة الاحتجاز النظري | arabterm_arabterm_wa | arabterm | morphological_kin, translation |  |
| 7 | ناتج الغاز الحيويّ ا | arabterm_arabterm_wa | arabterm | morphological_kin, translation |  |
| 8 | علم الاجتماع النظري | arabterm_arabterm_so | arabterm | morphological_kin, translation |  |
| 9 | تجريد نظري | arabterm_arabterm_ec | arabterm | morphological_kin, translation |  |
| 10 | اعتبارات نظرية | arabterm_arabterm_co | arabterm | morphological_kin, translation | غير عملية |

### Summary
- **Total unique entries:** 323
- **Unique contributions:** A=6, B=200, C=50, D=47, E=19
- **Sources:** arabterm: 273, hawramani: 45, ocr: 6
- **Time:** 2112ms

---

## 8. `awn4-02410992-a` — جامح, غير معتدل, مفرط

- **POS:** a
- **Lemmas (3):** جامح ، غير معتدل ، مفرط
- **Definition:** مفرط في السلوك
- **Examples:** غضب جامح

### Strategy A — Headword Match (SQL Tier 1)
*Query: جامح, غير معتدل, مفرط (7ms, 35 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | مُفرِط | arabterm_arabterm_in | arabterm | lemma_match, translation_bridg | صيغة تعبير غير مقبول من صفوة اللغة بسبب توسيع دلالته إلى فضا |
| 2 | مُفْرِط | arabterm_arabterm_la | arabterm | lemma_match, translation_bridg | صفة تعبير غير مقبول من صفوة اللغة بسبب توسيع دلالته إلى فضاء |
| 3 | مفرط | Mujmal_Lugha | ocr | lemma_match | غدير ملآن مؤخرون في قول الله |
| 4 | غير | hawramani_35 | hawramani | contextual | (غير) فلَان عَن بعيره حط عَنهُ رَحْله وَأصْلح من شَأْنه يُقَ |
| 5 | غير | hawramani_35 | hawramani | contextual | (غير) يكون اسْما بِمَعْنى إِلَّا تَقول جَاءَ الْقَوْم غير مُ |
| 6 | غير | hawramani_34 | hawramani | contextual | غيرغارَ على/ غارَ من يَغَار، غَرْ، غَيْرةً، فهو غيرانُ/ غيرا |
| 7 | غير | hawramani_17 | hawramani | contextual | غ ي ر : غَارَ الرَّجُلُ أَهْلَهُ غَيْرًا مِنْ بَابِ سَارَ وَ |
| 8 | غير | hawramani_12 | hawramani | contextual | (غ ي ر) : (الْغِيَارُ) عَلَامَة أَهْلِ الذِّمَّةِ كَالزُّنَّ |
| 9 | غير | hawramani_31 | hawramani | contextual | غيرغَيْرٌ يقال على أوجه:الأوّل: أن تكون للنّفي المجرّد من غي |
| 10 | غير | hawramani_9 | hawramani | contextual | غ ي ر غار على أهله من فلان، وأنا أغار عليها من ظلّها ومن شعا |

### Strategy B — Root Family (SQL Tier 2)
*Query: root=عدل,غير,فرط (110ms, 200 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | تغيّر المناخ البشري  | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 2 | تغير مناخي | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 3 | تغير بكري | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 4 | تغير سيتوبلازمي | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 5 | تغير اللون | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 6 | تغير غطاء الارض | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 7 | تغير استخدام الأراضي | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 8 | تغير إجتماعي | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 9 | تغير جسمي بكري | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 10 | تغيُّر الحياة؛ سِنّ  | arabterm_al_mawrid_a | arabterm | morphological_kin, translation | تغيُّر الحياة؛ سِنّ اليأس. |

### Strategy C — Definition Search (FTS5 BM25)
*Query: مفرط OR السلوك (7ms, 49 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | توسيخ مفرط | arabterm_arabterm_ci | arabterm | translation_bridge | توسيخ بيولوجي لنظام مائي من الكائنات الحية الكبيرة |
| 2 | سحب مفرط | arabterm_arabterm_ci | arabterm | morphological_kin, translation | ضخ المياه من حوض جوفي بمعدل يزيد عن طاقة تجددها الطبيعيةسحب  |
| 3 | استهلاك مفرط | arabterm_arabterm_cl | arabterm | morphological_kin, translation | فعل استهلاك شيء (متجدد) فوق قدرته على التجدد. |
| 4 | استهلاك مفرط للوقود  | arabterm_arabterm_re | arabterm | morphological_kin, translation |  |
| 5 | استخدام مفرط، تشغيل  | arabterm_arabterm_ec | arabterm | morphological_kin, translation | ينقسم الاستخدام إلى ناقص وتام ومفرط وينقسم كل منها إلى درجات |
| 6 | تراكم مفرط | arabterm_arabterm_ec | arabterm | morphological_kin, translation |  |
| 7 | تأثيل مفرط، رسملة مف | arabterm_arabterm_ec | arabterm | translation_bridge |  |
| 8 | نمو مفرط | arabterm_arabterm_ec | arabterm | morphological_kin, translation |  |
| 9 | توظيف مفرط | arabterm_arabterm_ec | arabterm | morphological_kin, translation |  |
| 10 | انتاج مفرط | arabterm_arabterm_ec | arabterm | morphological_kin, translation | عندما يتجاوز الانتاج حدود الطلب يكون هناك انتاج فائض أو مفرط |

### Strategy D — ColBERT Semantic Search
*Query: D1:'جامح; غير معتدل; مفرط' | D2:def | D3:combined (8638ms, 46 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | مرد | hawramani_32 | hawramani | contextual | مرد: مرد: يمرد. بلغ سن المراهقة (الكالا: بالأسبانية adolecer |
| 2 | الجامد | hawramani_24 | hawramani | contextual | الجامد:[في الانكليزية] Solid ،inflexible ،defective [ في الف |
| 3 | لفع | hawramani_32 | hawramani | contextual | لفع: ساط، جلد. جرَح. هجا، عاب. ضرب (بوشر). تلفع ب: إلاّ إنها |
| 4 | يلمع | hawramani_34 | hawramani | contextual | يلمعيَلْمَع [مفرد]: ج يَلامِعُ:1 - بَرْق خُلَّب لا يأتي بمطر |
| 5 | المقعد | hawramani_24 | hawramani | contextual | المقعد:[في الانكليزية] Infirm ،invalid [ في الفرنسية] Infirm |
| 6 | جحم | hawramani_34 | hawramani | contextual | جحمجَحيم [مفرد]:1 - مكان عذاب لا يُحتمل، أو مكانٌ شديد الحرّ |
| 7 | طمح | Al_Mujam_Al_Kabeer | ocr | contextual | شُخْبٌ طَمَحَ: يُضْرَبُ لِمَنْ تكونُ مِنهُ السَّقْطَةُ. فلان |
| 8 | الفجور | hawramani_24 | hawramani | contextual | الفجور:[في الانكليزية] Debauch ،profligacy [ في الفرنسية] De |
| 9 | غاموي | hawramani_48 | hawramani | contextual | غَامَّوِي من (غ م م) نسبة على غير قياس إلى الغام: الساتر للش |
| 10 | الجمود | hawramani_24 | hawramani | contextual | الجمود:[في الانكليزية] Rigidity ،immobility ،inertia ،catato |

### Strategy E — Translation Cross-reference
*Query: EN: intemperate (4ms, 2 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | ضارٌّ | arabterm_arabterm_ge | arabterm | morphological_kin, translation | يُحدث التحلل. |
| 2 | (1) مُفْرِط؛ مُسْرِف | arabterm_al_mawrid_a | arabterm | translation_bridge | (1) مُفْرِط؛ مُسْرِف (2) مُدْمِنٌ [معاقرةَ المُسْكِرات]. |

### Summary
- **Total unique entries:** 332
- **Unique contributions:** A=35, B=200, C=49, D=46, E=2
- **Sources:** arabterm: 259, hawramani: 67, ocr: 6
- **Time:** 8768ms

---

## 9. `awn4-00203457-r` — بذكاء

- **POS:** r
- **Lemmas (1):** بذكاء
- **Definition:** بطريقة ذكية
- **Examples:** تصرفت بذكاء في هذا الموقف الصعب

### Strategy A — Headword Match (SQL Tier 1)
*Query: بذكاء (0ms, 0 results)*

*No results*

### Strategy B — Root Family (SQL Tier 2)
*Query: (no root found) (0ms, 0 results)*

*No results*

### Strategy C — Definition Search (FTS5 BM25)
*Query: بطريقة OR ذكية (9ms, 50 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | الذَّكيّة | Al_Waseet | ocr | definition_support, morphologi | نار ذكية: شديدة اللهب |
| 2 | شبكة كهرباء ذكية | arabterm_arabterm_cl | arabterm | morphological_kin, translation | الشبكة الذكية هي اتصال في اتجاهين بين المستهلك وموزع إمدادات |
| 3 | شبكة ذكية | arabterm_arabterm_re | arabterm | morphological_kin, translation | تتميّز شبكة التيار الكهربائي الذكية عن نظيرتها التقليدية، با |
| 4 | شبكة ذكية | arabterm_arabterm_re | arabterm | morphological_kin, translation | شبكة كهربائية تجمع معلومات وتعمل بناءً عليها باستخدام تكنولو |
| 5 | شبكة ذكية | arabterm_arabterm_re | arabterm | morphological_kin, translation | تضم الشبكة الذكية الشبكات التواصلية والمتحكمة في مولدات الكه |
| 6 | إمدادات ذكية | arabterm_arabterm_re | arabterm | morphological_kin, translation | شبكة الكهرباء المبنية على أساس خلوي من إمدادات الطاقة اللامر |
| 7 | شبكة ذكية | arabterm_arabterm_re | arabterm | morphological_kin, translation | شبكة تيار كهربائي توصف بأنها 'ذكية' لأنها تشتمل على تقنيات ا |
| 8 | ريّ بطريقة الأخاديد  | arabterm_arabterm_wa | arabterm | translation_bridge |  |
| 9 | تقطير بطريقة انضغاط  | arabterm_arabterm_wa | arabterm | morphological_kin, translation |  |
| 10 | ريّ بطريقة الأخاديد  | arabterm_arabterm_wa | arabterm | translation_bridge |  |

### Strategy D — ColBERT Semantic Search
*Query: D1:'بذكاء' | D2:def | D3:combined (3025ms, 36 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | المذكية | Al_Mujam_Al_Kabeer | ocr | contextual | الذَّكِيَّةُ. |
| 2 | أسلوب الحكيم | hawramani_24 | hawramani | contextual | أسلوب الحكيم:[في الانكليزية] The method of the wise (pun)[ ف |
| 3 | ذكو | hawramani_8 | hawramani | contextual | (ذ ك و) ذكت النَّار ذُكُوّا وذكاً، واستَذْكَت كُله: اشتدّ لَ |
| 4 | ذكائي | hawramani_48 | hawramani | contextual | ذكَائي من (ذ ك و) نسبة إلى الذَكَاء. |
| 5 | شف | hawramani_8 | hawramani | contextual | الشين وَالْفَاء شَفَّه الْحبّ والحزن يَشُفّه شَفّا، وشُفُوفا |
| 6 | ذكت | hawramani_35 | hawramani | contextual | (ذكت)النَّار ذكوا وذكا وذكاء اشْتَدَّ لهبها واشتعلت وَيُقَال |
| 7 | ذكو | hawramani_32 | hawramani | contextual | ذكو: ذَكىً: جعله سريع الفهم، حاد الذهن، جعله ذكياً (لين غير  |
| 8 | ذكا | hawramani_1 | hawramani | contextual | ذكا: ذَكَتِ النارُ تَذْكو ذُكُوّاً وذكاً، مقصور، واسْتَذْكَت |
| 9 | بذك | hawramani_25 | hawramani | contextual | بذكتَبُوذَك يأْتي ذكره فِي الفَصْلِ الَّذِي بَعْدَه أَعني فص |
| 10 | حسن المطلب | hawramani_24 | hawramani | contextual | حسن المطلب:[في الانكليزية] Tact ،smartness [ في الفرنسية] Ta |

### Strategy E — Translation Cross-reference
*Query: EN: intelligently (2ms, 0 results)*

*No results*

### Summary
- **Total unique entries:** 85
- **Unique contributions:** A=0, B=0, C=49, D=35, E=0
- **Sources:** arabterm: 48, hawramani: 35, ocr: 3
- **Time:** 3036ms

---

## 10. `awn4-00038407-r` — بصدق, حقاً, في الحقيقة

- **POS:** r
- **Lemmas (3):** بصدق ، حقاً ، في الحقيقة
- **Definition:** في الواقع (تستخدم للتوكيد أو تعديل الجملة)
- **Examples:** في الحقيقة، عجل الانحلال الأخلاقي بسقوط الإمبراطورية الرومانية | حقاً، لم يكن يجب أن تفعل ذلك | كتاب مروع حقاً

### Strategy A — Headword Match (SQL Tier 1)
*Query: بصدق, حقاً, في الحقيقة (5ms, 17 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | حقا | hawramani_10 | hawramani | lemma_match | (حقا) - في حَديث عُمَر في النِّساء: "لا تَزْهَدْن في جَفَاءِ |
| 2 | حقا | hawramani_1 | hawramani | lemma_match | حقا: الحَقْوُ والحِقْوُ: الكَشْحُ، وقيل: مَعْقِدُ الإزار، وا |
| 3 | حَقَا | hawramani_11 | hawramani | lemma_match | (حَقَا)(هـ) فِيهِ «أَنَّهُ أعْطَى النِّساء اللَّاتِي غَسَّلْ |
| 4 | حقا | hawramani_6 | hawramani | lemma_match | [حقا] الحَقْوَةُ: وجع البطن. تقول منه حُقِيَ الرجل فهو مَحْق |
| 5 | حقا | hawramani_14 | hawramani | lemma_match | ح ق ا: (الْحَقْوُ) بِالْفَتْحِ الْإِزَارُ. وَالْحَقْوُ أَيْض |
| 6 | حَقَا | Al_Mujam_Al_Kabeer | ocr | lemma_match | فلانًا: أصابَ حَقْوَه الماءُ فلانًا: بَلَغَ حَقْوَه |
| 7 | الْحَقِيقَة | hawramani_35 | hawramani | morphological_kin | (الْحَقِيقَة) الشَّيْء الثَّابِت يَقِينا و (عِنْد اللغويين)  |
| 8 | الحَقِيقة | hawramani_27 | hawramani | morphological_kin | الحَقِيقة: هي اسم لما أريد به ما وُضع له، أو كل لفظ يبقى على |
| 9 | الحقيقة | hawramani_22 | hawramani | morphological_kin | الحقيقة: اسم لما أريد به ما وضع له فعيلة في حق الشيء إذا ثبت |
| 10 | الحَقيقَةُ | hawramani_20 | hawramani | morphological_kin | الحَقيقَةُ: مُشَاهدَة الربوبية. |

### Strategy B — Root Family (SQL Tier 2)
*Query: root=حقق,حقو (39ms, 200 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | حق الوصول | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 2 | حق الإشغال الأول | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 3 | الحق في بيئة نظيفة ص | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 4 | الحق في الغذاء | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 5 | الحق في المعلومات | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 6 | الحق في مستوى معيشة  | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 7 | الحق في المياه | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 8 | حق الاستخدام | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 9 | حق الإنتفاع | arabterm_agrovoc | arabterm | morphological_kin, translation |  |
| 10 | (1) حقّ أو امتياز فر | arabterm_al_mawrid_a | arabterm | morphological_kin, translation | (1) حقّ أو امتياز فرعيّ [كحقّ الطريق أو المرور] تابعٌ أو ملا |

### Strategy C — Definition Search (FTS5 BM25)
*Query: الواقع OR تستخدم OR للتوكيد OR تعديل OR الجملة (12ms, 50 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | الْقِصَّةُ | Al_Waseet | ocr | definition_support, morphologi | التى تُكْتَب الجملة من الكلام الحديث الأمر الخبر الشأنُ حكاي |
| 2 | تعديل الأخطاء | arabterm_arabterm_ci | arabterm | morphological_kin, translation |  |
| 3 | تعديل متزامن | arabterm_arabterm_ci | arabterm | morphological_kin, translation |  |
| 4 | تعديل المحطة | arabterm_arabterm_ci | arabterm | morphological_kin, translation |  |
| 5 | تعديل التربة | arabterm_arabterm_cl | arabterm | morphological_kin, translation | 1. تغيير في خصائص التربة، وبالتالي تغيير للتربة، من خلال إضا |
| 6 | تكنولوجيا حيوية | arabterm_arabterm_cl | arabterm | definition_support, translatio | أتطبيقات تكنولوجية تستخدم الموارد البيولوجية أو الكائنات الح |
| 7 | عنصر تعديل | arabterm_arabterm_tr | arabterm | morphological_kin, translation |  |
| 8 | معامل الحمل | arabterm_arabterm_re | arabterm | definition_support, morphologi | نسبة من متوسط ​​الحمل الواقع على نظامٍ ما، تستخدم في تقدير س |
| 9 | تعديل السلوك | arabterm_arabterm_ed | arabterm | morphological_kin, translation |  |
| 10 | تعديل الميزانية | arabterm_arabterm_co | arabterm | morphological_kin, translation |  |

### Strategy D — ColBERT Semantic Search
*Query: D1:'بصدق; حقاً; في الحقيقة' | D2:def | D3:combined (9869ms, 48 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | حق | Al_Waseet | ocr | contextual | الأمر - حقاً, وحقة, وحقوقاً: صح وثبت وصدق. وفي التنزيل العزي |
| 2 | الحق | hawramani_24 | hawramani | contextual | الحقّ:[في الانكليزية] Truth ،reality ،right ،certainty [ في  |
| 3 | صح | hawramani_32 | hawramani | contextual | صحّ: صحَّ: كان صحيحاً، حقاً، ويقال: إن صحت الأحلام: إن كانت  |
| 4 | صدق | hawramani_51 | hawramani | contextual | صدق  صَدَقَ(n. ac. صَدْق  صِدْق  تَصْدَاْق  مَصْدُوْقَة ) a. |
| 5 | الصواب | hawramani_24 | hawramani | contextual | الصّواب:[في الانكليزية] Just ،fair ،true ،righteous [ في الف |
| 6 | الصدق | hawramani_23 | hawramani | contextual | الصدْق: وَالتَّحْقِيق الْحقيق والتدقيق الأنيق مَا ذكره السَّ |
| 7 | حق | hawramani_18 | hawramani | contextual | الحق: في اللغة هو الثابت الذي لا يسوغ إنكاره، وفي اصطلاح أهل |
| 8 | الصدق | hawramani_24 | hawramani | contextual | الصّدق:[في الانكليزية] Truth ،correctness [ في الفرنسية] Ver |
| 9 | صدقه | Al_Waseet | ocr | contextual | وصدَّق به: تصديقاً, وتَصَدَّاقاً: اعترف بصدق قوله حقَّقه صدّ |
| 10 | حقق | hawramani_21 | hawramani | contextual | [حقق] نه فيه: "الحق" تعالى، الموجود حقيقة، المتحقق وجوده وإل |

### Strategy E — Translation Cross-reference
*Query: EN: in truth, really, truly (9ms, 4 results)*

| # | Headword | Dictionary | Source | Evidence | Definition (excerpt) |
|---|----------|------------|--------|----------|---------------------|
| 1 | في الحقّ؛ في الواقع. | arabterm_al_mawrid_a | arabterm | definition_support, translatio | في الحقّ؛ في الواقع. |
| 2 | (1) «أ» في الواقع. « | arabterm_al_mawrid_a | arabterm | definition_support, translatio | (1) «أ» في الواقع. «ب» من غير ريب (2) حقًا. |
| 3 | (1) بإخلاص truly you | arabterm_al_mawrid_a | arabterm | morphological_kin, translation | (1) بإخلاص truly yours (2) بِصِدق (3) برِقّة (4) حقًّا؛ في ا |
| 4 | (1) لك بإخلاص: صيغة  | arabterm_al_mawrid_a | arabterm | morphological_kin, translation | (1) لك بإخلاص: صيغة تُخْتَم بها الرِّسالة (2) نفسي؛ ذاتي I c |

### Summary
- **Total unique entries:** 316
- **Unique contributions:** A=15, B=200, C=49, D=45, E=4
- **Sources:** arabterm: 233, hawramani: 57, ocr: 29
- **Time:** 9936ms

---

## Global Summary

- **Avg entries per synset:** 293
- **Strategy A avg unique:** 20.0
- **Strategy B avg unique:** 159.9
- **Strategy C avg unique:** 49.1
- **Strategy D avg unique:** 45.2
- **Strategy E avg unique:** 16.1
