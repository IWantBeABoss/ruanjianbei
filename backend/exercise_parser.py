import json
import re


#练习题的解析器(有JSON和Markdown的)

def _extract_answer_block(text: str) -> tuple[str, str]:
    """Split text into question body and answer/explanation block."""
    patterns = [
        r"\n> 💡\s*答案与解析[：:]?",
        r"\n>\s*💡\s*答案与解析[：:]?",
        r"\n> 答案与解析[：:]?",
        r"\n>\s*答案[：:]",
        r"\n答案[：:]",
        r"\n> 正确答案[：:]?",
        r"\n正确答案[：:]?",
        r"\n> 解析[：:]",
        r"\n解析[：:]",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            question_part = text[:m.start()].strip()
            answer_part = text[m.start():].strip()
            return question_part, answer_part
    return text.strip(), ""


_HEADER_PATTERNS = re.compile(r"^(选择|填空|判断).*?[（(].*?题.*?[）)]")


def _is_header(text: str) -> bool:
    return bool(_HEADER_PATTERNS.match(text.strip()))


# ── 对练习题的各个部分进行提取(也就是将:题目、答案和解析分开) ──────────────────────────────────────────────

def _split_numbered_blocks(text: str) -> list[str]:
    """Split text by numbered item markers. Filters out header lines first."""
    lines = text.split("\n")
    filtered = [l for l in lines if not _is_header(l.strip())]
    text = "\n".join(filtered)
    blocks = re.split(r"\n(?:\*\*)?\s*\d+[\.\、\)）]\s*(?:\*\*)?", "\n" + text)
    return [b.strip() for b in blocks if b.strip() and not _is_header(b)]


def _extract_answer_letter(ans_block: str) -> str:
    """Extract answer letter (A-D) from an answer/explanation block."""
    m = re.search(r"答案[：:]\s*([A-D])", ans_block)
    return m.group(1) if m else ""


# ── 选择的组件(claude写的，测试了没问题) ─────────────────────────

def _parse_choice_questions(text: str) -> list[dict]:
    """Parse multiple choice questions by locating option groups (A/B/C/D)
    as anchors, then working outward to find the question and answer.

    Improved: supports multi-line question text (continues backward from the
    option group until a blank line or another numbered marker). Answer
    extraction searches the explanation block for 答案：X as well as
    standalone patterns like 正确答案.*[A-D]."""
    questions: list[dict] = []
    lines = [l for l in text.split("\n") if not _is_header(l.strip())]

    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if not re.match(r"^A[\.\、\)）]\s", s):
            i += 1
            continue

        # Found start of an option group — collect all consecutive options
        opt_start = i
        options: list[str] = []
        j = i
        while j < len(lines):
            om = re.match(r"^([A-D])[\.\、\)）]\s*(.+)", lines[j].strip())
            if om:
                options.append(f"{om.group(1)}. {om.group(2).strip()}")
                j += 1
            else:
                break

        # Look backward for question text — collect consecutive non-empty
        # lines up to the numbered marker (or blank line as boundary).
        question_lines: list[str] = []
        found_number = False
        for k in range(opt_start - 1, -1, -1):
            prev = lines[k].strip()
            if not prev:
                if found_number:
                    break  # blank after finding the numbered marker
                continue
            qm = re.match(r"^(?:\*\*)?\s*\d+[\.\、\)）]\s*(?:\*\*)?\s*(.*)", prev)
            if qm:
                question_lines.insert(0, qm.group(1).strip())
                found_number = True
                continue
            if found_number:
                # Non-blank, non-numbered line after finding number — could be
                # continuation of the question. Collect it.
                question_lines.insert(0, prev)
            # If we haven't found the number yet and this isn't it, it's likely
            # a stray line — stop.
            if not found_number and not re.match(r"^(?:\*\*)?\s*\d+[\.\、\)）]", prev):
                break

        question_text = "\n".join(question_lines) if question_lines else ""

        # Fallback: if we didn't find a numbered marker, grab the last
        # non-empty line before the option group
        if not question_text:
            for k in range(opt_start - 1, -1, -1):
                prev = lines[k].strip()
                if prev and not re.match(r"^[A-D][\.\、\)）]\s", prev):
                    question_text = prev
                    break

        # Look forward for answer / explanation (stop at next option group)
        explanation_lines: list[str] = []
        answer = ""
        for k in range(j, len(lines)):
            ns = lines[k].strip()
            if not ns:
                if explanation_lines:
                    explanation_lines.append("")
                continue
            # Stop at next option group or section header
            if re.match(r"^A[\.\、\)）]\s", ns) or _is_header(ns):
                break
            # Try multiple answer patterns
            for pat in [
                r"答案[：:]\s*([A-D])",
                r"正确答案[：:是为]*\s*([A-D])",
                r"[（(]\s*([A-D])\s*[）)]",
            ]:
                am = re.search(pat, ns)
                if am:
                    answer = am.group(1)
                    break
            explanation_lines.append(ns)

        explanation = "\n".join(explanation_lines).strip()

        if question_text and options:
            questions.append({
                "question_type": "choice",
                "question": question_text,
                "options": options,
                "answer": answer,
                "explanation": explanation,
            })

        i = j  # skip past processed option group
    return questions


# ── 填空题解析器(其实就是占位符) ─────────────────────────────────────────────

def _parse_fill_blank_questions(text: str) -> list[dict]:
    """Parse fill-in-the-blank questions."""
    questions: list[dict] = []
    for block in _split_numbered_blocks(text):
        body, ans = _extract_answer_block(block)
        if "___" in body:
            questions.append({
                "question_type": "fill_blank",
                "question": body.strip(),
                "options": [],
                "answer": "",
                "explanation": ans,
            })
    return questions


# ── 判断题解析器(进行判断题校验的) ─────────────────────────────────────────────

def _parse_true_false_questions(text: str) -> list[dict]:
    """Parse true/false questions from LLM output.

    Question body is identified by numbered blocks.
    The answer/explanation block is searched for indicators like
    正确/错误/对/错/True/False/✓/✗.
    """
    questions: list[dict] = []
    for block in _split_numbered_blocks(text):
        body, ans = _extract_answer_block(block)
        clean = re.sub(r"\s+", "", body)
        # True/false questions tend to be short declarative statements
        # with ( ) or （ ） placeholder; also allow bare statements
        if len(clean) >= 6:
            # Extract answer from explanation block
            answer = ""
            ans_lower = ans.lower()
            for kw in ["正确", "错误", "对", "错", "true", "false", "✓", "✗", "√", "×"]:
                if kw in ans_lower or kw in ans:
                    answer = kw
                    break
            questions.append({
                "question_type": "true_false",
                "question": body.strip(),
                "options": [],
                "answer": answer,
                "explanation": ans,
            })
    return questions


SUBSECTION_PATTERNS = [
    (r"选择", "choice", _parse_choice_questions),
    (r"填空", "fill_blank", _parse_fill_blank_questions),
    (r"判断", "true_false", _parse_true_false_questions),
]


# ── 主入口点 ─────────────────────────────────────────────

def parse_exercises_from_content(content: str, subject: str = "") -> list[dict]:
    """Parse multi-agent exercise output into a list of structured question dicts."""
    # 1. Locate the exercise section
    section_start = -1
    for marker in [
        "## ✏️", "## 三、", "配套练习题",
        "## 选择", "## 填空", "## 判断",
        "### 选择", "### 填空", "### 判断",
    ]:
        idx = content.find(marker)
        if idx != -1 and (section_start == -1 or idx < section_start):
            section_start = idx

    if section_start == -1:
        return []

    exercise_section = content[section_start:]

    # 2. Find where the exercise section ends (next major ## heading)
    end_match = re.search(
        r"\n## (?!✏️|三|[一二三四五]、|选择|填空|判断|代码)",
        exercise_section,
    )
    if end_match:
        exercise_section = exercise_section[:end_match.start()]

    # 3. Strip the main section header line (## ✏️ 三、配套练习题)
    first_newline = exercise_section.find("\n")
    if first_newline != -1:
        exercise_section = exercise_section[first_newline:].strip()

    # 4. Split into subsections by ## headers
    subsections = re.split(r"\n## ", exercise_section)
    all_questions: list[dict] = []

    for sub in subsections:
        sub = sub.strip()
        if not sub:
            continue
        for pattern, qtype, parser_func in SUBSECTION_PATTERNS:
            if re.search(pattern, sub):
                parsed = parser_func(sub)
                for q in parsed:
                    q["question_type"] = q.get("question_type", qtype)
                all_questions.extend(parsed)
                break

    # 5. Deduplicate by first 60 chars of question text
    seen: set[str] = set()
    unique: list[dict] = []
    for q in all_questions:
        key = q["question"][:60]
        if key not in seen:
            seen.add(key)
            unique.append(q)

    return unique


# ── JSON Parser 是专门用于解析 Quiz Agent 结构化输出的解析器，防止格式出问题 ────────────────

TYPE_MAP = {
    "choice": "choice",
    "fill": "fill_blank",
    "true_false": "true_false",
}


def parse_exercises_from_json(content: str, subject: str = "") -> list[dict]:
    """Parse exercise questions from Quiz agent's JSON output.

    The Quiz agent outputs JSON with a 'questions' array. Each question has:
      - type: "choice" | "fill" | "true_false"
      - question: str
      - answer: str
      - explanation: str
      - options: {"A": "...", ...} (choice only)

    Handles both the inner questions JSON directly and the outer
    resource-wrapper format.
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        # Try extracting JSON from markdown-wrapped text
        m = re.search(r'\{[\s\S]*\}', content)
        if m:
            try:
                data = json.loads(m.group())
            except json.JSONDecodeError:
                print(f"[exercise_parser] JSON parse failed even after regex extraction, content[:200]={content[:200]}", flush=True)
                return []
        else:
            print(f"[exercise_parser] No JSON-like structure found, content[:200]={content[:200]}", flush=True)
            return []

    # The content might be the outer wrapper: {"resource": {"content": "..."}}
    # or the inner questions JSON directly
    if isinstance(data, dict) and "resource" in data and isinstance(data["resource"], dict):
        inner_raw = data["resource"].get("content", "")
        if inner_raw and isinstance(inner_raw, str):
            try:
                inner = json.loads(inner_raw)
                data = inner
            except (json.JSONDecodeError, TypeError):
                # inner_raw might already be a dict if the LLM didn't stringify
                pass
        elif isinstance(inner_raw, dict):
            data = inner_raw

    questions_raw = data.get("questions", []) if isinstance(data, dict) else []

    if not questions_raw:
        print(f"[exercise_parser] No 'questions' key found, keys={list(data.keys()) if isinstance(data, dict) else 'N/A'}, content[:200]={str(data)[:200]}", flush=True)

    parsed: list[dict] = []
    for q in questions_raw:
        qtype = q.get("type", "")
        mapped_type = TYPE_MAP.get(qtype)
        if not mapped_type:
            continue

        options: list[str] = []
        if mapped_type == "choice" and isinstance(q.get("options"), dict):
            for letter in ["A", "B", "C", "D"]:
                if letter in q["options"]:
                    options.append(f"{letter}. {q['options'][letter]}")

        parsed.append({
            "question_type": mapped_type,
            "question": q.get("question", ""),
            "options": options,
            "answer": q.get("answer", ""),
            "explanation": q.get("explanation", ""),
        })

    return parsed
