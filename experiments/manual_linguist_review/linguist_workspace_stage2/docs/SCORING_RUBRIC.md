# معايير التقييم — Scoring (v2)

The v2 schema collapses the five scoring dimensions into a single `verdict` field.

The verdict criteria and flag taxonomy are now embedded directly in the prompt
template. See [templates/linguist_prompt.md](../templates/linguist_prompt.md),
section 6 (الإثراء والتعريف).

## Verdict

| القيمة | المعيار |
|--------|---------|
| `excellent` | كل اللمّات مؤيَّدة بشواهد قوية، التعريف بليغ، لا أعلام |
| `good` | اللمّات مؤيَّدة، بعض الملاحظات الطفيفة |
| `acceptable` | المعنى صحيح لكن هناك مشكلات قابلة للإصلاح |
| `poor` | لمّات غير مؤيَّدة أو أعلام حرجة متعددة |

## Flags

See [REVIEW_SCHEMA.md](REVIEW_SCHEMA.md) for the complete flag reference.
