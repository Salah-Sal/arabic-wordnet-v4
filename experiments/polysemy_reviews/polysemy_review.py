#!/usr/bin/env python3
"""Send polysemy evidence packages to Gemini for disambiguation review.

Stage 4B of the AWN4 review pipeline. For each polysemy group (synsets sharing
identical lemma sets), asks Gemini to propose disambiguating Arabic synonyms.

Requires: google-genai, python-dotenv (optional)
API key:  GEMINI_API_KEY environment variable

Usage:
    python experiments/polysemy_reviews/polysemy_review.py --dry-run --top 3
    python experiments/polysemy_reviews/polysemy_review.py --top 10
    python experiments/polysemy_reviews/polysemy_review.py --min-count 5
    python experiments/polysemy_reviews/polysemy_review.py  # all groups, with resume
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

# Lazy imports — google-genai only needed for actual API calls, not --dry-run
genai = None
genai_errors = None
types = None


def _ensure_genai():
    """Import google-genai on first use (allows --dry-run without the SDK)."""
    global genai, genai_errors, types
    if genai is not None:
        return
    try:
        from google import genai as _genai
        from google.genai import errors as _errors
        from google.genai import types as _types
        genai = _genai
        genai_errors = _errors
        types = _types
    except ImportError:
        print("ERROR: google-genai SDK not installed.")
        print("Install with: pip install google-genai")
        sys.exit(1)

# ─── Paths ────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
PACKAGES_FILE = str(SCRIPT_DIR / "polysemy_packages.json")
OUTPUT_DIR = SCRIPT_DIR / "reviews"
SUMMARY_FILE = str(SCRIPT_DIR / "review_summary.json")

DEFAULT_MODEL = "gemini-3-flash-preview"
MAX_RETRIES = 5
RETRY_BASE_DELAY = 2.0

# ─── Pricing per 1M tokens (from api_extract.py) ─────────────────────────────

MODEL_PRICING = {
    "gemini-3.1-pro": (2.00, 12.00),
    "gemini-3-pro": (2.00, 12.00),
    "gemini-3-flash": (0.0, 0.0),
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.0-flash-lite": (0.075, 0.30),
    "gemini-2.0-flash": (0.10, 0.40),
}

# ─── System Prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """أنت لغوي عربي متخصص في المعجمية الحاسوبية (Computational Lexicography). مهمتك الوحيدة: **اقتراح لمات عربية إضافية** تميّز كل مجموعة ترادفية عن بقية المجموعات التي تشترك معها في نفس اللمة.

## السياق

الشبكة العربية للكلمات (AWN4) تحتوي على مجموعات ترادفية (Synsets) تم إنشاؤها آلياً. المشكلة: مجموعات ترادفية متعددة تحمل نفس اللمة العربية دون أي تمييز. مثلاً: 18 مجموعة ترادفية كلها تحمل اللمة "عقد" فقط — ولا يمكن التفريق بينها من اللمات وحدها.

ستُقدَّم لك مجموعة من المجموعات الترادفية المتشابهة مع:
- تعريف كل مجموعة ترادفية بالعربية
- أمثلة (إن وجدت)
- المعنى الأعم (Hypernym) لكل مجموعة
- بيانات معجمية من المعجم الوسيط والمعجم الكبير (إن وجدت)

## المطلوب

لكل مجموعة ترادفية في المجموعة المقدمة:

1. **اقترح 1-2 لمة عربية إضافية** (مرادفات أو أوصاف مميزة) تميّز هذا المفهوم عن بقية المجموعات. اللمات المقترحة يجب أن تكون:
   - **مشكّلة بالكامل** (بالحركات): مثلاً "عَقْدٌ قَانُونِيّ" لا "عقد قانوني"
   - **لفظاً مختصاً** يعرفه أهل اللغة، لا وصفاً عاماً مركباً. فضّل اللفظ المفرد الأصيل على العبارة التوضيحية
   - **مدعومة بالبيانات المعجمية** المرفقة إن أمكن

2. **اذكر المبرر** بإيجاز (جملة واحدة): لماذا هذه اللمة تميّز هذا المفهوم؟

3. **حدد مستوى الثقة:**
   - `high`: اللمة موجودة في البيانات المعجمية المرفقة وتطابق المعنى
   - `medium`: اللمة صحيحة لغوياً لكن لم ترد في البيانات المعجمية المرفقة
   - `low`: اقتراح تقريبي لعدم توفر بيانات معجمية كافية

4. **أضف أعلاماً** عند الحاجة:
   - `CULTURALLY_IRRELEVANT`: المفهوم غريب عن الثقافة العربية (مثل: مصطلحات لعبة البريدج)
   - `DECADE_CLUSTER`: مجموعة فرعية من عقود زمنية محددة — اقترح قالباً واحداً
   - `PROPER_NOUN_SKIP`: اسم علم لا يحتاج تمييزاً لغوياً
   - `IDENTICAL_SENSES`: مجموعات ترادفية متطابقة فعلياً يجب دمجها

5. **اكتب ملاحظة عامة** عن المجموعة ككل (جملة أو جملتين).

## تنبيهات

- **لا تعد صياغة التعريفات** — مهمتك اقتراح لمات فقط.
- **لا تحذف اللمات الموجودة** — أضف لمات جديدة فقط.
- فضّل **اللفظ المختص** على اللفظ العام: لا تقل "عقد + صفة"، بل ابحث عن الكلمة العربية الأصيلة التي تدل على هذا المعنى بعينه.
- إذا كانت المجموعات الترادفية كلها تنتمي لنفس الفئة (مثل: عقود زمنية)، اقترح قالباً واحداً وطبّقه على الجميع.

## صيغة الإخراج (JSON)

أجب بصيغة JSON التالية حصراً:
```json
{
  "reviews": [
    {
      "synset_id": "awn4-XXXXXXXX-X",
      "proposed_lemmas": ["لَمَة١", "لَمَة٢"],
      "rationale": "مبرر الاقتراح",
      "confidence": "high|medium|low",
      "flags": []
    }
  ],
  "group_notes": "ملاحظة عامة عن المجموعة"
}
```
"""


# ─── Prompt Builder ───────────────────────────────────────────────────────────

POS_LABELS = {'n': 'اسم', 'v': 'فعل', 'a': 'صفة', 'r': 'ظرف'}


def build_user_prompt(package: dict) -> str:
    """Build the per-package user prompt from evidence package data."""
    parts = []

    lemma_str = '، '.join(package['lemma_set'])
    pos_label = POS_LABELS.get(package['pos'], package['pos'])
    parts.append(f"## المجموعة: {lemma_str} — {pos_label}")
    parts.append(f"عدد المجموعات الترادفية: {package['count']}")
    parts.append("")

    # Synsets
    for i, s in enumerate(package['synsets'], 1):
        parts.append(f"### المجموعة الترادفية {i}: {s['id']}")

        defs = s.get('definitions', [])
        if defs:
            parts.append(f"- التعريف: {defs[0]}")
        else:
            parts.append("- التعريف: (غير متوفر)")

        examples = s.get('examples', [])
        if examples:
            ex_text = '؛ '.join(str(e) for e in examples[:2])
            parts.append(f"- الأمثلة: {ex_text}")

        lemmas_raw = s.get('lemmas_raw', [])
        if lemmas_raw:
            parts.append(f"- اللمات الحالية: {', '.join(lemmas_raw)}")

        hyp = s.get('hypernym')
        if hyp:
            hyp_lemmas = ', '.join(hyp.get('lemmas_raw', []))
            hyp_def = hyp.get('definition', '')
            parts.append(f"- المعنى الأعم: {hyp_def} ({hyp_lemmas})")

        parts.append("")

    # Dictionary evidence
    dict_ev = package.get('dictionary_evidence', {})
    if dict_ev:
        parts.append("### البيانات المعجمية")
        parts.append("")
        for lemma, entries in dict_ev.items():
            parts.append(f"#### {lemma}")
            for e in entries:
                header = f"{e['source']}: {e['headword']} ({e['pos']})"
                if e.get('root'):
                    header += f" جذر={e['root']}"
                parts.append(header)
                for d in e.get('definitions', []):
                    if isinstance(d, str):
                        parts.append(f"  - {d}")
                    elif isinstance(d, dict):
                        parts.append(f"  - {d.get('text', str(d))}")
                parts.append("")
    else:
        parts.append("### البيانات المعجمية")
        parts.append("لا توجد بيانات معجمية متاحة لهذه المجموعة.")
        parts.append("")

    return '\n'.join(parts)


# ─── Rate Limiter (from api_extract.py) ──────────────────────────────────────

class RateLimiter:
    def __init__(self, rpm: int):
        self.rpm = rpm
        self.timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            while self.timestamps and now - self.timestamps[0] > 60:
                self.timestamps.popleft()
            if len(self.timestamps) >= self.rpm:
                sleep_time = 60 - (now - self.timestamps[0]) + 0.1
                await asyncio.sleep(sleep_time)
                now = time.monotonic()
                while self.timestamps and now - self.timestamps[0] > 60:
                    self.timestamps.popleft()
            self.timestamps.append(time.monotonic())


# ─── Cost Tracker (from api_extract.py) ──────────────────────────────────────

class CostTracker:
    def __init__(self, model: str):
        self.input_tokens = 0
        self.output_tokens = 0
        self._lock = asyncio.Lock()
        self.input_rate = 0.0
        self.output_rate = 0.0
        for prefix, (inp, out) in MODEL_PRICING.items():
            if model.startswith(prefix):
                self.input_rate = inp
                self.output_rate = out
                break

    async def record(self, usage_metadata):
        if not usage_metadata:
            return
        async with self._lock:
            self.input_tokens += getattr(usage_metadata, "prompt_token_count", 0) or 0
            self.output_tokens += getattr(usage_metadata, "candidates_token_count", 0) or 0

    @property
    def cost_usd(self) -> float:
        return (
            self.input_tokens * self.input_rate / 1_000_000
            + self.output_tokens * self.output_rate / 1_000_000
        )

    def summary(self) -> str:
        total = self.input_tokens + self.output_tokens
        return (
            f"Tokens: {self.input_tokens:,} in + {self.output_tokens:,} out "
            f"= {total:,} total  |  Cost: ${self.cost_usd:.4f}"
        )


# ─── Retry Helper (from api_extract.py) ──────────────────────────────────────

def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, genai_errors.ServerError):
        return True
    ename = type(exc).__name__
    return any(tok in ename for tok in (
        "Disconnect", "Timeout", "ConnectionError",
        "ConnectionReset", "BrokenPipe",
    ))


# ─── Core Review Function ────────────────────────────────────────────────────

async def review_package(
    client: genai.Client,
    package: dict,
    system_prompt: str,
    model: str,
    output_dir: Path,
    semaphore: asyncio.Semaphore,
    rate_limiter: RateLimiter,
    cost: CostTracker,
) -> tuple[int, bool, str]:
    """Review one polysemy package. Returns (group_id, success, message)."""
    group_id = package['group_id']
    output_file = output_dir / f"group_{group_id:04d}.json"

    # Resume: skip if already done
    if output_file.exists():
        return group_id, True, "skipped (already exists)"

    user_prompt = build_user_prompt(package)

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with semaphore:
                await rate_limiter.acquire()
                response = await client.aio.models.generate_content(
                    model=model,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        response_mime_type="application/json",
                        temperature=0.2,
                    ),
                )
        except Exception as e:
            last_error = e
            if _is_retryable(e) and attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                await asyncio.sleep(delay)
                continue
            etype = type(e).__name__
            suffix = f" (after {attempt} attempts)" if attempt > 1 else ""
            return group_id, False, f"api_error: {etype}: {e}{suffix}"

        # Track tokens
        await cost.record(response.usage_metadata)

        if not response.text:
            if attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                await asyncio.sleep(delay)
                continue
            return group_id, False, f"empty_response (after {attempt} attempts)"

        # Parse response
        try:
            result = json.loads(response.text)
        except json.JSONDecodeError:
            # Save raw text for debugging
            raw_file = output_dir / f"group_{group_id:04d}_raw.txt"
            raw_file.write_text(response.text, encoding='utf-8')
            return group_id, False, f"json_parse_error (raw saved to {raw_file.name})"

        # Enrich result with metadata
        usage = response.usage_metadata
        result_full = {
            'group_id': group_id,
            'lemma_set': package['lemma_set'],
            'pos': package['pos'],
            'count': package['count'],
            'model': model,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'input_tokens': getattr(usage, 'prompt_token_count', 0) or 0,
            'output_tokens': getattr(usage, 'candidates_token_count', 0) or 0,
            **result,
        }

        output_file.write_text(
            json.dumps(result_full, ensure_ascii=False, indent=1),
            encoding='utf-8',
        )
        return group_id, True, "ok"

    return group_id, False, f"exhausted_retries: {last_error}"


# ─── Aggregate Summary ───────────────────────────────────────────────────────

def aggregate_results(output_dir: Path, model: str, elapsed: float) -> dict:
    """Read all group_*.json files and produce aggregate stats."""
    completed = 0
    total_input = 0
    total_output = 0
    confidence_dist = {'high': 0, 'medium': 0, 'low': 0}
    flags_dist = {}
    total_proposed = 0
    total_synsets = 0

    for f in sorted(output_dir.glob("group_*.json")):
        if f.name.endswith("_raw.txt"):
            continue
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError):
            continue

        completed += 1
        total_input += data.get('input_tokens', 0)
        total_output += data.get('output_tokens', 0)

        for review in data.get('reviews', []):
            total_synsets += 1
            total_proposed += len(review.get('proposed_lemmas', []))

            conf = review.get('confidence', 'unknown')
            confidence_dist[conf] = confidence_dist.get(conf, 0) + 1

            for flag in review.get('flags', []):
                flags_dist[flag] = flags_dist.get(flag, 0) + 1

    cost_usd = 0.0
    for prefix, (inp, out) in MODEL_PRICING.items():
        if model.startswith(prefix):
            cost_usd = total_input * inp / 1_000_000 + total_output * out / 1_000_000
            break

    return {
        'metadata': {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'model': model,
            'completed': completed,
            'elapsed_minutes': round(elapsed / 60, 1),
            'total_input_tokens': total_input,
            'total_output_tokens': total_output,
            'cost_usd': round(cost_usd, 4),
        },
        'confidence_distribution': confidence_dist,
        'flags_distribution': flags_dist,
        'total_synsets_reviewed': total_synsets,
        'total_proposed_lemmas': total_proposed,
        'avg_proposed_lemmas_per_synset': round(
            total_proposed / max(total_synsets, 1), 2
        ),
    }


# ─── Main ────────────────────────────────────────────────────────────────────

async def run(args):
    start = time.time()

    # Load .env if available — search multiple locations
    import os
    try:
        from dotenv import load_dotenv
        # Load project-local .env last with override=True so it wins
        PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent
        for env_path in [
            PROJECT_ROOT / "arabic-dictionaries" / ".env",
            PROJECT_ROOT / "amr-agent" / ".env",
        ]:
            if env_path.exists():
                load_dotenv(env_path)
        # Project-local .env takes priority (arabic-wordnet-v4/.env)
        local_env = SCRIPT_DIR.parent.parent / ".env"
        if local_env.exists():
            load_dotenv(local_env, override=True)
        # Bridge GEM_API_KEY → GEMINI_API_KEY (always override — project-local wins)
        if "GEM_API_KEY" in os.environ:
            os.environ["GEMINI_API_KEY"] = os.environ["GEM_API_KEY"]
    except ImportError:
        pass

    # Phase 1: Load packages
    print("Phase 1: Loading polysemy packages...")
    data = json.load(open(args.packages, encoding='utf-8'))
    packages = data['packages']
    total_before = len(packages)

    if args.min_count is not None:
        packages = [p for p in packages if p['count'] >= args.min_count]
    if args.top is not None:
        packages = packages[:args.top]

    print(f"  Total in file: {total_before}")
    if args.min_count or args.top:
        print(f"  After filters (top={args.top}, min_count={args.min_count}): {len(packages)}")

    # Check for already-completed
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    done = {
        int(f.stem.split('_')[1])
        for f in output_dir.glob("group_*.json")
        if not f.name.endswith("_raw.txt")
    }
    remaining = [p for p in packages if p['group_id'] not in done]
    skipped = len(packages) - len(remaining)

    print(f"  Already completed: {skipped}")
    print(f"  Remaining: {len(remaining)}")
    total_synsets = sum(p['count'] for p in remaining)
    print(f"  Total synsets to review: {total_synsets}")

    if not remaining:
        print("\nAll groups already reviewed!")
        # Still aggregate
        summary = aggregate_results(output_dir, args.model, time.time() - start)
        summary_path = Path(args.summary)
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8'
        )
        print(f"Summary written to: {summary_path}")
        return

    # Phase 2: Build prompts (dry run mode)
    if args.dry_run:
        print(f"\n{'='*60}")
        print("DRY RUN — showing prompts, no API calls")
        print(f"{'='*60}")
        for p in remaining[:args.top or 3]:
            user_prompt = build_user_prompt(p)
            print(f"\n--- Group {p['group_id']}: {p['lemma_set']} ({p['count']} synsets) ---")
            print(f"Prompt length: {len(user_prompt)} chars")
            print(user_prompt[:2000])
            if len(user_prompt) > 2000:
                print(f"  ... ({len(user_prompt) - 2000} chars truncated)")
        print(f"\nSystem prompt length: {len(SYSTEM_PROMPT)} chars")
        return

    # Phase 3: Async API calls
    _ensure_genai()
    print(f"\nPhase 3: Sending to {args.model} (concurrency={args.concurrency}, rpm={args.rpm})...")

    client = genai.Client()
    semaphore = asyncio.Semaphore(args.concurrency)
    rate_limiter = RateLimiter(args.rpm)
    cost = CostTracker(args.model)

    tasks = [
        review_package(
            client, p, SYSTEM_PROMPT, args.model, output_dir,
            semaphore, rate_limiter, cost,
        )
        for p in remaining
    ]

    # Progress tracking
    completed = 0
    failed = 0
    results = []

    try:
        results = await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        print("\n\nInterrupted! Partial results saved.")

    for gid, success, msg in results:
        if success:
            if msg != "skipped (already exists)":
                completed += 1
        else:
            failed += 1

    elapsed = time.time() - start

    # Print results
    print(f"\n{'='*60}")
    print("POLYSEMY REVIEW — RESULTS")
    print(f"{'='*60}")
    print(f"Completed: {completed + skipped} / {len(packages)}")
    print(f"  New:     {completed}")
    print(f"  Skipped: {skipped}")
    print(f"Failed:    {failed}")
    print(f"Elapsed:   {elapsed/60:.1f} min")
    print(f"{cost.summary()}")

    if failed:
        print(f"\nFailed groups:")
        for gid, success, msg in results:
            if not success:
                print(f"  group_{gid:04d}: {msg}")

    # Phase 4: Aggregate
    print(f"\nPhase 4: Aggregating results...")
    summary = aggregate_results(output_dir, args.model, elapsed)
    summary_path = Path(args.summary)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    print(f"Summary written to: {summary_path}")

    s = summary
    print(f"\n  Synsets reviewed:     {s['total_synsets_reviewed']}")
    print(f"  Proposed lemmas:     {s['total_proposed_lemmas']}")
    print(f"  Avg per synset:      {s['avg_proposed_lemmas_per_synset']}")
    print(f"  Confidence: {s['confidence_distribution']}")
    if s['flags_distribution']:
        print(f"  Flags: {s['flags_distribution']}")


def main():
    parser = argparse.ArgumentParser(
        description="Send polysemy evidence packages to Gemini for disambiguation review."
    )
    parser.add_argument('--packages', default=PACKAGES_FILE,
                        help='Path to polysemy_packages.json')
    parser.add_argument('--output-dir', default=str(OUTPUT_DIR),
                        help='Directory for per-group review JSON files')
    parser.add_argument('--summary', default=SUMMARY_FILE,
                        help='Path for aggregate summary JSON')
    parser.add_argument('--model', default=DEFAULT_MODEL,
                        help=f'Gemini model name (default: {DEFAULT_MODEL})')
    parser.add_argument('--top', type=int, default=None,
                        help='Only process top N groups (by synset count)')
    parser.add_argument('--min-count', type=int, default=None,
                        help='Only process groups with >= N synsets')
    parser.add_argument('--concurrency', type=int, default=10,
                        help='Max concurrent API requests (default: 10)')
    parser.add_argument('--rpm', type=int, default=300,
                        help='Rate limit in requests per minute (default: 300)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print prompts without making API calls')
    args = parser.parse_args()

    asyncio.run(run(args))


if __name__ == '__main__':
    main()
